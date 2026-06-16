from __future__ import annotations

import os
import cv2
import base64
import numpy as np
from core.data_packet import FlowableResult, VisionResultImage
from core.node_base import Property, PropertyGroupNames
from core.node_vision import VisionNodeData
from core.node_roi import ROINodeData


def _is_hidden_or_system(path: str) -> bool:
    """检查文件/目录是否为隐藏或系统文件。

    Windows: 通过 GetFileAttributesW 检查 FILE_ATTRIBUTE_HIDDEN (2)
             和 FILE_ATTRIBUTE_SYSTEM (4)。
    其他平台: 检查名称是否以 '.' 开头。
    """
    if os.name == 'nt':
        try:
            import ctypes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
            if attrs != -1 and attrs & (2 | 4):
                return True
        except FileNotFoundError:
            pass
        except OSError:
            import logging
            logging.getLogger(__name__).debug("无法获取文件属性: %s", path)
        return False
    return os.path.basename(path).startswith('.')


# =============================================================================
# SelectableResultImageNodeData - 选择使用哪个上游节点的结果图像
# =============================================================================

class SelectableResultImageNodeData(ROINodeData):
    """允许选择处理哪个上游节点的结果图像。"""

    def __init__(self):
        super().__init__()
        # 当前选中的结果图像
        self._selected_result_image: VisionResultImage | None = None

    @property
    def selected_result_image(self) -> VisionResultImage | None:
        """获取当前选中的结果图像"""
        return self._selected_result_image

    @selected_result_image.setter
    def selected_result_image(self, value: VisionResultImage | None):
        """设置当前选中的结果图像"""
        self._selected_result_image = value

    def get_selectable_src_node_datas(self) -> list[VisionResultImage]:
        """获取所有上游 VisionNodeData 节点的结果图像列表"""
        results: list[VisionResultImage] = []
        # 遍历所有上游节点
        for node in self.get_all_from_node_datas():
            # 如果是视觉节点，将其结果图像添加到列表中
            if isinstance(node, VisionNodeData):
                results.extend(node.result_images)
        return results


# =============================================================================
# OpenCVNodeDataBase - OpenCV特定的Mat处理
# =============================================================================

class OpenCVNodeDataBase(SelectableResultImageNodeData):
    """基于OpenCV的视觉节点基类。Mat就是numpy.ndarray。"""

    # 图像源选择属性：可选择使用"处理后图片"（上游节点输出）或"原图"（数据源原始图像）
    image_source_mode = Property(
        "处理后图片", name="图像源", group=PropertyGroupNames.BASE_PARAMETERS,
        description="选择输入图像来源：处理后图片(上游节点输出) 或 原图(数据源原始图像)",
        editor="choices", choices=["处理后图片", "原图"], order=1000,
    )

    def is_valid(self, mat: np.ndarray) -> bool:
        """检查输入图像是否有效：非空且包含数据"""
        return mat is not None and mat.size > 0

    def _update_result_image_source(self):
        """将numpy数组转换为可显示的格式（由GUI层处理）。

        在GUI中，这将转换为QImage/QPixmap。在核心层，我们存储numpy数组，
        让GUI层处理转换。
        """
        # 存储numpy数组作为结果图像源
        self._result_image_source = self._mat

    def to_dict(self) -> dict:
        """序列化节点为字典"""
        data = super().to_dict()
        # 保存选中的结果图像名称（如果有）
        if self._selected_result_image:
            data["selected_result_image"] = self._selected_result_image.name
        return data


# =============================================================================
# SrcFilesVisionNodeData - 基于文件的图像源节点
# =============================================================================

class SrcFilesVisionNodeData(ROINodeData):
    """从文件加载图像的节点基类。
    提供文件列表管理、图像属性（宽度/高度/颜色类型）。
    """

    # 图像宽度（只读，用于显示结果信息）
    pixel_width = Property(0, name="图像宽度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 图像高度（只读，用于显示结果信息）
    pixel_height = Property(0, name="图像高度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 颜色类型（只读，如灰度、RGB、BGR等）
    image_color_type = Property(0, name="颜色类型", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 是否使用所有图像（True：循环使用所有图像，False：只使用当前图像）
    use_all_image = Property(False, name="使用所有图像", group=PropertyGroupNames.RUN_PARAMETERS)
    # 是否自动切换（True：自动切换到下一张，False：手动切换）
    use_auto_switch = Property(True, name="自动切换", group=PropertyGroupNames.RUN_PARAMETERS)
    # 当前选中的文件路径
    src_file_path = Property("", name="当前文件", group=PropertyGroupNames.RUN_PARAMETERS)
    # 执行延迟（毫秒），用于控制连续执行时的帧率
    invoke_milliseconds_delay = Property(33, name="执行延迟", group=PropertyGroupNames.FLOW_PARAMETERS,
                                         description="连续执行时，每次采集图像的目标间隔（毫秒）。33ms≈30FPS，500ms≈2FPS")

    def __init__(self):
        super().__init__()
        # 文件路径列表（在 super().__init__ 之后初始化，确保 load_default 已执行）
        if not hasattr(self, 'src_file_paths'):
            self.src_file_paths: list[str] = []
        # 此节点可以作为流程起始节点
        self.use_start = True

    # 支持的图像文件扩展名列表
    _IMAGE_EXTENSIONS = (
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
        ".webp", ".svg", ".tga", ".dds", ".eps",
    )

    @classmethod
    def collect_image_files(cls, folder_path: str, recursive: bool = True,
                            image_extensions: tuple = None) -> list[str]:
        """从文件夹中收集所有图像文件，可选择是否递归扫描子目录。

        参数：
            folder_path: 要扫描的根文件夹路径
            recursive: 是否递归扫描子目录
            image_extensions: 覆盖默认的图像扩展名元组

        返回：
            匹配图像扩展名的文件绝对路径列表（已排序）
        """
        if image_extensions is None:
            image_extensions = cls._IMAGE_EXTENSIONS

        result: list[str] = []

        def _scan(directory: str):
            try:
                entries = os.listdir(directory)
            except (PermissionError, OSError):
                return

            for name in sorted(entries):
                full_path = os.path.join(directory, name)
                # 跳过隐藏和系统文件
                if _is_hidden_or_system(full_path):
                    continue

                if os.path.isdir(full_path):
                    if recursive:
                        _scan(full_path)
                elif name.lower().endswith(image_extensions):
                    result.append(full_path)

        _scan(folder_path)
        return result

    def add_files_from_folder(self, folder_path: str, recursive: bool = True,
                              image_extensions: tuple = None):
        """从文件夹添加所有图像文件
          - 默认递归扫描子目录
          - 跳过隐藏和系统文件
          - 仅当 SrcFilePath 之前为空时才设置它
        """
        new_files = self.collect_image_files(folder_path, recursive, image_extensions)
        if not new_files:
            return
        existing = set(self.src_file_paths)
        for f in new_files:
            if f not in existing:
                self.src_file_paths.append(f)
                existing.add(f)
        # 如果当前没有选中文件，则选中第一个
        if not self.src_file_path:
            self.src_file_path = self.src_file_paths[0]

    def add_files(self, file_paths: list[str]):
        """添加指定的图像文件"""
        existing = set(self.src_file_paths)
        for f in file_paths:
            if f not in existing:
                self.src_file_paths.append(f)
                existing.add(f)
        # 如果当前没有选中文件且列表非空，则选中第一个
        if self.src_file_paths and not self.src_file_path:
            self.src_file_path = self.src_file_paths[0]

    def clear_files(self):
        """清空所有文件路径"""
        self.src_file_paths.clear()
        self.src_file_path = ""

    def delete_current_file(self):
        """从列表中移除当前选中的文件"""
        if self.src_file_path and self.src_file_path in self.src_file_paths:
            idx = self.src_file_paths.index(self.src_file_path)
            self.src_file_paths.remove(self.src_file_path)
            if self.src_file_paths:
                # 选择前一个或第一个文件
                new_idx = min(idx, len(self.src_file_paths) - 1)
                self.src_file_path = self.src_file_paths[new_idx]
            else:
                self.src_file_path = ""

    def move_next(self) -> bool:
        """切换到列表中的下一个文件。返回是否成功循环。
          → 索引 = SrcFilePaths.IndexOf(SrcFilePath)
          → 索引 = 索引 < 总数-1 ? 索引+1 : 0
          → SrcFilePath = SrcFilePaths[索引]
        """
        if not self.src_file_paths:
            return False
        # 如果当前文件不在列表中，选中第一个
        if self.src_file_path not in self.src_file_paths:
            self.src_file_path = self.src_file_paths[0]
            return True
        idx = self.src_file_paths.index(self.src_file_path)
        next_idx = (idx + 1) % len(self.src_file_paths)
        # 如果循环到开头但不使用所有图像，则返回False
        if next_idx == 0 and not self.use_all_image:
            return False
        self.src_file_path = self.src_file_paths[next_idx]
        return True

    def move_prev(self) -> bool:
        """切换到列表中的上一个文件。返回是否成功循环。

        与 move_next() 相反方向，用于"上一张"单步导航。
        """
        if not self.src_file_paths:
            return False
        # 如果当前文件不在列表中，选中最后一个
        if self.src_file_path not in self.src_file_paths:
            self.src_file_path = self.src_file_paths[-1]
            return True
        idx = self.src_file_paths.index(self.src_file_path)
        prev_idx = idx - 1
        if prev_idx < 0:
            if not self.use_all_image:
                return False
            prev_idx = len(self.src_file_paths) - 1
        self.src_file_path = self.src_file_paths[prev_idx]
        return True

    def is_valid_file_list(self) -> tuple[bool, str]:
        """检查文件列表是否有效。返回 (是否有效, 消息)"""
        if not self.src_file_paths:
            return False, "请选择数据源中的图片"
        if self.src_file_path is None:
            self.src_file_path = self.src_file_paths[0]
        return self.src_file_path is not None, ""

    def load_default(self):
        """加载默认设置：从 assets/images 文件夹添加示例图片。

        注意：在打包部署（PyInstaller 等）或 zip 内运行时，
        assets/images 目录可能不存在，此时静默跳过。
        """
        super().load_default()
        try:
            assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "images")
            if os.path.isdir(assets_dir):
                self.add_files_from_folder(assets_dir)
        except Exception:
            pass
        self.src_file_path = ""

    def to_dict(self) -> dict:
        """序列化节点为字典"""
        data = super().to_dict()
        data["src_file_paths"] = list(self.src_file_paths)
        data["src_file_path"] = self.src_file_path
        data["use_all_image"] = self.use_all_image
        data["use_auto_switch"] = self.use_auto_switch
        data["invoke_milliseconds_delay"] = self.invoke_milliseconds_delay
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "SrcFilesVisionNodeData":
        """从字典反序列化节点。

        注意：工作流反序列化走 restore_from_dict 路径，此方法可能未被调用。
        """
        node = super().from_dict(data)
        node.src_file_paths = data.get("src_file_paths", [])
        node.src_file_path = data.get("src_file_path", "")
        return node


# =============================================================================
# Base64MatchingNodeData - 模板匹配基类
# =============================================================================

class Base64MatchingNodeData(VisionNodeData):
    """使用Base64编码模板图像的模板匹配节点的基类。"""

    # 匹配数量结果（只读）
    matching_count_result = Property(0, name="匹配数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 置信度结果（只读）
    confidence = Property(0.0, name="置信度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 是否匹配到目标（只读，供条件分支使用）
    matched = Property(False, name="是否匹配", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 匹配矩形坐标（只读）
    match_x = Property(0, name="匹配X", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_y = Property(0, name="匹配Y", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_w = Property(0, name="匹配宽度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_h = Property(0, name="匹配高度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        # Base64编码的模板图像字符串
        self._base64_string: str = ""

    def _on_post_invoke(self, result: FlowableResult):
        """匹配成功后，将匹配偏移量累加到 _crop_chain_offset。

        所有模板匹配节点（XFeat、SIFT、SURF、ORB、Template等）自动适配，
        无需逐个修改。
        """
        super()._on_post_invoke(result)
        if result.is_ok and self.matched and self.match_w > 0 and self.match_h > 0:
            prev = self._crop_chain_offset
            self._crop_chain_offset = (
                prev[0] + int(self.match_x),
                prev[1] + int(self.match_y),
                int(self.match_w),
                int(self.match_h),
            )

    @property
    def base64_string(self) -> str:
        """获取Base64编码的模板图像"""
        return self._base64_string

    @base64_string.setter
    def base64_string(self, value: str):
        """设置Base64编码的模板图像"""
        self._base64_string = value

    def set_template_from_image(self, image: np.ndarray):
        """将numpy图像编码为Base64字符串，用于模板存储。"""
        # 将图像编码为PNG格式
        _, buffer = cv2.imencode(".png", image)
        # 将二进制数据编码为Base64字符串
        self._base64_string = base64.b64encode(buffer).decode("utf-8")

    def get_template_image(self) -> np.ndarray | None:
        """将Base64模板解码为numpy图像。"""
        if not self._base64_string:
            return None

        # 将Base64字符串解码为二进制数据
        buffer = base64.b64decode(self._base64_string)
        # 将二进制数据转为numpy数组
        arr = np.frombuffer(buffer, dtype=np.uint8)
        # 解码为彩色图像
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    # ── ROI 暴露：将匹配结果作为下游可用的 ROI ──

    def get_active_roi_rect(self) -> tuple | None:
        """如果匹配成功，返回匹配矩形作为 ROI，供下游节点"来自上游"截取。"""
        if getattr(self, "matched", False):
            x, y, w, h = self.match_x, self.match_y, self.match_w, self.match_h
            if w > 0 and h > 0:
                return (int(x), int(y), int(w), int(h))
        return super().get_active_roi_rect()

    # ── 序列化 ──

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["base64_string"] = self._base64_string
        return data

    def restore_from_dict(self, data: dict) -> "Base64MatchingNodeData":
        super().restore_from_dict(data)
        self._base64_string = data.get("base64_string", "")
        return self

    @classmethod
    def from_dict(cls, data: dict) -> "Base64MatchingNodeData":
        node = super().from_dict(data)
        node._base64_string = data.get("base64_string", "")
        return node

"""分割提取节点：HSV色彩范围提取、按位与掩膜、无缝融合/背景替换"""

import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, VisionNodeData, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class HSVInRange(OpenCVNodeDataBase):
    """
    HSV色彩范围提取节点
    - 通过吸管工具取色确定目标颜色，配合容差参数自动计算 HSV 上下限
    - Lower 使用全容差（更宽边界），Upper 使用半容差（更窄边界）
    """
    # 节点所属分组（用于UI分类）
    __group__ = "图像分割提取模块"
    # 取色属性（hex格式，默认绿色 RGB:0,128,0 — 与WPF-VisionMaster一致）
    pick_color = Property("#008000", name="取色", group=PropertyGroupNames.RUN_PARAMETERS,
                          editor="color", description="吸管工具取色，确定HSV提取的中心颜色")
    # 色相容差范围（对应WPF hRange，默认35，范围0-85）
    h_range = Property(35, name="色相范围(H)", group=PropertyGroupNames.RUN_PARAMETERS,
                       min_val=0, max_val=85,
                       description="以取色点为中心的色相容差，值越大匹配的色相范围越宽")
    # 饱和度容差范围（对应WPF sRange，默认30，范围0-255）
    s_range = Property(30, name="饱和度范围(S)", group=PropertyGroupNames.RUN_PARAMETERS,
                       min_val=0, max_val=255,
                       description="以取色点为中心的饱和度容差，值越大匹配的饱和度范围越宽")
    # 明度容差范围（对应WPF vRange，默认30，范围0-255）
    v_range = Property(30, name="明度范围(V)", group=PropertyGroupNames.RUN_PARAMETERS,
                       min_val=0, max_val=255,
                       description="以取色点为中心的明度容差，值越大匹配的明度范围越宽")

    def __init__(self):
        """初始化HSV色彩提取节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "HSV色彩提取"

    def _hex_to_bgr_pixel(self) -> np.ndarray:
        """将取色hex字符串转换为BGR像素数组（用于cv2.cvtColor）"""
        hex_color = (self.pick_color or "#008000").lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return np.array([[[b, g, r]]], dtype=np.uint8)

    def _get_hsv_range(self) -> tuple[np.ndarray, np.ndarray]:
        """根据取色和容差参数计算 HSV 上下限

        参考 WPF-VisionMaster OpenvCVExtension.GetHSVRange:
        1. 将取色 BGR 像素转为 OpenCV HSV
        2. 从 OpenCV 尺度(0-179,0-255,0-255)转到 WPF 内部尺度(0-360,0-100,0-100)
        3. Lower 用全容差、Upper 用半容差
        4. 转回 OpenCV 尺度生成 inRange 所需的 lower/upper 数组
        """
        bgr = self._hex_to_bgr_pixel()
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0, 0]
        h, s, v = int(hsv[0]), int(hsv[1]), int(hsv[2])

        # 转到 WPF 内部尺度
        h_wpf = h * 2              # OpenCV[0,179] → WPF[0,360]
        s_wpf = s / 2.55           # OpenCV[0,255] → WPF[0,100]
        v_wpf = v / 2.55

        hr, sr, vr = self.h_range, self.s_range, self.v_range

        # Lower: 全容差（更宽的下边界）
        l_h_min = max(0, h_wpf - hr)
        l_s_min = max(0, s_wpf - sr)
        l_v_min = max(0, v_wpf - vr)

        # Upper: 半容差（更窄的上边界）
        u_h_max = min(360, h_wpf + hr / 2)
        u_s_max = min(100, s_wpf + sr / 2)
        u_v_max = min(100, v_wpf + vr / 2)

        lower = np.array([l_h_min / 2, l_s_min * 2.55, l_v_min * 2.55], dtype=np.uint8)
        upper = np.array([u_h_max / 2, u_s_max * 2.55, u_v_max * 2.55], dtype=np.uint8)

        return lower, upper

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src: 源节点数据
            from_node: 上游节点
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 保存输入图像副本供吸管取色使用（对应WPF: ImageColorPickerPresenter.ImageSource = from.Mat.ToImageSource()）
        self._picker_mat = mat.copy()
        # 根据取色和容差计算 HSV 范围
        lower, upper = self._get_hsv_range()
        # 将图像从BGR转换为HSV色彩空间
        hsv = cv2.cvtColor(mat, cv2.COLOR_BGR2HSV)
        # 根据HSV阈值范围创建掩膜
        mask = cv2.inRange(hsv, lower, upper)
        # 返回成功结果
        return self.ok(mask, "HSV色彩范围提取完成")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class BitwiseAnd(OpenCVNodeDataBase):
    """按位与掩膜节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像分割提取模块"

    def __init__(self):
        """初始化按位与掩膜节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "按位与掩膜"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src: 源节点数据
            from_node: 上游节点
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 初始化掩膜为None
        mask = None
        # 遍历上游节点，查找掩膜图像（单通道灰度图）
        for n in self.from_node_datas:
            if isinstance(n, VisionNodeData) and n.mat is not None and len(n.mat.shape) == 2:
                mask = n.mat
                break
        # 如果没有找到掩膜输入，返回原图
        if mask is None:
            return self.ok(mat, "无掩膜输入，保持原图")
        # 对原图和掩膜执行按位与操作
        result = cv2.bitwise_and(mat, mat, mask=mask)
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class SeamlessCloneBackground(OpenCVNodeDataBase):
    """无缝融合/背景替换节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像分割提取模块"
    # 融合方式属性
    clone_type = Property("NORMAL_CLONE", name="融合方式", group=PropertyGroupNames.RUN_PARAMETERS)
    # 中心点X坐标属性
    center_x = Property(0, name="中心X", group=PropertyGroupNames.RUN_PARAMETERS)
    # 中心点Y坐标属性
    center_y = Property(0, name="中心Y", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化无缝融合节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "无缝融合/背景替换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src: 源节点数据（背景图像）
            from_node: 上游节点（前景图像）
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 获取输入图像（前景）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 如果没有背景图像，返回原图
        if src is None or src.mat is None:
            return self.ok(mat, "无背景图像，保持原图")
        # 融合方式映射字典
        clone_map = {
            "NORMAL_CLONE": cv2.NORMAL_CLONE,           # 普通克隆
            "MIXED_CLONE": cv2.MIXED_CLONE,             # 混合克隆
            "MONOCHROME_TRANSFER": cv2.MONOCHROME_TRANSFER  # 单色转移
        }
        # 创建全白掩膜（与前景图像相同尺寸）
        mask = np.ones(mat.shape[:2], dtype=np.uint8) * 255
        # 计算融合中心点（如果未指定，使用图像中心）
        cx = self.center_x or mat.shape[1] // 2
        cy = self.center_y or mat.shape[0] // 2
        # 执行无缝融合
        result = cv2.seamlessClone(mat, src.mat, mask, (cx, cy),
                                    clone_map.get(self.clone_type, cv2.NORMAL_CLONE))
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat
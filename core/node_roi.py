"""
ROI (Region of Interest) node classes
Extracted from core/node_base.py

Defines: ROIBase, FromROI, DrawROI, InputROI, NoROI, ROINodeData
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from core.data_packet import FlowableResult
from core.node_base import LinkData, NodeBase
from core.node_vision import VisionNodeData

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


# =============================================================================
# ROINodeData - ROI支持（NoROI / DrawROI / FromROI / InputROI）
# =============================================================================

class ROIBase:
    """ROI定义的基类。"""

    def __init__(self, roi_type: str = ""):
        # ROI名称，未指定时使用类名
        self.name = roi_type or self.__class__.__name__

    def to_dict(self) -> dict:
        """序列化ROI对象为字典"""
        return {"type": self.__class__.__name__, "name": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> "ROIBase":
        """从字典反序列化创建ROI对象"""
        # 获取ROI类型
        roi_type = data.get("type", "ROIBase")

        # NoROI：无ROI区域
        if roi_type == "NoROI":
            return NoROI()

        # DrawROI：用户绘制的ROI区域
        if roi_type == "DrawROI":
            roi = DrawROI()
            roi.rect = tuple(data.get("rect", roi.rect))
            return roi

        # InputROI：手动输入的ROI区域（坐标+宽高）
        if roi_type == "InputROI":
            roi = InputROI()
            roi.x = int(data.get("x", roi.x))
            roi.y = int(data.get("y", roi.y))
            roi.width = int(data.get("width", roi.width))
            roi.height = int(data.get("height", roi.height))
            return roi

        # FromROI：来自上游节点的ROI
        return FromROI()


class FromROI(ROIBase):
    """从上游节点获取的ROI区域。"""

    def __init__(self, source_node: NodeBase = None):
        # 调用父类构造函数，设置ROI名称为"使用上游ROI"
        super().__init__("使用上游ROI")
        # ROI来源节点（上游节点）
        self.source_node = source_node


class DrawROI(ROIBase):
    """在图像上交互式绘制的ROI区域。"""

    def __init__(self):
        super().__init__("绘制ROI")
        self.image_source: Any = None
        self.rect: tuple | None = None  # None=未绘制，等用户在编辑器中画

    def to_dict(self) -> dict:
        """序列化为字典"""
        data = super().to_dict()
        # 将矩形区域转为列表存储
        data["rect"] = list(self.rect or (0, 0, 100, 100))
        return data


class InputROI(ROIBase):
    """手动输入数值的ROI区域。"""

    def __init__(self):
        # 调用父类构造函数，设置ROI名称为"输入ROI"
        super().__init__("输入ROI")
        # 左上角X坐标
        self.x: int = 0
        # 左上角Y坐标
        self.y: int = 0
        # ROI宽度
        self.width: int = 100
        # ROI高度
        self.height: int = 100

    def to_dict(self) -> dict:
        """序列化为字典"""
        data = super().to_dict()
        # 添加坐标和尺寸信息
        data.update({
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        })
        return data


class NoROI(ROIBase):
    """无ROI — 不应用任何感兴趣区域。"""

    def __init__(self):
        # 调用父类构造函数，设置ROI名称为"无"
        super().__init__("无")


class ROINodeData(VisionNodeData):
    """
    为视觉节点添加ROI支持。
    支持四种ROI模式：NoROI（无）、FromROI（上游）、DrawROI（交互绘制）、InputROI（手动输入）。
    默认使用 NoROI，以防止意外的ROI级联传递。
    """

    def __init__(self):
        super().__init__()
        # 无ROI模式实例
        self.no_roi = NoROI()
        # 使用上游ROI模式实例，源节点指向自身
        self.from_roi = FromROI(source_node=self)
        # 绘制ROI模式实例
        self.draw_roi = DrawROI()
        # 输入ROI模式实例
        self.input_roi = InputROI()
        # 当前激活的ROI，默认为无ROI
        self._roi: ROIBase = self.no_roi

    @property
    def roi(self) -> ROIBase:
        """获取当前激活的ROI"""
        return self._roi

    @roi.setter
    def roi(self, value: ROIBase):
        """设置当前激活的ROI"""
        self._roi = value

    def get_rois(self) -> list[ROIBase]:
        """获取所有可用的ROI选项"""
        # 更新绘制ROI的图像源为当前结果图像
        self.draw_roi.image_source = self._result_image_source
        # 返回所有ROI选项列表
        return [self.no_roi, self.from_roi, self.draw_roi, self.input_roi]

    def get_active_roi_rect(self) -> tuple | None:
        """获取当前激活的ROI矩形区域，返回 (x, y, w, h) 或 None"""
        # 无ROI模式：返回None
        if isinstance(self._roi, NoROI):
            return None
        # 绘制ROI模式：返回绘制的矩形区域
        if isinstance(self._roi, DrawROI):
            if self._roi.rect:
                return self._roi.rect
        # 输入ROI模式：返回手动输入的坐标和尺寸
        elif isinstance(self._roi, InputROI):
            return (self._roi.x, self._roi.y, self._roi.width, self._roi.height)
        # 使用上游ROI模式：递归向上游节点获取ROI
        elif isinstance(self._roi, FromROI):
            src = self._roi.source_node
            if isinstance(src, ROINodeData) and src is not self:
                return src.get_active_roi_rect()
        return None

    @staticmethod
    def _validate_roi_rect(roi_rect: tuple | None,
                           input_mat: "np.ndarray | None") -> tuple | None:
        """验证 ROI 矩形并裁剪到图像边界内。返回 (x,y,w,h) 或 None。"""
        if roi_rect is None or input_mat is None:
            return None
        x, y, w, h = int(roi_rect[0]), int(roi_rect[1]), int(roi_rect[2]), int(roi_rect[3])
        h_img, w_img = input_mat.shape[:2]
        x, y = max(0, x), max(0, y)
        w, h = min(w, w_img - x), min(h, h_img - y)
        if w <= 0 or h <= 0:
            return None
        return (x, y, w, h)

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        """执行节点处理，支持ROI裁剪"""
        # 查找上游节点
        from_data = self._find_from_node(diagram, previors)

        # 为 FromROI 模式连接上游ROI
        if isinstance(from_data, ROINodeData) and from_data is not self:
            self.from_roi.source_node = from_data

        # 传递上游的原始图像
        if isinstance(from_data, VisionNodeData):
            upstream_original = getattr(from_data, '_original_mat', None)
            if upstream_original is not None:
                self._original_mat = upstream_original
            elif from_data.mat is not None:
                self._original_mat = from_data.mat.copy()

        # 传播上游累积裁剪偏移量
        upstream_offset = getattr(from_data, '_crop_chain_offset', (0, 0, 0, 0))

        # 根据图像源模式确定有效的输入图像
        # "原图"模式优先：即使上游mat为None，也能用完整原图
        if hasattr(self, 'image_source_mode') and self.image_source_mode == "原图" and self._original_mat is not None:
            input_mat = self._original_mat
        elif from_data is not None and from_data.mat is not None:
            input_mat = from_data.mat
        else:
            input_mat = None

        # 获取当前节点的ROI矩形并验证裁剪到图像边界内
        roi_rect = self.get_active_roi_rect() if not isinstance(self._roi, NoROI) else None
        roi_rect = self._validate_roi_rect(roi_rect, input_mat)

        # 有ROI时的处理
        if roi_rect is not None:
            x, y, w, h = roi_rect
            # 累积裁剪偏移量：上游偏移 + 本次ROI偏移
            self._crop_chain_offset = (upstream_offset[0] + x, upstream_offset[1] + y, w, h)
            self._prepared_input = input_mat[y:y+h, x:x+w]
            result = super().invoke(previors, diagram)
            self._prepared_input = None
        else:
            # 无ROI时透传上游偏移量
            self._crop_chain_offset = upstream_offset
            if from_data is not None and input_mat is not from_data.mat:
                self._prepared_input = input_mat
                result = super().invoke(previors, diagram)
                self._prepared_input = None
            else:
                result = super().invoke(previors, diagram)

        # 更新绘制ROI的图像源
        self.draw_roi.image_source = self._result_image_source
        return result

    def to_dict(self) -> dict:
        """序列化节点为字典"""
        data = super().to_dict()
        # 保存当前ROI配置
        data["roi"] = self._roi.to_dict() if self._roi is not None else None
        return data

    def restore_from_dict(self, data: dict) -> "ROINodeData":
        """从字典反序列化恢复节点状态"""
        super().restore_from_dict(data)
        roi_data = data.get("roi")
        if roi_data:
            self._roi = ROIBase.from_dict(roi_data)
        # 将反序列化的ROI替换为实例中的对应对象
        if isinstance(self._roi, NoROI):
            self._roi = self.no_roi
        elif isinstance(self._roi, DrawROI):
            r = tuple(self._roi.rect) if self._roi.rect else None
            if r == (0, 0, 100, 100):
                r = None  # 忽略旧版预设值
            self.draw_roi.rect = r
            self._roi = self.draw_roi
        elif isinstance(self._roi, InputROI):
            self.input_roi.x = int(self._roi.x)
            self.input_roi.y = int(self._roi.y)
            self.input_roi.width = int(self._roi.width)
            self.input_roi.height = int(self._roi.height)
            self._roi = self.input_roi
        elif isinstance(self._roi, FromROI):
            self._roi = self.from_roi
        else:
            self._roi = self.no_roi
        return self

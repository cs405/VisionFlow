"""
ROI (Region of Interest) node classes
Extracted from core/node_base.py

Defines: ROIBase, FromROI, DrawROI, InputROI, NoROI, ROINodeData
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from core.data_packet import FlowableResult
from core.node_base import LinkData, NodeBase
from core.node_vision import VisionNodeData

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


IMAGE_SOURCE_ORIGINAL = "原图"

# =============================================================================
# ROINodeData - ROI支持（NoROI / DrawROI / FromROI / InputROI）
# =============================================================================

class ROIBase:
    """ROI定义的基类。"""

    _roi_registry: dict[str, type] = {}  # 子类自动注册

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        ROIBase._roi_registry[cls.__name__] = cls
        NodeBase.register_deserializer(cls.__name__, ROIBase.from_dict)

    @classmethod
    def unregister(cls, name: str):
        """从注册表中移除一个 ROI 类型。"""
        cls._roi_registry.pop(name, None)

    def __init__(self, roi_type: str = ""):
        self.name = roi_type or self.__class__.__name__

    def to_dict(self) -> dict:
        return {"type": self.__class__.__name__, "name": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> "ROIBase":
        roi_type = data.get("type", "ROIBase")        # 默认类型
        roi_cls = cls._roi_registry.get(roi_type, FromROI)        # 默认使用 FromROI, 来自上游ROI
        return roi_cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> "ROIBase":
        """子类可重写以处理自身特有字段的反序列化。"""
        return cls()


class FromROI(ROIBase):
    """从上游节点获取的ROI区域，继承"""
    def __init__(self, source_node: NodeBase = None):
        super().__init__("使用上游ROI")
        self.source_node = source_node  # 上游节点引用
        self._source_node_id: str = ""  # 序列化时保存，反序列化后由 load_data 恢复

    def to_dict(self) -> dict:
        data = super().to_dict()                               # 获取基类的字典表示
        if self.source_node is not None:                       # 如果有上游节点，保存其 ID
            data["source_node_id"] = self.source_node.node_id  # 保存上游节点的 ID
        return data


class DrawROI(ROIBase):
    """在图像上交互式绘制的ROI区域"""

    def __init__(self):
        super().__init__("绘制ROI")
        self.image_source: Any = None   # 图像数据源（可以是节点输出的图像数据）
        self.rect: tuple | None = None  # None=未绘制，等用户在编辑器中画
        self.roi_type: str = "矩形"     # ROI类型：矩形/旋转矩形/圆形
        self.angle: float = 0.0         # 旋转角度（仅旋转矩形有效）

    def to_dict(self) -> dict:
        """序列化为字典"""
        data = super().to_dict()
        data["rect"] = list(self.rect)  # 将矩形区域转为列表存储
        data["roi_type"] = self.roi_type
        data["angle"] = self.angle
        return data

    @classmethod
    def _from_dict(cls, data: dict) -> "DrawROI":
        """反序列化 DrawROI，恢复 rect 字段。"""
        roi = cls()
        raw = data.get("rect")
        roi.rect = tuple(raw) if raw else None
        roi.roi_type = data.get("roi_type", "矩形")
        roi.angle = data.get("angle", 0.0)
        return roi


class InputROI(ROIBase):
    """手动输入数值的ROI区域。"""
    def __init__(self):
        # 调用父类构造函数，设置ROI名称为"输入ROI"
        super().__init__("输入ROI")
        self.x: int = None       # 左上角X坐标
        self.y: int = None       # 左上角Y坐标
        self.width: int = None   # ROI宽度
        self.height: int = None  # ROI高度

    def to_dict(self) -> dict:
        """序列化为字典"""
        data = super().to_dict()  # 获取基类的字典表示
        # 更新坐标和尺寸信息
        data.update({
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        })
        return data

    @classmethod
    def _from_dict(cls, data: dict) -> "InputROI":
        """反序列化 InputROI，恢复坐标和尺寸字段。"""
        roi = cls()
        roi.x = int(data.get("x", roi.x))
        roi.y = int(data.get("y", roi.y))
        roi.width = int(data.get("width", roi.width))
        roi.height = int(data.get("height", roi.height))
        return roi


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
        self.no_roi = NoROI()  # 无ROI模式实例
        self.from_roi = FromROI(source_node=self)  # 使用上游ROI模式实例，源节点指向自身
        self.draw_roi = DrawROI()                  # 绘制ROI模式实例
        self.input_roi = InputROI()                # 输入ROI模式实例
        self._roi: ROIBase = self.no_roi           # 当前激活的ROI，默认为无ROI

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
        return [self.no_roi, self.from_roi, self.draw_roi, self.input_roi]

    def get_active_roi_rect(self) -> tuple | None:
        """获取当前激活的ROI矩形区域，返回 (x, y, w, h) 或 None"""
        if isinstance(self._roi, NoROI):  # 无ROI模式：返回None
            return None
        if isinstance(self._roi, DrawROI):  # 绘制ROI模式：返回绘制的矩形区域
            if self._roi.rect:
                return self._roi.rect
        elif isinstance(self._roi, InputROI):  # 输入ROI模式：返回手动输入的坐标和尺寸
            return self._roi.x, self._roi.y, self._roi.width, self._roi.height
        elif isinstance(self._roi, FromROI):  # 使用上游ROI模式：递归向上游节点获取ROI
            src = self._roi.source_node
            if isinstance(src, ROINodeData) and src is not self:
                return src.get_active_roi_rect()
        return None

    @staticmethod
    def _validate_roi_rect(roi_rect: tuple | None,
                           input_mat: np.ndarray | None) -> tuple | None:
        """验证 ROI 矩形并裁剪到图像边界内。返回 (x,y,w,h) 或 None。"""
        if roi_rect is None or input_mat is None:
            return None
        x, y, w, h = int(roi_rect[0]), int(roi_rect[1]), int(roi_rect[2]), int(roi_rect[3])
        h_img, w_img = input_mat.shape[:2]
        x, y = max(0, x), max(0, y)
        w, h = min(w, w_img - x), min(h, h_img - y)
        if w <= 0 or h <= 0:
            return None
        return x, y, w, h

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        """Execute node processing with ROI cropping support."""
        from_data = self._find_from_node(diagram, previors)

        if isinstance(from_data, ROINodeData) and from_data is not self:
            if self.from_roi.source_node is self:
                self.from_roi.source_node = from_data

        if isinstance(from_data, VisionNodeData):
            self._propagate_upstream_state(from_data)

        upstream_offset = getattr(from_data, '_crop_chain_offset', (0, 0, 0, 0))
        input_mat = self._resolve_input_mat(from_data)
        roi_rect = self.get_active_roi_rect() if not isinstance(self._roi, NoROI) else None
        roi_rect = self._validate_roi_rect(roi_rect, input_mat)

        result = self._invoke_with_roi(previors, diagram, input_mat, roi_rect, upstream_offset, from_data)
        self.draw_roi.image_source = self._result_image_source
        return result

    def _resolve_input_mat(self, from_data):
        """Determine the effective input mat based on image source mode."""
        if hasattr(self, 'image_source_mode') and self.image_source_mode == IMAGE_SOURCE_ORIGINAL and self._original_mat is not None:
            return self._original_mat
        if from_data is not None and from_data.mat is not None:
            return from_data.mat
        return None

    def _invoke_with_roi(self, previors, diagram, input_mat, roi_rect, upstream_offset, from_data):
        """Apply ROI cropping then invoke, or passthrough if no ROI."""
        if roi_rect is not None:
            x, y, w, h = roi_rect
            self._crop_chain_offset = (upstream_offset[0] + x, upstream_offset[1] + y, w, h)
            self._prepared_input = input_mat[y:y+h, x:x+w]
            try:
                return super().invoke(previors, diagram)
            finally:
                self._prepared_input = None

        self._crop_chain_offset = upstream_offset
        if from_data is not None and input_mat is not from_data.mat:
            self._prepared_input = input_mat
            try:
                return super().invoke(previors, diagram)
            finally:
                self._prepared_input = None
        return super().invoke(previors, diagram)

    def invoke_core(self, src_image_node_data: "VisionNodeData | None",
                    from_node_data: "VisionNodeData | None",
                    diagram: "WorkflowEngine") -> FlowableResult:
        """ROI 裁剪已在 invoke() 中完成，此处为无处理直通。"""
        return FlowableResult()

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
            self.draw_roi.rect = tuple(self._roi.rect) if self._roi.rect else None
            self.draw_roi.roi_type = getattr(self._roi, 'roi_type', '矩形')
            self.draw_roi.angle = getattr(self._roi, 'angle', 0.0)
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

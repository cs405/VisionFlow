"""Output nodes: OK, NG, and various notification message outputs."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult, FlowableResultState
from core.workflow import WorkflowEngine
from core.events import EventType, event_system


class _OutputBase(OpenCVNodeDataBase):
    """Base for output nodes that pass through the image."""
    __group__ = "结果输出模块"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        msg = self._get_message()
        event_system.publish(self._event_type, sender=self, message=msg)
        return self.ok(mat, msg)

    def _get_message(self) -> str:
        return ""

    @property
    def _event_type(self) -> EventType:
        return EventType.MESSAGE_INFO

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class OKOutputNode(_OutputBase):
    __group__ = "结果输出模块"
    def __init__(self): super().__init__(); self.name = "OK输出"
    def _get_message(self): return "OK"
    @property
    def _event_type(self): return EventType.MESSAGE_SUCCESS


class NGOutputNode(_OutputBase):
    __group__ = "结果输出模块"
    def __init__(self): super().__init__(); self.name = "NG输出"
    def _get_message(self): return "NG"
    @property
    def _event_type(self): return EventType.MESSAGE_ERROR


class ShowInfoOutputNode(_OutputBase):
    __group__ = "结果输出模块"
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "信息提示"
    def _get_message(self): return self.message or "信息提示"
    @property
    def _event_type(self): return EventType.MESSAGE_INFO


class ShowSuccessOutputNode(_OutputBase):
    __group__ = "结果输出模块"
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "成功提示"
    def _get_message(self): return self.message or "操作成功"
    @property
    def _event_type(self): return EventType.MESSAGE_SUCCESS


class ShowWarnOutputNode(_OutputBase):
    __group__ = "结果输出模块"
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "警告提示"
    def _get_message(self): return self.message or "警告"
    @property
    def _event_type(self): return EventType.MESSAGE_WARN


class ShowErrorOutputNode(_OutputBase):
    __group__ = "结果输出模块"
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "错误提示"
    def _get_message(self): return self.message or "发生错误"
    @property
    def _event_type(self): return EventType.MESSAGE_ERROR


class ShowFatalOutputNode(_OutputBase):
    __group__ = "结果输出模块"
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "严重提示"
    def _get_message(self): return self.message or "严重错误"

    @property
    def _event_type(self): return EventType.MESSAGE_ERROR

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        msg = self._get_message()
        event_system.publish(EventType.MESSAGE_ERROR, sender=self, message=msg)
        return FlowableResult(mat, msg, FlowableResultState.ERROR)


class ShowDialogOutputNode(_OutputBase):
    __group__ = "结果输出模块"
    message = Property("", name="对话框消息", group=PropertyGroupNames.RUN_PARAMETERS)
    title = Property("提示", name="对话框标题", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "弹窗提示"
    def _get_message(self): return self.message or "弹窗消息"

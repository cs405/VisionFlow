from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult, FlowableResultState
from core.events import EventType, event_system
from nodes.outputs.output_base import OutputBase


class ShowInfoOutputNode(OutputBase):
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "信息提示"
    def _get_message(self) -> str: return self.message or "信息提示"
    @property
    def _event_type(self) -> EventType: return EventType.MESSAGE_INFO


class ShowSuccessOutputNode(OutputBase):
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "成功提示"
    def _get_message(self) -> str: return self.message or "操作成功"
    @property
    def _event_type(self) -> EventType: return EventType.MESSAGE_SUCCESS


class ShowWarnOutputNode(OutputBase):
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "警告提示"
    def _get_message(self) -> str: return self.message or "警告"
    @property
    def _event_type(self) -> EventType: return EventType.MESSAGE_WARN


class ShowErrorOutputNode(OutputBase):
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "错误提示"
    def _get_message(self) -> str: return self.message or "发生错误"
    @property
    def _event_type(self) -> EventType: return EventType.MESSAGE_ERROR


class ShowFatalOutputNode(OutputBase):
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "严重提示"
    @property
    def _event_type(self) -> EventType: return EventType.MESSAGE_ERROR
    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        msg = self._get_message()
        event_system.publish(EventType.MESSAGE_ERROR, sender=self, message=msg)
        return FlowableResult(mat, msg, FlowableResultState.ERROR)


class ShowDialogOutputNode(OutputBase):
    message = Property("", name="对话框消息", group=PropertyGroupNames.RUN_PARAMETERS)
    title = Property("提示", name="对话框标题", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "弹窗提示"
    def _get_message(self) -> str: return self.message or "弹窗消息"

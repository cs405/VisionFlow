import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase
from core.data_packet import FlowableResult, FlowableResultState
from core.events import EventType, event_system


class OutputBase(OpenCVNodeDataBase):
    """输出节点基类，透传图像并发布事件"""
    __group__ = "结果输出模块"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
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

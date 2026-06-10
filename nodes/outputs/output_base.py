"""输出节点基类 — 透传图像。通知节点显示 Qt 消息框 (对应 WPF IocMessage.Notify)。"""

from PyQt5.QtWidgets import QMessageBox
from core.node_base import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class OutputBase(OpenCVNodeDataBase):
    """输出节点基类"""
    __group__ = "结果输出模块"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        return self.ok(mat, self._get_message())

    def _get_message(self) -> str:
        return ""

    def _update_result_image_source(self):
        self._result_image_source = self._mat


def _show_msgbox(icon: QMessageBox.Icon, title: str, text: str):
    """显示 Qt 消息框 — 对应 WPF IocMessage.Notify.ShowXXX"""
    msg = QMessageBox()
    msg.setIcon(icon)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()

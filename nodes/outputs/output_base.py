"""输出节点基类 — 透传图像。通知节点显示 Qt 消息框"""

from PyQt5.QtWidgets import QMessageBox
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class OutputBase(OpenCVNodeDataBase):
    """输出节点基类"""
    __group__ = "结果输出模块"

    result_message = Property("OK", name="输出消息", group=PropertyGroupNames.RUN_PARAMETERS,
                              description="显示/返回的消息文本")
    result_success = Property(True, name="判定为成功", group=PropertyGroupNames.RUN_PARAMETERS,
                              description="开启时返回 OK 状态，关闭时返回 ERROR 状态")

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if self.result_success:
            return self.ok(mat, self._get_message())
        else:
            return self.error(mat, self._get_message())

    def _get_message(self) -> str:
        return self.result_message


def _show_msgbox(icon: QMessageBox.Icon, title: str, text: str):
    """显示 Qt 消息框"""
    msg = QMessageBox()
    msg.setIcon(icon)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()

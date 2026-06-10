"""通知输出节点 — ShowInfo/Success/Warn/Error/Fatal/Dialog。显示 Qt 消息框。"""

from PyQt5.QtWidgets import QMessageBox
from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.outputs.output_base import OutputBase, _show_msgbox


class ShowInfoOutputNode(OutputBase):
    message = Property("运行信息", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "信息提示"
    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        _show_msgbox(QMessageBox.Information, "信息", self.message or "运行信息")
        return self.ok(mat, self.message or "运行信息")


class ShowSuccessOutputNode(OutputBase):
    message = Property("操作成功", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "成功提示"
    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        _show_msgbox(QMessageBox.Information, "成功", self.message or "操作成功")
        return self.ok(mat, self.message or "操作成功")


class ShowWarnOutputNode(OutputBase):
    message = Property("警告", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "警告提示"
    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        _show_msgbox(QMessageBox.Warning, "警告", self.message or "警告")
        return self.ok(mat, self.message or "警告")


class ShowErrorOutputNode(OutputBase):
    message = Property("发生错误", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "错误提示"
    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        _show_msgbox(QMessageBox.Critical, "错误", self.message or "发生错误")
        return self.ok(mat, self.message or "发生错误")


class ShowFatalOutputNode(OutputBase):
    message = Property("运行严重错误", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "严重提示"
    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        _show_msgbox(QMessageBox.Critical, "严重错误", self.message or "运行严重错误")
        return self.error(mat, self.message or "运行严重错误")


class ShowDialogOutputNode(OutputBase):
    """对话框, 取消时中断流程。"""
    message = Property("是否继续运行流程", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    title = Property("提示", name="对话框标题", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "弹窗提示"
    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        reply = QMessageBox.question(None, self.title or "提示",
                                      self.message or "是否继续?",
                                      QMessageBox.Ok | QMessageBox.Cancel)
        if reply == QMessageBox.Cancel:
            return self.error(mat, "用户取消运行流程")
        return self.ok(mat, self.message or "弹窗消息")

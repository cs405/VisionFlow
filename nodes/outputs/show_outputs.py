"""通知输出节点 — 统一的 ShowMessageNode + 向后兼容的薄子类。"""

from PyQt5.QtWidgets import QMessageBox
from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.outputs.output_base import OutputBase, _show_msgbox

# ── 统一参数化节点 ──────────────────────────────────────────────

class ShowMessageNode(OutputBase):
    """统一消息输出节点：通过 message_type 属性切换六种类型。"""

    message_type = Property(
        "Info", name="消息类型", group=PropertyGroupNames.RUN_PARAMETERS,
        editor="choices",
        choices=["Info", "Success", "Warn", "Error", "Fatal", "Dialog"],
    )
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)
    title = Property("", name="对话框标题", group=PropertyGroupNames.RUN_PARAMETERS)

    _ICON_MAP = {
        "Info": QMessageBox.Information,
        "Success": QMessageBox.Information,
        "Warn": QMessageBox.Warning,
        "Error": QMessageBox.Critical,
        "Fatal": QMessageBox.Critical,
        "Dialog": QMessageBox.Question,
    }
    _DEFAULTS = {
        "Info":    {"title": "信息",     "text": "运行信息"},
        "Success": {"title": "成功",     "text": "操作成功"},
        "Warn":    {"title": "警告",     "text": "警告"},
        "Error":   {"title": "错误",     "text": "发生错误"},
        "Fatal":   {"title": "严重错误", "text": "运行严重错误"},
        "Dialog":  {"title": "提示",     "text": "是否继续运行流程"},
    }
    _NAMES = {
        "Info": "信息提示", "Success": "成功提示", "Warn": "警告提示",
        "Error": "错误提示", "Fatal": "严重提示", "Dialog": "弹窗提示",
    }

    def __init__(self):
        super().__init__()
        self.name = self._NAMES.get(self.message_type, "消息输出")

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        mt = self.message_type or "Info"
        defaults = self._DEFAULTS.get(mt, self._DEFAULTS["Info"])
        title = self.title or defaults["title"]
        text = self.message or defaults["text"]

        if mt == "Dialog":
            reply = QMessageBox.question(None, title, text,
                                         QMessageBox.Ok | QMessageBox.Cancel)
            if reply == QMessageBox.Cancel:
                return self.error(mat, "用户取消运行流程")
            return self.ok(mat, text)

        icon = self._ICON_MAP.get(mt, QMessageBox.Information)
        _show_msgbox(icon, title, text)
        if mt == "Fatal":
            return self.error(mat, text)
        return self.ok(mat, text)


# ── 向后兼容：保留旧类名作为薄子类 ──────────────────────────────

class ShowInfoOutputNode(ShowMessageNode):
    def __init__(self):
        super().__init__()
        self.message_type = "Info"
        self.name = "信息提示"

class ShowSuccessOutputNode(ShowMessageNode):
    def __init__(self):
        super().__init__()
        self.message_type = "Success"
        self.name = "成功提示"

class ShowWarnOutputNode(ShowMessageNode):
    def __init__(self):
        super().__init__()
        self.message_type = "Warn"
        self.name = "警告提示"

class ShowErrorOutputNode(ShowMessageNode):
    def __init__(self):
        super().__init__()
        self.message_type = "Error"
        self.name = "错误提示"

class ShowFatalOutputNode(ShowMessageNode):
    def __init__(self):
        super().__init__()
        self.message_type = "Fatal"
        self.name = "严重提示"

class ShowDialogOutputNode(ShowMessageNode):
    def __init__(self):
        super().__init__()
        self.message_type = "Dialog"
        self.name = "弹窗提示"

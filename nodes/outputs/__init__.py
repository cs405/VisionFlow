from nodes.outputs.output_base import OutputBase
from core.node_base import Property, PropertyGroupNames


# -- Backward-compatible aliases for existing project files --
class OKOutputNode(OutputBase):
    """OK 输出节点。继承 OutputBase，默认输出 'OK'。"""
    def __init__(self):
        super().__init__()
        self.name = "OK输出"


class NGOutputNode(OutputBase):
    """NG 输出节点。继承 OutputBase，默认输出 'NG' 且状态为错误。"""
    result_message = Property("NG", name="输出消息", group=PropertyGroupNames.RUN_PARAMETERS,
                              description="显示/返回的消息文本")
    result_success = Property(True, name="判定为成功", group=PropertyGroupNames.RUN_PARAMETERS,
                              description="开启时返回 OK 状态（绿色），关闭时返回 ERROR 状态（红色）")

    def __init__(self):
        super().__init__()
        self.name = "NG输出"


from nodes.outputs.show_outputs import (
    ShowMessageNode,
    ShowInfoOutputNode, ShowSuccessOutputNode, ShowWarnOutputNode,
    ShowErrorOutputNode, ShowFatalOutputNode, ShowDialogOutputNode,
)

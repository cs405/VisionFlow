from core.events import EventType
from nodes.outputs.output_base import OutputBase


class NGOutputNode(OutputBase):
    def __init__(self):
        super().__init__()
        self.name = "NG输出"

    def _get_message(self) -> str:
        return "NG"

    @property
    def _event_type(self) -> EventType:
        return EventType.MESSAGE_ERROR

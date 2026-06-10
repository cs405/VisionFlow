from core.events import EventType
from nodes.outputs.output_base import OutputBase


class OKOutputNode(OutputBase):
    def __init__(self):
        super().__init__()
        self.name = "OK输出"

    def _get_message(self) -> str:
        return "OK"

    @property
    def _event_type(self) -> EventType:
        return EventType.MESSAGE_SUCCESS

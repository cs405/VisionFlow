"""Data packet and flow result types

Defines the data structures passed between nodes during workflow execution.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any
import numpy as np


class FlowableResultState(Enum):
    """Result state for flow control"""
    OK = "OK"
    ERROR = "Error"
    BREAK = "Break"
    RUNNING = "Running"
    NONE = "None"


class FlowableInvokeMode(Enum):
    """How a node is invoked in the flow pipeline."""
    SEQUENTIAL = auto()
    PARALLEL = auto()


@dataclass
class FlowableResult:
    """
    Result from a node invocation. Carries data + state + message.
    """
    value: Any = None
    message: str = ""
    state: FlowableResultState = FlowableResultState.OK

    @property
    def is_ok(self) -> bool:
        return self.state == FlowableResultState.OK

    @property
    def is_error(self) -> bool:
        return self.state == FlowableResultState.ERROR

    @property
    def is_break(self) -> bool:
        return self.state == FlowableResultState.BREAK

    @classmethod
    def ok(cls, value: Any = None, message: str = "运行成功"):
        return cls(value=value, message=message, state=FlowableResultState.OK)

    @classmethod
    def error(cls, value: Any = None, message: str = "运行错误"):
        return cls(value=value, message=message, state=FlowableResultState.ERROR)

    @classmethod
    def break_(cls, value: Any = None, message: str = "不满足条件返回"):
        return cls(value=value, message=message, state=FlowableResultState.BREAK)

    def __bool__(self):
        return self.state == FlowableResultState.OK


@dataclass
class DataPacket:
    """
    Data flowing between nodes. Contains image data + metadata.
    In Python, we use numpy.ndarray for images
    and DataPacket for richer data exchange (metadata, multiple outputs, etc.).
    """
    image: np.ndarray | None = None
    images: list[np.ndarray] = field(default_factory=list)
    numeric_value: float = 0.0
    text_value: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    result_objects: list[Any] = field(default_factory=list)

    @property
    def has_image(self) -> bool:
        return self.image is not None

    @property
    def image_shape(self) -> tuple | None:
        if self.image is not None:
            return self.image.shape
        return None


@dataclass
class VisionResultImage:
    """
    Represents a named result image from a vision node.
    """
    name: str
    image: np.ndarray | None = None

    def dispose(self):
        """Release image memory."""
        self.image = None

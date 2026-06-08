"""Event system

Pub/sub for workflow execution events, node state changes, and property changes.
"""

from collections import defaultdict
from enum import Enum, auto
from typing import Any, Callable


class EventType(Enum):
    """Standard event types in the workflow system."""
    # Workflow lifecycle
    WORKFLOW_STARTED = auto()
    WORKFLOW_COMPLETED = auto()
    WORKFLOW_STOPPED = auto()
    WORKFLOW_ERROR = auto()

    # Node lifecycle
    NODE_STARTED = auto()
    NODE_COMPLETED = auto()
    NODE_ERROR = auto()
    NODE_PROPERTY_CHANGED = auto()
    NODE_SELECTED = auto()
    NODE_DESELECTED = auto()

    # Port / Link lifecycle
    PORT_STARTED = auto()
    PORT_COMPLETED = auto()
    LINK_STARTED = auto()
    LINK_COMPLETED = auto()

    # Diagram events
    DIAGRAM_CHANGED = auto()
    NODE_ADDED = auto()
    NODE_REMOVED = auto()
    LINK_ADDED = auto()
    LINK_REMOVED = auto()

    # Message events
    MESSAGE_INFO = auto()
    MESSAGE_WARN = auto()
    MESSAGE_ERROR = auto()
    MESSAGE_SUCCESS = auto()

    # Project events
    PROJECT_LOADED = auto()
    PROJECT_SAVED = auto()
    PROJECT_CHANGED = auto()

    # File iteration events (WPF "运行全部" / "显示全部")
    FILE_ITERATION_NEXT = auto()       # emitted before each file in run-all loop
    FILE_ITERATION_COMPLETED = auto()  # emitted when entire run-all loop finishes


class EventSystem:
    """Global event bus. Supports subscribe/publish with optional sender filtering."""

    def __init__(self):
        # 回调函数字典，键为事件类型，值为可调用对象的列表，支持一个事件触发多个处理函数
        self._handlers: dict[EventType, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: Callable):
        """Subscribe to an event type.

        Handler signature: handler(sender, **kwargs)
        """
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable):
        """Remove a subscription."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event_type: EventType, sender: Any = None, **kwargs):
        """Publish an event to all subscribers."""
        for handler in self._handlers.get(event_type, []):
            try:
                handler(sender, **kwargs)
            except Exception as e:
                # Let the error propagate but don't stop other handlers
                self.publish(EventType.MESSAGE_ERROR, sender=None,
                            message=f"Event handler error: {e}")

    def clear(self):
        """Remove all subscriptions."""
        self._handlers.clear()


# Global event system instance
event_system = EventSystem()

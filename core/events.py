"""Event system - ported from H.VisionMaster diagram events + C# event pattern.

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

    # Port / Link lifecycle (WPF FlowablePortData / FlowableLinkData invoke)
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


class EventSystem:
    """Global event bus. Supports subscribe/publish with optional sender filtering."""

    def __init__(self):
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

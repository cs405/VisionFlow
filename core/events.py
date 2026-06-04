"""
事件系统 - 实现core与UI的完全解耦
core层只发送事件，不关心谁监听
UI层监听事件并更新界面
"""

from typing import Dict, Any, Callable, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class EventType(Enum):
    """事件类型"""
    # 工作流事件
    WORKFLOW_NODE_ADDED = "workflow.node_added"
    WORKFLOW_NODE_REMOVED = "workflow.node_removed"
    WORKFLOW_EDGE_ADDED = "workflow.edge_added"
    WORKFLOW_EDGE_REMOVED = "workflow.edge_removed"
    WORKFLOW_EXECUTED = "workflow.executed"
    WORKFLOW_CLEARED = "workflow.cleared"

    # 节点事件
    NODE_PARAM_CHANGED = "node.param_changed"
    NODE_EXECUTED = "node.executed"
    NODE_SELECTED = "node.selected"

    # 图像事件
    IMAGE_UPDATED = "image.updated"

    # 日志事件
    LOG_MESSAGE = "log.message"

    # 项目事件
    PROJECT_LOADED = "project.loaded"
    PROJECT_SAVED = "project.saved"


@dataclass
class Event:
    """事件基类"""
    type: EventType
    data: Dict[str, Any] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class EventBus:
    """事件总线 - 单例模式，全局唯一"""

    _instance = None
    _listeners: Dict[EventType, List[Callable]] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._listeners = {}
        return cls._instance

    def subscribe(self, event_type: EventType, callback: Callable):
        """订阅事件"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        if callback not in self._listeners[event_type]:
            self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable):
        """取消订阅"""
        if event_type in self._listeners:
            if callback in self._listeners[event_type]:
                self._listeners[event_type].remove(callback)

    def emit(self, event: Event):
        """发送事件"""
        if event.type in self._listeners:
            for callback in self._listeners[event.type]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"事件回调执行失败: {e}")

    # 便捷方法
    def emit_log(self, level: str, message: str, module: str = ""):
        """发送日志事件"""
        self.emit(Event(
            type=EventType.LOG_MESSAGE,
            data={"level": level, "message": message, "module": module}
        ))
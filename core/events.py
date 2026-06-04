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
    WORKFLOW_EXECUTE = "workflow.execute"
    WORKFLOW_UNDO = "workflow.undo"
    WORKFLOW_REDO = "workflow.redo"
    WORKFLOW_DELETE_SELECTED = "workflow.delete_selected"
    WORKFLOW_NEW_FLOW = "workflow.new_flow"

    # 节点事件
    NODE_PARAM_CHANGED = "node.param_changed"
    NODE_PARAM_CHANGE_REQUEST = "node.param_change_request"
    NODE_EXECUTED = "node.executed"
    NODE_SELECTED = "node.selected"
    NODE_DOUBLE_CLICKED = "node.double_clicked"
    NODE_MOVED = "node.moved"
    NODE_CREATE_REQUEST = "node.create_request"
    NODE_CREATE = "node.create"

    # 图像事件
    IMAGE_UPDATED = "image.updated"

    # 日志事件
    LOG_MESSAGE = "log.message"

    # 项目事件
    PROJECT_LOADED = "project.loaded"
    PROJECT_SAVED = "project.saved"
    PROJECT_NEW = "project.new"
    PROJECT_LOAD = "project.load"
    PROJECT_SAVE = "project.save"
    PROJECT_SAVE_AS = "project.save_as"

    # 连接事件
    CONNECTION_STARTED = "connection.started"
    CONNECTION_DRAGGING = "connection.dragging"
    CONNECTION_FINISHED = "connection.finished"

    # 系统事件
    SYSTEM_INITIALIZED = "system.initialized"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_DISCOVER_NODES = "system.discover_nodes"
    SYSTEM_NODES_DISCOVERED = "system.nodes_discovered"
    SYSTEM_ERROR = "system.error"


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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._listeners = {}
            cls._instance._log_callbacks = []
        return cls._instance

    def __init__(self):
        # 避免重复初始化
        if not hasattr(self, '_initialized'):
            self._listeners: Dict[EventType, List[Callable]] = {}
            self._log_callbacks: List[Callable] = []
            self._initialized = True

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

    def emit_log(self, level: str, message: str, module: str = ""):
        """发送日志事件"""
        self.emit(Event(
            type=EventType.LOG_MESSAGE,
            data={"level": level, "message": message, "module": module}
        ))

    def register_log_callback(self, callback: Callable):
        """注册日志回调"""
        if callback not in self._log_callbacks:
            self._log_callbacks.append(callback)

    def clear(self):
        """清空所有监听器"""
        self._listeners.clear()

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls()
        return cls._instance
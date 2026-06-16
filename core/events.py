"""
事件系统
工作流执行事件、节点状态变更和属性变更的发布/订阅系统。
"""

import threading
from collections import defaultdict
from enum import Enum
from typing import Any, Callable


# 定义事件类型枚举类
class EventType(Enum):
    """工作流系统中的标准事件类型"""
    # 工作流生命周期
    WORKFLOW_STARTED = 10
    WORKFLOW_COMPLETED = 11
    WORKFLOW_STOPPED = 12
    WORKFLOW_ERROR = 13

    # 节点生命周期
    NODE_STARTED = 20
    NODE_COMPLETED = 21
    NODE_ERROR = 22
    NODE_PROPERTY_CHANGED = 23
    NODE_SELECTED = 24
    NODE_DESELECTED = 25

    # 端口/连线生命周期
    PORT_STARTED = 30
    PORT_COMPLETED = 31
    LINK_STARTED = 32
    LINK_COMPLETED = 33

    # 图表事件
    DIAGRAM_CHANGED = 40
    NODE_ADDED = 41
    NODE_REMOVED = 42
    LINK_ADDED = 43
    LINK_REMOVED = 44

    # 消息事件
    MESSAGE_INFO = 50
    MESSAGE_WARN = 51
    MESSAGE_ERROR = 52
    MESSAGE_SUCCESS = 53

    # 项目事件
    PROJECT_LOADED = 60
    PROJECT_SAVED = 61
    PROJECT_CHANGED = 62

    # 文件迭代事件
    FILE_ITERATION_NEXT = 70
    FILE_ITERATION_COMPLETED = 71


# 定义事件系统类
class EventSystem:
    """全局事件总线。支持带可选发送者过滤的订阅/发布。"""

    # 定义构造函数
    def __init__(self):
        self._handlers: dict[EventType, list[Callable]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_type: EventType, handler: Callable):
        """订阅事件类型。处理函数签名: handler(sender, **kwargs)"""
        with self._lock:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable):
        """取消订阅"""
        with self._lock:
            handlers = self._handlers.get(event_type)
            if handlers and handler in handlers:
                handlers.remove(handler)

    def publish(self, event_type: EventType, sender: Any = None, **kwargs):
        """发布事件给所有订阅者（线程安全）。

        如果 handler 抛出异常且 event_type 不是 MESSAGE_ERROR，
        发布 MESSAGE_ERROR 事件通知 UI（最多报告前 5 个错误，避免洪水）。
        """
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
        error_count = 0
        for handler in handlers:
            try:
                handler(sender, **kwargs)
            except Exception as e:
                if event_type != EventType.MESSAGE_ERROR and error_count < 5:
                    error_count += 1
                    try:
                        self.publish(EventType.MESSAGE_ERROR, sender=None,
                                    message=f"事件处理函数错误: {e}")
                    except Exception as e2:
                        import logging
                        logging.getLogger(__name__).error(
                            "无法发布 MESSAGE_ERROR: %s", e2, exc_info=True)

    # 定义清空方法
    def clear(self):
        """移除所有订阅"""
        with self._lock:
            self._handlers.clear()


# 创建全局事件系统实例
event_system = EventSystem()
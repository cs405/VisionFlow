"""
事件系统
工作流执行事件、节点状态变更和属性变更的发布/订阅系统。
"""
import logging
import threading
from collections import defaultdict
from enum import Enum
from typing import Any, Callable


# 定义事件类型枚举类
class EventType(Enum):
    """工作流系统中的标准事件类型"""
    # 工作流生命周期
    WORKFLOW_STARTED = 10          # 工作流开始事件
    WORKFLOW_COMPLETED = 11        # 工作流完成事件
    WORKFLOW_STOPPED = 12          # 工作流停止事件
    WORKFLOW_ERROR = 13            # 工作流错误事件

    # 节点生命周期
    NODE_STARTED = 20              # 节点开始事件
    NODE_COMPLETED = 21            # 节点完成事件
    NODE_ERROR = 22                # 节点错误事件
    NODE_PROPERTY_CHANGED = 23     # 节点属性变更事件
    NODE_SELECTED = 24             # 节点选中事件
    NODE_DESELECTED = 25           # 节点取消选中事件

    # 端口/连线生命周期
    PORT_STARTED = 30              # 端口开始事件
    PORT_COMPLETED = 31            # 端口完成事件
    LINK_STARTED = 32              # 连线开始事件
    LINK_COMPLETED = 33            # 连线完成事件

    # 图表事件
    DIAGRAM_CHANGED = 40           # 图表变更事件（如节点/连线增删改）
    NODE_ADDED = 41                # 增加节点事件
    NODE_REMOVED = 42              # 节点移除事件
    LINK_ADDED = 43                # 连线添加事件
    LINK_REMOVED = 44              # 连线移除事件

    # 消息事件
    MESSAGE_INFO = 50              # 信息消息事件
    MESSAGE_WARN = 51              # 警告消息事件
    MESSAGE_ERROR = 52             # 错误消息事件
    MESSAGE_SUCCESS = 53           # 成功消息事件

    # 项目事件
    PROJECT_LOADED = 60            # 项目加载事件
    PROJECT_SAVED = 61             # 项目保存事件
    PROJECT_CHANGED = 62           # 项目变更事件

    # 文件迭代事件
    FILE_ITERATION_NEXT = 70       # 文件迭代下一步事件
    FILE_ITERATION_COMPLETED = 71  # 文件迭代完成事件


# 定义事件系统类
class EventSystem:
    """全局事件总线。支持带可选发送者过滤的订阅/发布。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # 定义构造函数
    def __init__(self):
        if hasattr(self, '_handlers'):
            return  # 已经初始化过，跳过防止清空订阅
        self._handlers: dict[EventType, list[Callable]] = defaultdict(list)  # 待处理事件的字典
        self._lock = threading.RLock()                                       # 线程安全锁，保护事件处理函数的注册和调用

    def subscribe(self, event_type: EventType, handler: Callable):
        """订阅事件类型。处理函数签名: handler(sender, **kwargs)"""
        with self._lock:  # 获取锁，确保线程安全
            self._handlers[event_type].append(handler)  # 将处理函数添加到待处理事件的字典

    def unsubscribe(self, event_type: EventType, handler: Callable):
        """取消订阅"""
        with self._lock:  # 获得锁
            handlers = self._handlers.get(event_type)  # 从待办列表得到待处理事件
            if handlers and handler in handlers:  # 如果处理函数存在于待处理事件中
                handlers.remove(handler)  # 从待处理事件中移除处理函数

    def publish(self, event_type: EventType, sender: Any = None, **kwargs):
        """发布事件给所有订阅者（线程安全）。

        如果 handler 抛出异常且 event_type 不是 MESSAGE_ERROR，
        发布 MESSAGE_ERROR 事件通知 UI（最多报告前 5 个错误，避免洪水）。
        """
        with self._lock:  # 获取锁，确保线程安全
            handlers = list(self._handlers.get(event_type, []))  # 将待处理事件转为列表，避免在迭代过程中修改字典
        error_count = 0
        for handler in handlers:
            try:
                handler(sender, **kwargs)
            except Exception as e:
                self._report_handler_error(error_count, event_type, e)
                error_count += 1

    def _report_handler_error(self, error_count: int, event_type: EventType, e: Exception):
        """当 handler 抛出异常时，发布 MESSAGE_ERROR 通知 UI（最多报告前 5 个错误，避免洪水）。"""
        if event_type != EventType.MESSAGE_ERROR and error_count < 5:
            try:
                self.publish(EventType.MESSAGE_ERROR, sender=None,
                            message=f"事件处理函数错误: {e}")
            except Exception as e2:
                logging.getLogger(__name__).error(
                    "无法发布 MESSAGE_ERROR: %s", e2, exc_info=True)

    # 定义清空方法
    def clear(self):
        """移除所有订阅"""
        with self._lock:  # 获取锁，确保线程安全
            self._handlers.clear()  # 清空待办字典中所有的数据


# 创建全局事件系统实例
event_system = EventSystem()
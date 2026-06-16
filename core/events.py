"""
事件系统
工作流执行事件、节点状态变更和属性变更的发布/订阅系统。
"""

import threading
from collections import defaultdict
from enum import Enum, auto
from typing import Any, Callable


# 定义事件类型枚举类
class EventType(Enum):
    """工作流系统中的标准事件类型"""
    # 工作流生命周期
    WORKFLOW_STARTED = auto()      # 工作流启动
    WORKFLOW_COMPLETED = auto()    # 工作流完成
    WORKFLOW_STOPPED = auto()      # 工作流停止
    WORKFLOW_ERROR = auto()        # 工作流错误

    # 节点生命周期
    NODE_STARTED = auto()          # 节点开始执行
    NODE_COMPLETED = auto()        # 节点执行完成
    NODE_ERROR = auto()            # 节点执行错误
    NODE_PROPERTY_CHANGED = auto() # 节点属性变更
    NODE_SELECTED = auto()         # 节点被选中
    NODE_DESELECTED = auto()       # 节点取消选中

    # 端口/连线生命周期
    PORT_STARTED = auto()          # 端口开始执行
    PORT_COMPLETED = auto()        # 端口执行完成
    LINK_STARTED = auto()          # 连线开始执行
    LINK_COMPLETED = auto()        # 连线执行完成

    # 图表事件
    DIAGRAM_CHANGED = auto()       # 图表变更
    NODE_ADDED = auto()            # 节点添加
    NODE_REMOVED = auto()          # 节点移除
    LINK_ADDED = auto()            # 连线添加
    LINK_REMOVED = auto()          # 连线移除

    # 消息事件
    MESSAGE_INFO = auto()          # 信息消息
    MESSAGE_WARN = auto()          # 警告消息
    MESSAGE_ERROR = auto()         # 错误消息
    MESSAGE_SUCCESS = auto()       # 成功消息

    # 项目事件
    PROJECT_LOADED = auto()        # 项目加载
    PROJECT_SAVED = auto()         # 项目保存
    PROJECT_CHANGED = auto()       # 项目变更

    # 文件迭代事件
    FILE_ITERATION_NEXT = auto()       # 在运行全部循环中，每个文件处理前触发
    FILE_ITERATION_COMPLETED = auto()  # 整个运行全部循环完成时触发


# 定义事件系统类
class EventSystem:
    """全局事件总线。支持带可选发送者过滤的订阅/发布。"""

    # 定义构造函数
    def __init__(self):
        self._handlers: dict[EventType, list[Callable]] = defaultdict(list)
        self._in_error_publish: bool = False
        self._lock = threading.Lock()

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
        """发布事件给所有订阅者（线程安全）"""
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
        for handler in handlers:
            # 尝试执行处理函数
            try:
                # 调用处理函数，传入发送者和关键字参数
                handler(sender, **kwargs)
            # 如果执行过程中发生异常
            except Exception as e:
                # 防止 MESSAGE_ERROR 处理器自身异常导致无限递归
                if event_type != EventType.MESSAGE_ERROR and not self._in_error_publish:
                    self._in_error_publish = True
                    try:
                        self.publish(EventType.MESSAGE_ERROR, sender=None,
                                    message=f"事件处理函数错误: {e}")
                    finally:
                        self._in_error_publish = False

    # 定义清空方法
    def clear(self):
        """移除所有订阅"""
        with self._lock:
            self._handlers.clear()


# 创建全局事件系统实例
event_system = EventSystem()
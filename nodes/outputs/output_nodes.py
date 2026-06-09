"""输出节点：OK、NG以及各种通知消息输出。"""

import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult, FlowableResultState
from core.workflow import WorkflowEngine
from core.events import EventType, event_system


class _OutputBase(OpenCVNodeDataBase):
    """输出节点基类，透传图像"""
    # 节点所属分组（用于UI分类）
    __group__ = "结果输出模块"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src: 源节点数据
            from_node: 上游节点
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 获取消息内容
        msg = self._get_message()
        # 发布事件
        event_system.publish(self._event_type, sender=self, message=msg)
        # 返回成功结果，透传图像
        return self.ok(mat, msg)

    def _get_message(self) -> str:
        """获取消息内容（子类需重写）

        返回：
            消息字符串
        """
        return ""

    @property
    def _event_type(self) -> EventType:
        """获取事件类型（子类需重写）

        返回：
            事件类型
        """
        return EventType.MESSAGE_INFO

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class OKOutputNode(_OutputBase):
    """OK输出节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "结果输出模块"

    def __init__(self):
        """初始化OK输出节点"""
        super().__init__()
        self.name = "OK输出"

    def _get_message(self) -> str:
        """获取消息内容"""
        return "OK"

    @property
    def _event_type(self) -> EventType:
        """获取事件类型：成功消息"""
        return EventType.MESSAGE_SUCCESS


class NGOutputNode(_OutputBase):
    """NG输出节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "结果输出模块"

    def __init__(self):
        """初始化NG输出节点"""
        super().__init__()
        self.name = "NG输出"

    def _get_message(self) -> str:
        """获取消息内容"""
        return "NG"

    @property
    def _event_type(self) -> EventType:
        """获取事件类型：错误消息"""
        return EventType.MESSAGE_ERROR


class ShowInfoOutputNode(_OutputBase):
    """信息提示输出节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "结果输出模块"
    # 提示消息属性
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化信息提示节点"""
        super().__init__()
        self.name = "信息提示"

    def _get_message(self) -> str:
        """获取消息内容"""
        return self.message or "信息提示"

    @property
    def _event_type(self) -> EventType:
        """获取事件类型：信息消息"""
        return EventType.MESSAGE_INFO


class ShowSuccessOutputNode(_OutputBase):
    """成功提示输出节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "结果输出模块"
    # 提示消息属性
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化成功提示节点"""
        super().__init__()
        self.name = "成功提示"

    def _get_message(self) -> str:
        """获取消息内容"""
        return self.message or "操作成功"

    @property
    def _event_type(self) -> EventType:
        """获取事件类型：成功消息"""
        return EventType.MESSAGE_SUCCESS


class ShowWarnOutputNode(_OutputBase):
    """警告提示输出节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "结果输出模块"
    # 提示消息属性
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化警告提示节点"""
        super().__init__()
        self.name = "警告提示"

    def _get_message(self) -> str:
        """获取消息内容"""
        return self.message or "警告"

    @property
    def _event_type(self) -> EventType:
        """获取事件类型：警告消息"""
        return EventType.MESSAGE_WARN


class ShowErrorOutputNode(_OutputBase):
    """错误提示输出节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "结果输出模块"
    # 提示消息属性
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化错误提示节点"""
        super().__init__()
        self.name = "错误提示"

    def _get_message(self) -> str:
        """获取消息内容"""
        return self.message or "发生错误"

    @property
    def _event_type(self) -> EventType:
        """获取事件类型：错误消息"""
        return EventType.MESSAGE_ERROR


class ShowFatalOutputNode(_OutputBase):
    """严重提示输出节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "结果输出模块"
    # 提示消息属性
    message = Property("", name="提示消息", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化严重提示节点"""
        super().__init__()
        self.name = "严重提示"

    @property
    def _event_type(self) -> EventType:
        """获取事件类型：错误消息"""
        return EventType.MESSAGE_ERROR

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑（重写以返回错误状态）"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 获取消息内容
        msg = self._get_message()
        # 发布错误消息事件
        event_system.publish(EventType.MESSAGE_ERROR, sender=self, message=msg)
        # 返回错误结果
        return FlowableResult(mat, msg, FlowableResultState.ERROR)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class ShowDialogOutputNode(_OutputBase):
    """弹窗提示输出节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "结果输出模块"
    # 对话框消息属性
    message = Property("", name="对话框消息", group=PropertyGroupNames.RUN_PARAMETERS)
    # 对话框标题属性
    title = Property("提示", name="对话框标题", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化弹窗提示节点"""
        super().__init__()
        self.name = "弹窗提示"

    def _get_message(self) -> str:
        """获取消息内容"""
        return self.message or "弹窗消息"
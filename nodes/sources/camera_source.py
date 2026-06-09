"""摄像头采集源节点 - 从摄像头采集帧"""

import cv2
import numpy as np

from core.node_base import OpenCVNodeDataBase, SrcFilesVisionNodeData, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine
from core.events import EventType, event_system


class CameraCaptureNodeData(SrcFilesVisionNodeData, OpenCVNodeDataBase):
    """从摄像头设备采集帧的节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像数据源"

    # 摄像头索引属性（0=默认摄像头，1=第二个摄像头等）
    camera_index = Property(0, name="摄像头索引", group=PropertyGroupNames.RUN_PARAMETERS)
    # 帧宽度属性（设置采集分辨率宽度）
    frame_width = Property(640, name="帧宽度", group=PropertyGroupNames.RUN_PARAMETERS)
    # 帧高度属性（设置采集分辨率高度）
    frame_height = Property(480, name="帧高度", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化摄像头采集节点"""
        # 调用父类SrcFilesVisionNodeData的构造函数
        SrcFilesVisionNodeData.__init__(self)
        # 调用父类OpenCVNodeDataBase的构造函数
        OpenCVNodeDataBase.__init__(self)
        # 设置节点显示名称
        self.name = "摄像头"
        # 清空文件路径列表（摄像头不使用文件源）
        self.src_file_paths.clear()
        self.src_file_path = ""
        # 摄像头长连接：只在首次invoke时打开，dispose时释放，避免每次拍照都重新open/close
        self._cap: cv2.VideoCapture | None = None
        # 监听流程停止事件，自动释放摄像头资源
        event_system.subscribe(EventType.WORKFLOW_STOPPED, self._on_workflow_stopped)

    def _on_workflow_stopped(self, sender, **kwargs):
        """流程停止时立即释放摄像头硬件资源"""
        # 如果摄像头对象存在
        if self._cap is not None:
            self._cap.release()  # 关闭摄像头，释放硬件
            self._cap = None

    def _ensure_cap(self) -> cv2.VideoCapture | None:
        """懒加载摄像头连接，只在未打开时重新创建

        返回：
            VideoCapture对象或None
        """
        # 如果摄像头已存在且已打开，直接返回
        if self._cap is not None and self._cap.isOpened():
            return self._cap
        # 摄像头未打开（可能是初次或停止后被释放），重新创建连接
        self._cap = cv2.VideoCapture(self.camera_index)
        # 如果打开失败
        if not self._cap.isOpened():
            self._cap = None
            return None
        # 设置摄像头分辨率宽度
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        # 设置摄像头分辨率高度
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        return self._cap

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src_image_node_data: 源节点数据
            from_node_data: 上游节点数据
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 复用已打开的摄像头连接，不再每次重新open/close
        cap = self._ensure_cap()
        # 如果摄像头打开失败
        if cap is None:
            return self.error(None, f"无法打开摄像头 {self.camera_index}")
        # 从持续打开的摄像头读取最新一帧
        ret, frame = cap.read()
        # 如果读取失败
        if not ret:
            return self.error(None, f"无法从摄像头 {self.camera_index} 读取帧")
        # 记录图像宽度（像素）
        self.pixel_width = frame.shape[1]
        # 记录图像高度（像素）
        self.pixel_height = frame.shape[0]
        # 返回成功结果
        return self.ok(frame, "摄像头捕获")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat

    def dispose(self):
        """释放摄像头长连接并取消事件订阅"""
        # 取消工作流停止事件的订阅
        event_system.unsubscribe(EventType.WORKFLOW_STOPPED, self._on_workflow_stopped)
        # 如果摄像头对象存在
        if self._cap is not None:
            # 释放摄像头硬件资源
            self._cap.release()
            self._cap = None
        # 调用父类的dispose方法
        super().dispose()
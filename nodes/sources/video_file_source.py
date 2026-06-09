"""视频文件源节点 - 从视频文件读取帧。"""

import os
import cv2
import numpy as np

from core.node_base import OpenCVNodeDataBase, SrcFilesVisionNodeData, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class SrcVideoFilesNodeData(SrcFilesVisionNodeData, OpenCVNodeDataBase):
    """将视频帧作为图像源读取。"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像数据源"

    # 帧索引属性（只读，用于显示当前帧号）
    frame_index = Property(0, name="帧索引", group=PropertyGroupNames.RUN_PARAMETERS, readonly=True)
    # 帧率属性（只读，用于显示视频帧率）
    fps = Property(0.0, name="帧率", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        """初始化视频文件源节点"""
        # 调用父类SrcFilesVisionNodeData的构造函数
        SrcFilesVisionNodeData.__init__(self)
        # 调用父类OpenCVNodeDataBase的构造函数
        OpenCVNodeDataBase.__init__(self)
        # 设置节点显示名称
        self.name = "视频文件"
        # 视频捕获对象，初始为None
        self._cap: cv2.VideoCapture | None = None

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src_image_node_data: 源节点数据
            from_node_data: 上游节点数据
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 获取当前文件路径
        path = self.src_file_path
        # 如果路径为空或文件不存在
        if not path or not os.path.exists(path):
            return self.error(None, f"视频文件不存在: {path}")

        # 如果视频捕获对象不存在或未打开
        if self._cap is None or not self._cap.isOpened():
            # 创建视频捕获对象
            self._cap = cv2.VideoCapture(path)
            # 获取视频帧率
            self.fps = self._cap.get(cv2.CAP_PROP_FPS)

        # 读取下一帧
        ret, frame = self._cap.read()
        # 如果读取失败（到达视频末尾）
        if not ret:
            # 重置到视频开头
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            # 重新读取第一帧
            ret, frame = self._cap.read()
            if not ret:
                return self.error(None, "无法读取视频帧")

        # 记录当前帧索引
        self.frame_index = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))
        # 记录图像宽度（像素）
        self.pixel_width = frame.shape[1]
        # 记录图像高度（像素）
        self.pixel_height = frame.shape[0]
        # 返回成功结果
        return self.ok(frame, f"帧: {self.frame_index}")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat

    def dispose(self):
        """释放资源"""
        # 如果视频捕获对象存在，释放资源
        if self._cap:
            self._cap.release()
            self._cap = None
        # 调用父类的dispose方法
        super().dispose()
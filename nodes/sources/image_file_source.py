"""图像文件源节点 - 从文件列表加载图像。"""

import os
import cv2
import numpy as np

from core.node_base import OpenCVNodeDataBase, SrcFilesVisionNodeData, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class SrcImageFilesNodeData(SrcFilesVisionNodeData, OpenCVNodeDataBase):
    """从文件列表加载图像。图像处理的主要数据源。"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像数据源"

    def __init__(self):
        """初始化图像文件源节点"""
        # 调用父类SrcFilesVisionNodeData的构造函数
        SrcFilesVisionNodeData.__init__(self)
        # 调用父类OpenCVNodeDataBase的构造函数
        OpenCVNodeDataBase.__init__(self)
        # 设置节点显示名称
        self.name = "图像文件"

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
            return self.error(None, f"文件不存在: {path}")

        # 使用OpenCV读取图像（彩色模式）
        mat = cv2.imread(path, cv2.IMREAD_COLOR)
        # 如果读取失败
        if mat is None:
            return self.error(None, f"无法读取图像: {path}")

        # 记录图像宽度（像素）
        self.pixel_width = mat.shape[1]
        # 记录图像高度（像素）
        self.pixel_height = mat.shape[0]
        # 记录图像颜色类型（数据类型）
        self.image_color_type = mat.dtype.type.__name__ if hasattr(mat.dtype, 'type') else str(mat.dtype)
        # 返回成功结果
        return self.ok(mat, f"已加载: {os.path.basename(path)}")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat

    def is_valid(self, mat: np.ndarray) -> bool:
        """检查图像是否有效

        参数：
            mat: 图像数组

        返回：
            是否有效
        """
        return mat is not None and mat.size > 0
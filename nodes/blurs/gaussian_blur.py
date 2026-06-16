"""高斯模糊节点"""

import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class GaussianBlur(OpenCVNodeDataBase):
    """高斯模糊节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "滤波模块"
    # 卷积核大小属性（控制模糊程度，奇数）
    ksize = Property(3, name="卷积核大小", group=PropertyGroupNames.RUN_PARAMETERS)
    # X方向标准差属性
    sigma_x = Property(0.0, name="Sigma X", group=PropertyGroupNames.RUN_PARAMETERS)
    # Y方向标准差属性
    sigma_y = Property(0.0, name="Sigma Y", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化高斯模糊节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "高斯模糊"

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
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 确保卷积核大小为奇数且至少为1（高斯卷积核必须为奇数）
        k = max(1, self.ksize if self.ksize % 2 == 1 else self.ksize + 1)
        # 调用OpenCV的GaussianBlur进行高斯模糊处理
        result = cv2.GaussianBlur(mat, (k, k), self.sigma_x, self.sigma_y)
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat

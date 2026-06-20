"""细节增强 + 边缘保留滤波节点"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class DetailEnhance(OpenCVNodeDataBase):
    """细节增强节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "滤波模块"
    # 空间标准差属性（控制滤波窗口大小）
    sigma_s = Property(10.0, name="空间标准差", group=PropertyGroupNames.RUN_PARAMETERS)
    # 色彩标准差属性（控制颜色相似度阈值）
    sigma_r = Property(0.15, name="色彩标准差", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化细节增强节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "细节增强"

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
        mat = self._require_input_mat(from_node)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 调用OpenCV的detailEnhance进行细节增强，返回成功结果
        return self.ok(cv2.detailEnhance(mat, sigma_s=self.sigma_s, sigma_r=self.sigma_r))

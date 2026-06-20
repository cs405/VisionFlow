"""按位取反节点"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class BitwiseNot(OpenCVNodeDataBase):
    """按位取反节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像预处理模块"

    def __init__(self):
        """初始化按位取反节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "按位取反"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self._require_input_mat(from_node)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 执行按位取反操作
        return self.ok(cv2.bitwise_not(mat))
"""BGR通道分离节点"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class SplitBGR(OpenCVNodeDataBase):
    """BGR通道分离节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像预处理模块"
    # 输出通道属性（B/G/R）
    channel = Property("B", name="输出通道", group=PropertyGroupNames.RUN_PARAMETERS,
                       editor="choices", choices=["B", "G", "R"])

    def __init__(self):
        """初始化BGR通道分离节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "BGR通道分离"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 如果图像不是彩色图（少于3通道），直接返回原图
        if len(mat.shape) < 3:
            return self.ok(mat)
        # 分离BGR三个通道
        b, g, r = cv2.split(mat)
        # 根据选择的通道输出对应的单通道图像
        ch = {"B": b, "G": g, "R": r}.get(self.channel, b)
        # 返回成功结果
        return self.ok(ch)
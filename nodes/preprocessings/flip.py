"""翻转节点 - 水平/垂直/双向翻转"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Flip(OpenCVNodeDataBase):
    """图像翻转节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像预处理模块"
    # 翻转模式属性
    # 0: 垂直翻转（绕X轴）\n1: 水平翻转（绕Y轴）\n-1: 同时翻转（绕X轴和Y轴）
    flip_code = Property(0, name="翻转角度", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化翻转节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "翻转"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 执行图像翻转
        # flip_code: 0=垂直翻转, 1=水平翻转, -1=同时翻转
        result = cv2.flip(mat, self.flip_code)
        # 返回成功结果
        return self.ok(result)
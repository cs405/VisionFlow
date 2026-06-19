"""旋转节点 - 按角度旋转图像"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Rotate(OpenCVNodeDataBase):
    """图像旋转节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像预处理模块"
    # 旋转角度属性（度，顺时针为正）
    angle = Property(0.0, name="旋转角度", group=PropertyGroupNames.RUN_PARAMETERS)
    # 缩放比例属性（旋转后图像的缩放比例）
    scale = Property(1.0, name="缩放比例", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化旋转节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "旋转"

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
        # 获取图像尺寸
        h, w = mat.shape[:2]
        # 计算图像中心点
        center = (w // 2, h // 2)
        # 获取旋转矩阵
        M = cv2.getRotationMatrix2D(center, self.angle, self.scale)
        # 执行仿射变换（旋转）
        result = cv2.warpAffine(mat, M, (w, h))
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat
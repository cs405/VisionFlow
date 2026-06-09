"""归一化节点"""

import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Normalize(OpenCVNodeDataBase):
    """图像归一化节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像预处理模块"
    # Alpha属性（目标范围的下限或归一化因子）
    alpha = Property(1.0, name="Alpha", group=PropertyGroupNames.RUN_PARAMETERS)
    # Beta属性（目标范围的上限）
    beta = Property(0.0, name="Beta", group=PropertyGroupNames.RUN_PARAMETERS)
    # 归一化类型属性
    norm_type = Property("MinMax", name="归一化类型", group=PropertyGroupNames.RUN_PARAMETERS,
                         editor="choices", choices=["MinMax", "L1", "L2", "Inf"])

    def __init__(self):
        """初始化归一化节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "归一化"

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
        # 归一化类型映射字典
        nmap = {
            "MinMax": cv2.NORM_MINMAX,  # 最小-最大归一化
            "L1": cv2.NORM_L1,          # L1范数归一化
            "L2": cv2.NORM_L2,          # L2范数归一化
            "INF": cv2.NORM_INF         # 无穷范数归一化
        }
        # 创建与输入图像相同形状的浮点数组
        result = np.zeros_like(mat, dtype=np.float32)
        # 执行归一化
        cv2.normalize(mat, result, self.alpha, self.beta, nmap.get(self.norm_type, cv2.NORM_MINMAX))
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat
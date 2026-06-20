"""阈值化节点 - 二值化/反二值化/截断/取零等阈值处理"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine

# 阈值类型映射字典
_THRESH_TYPES = {
    "Binary": cv2.THRESH_BINARY,           # 二值化：大于阈值的设为最大值，否则为0
    "BinaryInv": cv2.THRESH_BINARY_INV,    # 反二值化：大于阈值的设为0，否则为最大值
    "Trunc": cv2.THRESH_TRUNC,             # 截断：大于阈值的设为阈值，否则不变
    "ToZero": cv2.THRESH_TOZERO,           # 取零：大于阈值的不变，否则为0
    "ToZeroInv": cv2.THRESH_TOZERO_INV,    # 反取零：大于阈值的为0，否则不变
    "Otsu": cv2.THRESH_OTSU,               # OTSU大津法（自动计算最优阈值）
    "Triangle": cv2.THRESH_TRIANGLE,       # 三角法（自动计算最优阈值）
}


class Threshold(OpenCVNodeDataBase):
    """阈值化节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像预处理模块"
    # 阈值属性
    thresh = Property(125.0, name="阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    # 最大值属性（二值化时设置的最大值）
    maxval = Property(255.0, name="最大值", group=PropertyGroupNames.RUN_PARAMETERS)
    # 阈值类型属性
    threshold_type = Property("Binary",
                              name="阈值类型",
                              group=PropertyGroupNames.RUN_PARAMETERS,
                              editor="choices",
                              choices=["Binary", "BinaryInv", "Trunc", "ToZero", "ToZeroInv", "Otsu", "Triangle"])

    def __init__(self):
        """初始化阈值化节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "阈值化"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self._require_input_mat(from_node)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 转换为灰度图（如果是彩色图像）
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        # 获取阈值类型常量
        ttype = _THRESH_TYPES.get(self.threshold_type, cv2.THRESH_BINARY)
        # 执行阈值化处理
        _, result = cv2.threshold(gray, self.thresh, self.maxval, ttype)
        # 返回成功结果
        return self.ok(result)
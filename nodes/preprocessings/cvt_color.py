"""色彩空间转换节点"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


# 色彩空间转换代码映射字典
_COLOR_CODES = {
    # BGR ↔ 灰度
    "BGR2GRAY": cv2.COLOR_BGR2GRAY,
    "GRAY2BGR": cv2.COLOR_GRAY2BGR,
    # BGR ↔ HSV
    "BGR2HSV": cv2.COLOR_BGR2HSV,
    "HSV2BGR": cv2.COLOR_HSV2BGR,
    # BGR ↔ LAB
    "BGR2LAB": cv2.COLOR_BGR2LAB,
    "LAB2BGR": cv2.COLOR_LAB2BGR,
    # BGR ↔ YUV
    "BGR2YUV": cv2.COLOR_BGR2YUV,
    "YUV2BGR": cv2.COLOR_YUV2BGR,
    # BGR ↔ RGB
    "BGR2RGB": cv2.COLOR_BGR2RGB,
    "RGB2BGR": cv2.COLOR_RGB2BGR,
    # BGR ↔ YCrCb
    "BGR2YCrCb": cv2.COLOR_BGR2YCrCb,
    "YCrCb2BGR": cv2.COLOR_YCrCb2BGR,
    # BGR ↔ HLS
    "BGR2HLS": cv2.COLOR_BGR2HLS,
    "HLS2BGR": cv2.COLOR_HLS2BGR,
}


class CvtColor(OpenCVNodeDataBase):
    """色彩空间转换节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像预处理模块"
    # 色彩转换模式属性
    color_code = Property("BGR2GRAY", name="色彩转换模式", group=PropertyGroupNames.RUN_PARAMETERS,
                          editor="choices", choices=["BGR2GRAY", "BGR2HSV", "HSV2BGR", "BGR2LAB",
                                                     "LAB2BGR", "BGR2YUV", "YUV2BGR", "BGR2RGB", "RGB2BGR",
                                                     "BGR2YCrCb", "YCrCb2BGR", "BGR2HLS", "HLS2BGR"])
    # 目标通道数属性
    dst_cn = Property(0, name="目标通道数", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化色彩空间转换节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "色彩空间转换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self._require_input_mat(from_node)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 获取色彩转换代码（默认使用BGR2GRAY）
        code = _COLOR_CODES.get(self.color_code, cv2.COLOR_BGR2GRAY)
        # 执行色彩空间转换
        try:
            result = cv2.cvtColor(mat, code, dstCn=self.dst_cn)
        except cv2.error as e:
            return self.error(None, f"色彩转换失败: {e}")
        # 返回成功结果
        return self.ok(result)
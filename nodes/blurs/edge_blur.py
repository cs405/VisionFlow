import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class EdgePreservingFilter(OpenCVNodeDataBase):
    """边缘保留滤波节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "滤波模块"
    # 滤波类型属性（RECURSIVE递归滤波 / NORMCONV归一化卷积滤波）
    filter_type = Property("RECURSIVE", name="滤波类型", group=PropertyGroupNames.RUN_PARAMETERS,
                           editor="choices", choices=["RECURSIVE", "NORMCONV"])
    # 空间标准差属性（控制滤波窗口大小）
    sigma_s = Property(60.0, name="空间标准差", group=PropertyGroupNames.RUN_PARAMETERS)
    # 色彩标准差属性（控制颜色相似度阈值）
    sigma_r = Property(0.4, name="色彩标准差", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化边缘保留滤波节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "边缘保留滤波"

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
        # 滤波类型映射字典
        flags = {
            "RECURSIVE": cv2.RECURS_FILTER,    # 递归滤波
            "NORMCONV": cv2.NORMCONV_FILTER    # 归一化卷积滤波
        }
        # 调用OpenCV的edgePreservingFilter进行边缘保留滤波
        return self.ok(cv2.edgePreservingFilter(
            mat,
            flags=flags.get(self.filter_type, cv2.RECURS_FILTER),  # 滤波类型
            sigma_s=self.sigma_s,   # 空间标准差
            sigma_r=self.sigma_r    # 色彩标准差
        ))

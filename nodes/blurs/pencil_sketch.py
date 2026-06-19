"""铅笔素描 + 风格化节点"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class PencilSketch(OpenCVNodeDataBase):
    """铅笔素描节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "滤波模块"
    # 空间标准差属性（控制滤波窗口大小）
    sigma_s = Property(60.0, name="空间标准差", group=PropertyGroupNames.RUN_PARAMETERS)
    # 色彩标准差属性（控制颜色相似度阈值）
    sigma_r = Property(0.07, name="色彩标准差", group=PropertyGroupNames.RUN_PARAMETERS)
    # 阴影强度属性（控制素描阴影的强度）
    shade_factor = Property(0.02, name="阴影强度", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化铅笔素描节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "铅笔素描"

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
        # 调用OpenCV的pencilSketch进行铅笔素描处理
        # 返回灰度素描图像和彩色素描图像（此处只取灰度素描）
        gray, color = cv2.pencilSketch(
            mat,
            sigma_s=self.sigma_s,      # 空间标准差
            sigma_r=self.sigma_r,      # 色彩标准差
            shade_factor=self.shade_factor  # 阴影强度
        )
        # 返回成功结果，输出灰度素描图像
        return self.ok(gray)

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat


class Stylization(OpenCVNodeDataBase):
    """风格化节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "滤波模块"
    # 空间标准差属性（控制滤波窗口大小）
    sigma_s = Property(60.0, name="空间标准差", group=PropertyGroupNames.RUN_PARAMETERS)
    # 色彩标准差属性（控制颜色相似度阈值）
    sigma_r = Property(0.45, name="色彩标准差", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化风格化节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "风格化"

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
        # 调用OpenCV的stylization进行风格化处理
        return self.ok(cv2.stylization(mat, sigma_s=self.sigma_s, sigma_r=self.sigma_r))

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat
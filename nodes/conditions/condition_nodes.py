"""条件/逻辑节点：条件分支和像素阈值条件"""

import cv2
import numpy as np
from core.node_base import (ConditionNodeData, OpenCVNodeDataBase, Property,
                           PropertyGroupNames, WaitAllParallelNodeData)  # 重导出以便插件发现
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class OpenCVConditionNode(ConditionNodeData, OpenCVNodeDataBase):
    """通用条件分支节点。评估上游节点的条件结果"""
    # 节点所属分组（用于UI分类）
    __group__ = "逻辑模块"

    def __init__(self):
        """初始化条件分支节点"""
        # 调用父类ConditionNodeData的构造函数
        ConditionNodeData.__init__(self)
        # 调用父类OpenCVNodeDataBase的构造函数
        OpenCVNodeDataBase.__init__(self)
        # 设置节点显示名称
        self.name = "条件分支"

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
        # 返回成功结果，透传图像
        return self.ok(mat)

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat


class PixelThresholdConditionNode(OpenCVNodeDataBase):
    """基于像素数量高于/低于阈值的条件节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "逻辑模块"
    # 像素阈值属性（用于判断像素值是否超过阈值）
    threshold = Property(128, name="像素阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    # 比较方式属性（">"表示大于，"<"表示小于）
    compare = Property(">", name="比较方式", group=PropertyGroupNames.RUN_PARAMETERS)
    # 最小像素数属性（满足条件的像素数量至少需要达到此值）
    min_pixels = Property(100, name="最小像素数", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化像素阈值条件节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "像素阈值条件"
        # 匹配的像素数量，初始为0
        self._match_count = 0

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
        # 转换为灰度图（如果是彩色图像）
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        # 根据比较方式计算满足条件的像素数量
        if self.compare == ">":
            # 计算大于阈值的像素数量
            count = np.sum(gray > self.threshold)
        else:
            # 计算小于阈值的像素数量
            count = np.sum(gray < self.threshold)
        # 保存匹配的像素数量
        self._match_count = count
        # 如果满足条件的像素数量大于等于最小像素数
        if count >= self.min_pixels:
            # 返回成功结果，透传图像，并显示满足条件的信息
            return self.ok(mat, f"满足条件: {count} >= {self.min_pixels}")
        # 否则返回中断结果，透传图像，并显示不满足条件的信息
        return self.break_(mat, f"不满足条件: {count} < {self.min_pixels}")

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat
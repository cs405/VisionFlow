"""条件/逻辑节点：条件分支和像素阈值条件"""

import cv2
import numpy as np
from core.node_base import (ConditionNodeData, OpenCVNodeDataBase, Property,
                           PropertyGroupNames, LogicModuleNode)
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class OpenCVConditionNode(ConditionNodeData, OpenCVNodeDataBase, LogicModuleNode):
    """通用条件分支节点。评估上游节点的条件结果"""
    # 节点所属分组（用于UI分类）
    __group__ = "逻辑模块"
    # 声明使用菱形模板（仅此节点，解耦自 ConditionNodeData 继承链）
    __template__ = "condition"

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


class PixelThresholdConditionNode(OpenCVNodeDataBase, LogicModuleNode):
    """基于像素数量高于/低于阈值的条件节点

    通过左右两个输出端口实现分支路由（"满足条件"/"不满足条件"）。

    端口布局：
           ┌── 输入(Top) ──┐
           │                │
      不满足(Left)      满足(Right)
    """
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
        # 当前激活的输出端口名（"满足条件" 或 "不满足条件"）
        self._active_output_port_name = ""

    def _init_ports(self):
        """创建3个端口：1个顶部输入 + 左右2个命名输出。

        左右两个输出端口各有名称，GetFlowablePortDatas() 根据条件二选一。
        """
        from core.node_base import PortDock, PortType
        self.ports = []
        # 顶部 - 输入端口
        p = self.create_port_data()
        p.dock = PortDock.TOP
        p.port_type = PortType.INPUT
        self.ports.append(p)
        # 左侧 - 输出"不满足条件"
        p = self.create_port_data()
        p.dock = PortDock.LEFT
        p.port_type = PortType.OUTPUT
        p.name = "不满足条件"
        self.ports.append(p)
        # 右侧 - 输出"满足条件"
        p = self.create_port_data()
        p.dock = PortDock.RIGHT
        p.port_type = PortType.OUTPUT
        p.name = "满足条件"
        self.ports.append(p)

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
            count = np.sum(gray > self.threshold)
        else:
            count = np.sum(gray < self.threshold)
        self._match_count = count
        # 设置活动输出端口
        if count >= self.min_pixels:
            self._active_output_port_name = "满足条件"
            return self.ok(mat, f"满足条件: {count} >= {self.min_pixels}")
        else:
            self._active_output_port_name = "不满足条件"
            return self.ok(mat, f"不满足条件: {count} < {self.min_pixels}")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat
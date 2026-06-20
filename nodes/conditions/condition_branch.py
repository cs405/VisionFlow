"""条件分支节点"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.node_condition import ConditionNodeData, LogicModuleNode
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class OpenCVConditionNode(ConditionNodeData, OpenCVNodeDataBase, LogicModuleNode):
    """通用条件分支节点

    通过 ConditionsPresenter 评估上游节点属性条件，动态选择输出端口。
    """

    __group__ = "逻辑模块"
    __template__ = "condition"

    def __init__(self):
        ConditionNodeData.__init__(self)
        OpenCVNodeDataBase.__init__(self)
        self.name = "条件分支"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        return self.ok(mat)

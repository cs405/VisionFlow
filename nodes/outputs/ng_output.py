"""NG输出返回 ERROR 状态。"""

from core.data_packet import FlowableResult
from nodes.outputs.output_base import OutputBase


class NGOutputNode(OutputBase):
    def __init__(self):
        super().__init__()
        self.name = "NG输出"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        return self.error(mat, "NG")

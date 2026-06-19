import cv2
from core.node_selectable import OpenCVNodeDataBase
from core.node_vision import VisionNodeData
from core.data_packet import FlowableResult


class BitwiseAnd(OpenCVNodeDataBase):
    """按位与掩膜 — 从上游节点查找单通道掩膜图并执行 bitwise_and"""
    __group__ = "图像分割提取模块"

    def __init__(self):
        super().__init__()
        self.name = "按位与掩膜"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        mask = None
        for n in self.from_node_datas:
            if isinstance(n, VisionNodeData) and n.mat is not None and len(n.mat.shape) == 2:
                mask = n.mat
                break
        if mask is None:
            return self.ok(mat, "无掩膜输入，保持原图")
        return self.ok(cv2.bitwise_and(mat, mat, mask=mask))

    def _update_result_image_source(self):
        self._result_image_source = self._mat

import cv2
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class DnnSuperres(OpenCVNodeDataBase):
    __group__ = "其他模块"
    scale = Property(4, name="放大倍数", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "DNN超分辨率"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        try:
            result = cv2.resize(mat, (mat.shape[1] * self.scale, mat.shape[0] * self.scale),
                                interpolation=cv2.INTER_CUBIC)
            return self.ok(result, f"放大 {self.scale}x")
        except Exception as e:
            return self.error(mat, str(e))

    def _update_result_image_source(self):
        self._result_image_source = self._mat

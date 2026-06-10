import cv2
from core.node_base import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class Stitching(OpenCVNodeDataBase):
    __group__ = "其他模块"

    def __init__(self):
        super().__init__()
        self.name = "图像拼接"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        if src is None or src.mat is None:
            return self.ok(mat, "需要两张图像进行拼接")
        try:
            stitcher = cv2.Stitcher_create()
            status, result = stitcher.stitch([mat, src.mat])
            if status == cv2.Stitcher_OK:
                return self.ok(result, "拼接成功")
            return self.error(mat, f"拼接失败: status={status}")
        except Exception as e:
            return self.error(mat, str(e))

    def _update_result_image_source(self):
        self._result_image_source = self._mat

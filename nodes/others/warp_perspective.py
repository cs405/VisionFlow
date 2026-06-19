import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class WarpPerspectiveTransform(OpenCVNodeDataBase):
    __group__ = "其他模块"
    tl_x = Property(0, name="左上X", group=PropertyGroupNames.RUN_PARAMETERS)
    tl_y = Property(0, name="左上Y", group=PropertyGroupNames.RUN_PARAMETERS)
    tr_x = Property(100, name="右上X", group=PropertyGroupNames.RUN_PARAMETERS)
    tr_y = Property(0, name="右上Y", group=PropertyGroupNames.RUN_PARAMETERS)
    bl_x = Property(0, name="左下X", group=PropertyGroupNames.RUN_PARAMETERS)
    bl_y = Property(100, name="左下Y", group=PropertyGroupNames.RUN_PARAMETERS)
    br_x = Property(100, name="右下X", group=PropertyGroupNames.RUN_PARAMETERS)
    br_y = Property(100, name="右下Y", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "透视变换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        h, w = mat.shape[:2]
        src_pts = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
        dst_pts = np.float32([[self.tl_x, self.tl_y], [self.tr_x, self.tr_y],
                              [self.bl_x, self.bl_y], [self.br_x, self.br_y]])
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        return self.ok(cv2.warpPerspective(mat, M, (w, h)))

    def _update_result_image_source(self):
        self._result_image_source = self._mat

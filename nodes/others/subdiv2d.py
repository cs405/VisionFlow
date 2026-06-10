import cv2
from core.node_base import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class Subdiv2D(OpenCVNodeDataBase):
    __group__ = "其他模块"

    def __init__(self):
        super().__init__()
        self.name = "2D细分"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        h, w = mat.shape[:2]
        subdiv = cv2.Subdiv2D((0, 0, w, h))
        points = [(w//4, h//4), (3*w//4, h//4), (w//2, 3*h//4), (w//4, h//2), (3*w//4, h//2)]
        for pt in points:
            subdiv.insert(pt)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        cv2.circle(out, points[0], 5, (0, 0, 255), -1)
        for t in subdiv.getTriangleList():
            pts = [(int(t[i]), int(t[i+1])) for i in range(0, 6, 2)]
            cv2.line(out, pts[0], pts[1], (255, 0, 0), 1)
            cv2.line(out, pts[1], pts[2], (255, 0, 0), 1)
            cv2.line(out, pts[2], pts[0], (255, 0, 0), 1)
        return self.ok(out)

    def _update_result_image_source(self):
        self._result_image_source = self._mat

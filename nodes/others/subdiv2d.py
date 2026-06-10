"""平面细分支持 Voronoi 图和 Delaunay 三角剖分。"""

import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class Subdiv2D(OpenCVNodeDataBase):
    __group__ = "其他模块"
    out_type = Property("Voronoi", name="单元类型", group=PropertyGroupNames.RUN_PARAMETERS,
                        editor="choices", choices=["Voronoi", "Delaunay"])
    size = Property(600, name="单元大小", group=PropertyGroupNames.RUN_PARAMETERS,
                    min_val=100, max_val=2000, step=50)

    def __init__(self):
        super().__init__()
        self.name = "平面细分"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        h, w = mat.shape[:2]
        sz = self.size
        if sz > max(w, h):
            sz = max(w, h)
        subdiv = cv2.Subdiv2D((0, 0, sz, sz))
        # FAST 角点作为细分输入点
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        fast = cv2.FastFeatureDetector_create(20)
        kp = fast.detect(gray, None)
        points = [(int(p.pt[0]), int(p.pt[1])) for p in kp[:200]]
        for pt in points:
            subdiv.insert(pt)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        for pt in points:
            cv2.circle(out, pt, 3, (0, 0, 255), -1)
        if self.out_type == "Voronoi":
            facets, centers = subdiv.getVoronoiFacetList([])
            for facet in facets:
                if len(facet) > 0:
                    cv2.polylines(out, [np.int32(facet)], True, (64, 255, 128), 1)
        else:
            edges = subdiv.getEdgeList()
            for e in edges:
                p1 = (int(e[0]), int(e[1]))
                p2 = (int(e[2]), int(e[3]))
                cv2.line(out, p1, p2, (64, 255, 128), 1)
        return self.ok(out, f"细分: {self.out_type} ({len(points)} 点)")

    def _update_result_image_source(self):
        self._result_image_source = self._mat

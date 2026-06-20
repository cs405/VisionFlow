"""KAZE 特征检测 """

import cv2
from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.features.feature_base import FeatureBase, DIFFUSIVITY_CHOICES, DIFFUSIVITY_MAP


class KazeFeatureDetector(FeatureBase):
    extended = Property(False, name="扩展描述符", group=PropertyGroupNames.RUN_PARAMETERS, description="True=128维, False=64维")
    upright = Property(False, name="忽略方向", group=PropertyGroupNames.RUN_PARAMETERS)
    threshold = Property(0.001, name="响应阈值", group=PropertyGroupNames.RUN_PARAMETERS, step=0.0001, decimals=4, description="越小特征点越多")
    n_octaves = Property(4, name="组数(Octaves)", group=PropertyGroupNames.RUN_PARAMETERS)
    n_octave_layers = Property(4, name="组内层数", group=PropertyGroupNames.RUN_PARAMETERS)
    diffusivity = Property("DIFF_PM_G2", name="扩散系数", group=PropertyGroupNames.RUN_PARAMETERS, editor="choices",
                           choices=DIFFUSIVITY_CHOICES)

    def __init__(self):
        super().__init__()
        self.name = "KAZE"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat, gray = self._get_gray(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        df = DIFFUSIVITY_MAP.get(self.diffusivity, cv2.KAZE_DIFF_PM_G2)
        kaze = cv2.KAZE_create(extended=self.extended, upright=self.upright, threshold=self.threshold,
                                nOctaves=self.n_octaves, nOctaveLayers=self.n_octave_layers, diffusivity=df)
        kp, des = kaze.detectAndCompute(gray, None)
        out = self._draw_keypoints(mat, kp) if kp else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        self.feature_count = len(kp) if kp else 0
        return self.ok(out, f"{self.feature_count} 个特征点")

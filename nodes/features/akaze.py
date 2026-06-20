"""AKAZE 特征检测"""

import cv2
from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.features.feature_base import FeatureBase, DIFFUSIVITY_CHOICES, DIFFUSIVITY_MAP


class AKazeFeatureDetector(FeatureBase):
    descriptor_type = Property("MLDB", name="描述符类型", group=PropertyGroupNames.RUN_PARAMETERS, editor="choices", choices=["MLDB", "KAZE"])
    descriptor_size = Property(0, name="描述符大小", group=PropertyGroupNames.RUN_PARAMETERS, description="0=自动")
    descriptor_channels = Property(3, name="描述符通道数", group=PropertyGroupNames.RUN_PARAMETERS)
    threshold = Property(0.001, name="响应阈值", group=PropertyGroupNames.RUN_PARAMETERS, step=0.0001, decimals=4, description="越小特征点越多")
    n_octaves = Property(4, name="组数(Octaves)", group=PropertyGroupNames.RUN_PARAMETERS)
    n_octave_layers = Property(4, name="组内层数", group=PropertyGroupNames.RUN_PARAMETERS)
    diffusivity = Property("DIFF_PM_G2", name="扩散系数", group=PropertyGroupNames.RUN_PARAMETERS, editor="choices",
                           choices=DIFFUSIVITY_CHOICES)

    def __init__(self):
        super().__init__()
        self.name = "AKAZE"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat, gray = self._get_gray(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        dt = {"MLDB": cv2.AKAZE_DESCRIPTOR_MLDB, "KAZE": cv2.AKAZE_DESCRIPTOR_KAZE}.get(self.descriptor_type, cv2.AKAZE_DESCRIPTOR_MLDB)
        df = DIFFUSIVITY_MAP.get(self.diffusivity, cv2.KAZE_DIFF_PM_G2)
        akaze = cv2.AKAZE_create(descriptor_type=dt, descriptor_size=self.descriptor_size,
                                  descriptor_channels=self.descriptor_channels, threshold=self.threshold,
                                  nOctaves=self.n_octaves, nOctaveLayers=self.n_octave_layers, diffusivity=df)
        kp, des = akaze.detectAndCompute(gray, None)
        out = self._draw_keypoints(mat, kp) if kp else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        self.feature_count = len(kp) if kp else 0
        return self.ok(out, f"{self.feature_count} 个特征点")

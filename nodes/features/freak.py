import cv2
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult

class FreakFeatureDetector(OpenCVNodeDataBase):
    __group__ = "特征提取模块"
    feature_count = Property(0, name="特征点数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    n_features = Property(100, name="最大特征点数", group=PropertyGroupNames.RUN_PARAMETERS)
    scale_factor = Property(1.2, name="缩放因子", group=PropertyGroupNames.RUN_PARAMETERS, step=0.1, decimals=1)
    n_levels = Property(8, name="金字塔层数", group=PropertyGroupNames.RUN_PARAMETERS)
    edge_threshold = Property(31, name="边缘阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    first_level = Property(0, name="起始层", group=PropertyGroupNames.RUN_PARAMETERS)
    wta_k = Property(2, name="WTA点数", group=PropertyGroupNames.RUN_PARAMETERS)
    score_type = Property("HARRIS", name="评分方式", group=PropertyGroupNames.RUN_PARAMETERS, editor="choices", choices=["HARRIS", "FAST"])
    patch_size = Property(31, name="采样块大小", group=PropertyGroupNames.RUN_PARAMETERS)
    fast_threshold = Property(20, name="FAST阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    orientation_normalized = Property(True, name="方向归一化", group=PropertyGroupNames.RUN_PARAMETERS)
    scale_normalized = Property(True, name="尺度归一化", group=PropertyGroupNames.RUN_PARAMETERS)
    pattern_scale = Property(22.0, name="采样间距", group=PropertyGroupNames.RUN_PARAMETERS, step=0.1, decimals=1)
    n_octaves = Property(4, name="组数(Octaves)", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self): super().__init__(); self.name = "FREAK"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        st = {"HARRIS": cv2.ORB_HARRIS_SCORE, "FAST": cv2.ORB_FAST_SCORE}.get(self.score_type, cv2.ORB_HARRIS_SCORE)
        orb = cv2.ORB_create(nfeatures=self.n_features, scaleFactor=self.scale_factor, nlevels=self.n_levels,
                             edgeThreshold=self.edge_threshold, firstLevel=self.first_level,
                             WTA_K=self.wta_k, scoreType=st, patchSize=self.patch_size, fastThreshold=self.fast_threshold)
        kp = orb.detect(gray, None)
        if hasattr(cv2, 'xfeatures2d'):
            freak = cv2.xfeatures2d.FREAK_create(orientationNormalized=self.orientation_normalized,
                                                  scaleNormalized=self.scale_normalized,
                                                  patternScale=self.pattern_scale, nOctaves=self.n_octaves)
            kp, des = freak.compute(gray, kp)
        out = cv2.drawKeypoints(mat, kp, None, (0, 255, 0), cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        self.feature_count = len(kp)
        return self.ok(out, f"{len(kp)} 个FREAK特征点")

    def _update_result_image_source(self): self._result_image_source = self._mat

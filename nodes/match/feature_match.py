"""
特征匹配节点 - 基于特征点的图像匹配
支持 ORB、SIFT、AKAZE 等特征检测器
"""

import cv2
import numpy as np
from typing import Any, Dict, List, Tuple, Optional

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class FeatureMatchNode(NodeBase):
    """
    特征匹配节点
    使用特征点检测器在目标图像中查找模板特征
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "特征匹配"
        self.category = "匹配"
        self.description = "使用特征点匹配查找图像中的目标"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="目标图像"),
            Socket("template", DataType.IMAGE, is_input=True, description="模板图像")
        ]
        self.output_sockets = [
            Socket("matches", DataType.ROI_LIST, is_input=False, description="匹配结果"),
            Socket("debug_image", DataType.IMAGE, is_input=False, description="调试图像"),
            Socket("best_score", DataType.NUMBER, is_input=False, description="最佳匹配分数"),
            Socket("keypoints_count", DataType.NUMBER, is_input=False, description="特征点数量")
        ]

        # 参数
        self.parameters = {
            "detector": NodeParameter(
                name="detector",
                label="特征检测器",
                type=ParamType.ENUM,
                default="orb",
                options=["orb", "sift", "akaze", "brisk"]
            ),
            "matcher": NodeParameter(
                name="matcher",
                label="匹配器",
                type=ParamType.ENUM,
                default="flann",
                options=["bruteforce", "flann"]
            ),
            "ratio_test": NodeParameter(
                name="ratio_test",
                label="比率测试阈值",
                type=ParamType.FLOAT_SLIDER,
                default=0.75,
                min=0.5,
                max=1.0,
                step=0.01
            ),
            "distance_threshold": NodeParameter(
                name="distance_threshold",
                label="距离阈值",
                type=ParamType.SLIDER,
                default=50,
                min=10,
                max=200,
                step=5
            ),
            "min_match_count": NodeParameter(
                name="min_match_count",
                label="最小匹配数",
                type=ParamType.SLIDER,
                default=10,
                min=4,
                max=100,
                step=5
            ),
            "draw_matches": NodeParameter(
                name="draw_matches",
                label="绘制匹配线",
                type=ParamType.BOOL,
                default=True
            ),
            "draw_keypoints": NodeParameter(
                name="draw_keypoints",
                label="绘制特征点",
                type=ParamType.BOOL,
                default=False
            ),
            "homography_method": NodeParameter(
                name="homography_method",
                label="单应性计算方法",
                type=ParamType.ENUM,
                default="ransac",
                options=["ransac", "lmeds", "none"]
            ),
            "ransac_reproj_threshold": NodeParameter(
                name="ransac_reproj_threshold",
                label="RANSAC重投影阈值",
                type=ParamType.SLIDER,
                default=3.0,
                min=1.0,
                max=10.0,
                step=0.5
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

        # 缓存特征检测器和匹配器
        self._detector = None
        self._matcher = None

    def _get_detector(self):
        """获取或创建特征检测器"""
        detector_type = self.get_param("detector")

        if detector_type == "orb":
            return cv2.ORB_create(nfeatures=1000, scaleFactor=1.2, nlevels=8)
        elif detector_type == "sift":
            return cv2.SIFT_create(nfeatures=1000)
        elif detector_type == "akaze":
            return cv2.AKAZE_create()
        elif detector_type == "brisk":
            return cv2.BRISK_create()
        else:
            return cv2.ORB_create()

    def _get_matcher(self, descriptor_type):
        """获取特征匹配器"""
        matcher_type = self.get_param("matcher")

        if matcher_type == "flann":
            # FLANN匹配器参数
            if descriptor_type == "orb" or descriptor_type == "brisk":
                # ORB/BRISK使用二进制描述子
                index_params = dict(algorithm=6, table_number=12, key_size=20, multi_probe_level=2)
                search_params = dict(checks=50)
            else:
                # SIFT/AKAZE使用浮点描述子
                index_params = dict(algorithm=1, trees=5)
                search_params = dict(checks=50)
            return cv2.FlannBasedMatcher(index_params, search_params)
        else:
            # 暴力匹配器
            if descriptor_type == "orb" or descriptor_type == "brisk":
                return cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            else:
                return cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)

    def _compute_features(self, img):
        """计算图像的特征点和描述子"""
        if img is None:
            return None, None

        # 转换为灰度图
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        detector = self._get_detector()
        keypoints, descriptors = detector.detectAndCompute(gray, None)

        return keypoints, descriptors

    def _filter_matches_by_distance(self, matches, distance_threshold):
        """根据距离阈值过滤匹配点"""
        return [m for m in matches if m.distance < distance_threshold]

    def _filter_matches_by_ratio(self, matches, ratio_threshold):
        """使用最近邻比率测试过滤匹配点"""
        good_matches = []
        for match_pair in matches:
            if len(match_pair) >= 2:
                m, n = match_pair[0], match_pair[1]
                if m.distance < ratio_threshold * n.distance:
                    good_matches.append(m)
        return good_matches

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        template = inputs.get("template")

        if img is None:
            return {"matches": [], "debug_image": None, "best_score": 0, "keypoints_count": 0}

        if template is None:
            return {"matches": [], "debug_image": img.copy(), "best_score": 0, "keypoints_count": 0}

        # 获取参数
        detector_type = self.get_param("detector")
        ratio_threshold = self.get_param("ratio_test")
        distance_threshold = self.get_param("distance_threshold")
        min_match_count = self.get_param("min_match_count")
        draw_matches = self.get_param("draw_matches")
        draw_keypoints = self.get_param("draw_keypoints")
        homography_method = self.get_param("homography_method")
        ransac_threshold = self.get_param("ransac_reproj_threshold")

        # 计算特征
        kp_template, desc_template = self._compute_features(template)
        kp_image, desc_image = self._compute_features(img)

        if desc_template is None or desc_image is None:
            return {
                "matches": [],
                "debug_image": img.copy(),
                "best_score": 0,
                "keypoints_count": 0
            }

        # 特征匹配
        matcher = self._get_matcher(detector_type)

        if self.get_param("matcher") == "flann":
            # FLANN匹配
            raw_matches = matcher.knnMatch(desc_template, desc_image, k=2)
            matches = self._filter_matches_by_ratio(raw_matches, ratio_threshold)
        else:
            # 暴力匹配
            raw_matches = matcher.knnMatch(desc_template, desc_image, k=2)
            matches = self._filter_matches_by_ratio(raw_matches, ratio_threshold)

        # 按距离过滤
        matches = self._filter_matches_by_distance(matches, distance_threshold)

        # 计算单应性矩阵
        homography = None
        matched_img_pts = []
        matched_template_pts = []

        if len(matches) >= min_match_count:
            # 提取匹配点坐标
            template_pts = np.float32([kp_template[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
            img_pts = np.float32([kp_image[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

            # 计算单应性矩阵
            homography_method_code = cv2.RANSAC if homography_method == "ransac" else cv2.LMEDS
            homography, mask = cv2.findHomography(
                template_pts, img_pts, homography_method_code, ransac_threshold
            )

            # 提取内点
            if mask is not None:
                mask = mask.ravel().tolist()
                matched_template_pts = [template_pts[i] for i in range(len(mask)) if mask[i]]
                matched_img_pts = [img_pts[i] for i in range(len(mask)) if mask[i]]
                matches = [matches[i] for i in range(len(mask)) if mask[i]]

        # 计算匹配分数
        best_score = len(matches) / max(len(kp_template), 1)

        # 构建匹配结果
        matches_data = []
        if homography is not None:
            h, w = template.shape[:2]
            # 计算模板在目标图像中的位置
            template_corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
            projected_corners = cv2.perspectiveTransform(template_corners, homography)

            # 计算边界框
            x_coords = [corner[0][0] for corner in projected_corners]
            y_coords = [corner[0][1] for corner in projected_corners]
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)

            matches_data.append({
                "x": int(x_min),
                "y": int(y_min),
                "width": int(x_max - x_min),
                "height": int(y_max - y_min),
                "center_x": int((x_min + x_max) / 2),
                "center_y": int((y_min + y_max) / 2),
                "score": float(best_score),
                "match_count": len(matches),
                "homography": homography.tolist()
            })

        # 绘制调试图像
        debug_img = img.copy()

        if draw_keypoints:
            # 绘制特征点
            cv2.drawKeypoints(img, kp_image, debug_img, (0, 255, 0),
                              cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)

        if draw_matches and len(matches) > 0:
            # 绘制匹配线
            for match in matches:
                pt_template = tuple(map(int, kp_template[match.queryIdx].pt))
                pt_image = tuple(map(int, kp_image[match.trainIdx].pt))
                cv2.line(debug_img, pt_image, pt_image, (0, 255, 0), 2)

            # 绘制匹配矩形
            for match_data in matches_data:
                cv2.rectangle(debug_img,
                              (match_data["x"], match_data["y"]),
                              (match_data["x"] + match_data["width"],
                               match_data["y"] + match_data["height"]),
                              (0, 255, 0), 2)
                cv2.putText(debug_img,
                            f"Score: {match_data['score']:.2f}",
                            (match_data["x"], match_data["y"] - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        return {
            "matches": matches_data,
            "debug_image": debug_img,
            "best_score": best_score,
            "keypoints_count": len(kp_image)
        }
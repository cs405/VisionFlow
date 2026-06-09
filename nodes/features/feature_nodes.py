"""特征提取节点：AKAZE、BRISK、FAST、FREAK、KAZE、MSER、Star、单应性变换"""

import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class _FeatureBase(OpenCVNodeDataBase):
    """特征检测器节点的基类。运行前检查算法可用性。"""
    # 特征点数量属性（只读，用于显示结果）
    feature_count = Property(0, name="特征点数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src: 源节点数据
            from_node: 上游节点
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        try:
            # 创建特征检测器
            detector = self._create_detector()
        except Exception as e:
            # 算法不可用时返回错误
            return self.error(None, f"特征算法不可用: {e}\n请确认 opencv-contrib-python 已安装")
        # 转换为灰度图（如果是彩色图像）
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        try:
            # 检测特征点
            keypoints = detector.detect(gray, None)
        except Exception as e:
            # 检测失败时返回错误
            return self.error(None, f"特征检测失败: {e}")
        # 创建输出图像（彩色）
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        # 绘制特征点（绿色，丰富关键点绘制）
        cv2.drawKeypoints(out, keypoints, out, (0, 255, 0),
                           cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        # 保存特征点数量
        self.feature_count = len(keypoints)
        # 返回成功结果，显示特征点数量
        return self.ok(out, f"{len(keypoints)} 个特征点")

    def _create_detector(self):
        """创建特征检测器（子类必须实现）"""
        raise NotImplementedError

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat


class AKazeFeatureDetector(_FeatureBase):
    """AKAZE特征检测器节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "特征提取模块"

    def __init__(self):
        """初始化AKAZE特征检测器节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "AKAZE"

    def _create_detector(self):
        """创建AKAZE检测器"""
        return cv2.AKAZE_create()


class BriskFeatureDetector(_FeatureBase):
    """BRISK特征检测器节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "特征提取模块"

    def __init__(self):
        """初始化BRISK特征检测器节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "BRISK"

    def _create_detector(self):
        """创建BRISK检测器"""
        return cv2.BRISK_create()


class FastFeatureDetector(_FeatureBase):
    """FAST特征检测器节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "特征提取模块"
    # 阈值属性
    threshold = Property(10, name="阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    # 非极大抑制属性
    nonmax_suppression = Property(True, name="非极大抑制", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化FAST特征检测器节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "FAST"

    def _create_detector(self):
        """创建FAST检测器"""
        return cv2.FastFeatureDetector_create(self.threshold, self.nonmax_suppression)


class FreakFeatureDetector(OpenCVNodeDataBase):
    """FREAK是描述子提取器（需要先检测关键点）"""
    # 节点所属分组（用于UI分类）
    __group__ = "特征提取模块"
    # 特征点数量属性（只读，用于显示结果）
    feature_count = Property(0, name="特征点数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        """初始化FREAK特征检测器节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "FREAK"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src: 源节点数据
            from_node: 上游节点
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 转换为灰度图（如果是彩色图像）
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        # 使用FAST检测关键点
        fast = cv2.FastFeatureDetector_create()
        kp = fast.detect(gray, None)
        # 创建FREAK描述子提取器（需要opencv-contrib）
        freak = cv2.xfeatures2d.FREAK_create() if hasattr(cv2, 'xfeatures2d') else None
        if freak is not None:
            # 计算描述子
            kp, des = freak.compute(gray, kp)
        # 绘制关键点
        out = cv2.drawKeypoints(mat, kp, None, (0, 255, 0),
                                 cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        # 保存特征点数量
        self.feature_count = len(kp)
        # 返回成功结果
        return self.ok(out, f"{len(kp)} 个FREAK特征点")

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat


class KazeFeatureDetector(_FeatureBase):
    """KAZE特征检测器节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "特征提取模块"

    def __init__(self):
        """初始化KAZE特征检测器节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "KAZE"

    def _create_detector(self):
        """创建KAZE检测器"""
        return cv2.KAZE_create()


class MserFeatureDetector(_FeatureBase):
    """MSER特征检测器节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "特征提取模块"

    def __init__(self):
        """初始化MSER特征检测器节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "MSER"

    def _create_detector(self):
        """创建MSER检测器"""
        return cv2.MSER_create()


class StarFeatureDetector(_FeatureBase):
    """Star特征检测器节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "特征提取模块"

    def __init__(self):
        """初始化Star特征检测器节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "StarDetector"

    def _create_detector(self):
        """创建Star检测器（需要opencv-contrib，否则使用SIFT作为后备）"""
        # 如果xfeatures2d可用，使用StarDetector，否则使用SIFT
        return cv2.xfeatures2d.StarDetector_create() if hasattr(cv2, 'xfeatures2d') else cv2.SIFT_create()


class HomographyTransform(OpenCVNodeDataBase):
    """使用两幅图像之间的特征匹配进行单应性变换"""
    # 节点所属分组（用于UI分类）
    __group__ = "特征提取模块"
    # 匹配点数属性（只读，用于显示结果）
    match_count = Property(0, name="匹配点数", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        """初始化单应性变换节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "单应性变换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src: 源节点数据（参考图像）
            from_node: 上游节点
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 如果没有参考图像，直接返回原图
        if src is None or src.mat is None:
            return self.ok(mat, "无参考图像")
        # 获取参考图像
        ref = src.mat
        # 转换为灰度图
        gray1 = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY) if len(ref.shape) == 3 else ref
        gray2 = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        # 创建SIFT特征检测器
        sift = cv2.SIFT_create()
        # 检测关键点并计算描述子
        kp1, des1 = sift.detectAndCompute(gray1, None)
        kp2, des2 = sift.detectAndCompute(gray2, None)
        # 如果特征点不足，返回原图
        if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
            return self.ok(mat, "特征点不足")
        # 创建暴力匹配器
        bf = cv2.BFMatcher()
        # 进行knn匹配（k=2）
        matches = bf.knnMatch(des1, des2, k=2)
        # 使用Lowe's ratio test筛选好的匹配点
        good = [m for m, n in matches if m.distance < 0.75 * n.distance]
        # 保存匹配点数量
        self.match_count = len(good)
        # 如果至少有4个好的匹配点
        if len(good) >= 4:
            # 获取源点和目标点坐标
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            # 计算单应性矩阵
            H, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC)
            # 获取参考图像尺寸
            h, w = ref.shape[:2]
            # 应用透视变换
            result = cv2.warpPerspective(mat, H, (w, h))
            # 返回成功结果
            return self.ok(result, f"单应性变换: {len(good)} 匹配点")
        # 匹配点不足，返回原图
        return self.ok(mat, f"不足4个匹配点 ({len(good)})")

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat
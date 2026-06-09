"""模板匹配节点：标准匹配、最佳匹配、SIFT、SURF、HSV Blob。"""

import base64
import cv2
import numpy as np
from core.node_base import Base64MatchingNodeData, OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class TemplateBase64MatchingNode(Base64MatchingNodeData, OpenCVNodeDataBase):
    """使用cv2.matchTemplate和Base64模板进行模板匹配"""
    # 节点所属分组（用于UI分类）
    __group__ = "模板匹配模块"
    # 匹配方法属性（决定使用的匹配算法）
    match_mode = Property("CCoeffNormed", name="匹配方法", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化模板匹配节点"""
        # 调用父类Base64MatchingNodeData的构造函数
        Base64MatchingNodeData.__init__(self)
        # 调用父类OpenCVNodeDataBase的构造函数
        OpenCVNodeDataBase.__init__(self)
        # 设置节点显示名称
        self.name = "模板匹配"

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
        # 获取模板图像
        template = self.get_template_image()
        # 如果模板图像为空
        if template is None:
            return self.error(mat, "未设置模板图片")

        # 匹配方法映射字典
        modes = {
            "SQDIFF": cv2.TM_SQDIFF,                    # 平方差匹配法
            "SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED,      # 标准平方差匹配法
            "CCORR": cv2.TM_CCORR,                      # 相关匹配法
            "CCORR_NORMED": cv2.TM_CCORR_NORMED,        # 标准相关匹配法
            "CCoeff": cv2.TM_CCOEFF,                    # 相关系数匹配法
            "CCoeffNormed": cv2.TM_CCOEFF_NORMED        # 标准相关系数匹配法
        }
        # 获取匹配方法常量（默认使用标准相关系数匹配法）
        method = modes.get(self.match_mode, cv2.TM_CCOEFF_NORMED)

        # 执行模板匹配
        result = cv2.matchTemplate(mat, template, method)
        # 获取匹配结果的最大值和最小值及其位置
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        # 如果匹配置信度大于等于0.8
        if max_val >= 0.8:
            # 获取模板尺寸
            h, w = template.shape[:2]
            # 复制原图
            color_mat = mat.copy()
            # 绘制匹配矩形框（绿色）
            cv2.rectangle(color_mat, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 255, 0), 2)
            # 保存匹配数量
            self.matching_count_result = 1
            # 保存置信度
            self.confidence = max_val
            # 返回成功结果
            return self.ok(color_mat, f"匹配成功 置信度: {max_val:.3f}")
        # 匹配失败
        self.matching_count_result = 0
        self.confidence = 0.0
        return self.ok(mat, "没有匹配到模板")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class BestMatchBase64TemplateMatchingNode(Base64MatchingNodeData, OpenCVNodeDataBase):
    """仅返回高于阈值的最佳匹配的模板匹配"""
    # 节点所属分组（用于UI分类）
    __group__ = "模板匹配模块"
    # 匹配方法属性
    match_mode = Property("CCoeffNormed", name="匹配方法", group=PropertyGroupNames.RUN_PARAMETERS)
    # 最小置信度阈值属性
    threshold = Property(0.8, name="最小置信度", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化最佳匹配节点"""
        # 调用父类Base64MatchingNodeData的构造函数
        Base64MatchingNodeData.__init__(self)
        # 调用父类OpenCVNodeDataBase的构造函数
        OpenCVNodeDataBase.__init__(self)
        # 设置节点显示名称
        self.name = "最佳匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 获取模板图像
        template = self.get_template_image()
        # 如果模板图像为空
        if template is None:
            return self.error(mat, "未设置模板图片")

        # 匹配方法映射字典（只使用归一化方法）
        modes = {
            "SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED,      # 标准平方差匹配法
            "CCORR_NORMED": cv2.TM_CCORR_NORMED,        # 标准相关匹配法
            "CCoeffNormed": cv2.TM_CCOEFF_NORMED        # 标准相关系数匹配法
        }
        # 获取匹配方法常量（默认使用标准相关系数匹配法）
        method = modes.get(self.match_mode, cv2.TM_CCOEFF_NORMED)

        # 执行模板匹配
        result = cv2.matchTemplate(mat, template, method)
        # 获取匹配结果的最大值和最小值及其位置
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        # 如果匹配置信度大于等于阈值
        if max_val >= self.threshold:
            # 获取模板尺寸
            h, w = template.shape[:2]
            # 复制原图
            out = mat.copy()
            # 绘制匹配矩形框（绿色）
            cv2.rectangle(out, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 255, 0), 2)
            # 保存匹配数量
            self.matching_count_result = 1
            # 保存置信度
            self.confidence = max_val
            # 返回成功结果
            return self.ok(out, f"最佳匹配: {max_val:.3f}")
        # 匹配失败
        self.matching_count_result = 0
        self.confidence = 0.0
        return self.ok(mat, "未找到匹配")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class SiftBase64FeatureMatchingNode(Base64MatchingNodeData, OpenCVNodeDataBase):
    """使用SIFT描述子进行特征匹配"""
    # 节点所属分组（用于UI分类）
    __group__ = "模板匹配模块"

    def __init__(self):
        """初始化SIFT特征匹配节点"""
        # 调用父类Base64MatchingNodeData的构造函数
        Base64MatchingNodeData.__init__(self)
        # 调用父类OpenCVNodeDataBase的构造函数
        OpenCVNodeDataBase.__init__(self)
        # 设置节点显示名称
        self.name = "SIFT特征匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 获取模板图像
        template = self.get_template_image()
        # 如果模板图像为空
        if template is None:
            return self.error(mat, "未设置模板图片")

        # 创建SIFT检测器
        sift = cv2.SIFT_create()
        # 检测模板图像的特征点和描述子
        kp1, des1 = sift.detectAndCompute(template, None)
        # 检测输入图像的特征点和描述子
        kp2, des2 = sift.detectAndCompute(mat, None)

        # 如果无法提取特征点
        if des1 is None or des2 is None:
            return self.ok(mat, "无法提取特征点")

        # 创建暴力匹配器
        bf = cv2.BFMatcher()
        # 对每个特征点找两个最近邻
        matches = bf.knnMatch(des1, des2, k=2)
        # Lowe's ratio test过滤优秀匹配
        good = [m for m, n in matches if m.distance < 0.75 * n.distance]

        # 复制原图
        out = mat.copy()
        # 绘制匹配连线
        out = cv2.drawMatches(template, kp1, mat, kp2, good, out,
                               flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        # 保存匹配数量
        self.matching_count_result = len(good)
        # 保存置信度（优秀匹配数/模板特征点数）
        self.confidence = len(good) / max(len(kp1), 1)
        # 返回成功结果
        return self.ok(out, f"匹配 {len(good)} 个特征点")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class SurfBase64FeatureMatchingNode(SiftBase64FeatureMatchingNode):
    """使用SURF进行特征匹配（如果不可用则回退到SIFT）"""
    # 节点所属分组（用于UI分类）
    __group__ = "模板匹配模块"

    def __init__(self):
        """初始化SURF特征匹配节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "SURF特征匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 获取模板图像
        template = self.get_template_image()
        # 如果模板图像为空
        if template is None:
            return self.error(mat, "未设置模板图片")

        try:
            # 尝试创建SURF检测器
            surf = cv2.xfeatures2d.SURF_create()
        except AttributeError:
            # 如果SURF不可用，回退到SIFT
            return SiftBase64FeatureMatchingNode.invoke_core(self, src, from_node, diagram)

        # 检测模板图像的特征点和描述子
        kp1, des1 = surf.detectAndCompute(template, None)
        # 检测输入图像的特征点和描述子
        kp2, des2 = surf.detectAndCompute(mat, None)
        # 如果无法提取特征点
        if des1 is None or des2 is None:
            return self.ok(mat, "无法提取特征点")

        # 创建暴力匹配器
        bf = cv2.BFMatcher()
        # 对每个特征点找两个最近邻
        matches = bf.knnMatch(des1, des2, k=2)
        # Lowe's ratio test过滤优秀匹配
        good = [m for m, n in matches if m.distance < 0.75 * n.distance]
        # 绘制匹配连线
        out = cv2.drawMatches(template, kp1, mat, kp2, good, mat.copy(),
                               flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        # 保存匹配数量
        self.matching_count_result = len(good)
        # 返回成功结果
        return self.ok(out, f"SURF匹配 {len(good)} 个特征点")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class HSVInRangeRenderBlobMatchingNode(OpenCVNodeDataBase):
    """基于HSV颜色的Blob匹配"""
    # 节点所属分组（用于UI分类）
    __group__ = "模板匹配模块"
    # H色相最小值属性
    h_low = Property(0, name="H低", group=PropertyGroupNames.RUN_PARAMETERS)
    # H色相最大值属性
    h_high = Property(180, name="H高", group=PropertyGroupNames.RUN_PARAMETERS)
    # S饱和度最小值属性
    s_low = Property(0, name="S低", group=PropertyGroupNames.RUN_PARAMETERS)
    # S饱和度最大值属性
    s_high = Property(255, name="S高", group=PropertyGroupNames.RUN_PARAMETERS)
    # V明度最小值属性
    v_low = Property(0, name="V低", group=PropertyGroupNames.RUN_PARAMETERS)
    # V明度最大值属性
    v_high = Property(255, name="V高", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化HSV Blob匹配节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "HSV Blob匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 将图像从BGR转换为HSV色彩空间
        hsv = cv2.cvtColor(mat, cv2.COLOR_BGR2HSV)
        # 创建HSV阈值下界数组
        lower = np.array([self.h_low, self.s_low, self.v_low], dtype=np.uint8)
        # 创建HSV阈值上界数组
        upper = np.array([self.h_high, self.s_high, self.v_high], dtype=np.uint8)
        # 根据HSV阈值范围创建掩膜
        mask = cv2.inRange(hsv, lower, upper)
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # 复制原图
        out = mat.copy()
        # 绘制所有轮廓（绿色）
        cv2.drawContours(out, contours, -1, (0, 255, 0), 2)
        # 返回成功结果
        return self.ok(out, f"发现 {len(contours)} 个Blob")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat
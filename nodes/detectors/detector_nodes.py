"""检测器节点：Canny边缘检测、查找轮廓、霍夫线检测、霍夫线段检测、Blob渲染、Blob检测器、二维码识别"""

import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Canny(OpenCVNodeDataBase):
    """Canny边缘检测节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "对象识别模块"
    # 阈值1属性（低阈值）
    threshold1 = Property(50.0, name="阈值1", group=PropertyGroupNames.RUN_PARAMETERS)
    # 阈值2属性（高阈值）
    threshold2 = Property(200.0, name="阈值2", group=PropertyGroupNames.RUN_PARAMETERS)
    # Sobel孔径大小属性
    aperture_size = Property(3, name="Sobel孔径", group=PropertyGroupNames.RUN_PARAMETERS)
    # L2梯度属性（是否使用更精确的L2范数）
    l2_gradient = Property(False, name="L2梯度", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化Canny边缘检测节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "Canny边缘检测"

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
        # 调用OpenCV的Canny边缘检测
        result = cv2.Canny(gray, self.threshold1, self.threshold2,
                            apertureSize=self.aperture_size, L2gradient=self.l2_gradient)
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat


class FindContours(OpenCVNodeDataBase):
    """查找轮廓节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "对象识别模块"
    # 轮廓数量属性（只读，用于显示结果）
    contour_count = Property(0, name="轮廓数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        """初始化查找轮廓节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "查找轮廓"

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
        # 二值化处理
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        # 查找轮廓（只检测外部轮廓，使用简单链式近似）
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # 创建输出图像（彩色）
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        # 绘制所有轮廓（绿色，线宽2）
        cv2.drawContours(out, contours, -1, (0, 255, 0), 2)
        # 保存轮廓数量
        self.contour_count = len(contours)
        # 返回成功结果，显示轮廓数量信息
        return self.ok(out, f"发现 {len(contours)} 个轮廓")

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat


class HoughLines(OpenCVNodeDataBase):
    """霍夫线检测节点（检测整条直线）"""
    # 节点所属分组（用于UI分类）
    __group__ = "对象识别模块"
    # 距离分辨率属性（像素）
    rho = Property(1.0, name="距离分辨率", group=PropertyGroupNames.RUN_PARAMETERS)
    # 角度分辨率属性（度）
    theta = Property(1.0, name="角度分辨率", group=PropertyGroupNames.RUN_PARAMETERS)
    # 阈值属性（检测直线的累加器阈值）
    threshold = Property(100, name="阈值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化霍夫线检测节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "霍夫线检测"

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
        # Canny边缘检测
        edges = cv2.Canny(gray, 50, 200)
        # 霍夫线检测
        lines = cv2.HoughLines(edges, self.rho, np.pi / 180 * self.theta, self.threshold)
        # 创建输出图像
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        # 检测到的直线数量
        count = 0
        if lines is not None:
            # 遍历所有检测到的直线
            for line in lines:
                # 获取rho和theta参数
                rho, theta = line[0]
                # 计算直线端点
                a, b = np.cos(theta), np.sin(theta)
                x0, y0 = a * rho, b * rho
                pt1 = (int(x0 + 1000 * (-b)), int(y0 + 1000 * a))
                pt2 = (int(x0 - 1000 * (-b)), int(y0 - 1000 * a))
                # 绘制直线（蓝色，线宽1）
                cv2.line(out, pt1, pt2, (0, 0, 255), 1)
                count += 1
        # 返回成功结果，显示检测到的直线数量
        return self.ok(out, f"检测到 {count} 条直线")

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat


class HoughLinesP(OpenCVNodeDataBase):
    """霍夫线段检测节点（检测线段）"""
    # 节点所属分组（用于UI分类）
    __group__ = "对象识别模块"
    # 距离分辨率属性（像素）
    rho = Property(1.0, name="Rho", group=PropertyGroupNames.RUN_PARAMETERS)
    # 最小线段长度属性
    min_line_length = Property(50, name="最小线长", group=PropertyGroupNames.RUN_PARAMETERS)
    # 最大线段间隔属性
    max_line_gap = Property(10, name="最大间隔", group=PropertyGroupNames.RUN_PARAMETERS)
    # 阈值属性
    threshold = Property(50, name="阈值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化霍夫线段检测节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "霍夫线段检测"

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
        # Canny边缘检测
        edges = cv2.Canny(gray, 50, 200)
        # 概率霍夫线段检测
        lines = cv2.HoughLinesP(edges, self.rho, np.pi / 180, self.threshold,
                                 minLineLength=self.min_line_length, maxLineGap=self.max_line_gap)
        # 创建输出图像
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        # 检测到的线段数量
        count = 0
        if lines is not None:
            # 遍历所有检测到的线段
            for line in lines:
                # 获取线段端点坐标
                x1, y1, x2, y2 = line[0]
                # 绘制线段（绿色，线宽2）
                cv2.line(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
                count += 1
        # 返回成功结果，显示检测到的线段数量
        return self.ok(out, f"检测到 {count} 条线段")

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat


class RenderBlobs(OpenCVNodeDataBase):
    """Blob渲染节点（渲染轮廓的边界框）"""
    # 节点所属分组（用于UI分类）
    __group__ = "对象识别模块"

    def __init__(self):
        """初始化Blob渲染节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "Blob渲染"

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
        # 二值化处理
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        # 查找轮廓
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # 创建输出图像（彩色）
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        # 为每个轮廓绘制边界框
        for c in contours:
            # 获取轮廓的边界矩形
            x, y, w, h = cv2.boundingRect(c)
            # 绘制矩形（绿色，线宽2）
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        # 返回成功结果，显示渲染的Blob数量
        return self.ok(out, f"渲染 {len(contours)} 个Blob")

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat


class BlobDetector(OpenCVNodeDataBase):
    """Blob检测器节点（检测图像中的斑点）"""
    # 节点所属分组（用于UI分类）
    __group__ = "对象识别模块"

    def __init__(self):
        """初始化Blob检测器节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "Blob检测器"

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
        # 创建Blob检测器参数
        params = cv2.SimpleBlobDetector_Params()
        # 创建Blob检测器
        detector = cv2.SimpleBlobDetector_create(params)
        # 检测关键点
        keypoints = detector.detect(mat)
        # 绘制关键点
        out = cv2.drawKeypoints(mat, keypoints, None, (0, 255, 0),
                                 cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        # 返回成功结果，显示检测到的Blob数量
        return self.ok(out, f"检测到 {len(keypoints)} 个Blob")

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat


class QRCode(OpenCVNodeDataBase):
    """二维码识别节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "对象识别模块"
    # 二维码结果属性（只读，用于显示识别结果）
    qr_result = Property("", name="二维码结果", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        """初始化二维码识别节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "二维码识别"

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
        # 创建二维码检测器
        detector = cv2.QRCodeDetector()
        # 检测并解码二维码
        data, points, _ = detector.detectAndDecode(mat)
        # 创建输出图像
        out = mat.copy()
        # 如果成功检测到二维码
        if data:
            # 保存二维码结果
            self.qr_result = data
            # 如果有点坐标
            if points is not None:
                # 将点坐标转换为整数
                pts = points.astype(int)
                # 绘制二维码边界框（绿色，线宽2）
                for i in range(4):
                    cv2.line(out, tuple(pts[i][0]), tuple(pts[(i+1)%4][0]), (0, 255, 0), 2)
            # 返回成功结果，显示二维码内容
            return self.ok(out, f"QR: {data}")
        # 清空二维码结果
        self.qr_result = ""
        # 返回成功结果，提示未检测到二维码
        return self.ok(out, "未检测到二维码")

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat
"""其他CV节点：Haar级联、LBP级联、直方图、HOG、无缝融合、图像拼接、2D细分、SVM、仿射变换、透视变换、DNN超分辨率、YOLOv3。"""

import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class HaarCascade(OpenCVNodeDataBase):
    """Haar级联分类器节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "其他模块"
    # 级联文件路径属性
    cascade_path = Property("", name="级联文件路径", group=PropertyGroupNames.RUN_PARAMETERS)
    # 缩放因子属性
    scale_factor = Property(1.1, name="缩放因子", group=PropertyGroupNames.RUN_PARAMETERS)
    # 最小邻居数属性
    min_neighbors = Property(3, name="最小邻居数", group=PropertyGroupNames.RUN_PARAMETERS)
    # 检测数量属性（只读）
    detect_count = Property(0, name="检测数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        """初始化Haar级联分类器节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "Haar级联分类器"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        # 转换为灰度图（如果是彩色图像）
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        # 如果指定了级联文件路径，使用指定文件；否则使用默认人脸检测模型
        if self.cascade_path:
            cascade = cv2.CascadeClassifier(self.cascade_path)
        else:
            cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        # 检测目标
        objects = cascade.detectMultiScale(gray, self.scale_factor, self.min_neighbors)
        # 创建输出图像（彩色）
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        # 绘制检测框（绿色）
        for (x, y, w, h) in objects:
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        # 保存检测数量
        self.detect_count = len(objects)
        return self.ok(out, f"检测到 {len(objects)} 个目标")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class LbpCascade(HaarCascade):
    """LBP级联分类器节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "其他模块"

    def __init__(self):
        """初始化LBP级联分类器节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "LBP级联分类器"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        # 转换为灰度图（如果是彩色图像）
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        # 使用LBP人脸检测模型
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "lbpcascade_frontalface_improved.xml")
        # 检测目标
        objects = cascade.detectMultiScale(gray, self.scale_factor, self.min_neighbors)
        # 创建输出图像（彩色）
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        # 绘制检测框（绿色）
        for (x, y, w, h) in objects:
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        # 保存检测数量
        self.detect_count = len(objects)
        return self.ok(out, f"LBP检测到 {len(objects)} 个目标")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class Hist(OpenCVNodeDataBase):
    """直方图节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "其他模块"
    # 直方图大小属性
    hist_size = Property(256, name="直方图大小", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化直方图节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "直方图"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        # 转换为灰度图（如果是彩色图像）
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        # 计算直方图
        hist = cv2.calcHist([gray], [0], None, [self.hist_size], [0, 256])
        # 创建直方图图像
        hist_img = np.zeros((256, 256, 3), dtype=np.uint8)
        # 归一化直方图到0-256范围
        cv2.normalize(hist, hist, 0, 256, cv2.NORM_MINMAX)
        # 绘制直方图折线
        for i in range(1, 256):
            cv2.line(hist_img, (i-1, 255 - int(hist[i-1])),
                      (i, 255 - int(hist[i])), (0, 255, 0), 1)
        return self.ok(hist_img, "直方图计算完成")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class Hog(OpenCVNodeDataBase):
    """HOG描述子节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "其他模块"

    def __init__(self):
        """初始化HOG描述子节点"""
        super().__init__()
        self.name = "HOG描述子"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        # 转换为灰度图（如果是彩色图像）
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        # 创建HOG描述子
        hog = cv2.HOGDescriptor()
        # 计算HOG特征
        h = hog.compute(gray)
        return self.ok(mat, f"HOG特征维度: {h.shape}")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class SeamlessClone(OpenCVNodeDataBase):
    """无缝融合节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "其他模块"
    # 融合方式属性
    clone_type = Property("NORMAL_CLONE", name="融合方式", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化无缝融合节点"""
        super().__init__()
        self.name = "无缝融合"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        # 如果没有源图像（背景），返回原图
        if src is None or src.mat is None:
            return self.ok(mat, "无目标背景")
        # 获取图像尺寸
        h, w = mat.shape[:2]
        # 创建全白掩码
        mask = np.ones((h, w), dtype=np.uint8) * 255
        # 计算中心点
        cx, cy = w // 2, h // 2
        # 融合方式映射
        cmap = {"NORMAL_CLONE": cv2.NORMAL_CLONE, "MIXED_CLONE": cv2.MIXED_CLONE}
        # 执行无缝融合
        result = cv2.seamlessClone(mat, src.mat, mask, (cx, cy), cmap.get(self.clone_type, cv2.NORMAL_CLONE))
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class Stitching(OpenCVNodeDataBase):
    """图像拼接节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "其他模块"

    def __init__(self):
        """初始化图像拼接节点"""
        super().__init__()
        self.name = "图像拼接"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        # 如果没有源图像，返回
        if src is None or src.mat is None:
            return self.ok(mat, "需要两张图像进行拼接")
        try:
            # 创建拼接器
            stitcher = cv2.Stitcher_create()
            # 执行拼接
            status, result = stitcher.stitch([mat, src.mat])
            # 拼接成功
            if status == cv2.Stitcher_OK:
                return self.ok(result, "拼接成功")
            return self.error(mat, f"拼接失败: status={status}")
        except Exception as e:
            return self.error(mat, str(e))

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class Subdiv2D(OpenCVNodeDataBase):
    """2D细分节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "其他模块"

    def __init__(self):
        """初始化2D细分节点"""
        super().__init__()
        self.name = "2D细分"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        # 获取图像尺寸
        h, w = mat.shape[:2]
        # 创建细分器
        subdiv = cv2.Subdiv2D((0, 0, w, h))
        # 定义采样点
        points = [(w//4, h//4), (3*w//4, h//4), (w//2, 3*h//4), (w//4, h//2), (3*w//4, h//2)]
        # 插入点
        for pt in points:
            subdiv.insert(pt)
        # 创建输出图像（彩色）
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        # 绘制第一个点（红色）
        cv2.circle(out, points[0], 5, (0, 0, 255), -1)
        # 获取三角形列表
        triangles = subdiv.getTriangleList()
        # 绘制三角形边（蓝色）
        for t in triangles:
            pts = [(int(t[i]), int(t[i+1])) for i in range(0, 6, 2)]
            cv2.line(out, pts[0], pts[1], (255, 0, 0), 1)
            cv2.line(out, pts[1], pts[2], (255, 0, 0), 1)
            cv2.line(out, pts[2], pts[0], (255, 0, 0), 1)
        return self.ok(out)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class SVM(OpenCVNodeDataBase):
    """SVM分类器节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "其他模块"
    # SVM类型属性
    svm_type = Property("C_SVC", name="SVM类型", group=PropertyGroupNames.RUN_PARAMETERS)
    # 核函数类型属性
    kernel_type = Property("RBF", name="核函数", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化SVM分类器节点"""
        super().__init__()
        self.name = "SVM分类器"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        # 创建SVM对象
        svm = cv2.ml.SVM_create()
        # SVM类型映射
        type_map = {
            "C_SVC": cv2.ml.SVM_C_SVC,
            "NU_SVC": cv2.ml.SVM_NU_SVC,
            "ONE_CLASS": cv2.ml.SVM_ONE_CLASS
        }
        # 核函数映射
        kernel_map = {
            "LINEAR": cv2.ml.SVM_LINEAR,
            "RBF": cv2.ml.SVM_RBF,
            "POLY": cv2.ml.SVM_POLY
        }
        # 设置SVM类型
        svm.setType(type_map.get(self.svm_type, cv2.ml.SVM_C_SVC))
        # 设置核函数类型
        svm.setKernel(kernel_map.get(self.kernel_type, cv2.ml.SVM_RBF))
        return self.ok(mat, "SVM分类器已配置")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class WarpAffineTransform(OpenCVNodeDataBase):
    """仿射变换节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "其他模块"
    # 平移X属性
    dx = Property(0, name="平移X", group=PropertyGroupNames.RUN_PARAMETERS)
    # 平移Y属性
    dy = Property(0, name="平移Y", group=PropertyGroupNames.RUN_PARAMETERS)
    # 旋转角度属性
    angle = Property(0.0, name="旋转角度", group=PropertyGroupNames.RUN_PARAMETERS)
    # 缩放因子属性
    scale = Property(1.0, name="缩放", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化仿射变换节点"""
        super().__init__()
        self.name = "仿射变换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        # 获取图像尺寸
        h, w = mat.shape[:2]
        # 计算图像中心
        center = (w // 2, h // 2)
        # 获取旋转矩阵
        M = cv2.getRotationMatrix2D(center, self.angle, self.scale)
        # 添加平移
        M[0, 2] += self.dx
        M[1, 2] += self.dy
        # 执行仿射变换
        result = cv2.warpAffine(mat, M, (w, h))
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class WarpPerspectiveTransform(OpenCVNodeDataBase):
    """透视变换节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "其他模块"
    # 左上角X坐标
    tl_x = Property(0, name="左上X", group=PropertyGroupNames.RUN_PARAMETERS)
    # 左上角Y坐标
    tl_y = Property(0, name="左上Y", group=PropertyGroupNames.RUN_PARAMETERS)
    # 右上角X坐标
    tr_x = Property(100, name="右上X", group=PropertyGroupNames.RUN_PARAMETERS)
    # 右上角Y坐标
    tr_y = Property(0, name="右上Y", group=PropertyGroupNames.RUN_PARAMETERS)
    # 左下角X坐标
    bl_x = Property(0, name="左下X", group=PropertyGroupNames.RUN_PARAMETERS)
    # 左下角Y坐标
    bl_y = Property(100, name="左下Y", group=PropertyGroupNames.RUN_PARAMETERS)
    # 右下角X坐标
    br_x = Property(100, name="右下X", group=PropertyGroupNames.RUN_PARAMETERS)
    # 右下角Y坐标
    br_y = Property(100, name="右下Y", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化透视变换节点"""
        super().__init__()
        self.name = "透视变换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        # 获取图像尺寸
        h, w = mat.shape[:2]
        # 源点（图像四角）
        src_pts = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
        # 目标点（用户指定）
        dst_pts = np.float32([
            [self.tl_x, self.tl_y],
            [self.tr_x, self.tr_y],
            [self.bl_x, self.bl_y],
            [self.br_x, self.br_y]
        ])
        # 获取透视变换矩阵
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        # 执行透视变换
        result = cv2.warpPerspective(mat, M, (w, h))
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class DnnSuperres(OpenCVNodeDataBase):
    """DNN超分辨率节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "其他模块"
    # 放大倍数属性
    scale = Property(4, name="放大倍数", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化DNN超分辨率节点"""
        super().__init__()
        self.name = "DNN超分辨率"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        try:
            # 创建超分辨率对象
            sr = cv2.dnn_superres.DnnSuperResImpl_create()
            # 使用双三次插值作为后备方案
            result = cv2.resize(mat, (mat.shape[1] * self.scale, mat.shape[0] * self.scale),
                                 interpolation=cv2.INTER_CUBIC)
            return self.ok(result, f"放大 {self.scale}x")
        except Exception as e:
            return self.error(mat, str(e))

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class Yolov3(OpenCVNodeDataBase):
    """YOLOv3检测器节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "其他模块"
    # 配置文件路径属性
    config_path = Property("", name="配置文件", group=PropertyGroupNames.RUN_PARAMETERS)
    # 权重文件路径属性
    weights_path = Property("", name="权重文件", group=PropertyGroupNames.RUN_PARAMETERS)
    # 置信度阈值属性
    confidence = Property(0.5, name="置信度阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    # NMS阈值属性
    nms_threshold = Property(0.4, name="NMS阈值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化YOLOv3检测器节点"""
        super().__init__()
        self.name = "YOLOv3检测器"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        # 加载Darknet模型
        if not self.config_path or not self.weights_path:
            self._net = cv2.dnn.readNetFromDarknet(
                self.config_path or "yolov3.cfg",
                self.weights_path or "yolov3.weights")
        # 获取图像尺寸
        h, w = mat.shape[:2]
        # 创建blob
        blob = cv2.dnn.blobFromImage(mat, 1/255.0, (416, 416), swapRB=True, crop=False)
        # 获取未连接的输出层名称
        layers = self._net.getUnconnectedOutLayersNames()
        # 设置输入
        self._net.setInput(blob)
        # 前向推理
        outputs = self._net.forward(layers)
        # 创建输出图像
        out = mat.copy()
        # 处理检测结果
        for output in outputs:
            for det in output:
                # 获取类别分数
                scores = det[5:]
                # 获取最高分类别
                class_id = np.argmax(scores)
                confidence_val = scores[class_id]
                # 如果置信度超过阈值
                if confidence_val > self.confidence:
                    # 获取边界框坐标
                    cx, cy, bw, bh = det[0:4] * np.array([w, h, w, h])
                    x = int(cx - bw / 2)
                    y = int(cy - bh / 2)
                    # 绘制边界框（绿色）
                    cv2.rectangle(out, (x, y), (int(x + bw), int(y + bh)), (0, 255, 0), 2)
        return self.ok(out, "YOLOv3检测完成")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat
"""ONNX/DNN模型节点：分类、目标检测、分割、推理。"""

import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class _OnnxBase(OpenCVNodeDataBase):
    """使用cv2.dnn的ONNX模型节点基类"""
    # 模型文件路径属性
    model_path = Property("", name="模型路径", group=PropertyGroupNames.RUN_PARAMETERS)
    # 输入图像尺寸属性
    input_size = Property(224, name="输入尺寸", group=PropertyGroupNames.RUN_PARAMETERS)
    # 缩放因子属性
    scale = Property(1.0, name="缩放因子", group=PropertyGroupNames.RUN_PARAMETERS)
    # 均值属性（逗号分隔，如"0,0,0"）
    mean = Property("0,0,0", name="均值", group=PropertyGroupNames.RUN_PARAMETERS)

    # 神经网络对象，初始为None
    _net: cv2.dnn.Net | None = None

    def _get_net(self) -> cv2.dnn.Net | None:
        """获取或加载ONNX网络模型

        返回：
            cv2.dnn.Net对象或None
        """
        # 如果网络未加载且模型路径存在
        if self._net is None and self.model_path:
            # 从ONNX文件读取网络
            self._net = cv2.dnn.readNetFromONNX(self.model_path)
        return self._net

    def _blob_from_image(self, mat: np.ndarray, size: int = None) -> np.ndarray:
        """从图像创建blob

        参数：
            mat: 输入图像
            size: 目标尺寸（可选，默认使用input_size）

        返回：
            blob数组
        """
        # 确定目标尺寸
        sz = size or self.input_size
        # 解析均值字符串
        means = [float(x) for x in self.mean.split(",")]
        # 如果只有一个均值，复制为3个通道
        if len(means) == 1:
            means = means * 3
        # 创建blob（交换RB通道，不裁剪）
        return cv2.dnn.blobFromImage(mat, self.scale, (sz, sz), tuple(means), swapRB=True, crop=False)

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat


class OnnxClassification(_OnnxBase):
    """使用ONNX模型的图像分类节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "Onnx通用模型"
    # 标签文件路径属性
    label_path = Property("", name="标签文件", group=PropertyGroupNames.RUN_PARAMETERS)
    # 分类结果属性（只读）
    class_result = Property("", name="分类结果", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 置信度属性（只读）
    conf_result = Property(0.0, name="置信度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        """初始化ONNX分类节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "ONNX分类"

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
        # 获取网络模型
        net = self._get_net()
        if net is None:
            return self.error(mat, "模型未加载")
        # 创建blob并设置输入
        blob = self._blob_from_image(mat)
        net.setInput(blob)
        # 前向推理
        output = net.forward()
        # 获取最大概率的类别索引
        class_id = np.argmax(output)
        # 保存置信度
        self.conf_result = float(output[0][class_id])
        # 设置分类结果
        self.class_result = str(class_id)
        # 如果有标签文件
        if self.label_path:
            try:
                # 读取标签文件
                with open(self.label_path) as f:
                    labels = [l.strip() for l in f.readlines()]
                # 获取标签名称
                self.class_result = labels[class_id] if class_id < len(labels) else str(class_id)
            except Exception:
                pass
        # 返回成功结果
        return self.ok(mat, f"分类: {self.class_result} ({self.conf_result:.3f})")


class OnnxObjectDetection(_OnnxBase):
    """使用ONNX模型的目标检测节点（例如YOLOv5）"""
    # 节点所属分组（用于UI分类）
    __group__ = "Onnx通用模型"
    # 置信度阈值属性
    conf_threshold = Property(0.5, name="置信度阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    # NMS阈值属性
    nms_threshold = Property(0.4, name="NMS阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    # 检测数量属性（只读）
    detect_count = Property(0, name="检测数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        """初始化ONNX目标检测节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "ONNX目标检测"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 获取网络模型
        net = self._get_net()
        if net is None:
            return self.error(mat, "模型未加载")
        # 创建blob并设置输入（YOLO使用640尺寸）
        blob = self._blob_from_image(mat, 640)
        net.setInput(blob)
        # 前向推理
        output = net.forward()
        # 获取图像尺寸
        h, w = mat.shape[:2]
        # 复制输出图像
        out = mat.copy()
        # 检测计数
        count = 0
        # 遍历所有检测结果
        for det in output[0]:
            # 获取置信度
            conf = float(det[4])
            # 如果置信度超过阈值
            if conf > self.conf_threshold:
                # 获取边界框坐标
                cx, cy, bw, bh = det[0:4]
                # 缩放到原始图像尺寸
                cx, cy = cx * w / 640, cy * h / 640
                bw, bh = bw * w / 640, bh * h / 640
                # 计算左上角和右下角坐标
                x1, y1 = int(cx - bw/2), int(cy - bh/2)
                x2, y2 = int(cx + bw/2), int(cy + bh/2)
                # 绘制边界框（绿色）
                cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
                # 绘制置信度文本
                cv2.putText(out, f"{conf:.2f}", (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                count += 1
        # 保存检测数量
        self.detect_count = count
        # 返回成功结果
        return self.ok(out, f"检测到 {count} 个目标")


class OnnxSemanticSegmentation(_OnnxBase):
    """使用ONNX模型的语义分割节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "Onnx通用模型"
    # 混合透明度属性（用于叠加显示）
    alpha = Property(0.5, name="混合透明度", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化ONNX语义分割节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "ONNX语义分割"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 获取网络模型
        net = self._get_net()
        if net is None:
            return self.error(mat, "模型未加载")
        # 创建blob并设置输入
        blob = self._blob_from_image(mat)
        net.setInput(blob)
        # 前向推理
        output = net.forward()
        # 获取分割掩码（取最大概率的类别）
        mask = np.argmax(output[0], axis=0).astype(np.uint8)
        # 获取原始图像尺寸
        h, w = mat.shape[:2]
        # 调整掩码大小到原始图像尺寸
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
        # 生成随机颜色映射
        colors = np.random.randint(0, 255, (int(mask.max()) + 2, 3), dtype=np.uint8)
        # 应用颜色映射
        color_mask = colors[mask]
        # 混合原图和彩色掩码
        result = cv2.addWeighted(mat, 1 - self.alpha, color_mask, self.alpha, 0)
        # 返回成功结果
        return self.ok(result, "语义分割完成")


class OnnxInference(_OnnxBase):
    """使用ONNX模型的通用数值推理节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "Onnx通用模型"
    # 推理结果属性（只读）
    value_result = Property("", name="推理结果", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        """初始化ONNX推理节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "ONNX推理"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 获取网络模型
        net = self._get_net()
        if net is None:
            return self.error(mat, "模型未加载")
        # 创建blob并设置输入
        blob = self._blob_from_image(mat)
        net.setInput(blob)
        # 前向推理
        output = net.forward()
        # 展平输出数组
        values = output.flatten()
        # 格式化输出（最多显示20个值）
        self.value_result = ", ".join([f"{v:.4f}" for v in values[:20]])
        # 返回成功结果
        return self.ok(mat, self.value_result)
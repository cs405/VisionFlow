"""分割提取节点：HSV色彩范围提取、按位与掩膜、无缝融合/背景替换"""

import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, VisionNodeData, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class HSVInRange(OpenCVNodeDataBase):
    """HSV色彩范围提取节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像分割提取模块"
    # H（色相）最小值属性
    h_low = Property(0, name="H最小值", group=PropertyGroupNames.RUN_PARAMETERS)
    # H（色相）最大值属性
    h_high = Property(180, name="H最大值", group=PropertyGroupNames.RUN_PARAMETERS)
    # S（饱和度）最小值属性
    s_low = Property(0, name="S最小值", group=PropertyGroupNames.RUN_PARAMETERS)
    # S（饱和度）最大值属性
    s_high = Property(255, name="S最大值", group=PropertyGroupNames.RUN_PARAMETERS)
    # V（明度）最小值属性
    v_low = Property(0, name="V最小值", group=PropertyGroupNames.RUN_PARAMETERS)
    # V（明度）最大值属性
    v_high = Property(255, name="V最大值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化HSV色彩提取节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "HSV色彩提取"

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
        # 将图像从BGR转换为HSV色彩空间
        hsv = cv2.cvtColor(mat, cv2.COLOR_BGR2HSV)
        # 创建HSV阈值下界数组
        lower = np.array([self.h_low, self.s_low, self.v_low], dtype=np.uint8)
        # 创建HSV阈值上界数组
        upper = np.array([self.h_high, self.s_high, self.v_high], dtype=np.uint8)
        # 根据HSV阈值范围创建掩膜
        mask = cv2.inRange(hsv, lower, upper)
        # 返回成功结果
        return self.ok(mask, "HSV色彩范围提取完成")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class BitwiseAnd(OpenCVNodeDataBase):
    """按位与掩膜节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像分割提取模块"

    def __init__(self):
        """初始化按位与掩膜节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "按位与掩膜"

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
        # 初始化掩膜为None
        mask = None
        # 遍历上游节点，查找掩膜图像（单通道灰度图）
        for n in self.from_node_datas:
            if isinstance(n, VisionNodeData) and n.mat is not None and len(n.mat.shape) == 2:
                mask = n.mat
                break
        # 如果没有找到掩膜输入，返回原图
        if mask is None:
            return self.ok(mat, "无掩膜输入，保持原图")
        # 对原图和掩膜执行按位与操作
        result = cv2.bitwise_and(mat, mat, mask=mask)
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class SeamlessCloneBackground(OpenCVNodeDataBase):
    """无缝融合/背景替换节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像分割提取模块"
    # 融合方式属性
    clone_type = Property("NORMAL_CLONE", name="融合方式", group=PropertyGroupNames.RUN_PARAMETERS)
    # 中心点X坐标属性
    center_x = Property(0, name="中心X", group=PropertyGroupNames.RUN_PARAMETERS)
    # 中心点Y坐标属性
    center_y = Property(0, name="中心Y", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化无缝融合节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "无缝融合/背景替换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src: 源节点数据（背景图像）
            from_node: 上游节点（前景图像）
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 获取输入图像（前景）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 如果没有背景图像，返回原图
        if src is None or src.mat is None:
            return self.ok(mat, "无背景图像，保持原图")
        # 融合方式映射字典
        clone_map = {
            "NORMAL_CLONE": cv2.NORMAL_CLONE,           # 普通克隆
            "MIXED_CLONE": cv2.MIXED_CLONE,             # 混合克隆
            "MONOCHROME_TRANSFER": cv2.MONOCHROME_TRANSFER  # 单色转移
        }
        # 创建全白掩膜（与前景图像相同尺寸）
        mask = np.ones(mat.shape[:2], dtype=np.uint8) * 255
        # 计算融合中心点（如果未指定，使用图像中心）
        cx = self.center_x or mat.shape[1] // 2
        cy = self.center_y or mat.shape[0] // 2
        # 执行无缝融合
        result = cv2.seamlessClone(mat, src.mat, mask, (cx, cy),
                                    clone_map.get(self.clone_type, cv2.NORMAL_CLONE))
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat
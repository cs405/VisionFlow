"""形态学节点：膨胀、腐蚀、开运算、闭运算、形态学梯度、顶帽、黑帽"""

import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class _MorphBase(OpenCVNodeDataBase):
    """形态学节点基类，包含卷积核设置"""
    # 卷积核大小属性
    kernel_size = Property(3, name="卷积核大小", group=PropertyGroupNames.RUN_PARAMETERS)
    # 迭代次数属性
    iterations = Property(1, name="迭代次数", group=PropertyGroupNames.RUN_PARAMETERS)
    # 卷积核形状属性（RECT矩形、ELLIPSE椭圆形、CROSS十字形）
    kernel_shape = Property("RECT", name="卷积核形状", group=PropertyGroupNames.RUN_PARAMETERS,
                            editor="choices", choices=["RECT", "ELLIPSE", "CROSS"])

    # 形态学操作类型（子类需要设置）
    _morph_op: int = cv2.MORPH_DILATE

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
        # 卷积核形状映射字典
        shapes = {
            "RECT": cv2.MORPH_RECT,      # 矩形卷积核
            "ELLIPSE": cv2.MORPH_ELLIPSE, # 椭圆形卷积核
            "CROSS": cv2.MORPH_CROSS     # 十字形卷积核
        }
        # 获取卷积核
        kernel = cv2.getStructuringElement(
            shapes.get(self.kernel_shape, cv2.MORPH_RECT),  # 形状
            (self.kernel_size, self.kernel_size)           # 大小
        )
        # 执行形态学操作
        result = cv2.morphologyEx(mat, self._morph_op, kernel, iterations=self.iterations)
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        # 将当前处理后的图像设置为结果图像源
        self._result_image_source = self._mat


class Dilate(_MorphBase):
    """膨胀节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "形态学模块"
    # 形态学操作类型：膨胀
    _morph_op = cv2.MORPH_DILATE

    def __init__(self):
        """初始化膨胀节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "膨胀"


class Erode(_MorphBase):
    """腐蚀节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "形态学模块"
    # 形态学操作类型：腐蚀
    _morph_op = cv2.MORPH_ERODE

    def __init__(self):
        """初始化腐蚀节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "腐蚀"


class Open(_MorphBase):
    """开运算节点（先腐蚀后膨胀）"""
    # 节点所属分组（用于UI分类）
    __group__ = "形态学模块"
    # 形态学操作类型：开运算
    _morph_op = cv2.MORPH_OPEN

    def __init__(self):
        """初始化开运算节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "开运算"


class Close(_MorphBase):
    """闭运算节点（先膨胀后腐蚀）"""
    # 节点所属分组（用于UI分类）
    __group__ = "形态学模块"
    # 形态学操作类型：闭运算
    _morph_op = cv2.MORPH_CLOSE

    def __init__(self):
        """初始化闭运算节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "闭运算"


class Gradient(_MorphBase):
    """形态学梯度节点（膨胀减腐蚀）"""
    # 节点所属分组（用于UI分类）
    __group__ = "形态学模块"
    # 形态学操作类型：形态学梯度
    _morph_op = cv2.MORPH_GRADIENT

    def __init__(self):
        """初始化形态学梯度节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "形态学梯度"


class TopHat(_MorphBase):
    """顶帽节点（原图减开运算）"""
    # 节点所属分组（用于UI分类）
    __group__ = "形态学模块"
    # 形态学操作类型：顶帽
    _morph_op = cv2.MORPH_TOPHAT

    def __init__(self):
        """初始化顶帽节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "顶帽"


class BlackHat(_MorphBase):
    """黑帽节点（闭运算减原图）"""
    # 节点所属分组（用于UI分类）
    __group__ = "形态学模块"
    # 形态学操作类型：黑帽
    _morph_op = cv2.MORPH_BLACKHAT

    def __init__(self):
        """初始化黑帽节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "黑帽"
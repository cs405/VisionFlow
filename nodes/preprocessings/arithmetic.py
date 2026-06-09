"""算术运算节点：加/减、乘/除、幂运算。"""

import cv2
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class AddSubtract(OpenCVNodeDataBase):
    """图像加减节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像预处理模块"
    # 运算类型属性（Add/Subtract）
    # operation = Property("Add", name="运算", group=PropertyGroupNames.RUN_PARAMETERS)
    operation = Property("Add", name="运算", group=PropertyGroupNames.RUN_PARAMETERS,
                         editor="choices", choices=["Add", "Subtract"])
    # 标量值属性
    scalar = Property(50.0, name="标量值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化图像加减节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "图像加减"

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
        # 根据运算类型执行加法或减法
        if self.operation == "Add":
            # 加法：图像每个像素加上标量值
            result = cv2.add(mat, self.scalar)
        else:
            # 减法：图像每个像素减去标量值
            result = cv2.subtract(mat, self.scalar)
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class MultiplyDivide(OpenCVNodeDataBase):
    """图像乘除节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像预处理模块"
    # 运算类型属性（Multiply/Divide）
    operation = Property("Multiply", name="运算", group=PropertyGroupNames.RUN_PARAMETERS,
                         editor="choices", choices=["Multiply", "Divide"])
    # 标量值属性
    scalar = Property(2.0, name="标量值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化图像乘除节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "图像乘除"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 根据运算类型执行乘法或除法
        if self.operation == "Multiply":
            # 乘法：图像每个像素乘以标量值
            result = cv2.multiply(mat, self.scalar)
        else:
            # 除法：图像每个像素除以标量值
            result = cv2.divide(mat, self.scalar)
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class Pow(OpenCVNodeDataBase):
    """幂运算节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像预处理模块"
    # 幂值属性
    power = Property(2.0, name="幂值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化幂运算节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "幂运算"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        """核心处理逻辑"""
        # 获取输入图像（优先使用_prepared_input，否则使用上游节点的mat）
        mat = self.get_input_mat(from_node.mat if from_node else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像")
        # 执行幂运算：图像每个像素的power次方
        result = cv2.pow(mat, self.power)
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat
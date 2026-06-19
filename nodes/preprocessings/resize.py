"""缩放节点 - 按比例缩放或固定尺寸缩放"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Resize(OpenCVNodeDataBase):
    """图像缩放节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "图像预处理模块"
    # 缩放模式属性（Scale:按比例缩放，Fixed:固定尺寸）
    resize_mode = Property("Scale", name="缩放模式", group=PropertyGroupNames.RUN_PARAMETERS,
                           editor="choices", choices=["Scale", "Fixed"])
    # 缩放比例属性（仅在Scale模式下使用）
    scale = Property(1.0, name="缩放比例", group=PropertyGroupNames.RUN_PARAMETERS)
    # 目标宽度属性（仅在Fixed模式下使用）
    width = Property(640, name="目标宽度", group=PropertyGroupNames.RUN_PARAMETERS)
    # 目标高度属性（仅在Fixed模式下使用）
    height = Property(640, name="目标高度", group=PropertyGroupNames.RUN_PARAMETERS)
    # 插值方式属性（NEAREST, LINEAR, AREA, CUBIC, LANCZOS4）
    interpolation = Property("LINEAR", name="插值方式", group=PropertyGroupNames.RUN_PARAMETERS,
                             editor="choices", choices=["NEAREST", "LINEAR", "AREA", "CUBIC", "LANCZOS4"]
                             )

    def __init__(self):
        """初始化图像缩放节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "图像缩放"

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

        # 获取插值方式常量
        inter = getattr(cv2, f"INTER_{self.interpolation}", cv2.INTER_LINEAR)
        # 根据缩放模式计算目标尺寸
        if self.resize_mode == "Scale":
            # 按比例缩放
            w = int(mat.shape[1] * self.scale) if self.scale else mat.shape[1]
            h = int(mat.shape[0] * self.scale) if self.scale else mat.shape[0]
        else:
            # 固定尺寸缩放，确保宽高为整数类型
            w, h = int(self.width), int(self.height)
        # 确保尺寸至少为1x1
        w, h = max(1, w), max(1, h)
        # 确保输入为连续内存布局，避免cv2.resize在非连续数组上报错
        if not mat.flags['C_CONTIGUOUS']:
            mat = np.ascontiguousarray(mat)
        # 执行图像缩放，异常时回退原图保证连续执行不中断
        try:
            result = cv2.resize(mat, (w, h), interpolation=inter)
        except cv2.error as e:
            return self.ok(mat, message=f"缩放失败(已回退原图): {e}")
        # 返回成功结果
        return self.ok(result)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat
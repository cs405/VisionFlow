"""裁剪节点 — 根据 ROI 设置裁剪输入图像并输出裁剪后的区域。
"""

from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class CropNode(OpenCVNodeDataBase):
    """裁剪节点：设置 ROI 后将输入图像裁剪到指定区域并输出。

    ROI 裁剪由 ROINodeData.invoke() 自动处理：
    - 无 ROI → 输出原图
    - 绘制/输入/来自上游 → 输出裁剪后的 ROI 区域
    """
    __group__ = "图像分割提取模块"

    def __init__(self):
        super().__init__()
        self.name = "裁剪"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        h, w = mat.shape[:2]
        return self.ok(mat, f"裁剪区域: {w}x{h}")

    def _update_result_image_source(self):
        self._result_image_source = self._mat

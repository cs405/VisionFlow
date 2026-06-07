"""Image file source node - loads images from file list.
"""

import os
import cv2
import numpy as np

from core.node_base import OpenCVNodeDataBase, SrcFilesVisionNodeData, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class SrcImageFilesNodeData(SrcFilesVisionNodeData, OpenCVNodeDataBase):
    """Loads images from a file list. The primary data source for image processing.

    """
    __group__ = "图像数据源"

    def __init__(self):
        SrcFilesVisionNodeData.__init__(self)
        OpenCVNodeDataBase.__init__(self)
        self.name = "图像文件"

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        path = self.src_file_path
        if not path or not os.path.exists(path):
            return self.error(None, f"文件不存在: {path}")

        mat = cv2.imread(path, cv2.IMREAD_COLOR)
        if mat is None:
            return self.error(None, f"无法读取图像: {path}")

        self.pixel_width = mat.shape[1]
        self.pixel_height = mat.shape[0]
        self.image_color_type = mat.dtype.type.__name__ if hasattr(mat.dtype, 'type') else str(mat.dtype)
        return self.ok(mat, f"已加载: {os.path.basename(path)}")

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def is_valid(self, mat: np.ndarray) -> bool:
        return mat is not None and mat.size > 0

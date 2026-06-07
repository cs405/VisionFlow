"""Zoo image sources - system-provided test image datasets.
Each subclass filters to a specific set of test images.
"""

import os
import cv2
import numpy as np

from core.node_base import OpenCVNodeDataBase, SrcFilesVisionNodeData, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class _ZooSrcImageBase(SrcFilesVisionNodeData, OpenCVNodeDataBase):
    """Base for zoo image sources with path filtering.

    Each subclass defines a _path_filter string to select a subset
    of the assets/images directory. The file list is populated
    during __init__ so thumbnails appear immediately after node creation.
    """
    __group__ = "系统数据源"
    _path_filter: str = ""

    def __init__(self):
        SrcFilesVisionNodeData.__init__(self)
        OpenCVNodeDataBase.__init__(self)
        self.load_default()

    def load_default(self):
        super().load_default()
        # Filter to matching paths
        if self._path_filter:
            self.src_file_paths = [p for p in self.src_file_paths
                                    if self._path_filter.lower() in p.lower()]
            if self.src_file_paths:
                self.src_file_path = self.src_file_paths[0]

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        path = self.src_file_path
        if not path or not os.path.exists(path):
            return self.error(None, f"文件不存在: {path}")
        mat = cv2.imread(path, cv2.IMREAD_COLOR)
        if mat is None:
            return self.error(None, f"无法读取图像: {path}")
        self.pixel_width = mat.shape[1]
        self.pixel_height = mat.shape[0]
        return self.ok(mat, f"已加载: {os.path.basename(path)}")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class OpenCVSrcImageFilesNodeData(_ZooSrcImageBase):
    __group__ = "系统数据源"
    _path_filter = "OpenCV"
    def __init__(self): super().__init__(); self.name = "OpenCV测试图"


class BitholderSrcImageFilesNodeData(_ZooSrcImageBase):
    __group__ = "系统数据源"
    _path_filter = "multi_view_bitholder_cam"
    def __init__(self): super().__init__(); self.name = "刀架测试图"


class BoardSrcImageFilesNodeData(_ZooSrcImageBase):
    __group__ = "系统数据源"
    _path_filter = "board"
    def __init__(self): super().__init__(); self.name = "电路板测试图"


class CardoorSrcImageFilesNodeData(_ZooSrcImageBase):
    __group__ = "系统数据源"
    _path_filter = "car_door"
    def __init__(self): super().__init__(); self.name = "车门测试图"


class HalconSrcImageFilesNodeData(_ZooSrcImageBase):
    __group__ = "系统数据源"
    _path_filter = "BaseImages"
    def __init__(self): super().__init__(); self.name = "Halcon示例图"


class PersonsSrcImageFilesNodeData(_ZooSrcImageBase):
    __group__ = "系统数据源"
    _path_filter = "Person"
    def __init__(self): super().__init__(); self.name = "行人检测图"


class PillbagSrcImageFilesNodeData(_ZooSrcImageBase):
    __group__ = "系统数据源"
    _path_filter = "pill_bag"
    def __init__(self): super().__init__(); self.name = "药袋检测图"


class PillMagnesiumSrcImageFilesNodeData(_ZooSrcImageBase):
    __group__ = "系统数据源"
    _path_filter = "pill_magnesium_crack"
    def __init__(self): super().__init__(); self.name = "药品裂纹图"


class PipeJointsSrcImageFilesNodeData(_ZooSrcImageBase):
    __group__ = "系统数据源"
    _path_filter = "multi_view_pipe_joints_cam"
    def __init__(self): super().__init__(); self.name = "管接头测试图"


class RadiusGaugesSrcImageFilesNodeData(_ZooSrcImageBase):
    __group__ = "系统数据源"
    _path_filter = "radius-gauges"
    def __init__(self): super().__init__(); self.name = "半径规测试图"

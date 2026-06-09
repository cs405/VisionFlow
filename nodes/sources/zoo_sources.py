"""系统图像源 - 系统提供的测试图像数据集。
每个子类过滤到特定的测试图像集。
"""

import os
import cv2
import numpy as np

from core.node_base import OpenCVNodeDataBase, SrcFilesVisionNodeData, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class _ZooSrcImageBase(SrcFilesVisionNodeData, OpenCVNodeDataBase):
    """系统图像源基类，支持路径过滤。

    每个子类定义 _path_filter 字符串来选择 assets/images 目录的子集。
    文件列表在 __init__ 期间填充，以便在节点创建后立即显示缩略图。
    """
    # 节点所属分组（用于UI分类）
    __group__ = "系统数据源"
    # 路径过滤器字符串（子类必须设置）
    _path_filter: str = ""

    def __init__(self):
        """初始化系统图像源"""
        # 调用父类SrcFilesVisionNodeData的构造函数
        SrcFilesVisionNodeData.__init__(self)
        # 调用父类OpenCVNodeDataBase的构造函数
        OpenCVNodeDataBase.__init__(self)
        # 加载默认设置
        self.load_default()

    def load_default(self):
        """加载默认设置，过滤匹配路径的图像"""
        # 调用父类的load_default方法
        super().load_default()
        # 如果设置了路径过滤器
        if self._path_filter:
            # 过滤文件路径列表，只保留包含过滤器字符串的路径
            self.src_file_paths = [p for p in self.src_file_paths
                                    if self._path_filter.lower() in p.lower()]
            # 如果过滤后还有文件，选中第一个
            if self.src_file_paths:
                self.src_file_path = self.src_file_paths[0]

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src_image_node_data: 源节点数据
            from_node_data: 上游节点数据
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 获取当前文件路径
        path = self.src_file_path
        # 如果路径为空或文件不存在
        if not path or not os.path.exists(path):
            return self.error(None, f"文件不存在: {path}")
        # 使用OpenCV读取图像（彩色模式）
        mat = cv2.imread(path, cv2.IMREAD_COLOR)
        # 如果读取失败
        if mat is None:
            return self.error(None, f"无法读取图像: {path}")
        # 记录图像宽度（像素）
        self.pixel_width = mat.shape[1]
        # 记录图像高度（像素）
        self.pixel_height = mat.shape[0]
        # 返回成功结果
        return self.ok(mat, f"已加载: {os.path.basename(path)}")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class OpenCVSrcImageFilesNodeData(_ZooSrcImageBase):
    """OpenCV测试图节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "系统数据源"
    # 路径过滤器：匹配"OpenCV"
    _path_filter = "OpenCV"

    def __init__(self):
        """初始化OpenCV测试图节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "OpenCV测试图"


class BitholderSrcImageFilesNodeData(_ZooSrcImageBase):
    """刀架测试图节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "系统数据源"
    # 路径过滤器：匹配"multi_view_bitholder_cam"
    _path_filter = "multi_view_bitholder_cam"

    def __init__(self):
        """初始化刀架测试图节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "刀架测试图"


class BoardSrcImageFilesNodeData(_ZooSrcImageBase):
    """电路板测试图节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "系统数据源"
    # 路径过滤器：匹配"board"
    _path_filter = "board"

    def __init__(self):
        """初始化电路板测试图节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "电路板测试图"


class CardoorSrcImageFilesNodeData(_ZooSrcImageBase):
    """车门测试图节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "系统数据源"
    # 路径过滤器：匹配"car_door"
    _path_filter = "car_door"

    def __init__(self):
        """初始化车门测试图节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "车门测试图"


class HalconSrcImageFilesNodeData(_ZooSrcImageBase):
    """Halcon示例图节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "系统数据源"
    # 路径过滤器：匹配"BaseImages"
    _path_filter = "BaseImages"

    def __init__(self):
        """初始化Halcon示例图节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "Halcon示例图"


class PersonsSrcImageFilesNodeData(_ZooSrcImageBase):
    """行人检测图节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "系统数据源"
    # 路径过滤器：匹配"Person"
    _path_filter = "Person"

    def __init__(self):
        """初始化行人检测图节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "行人检测图"


class PillbagSrcImageFilesNodeData(_ZooSrcImageBase):
    """药袋检测图节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "系统数据源"
    # 路径过滤器：匹配"pill_bag"
    _path_filter = "pill_bag"

    def __init__(self):
        """初始化药袋检测图节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "药袋检测图"


class PillMagnesiumSrcImageFilesNodeData(_ZooSrcImageBase):
    """药品裂纹图节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "系统数据源"
    # 路径过滤器：匹配"pill_magnesium_crack"
    _path_filter = "pill_magnesium_crack"

    def __init__(self):
        """初始化药品裂纹图节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "药品裂纹图"


class PipeJointsSrcImageFilesNodeData(_ZooSrcImageBase):
    """管接头测试图节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "系统数据源"
    # 路径过滤器：匹配"multi_view_pipe_joints_cam"
    _path_filter = "multi_view_pipe_joints_cam"

    def __init__(self):
        """初始化管接头测试图节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "管接头测试图"


class RadiusGaugesSrcImageFilesNodeData(_ZooSrcImageBase):
    """半径规测试图节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "系统数据源"
    # 路径过滤器：匹配"radius-gauges"
    _path_filter = "radius-gauges"

    def __init__(self):
        """初始化半径规测试图节点"""
        super().__init__()
        # 设置节点显示名称
        self.name = "半径规测试图"
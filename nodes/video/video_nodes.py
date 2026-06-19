"""视频处理节点：MOG背景减除、视频写入器。"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class MOG(OpenCVNodeDataBase):
    """MOG2背景减除节点，用于运动检测"""
    # 节点所属分组（用于UI分类）
    __group__ = "视频处理模块"
    # 历史帧数属性（用于建立背景模型的帧数）
    history = Property(500, name="历史帧数", group=PropertyGroupNames.RUN_PARAMETERS)
    # 方差阈值属性（用于区分前景和背景）
    var_threshold = Property(16.0, name="方差阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    # 是否检测阴影属性
    detect_shadows = Property(True, name="检测阴影", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        """初始化MOG背景减除节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "MOG背景减除"
        # MOG2背景减除器对象，初始为None
        self._mog = None

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
        # 如果背景减除器尚未创建
        if self._mog is None:
            # 创建MOG2背景减除器
            self._mog = cv2.createBackgroundSubtractorMOG2(self.history, self.var_threshold, self.detect_shadows)
        # 应用背景减除，获取前景掩膜
        mask = self._mog.apply(mat)
        # 返回成功结果
        return self.ok(mask, "前景检测完成")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat


class VideoWriter(OpenCVNodeDataBase):
    """视频写入节点，将帧写入视频文件"""
    # 节点所属分组（用于UI分类）
    __group__ = "视频处理模块"
    # 输出路径属性
    output_path = Property("output.avi", name="输出路径", group=PropertyGroupNames.RUN_PARAMETERS,
                           description="视频输出文件路径 (.avi/.mp4)")
    # 帧率属性
    fps = Property(30.0, name="帧率", group=PropertyGroupNames.RUN_PARAMETERS,
                    description="输出视频帧率")
    # 编码格式属性（FourCC编码代码）
    fourcc_code = Property("XVID", name="编码格式", group=PropertyGroupNames.RUN_PARAMETERS,
                           description="FourCC 编码代码 (XVID/MJPG/H264/MP4V)")
    # 已写入帧数属性（只读）
    frame_count = Property(0, name="已写入帧数", group=PropertyGroupNames.RESULT_PARAMETERS,
                           readonly=True)

    # 有效的FourCC编码格式集合
    VALID_FOURCC = {"XVID", "MJPG", "H264", "MP4V", "DIVX", "I420", "IYUV", "WMV1", "WMV2"}

    def __init__(self):
        """初始化视频写入节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "视频写入"
        # 视频写入器对象，初始为None
        self._writer: cv2.VideoWriter | None = None

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
        # 如果视频写入器尚未创建
        if self._writer is None:
            # 检查FourCC编码长度是否为4
            if len(self.fourcc_code) != 4:
                return self.error(None, f"无效的 FourCC 编码: '{self.fourcc_code}' (需要4个字符)")
            # 如果编码格式不在有效列表中，记录警告
            if self.fourcc_code not in self.VALID_FOURCC:
                self._log_warning(f"未知编码格式: {self.fourcc_code}，尝试使用")
            # 获取图像尺寸
            h, w = mat.shape[:2]
            try:
                # 创建FourCC编码
                fourcc = cv2.VideoWriter_fourcc(*self.fourcc_code)
                # 创建视频写入器
                self._writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, (w, h))
                # 如果无法打开视频写入器
                if not self._writer.isOpened():
                    return self.error(None, f"无法打开视频写入: {self.output_path}")
            except Exception as e:
                return self.error(None, f"初始化视频编码器失败: {e}")
        # 写入当前帧
        self._writer.write(mat)
        # 更新已写入帧数
        self.frame_count += 1
        # 返回成功结果
        return self.ok(mat, f"写入第 {self.frame_count} 帧")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat

    def dispose(self):
        """释放资源"""
        # 如果视频写入器存在，释放资源
        if self._writer:
            self._writer.release()
            self._writer = None
        # 调用父类的dispose方法
        super().dispose()
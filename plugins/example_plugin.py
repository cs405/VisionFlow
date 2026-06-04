"""
示例插件 - 演示如何通过插件系统扩展新的算子节点

插件使用说明：
1. 将自定义节点类放在 plugins/ 目录下
2. 节点类必须继承 NodeBase
3. 实现必要的属性和 evaluate 方法
4. 程序启动时会自动加载 plugins/ 目录下的所有插件
"""

import cv2
import numpy as np
from typing import Any, Dict

# 导入节点基类
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


# ========== 示例插件1：图像锐化节点 ==========
class SharpenNode(NodeBase):
    """
    图像锐化节点
    使用拉普拉斯算子或非锐化掩模增强图像边缘
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "图像锐化"
        self.category = "增强"
        self.description = "增强图像边缘，使图像更清晰"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像")
        ]
        self.output_sockets = [
            Socket("image", DataType.IMAGE, is_input=False, description="锐化后的图像"),
            Socket("info", DataType.STRING, is_input=False, description="处理信息")
        ]

        # 参数
        self.parameters = {
            "method": NodeParameter(
                name="method",
                label="锐化方法",
                type=ParamType.ENUM,
                default="unsharp_mask",
                options=["laplacian", "unsharp_mask", "high_boost"]
            ),
            "strength": NodeParameter(
                name="strength",
                label="锐化强度",
                type=ParamType.FLOAT_SLIDER,
                default=1.0,
                min=0.5,
                max=3.0,
                step=0.1
            ),
            "kernel_size": NodeParameter(
                name="kernel_size",
                label="核大小",
                type=ParamType.SLIDER,
                default=3,
                min=3,
                max=7,
                step=2
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"image": None, "info": "无输入图像"}

        method = self.get_param("method")
        strength = self.get_param("strength")
        ksize = self.get_param("kernel_size")

        # 确保核大小为奇数
        if ksize % 2 == 0:
            ksize += 1

        result = img.copy()

        if method == "laplacian":
            # 拉普拉斯锐化
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                laplacian = cv2.Laplacian(gray, cv2.CV_64F, ksize=ksize)
                laplacian = np.uint8(np.abs(laplacian) * strength)
                result = cv2.cvtColor(gray + laplacian, cv2.COLOR_GRAY2BGR)
            else:
                laplacian = cv2.Laplacian(img, cv2.CV_64F, ksize=ksize)
                laplacian = np.uint8(np.abs(laplacian) * strength)
                result = img + laplacian

        elif method == "unsharp_mask":
            # 非锐化掩模
            blurred = cv2.GaussianBlur(img, (ksize, ksize), 0)
            result = cv2.addWeighted(img, 1 + strength, blurred, -strength, 0)

        else:  # high_boost
            # 高通滤波增强
            blurred = cv2.GaussianBlur(img, (ksize, ksize), 0)
            mask = cv2.subtract(img, blurred)
            result = cv2.addWeighted(img, 1, mask, strength, 0)

        info = f"方法: {method}, 强度: {strength}"

        return {"image": result, "info": info}


# ========== 示例插件2：图像旋转节点 ==========
class RotateNode(NodeBase):
    """
    图像旋转节点
    按指定角度旋转图像
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "图像旋转"
        self.category = "几何变换"
        self.description = "旋转图像指定角度"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像")
        ]
        self.output_sockets = [
            Socket("image", DataType.IMAGE, is_input=False, description="旋转后的图像"),
            Socket("info", DataType.STRING, is_input=False, description="旋转信息")
        ]

        # 参数
        self.parameters = {
            "angle": NodeParameter(
                name="angle",
                label="旋转角度",
                type=ParamType.SLIDER,
                default=0,
                min=-360,
                max=360,
                step=1
            ),
            "scale": NodeParameter(
                name="scale",
                label="缩放比例",
                type=ParamType.FLOAT_SLIDER,
                default=1.0,
                min=0.5,
                max=2.0,
                step=0.05
            ),
            "auto_crop": NodeParameter(
                name="auto_crop",
                label="自动裁剪",
                type=ParamType.BOOL,
                default=False
            ),
            "fill_color": NodeParameter(
                name="fill_color",
                label="填充颜色",
                type=ParamType.ENUM,
                default="black",
                options=["black", "white", "border_replicate"]
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"image": None, "info": "无输入图像"}

        angle = self.get_param("angle")
        scale = self.get_param("scale")
        auto_crop = self.get_param("auto_crop")
        fill_color = self.get_param("fill_color")

        h, w = img.shape[:2]

        # 获取旋转矩阵
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, scale)

        # 处理填充颜色
        if fill_color == "border_replicate":
            border_mode = cv2.BORDER_REPLICATE
            fill_color_val = None
        else:
            border_mode = cv2.BORDER_CONSTANT
            fill_color_val = (0, 0, 0) if fill_color == "black" else (255, 255, 255)

        # 执行旋转
        if auto_crop:
            # 计算新尺寸
            cos = abs(M[0, 0])
            sin = abs(M[0, 1])
            new_w = int((h * sin) + (w * cos))
            new_h = int((h * cos) + (w * sin))
            M[0, 2] += (new_w / 2) - center[0]
            M[1, 2] += (new_h / 2) - center[1]
            result = cv2.warpAffine(img, M, (new_w, new_h),
                                    borderMode=border_mode, borderValue=fill_color_val)
            info = f"旋转 {angle}°, 缩放 {scale}, 新尺寸: {new_w}x{new_h}"
        else:
            result = cv2.warpAffine(img, M, (w, h),
                                    borderMode=border_mode, borderValue=fill_color_val)
            info = f"旋转 {angle}°, 缩放 {scale}, 尺寸不变"

        return {"image": result, "info": info}


# ========== 示例插件3：图像翻转节点 ==========
class FlipNode(NodeBase):
    """
    图像翻转节点
    水平、垂直或同时翻转图像
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "图像翻转"
        self.category = "几何变换"
        self.description = "水平、垂直或同时翻转图像"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像")
        ]
        self.output_sockets = [
            Socket("image", DataType.IMAGE, is_input=False, description="翻转后的图像"),
            Socket("info", DataType.STRING, is_input=False, description="翻转信息")
        ]

        # 参数
        self.parameters = {
            "mode": NodeParameter(
                name="mode",
                label="翻转模式",
                type=ParamType.ENUM,
                default="horizontal",
                options=["horizontal", "vertical", "both"]
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"image": None, "info": "无输入图像"}

        mode = self.get_param("mode")

        if mode == "horizontal":
            result = cv2.flip(img, 1)
            info = "水平翻转"
        elif mode == "vertical":
            result = cv2.flip(img, 0)
            info = "垂直翻转"
        else:  # both
            result = cv2.flip(img, -1)
            info = "水平+垂直翻转"

        return {"image": result, "info": info}


# ========== 示例插件4：通道分离节点 ==========
class SplitChannelsNode(NodeBase):
    """
    通道分离节点
    将彩色图像分离为单通道图像
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "通道分离"
        self.category = "颜色处理"
        self.description = "将彩色图像分离为R、G、B单通道图像"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入彩色图像")
        ]
        self.output_sockets = [
            Socket("R", DataType.GRAY_IMAGE, is_input=False, description="R通道"),
            Socket("G", DataType.GRAY_IMAGE, is_input=False, description="G通道"),
            Socket("B", DataType.GRAY_IMAGE, is_input=False, description="B通道"),
            Socket("info", DataType.STRING, is_input=False, description="处理信息")
        ]

        # 参数
        self.parameters = {
            "order": NodeParameter(
                name="order",
                label="颜色顺序",
                type=ParamType.ENUM,
                default="bgr",
                options=["bgr", "rgb"]
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"R": None, "G": None, "B": None, "info": "无输入图像"}

        if len(img.shape) != 3 or img.shape[2] != 3:
            return {"R": None, "G": None, "B": None, "info": "需要彩色图像"}

        order = self.get_param("order")

        if order == "bgr":
            # OpenCV默认BGR顺序
            b, g, r = cv2.split(img)
            info = "BGR通道分离: B通道, G通道, R通道"
        else:
            # RGB顺序（需要转换）
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            r, g, b = cv2.split(rgb)
            info = "RGB通道分离: R通道, G通道, B通道"

        return {"B": b, "G": g, "R": r, "info": info}


# ========== 示例插件5：直方图均衡化节点 ==========
class HistogramEqualizeNode(NodeBase):
    """
    直方图均衡化节点
    增强图像对比度
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "直方图均衡化"
        self.category = "增强"
        self.description = "增强图像对比度"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像")
        ]
        self.output_sockets = [
            Socket("image", DataType.IMAGE, is_input=False, description="均衡化后的图像"),
            Socket("info", DataType.STRING, is_input=False, description="处理信息")
        ]

        # 参数
        self.parameters = {
            "mode": NodeParameter(
                name="mode",
                label="均衡化模式",
                type=ParamType.ENUM,
                default="global",
                options=["global", "clahe"]
            ),
            "clip_limit": NodeParameter(
                name="clip_limit",
                label="CLAHE裁剪限制",
                type=ParamType.FLOAT_SLIDER,
                default=2.0,
                min=1.0,
                max=10.0,
                step=0.5
            ),
            "grid_size": NodeParameter(
                name="grid_size",
                label="CLAHE网格大小",
                type=ParamType.SLIDER,
                default=8,
                min=4,
                max=16,
                step=1
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"image": None, "info": "无输入图像"}

        mode = self.get_param("mode")

        if len(img.shape) == 3:
            # 彩色图像：转换到YUV空间，对Y通道均衡化
            yuv = cv2.cvtColor(img, cv2.COLOR_BGR2YUV)
            y, u, v = cv2.split(yuv)

            if mode == "global":
                y_eq = cv2.equalizeHist(y)
                info = "全局直方图均衡化 (YUV)"
            else:
                clahe = cv2.createCLAHE(
                    clipLimit=self.get_param("clip_limit"),
                    tileGridSize=(self.get_param("grid_size"), self.get_param("grid_size"))
                )
                y_eq = clahe.apply(y)
                info = "CLAHE自适应均衡化 (YUV)"

            yuv_eq = cv2.merge([y_eq, u, v])
            result = cv2.cvtColor(yuv_eq, cv2.COLOR_YUV2BGR)
        else:
            # 灰度图像
            if mode == "global":
                result = cv2.equalizeHist(img)
                info = "全局直方图均衡化 (灰度)"
            else:
                clahe = cv2.createCLAHE(
                    clipLimit=self.get_param("clip_limit"),
                    tileGridSize=(self.get_param("grid_size"), self.get_param("grid_size"))
                )
                result = clahe.apply(img)
                info = "CLAHE自适应均衡化 (灰度)"

        return {"image": result, "info": info}


# ========== 导出所有插件节点 ==========
# 程序启动时会自动发现这些类并注册到节点工具箱
__all__ = [
    'SharpenNode',
    'RotateNode',
    'FlipNode',
    'SplitChannelsNode',
    'HistogramEqualizeNode'
]
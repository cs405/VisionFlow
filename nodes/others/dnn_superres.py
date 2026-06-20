import os
import cv2
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class DnnSuperres(OpenCVNodeDataBase):
    """DNN 超分辨率节点。

    优先使用 cv2.dnn_superres 模块进行深度学习超分放大，
    如果模型文件不存在或 OpenCV 版本不支持，则回退到双三次插值。
    支持的模型：EDSR、ESPCN、FSRCNN、LapSRN。
    """
    __group__ = "其他模块"
    scale = Property(4, name="放大倍数", group=PropertyGroupNames.RUN_PARAMETERS)
    model_name = Property("EDSR", name="模型名称",
                          group=PropertyGroupNames.RUN_PARAMETERS,
                          editor="choices",
                          choices=["EDSR", "ESPCN", "FSRCNN", "LapSRN"])
    model_path = Property("", name="模型路径 (.pb)",
                          group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "DNN超分辨率"
        self._dnn_sr = None

    def _ensure_dnn_sr(self):
        """惰性初始化 DNN 超分模型。"""
        if self._dnn_sr is not None:
            return self._dnn_sr
        if not hasattr(cv2, 'dnn_superres'):
            return None
        try:
            sr = cv2.dnn_superres.DnnSuperResImpl_create()
            model_path = self.model_path or self._default_model_path()
            if model_path and os.path.isfile(model_path):
                sr.readModel(model_path)
                sr.setModel(self.model_name.lower(), self.scale)
                self._dnn_sr = sr
                return sr
        except Exception:
            pass
        return None

    def _default_model_path(self):
        """获取默认模型文件路径。"""
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(__file__)))
        model_dir = os.path.join(project_root, 'assets', 'models', 'dnn_superres')
        filename = f"{self.model_name.upper()}_x{self.scale}.pb"
        return os.path.join(model_dir, filename)

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        try:
            sr = self._ensure_dnn_sr()
            if sr is not None:
                result = sr.upsample(mat)
                return self.ok(result, f"DNN 超分 {self.scale}x ({self.model_name})")
            # 回退：双三次插值
            result = cv2.resize(
                mat,
                (mat.shape[1] * self.scale, mat.shape[0] * self.scale),
                interpolation=cv2.INTER_CUBIC
            )
            return self.ok(result, f"双三次插值 {self.scale}x (DNN模型未找到)")
        except Exception as e:
            return self.error(mat, str(e))

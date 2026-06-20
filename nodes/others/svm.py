"""SVM 像素分类 — 用 SVM 对图像前景/背景像素分类，输出分割掩膜"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class SVM(OpenCVNodeDataBase):
    __group__ = "其他模块"
    kernel_type = Property("RBF", name="核函数", group=PropertyGroupNames.RUN_PARAMETERS,
                           editor="choices", choices=["LINEAR", "RBF", "POLY"])
    sample_count = Property(1000, name="采样点数", group=PropertyGroupNames.RUN_PARAMETERS,
                            min_val=100, max_val=10000, step=100)

    def __init__(self):
        super().__init__()
        self.name = "SVM像素分类"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        h, w = gray.shape[:2]

        # 提取像素特征：坐标(x,y) + 灰度值 + 局部均值
        ys, xs = np.mgrid[0:h, 0:w]
        local_mean = cv2.blur(gray, (15, 15))
        features = np.stack([xs.ravel() / w, ys.ravel() / h,
                             gray.ravel() / 255.0, local_mean.ravel() / 255.0], axis=1).astype(np.float32)

        # 采样训练数据：亮区域 = 前景(1)，暗区域 = 背景(0)
        indices = np.random.choice(h * w, min(self.sample_count, h * w), replace=False)
        train_data = features[indices]
        labels = (train_data[:, 2] > 0.5).astype(np.int32)  # 灰度 > 128 为前景
        labels = labels * 2 - 1  # SVM 标签需要 +1/-1

        # 训练 SVM
        svm = cv2.ml.SVM_create()
        svm.setType(cv2.ml.SVM_C_SVC)
        kernel_map = {"LINEAR": cv2.ml.SVM_LINEAR, "RBF": cv2.ml.SVM_RBF, "POLY": cv2.ml.SVM_POLY}
        svm.setKernel(kernel_map.get(self.kernel_type, cv2.ml.SVM_RBF))
        if self.kernel_type == "POLY":
            svm.setDegree(2.0)  # 限制多项式次数，默认值太大会卡死
        svm.setC(1.0)
        svm.train(train_data, cv2.ml.ROW_SAMPLE, labels)

        # 预测全图 → 分割掩膜
        _, result = svm.predict(features)
        mask = (result.reshape(h, w) > 0).astype(np.uint8) * 255
        out = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        return self.ok(out, f"SVM 像素分类完成 ({self.kernel_type})")

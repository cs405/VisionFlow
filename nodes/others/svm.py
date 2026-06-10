import cv2
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class SVM(OpenCVNodeDataBase):
    __group__ = "其他模块"
    svm_type = Property("C_SVC", name="SVM类型", group=PropertyGroupNames.RUN_PARAMETERS)
    kernel_type = Property("RBF", name="核函数", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "SVM分类器"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        svm = cv2.ml.SVM_create()
        type_map = {"C_SVC": cv2.ml.SVM_C_SVC, "NU_SVC": cv2.ml.SVM_NU_SVC, "ONE_CLASS": cv2.ml.SVM_ONE_CLASS}
        kernel_map = {"LINEAR": cv2.ml.SVM_LINEAR, "RBF": cv2.ml.SVM_RBF, "POLY": cv2.ml.SVM_POLY}
        svm.setType(type_map.get(self.svm_type, cv2.ml.SVM_C_SVC))
        svm.setKernel(kernel_map.get(self.kernel_type, cv2.ml.SVM_RBF))
        return self.ok(mat, "SVM分类器已配置")

    def _update_result_image_source(self):
        self._result_image_source = self._mat

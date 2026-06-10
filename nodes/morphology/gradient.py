import cv2
from nodes.morphology.morph_base import MorphBase

class Gradient(MorphBase):
    _morph_op = cv2.MORPH_GRADIENT
    def __init__(self): super().__init__(); self.name = "形态学梯度"

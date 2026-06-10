import cv2
from nodes.morphology.morph_base import MorphBase

class Close(MorphBase):
    _morph_op = cv2.MORPH_CLOSE
    def __init__(self): super().__init__(); self.name = "闭运算"

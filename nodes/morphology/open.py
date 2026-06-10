import cv2
from nodes.morphology.morph_base import MorphBase

class Open(MorphBase):
    _morph_op = cv2.MORPH_OPEN
    def __init__(self): super().__init__(); self.name = "开运算"

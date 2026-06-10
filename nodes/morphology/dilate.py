import cv2
from nodes.morphology.morph_base import MorphBase

class Dilate(MorphBase):
    _morph_op = cv2.MORPH_DILATE
    def __init__(self): super().__init__(); self.name = "膨胀"

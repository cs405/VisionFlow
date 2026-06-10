import cv2
from nodes.morphology.morph_base import MorphBase

class Erode(MorphBase):
    _morph_op = cv2.MORPH_ERODE
    def __init__(self): super().__init__(); self.name = "腐蚀"

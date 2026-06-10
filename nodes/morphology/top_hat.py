import cv2
from nodes.morphology.morph_base import MorphBase

class TopHat(MorphBase):
    _morph_op = cv2.MORPH_TOPHAT
    def __init__(self): super().__init__(); self.name = "顶帽"

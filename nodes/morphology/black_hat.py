import cv2
from nodes.morphology.morph_base import MorphBase

class BlackHat(MorphBase):
    _morph_op = cv2.MORPH_BLACKHAT
    def __init__(self): super().__init__(); self.name = "黑帽"

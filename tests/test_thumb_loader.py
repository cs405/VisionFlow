"""诊断 ThumbnailLoader 是否正常加载缩略图。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QScrollArea, QHBoxLayout, QFrame
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QFont, QColor

app = QApplication(sys.argv)

# ── 直接用最简方式测试 cv2 加载 ──
print("1. Testing cv2.imread...")
assets = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "images")
files = []
if os.path.isdir(assets):
    for f in sorted(os.listdir(assets)):
        if f.lower().endswith(('.png','.jpg','.jpeg','.bmp','.tiff','.tif','.webp')):
            files.append(os.path.join(assets, f))
print(f"   Found {len(files)} files")

import cv2
import numpy as np
test_file = files[0]
print(f"   Loading: {os.path.basename(test_file)}")
img = cv2.imread(test_file, cv2.IMREAD_COLOR)
print(f"   Shape: {img.shape if img is not None else 'FAILED (None)'}")

if img is not None:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    from PyQt5.QtGui import QImage
    qimg = QImage(rgb.data, w, h, w*3, QImage.Format_RGB888)
    pix = QPixmap.fromImage(qimg)
    print(f"   QPixmap: {pix.width()}x{pix.height()} isNull={pix.isNull()}")

# ── 测试 ThumbnailLoader 线程 ──
print("\n2. Testing ThumbnailLoader QThread...")
class MiniLoader(QThread):
    done = pyqtSignal(str, QPixmap)
    def __init__(self, paths):
        super().__init__()
        self.paths = paths
    def run(self):
        for p in self.paths[:3]:
            img = cv2.imread(p, cv2.IMREAD_COLOR)
            if img is not None:
                h, w = img.shape[:2]
                s = min(75/max(w,1), 75/max(h,1))
                if s < 1.0:
                    img = cv2.resize(img, (int(w*s), int(h*s)))
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w, c = rgb.shape
                qimg = QImage(rgb.data, w, h, w*c, QImage.Format_RGB888)
                self.done.emit(p, QPixmap.fromImage(qimg))

loader = MiniLoader(files)
results = {}
loader.done.connect(lambda p, pix: results.update({p: pix}))
loader.start()
loader.wait(3000)
print(f"   Loaded {len(results)} thumbnails")
for p, pix in list(results.items())[:3]:
    print(f"   {os.path.basename(p)}: {pix.width()}x{pix.height()} isNull={pix.isNull()}")

# ── UI 测试 ──
win = QMainWindow()
cw = QWidget()
layout = QVBoxLayout(cw)

# Scroll strip
scroll = QScrollArea()
scroll.setFixedHeight(75+14)
scroll.setWidgetResizable(True)
scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
container = QWidget()
hlay = QHBoxLayout(container)
hlay.setContentsMargins(36,4,36,4)
hlay.setSpacing(2)
hlay.setAlignment(Qt.AlignLeft)

class Tb(QPushButton):
    def __init__(self, path):
        super().__init__()
        self.pix = None
        self.setFixedSize(81,81)
        self.setToolTip(os.path.basename(path))
    def set_pix(self, p):
        self.pix = p
        self.update()
    def paintEvent(self, e):
        super().paintEvent(e)
        if self.pix:
            p = QPainter(self)
            pw, ph = self.pix.width(), self.pix.height()
            p.drawPixmap((81-pw)//2, (81-ph)//2, self.pix)
        else:
            p = QPainter(self)
            p.setPen(QColor("#555"))
            p.drawText(self.rect(), Qt.AlignCenter, "...")

btns = []
for f in files[:10]:
    b = Tb(f)
    b.setStyleSheet("background:#333; border:2px solid #555;")
    hlay.addWidget(b)
    btns.append((b, f))

# 加载图片
loader2 = MiniLoader(files[:10])
for b, f in btns:
    loader2.done.connect(lambda p, pix, b=b: b.set_pix(pix))
loader2.start()

count = len(btns)
total_w = count * (81+2) - 2 + 72
container.setMinimumSize(total_w, 0)
scroll.setWidget(container)
layout.addWidget(QLabel(f"10 thumbnails, container={total_w}px"))
layout.addWidget(scroll)

win.setCentralWidget(cw)
win.resize(800, 250)
win.show()

QTimer.singleShot(2000, lambda: print(f"\n3. Loaded: {sum(1 for b,f in btns if b.pix is not None)}/10"))
QTimer.singleShot(5000, app.quit)
app.exec_()

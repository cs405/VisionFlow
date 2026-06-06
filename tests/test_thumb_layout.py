"""纯布局诊断 — 绕过 OpenCV，仅测试 QScrollArea + 缩略图按钮布局。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QLabel, QFrame)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont

app = QApplication(sys.argv)

THUMB_SIZE = 75
PAGE_BTN_SIZE = 30
NUM_THUMBS = 20

# ── 方案1: 当前 VisionFlow 方式 (setWidgetResizable=False + adjustSize) ──
class Strip1(QWidget):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel(label))

        self.scroll = QScrollArea()
        self.scroll.setFixedHeight(THUMB_SIZE + 14)
        self.scroll.setWidgetResizable(False)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.thumb_layout = QHBoxLayout(self.container)
        self.thumb_layout.setContentsMargins(36, 4, 36, 4)
        self.thumb_layout.setSpacing(2)
        self.thumb_layout.setAlignment(Qt.AlignLeft)

        for i in range(NUM_THUMBS):
            btn = QPushButton(str(i + 1))
            btn.setFixedSize(THUMB_SIZE + 6, THUMB_SIZE + 6)
            btn.setStyleSheet("background: #333; border: 2px solid #555; color: white;")
            self.thumb_layout.addWidget(btn)

        self.scroll.setWidget(self.container)
        self.container.adjustSize()
        lay.addWidget(self.scroll)

        self.info = QLabel("")
        lay.addWidget(self.info)

    def diagnose(self):
        c = self.container
        s = self.scroll
        chars = []
        chars.append(f"container: {c.width()}x{c.height()} (sizeHint={c.sizeHint().width()})")
        chars.append(f"scroll.viewport: {s.viewport().size().width()}x{s.viewport().size().height()}")
        chars.append(f"layout count: {self.thumb_layout.count()}")
        chars.append(f"hbar visible={s.horizontalScrollBar().isVisible()} range={s.horizontalScrollBar().maximum()}")
        # 检查 stretch
        for i in range(self.thumb_layout.count()):
            item = self.thumb_layout.itemAt(i)
            if item and item.spacerItem():
                chars.append(f"  ⚠️ layout[{i}]: SPACER found!")
                break
        else:
            chars.append(f"  ✓ no spacer in layout")
        # 检查前3个 visible
        for i in range(min(3, self.thumb_layout.count())):
            item = self.thumb_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                chars.append(f"  btn[{i}]: pos=({w.x()},{w.y()}) visible={w.isVisible()}")
        self.info.setText(" | ".join(chars))


# ── 方案2: setWidgetResizable=True + container minimumWidth ──
class Strip2(QWidget):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(label))

        self.scroll = QScrollArea()
        self.scroll.setFixedHeight(THUMB_SIZE + 14)
        self.scroll.setWidgetResizable(True)  # ← 关键区别
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.thumb_layout = QHBoxLayout(self.container)
        self.thumb_layout.setContentsMargins(36, 4, 36, 4)
        self.thumb_layout.setSpacing(2)
        self.thumb_layout.setAlignment(Qt.AlignLeft)

        for i in range(NUM_THUMBS):
            btn = QPushButton(str(i + 1))
            btn.setFixedSize(THUMB_SIZE + 6, THUMB_SIZE + 6)
            btn.setStyleSheet("background: #444; border: 2px solid #666; color: white;")
            self.thumb_layout.addWidget(btn)

        self.scroll.setWidget(self.container)
        # 关键: 设置最小宽度让 container 展开
        self.container.setMinimumWidth(self.container.sizeHint().width())
        lay.addWidget(self.scroll)

        self.info = QLabel("")
        lay.addWidget(self.info)

    def diagnose(self):
        c = self.container
        s = self.scroll
        chars = []
        chars.append(f"container: {c.width()}x{c.height()} (sizeHint={c.sizeHint().width()})")
        chars.append(f"scroll.viewport: {s.viewport().size().width()}x{s.viewport().size().height()}")
        chars.append(f"hbar visible={s.horizontalScrollBar().isVisible()} range={s.horizontalScrollBar().maximum()}")
        self.info.setText(" | ".join(chars))


# ── 窗口 ──
win = QMainWindow()
win.setWindowTitle("缩略图布局对比诊断")
cw = QWidget()
layout = QVBoxLayout(cw)
layout.setSpacing(10)

strip1 = Strip1("方案A: setWidgetResizable(False) + adjustSize()")
layout.addWidget(strip1)

strip2 = Strip2("方案B: setWidgetResizable(True) + setMinimumWidth(sizeHint)")
layout.addWidget(strip2)

win.setCentralWidget(cw)
win.resize(1100, 450)
win.show()

def post_show():
    print("=== 显示后诊断 ===")
    strip1.diagnose()
    print(f"方案A: {strip1.info.text()}")
    strip2.diagnose()
    print(f"方案B: {strip2.info.text()}")

    # 结论
    print("\n如果方案A的hbar range=0 → adjustSize没生效 → container卡在viewport宽度")
    print("如果方案B的hbar range>0 → setMinimumWidth有效 → 用这个方案修复")

QTimer.singleShot(300, post_show)
QTimer.singleShot(3000, app.quit)
app.exec_()

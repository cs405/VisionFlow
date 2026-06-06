"""诊断缩略图不显示 — 模拟 set_node 完整流程。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QScrollArea, QPushButton, QLabel, QFrame)
from PyQt5.QtCore import Qt, QTimer

app = QApplication(sys.argv)

# 复制 FlowResourcePanel 的关键常量
THUMB_SIZE = 75
PAGE_BTN_SIZE = 40

# 模拟 SrcFilesVisionNodeData
class MockNode:
    def __init__(self):
        assets = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "images")
        self.src_file_paths = []
        if os.path.isdir(assets):
            for f in sorted(os.listdir(assets)):
                if f.lower().endswith(('.png','.jpg','.jpeg','.bmp','.tiff','.tif','.webp')):
                    self.src_file_paths.append(os.path.join(assets, f))
        self.src_file_path = self.src_file_paths[0] if self.src_file_paths else ""
        self.use_all_image = False
        self.use_auto_switch = True

node = MockNode()
print(f"1. Node files: {len(node.src_file_paths)}")
for p in node.src_file_paths[:3]:
    print(f"   {p}")

# ── 复制 FlowResourcePanel 的核心逻辑 ──
win = QMainWindow()
cw = QWidget()
layout = QVBoxLayout(cw)

# scroll area 设置（和 flow_resource_panel 一样）
scroll = QScrollArea()
scroll.setFixedHeight(THUMB_SIZE + 14)
scroll.setWidgetResizable(True)
scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
scroll.setFrameShape(QFrame.NoFrame)
scroll.setFocusPolicy(Qt.NoFocus)

# container
container = QWidget()
thumb_layout = QHBoxLayout(container)
thumb_layout.setContentsMargins(36, 4, 36, 4)
thumb_layout.setSpacing(2)
thumb_layout.setAlignment(Qt.AlignLeft)

scroll.setWidget(container)
layout.addWidget(QLabel(f"Files: {len(node.src_file_paths)} | Container sizing test"))
layout.addWidget(scroll)

# ── 模拟 _build_thumbnails ──
from gui.flow_resource_panel import ThumbnailButton

count = len(node.src_file_paths)
for path in node.src_file_paths:
    btn = ThumbnailButton(path)
    thumb_layout.addWidget(btn)

# 模拟 _update_container_size
btn_w = THUMB_SIZE + 6
spacing = thumb_layout.spacing()
margins = thumb_layout.contentsMargins()
total_w = count * (btn_w + spacing) - spacing + margins.left() + margins.right()
container.setMinimumSize(total_w, 0)

print(f"\n2. Container sizing:")
print(f"   count={count} btn_w={btn_w} spacing={spacing} margins=({margins.left()},{margins.right()})")
print(f"   total_w={total_w}")
print(f"   container.minimumSize={container.minimumWidth()}x{container.minimumHeight()}")
print(f"   container.sizeHint={container.sizeHint().width()}x{container.sizeHint().height()}")

# Add deferred re-size (same as fix)
def deferred_size():
    cw = count
    w = cw * (btn_w + spacing) - spacing + margins.left() + margins.right()
    container.setMinimumSize(w, 0)
    print(f"\n3. Deferred re-size:")
    print(f"   container.minimumSize={container.minimumWidth()}x{container.minimumHeight()}")
    print(f"   container.width={container.width()}")
    print(f"   scroll.viewport.width={scroll.viewport().width()}")
    print(f"   hbar max={scroll.horizontalScrollBar().maximum()}")
    print(f"   Thumbnails visible: {container.width() > scroll.viewport().width()}")

QTimer.singleShot(0, deferred_size)

win.setCentralWidget(cw)
win.resize(1000, 300)
win.show()

# After show, check actual container width vs viewport
def after_show():
    print(f"\n4. After show:")
    print(f"   container.width={container.width()}")
    print(f"   viewport.width={scroll.viewport().width()}")
    print(f"   hbar max={scroll.horizontalScrollBar().maximum()}")
    print(f"   Thumbnails should be scrollable: {scroll.horizontalScrollBar().maximum() > 0}")

QTimer.singleShot(500, after_show)
QTimer.singleShot(7000, app.quit)
app.exec_()

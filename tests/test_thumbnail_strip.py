"""诊断缩略图不显示问题 — 逐步排查布局/尺寸/滚动。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QLabel)
from PyQt5.QtCore import Qt, QSize

# ── 模拟 FlowResourcePanel 核心布局 ──
THUMB_SIZE = 75
PAGE_BTN_SIZE = 30

app = QApplication(sys.argv)

win = QMainWindow()
win.setWindowTitle("缩略图诊断")
central = QWidget()
win.setCentralWidget(central)
layout = QVBoxLayout(central)

# 复制 FlowResourcePanel 的滚动区域设置
scroll = QScrollArea()
scroll.setFixedHeight(THUMB_SIZE + 14)
scroll.setWidgetResizable(False)
scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
scroll.setFrameShape(scroll.NoFrame)

container = QWidget()
thumb_layout = QHBoxLayout(container)
thumb_layout.setContentsMargins(36, 4, 36, 4)
thumb_layout.setSpacing(2)
thumb_layout.setAlignment(Qt.AlignLeft)

# 添加测试缩略图
for i in range(10):
    btn = QPushButton(f"{i+1}")
    btn.setFixedSize(THUMB_SIZE + 6, THUMB_SIZE + 6)
    btn.setStyleSheet("background: #333; border: 2px solid #555; color: white;")
    thumb_layout.addWidget(btn)

scroll.setWidget(container)

# ── 关键诊断 ──
print("=" * 60)
print("1. 布局状态")
print(f"   thumb_layout.count()        = {thumb_layout.count()}")
print(f"   thumb_layout.sizeHint()     = {thumb_layout.sizeHint().width()}x{thumb_layout.sizeHint().height()}")
print(f"   container.sizeHint()        = {container.sizeHint().width()}x{container.sizeHint().height()}")
print(f"   container.size() BEFORE adjustSize  = {container.width()}x{container.height()}")
print(f"   container.minimumSizeHint() = {container.minimumSizeHint().width()}x{container.minimumSizeHint().height()}")
print(f"   scroll.viewport().size()    = {scroll.viewport().size().width()}x{scroll.viewport().size().height()}")

# 测试 adjustSize()
container.adjustSize()
print(f"\n2. AFTER adjustSize():")
print(f"   container.size()            = {container.width()}x{container.height()}")
print(f"   container.sizeHint()        = {container.sizeHint().width()}x{container.sizeHint().height()}")

# 测试手动设置宽度
expected_width = 10 * (THUMB_SIZE + 6 + 2) + 36 + 36
print(f"\n3. Expected vs Actual:")
print(f"   Expected container width (10 btns) = {expected_width}")
print(f"   Actual container width             = {container.width()}")
print(f"   Match: {container.width() >= expected_width - 20}")

# 测试 setWidgetResizable 的影响
print(f"\n4. QScrollArea 配置:")
print(f"   widgetResizable = {scroll.widgetResizable()}")
print(f"   scroll widget() = {scroll.widget()}")
print(f"   scroll widget().size() = {scroll.widget().width()}x{scroll.widget().height()}")

# 测试：强制设置 container 的宽度
container.setFixedWidth(expected_width)
print(f"\n5. After setFixedWidth({expected_width}):")
print(f"   container.size() = {container.width()}x{container.height()}")
print(f"   container.sizeHint() = {container.sizeHint().width()}x{container.sizeHint().height()}")

# 测试：每个子 widget 的大小
print(f"\n6. Child widget sizes:")
for i in range(thumb_layout.count()):
    item = thumb_layout.itemAt(i)
    if item and item.widget():
        w = item.widget()
        print(f"   [{i}] {w.text() if hasattr(w,'text') else '?'}: "
              f"pos=({w.x()},{w.y()}) size={w.width()}x{w.height()} visible={w.isVisible()}")

# 测试：不使用 setWidgetResizable(False)
scroll2 = QScrollArea()
scroll2.setFixedHeight(THUMB_SIZE + 14)
scroll2.setWidgetResizable(True)  # ← 关键区别
scroll2.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
container2 = QWidget()
layout2 = QHBoxLayout(container2)
layout2.setContentsMargins(36, 4, 36, 4)
layout2.setSpacing(2)
layout2.setAlignment(Qt.AlignLeft)
for i in range(10):
    btn2 = QPushButton(f"V{i+1}")
    btn2.setFixedSize(THUMB_SIZE + 6, THUMB_SIZE + 6)
    btn2.setStyleSheet("background: #333; border: 2px solid #555; color: white;")
    layout2.addWidget(btn2)
scroll2.setWidget(container2)

print(f"\n7. setWidgetResizable(True) 对比:")
print(f"   container2.size() = {container2.width()}x{container2.height()}")
print(f"   container2.sizeHint() = {container2.sizeHint().width()}x{container2.sizeHint().height()}")
print(f"   This approach: scrollbar should NOT appear (container fills viewport)")

# 添加两个滚动区域到窗口
label1 = QLabel("=== 方案A: setWidgetResizable(False) + adjustSize() ===")
layout.addWidget(label1)
layout.addWidget(scroll)

label2 = QLabel("=== 方案B: setWidgetResizable(True) + container min width ===")
layout.addWidget(label2)
layout.addWidget(scroll2)

label3 = QLabel("=== 方案C: setWidgetResizable(False) + setFixedWidth ===")
layout.addWidget(label3)
scroll3 = QScrollArea()
scroll3.setFixedHeight(THUMB_SIZE + 14)
scroll3.setWidgetResizable(False)
scroll3.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
container3 = QWidget()
layout3 = QHBoxLayout(container3)
layout3.setContentsMargins(36, 4, 36, 4)
layout3.setSpacing(2)
layout3.setAlignment(Qt.AlignLeft)
for i in range(10):
    btn3 = QPushButton(f"F{i+1}")
    btn3.setFixedSize(THUMB_SIZE + 6, THUMB_SIZE + 6)
    btn3.setStyleSheet("background: #333; border: 2px solid #555; color: white;")
    layout3.addWidget(btn3)
container3.setFixedWidth(expected_width)
scroll3.setWidget(container3)
layout.addWidget(scroll3)

# 结论
print(f"\n8. 推荐方案:")
print(f"   方案A (当前): adjustSize() 后 container.width={container.width()}")
print(f"     → 如果 < {expected_width}，说明 adjustSize 未生效 → 需要用 setFixedWidth")
print(f"   方案C: setFixedWidth 强制设置宽度 — 最可靠")
print(f"   方案B: setWidgetResizable(True) — 无滚动条，不适合缩略图")

win.resize(800, 500)
print("\n启动窗口... 检查3个滚动区域哪个能正常显示10个缩略图")
win.show()
app.exec_()

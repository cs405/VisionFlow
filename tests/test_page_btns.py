"""诊断 PageLeft/PageRight - 简洁版，避免 GBK 编码问题。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QScrollArea, QPushButton, QLabel)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QFontDatabase

app = QApplication(sys.argv)

from gui.font_icons import ICON_FONT_FAMILY, icon_font, FontIcons

print("ICON_FONT_FAMILY:", ICON_FONT_FAMILY)
print("PageLeft  codepoint: U+E760")
print("PageRight codepoint: U+E761")

# Test: icon_font() renders PageLeft/PageRight correctly?
f = icon_font(16)
print("icon_font family:", f.family())

# Verify the glyph actually exists
if f.family() == "Segoe Fluent Icons":
    # Segoe Fluent Icons may NOT have U+E760/U+E761 - these are MDL2 codepoints
    print("WARNING: Segoe Fluent Icons may lack PageLeft/PageRight!")
    print("Try Segoe MDL2 Assets instead")

# Check MDL2 availability
mdl2 = QFont("Segoe MDL2 Assets")
print("MDL2 exactMatch:", mdl2.exactMatch())

# ── UI test with both fonts ──
win = QMainWindow()
win.setWindowTitle("PageLeft/PageRight Font Test")
cw = QWidget()
layout = QVBoxLayout(cw)

layout.addWidget(QLabel("icon_font(16) -> " + icon_font(16).family()))
row1 = QHBoxLayout()
b1 = QPushButton(FontIcons.PageLeft)
b1.setFont(icon_font(16))
b1.setFixedSize(50, 50)
b1.setStyleSheet("background: #333; border: 1px solid red; color: white; font-size: 20px;")
row1.addWidget(b1)
b2 = QPushButton(FontIcons.PageRight)
b2.setFont(icon_font(16))
b2.setFixedSize(50, 50)
b2.setStyleSheet("background: #333; border: 1px solid red; color: white; font-size: 20px;")
row1.addWidget(b2)
layout.addLayout(row1)

layout.addWidget(QLabel("Segoe MDL2 Assets QFont 16px"))
row2 = QHBoxLayout()
b3 = QPushButton(FontIcons.PageLeft)
b3.setFont(QFont("Segoe MDL2 Assets", 16))
b3.setFixedSize(50, 50)
b3.setStyleSheet("background: #333; border: 1px solid green; color: white; font-size: 20px;")
row2.addWidget(b3)
b4 = QPushButton(FontIcons.PageRight)
b4.setFont(QFont("Segoe MDL2 Assets", 16))
b4.setFixedSize(50, 50)
b4.setStyleSheet("background: #333; border: 1px solid green; color: white; font-size: 20px;")
row2.addWidget(b4)
layout.addLayout(row2)

# ── Position test with scroll area ──
layout.addWidget(QLabel("Position test: red border = left-edge, green = right-edge"))
scroll = QScrollArea()
scroll.setFixedHeight(75 + 14)
scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
scroll.setWidgetResizable(True)
container = QWidget()
hlay = QHBoxLayout(container)
hlay.setContentsMargins(42, 4, 42, 4)
hlay.setAlignment(Qt.AlignLeft)
for i in range(8):
    b = QPushButton(str(i+1))
    b.setFixedSize(81, 81)
    b.setStyleSheet("background: #252525; border: 1px solid #555; color: #aaa;")
    hlay.addWidget(b)
scroll.setWidget(container)

pg_size = 34
left_btn = QPushButton(FontIcons.PageLeft)
left_btn.setFont(icon_font(16))
left_btn.setFixedSize(pg_size, pg_size)
left_btn.setCursor(Qt.PointingHandCursor)
left_btn.setParent(scroll)
left_btn.setStyleSheet("background: rgba(45,45,48,0.9); border: 1px solid red; color: white;")
left_btn.show()

right_btn = QPushButton(FontIcons.PageRight)
right_btn.setFont(icon_font(16))
right_btn.setFixedSize(pg_size, pg_size)
right_btn.setCursor(Qt.PointingHandCursor)
right_btn.setParent(scroll)
right_btn.setStyleSheet("background: rgba(45,45,48,0.9); border: 1px solid green; color: white;")
right_btn.show()

layout.addWidget(scroll)
win.setCentralWidget(cw)
win.resize(900, 450)
win.show()

def after_show():
    sw = scroll.width()
    sh = scroll.height()
    left_btn.move(2, (sh - pg_size) // 2)
    right_btn.move(sw - pg_size - 2, (sh - pg_size) // 2)
    print("scroll size:", sw, "x", sh)
    print("left  pos:", left_btn.x(), left_btn.y(), "right pos:", right_btn.x(), right_btn.y())
    print("right at edge:", abs(right_btn.x() + pg_size + 2 - sw) <= 2)
    print()
    print("If red/green bordered buttons show BLANK:")
    print("  -> icon_font() picked Segoe Fluent Icons which lacks PageLeft/PageRight")
    print("  -> Fix: use FontIcons with Segoe MDL2 Assets directly or remap codepoints")
    print("If green border NOT at right edge:")
    print("  -> right_btn.move() didn't use correct scroll width")

QTimer.singleShot(300, after_show)
QTimer.singleShot(5000, app.quit)
app.exec_()

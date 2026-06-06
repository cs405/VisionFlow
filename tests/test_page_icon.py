"""精确复现 FlowResourcePanel 按钮环境 — 不导入 theme"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont, QFontDatabase

app = QApplication(sys.argv)

# 手动检测（不导入 font_icons 避免 theme 初始化冲突）
db = QFontDatabase()
ICON_FAMILY = "Segoe MDL2 Assets"
# 确认存在
f = QFont(ICON_FAMILY)
if not f.exactMatch():
    for name in ["Segoe Fluent Icons", "Segoe UI Symbol"]:
        if QFont(name).exactMatch():
            ICON_FAMILY = name
            break
print(f"Font: {ICON_FAMILY}")

PAGE_LEFT = ""
PAGE_RIGHT = ""
print(f"PageLeft: U+{ord(PAGE_LEFT):04X}  PageRight: U+{ord(PAGE_RIGHT):04X}")

win = QMainWindow()
cw = QWidget()
layout = QVBoxLayout(cw)

def add_test(label, btn):
    layout.addWidget(QLabel(label))
    layout.addWidget(btn)

# A: 只有 QSS（无 setFont）
a = QPushButton(PAGE_LEFT)
a.setFixedSize(50, 50)
a.setStyleSheet("background:#333; border:1px solid red; color:white; font-size:16px;")
add_test("A: QSS no font-family", a)

# B: QSS 含 font-family（当前 fix）
b = QPushButton(PAGE_LEFT)
b.setFixedSize(50, 50)
b.setStyleSheet(f'background:#333; border:1px solid green; color:white; font-family:"{ICON_FAMILY}"; font-size:16px;')
add_test("B: QSS with font-family", b)

# C: setFont 无 QSS
c = QPushButton(PAGE_LEFT)
c.setFont(QFont(ICON_FAMILY, 16))
c.setFixedSize(50, 50)
add_test("C: setFont no QSS", c)

# D: setFont + 简单 QSS（无 font-family）
d = QPushButton(PAGE_LEFT)
d.setFont(QFont(ICON_FAMILY, 16))
d.setFixedSize(50, 50)
d.setStyleSheet("background:#333; border:1px solid blue; color:white;")
add_test("D: setFont + QSS(no-font)", d)  # 旧 FlowResourcePanel 方式

# E: 左右箭头同排
row = QWidget()
rlay = QVBoxLayout(row)
for char, name in [(PAGE_LEFT,"PageLeft"),(PAGE_RIGHT,"PageRight"),
                    ("","ChevronLeft"),("","ChevronRight"),
                    ("","Play"),("","Pause")]:
    b = QPushButton(char)
    b.setFixedSize(44,44)
    b.setStyleSheet(f'font-family:"{ICON_FAMILY}"; font-size:16px; color:white; background:#222; border:1px solid #555;')
    b.setToolTip(f"{name} U+{ord(char):04X}")
    rlay.addWidget(b)
add_test("E: MDL2 icon test (all should render)", row)

# F: Fluent Icons 字体对比
if QFont("Segoe Fluent Icons").exactMatch():
    row2 = QWidget()
    r2lay = QVBoxLayout(row2)
    for char, name in [(PAGE_LEFT,"PageLeft"),(PAGE_RIGHT,"PageRight"),
                        ("","ChevLeft"),("","ChevRight")]:
        b = QPushButton(char)
        b.setFixedSize(44,44)
        b.setStyleSheet('font-family:"Segoe Fluent Icons"; font-size:16px; color:white; background:#222; border:1px solid #555;')
        b.setToolTip(name)
        r2lay.addWidget(b)
    add_test("F: Fluent Icons (may be blank)", row2)

win.setCentralWidget(cw)
win.resize(500, 750)
win.show()
QTimer.singleShot(7000, app.quit)
app.exec_()

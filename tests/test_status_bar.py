"""诊断 QStatusBar 蓝色边框问题 — 打印实际样式 & 主题值。"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt5.QtWidgets import QApplication, QLabel
from PyQt5.QtCore import Qt

# 1. 检查主题 accent 色
from gui.theme import theme_manager
accent = theme_manager.color("accent")
print(f"1. 主题 accent color: {accent.name()} (theme={theme_manager.current_theme_id})")
print(f"   _active_colors['accent']: {theme_manager._active_colors.get('accent', 'MISSING')}")

# 2. 检查 QStatusBar 样式
app = QApplication(sys.argv)
from gui.main_window import MainWindow
win = MainWindow()

sb = win.statusBar()
actual_qss = sb.styleSheet()
print(f"\n2. QStatusBar 实际样式:\n---\n{actual_qss}\n---")

# 3. 检查子控件样式
for child in sb.findChildren(QLabel):
    print(f"3. QLabel '{child.text()}': styleSheet='{child.styleSheet()}'")

# 4. 检查 palette
pal = sb.palette()
print(f"\n4. QStatusBar palette:")
print(f"   Window:        {pal.color(pal.Window).name()}")
print(f"   WindowText:    {pal.color(pal.WindowText).name()}")
print(f"   Base:          {pal.color(pal.Base).name()}")
print(f"   Highlight:     {pal.color(pal.Highlight).name()}")

# 5. 检查 _hsep() 的样式
print(f"\n5. _hsep separator styleSheet:")
from gui.main_window import _Sep
sep = _Sep()
print(f"   {sep.styleSheet()}")

# 6. 模拟主题切换看看
print(f"\n6. 模拟主题切换...")
if theme_manager.current_theme_id == "dark":
    theme_manager.set_theme("light")
    print(f"   切换到 light → accent={theme_manager.color('accent').name()}")
    theme_manager.set_theme("dark")
    print(f"   切换回 dark → accent={theme_manager.color('accent').name()}")
else:
    theme_manager.set_theme("dark")
    print(f"   切换到 dark → accent={theme_manager.color('accent').name()}")

# 7. 再次检查 QStatusBar 样式 (切换后 connect_theme 应该生效)
actual_qss2 = sb.styleSheet()
print(f"\n7. 主题切换后 QStatusBar 样式:\n---\n{actual_qss2}\n---")
if "#007acc" in actual_qss2:
    print("   ❌ 仍然包含硬编码 #007acc！")
else:
    print("   ✓ 不再包含 #007acc")

print("\n=== 诊断完成 ===")
print("如果你的 statusBar 仍然是蓝色的，可能是以下原因：")
print("  (a) 样式被其他地方重新设置过覆盖了")
print("  (b) palette 或 native style 强制绘制了蓝色")
print("  (c) 有 widget 盖在 statusBar 上方并设置了蓝色背景")

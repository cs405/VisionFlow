"""Test script: isolate crash when opening theme dialog + applying theme."""
import sys
import traceback
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton,
                               QVBoxLayout, QWidget, QLabel, QSplitter,
                               QTabWidget, QTreeWidget, QTreeWidgetItem,
                               QTextEdit, QMenuBar, QAction)
from PyQt5.QtCore import Qt, QTimer

app = QApplication(sys.argv)
print("1. App created", flush=True)

# Build a complex-ish main window to approximate the real app
w = QMainWindow()
w.setWindowTitle('Theme Dialog Test - Complex Window')
w.resize(800, 500)

# Menu bar
mb = w.menuBar()
file_menu = mb.addMenu("文件")
file_menu.addAction("新建")
file_menu.addAction("打开")

# Central with tabs + splitter
central = QSplitter(Qt.Horizontal)

left = QTreeWidget()
left.setHeaderLabel("工具箱")
for i in range(10):
    item = QTreeWidgetItem([f"节点类型 {i}"])
    left.addTopLevelItem(item)
    item.addChild(QTreeWidgetItem(["子节点"]))
central.addWidget(left)

right = QSplitter(Qt.Vertical)
tab = QTabWidget()
tab.addTab(QTextEdit(), "流程图")
tab.addTab(QTextEdit(), "结果")
right.addWidget(tab)
right.addWidget(QTextEdit("日志输出..."))
central.addWidget(right)

central.setSizes([200, 600])
w.setCentralWidget(central)

# Toolbar
toolbar = w.addToolBar("测试")
btn_open = QAction("打开颜色主题", w)
toolbar.addAction(btn_open)
btn_toggle = QAction("切换深色/浅色", w)
toolbar.addAction(btn_toggle)

# Status bar
status = w.statusBar()
status.showMessage("就绪")

print("2. Window built - widgets:", len(w.findChildren(QWidget)), flush=True)


def on_open():
    print("\n3. === Opening theme dialog ===", flush=True)
    try:
        from gui.theme import theme_manager, ThemePickerDialog
        print(f"   current theme: {theme_manager.current_theme_id}", flush=True)

        dlg = ThemePickerDialog(w)
        print(f"   dialog created: {dlg.windowTitle()}", flush=True)

        result = dlg.exec_()
        print(f"   dialog closed, result={result}, theme={theme_manager.current_theme_id}", flush=True)

        if result:
            print("4. === Calling _apply_theme ===", flush=True)
            _apply_theme(w)
            print("5. === _apply_theme done ===", flush=True)

        status.showMessage(f"主题: {theme_manager.current_theme_name}")

    except Exception as e:
        traceback.print_exc()
        print(f"ERROR: {e}", flush=True)


def on_toggle():
    from gui.theme import theme_manager
    theme_manager.toggle()
    print(f"Toggled: {theme_manager.current_theme_id}", flush=True)
    _apply_theme(w)
    status.showMessage(f"主题: {theme_manager.current_theme_name}")


def _apply_theme(win):
    """Same as main_window._apply_theme."""
    from gui.theme import theme_manager
    win.setPalette(theme_manager.colors.to_palette())
    win.setStyleSheet(theme_manager.get_stylesheet())
    for child in win.findChildren(QWidget):
        try:
            child.style().unpolish(child)
            child.style().polish(child)
            child.update()
        except Exception:
            pass  # Some widgets may fail polish


btn_open.triggered.connect(on_open)
btn_toggle.triggered.connect(on_toggle)

print("3. Show window...", flush=True)
w.show()

QTimer.singleShot(20000, lambda: (print("Timeout", flush=True), app.quit()))

sys.exit(app.exec_())

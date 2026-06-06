"""诊断 FlowResourcePanel 缩略图 — 模拟节点数据。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PyQt5.QtCore import QTimer, Qt, QSize
from gui.flow_resource_panel import FlowResourcePanel, ThumbnailButton

app = QApplication(sys.argv)

# 用 assets/images 文件夹测试
test_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "images")
print(f"测试目录: {test_dir}")
print(f"目录存在: {os.path.isdir(test_dir)}")

# 收集图片
images = []
for root, dirs, files in os.walk(test_dir):
    for f in sorted(files):
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp')):
            images.append(os.path.join(root, f))
print(f"图片数量: {len(images)}")

# 创建模拟 node (不调用 OpenCV)
class MockNode:
    def __init__(self):
        self.name = "mock_source"
        self.src_file_paths = images
        self.src_file_path = images[0] if images else ""
        self.use_all_image = False
        self.use_auto_switch = True

    def add_files(self, paths):
        self.src_file_paths.extend(paths)

    def add_files_from_folder(self, path, recursive=True):
        pass

    def clear_files(self):
        self.src_file_paths.clear()
        self.src_file_path = ""

    def delete_current_file(self):
        if self.src_file_path in self.src_file_paths:
            idx = self.src_file_paths.index(self.src_file_path)
            self.src_file_paths.remove(self.src_file_path)
            if self.src_file_paths:
                self.src_file_path = self.src_file_paths[min(idx, len(self.src_file_paths)-1)]
            else:
                self.src_file_path = ""

node = MockNode()

# 创建 panel 并注入数据
panel = FlowResourcePanel()
panel.set_node(node)

print(f"\n=== 缩略图 Layout 诊断（显示前） ===")
print(f"_thumb_layout.count() = {panel._thumb_layout.count()}")
print(f"_thumbnails len = {len(panel._thumbnails)}")
print(f"_thumb_container.size() = {panel._thumb_container.width()}x{panel._thumb_container.height()}")
print(f"_scroll_area.viewport().size() = {panel._scroll_area.viewport().size().width()}x{panel._scroll_area.viewport().size().height()}")

# 检查前5个
for i, key in enumerate(list(panel._thumbnails.keys())[:5]):
    btn = panel._thumbnails[key]
    print(f"[{i}] {os.path.basename(key)[:25]}: pos=({btn.x()},{btn.y()}) size={btn.width()}x{btn.height()}")

# 显示窗口
win = QMainWindow()
win.setWindowTitle("FlowResourcePanel 诊断 - 模拟节点")
cw = QWidget()
layout = QVBoxLayout(cw)
info = QLabel(f"图片: {len(images)}, 缩略图: {len(panel._thumbnails)}, "
              f"container: {panel._thumb_container.width()}x{panel._thumb_container.height()}")
layout.addWidget(info)
layout.addWidget(panel)
win.setCentralWidget(cw)
win.resize(1200, 300)
win.show()

def diagnose():
    print(f"\n=== 窗口显示后诊断 ===")
    c = panel._thumb_container
    s = panel._scroll_area
    print(f"panel height = {panel.height()}")
    print(f"_scroll_area.size() = {s.width()}x{s.height()}")
    print(f"_scroll_area.viewport().size() = {s.viewport().size().width()}x{s.viewport().size().height()}")
    print(f"_thumb_container.size() = {c.width()}x{c.height()}")
    print(f"_thumb_container.pos() = ({c.x()},{c.y()})")
    print(f"container visible rect (in viewport): {s.viewport().visibleRegion().boundingRect()}")
    for i, key in enumerate(list(panel._thumbnails.keys())[:5]):
        btn = panel._thumbnails[key]
        print(f"[{i}] {os.path.basename(key)[:20]}: visible={btn.isVisible()} "
              f"parent_visible={btn.parent().isVisible() if btn.parent() else 'N/A'} "
              f"pos=({btn.x()},{btn.y()}) size={btn.width()}x{btn.height()}")
    # 滚动条状态
    hbar = s.horizontalScrollBar()
    print(f"hbar visible={hbar.isVisible()} range={hbar.minimum()}..{hbar.maximum()} value={hbar.value()}")
    print(f"hbar pageStep={hbar.pageStep()} singleStep={hbar.singleStep()}")

    # 检查 stretch 是否存在
    for i in range(panel._thumb_layout.count()):
        item = panel._thumb_layout.itemAt(i)
        if item:
            if item.widget():
                w = item.widget()
                print(f"  layout[{i}]: widget type={type(w).__name__}")
            elif item.spacerItem():
                print(f"  layout[{i}]: SPACER (stretch!)")
            else:
                print(f"  layout[{i}]: unknown item type={type(item)}")
        else:
            print(f"  layout[{i}]: None")

QTimer.singleShot(500, diagnose)
QTimer.singleShot(3000, app.quit)
app.exec_()

"""
VisionFlow 主入口 — WPF VisionMaster风格视觉流程设计器
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from core.registry import NodeRegistry
from core.events import EventBus
from gui.main_window import MainWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("VisionFlow")
    app.setOrganizationName("VisionFlow")

    # 初始化核心组件
    event_bus = EventBus()
    event_bus.emit_log("INFO", "VisionFlow 启动中...")

    # 自动发现并注册所有节点
    NodeRegistry.discover_nodes("nodes")
    NodeRegistry.discover_plugins("plugins")

    # 打印注册信息
    print("\n" + "=" * 50)
    print("  VisionFlow - 智能视觉流程设计器")
    print("=" * 50)
    categories = NodeRegistry.get_categories()
    total = 0
    for category, nodes in sorted(categories.items()):
        print(f"  [{category}] {', '.join(sorted(nodes))}")
        total += len(nodes)
    print(f"  共 {total} 个节点已注册")
    print("=" * 50 + "\n")

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

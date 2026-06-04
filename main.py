"""
主入口 - VisionFlow 视觉流程设计器
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from core.registry import NodeRegistry
from core.events import EventBus
from gui.main_window import MainWindow


def main():
    """主函数"""
    # 启用高DPI支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("VisionFlow")
    app.setOrganizationName("VisionFlow")

    # 先创建事件总线实例（确保单例存在）
    event_bus = EventBus()

    # 自动发现所有节点（现在可以安全地发送日志了）
    NodeRegistry.discover_nodes("nodes")
    NodeRegistry.discover_plugins("plugins")

    # 打印已注册的节点（调试用）
    print("\n" + "="*50)
    print("已注册的节点:")
    print("="*50)
    for category, nodes in NodeRegistry.get_categories().items():
        print(f"  [{category}] {', '.join(nodes)}")
    print("="*50 + "\n")

    # 创建主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
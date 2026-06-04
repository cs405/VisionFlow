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
from gui.main_window import MainWindow


def main():
    """主函数"""
    # 启用高DPI支持 - 使用新API避免弃用警告
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    # 注释掉已弃用的API
    # QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

    app = QApplication(sys.argv)
    app.setApplicationName("VisionFlow")
    app.setOrganizationName("VisionFlow")

    # 自动发现所有节点
    NodeRegistry.discover_nodes("nodes")

    # 打印已注册的节点（调试用）
    print("已注册的节点:")
    for category, nodes in NodeRegistry.get_categories().items():
        print(f"  [{category}] {', '.join(nodes)}")

    # 创建主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
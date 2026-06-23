import os
import sys
import importlib
import inspect


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.app_context import AppContext, set_app_context
_ctx = AppContext()
_ctx.init_defaults()
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QApplication

from core.commands import set_point_converter
from core.node_base import NodeBase
from core.crash_handler import install as install_crash_handlers
from gui.main_window import MainWindow
from gui.theme import theme_manager



def bootstrap_app_context():
    """返回已初始化的上下文。"""
    discover_nodes(_ctx)
    set_app_context(_ctx)
    return _ctx

def discover_nodes(ctx):
    """显式发现并注册所有节点类型。

    参数：
        ctx: 应用上下文对象
    """
    # 标准节点包列表（包名, 分组名）
    packages = [
        ("nodes.sources", "图像数据源"),  # 图像源节点
        ("nodes.preprocessings", "图像预处理模块"),  # 预处理节点
        ("nodes.blurs", "滤波模块"),  # 滤波节点
        ("nodes.takeoffs", "图像分割提取模块"),  # 分割提取节点
        ("nodes.morphology", "形态学模块"),  # 形态学节点
        ("nodes.conditions", "逻辑模块"),  # 条件逻辑节点
        ("nodes.template_matchings", "模板匹配模块"),  # 模板匹配节点
        ("nodes.detectors", "对象识别模块"),  # 对象识别节点
        ("nodes.features", "特征提取模块"),  # 特征提取节点
        ("nodes.others", "其他模块"),  # 其他节点
        ("nodes.video", "视频处理模块"),  # 视频处理节点
        ("nodes.outputs", "结果输出模块"),  # 结果输出节点
        ("nodes.onnx", "Onnx通用模型"),  # ONNX模型节点
        ("nodes.network", "网络通讯模块"),  # 网络通讯节点
    ]

    # 遍历所有包
    for module_name, group_name in packages:
        try:
            # 导入模块
            module = importlib.import_module(module_name)
            # 遍历模块中的所有成员
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # 如果不是 NodeBase 的子类或就是 NodeBase 本身，跳过
                if not issubclass(obj, NodeBase) or obj is NodeBase:
                    continue
                # 如果是抽象类，跳过
                if getattr(obj, '__abstract__', False) or inspect.isabstract(obj):
                    continue
                # 在分组管理器和类型注册表中注册节点
                ctx.node_groups.register_node(obj, group_name)
                ctx.node_registry.register(obj, group_name)
        except ImportError:
            # 包可能不存在，忽略
            pass

def run_gui(ctx):
    """在 GUI 模式下运行应用程序，使用依赖注入

    参数：
        ctx: 应用上下文对象
        project_path: 可选的项目文件路径
    """
    app = QApplication(sys.argv)
    app.setApplicationName("VisionFlow")
    app.setOrganizationName("VisionFlow")
    app.setApplicationVersion("2.0.0")
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "icons", "logo.ico")



    set_point_converter(lambda p: QPointF(p[0], p[1]))

    # 通过 ThemeManager 应用主题（唯一数据源）
    app.setStyle("Fusion")
    # 设置应用程序调色板
    app.setPalette(theme_manager.to_palette())
    # 设置应用程序样式表
    app.setStyleSheet(theme_manager.get_stylesheet())

    window = MainWindow(ctx=ctx)
    # 如果图标文件存在，设置窗口图标
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    # 显示窗口
    window.show()

    # 进入应用程序事件循环
    sys.exit(app.exec_())


def main():
    install_crash_handlers()
    ctx = bootstrap_app_context()
    run_gui(ctx)



if __name__ == '__main__':
    main()
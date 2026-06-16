#!/usr/bin/env python3
"""VisionFlow

一个受 VisionMaster 启发的计算机视觉可视化工作流编辑器。
使用 PyQt5 作为 GUI，使用 OpenCV 进行图像处理。

架构：
  main.py          → 启动入口：创建 AppContext，发现节点，启动 GUI
  core/            → 领域逻辑（无 GUI 导入）：接口、节点基类、工作流、事件
  services/        → 应用层：桥接 core ↔ gui（依赖注入容器、节点/项目/主题服务）
  gui/             → 纯 UI：面板、编辑器、控制器（依赖 core.interfaces + services）
  nodes/           → 视觉处理实现

用法：
    python main.py                          # 启动应用程序
    python main.py --project <file.json>    # 打开指定项目
    python main.py --cli <file.json>        # 无头模式运行项目（CLI 模式）
"""

import sys
import os
import argparse
import importlib
import inspect
import logging

from core.node_base import NodeBase
from gui.theme import theme_manager
from services.app_context import AppContext, set_app_context

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication


# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_logging():
    """配置应用程序的日志记录。"""
    # 配置日志记录的基本设置
    logging.basicConfig(
        level=logging.INFO,  # 日志级别为 INFO
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  # 日志格式
        handlers=[logging.StreamHandler(sys.stdout)],  # 输出到标准输出
    )


def bootstrap_app_context():
    """创建并初始化应用程序的依赖注入容器。

    这是所有服务连接在一起的唯一位置。
    其他模块不应创建全局单例。

    返回：
        初始化完成的 AppContext 对象
    """
    # 创建应用上下文对象
    ctx = AppContext()
    # 初始化默认服务（获得左侧控制面板内部有哪些组）
    ctx.init_defaults()

    # ── 发现并注册所有节点类型 ──
    _discover_nodes(ctx)
    # 设置全局应用上下文
    set_app_context(ctx)
    return ctx


def _discover_nodes(ctx):
    """显式发现并注册所有节点类型。

    取代了旧的 plugin_manager.discover_nodes_package()，
    该函数依赖于导入时的副作用。

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


def run_cli(project_path: str):
    """在 CLI 模式下运行项目（无头模式，无 GUI）

    参数：
        project_path: 项目文件路径
    """
    # 导入必要的模块（延迟导入，避免 GUI 依赖）
    from core.project import ProjectService
    from core.workflow import WorkflowState

    # 配置日志
    setup_logging()
    # 获取日志记录器
    logger = __import__('logging').getLogger('VisionFlow.CLI')

    # 创建项目服务
    svc = ProjectService()
    # 加载项目
    project = svc.load(project_path)
    # 如果加载失败或没有工作流
    if project is None or project.workflow is None:
        logger.error(f"Failed to load project: {project_path}")
        sys.exit(1)

    # 记录开始运行
    logger.info(f"Running project: {project.name}")
    # 执行工作流
    result = project.workflow.execute()

    # 根据执行结果退出
    if result.is_ok:
        logger.info(f"Project completed successfully: {result.message}")
        sys.exit(0)
    else:
        logger.error(f"Project failed: {result.message}")
        sys.exit(1)


def run_gui(ctx, project_path: str = None):
    """在 GUI 模式下运行应用程序，使用依赖注入

    参数：
        ctx: 应用上下文对象
        project_path: 可选的项目文件路径
    """
    # 配置日志
    setup_logging()

    # 创建 Qt 应用程序
    app = QApplication(sys.argv)
    # 设置应用程序名称
    app.setApplicationName("VisionFlow")
    # 设置组织名称
    app.setOrganizationName("VisionFlow")
    # 设置应用程序版本
    app.setApplicationVersion("2.0.0")
    # Logo 图标路径
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "icons", "logo.ico")
    # 如果图标文件存在
    if os.path.exists(icon_path):
        # 设置应用程序图标
        app.setWindowIcon(QIcon(icon_path))

    # 注入坐标转换器（core → GUI 桥接）
    from core.commands import set_point_converter
    from PyQt5.QtCore import QPointF
    set_point_converter(lambda p: QPointF(p[0], p[1]))

    # 通过 ThemeManager 应用主题（唯一数据源）
    app.setStyle("Fusion")
    # 设置应用程序调色板
    app.setPalette(theme_manager.colors.to_palette())
    # 设置应用程序样式表
    app.setStyleSheet(theme_manager.get_stylesheet())

    # 创建并显示主窗口，注入上下文
    from gui.main_window import MainWindow
    window = MainWindow(ctx=ctx)
    # 如果图标文件存在，设置窗口图标
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    # 显示窗口
    window.show()

    # 如果指定了项目路径且文件存在，打开项目
    if project_path and os.path.exists(project_path):
        window.open_project(project_path)

    # 进入应用程序事件循环
    sys.exit(app.exec_())


def main():
    """主入口点 — 显式引导，没有隐藏的副作用。"""
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(
        description="VisionFlow - Visual Workflow Editor for Computer Vision"
    )
    # 添加项目文件参数
    parser.add_argument("--project", "-p", type=str,
                        help="Project file to open (.json)")
    # 添加 CLI 模式参数
    parser.add_argument("--cli", "-c", type=str,
                        help="Run project in CLI mode (headless)")
    # 解析参数
    args = parser.parse_args()

    # 如果指定了 CLI 模式
    if args.cli:
        run_cli(args.cli)
    else:
        # 引导应用上下文
        ctx = bootstrap_app_context()
        # 运行 GUI 模式
        run_gui(ctx, args.project)


# 如果作为主程序运行
if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""VisionFlow

A visual workflow editor for computer vision, inspired by VisionMaster.
Uses PyQt5 for the GUI and OpenCV for image processing.

Architecture:
  main.py          → bootstrap: creates AppContext, discovers nodes, starts GUI
  core/            → domain logic (no GUI imports): interfaces, node_base, workflow, events
  services/        → application layer: bridges core ↔ gui (DI container, node/project/theme services)
  gui/             → pure UI: panels, editors, controllers (depends on core.interfaces + services)
  nodes/           → vision processing implementations

Usage:
    python main.py                          # Launch the application
    python main.py --project <file.json>    # Open a specific project
    python main.py --cli <file.json>        # Run a project headless (CLI mode)
"""

import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_logging():
    """Configure logging for the application."""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def bootstrap_app_context():
    """Create and initialize the application DI container.

    This is the SINGLE place where all services are wired together.
    No other module should create global singletons.
    """
    from services.app_context import AppContext, set_app_context

    ctx = AppContext()
    ctx.init_defaults()

    # ── Discover and register all node types ──
    _discover_nodes(ctx)

    set_app_context(ctx)
    return ctx


def _discover_nodes(ctx):
    """Explicitly discover and register all node types.

    Replaces the old plugin_manager.discover_nodes_package() which
    relied on import-time side effects.
    """
    import importlib
    import inspect
    from core.node_base import NodeBase

    # Standard node packages
    packages = [
        ("nodes.sources",          "图像数据源"),
        ("nodes.preprocessings",   "图像预处理模块"),
        ("nodes.blurs",            "滤波模块"),
        ("nodes.takeoffs",         "图像分割提取模块"),
        ("nodes.morphology",       "形态学模块"),
        ("nodes.conditions",       "逻辑模块"),
        ("nodes.template_matchings", "模板匹配模块"),
        ("nodes.detectors",         "对象识别模块"),
        ("nodes.features",          "特征提取模块"),
        ("nodes.others",            "其他模块"),
        ("nodes.video",             "视频处理模块"),
        ("nodes.outputs",           "结果输出模块"),
        ("nodes.onnx",              "Onnx通用模型"),
        ("nodes.network",           "网络通讯模块"),
    ]

    for module_name, group_name in packages:
        try:
            module = importlib.import_module(module_name)
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if not issubclass(obj, NodeBase) or obj is NodeBase:
                    continue
                if getattr(obj, '__abstract__', False) or inspect.isabstract(obj):
                    continue
                # Register in both group manager AND type registry
                ctx.node_groups.register_node(obj, group_name)
                ctx.node_registry.register(obj, group_name)
        except ImportError:
            pass  # package may not exist


def run_cli(project_path: str):
    """Run a project in CLI mode (headless, no GUI)."""
    from core.project import ProjectService
    from core.workflow import WorkflowState

    setup_logging()
    logger = __import__('logging').getLogger('VisionFlow.CLI')

    svc = ProjectService()
    project = svc.load(project_path)
    if project is None or project.workflow is None:
        logger.error(f"Failed to load project: {project_path}")
        sys.exit(1)

    logger.info(f"Running project: {project.name}")
    result = project.workflow.execute()

    if result.is_ok:
        logger.info(f"Project completed successfully: {result.message}")
        sys.exit(0)
    else:
        logger.error(f"Project failed: {result.message}")
        sys.exit(1)


def run_gui(ctx, project_path: str = None):
    """Run the application in GUI mode with dependency injection."""
    setup_logging()

    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QIcon
    except ImportError:
        print("PyQt5 is required for GUI mode. Install it with: pip install PyQt5")
        print("Or use CLI mode: python main.py --cli <project.json>")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("VisionFlow")
    app.setOrganizationName("VisionFlow")
    app.setApplicationVersion("2.0.0")

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "icons", "logo.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Apply theme via ThemeManager (single source of truth)
    from gui.theme import theme_manager
    app.setStyle("Fusion")
    app.setPalette(theme_manager.colors.to_palette())
    app.setStyleSheet(theme_manager.get_stylesheet())

    # Create and show main window with injected context
    from gui.main_window import MainWindow
    window = MainWindow(ctx=ctx)
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    # Open project if specified
    if project_path and os.path.exists(project_path):
        window.open_project(project_path)

    sys.exit(app.exec_())


def main():
    """Main entry point — explicit bootstrap, no hidden side effects."""
    import argparse

    parser = argparse.ArgumentParser(
        description="VisionFlow - Visual Workflow Editor for Computer Vision"
    )
    parser.add_argument("--project", "-p", type=str,
                        help="Project file to open (.json)")
    parser.add_argument("--cli", "-c", type=str,
                        help="Run project in CLI mode (headless)")
    args = parser.parse_args()

    if args.cli:
        run_cli(args.cli)
    else:
        ctx = bootstrap_app_context()
        run_gui(ctx, args.project)


if __name__ == "__main__":
    main()

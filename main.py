#!/usr/bin/env python3
"""VisionFlow - Python port of WPF-VisionMaster.

A visual workflow editor for computer vision, inspired by VisionMaster.
Uses PyQt5 for the GUI and OpenCV for image processing.

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
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def run_cli(project_path: str):
    """Run a project in CLI mode (headless, no GUI)."""
    import json
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


def run_gui(project_path: str = None):
    """Run the application in GUI mode."""
    setup_logging()

    # Check PyQt availability
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

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons", "logo.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Apply dark theme
    app.setStyle("Fusion")
    _apply_dark_theme(app)

    # Bootstrap: auto-discover and register all nodes
    from core.plugin_manager import plugin_manager
    plugin_manager.discover_nodes_package()

    # Create and show main window
    from gui.main_window import MainWindow
    window = MainWindow()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    # Open project if specified
    if project_path and os.path.exists(project_path):
        window.open_project(project_path)

    sys.exit(app.exec_())


def _apply_dark_theme(app):
    """Apply a dark color palette - ported from H.Themes.Colors.Dark."""
    from PyQt5.QtGui import QPalette, QColor
    from PyQt5.QtCore import Qt

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(45, 45, 48))
    palette.setColor(QPalette.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.Base, QColor(30, 30, 30))
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 48))
    palette.setColor(QPalette.ToolTipBase, QColor(60, 60, 60))
    palette.setColor(QPalette.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.Button, QColor(45, 45, 48))
    palette.setColor(QPalette.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(128, 128, 128))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(128, 128, 128))
    app.setPalette(palette)

    # Dark theme stylesheet
    app.setStyleSheet("""
        QToolTip { color: #dcdcdc; background-color: #3c3c3c; border: 1px solid #505050; }
        QDockWidget { color: #dcdcdc; }
        QDockWidget::title { background: #2d2d30; padding: 6px; }
        QMenuBar { background: #2d2d30; color: #dcdcdc; }
        QMenuBar::item:selected { background: #3e3e42; }
        QMenu { background: #2d2d30; color: #dcdcdc; border: 1px solid #505050; }
        QMenu::item:selected { background: #0078d4; }
        QStatusBar { background: #007acc; color: white; }
        QStatusBar::item { border: none; }
        QScrollBar:vertical { background: #1e1e1e; width: 12px; }
        QScrollBar::handle:vertical { background: #505050; min-height: 20px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar:horizontal { background: #1e1e1e; height: 12px; }
        QScrollBar::handle:horizontal { background: #505050; min-width: 20px; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
    """)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="VisionFlow - Visual Workflow Editor for Computer Vision"
    )
    parser.add_argument("--project", "-p", type=str, help="Project file to open (.json)")
    parser.add_argument("--cli", "-c", type=str, help="Run project in CLI mode (headless)")
    args = parser.parse_args()

    if args.cli:
        run_cli(args.cli)
    else:
        run_gui(args.project)


if __name__ == "__main__":
    main()

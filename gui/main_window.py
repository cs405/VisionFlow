"""
主窗口 - 组装所有UI组件
"""

import sys
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMenuBar, QMenu, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QDockWidget, QTreeWidget,
    QTreeWidgetItem, QLabel, QPushButton, QApplication
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence

from core.registry import NodeRegistry
from core.workflow import Workflow
from core.events import EventBus, Event, EventType

from .node_editor.editor_widget import NodeEditorWidget
from .property_panel import PropertyPanel
from .image_viewer import ImageViewer
from .log_panel import LogPanel


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()

        # 核心组件
        self.workflow = Workflow()
        self.event_bus = EventBus()
        self.node_registry = NodeRegistry()

        # 订阅事件
        self._subscribe_events()

        # 自动发现节点
        self.node_registry.discover_nodes("nodes")
        self.node_registry.discover_plugins("plugins")

        # 设置UI
        self.setWindowTitle("VisionFlow - 视觉流程设计器")
        self.setMinimumSize(1200, 800)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # 左侧：节点工具箱
        self._create_toolbox_dock()

        # 中间：节点编辑器
        self.node_editor = NodeEditorWidget(self.workflow, self.event_bus)
        splitter.addWidget(self.node_editor)

        # 右侧：属性面板和图像显示
        right_splitter = QSplitter(Qt.Vertical)

        self.property_panel = PropertyPanel(self.event_bus)
        right_splitter.addWidget(self.property_panel)

        self.image_viewer = ImageViewer(self.event_bus)
        right_splitter.addWidget(self.image_viewer)

        splitter.addWidget(right_splitter)

        # 设置分割比例
        splitter.setSizes([250, 600, 300])
        right_splitter.setSizes([300, 400])

        # 创建菜单栏和工具栏
        self._create_menu_bar()
        self._create_tool_bar()

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)

        # 日志面板（底部停靠）
        self._create_log_dock()

        # 初始化完成
        self.event_bus.emit_log("INFO", "VisionFlow 启动完成")

    def _subscribe_events(self):
        """订阅事件"""
        self.event_bus.subscribe(EventType.LOG_MESSAGE, self._on_log_message)
        self.event_bus.subscribe(EventType.WORKFLOW_EXECUTED, self._on_workflow_executed)
        self.event_bus.subscribe(EventType.PROJECT_LOADED, self._on_project_loaded)
        self.event_bus.subscribe(EventType.PROJECT_SAVED, self._on_project_saved)

    def _create_toolbox_dock(self):
        """创建左侧工具箱停靠窗口"""
        dock = QDockWidget("节点工具箱", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # 创建树形控件
        self.toolbox_tree = QTreeWidget()
        self.toolbox_tree.setHeaderLabel("节点类型")
        self.toolbox_tree.setDragEnabled(True)

        # 按分类添加节点
        categories = self.node_registry.get_categories()
        for category, nodes in sorted(categories.items()):
            category_item = QTreeWidgetItem([category])
            category_item.setFlags(category_item.flags() | Qt.ItemIsEnabled)

            for node_name in sorted(nodes):
                node_item = QTreeWidgetItem([node_name])
                node_item.setData(0, Qt.UserRole, node_name)
                node_item.setFlags(node_item.flags() | Qt.ItemIsDragEnabled)
                category_item.addChild(node_item)

            self.toolbox_tree.addTopLevelItem(category_item)

        # 展开所有分类
        self.toolbox_tree.expandAll()

        dock.setWidget(self.toolbox_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def _create_log_dock(self):
        """创建日志面板停靠窗口"""
        dock = QDockWidget("日志输出", self)
        dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)

        self.log_panel = LogPanel(self.event_bus)
        dock.setWidget(self.log_panel)

        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        new_action = QAction("新建项目(&N)", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._on_new_project)
        file_menu.addAction(new_action)

        open_action = QAction("打开项目(&O)...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_action)

        save_action = QAction("保存项目(&S)", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._on_save_project)
        file_menu.addAction(save_action)

        save_as_action = QAction("另存为(&A)...", self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(self._on_save_as_project)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑(&E)")

        clear_action = QAction("清空工作流", self)
        clear_action.triggered.connect(self._on_clear_workflow)
        edit_menu.addAction(clear_action)

        # 运行菜单
        run_menu = menubar.addMenu("运行(&R)")

        execute_action = QAction("执行工作流(&E)", self)
        execute_action.setShortcut(QKeySequence("F5"))
        execute_action.triggered.connect(self._on_execute_workflow)
        run_menu.addAction(execute_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")

        reset_view_action = QAction("重置视图", self)
        reset_view_action.triggered.connect(self._on_reset_view)
        view_menu.addAction(reset_view_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _create_tool_bar(self):
        """创建工具栏"""
        toolbar = QToolBar("主工具栏")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        # 执行按钮
        execute_btn = QPushButton("▶ 执行")
        execute_btn.clicked.connect(self._on_execute_workflow)
        toolbar.addWidget(execute_btn)

        toolbar.addSeparator()

        # 保存按钮
        save_btn = QPushButton("💾 保存")
        save_btn.clicked.connect(self._on_save_project)
        toolbar.addWidget(save_btn)

    def _on_new_project(self):
        """新建项目"""
        if self._confirm_discard_changes():
            self.workflow.clear()
            self.property_panel.clear()
            self.image_viewer.clear()
            self.status_label.setText("已创建新项目")

    def _on_open_project(self):
        """打开项目"""
        if not self._confirm_discard_changes():
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self, "打开项目", "", "VisionFlow项目 (*.vfproj);;JSON文件 (*.json)"
        )
        if filepath:
            try:
                self.workflow.load(filepath)
                self.node_editor.refresh_from_workflow()
                self.status_label.setText(f"已加载项目: {os.path.basename(filepath)}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载项目失败: {str(e)}")

    def _on_save_project(self):
        """保存项目"""
        if self.workflow.project_path:
            self.workflow.save(self.workflow.project_path)
            self.status_label.setText(f"已保存: {os.path.basename(self.workflow.project_path)}")
        else:
            self._on_save_as_project()

    def _on_save_as_project(self):
        """另存为"""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存项目", "", "VisionFlow项目 (*.vfproj)"
        )
        if filepath:
            if not filepath.endswith('.vfproj'):
                filepath += '.vfproj'
            self.workflow.save(filepath)
            self.status_label.setText(f"已保存: {os.path.basename(filepath)}")

    def _on_clear_workflow(self):
        """清空工作流"""
        if self._confirm_discard_changes():
            self.workflow.clear()
            self.node_editor.clear_scene()
            self.property_panel.clear()

    def _on_execute_workflow(self):
        """执行工作流"""
        if len(self.workflow.nodes) == 0:
            QMessageBox.information(self, "提示", "工作流中没有节点")
            return

        self.status_label.setText("正在执行...")
        QApplication.processEvents()

        try:
            results = self.workflow.execute()

            # 显示最终输出图像
            for node_id, outputs in results.items():
                for name, value in outputs.items():
                    if hasattr(value, 'shape'):  # 是图像
                        self.image_viewer.set_image(value, f"节点输出")
                        break

            self.status_label.setText("执行完成")
        except Exception as e:
            QMessageBox.critical(self, "执行错误", str(e))
            self.status_label.setText("执行失败")

    def _on_reset_view(self):
        """重置视图"""
        self.node_editor.reset_view()

    def _on_about(self):
        """关于对话框"""
        QMessageBox.about(
            self,
            "关于 VisionFlow",
            "VisionFlow - 视觉流程设计器\n\n"
            "版本: 1.0.0\n"
            "基于 PySide6 + OpenCV 开发\n\n"
            "支持拖拽式构建视觉检测流程"
        )

    def _confirm_discard_changes(self) -> bool:
        """确认丢弃更改"""
        if len(self.workflow.nodes) > 0:
            reply = QMessageBox.question(
                self, "确认",
                "当前工作流未保存，是否继续？",
                QMessageBox.Yes | QMessageBox.No
            )
            return reply == QMessageBox.Yes
        return True

    def _on_log_message(self, event: Event):
        """处理日志消息"""
        data = event.data
        level = data.get("level", "INFO")
        message = data.get("message", "")
        self.status_label.setText(f"[{level}] {message[:50]}")

    def _on_workflow_executed(self, event: Event):
        """工作流执行完成"""
        results = event.data.get("results", {})
        self.status_label.setText(f"执行完成，共 {len(results)} 个节点")

    def _on_project_loaded(self, event: Event):
        """项目加载完成"""
        self.node_editor.refresh_from_workflow()

    def _on_project_saved(self, event: Event):
        """项目保存完成"""
        pass

    def closeEvent(self, event):
        """关闭事件"""
        if self._confirm_discard_changes():
            event.accept()
        else:
            event.ignore()
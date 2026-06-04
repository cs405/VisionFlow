"""Main window - full application layout with menus, toolbar, dock panels.

Ported from:
  - H.App.VisionMaster.OpenCV/MainWindow.xaml(.cs)
  - H.Windows.Main/MainWindow

Layout:
  ┌─────────────────────────────────────────────────────┐
  │ Custom Title Bar  [菜单栏 + 工具栏]                    │
  ├────────┬───────────────────────────┬────────────────┤
  │ 工具箱  │                           │ 属性面板         │
  │ (树形)  │   节点编辑器 / 图像查看器    │ 结果面板         │
  │        │                           │ 帮助面板         │
  │ 流程资源 │                           │                │
  ├────────┴───────────────────────────┴────────────────┤
  │ 图像源文件列表 (FlowResourcePanel)                    │
  ├─────────────────────────────────────────────────────┤
  │ 状态栏: 流程状态 | 消息 | 时间                         │
  └─────────────────────────────────────────────────────┘
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QSplitter, QDockWidget, QMenuBar, QMenu, QAction,
                              QToolBar, QStatusBar, QLabel, QTabWidget,
                              QMessageBox, QFileDialog, QApplication,
                              QPushButton, QFrame, QSizePolicy)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette

from core.node_base import NodeBase, VisionNodeData, SrcFilesVisionNodeData
from core.workflow import WorkflowEngine
from core.project import project_service
from core.events import EventType, event_system
from core.registry import node_registry

from gui.theme import theme_manager, ThemeColors
from gui.toolbox_panel import ToolboxPanel
from gui.property_panel import PropertyPanel
from gui.result_panel import ResultPanel
from gui.image_viewer import ImageViewerPanel
from gui.log_panel import LogPanel
from gui.flow_resource_panel import FlowResourcePanel


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self._workflow: WorkflowEngine | None = None
        self._selected_node: NodeBase | None = None

        self._setup_window()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_content()
        self._setup_status_bar()
        self._connect_events()

        # Create initial empty project
        self._on_new_project()

    def _setup_window(self):
        """Configure the main window."""
        self.setWindowTitle("VisionFlow - 视觉流程编辑器")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 600)

        # Apply theme
        palette = theme_manager.colors.to_palette()
        self.setPalette(palette)
        self.setStyleSheet(theme_manager.get_stylesheet())

        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2,
                  (screen.height() - self.height()) // 2)

    # -- Menu Bar --

    def _setup_menu_bar(self):
        """Create the menu bar matching the WPF version."""
        menubar = self.menuBar()

        # === 文件 (File) ===
        file_menu = menubar.addMenu("文件")

        new_action = QAction("新建项目", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._on_new_project)
        file_menu.addAction(new_action)

        open_action = QAction("打开项目...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_action)

        save_action = QAction("保存项目", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save_project)
        file_menu.addAction(save_action)

        save_as_action = QAction("另存为...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self._on_save_as_project)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        # Recent projects submenu
        self.recent_menu = file_menu.addMenu("最近的项目")
        self.recent_menu.aboutToShow.connect(self._update_recent_menu)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # === 编辑 (Edit) ===
        edit_menu = menubar.addMenu("编辑")

        undo_action = QAction("撤销", self)
        undo_action.setShortcut("Ctrl+Z")
        edit_menu.addAction(undo_action)

        redo_action = QAction("重做", self)
        redo_action.setShortcut("Ctrl+Y")
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        delete_action = QAction("删除选中节点", self)
        delete_action.setShortcut("Delete")
        edit_menu.addAction(delete_action)

        select_all_action = QAction("全选", self)
        select_all_action.setShortcut("Ctrl+A")
        edit_menu.addAction(select_all_action)

        # === 运行 (Run) ===
        run_menu = menubar.addMenu("运行")

        run_action = QAction("运行流程", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self._on_run_workflow)
        run_menu.addAction(run_action)

        stop_action = QAction("停止", self)
        stop_action.setShortcut("Shift+F5")
        stop_action.triggered.connect(self._on_stop_workflow)
        run_menu.addAction(stop_action)

        step_action = QAction("单步执行", self)
        step_action.setShortcut("F10")
        run_menu.addAction(step_action)

        # === 系统 (System) ===
        sys_menu = menubar.addMenu("系统")

        settings_action = QAction("设置...", self)
        sys_menu.addAction(settings_action)

        theme_action = QAction("主题设置", self)
        sys_menu.addAction(theme_action)

        sys_menu.addSeparator()
        sys_menu.addAction("流程功能列表")

        # === 帮助 (Help) ===
        help_menu = menubar.addMenu("帮助")

        about_action = QAction("关于 VisionFlow", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _update_recent_menu(self):
        """Update the recent projects submenu."""
        self.recent_menu.clear()
        for path in project_service.recent_projects:
            import os
            action = QAction(os.path.basename(path), self)
            action.setToolTip(path)
            action.triggered.connect(lambda checked, p=path: self._open_project(p))
            self.recent_menu.addAction(action)

    # -- Toolbar --

    def _setup_toolbar(self):
        """Create the toolbar matching the WPF version."""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        # Project operations
        new_btn = QPushButton("新建")
        new_btn.setFlat(True)
        new_btn.clicked.connect(self._on_new_project)
        toolbar.addWidget(new_btn)

        open_btn = QPushButton("打开")
        open_btn.setFlat(True)
        open_btn.clicked.connect(self._on_open_project)
        toolbar.addWidget(open_btn)

        save_btn = QPushButton("保存")
        save_btn.setFlat(True)
        save_btn.clicked.connect(self._on_save_project)
        toolbar.addWidget(save_btn)

        toolbar.addSeparator()

        # Workflow operations
        run_btn = QPushButton("▶ 运行")
        run_btn.setFlat(True)
        run_btn.clicked.connect(self._on_run_workflow)
        toolbar.addWidget(run_btn)

        stop_btn = QPushButton("■ 停止")
        stop_btn.setFlat(True)
        stop_btn.clicked.connect(self._on_stop_workflow)
        toolbar.addWidget(stop_btn)

        toolbar.addSeparator()

        # Zoom controls
        zoom_in_btn = QPushButton("放大")
        zoom_in_btn.setFlat(True)
        zoom_in_btn.clicked.connect(lambda: self.image_panel.viewer.zoom_in())
        toolbar.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("缩小")
        zoom_out_btn.setFlat(True)
        zoom_out_btn.clicked.connect(lambda: self.image_panel.viewer.zoom_out())
        toolbar.addWidget(zoom_out_btn)

        fit_btn = QPushButton("适应")
        fit_btn.setFlat(True)
        fit_btn.clicked.connect(lambda: self.image_panel.viewer.fit_to_window())
        toolbar.addWidget(fit_btn)

        toolbar.addSeparator()

        # Project name display
        self.project_name_label = QLabel("  新建项目  ")
        self.project_name_label.setStyleSheet("color: #dcdcdc; font-size: 12px;")
        toolbar.addWidget(self.project_name_label)

    # -- Content Area --

    def _setup_content(self):
        """Set up the main content area with all panels."""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main horizontal splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # === LEFT PANEL - Toolbox + Log ===
        left_tabs = QTabWidget()
        left_tabs.setFixedWidth(280)

        self.toolbox = ToolboxPanel()
        left_tabs.addTab(self.toolbox, "工具箱")

        self.log_panel = LogPanel()
        left_tabs.addTab(self.log_panel, "日志")

        self.main_splitter.addWidget(left_tabs)

        # === CENTER - Image viewer (placeholder for node editor in P2) ===
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # Tab widget for diagram/image view
        self.center_tabs = QTabWidget()
        self.image_panel = ImageViewerPanel()
        self.center_tabs.addTab(self.image_panel, "图像预览")
        center_layout.addWidget(self.center_tabs)

        self.main_splitter.addWidget(center_widget)

        # === RIGHT PANEL - Property + Result + Help ===
        right_tabs = QTabWidget()
        right_tabs.setFixedWidth(300)

        self.property_panel = PropertyPanel()
        right_tabs.addTab(self.property_panel, "属性")

        self.result_panel = ResultPanel()
        right_tabs.addTab(self.result_panel, "结果")

        self.main_splitter.addWidget(right_tabs)

        # Set splitter ratios (left: 280, center: stretch, right: 300)
        self.main_splitter.setSizes([280, 800, 300])

        # === BOTTOM - Flow Resource Panel (image source file list) ===
        self.resource_panel = FlowResourcePanel()
        self.resource_panel.setVisible(False)  # Hidden until a source node is selected
        main_layout.addWidget(self.resource_panel)

        # Connect signals
        self.toolbox.node_type_selected.connect(self._on_node_type_selected)
        self.property_panel.property_changed.connect(self._on_property_changed)

    # -- Status Bar --

    def _setup_status_bar(self):
        """Create the status bar matching the WPF version."""
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: #007acc;
                color: white;
                padding: 2px 8px;
                font-size: 12px;
            }
            QStatusBar::item { border: none; }
        """)
        self.setStatusBar(self.status_bar)

        # Flow state indicator
        self.state_label = QLabel("● 空闲")
        self.state_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        self.status_bar.addWidget(self.state_label)

        self.status_bar.addWidget(self._make_separator())

        # Message
        self.message_label = QLabel("就绪")
        self.status_bar.addWidget(self.message_label, 1)

        self.status_bar.addWidget(self._make_separator())

        # Node count
        self.node_count_label = QLabel("节点: 0")
        self.status_bar.addPermanentWidget(self.node_count_label)

        # Time
        self.time_label = QLabel("")
        self.status_bar.addPermanentWidget(self.time_label)

    def _make_separator(self) -> QFrame:
        """Create a vertical separator for the status bar."""
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.3);")
        return sep

    # -- Event Connections --

    def _connect_events(self):
        """Connect to the event system for automatic updates."""
        event_system.subscribe(EventType.NODE_SELECTED, self._on_event_node_selected)
        event_system.subscribe(EventType.DIAGRAM_CHANGED, self._on_event_diagram_changed)
        event_system.subscribe(EventType.WORKFLOW_STARTED, self._on_workflow_started)
        event_system.subscribe(EventType.WORKFLOW_COMPLETED, self._on_workflow_completed)
        event_system.subscribe(EventType.WORKFLOW_ERROR, self._on_workflow_error)
        event_system.subscribe(EventType.PROJECT_LOADED, self._on_project_loaded)
        event_system.subscribe(EventType.PROJECT_SAVED, self._on_project_saved)

    # -- Event Handlers --

    def _on_event_node_selected(self, sender, **kwargs):
        """Handle node selection (from event or UI)."""
        node = kwargs.get('node', sender)
        self._select_node(node)

    def _on_event_diagram_changed(self, sender, **kwargs):
        """Handle diagram changes."""
        if self._workflow:
            nodes = self._workflow.get_all_nodes()
            self.node_count_label.setText(f"节点: {len(nodes)}")
            self.status_bar.showMessage(f"节点数量: {len(nodes)}", 3000)

    def _on_workflow_started(self, sender, **kwargs):
        self.state_label.setText("● 运行中")
        self.state_label.setStyleSheet("color: #2196f3; font-weight: bold;")
        self.message_label.setText("流程运行中...")

    def _on_workflow_completed(self, sender, **kwargs):
        self.state_label.setText("● 完成")
        self.state_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        self.message_label.setText("流程执行完成")

    def _on_workflow_error(self, sender, **kwargs):
        self.state_label.setText("● 错误")
        self.state_label.setStyleSheet("color: #f44336; font-weight: bold;")
        result = kwargs.get('result')
        msg = str(result) if result else "流程执行错误"
        self.message_label.setText(msg)

    def _on_project_loaded(self, sender, **kwargs):
        project = kwargs.get('project')
        if project:
            self.project_name_label.setText(f"  {project.display_name}  ")
            self._workflow = project.workflow
            self._select_node(None)

    def _on_project_saved(self, sender, **kwargs):
        project = kwargs.get('project')
        if project:
            self.project_name_label.setText(f"  {project.display_name}  ")

    # -- Node selection --

    def _select_node(self, node: NodeBase | None):
        """Select a node and update panels."""
        self._selected_node = node

        # Update property panel
        self.property_panel.set_node(node)

        # Update result panel
        if isinstance(node, VisionNodeData):
            self.result_panel.show_node_results(node)
            self.result_panel.show_help(node)
        else:
            self.result_panel.show_node_results(None)
            self.result_panel.show_help(None)

        # Show/hide resource panel for source file nodes
        if isinstance(node, SrcFilesVisionNodeData):
            self.resource_panel.set_node(node)
            self.resource_panel.setVisible(True)
        else:
            self.resource_panel.setVisible(False)

        # Update image viewer
        if isinstance(node, VisionNodeData) and node.mat is not None:
            self.image_panel.set_image(node.mat)
        elif isinstance(node, VisionNodeData) and node._result_image_source is not None:
            self.image_panel.set_image(node._result_image_source)

    def _on_node_type_selected(self, type_name: str):
        """Create a node from the toolbox and add it to the workflow."""
        if self._workflow is None:
            return
        node = node_registry.create(type_name)
        if node:
            self._workflow.add_node(node)
            self.log_panel.info(f"添加节点: {node.name}")
            self.node_count_label.setText(f"节点: {len(self._workflow.get_all_nodes())}")

    def _on_property_changed(self, name: str, old_value, new_value):
        """Handle property changes from the property panel."""
        if self._selected_node:
            event_system.publish(EventType.NODE_PROPERTY_CHANGED,
                               sender=self._selected_node,
                               name=name, old=old_value, new=new_value)

    # -- Project Operations --

    def _on_new_project(self):
        """Create a new empty project."""
        if self._workflow:
            # TODO: Ask save if dirty
            pass
        project = project_service.new_project()
        self._workflow = project.workflow
        self.project_name_label.setText(f"  {project.display_name}  ")
        self._select_node(None)
        self.log_panel.info("新建项目")

    def _on_open_project(self):
        """Open a project file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "打开项目", "", project_service.FILE_FILTER)
        if path:
            self._open_project(path)

    def _open_project(self, path: str):
        """Load a project from a file path."""
        project = project_service.load(path)
        if project:
            self._workflow = project.workflow
            self.project_name_label.setText(f"  {project.display_name}  ")
            self._select_node(None)
            self.log_panel.success(f"已打开: {path}")

    def open_project(self, file_path: str):
        """Public method to open a project (called by main.py)."""
        self._open_project(file_path)

    def _on_save_project(self):
        """Save the current project."""
        if project_service.current_project:
            if project_service.current_project.is_saved:
                project_service.save()
                self.log_panel.success("项目已保存")
            else:
                self._on_save_as_project()

    def _on_save_as_project(self):
        """Save project to a new file."""
        project = project_service.current_project or project_service.new_project()
        path, _ = QFileDialog.getSaveFileName(
            self, "另存为...", f"{project.display_name}.json", project_service.FILE_FILTER)
        if path:
            if project.workflow is None:
                project.workflow = self._workflow
            project_service.save_as(project, path)
            self.log_panel.success(f"项目已保存至: {path}")

    # -- Workflow Operations --

    def _on_run_workflow(self):
        """Execute the current workflow."""
        if self._workflow is None:
            return
        self.log_panel.info("开始执行流程...")
        result = self._workflow.execute()
        if result.is_ok:
            self.log_panel.success(f"流程完成: {result.message}")
        elif result.is_error:
            self.log_panel.error(f"流程错误: {result.message}")

    def _on_stop_workflow(self):
        """Stop workflow execution."""
        if self._workflow:
            self._workflow.stop()
            self.log_panel.warning("流程已停止")

    # -- Help --

    def _on_about(self):
        """Show about dialog."""
        QMessageBox.about(self, "关于 VisionFlow",
                          "<h2>VisionFlow 2.0</h2>"
                          "<p>视觉流程编辑器</p>"
                          "<p>移植自 WPF-VisionMaster (HeBianGu)</p>"
                          "<p>使用 Python + PyQt5 + OpenCV</p>"
                          "<hr>"
                          "<p>开源项目 | MIT License</p>")

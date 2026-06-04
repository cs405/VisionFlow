"""
主窗口 - 专业级视觉流程设计器（仿VisionMaster风格）
"""

import sys
import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMenuBar, QMenu, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QDockWidget, QTreeWidget,
    QTreeWidgetItem, QLabel, QPushButton, QApplication,
    QTabWidget, QFrame, QSizePolicy, QToolButton,
    QButtonGroup, QStackedWidget, QListWidget, QListWidgetItem,
    QLineEdit, QComboBox, QProgressBar, QCheckBox, QGroupBox
)
from PySide6.QtCore import Qt, QSize, Signal, QTimer, QRect
from PySide6.QtGui import QAction, QIcon, QKeySequence, QFont, QColor, QPalette, QPixmap, QPainter, QPen, QBrush

from core.registry import NodeRegistry
from core.workflow import Workflow
from core.events import EventBus, Event, EventType

from .node_editor.editor_widget import NodeEditorWidget
from .property_panel import PropertyPanel
from .image_viewer import ImageViewer
from .log_panel import LogPanel


class MainWindow(QMainWindow):
    """主窗口 - VisionMaster风格"""

    def __init__(self):
        super().__init__()

        # 事件总线（唯一与Core层的连接）
        self.event_bus = EventBus()
        self.node_registry = NodeRegistry()

        # ========== 初始化状态属性（必须在创建UI之前） ==========
        self.status_label = None
        self.status_indicator = None
        self.node_count_label = None
        self.flow_status_label = None
        self.progress_bar = None
        # ======================================================

        # 订阅UI需要响应的事件
        self._subscribe_events()

        # 自动发现节点（通过事件通知Core层）
        self.event_bus.emit(Event(
            type=EventType.SYSTEM_DISCOVER_NODES,
            data={"paths": ["nodes", "plugins"]}
        ))

        # 设置窗口
        self.setWindowTitle("VisionFlow - 智能视觉流程设计器")
        self.setMinimumSize(1400, 900)
        self.setWindowState(Qt.WindowMaximized)

        # 设置样式
        self._setup_style()

        # 创建UI组件
        self._setup_central_widget()
        self._create_menu_bar()
        self._create_tool_bars()
        self._create_status_bar()
        self._create_dock_panels()

        # 请求初始化完成
        self.event_bus.emit(Event(
            type=EventType.SYSTEM_INITIALIZED,
            data={}
        ))

        self.event_bus.emit_log("INFO", "VisionFlow UI 启动完成")
        if self.status_bar:
            self.status_bar.showMessage("就绪", 3000)

    def _setup_style(self):
        """设置现代化样式表"""
        self.setStyleSheet("""
            /* 主窗口背景 */
            QMainWindow {
                background-color: #1E1E1E;
            }
            
            /* 菜单栏 */
            QMenuBar {
                background-color: #2D2D2D;
                color: #E0E0E0;
                border-bottom: 1px solid #3D3D3D;
                font: 12px "Microsoft YaHei";
            }
            QMenuBar::item {
                padding: 4px 8px;
                background: transparent;
            }
            QMenuBar::item:selected {
                background-color: #4A4A4A;
                border-radius: 3px;
            }
            
            /* 菜单 */
            QMenu {
                background-color: #2D2D2D;
                color: #E0E0E0;
                border: 1px solid #3D3D3D;
                font: 12px "Microsoft YaHei";
            }
            QMenu::item {
                padding: 6px 30px 6px 20px;
            }
            QMenu::item:selected {
                background-color: #4A6A9A;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3D3D3D;
                margin: 5px 10px;
            }
            
            /* 工具栏 */
            QToolBar {
                background-color: #2D2D2D;
                border: none;
                border-bottom: 1px solid #3D3D3D;
                spacing: 5px;
                padding: 3px;
            }
            QToolBar QToolButton {
                background-color: transparent;
                color: #E0E0E0;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font: 11px "Microsoft YaHei";
            }
            QToolBar QToolButton:hover {
                background-color: #4A4A4A;
            }
            QToolBar QToolButton:pressed {
                background-color: #4A6A9A;
            }
            
            /* 状态栏 */
            QStatusBar {
                background-color: #2D2D2D;
                color: #A0A0A0;
                border-top: 1px solid #3D3D3D;
                font: 11px "Microsoft YaHei";
            }
            
            /* 停靠窗口 */
            QDockWidget {
                titlebar-close-icon: url(none);
                titlebar-normal-icon: url(none);
            }
            QDockWidget::title {
                background-color: #2D2D2D;
                color: #E0E0E0;
                padding: 6px;
                font: bold 12px "Microsoft YaHei";
                border-bottom: 1px solid #3D3D3D;
            }
            QDockWidget::close-button, QDockWidget::float-button {
                background-color: transparent;
                border-radius: 2px;
            }
            QDockWidget::close-button:hover, QDockWidget::float-button:hover {
                background-color: #4A4A4A;
            }
            
            /* 树形控件 */
            QTreeWidget {
                background-color: #252526;
                color: #E0E0E0;
                border: none;
                font: 11px "Microsoft YaHei";
                outline: 0;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #2A2D2E;
            }
            QTreeWidget::item:selected {
                background-color: #4A6A9A;
            }
            
            /* 标签页 */
            QTabWidget::pane {
                background-color: #1E1E1E;
                border: 1px solid #3D3D3D;
                border-radius: 0px;
            }
            QTabBar::tab {
                background-color: #2D2D2D;
                color: #A0A0A0;
                padding: 8px 20px;
                font: 11px "Microsoft YaHei";
            }
            QTabBar::tab:selected {
                background-color: #4A6A9A;
                color: #FFFFFF;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3D3D3D;
                color: #E0E0E0;
            }
            
            /* 分割器 */
            QSplitter::handle {
                background-color: #3D3D3D;
                width: 2px;
                height: 2px;
            }
            
            /* 滚动条 */
            QScrollBar:vertical {
                background-color: #1E1E1E;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #4A4A4A;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5A5A5A;
            }
            QScrollBar:horizontal {
                background-color: #1E1E1E;
                height: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background-color: #4A4A4A;
                border-radius: 5px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #5A5A5A;
            }
            
            /* 按钮 */
            QPushButton {
                background-color: #4A6A9A;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font: 11px "Microsoft YaHei";
            }
            QPushButton:hover {
                background-color: #5A7AAA;
            }
            QPushButton:pressed {
                background-color: #3A5A8A;
            }
            
            /* 分组框 */
            QGroupBox {
                color: #E0E0E0;
                font: bold 11px "Microsoft YaHei";
                border: 1px solid #3D3D3D;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            
            /* 标签 */
            QLabel {
                color: #E0E0E0;
                font: 11px "Microsoft YaHei";
            }
            
            /* 输入框 */
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #2D2D2D;
                color: #E0E0E0;
                border: 1px solid #3D3D3D;
                border-radius: 3px;
                padding: 4px;
                font: 11px "Microsoft YaHei";
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border-color: #4A6A9A;
            }
            
            /* 滑块 */
            QSlider::groove:horizontal {
                background-color: #3D3D3D;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background-color: #4A6A9A;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background-color: #5A7AAA;
            }
        """)

    def _setup_central_widget(self):
        """设置中心区域"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # 左侧面板
        left_panel = self._create_left_panel()
        self.main_splitter.addWidget(left_panel)

        # 中间：节点编辑器（修复：只传递 event_bus）
        self.node_editor = NodeEditorWidget(self.event_bus)  # 移除 workflow 参数
        self.main_splitter.addWidget(self.node_editor)

        # 右侧面板
        right_panel = self._create_right_panel()
        self.main_splitter.addWidget(right_panel)

        self.main_splitter.setSizes([280, 700, 320])

    def _create_left_panel(self):
        """创建左侧面板（流程树 + 节点工具箱）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 流程管理标签页
        self.left_tab = QTabWidget()
        self.left_tab.setStyleSheet("""
            QTabWidget::pane { background-color: #252526; border: none; }
        """)

        # 流程树
        self.flow_tree = self._create_flow_tree()
        self.left_tab.addTab(self.flow_tree, "📁 流程管理")

        # 节点工具箱
        self.toolbox_widget = self._create_toolbox_widget()
        self.left_tab.addTab(self.toolbox_widget, "🔧 节点工具箱")

        layout.addWidget(self.left_tab)

        return panel

    def _create_flow_tree(self):
        """创建流程树"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # 工具栏
        flow_toolbar = QHBoxLayout()
        new_flow_btn = QPushButton("新建流程")
        new_flow_btn.setFixedSize(80, 28)
        new_flow_btn.clicked.connect(self._on_new_flow)
        flow_toolbar.addWidget(new_flow_btn)

        copy_flow_btn = QPushButton("复制流程")
        copy_flow_btn.setFixedSize(80, 28)
        flow_toolbar.addWidget(copy_flow_btn)

        delete_flow_btn = QPushButton("删除流程")
        delete_flow_btn.setFixedSize(80, 28)
        flow_toolbar.addWidget(delete_flow_btn)

        flow_toolbar.addStretch()
        layout.addLayout(flow_toolbar)

        # 流程树
        self.flow_tree_widget = QTreeWidget()
        self.flow_tree_widget.setHeaderHidden(True)
        self.flow_tree_widget.setIndentation(16)

        # 根流程
        root_item = QTreeWidgetItem(["主流程"])
        root_item.setIcon(0, self._create_icon("🎯"))
        self.flow_tree_widget.addTopLevelItem(root_item)

        # 子流程
        sub_item = QTreeWidgetItem(["子流程1"])
        sub_item.setIcon(0, self._create_icon("📄"))
        root_item.addChild(sub_item)

        self.flow_tree_widget.expandAll()
        layout.addWidget(self.flow_tree_widget)

        return widget

    def _create_toolbox_widget(self):
        """创建节点工具箱"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # 搜索框
        search_box = QLineEdit()
        search_box.setPlaceholderText("🔍 搜索节点...")
        search_box.textChanged.connect(self._on_search_nodes)
        layout.addWidget(search_box)

        # 节点树
        self.node_tree = QTreeWidget()
        self.node_tree.setHeaderHidden(True)
        self.node_tree.setDragEnabled(True)
        self.node_tree.setIndentation(12)

        # 按分类添加节点
        categories = self.node_registry.get_categories()
        for category, nodes in sorted(categories.items()):
            category_item = QTreeWidgetItem([category])
            category_item.setIcon(0, self._create_icon("📁"))
            category_item.setExpanded(True)

            for node_name in sorted(nodes):
                node_item = QTreeWidgetItem([node_name])
                node_item.setData(0, Qt.UserRole, node_name)
                node_item.setIcon(0, self._create_icon("🔘"))
                node_item.setFlags(node_item.flags() | Qt.ItemIsDragEnabled)
                category_item.addChild(node_item)

            self.node_tree.addTopLevelItem(category_item)

        layout.addWidget(self.node_tree)

        return widget

    def _create_right_panel(self):
        """创建右侧面板（输出 + 图像）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 右侧标签页
        self.right_tab = QTabWidget()

        # 图像显示标签页
        self.image_viewer = ImageViewer(self.event_bus)
        self.right_tab.addTab(self.image_viewer, "🖼️ 图像显示")

        # 属性面板标签页
        self.property_panel = PropertyPanel(self.event_bus)
        self.right_tab.addTab(self.property_panel, "⚙️ 属性配置")

        # 输出结果标签页
        self.result_widget = self._create_result_widget()
        self.right_tab.addTab(self.result_widget, "📊 输出结果")

        layout.addWidget(self.right_tab)

        return panel

    def _create_result_widget(self):
        """创建结果输出控件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # 结果树
        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderHidden(True)
        self.result_tree.setIndentation(16)
        layout.addWidget(self.result_tree)

        return widget

    def _create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 左侧状态信息
        self.status_label = QLabel("✅ 就绪")
        self.status_bar.addWidget(self.status_label)

        self.status_bar.addWidget(self._create_separator())

        # 节点计数
        self.node_count_label = QLabel("📦 节点: 0")
        self.status_bar.addWidget(self.node_count_label)

        self.status_bar.addWidget(self._create_separator())

        # 流程状态
        self.flow_status_label = QLabel("🔄 未执行")
        self.status_bar.addWidget(self.flow_status_label)

        self.status_bar.addWidget(self._create_separator())

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addWidget(self.progress_bar)

        self.status_bar.addPermanentWidget(self._create_separator())

        # 右侧信息
        self.version_label = QLabel("版本 v1.0.0")
        self.status_bar.addPermanentWidget(self.version_label)

        # 订阅事件更新状态
        self.event_bus.subscribe(EventType.WORKFLOW_NODE_ADDED, self._on_node_count_changed)
        self.event_bus.subscribe(EventType.WORKFLOW_NODE_REMOVED, self._on_node_count_changed)
        self.event_bus.subscribe(EventType.WORKFLOW_EXECUTED, self._on_workflow_executed_status)

    def _create_separator(self):
        """创建分隔符"""
        label = QLabel("|")
        label.setStyleSheet("color: #3D3D3D; padding: 0 5px;")
        return label

    def _create_icon(self, text):
        """创建简单图标（使用文本）"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        return QIcon(pixmap)

    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = self._create_file_menu()
        menubar.addMenu(file_menu)

        # 编辑菜单
        edit_menu = self._create_edit_menu()
        menubar.addMenu(edit_menu)

        # 视图菜单
        view_menu = self._create_view_menu()
        menubar.addMenu(view_menu)

        # 运行菜单
        run_menu = self._create_run_menu()
        menubar.addMenu(run_menu)

        # 工具菜单
        tools_menu = self._create_tools_menu()
        menubar.addMenu(tools_menu)

        # 帮助菜单
        help_menu = self._create_help_menu()
        menubar.addMenu(help_menu)

    def _create_file_menu(self):
        """创建文件菜单"""
        menu = QMenu("文件(&F)")

        new_action = QAction("新建项目(&N)", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._on_new_project)
        menu.addAction(new_action)

        open_action = QAction("打开项目(&O)...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._on_open_project)
        menu.addAction(open_action)

        save_action = QAction("保存项目(&S)", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._on_save_project)
        menu.addAction(save_action)

        save_as_action = QAction("另存为(&A)...", self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(self._on_save_as_project)
        menu.addAction(save_as_action)

        menu.addSeparator()

        import_action = QAction("导入流程...", self)
        menu.addAction(import_action)

        export_action = QAction("导出流程...", self)
        menu.addAction(export_action)

        menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        menu.addAction(exit_action)

        return menu

    def _create_edit_menu(self):
        """创建编辑菜单"""
        menu = QMenu("编辑(&E)")

        undo_action = QAction("撤销(&U)", self)
        undo_action.setShortcut(QKeySequence.Undo)
        menu.addAction(undo_action)

        redo_action = QAction("重做(&R)", self)
        redo_action.setShortcut(QKeySequence.Redo)
        menu.addAction(redo_action)

        menu.addSeparator()

        cut_action = QAction("剪切(&T)", self)
        cut_action.setShortcut(QKeySequence.Cut)
        menu.addAction(cut_action)

        copy_action = QAction("复制(&C)", self)
        copy_action.setShortcut(QKeySequence.Copy)
        menu.addAction(copy_action)

        paste_action = QAction("粘贴(&P)", self)
        paste_action.setShortcut(QKeySequence.Paste)
        menu.addAction(paste_action)

        delete_action = QAction("删除(&D)", self)
        delete_action.setShortcut(QKeySequence.Delete)
        menu.addAction(delete_action)

        menu.addSeparator()

        select_all_action = QAction("全选(&A)", self)
        select_all_action.setShortcut(QKeySequence.SelectAll)
        menu.addAction(select_all_action)

        return menu

    def _create_view_menu(self):
        """创建视图菜单"""
        menu = QMenu("视图(&V)")

        reset_view_action = QAction("重置视图(&R)", self)
        reset_view_action.setShortcut(QKeySequence("Ctrl+0"))
        reset_view_action.triggered.connect(self._on_reset_view)
        menu.addAction(reset_view_action)

        zoom_in_action = QAction("放大(&I)", self)
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        menu.addAction(zoom_in_action)

        zoom_out_action = QAction("缩小(&O)", self)
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        menu.addAction(zoom_out_action)

        menu.addSeparator()

        show_toolbox_action = QAction("显示工具箱(&T)", self)
        show_toolbox_action.setCheckable(True)
        show_toolbox_action.setChecked(True)
        menu.addAction(show_toolbox_action)

        show_property_action = QAction("显示属性面板(&P)", self)
        show_property_action.setCheckable(True)
        show_property_action.setChecked(True)
        menu.addAction(show_property_action)

        show_log_action = QAction("显示日志(&L)", self)
        show_log_action.setCheckable(True)
        show_log_action.setChecked(True)
        menu.addAction(show_log_action)

        return menu

    def _create_run_menu(self):
        """创建运行菜单"""
        menu = QMenu("运行(&R)")

        run_action = QAction("执行(&E)", self)
        run_action.setShortcut(QKeySequence("F5"))
        run_action.triggered.connect(self._on_execute_workflow)
        menu.addAction(run_action)

        run_once_action = QAction("单步执行(&S)", self)
        run_once_action.setShortcut(QKeySequence("F10"))
        menu.addAction(run_once_action)

        pause_action = QAction("暂停(&P)", self)
        pause_action.setShortcut(QKeySequence("F6"))
        menu.addAction(pause_action)

        stop_action = QAction("停止(&T)", self)
        stop_action.setShortcut(QKeySequence("F7"))
        menu.addAction(stop_action)

        menu.addSeparator()

        continuous_run_action = QAction("连续执行(&C)", self)
        continuous_run_action.setCheckable(True)
        menu.addAction(continuous_run_action)

        return menu

    def _create_tools_menu(self):
        """创建工具菜单"""
        menu = QMenu("工具(&T)")

        camera_action = QAction("相机配置(&C)...", self)
        menu.addAction(camera_action)

        calibration_action = QAction("标定工具(&L)...", self)
        menu.addAction(calibration_action)

        menu.addSeparator()

        plugin_action = QAction("插件管理(&P)...", self)
        menu.addAction(plugin_action)

        options_action = QAction("选项(&O)...", self)
        menu.addAction(options_action)

        return menu

    def _create_help_menu(self):
        """创建帮助菜单"""
        menu = QMenu("帮助(&H)")

        doc_action = QAction("帮助文档(&D)", self)
        doc_action.setShortcut(QKeySequence.HelpContents)
        menu.addAction(doc_action)

        menu.addSeparator()

        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._on_about)
        menu.addAction(about_action)

        return menu

    def _create_tool_bars(self):
        """创建工具栏"""
        # 主工具栏
        main_toolbar = QToolBar("主工具栏")
        main_toolbar.setMovable(False)
        self.addToolBar(main_toolbar)

        # 文件操作
        new_btn = QToolButton()
        new_btn.setText("新建")
        new_btn.clicked.connect(self._on_new_project)
        main_toolbar.addWidget(new_btn)

        open_btn = QToolButton()
        open_btn.setText("打开")
        open_btn.clicked.connect(self._on_open_project)
        main_toolbar.addWidget(open_btn)

        save_btn = QToolButton()
        save_btn.setText("保存")
        save_btn.clicked.connect(self._on_save_project)
        main_toolbar.addWidget(save_btn)

        main_toolbar.addSeparator()

        # 运行控制
        run_btn = QToolButton()
        run_btn.setText("▶ 执行")
        run_btn.clicked.connect(self._on_execute_workflow)
        main_toolbar.addWidget(run_btn)

        pause_btn = QToolButton()
        pause_btn.setText("⏸ 暂停")
        main_toolbar.addWidget(pause_btn)

        stop_btn = QToolButton()
        stop_btn.setText("⏹ 停止")
        main_toolbar.addWidget(stop_btn)

        main_toolbar.addSeparator()

        # 调试工具
        run_once_btn = QToolButton()
        run_once_btn.setText("单步")
        main_toolbar.addWidget(run_once_btn)

        # 分隔线
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        main_toolbar.addWidget(spacer)

        # 状态指示器
        self.status_indicator = QLabel("● 空闲")
        self.status_indicator.setStyleSheet("color: #4CAF50; padding: 0 10px;")
        main_toolbar.addWidget(self.status_indicator)

    def _create_dock_panels(self):
        """创建停靠面板"""
        # 日志面板
        self.log_panel = LogPanel(self.event_bus)
        log_dock = QDockWidget("📋 输出日志", self)
        log_dock.setWidget(self.log_panel)
        log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, log_dock)

        # 缩略图导航
        self._create_navigation_dock()

    def _create_navigation_dock(self):
        """创建缩略图导航停靠窗口"""
        nav_dock = QDockWidget("🗺️ 导航", self)
        nav_dock.setAllowedAreas(Qt.RightDockWidgetArea)

        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)

        # 缩略图视图
        self.thumbnail_view = QLabel()
        self.thumbnail_view.setFixedSize(200, 150)
        self.thumbnail_view.setStyleSheet("background-color: #252526; border: 1px solid #3D3D3D;")
        self.thumbnail_view.setAlignment(Qt.AlignCenter)
        self.thumbnail_view.setText("缩略图")
        nav_layout.addWidget(self.thumbnail_view)

        nav_dock.setWidget(nav_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, nav_dock)

    def _subscribe_events(self):
        """订阅事件"""
        self.event_bus.subscribe(EventType.LOG_MESSAGE, self._on_log_message)
        self.event_bus.subscribe(EventType.WORKFLOW_EXECUTED, self._on_workflow_executed)
        self.event_bus.subscribe(EventType.PROJECT_LOADED, self._on_project_loaded)
        self.event_bus.subscribe(EventType.PROJECT_SAVED, self._on_project_saved)

    def _on_new_project(self):
        """新建项目"""
        if self._confirm_discard_changes():
            self.workflow.clear()
            self.property_panel.clear()
            self.image_viewer.clear()
            self.status_label.setText("✅ 已创建新项目")
            self.status_bar.showMessage("新项目已创建", 2000)

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
                self.status_label.setText(f"✅ 已加载项目: {os.path.basename(filepath)}")
                self.status_bar.showMessage(f"项目加载成功: {os.path.basename(filepath)}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载项目失败: {str(e)}")

    def _on_save_project(self):
        """保存项目"""
        if self.workflow.project_path:
            self.workflow.save(self.workflow.project_path)
            self.status_label.setText(f"✅ 已保存: {os.path.basename(self.workflow.project_path)}")
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
            self.status_label.setText(f"✅ 已保存: {os.path.basename(filepath)}")

    def _on_execute_workflow(self):
        """执行工作流"""
        if len(self.workflow.nodes) == 0:
            QMessageBox.information(self, "提示", "工作流中没有节点")
            return

        self.status_label.setText("🔄 正在执行...")
        self.status_indicator.setText("● 运行中")
        self.status_indicator.setStyleSheet("color: #FF9800; padding: 0 10px;")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 无限进度

        QApplication.processEvents()

        try:
            results = self.workflow.execute()

            # 更新状态
            self.status_label.setText("✅ 执行完成")
            self.status_indicator.setText("● 空闲")
            self.status_indicator.setStyleSheet("color: #4CAF50; padding: 0 10px;")
            self.flow_status_label.setText("✅ 执行成功")

            # 更新节点计数
            self.node_count_label.setText(f"📦 节点: {len(self.workflow.nodes)}")

            # 显示最终输出图像
            for node_id, outputs in results.items():
                for name, value in outputs.items():
                    if hasattr(value, 'shape'):  # 是图像
                        self.image_viewer.set_image(value, f"节点输出")
                        break

        except Exception as e:
            QMessageBox.critical(self, "执行错误", str(e))
            self.status_label.setText("❌ 执行失败")
            self.status_indicator.setText("● 错误")
            self.status_indicator.setStyleSheet("color: #F44336; padding: 0 10px;")
            self.flow_status_label.setText("❌ 执行失败")
        finally:
            self.progress_bar.setVisible(False)
            self.progress_bar.setRange(0, 100)

    def _on_reset_view(self):
        """重置视图"""
        self.node_editor.reset_view()
        self.status_bar.showMessage("视图已重置", 1500)

    def _on_about(self):
        """关于对话框"""
        QMessageBox.about(
            self,
            "关于 VisionFlow",
            "<h2>VisionFlow 视觉流程设计器</h2>"
            "<p><b>版本:</b> 1.0.0</p>"
            "<p><b>基于:</b> PySide6 + OpenCV</p>"
            "<p><b>功能:</b> 拖拽式构建视觉检测流程</p>"
            "<p><b>特点:</b></p>"
            "<ul>"
            "<li>可视化节点编辑器</li>"
            "<li>丰富的图像处理算子</li>"
            "<li>插件化扩展架构</li>"
            "<li>项目保存/加载</li>"
            "</ul>"
            "<p><b>版权:</b> © 2024 VisionFlow</p>"
        )

    def _on_new_flow(self):
        """新建流程"""
        self.event_bus.emit_log("INFO", "创建新流程")

    def _on_search_nodes(self, text):
        """搜索节点"""
        for i in range(self.node_tree.topLevelItemCount()):
            category_item = self.node_tree.topLevelItem(i)
            visible = False
            for j in range(category_item.childCount()):
                node_item = category_item.child(j)
                if text.lower() in node_item.text(0).lower():
                    node_item.setHidden(False)
                    visible = True
                else:
                    node_item.setHidden(True)
            category_item.setHidden(not visible)

    def _on_node_count_changed(self, event):
        """节点数量变化"""
        self.node_count_label.setText(f"📦 节点: {len(self.workflow.nodes)}")

    def _on_workflow_executed_status(self, event):
        """工作流执行状态更新"""
        self.flow_status_label.setText("✅ 执行成功")

    def _on_log_message(self, event: Event):
        """处理日志消息"""
        data = event.data
        level = data.get("level", "INFO")
        message = data.get("message", "")

        # 更新状态栏
        if level == "ERROR":
            self.status_label.setText(f"❌ {message[:50]}")
            self.status_indicator.setText("● 错误")
            self.status_indicator.setStyleSheet("color: #F44336; padding: 0 10px;")
        elif level == "WARNING":
            self.status_label.setText(f"⚠️ {message[:50]}")
        else:
            self.status_label.setText(f"✅ {message[:50]}")
            self.status_indicator.setText("● 空闲")
            self.status_indicator.setStyleSheet("color: #4CAF50; padding: 0 10px;")

    def _on_workflow_executed(self, event: Event):
        """工作流执行完成"""
        results = event.data.get("results", {})
        self.flow_status_label.setText(f"✅ 执行完成 ({len(results)}节点)")
        self.progress_bar.setVisible(False)

    def _on_project_loaded(self, event: Event):
        """项目加载完成"""
        self.node_editor.refresh_from_workflow()
        self.status_bar.showMessage("项目加载成功", 3000)

    def _on_project_saved(self, event: Event):
        """项目保存完成"""
        self.status_bar.showMessage("项目保存成功", 2000)

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

    def closeEvent(self, event):
        """关闭事件"""
        if self._confirm_discard_changes():
            event.accept()
        else:
            event.ignore()
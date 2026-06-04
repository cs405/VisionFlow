"""
主窗口 — WPF VisionMaster风格完整布局
├── 自定义标题栏 (TitleBar)
├── 菜单栏 + 工具栏
├── 左侧面板 (FlowTree + ToolboxPanel)
├── 中央区域 (节点编辑器 + 结果面板)
├── 右侧面板 (图像显示 + 属性配置)
├── 底部日志 (LogPanel Dock)
└── 状态栏
"""

import os

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMenuBar, QMenu, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QDockWidget, QTabWidget,
    QLabel, QPushButton, QApplication, QSizePolicy,
    QToolButton, QProgressBar, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize, QRect
from PySide6.QtGui import QAction, QKeySequence, QFont

from core.registry import NodeRegistry
from core.workflow import Workflow
from core.events import EventBus, Event, EventType

from .node_editor.editor_widget import NodeEditorWidget
from .property_panel import PropertyPanel
from .image_viewer import ImageViewer
from .log_panel import LogPanel
from .toolbox_panel import ToolboxPanel
from .flow_tree import FlowTree
from .result_panel import ResultPanel
from .title_bar import TitleBar
from .theme import Colors, Fonts, GLOBAL_STYLESHEET


class MainWindow(QMainWindow):
    """VisionFlow 主窗口 — WPF VisionMaster风格"""

    def __init__(self):
        super().__init__()

        # 核心组件
        self.event_bus = EventBus()
        self.node_registry = NodeRegistry()
        self.workflow = Workflow()

        # 设置无边框窗口 + 自定义标题栏
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self.setWindowTitle("VisionFlow - 智能视觉流程设计器")
        self.resize(1500, 900)
        self.setMinimumSize(1200, 700)

        # 应用全局样式
        self.setStyleSheet(GLOBAL_STYLESHEET)

        # 构建UI
        self._create_title_bar()
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_central_layout()
        self._create_bottom_dock()
        self._create_status_bar()
        self._subscribe_events()

        # 初始化完成
        self.event_bus.emit(Event(type=EventType.SYSTEM_INITIALIZED, data={}))
        self.event_bus.emit_log("INFO", "VisionFlow UI 启动完成")

    # ========== 标题栏 ==========

    def _create_title_bar(self):
        self.title_bar = TitleBar(self, "VisionFlow - 智能视觉流程设计器")
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize)
        self.title_bar.close_clicked.connect(self.close)

        # 将标题栏设置为菜单栏上方的widget
        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        title_layout.addWidget(self.title_bar)

        self.setMenuWidget(title_container)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ========== 菜单栏 ==========

    def _create_menu_bar(self):
        menubar = QMenuBar()
        menubar.setNativeMenuBar(False)  # 使用自定义菜单栏

        # 文件
        file_menu = menubar.addMenu("文件(&F)")
        file_menu.addAction("新建项目(&N)", self._on_new_project, QKeySequence.New)
        file_menu.addAction("打开项目(&O)...", self._on_open_project, QKeySequence.Open)
        file_menu.addAction("保存项目(&S)", self._on_save_project, QKeySequence.Save)
        file_menu.addAction("另存为(&A)...", self._on_save_as_project, QKeySequence("Ctrl+Shift+S"))
        file_menu.addSeparator()
        file_menu.addAction("退出(&X)", self.close, QKeySequence.Quit)

        # 编辑
        edit_menu = menubar.addMenu("编辑(&E)")
        edit_menu.addAction("撤销(&U)", None, QKeySequence.Undo)
        edit_menu.addAction("重做(&R)", None, QKeySequence.Redo)
        edit_menu.addSeparator()
        edit_menu.addAction("删除(&D)", None, QKeySequence.Delete)

        # 视图
        view_menu = menubar.addMenu("视图(&V)")
        view_menu.addAction("重置视图(&R)", self._on_reset_view, "Ctrl+0")
        view_menu.addAction("放大(&I)", None, QKeySequence.ZoomIn)
        view_menu.addAction("缩小(&O)", None, QKeySequence.ZoomOut)

        # 运行
        run_menu = menubar.addMenu("运行(&R)")
        run_menu.addAction("执行(&E)", self._on_execute_workflow, "F5")
        run_menu.addAction("单步执行(&S)", None, "F10")
        run_menu.addAction("停止(&T)", None, "F7")

        # 工具
        tools_menu = menubar.addMenu("工具(&T)")
        tools_menu.addAction("插件管理(&P)...", None)

        # 帮助
        help_menu = menubar.addMenu("帮助(&H)")
        help_menu.addAction("关于(&A)", self._on_about)

        self.setMenuBar(menubar)

    # ========== 工具栏 ==========

    def _create_tool_bar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))

        # 文件操作
        for text, handler, tip in [
            ("📄 新建", self._on_new_project, "新建项目"),
            ("📂 打开", self._on_open_project, "打开项目"),
            ("💾 保存", self._on_save_project, "保存项目"),
        ]:
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tip)
            btn.clicked.connect(handler)
            toolbar.addWidget(btn)

        toolbar.addSeparator()

        # 运行控制
        self.status_indicator = QLabel("● 空闲")
        self.status_indicator.setStyleSheet(f"color: {Colors.Green}; padding: 0 8px; font-weight: bold;")

        for text, handler, tip in [
            ("▶ 执行", self._on_execute_workflow, "执行工作流 (F5)"),
        ]:
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tip)
            btn.clicked.connect(handler)
            toolbar.addWidget(btn)

        # 弹性空间
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        toolbar.addWidget(self.status_indicator)
        self.addToolBar(toolbar)

    # ========== 中央布局 ==========

    def _create_central_layout(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 主分割器 (左-中-右)
        self.main_splitter = QSplitter(Qt.Horizontal)

        # === 左侧面板 ===
        left_panel = self._create_left_panel()
        self.main_splitter.addWidget(left_panel)

        # === 中央区域 (编辑器 + 底部结果面板) ===
        center_panel = self._create_center_panel()
        self.main_splitter.addWidget(center_panel)

        # === 右侧面板 ===
        right_panel = self._create_right_panel()
        self.main_splitter.addWidget(right_panel)

        self.main_splitter.setSizes([250, 800, 350])
        main_layout.addWidget(self.main_splitter)

    def _create_left_panel(self):
        """左侧面板: 流程管理 + 节点工具箱"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.left_tabs = QTabWidget()
        self.left_tabs.setDocumentMode(True)

        # 流程管理树
        self.flow_tree = FlowTree()
        self.flow_tree.flow_added.connect(self._on_add_flow)
        self.left_tabs.addTab(self.flow_tree, "流程")

        # 节点工具箱
        self.toolbox_panel = ToolboxPanel()
        self.left_tabs.addTab(self.toolbox_panel, "工具箱")

        layout.addWidget(self.left_tabs)
        return panel

    def _create_center_panel(self):
        """中央区域: 节点编辑器 + 结果面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 垂直分割器
        center_splitter = QSplitter(Qt.Vertical)

        # 节点编辑器
        self.node_editor = NodeEditorWidget(self.event_bus)
        center_splitter.addWidget(self.node_editor)

        # 底部结果面板
        self.result_panel = ResultPanel(self.event_bus)
        center_splitter.addWidget(self.result_panel)

        center_splitter.setSizes([550, 250])
        layout.addWidget(center_splitter)

        return panel

    def _create_right_panel(self):
        """右侧面板: 图像显示 + 属性配置"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.right_tabs = QTabWidget()
        self.right_tabs.setDocumentMode(True)

        # 图像显示
        self.image_viewer = ImageViewer(self.event_bus)
        self.right_tabs.addTab(self.image_viewer, "图像")

        # 属性面板
        self.property_panel = PropertyPanel(self.event_bus)
        self.right_tabs.addTab(self.property_panel, "属性")

        layout.addWidget(self.right_tabs)
        return panel

    # ========== 底部日志面板 ==========

    def _create_bottom_dock(self):
        self.log_panel = LogPanel(self.event_bus)

        log_dock = QDockWidget("输出日志", self)
        log_dock.setWidget(self.log_panel)
        log_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        log_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)

        self.addDockWidget(Qt.BottomDockWidgetArea, log_dock)

    # ========== 状态栏 ==========

    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 左侧: 状态信息
        self.status_msg_label = QLabel("就绪")
        self.status_msg_label.setStyleSheet(f"color: {Colors.Green}; padding: 0 8px;")
        self.status_bar.addWidget(self.status_msg_label)

        self.status_bar.addWidget(self._status_separator())

        # 节点计数
        self.node_count_label = QLabel("节点: 0")
        self.status_bar.addWidget(self.node_count_label)

        self.status_bar.addWidget(self._status_separator())

        # 流程状态
        self.flow_status_label = QLabel("未执行")
        self.status_bar.addWidget(self.flow_status_label)

        self.status_bar.addWidget(self._status_separator())

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(150)
        self.progress_bar.setVisible(False)
        self.status_bar.addWidget(self.progress_bar)

        self.status_bar.addPermanentWidget(self._status_separator())
        self.version_label = QLabel("v1.0.0")
        self.version_label.setStyleSheet(f"color: {Colors.ForegroundDim};")
        self.status_bar.addPermanentWidget(self.version_label)

    def _status_separator(self):
        sep = QLabel("|")
        sep.setStyleSheet(f"color: {Colors.Border}; padding: 0 5px;")
        return sep

    # ========== 事件订阅 ==========

    def _subscribe_events(self):
        self.event_bus.subscribe(EventType.LOG_MESSAGE, self._on_log_message)
        self.event_bus.subscribe(EventType.WORKFLOW_EXECUTED, self._on_workflow_executed)
        self.event_bus.subscribe(EventType.WORKFLOW_NODE_ADDED, self._on_nodes_changed)
        self.event_bus.subscribe(EventType.WORKFLOW_NODE_REMOVED, self._on_nodes_changed)
        self.event_bus.subscribe(EventType.PROJECT_LOADED, self._on_project_loaded)
        self.event_bus.subscribe(EventType.PROJECT_SAVED, self._on_project_saved)

    def _on_log_message(self, event: Event):
        data = event.data
        level = data.get("level", "INFO")
        message = data.get("message", "")

        if level == "ERROR":
            self.status_msg_label.setStyleSheet(f"color: {Colors.Red}; padding: 0 8px;")
            self.status_msg_label.setText(f"❌ {message[:60]}")
            self.status_indicator.setText("● 错误")
            self.status_indicator.setStyleSheet(f"color: {Colors.Red}; padding: 0 8px; font-weight: bold;")
        elif level == "WARNING":
            self.status_msg_label.setStyleSheet(f"color: {Colors.Orange}; padding: 0 8px;")
            self.status_msg_label.setText(f"⚠ {message[:60]}")
        else:
            self.status_msg_label.setStyleSheet(f"color: {Colors.Green}; padding: 0 8px;")
            self.status_msg_label.setText(message[:60])
            self.status_indicator.setText("● 空闲")
            self.status_indicator.setStyleSheet(f"color: {Colors.Green}; padding: 0 8px; font-weight: bold;")

    def _on_workflow_executed(self, event: Event):
        results = event.data.get("results", {})
        self.flow_status_label.setText(f"执行完成 ({len(results)}节点)")
        self.flow_status_label.setStyleSheet(f"color: {Colors.Green};")
        self.progress_bar.setVisible(False)
        self.status_indicator.setText("● 空闲")
        self.status_indicator.setStyleSheet(f"color: {Colors.Green}; padding: 0 8px; font-weight: bold;")
        self.node_count_label.setText(f"节点: {len(self.workflow.nodes)}")

    def _on_nodes_changed(self, event: Event):
        self.node_count_label.setText(f"节点: {len(self.workflow.nodes)}")

    def _on_project_loaded(self, event: Event):
        path = event.data.get("path", "")
        self.node_editor.refresh_from_workflow()
        self.status_bar.showMessage(f"项目加载: {os.path.basename(path)}", 3000)

    def _on_project_saved(self, event: Event):
        path = event.data.get("path", "")
        self.status_bar.showMessage(f"项目保存: {os.path.basename(path)}", 2000)

    # ========== 操作处理 ==========

    def _on_new_project(self):
        if self._confirm_discard():
            self.workflow.clear()
            self.node_editor.clear_scene()
            self.image_viewer.clear()
            self.property_panel.clear()
            self.result_panel.clear_history()
            self.status_bar.showMessage("新项目已创建", 2000)

    def _on_open_project(self):
        if not self._confirm_discard():
            return
        filepath, _ = QFileDialog.getOpenFileName(
            self, "打开项目", "", "VisionFlow项目 (*.vfproj);;JSON文件 (*.json)"
        )
        if filepath:
            try:
                self.workflow.load(filepath)
                self.node_editor.refresh_from_workflow()
                self.status_bar.showMessage(f"项目加载: {os.path.basename(filepath)}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载项目失败:\n{str(e)}")

    def _on_save_project(self):
        if self.workflow.project_path:
            self.workflow.save(self.workflow.project_path)
            self.status_bar.showMessage(f"已保存: {os.path.basename(self.workflow.project_path)}", 2000)
        else:
            self._on_save_as_project()

    def _on_save_as_project(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存项目", "", "VisionFlow项目 (*.vfproj)"
        )
        if filepath:
            if not filepath.endswith('.vfproj'):
                filepath += '.vfproj'
            self.workflow.save(filepath)
            self.status_bar.showMessage(f"已保存: {os.path.basename(filepath)}", 2000)

    def _on_execute_workflow(self):
        if len(self.workflow.nodes) == 0:
            QMessageBox.information(self, "提示", "工作流中没有节点，请先添加节点。")
            return

        self.status_indicator.setText("● 运行中")
        self.status_indicator.setStyleSheet(f"color: {Colors.Orange}; padding: 0 8px; font-weight: bold;")
        self.flow_status_label.setText("执行中...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        QApplication.processEvents()

        try:
            results = self.workflow.execute()
            self.flow_status_label.setText(f"执行完成 ({len(results)}节点)")
            self.flow_status_label.setStyleSheet(f"color: {Colors.Green};")
            self.status_indicator.setText("● 空闲")
            self.status_indicator.setStyleSheet(f"color: {Colors.Green}; padding: 0 8px; font-weight: bold;")

            # 显示输出图像
            for outputs in results.values():
                for value in outputs.values():
                    if hasattr(value, 'shape') and len(value.shape) in [2, 3]:
                        self.image_viewer.set_image(value, "执行结果")
                        self.right_tabs.setCurrentWidget(self.image_viewer)
                        break
        except Exception as e:
            QMessageBox.critical(self, "执行错误", str(e))
            self.flow_status_label.setText("执行失败")
            self.flow_status_label.setStyleSheet(f"color: {Colors.Red};")
            self.status_indicator.setText("● 错误")
            self.status_indicator.setStyleSheet(f"color: {Colors.Red}; padding: 0 8px; font-weight: bold;")
        finally:
            self.progress_bar.setVisible(False)
            self.progress_bar.setRange(0, 100)

    def _on_reset_view(self):
        self.node_editor.reset_view()
        self.status_bar.showMessage("视图已重置", 1500)

    def _on_add_flow(self):
        self.node_editor.add_flow_tab(f"流程{len(self.node_editor.workflows) + 1}")
        self.status_bar.showMessage("新流程已添加", 1500)

    def _on_about(self):
        QMessageBox.about(
            self, "关于 VisionFlow",
            "<h3 style='color:#4A6A9A;'>VisionFlow 视觉流程设计器</h3>"
            "<p><b>版本:</b> 1.0.0</p>"
            "<p><b>基于:</b> PySide6 + OpenCV + NumPy</p>"
            "<p>拖拽式构建视觉检测流程的可视化工具。</p>"
            "<hr>"
            "<p><b>特性:</b></p>"
            "<ul>"
            "<li>可视化节点编辑器 (WPF VisionMaster风格)</li>"
            "<li>丰富的图像处理算子</li>"
            "<li>插件化扩展架构</li>"
            "<li>多Tab流程管理</li>"
            "<li>项目保存/加载</li>"
            "<li>实时图像预览</li>"
            "</ul>"
        )

    def _confirm_discard(self) -> bool:
        if len(self.workflow.nodes) > 0:
            reply = QMessageBox.question(
                self, "确认",
                "当前工作流未保存，是否继续？",
                QMessageBox.Yes | QMessageBox.No
            )
            return reply == QMessageBox.Yes
        return True

    def closeEvent(self, event):
        if self._confirm_discard():
            self.event_bus.emit(Event(type=EventType.SYSTEM_SHUTDOWN, data={}))
            event.accept()
        else:
            event.ignore()

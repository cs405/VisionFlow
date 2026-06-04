"""
VisionFlow 主窗口 — WPF MainWindow.xaml 精确还原

布局结构(WPF对应):
  CaptionTemplate → TitleBar (85px, 菜单+工具栏)
  Left GridSplitterBox → FlowResourcePanel
  Center Grid + TabControl → EditorWidget + ResultPanel
  Right GridSplitterBox → ImageViewer + PropertyPanel
  StatusBar(操作消息) → 底部QStatusBar
  StatusBar(流程消息) → 嵌入式状态标签
"""

import os

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QDockWidget, QStatusBar, QLabel, QProgressBar,
    QFileDialog, QMessageBox, QApplication, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QAction, QKeySequence, QFont

from core.registry import NodeRegistry
from core.workflow import Workflow
from core.events import EventBus, Event, EventType

from .title_bar import TitleBar
from .flow_resource_panel import FlowResourcePanel
from .node_editor.editor_widget import NodeEditorWidget
from .result_panel import ResultPanel
from .image_viewer import ImageViewer
from .property_panel import PropertyPanel
from .log_panel import LogPanel
from .theme import Colors, GLOBAL_STYLESHEET


class MainWindow(QMainWindow):
    """VisionFlow 主窗口 — WPF VisionMaster风格"""

    def __init__(self):
        super().__init__()

        # 核心
        self.event_bus = EventBus()
        self.workflow = Workflow()

        # 无边框窗口
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("VisionMaster-OpenCV")
        self.resize(1400, 850)
        self.setMinimumSize(1100, 650)

        self.setStyleSheet(GLOBAL_STYLESHEET)

        self._setup_ui()
        self._subscribe_events()

        self.event_bus.emit(Event(type=EventType.SYSTEM_INITIALIZED, data={}))
        self.event_bus.emit_log("INFO", "VisionFlow UI 启动完成")

    # ================================================================
    # UI构建 — 严格按WPF布局
    # ================================================================

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_vbox = QVBoxLayout()
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(0)

        # ===== 标题栏(85px, 嵌入菜单+工具栏+系统按钮) =====
        self.title_bar = TitleBar(self, self.event_bus, "VisionFlow")
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize)
        self.title_bar.close_clicked.connect(self.close)
        self.title_bar.new_project.connect(self._on_new_project)
        self.title_bar.open_project.connect(self._on_open_project)
        self.title_bar.save_project.connect(self._on_save_project)
        self.title_bar.edit_project.connect(lambda: None)
        self.title_bar.execute_workflow.connect(self._on_execute_workflow)
        self.title_bar.about_clicked.connect(self._on_about)
        main_vbox.addWidget(self.title_bar)

        # ===== 主内容区: 左-中-右 三栏 =====
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setHandleWidth(2)

        # --- 左侧面板: 流程资源 ---
        left_panel = self._build_left_panel()
        self.main_splitter.addWidget(left_panel)

        # --- 中间: 纵向分割(上=编辑器, 下=结果面板) ---
        center_panel = self._build_center_panel()
        self.main_splitter.addWidget(center_panel)

        # --- 右侧: 纵向分割(上=图像, 下=属性) ---
        right_panel = self._build_right_panel()
        self.main_splitter.addWidget(right_panel)

        self.main_splitter.setSizes([260, 780, 340])
        main_vbox.addWidget(self.main_splitter, 1)

        central.setLayout(main_vbox)

        # ===== 底部日志 Dock =====
        self._build_bottom_dock()

        # ===== 状态栏 =====
        self._build_status_bar()

    def _build_left_panel(self):
        """左侧: 流程资源面板"""
        wrapper = QWidget()
        wrapper.setStyleSheet(f"background-color: {Colors.BackgroundDark};")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.flow_resource = FlowResourcePanel()
        layout.addWidget(self.flow_resource)
        return wrapper

    def _build_center_panel(self):
        """中间: QSplitter(纵向) — 上=编辑器, 下=结果面板"""
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        center_splitter = QSplitter(Qt.Vertical)
        center_splitter.setHandleWidth(2)

        # 上: 节点编辑器(多Tab流程图)
        self.node_editor = NodeEditorWidget(self.event_bus)
        center_splitter.addWidget(self.node_editor)

        # 下: 结果面板(历史/模块/帮助) + 底部流程消息
        bottom_wrapper = QWidget()
        bottom_layout = QVBoxLayout(bottom_wrapper)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)

        self.result_panel = ResultPanel(self.event_bus)
        bottom_layout.addWidget(self.result_panel)

        # 流程消息状态栏(嵌入式)
        self.flow_msg_bar = QWidget()
        self.flow_msg_bar.setFixedHeight(24)
        self.flow_msg_bar.setStyleSheet(f"background-color: {Colors.BackgroundLight}; border-top: 1px solid {Colors.Border};")
        fmb_layout = QHBoxLayout(self.flow_msg_bar)
        fmb_layout.setContentsMargins(8, 2, 8, 2)
        fmb_layout.setSpacing(6)

        self.flow_state_icon = QLabel("●")
        self.flow_state_icon.setStyleSheet(f"color: {Colors.Green}; font-size: 12px; background: transparent;")
        fmb_layout.addWidget(self.flow_state_icon)

        self.flow_state_label = QLabel("空闲")
        self.flow_state_label.setStyleSheet(f"color: {Colors.ForegroundDim}; font: 10px 'Microsoft YaHei'; background: transparent;")
        fmb_layout.addWidget(self.flow_state_label)

        fmb_layout.addStretch()

        self.flow_time_label = QLabel("用时: 00:00:00")
        self.flow_time_label.setStyleSheet(f"color: {Colors.ForegroundDim}; font: 10px 'Microsoft YaHei'; background: transparent;")
        fmb_layout.addWidget(self.flow_time_label)

        bottom_layout.addWidget(self.flow_msg_bar)
        center_splitter.addWidget(bottom_wrapper)

        center_splitter.setSizes([500, 250])
        layout.addWidget(center_splitter)

        # 底部操作消息状态栏
        self.op_msg_bar = QWidget()
        self.op_msg_bar.setFixedHeight(24)
        self.op_msg_bar.setStyleSheet(f"background-color: {Colors.BackgroundLight}; border-top: 1px solid {Colors.Border};")
        omb_layout = QHBoxLayout(self.op_msg_bar)
        omb_layout.setContentsMargins(8, 2, 8, 2)
        omb_layout.setSpacing(6)

        self.op_state_icon = QLabel("●")
        self.op_state_icon.setStyleSheet(f"color: {Colors.Green}; font-size: 12px; background: transparent;")
        omb_layout.addWidget(self.op_state_icon)

        self.op_message_label = QLabel("就绪")
        self.op_message_label.setStyleSheet(f"color: {Colors.ForegroundDim}; font: 10px 'Microsoft YaHei'; background: transparent;")
        omb_layout.addWidget(self.op_message_label)

        self.op_node_name_label = QLabel("")
        self.op_node_name_label.setStyleSheet(f"color: {Colors.Accent}; font: 10px 'Microsoft YaHei'; background: transparent;")
        omb_layout.addWidget(self.op_node_name_label)

        omb_layout.addStretch()

        self.op_progress = QProgressBar()
        self.op_progress.setFixedWidth(120)
        self.op_progress.setFixedHeight(12)
        self.op_progress.setVisible(False)
        omb_layout.addWidget(self.op_progress)

        layout.addWidget(self.op_msg_bar)
        return wrapper

    def _build_right_panel(self):
        """右侧: QSplitter(纵向) — 上=图像显示, 下=属性配置"""
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setHandleWidth(2)

        self.image_viewer = ImageViewer(self.event_bus)
        right_splitter.addWidget(self.image_viewer)

        self.property_panel = PropertyPanel(self.event_bus)
        right_splitter.addWidget(self.property_panel)

        right_splitter.setSizes([400, 350])
        layout.addWidget(right_splitter)
        return wrapper

    def _build_bottom_dock(self):
        """底部日志面板"""
        self.log_panel = LogPanel(self.event_bus)
        log_dock = QDockWidget("输出日志", self)
        log_dock.setWidget(self.log_panel)
        log_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        log_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.BottomDockWidgetArea, log_dock)

    def _build_status_bar(self):
        """状态栏"""
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {Colors.BackgroundLight};
                color: {Colors.ForegroundDim};
                border-top: 1px solid {Colors.Border};
                font: 10px "Microsoft YaHei";
            }}
        """)
        self.setStatusBar(self.status_bar)

        self.status_msg_label = QLabel("✅ 就绪")
        self.status_bar.addWidget(self.status_msg_label)
        self.status_bar.addWidget(self._sep())

        self.node_count_label = QLabel("节点: 0")
        self.status_bar.addWidget(self.node_count_label)
        self.status_bar.addWidget(self._sep())

        self.workflow_status_label = QLabel("未执行")
        self.status_bar.addWidget(self.workflow_status_label)

        self.status_bar.addPermanentWidget(self._sep())
        self.status_bar.addPermanentWidget(QLabel("v1.0.0"))

    def _sep(self):
        s = QLabel("|")
        s.setStyleSheet(f"color: {Colors.Border}; padding: 0 4px; background: transparent;")
        return s

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ================================================================
    # 事件订阅
    # ================================================================

    def _subscribe_events(self):
        eb = self.event_bus
        eb.subscribe(EventType.LOG_MESSAGE, self._on_log_message)
        eb.subscribe(EventType.WORKFLOW_EXECUTED, self._on_workflow_executed)
        eb.subscribe(EventType.WORKFLOW_NODE_ADDED, self._on_nodes_changed)
        eb.subscribe(EventType.WORKFLOW_NODE_REMOVED, self._on_nodes_changed)
        eb.subscribe(EventType.NODE_SELECTED, self._on_node_selected)
        eb.subscribe(EventType.PROJECT_LOADED, self._on_project_loaded)
        eb.subscribe(EventType.PROJECT_SAVED, self._on_project_saved)

    def _on_log_message(self, event: Event):
        data = event.data
        level = data.get("level", "INFO")
        msg = data.get("message", "")

        if level == "ERROR":
            self.op_state_icon.setStyleSheet(f"color: {Colors.Red}; font-size: 12px; background: transparent;")
            self.op_message_label.setText(f"❌ {msg[:80]}")
            self.flow_state_icon.setStyleSheet(f"color: {Colors.Red}; font-size: 12px; background: transparent;")
        elif level == "WARNING":
            self.op_state_icon.setStyleSheet(f"color: {Colors.Orange}; font-size: 12px; background: transparent;")
            self.op_message_label.setText(f"⚠ {msg[:80]}")
        else:
            self.op_state_icon.setStyleSheet(f"color: {Colors.Green}; font-size: 12px; background: transparent;")
            self.op_message_label.setText(msg[:80])

    def _on_workflow_executed(self, event: Event):
        results = event.data.get("results", {})
        self.flow_state_label.setText("执行成功")
        self.flow_state_label.setStyleSheet(f"color: {Colors.Green}; font: 10px 'Microsoft YaHei'; background: transparent;")
        self.flow_state_icon.setStyleSheet(f"color: {Colors.Green}; font-size: 12px; background: transparent;")
        self.workflow_status_label.setText(f"执行完成 ({len(results)}节点)")
        self.node_count_label.setText(f"节点: {len(self.workflow.nodes)}")

        for outputs in results.values():
            for v in outputs.values():
                if hasattr(v, 'shape') and len(v.shape) in [2, 3]:
                    self.image_viewer.set_image(v, "执行结果")
                    break

    def _on_nodes_changed(self, event: Event):
        self.node_count_label.setText(f"节点: {len(self.workflow.nodes)}")

    def _on_node_selected(self, event: Event):
        meta = event.data.get("node_metadata", {})
        name = meta.get("name", "")
        self.op_node_name_label.setText(name)
        self.op_state_icon.setStyleSheet(f"color: {Colors.Blue}; font-size: 12px; background: transparent;")
        self.op_message_label.setText(f"选中: {name}")

    def _on_project_loaded(self, event: Event):
        path = event.data.get("path", "")
        self.title_bar.set_project_name(os.path.basename(path))
        self.node_editor.refresh_from_workflow(self.workflow.to_dict())
        self.status_bar.showMessage(f"项目加载: {os.path.basename(path)}", 3000)

    def _on_project_saved(self, event: Event):
        path = event.data.get("path", "")
        self.status_bar.showMessage(f"项目保存: {os.path.basename(path)}", 2000)

    # ================================================================
    # 操作处理
    # ================================================================

    def _on_new_project(self):
        if self._confirm_discard():
            self.workflow.clear()
            self.node_editor.clear_scene()
            self.image_viewer.clear()
            self.property_panel.clear()
            self.title_bar.set_project_name("未命名项目")
            self.flow_state_label.setText("空闲")
            self.status_bar.showMessage("新项目已创建", 2000)

    def _on_open_project(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "打开项目", "", "VisionFlow项目 (*.vfproj);;JSON (*.json)")
        if path:
            try:
                self.workflow.load(path)
                self.node_editor.refresh_from_workflow(self.workflow.to_dict())
                self.title_bar.set_project_name(os.path.basename(path))
                self.status_bar.showMessage(f"已加载: {os.path.basename(path)}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载项目失败:\n{e}")

    def _on_save_project(self):
        if self.workflow.project_path:
            self.workflow.save(self.workflow.project_path)
            self.status_bar.showMessage(f"已保存: {os.path.basename(self.workflow.project_path)}", 2000)
        else:
            path, _ = QFileDialog.getSaveFileName(self, "保存项目", "", "VisionFlow项目 (*.vfproj)")
            if path:
                if not path.endswith('.vfproj'):
                    path += '.vfproj'
                self.workflow.save(path)
                self.title_bar.set_project_name(os.path.basename(path))
                self.status_bar.showMessage(f"已保存: {os.path.basename(path)}", 2000)

    def _on_execute_workflow(self):
        if len(self.workflow.nodes) == 0:
            QMessageBox.information(self, "提示", "工作流中没有节点，请先添加节点。")
            return

        self.flow_state_icon.setStyleSheet(f"color: {Colors.Orange}; font-size: 12px; background: transparent;")
        self.flow_state_label.setText("运行中...")
        self.op_progress.setVisible(True)
        self.op_progress.setRange(0, 0)
        QApplication.processEvents()

        try:
            results = self.workflow.execute()
            self.flow_state_icon.setStyleSheet(f"color: {Colors.Green}; font-size: 12px; background: transparent;")
            self.flow_state_label.setText("执行成功")
            for outputs in results.values():
                for v in outputs.values():
                    if hasattr(v, 'shape') and len(v.shape) in [2, 3]:
                        self.image_viewer.set_image(v, "执行结果")
                        break
        except Exception as e:
            QMessageBox.critical(self, "执行错误", str(e))
            self.flow_state_icon.setStyleSheet(f"color: {Colors.Red}; font-size: 12px; background: transparent;")
            self.flow_state_label.setText("执行失败")
        finally:
            self.op_progress.setVisible(False)
            self.op_progress.setRange(0, 100)

    def _on_about(self):
        QMessageBox.about(self, "关于 VisionFlow",
            "<h3>VisionFlow 视觉流程设计器</h3>"
            "<p><b>版本:</b> 1.0.0 | <b>基于:</b> PySide6 + OpenCV</p>"
            "<p>WPF VisionMaster风格 — 拖拽式视觉检测流程设计</p>"
            "<hr><p><b>特性:</b> 可视化节点编辑 | 多流程管理 | 插件扩展 | 实时预览</p>")

    def _confirm_discard(self):
        if len(self.workflow.nodes) > 0:
            reply = QMessageBox.question(self, "确认", "当前工作流未保存，是否继续？",
                                         QMessageBox.Yes | QMessageBox.No)
            return reply == QMessageBox.Yes
        return True

    def closeEvent(self, event):
        if self._confirm_discard():
            self.event_bus.emit(Event(type=EventType.SYSTEM_SHUTDOWN, data={}))
            event.accept()
        else:
            event.ignore()

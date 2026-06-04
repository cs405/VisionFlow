"""Main window - full application layout matching WPF MainWindow.xaml.

Ported from:
  - H.App.VisionMaster.OpenCV/MainWindow.xaml(.cs)
  - H.Windows.Main/MainWindow

Layout (matching WPF):
  ┌─────────────────────────────────────────────────────────────────────┐
  │ [Logo] VisionFlow  文件 编辑 运行 系统 帮助         [_][□][×]      │ Custom Caption
  ├─────────────────────────────────────────────────────────────────────┤
  │ [新建][打开][保存] │ ▶运行 ■停止 │ [放大][缩小][适应]  项目: xxx  │ Command Bar
  ├──────────┬──────────────────────────────┬───────────────────────────┤
  │ 工具箱    │                              │ 流程图标签页 [×]          │
  │ (树形)   │    节点编辑器 / 图像查看器     │                           │
  │          │                              │ [属性|结果|帮助]          │
  │ 流程资源  │                              │                           │
  ├──────────┴──────────────────────────────┴───────────────────────────┤
  │ 图像源文件列表 (FlowResourcePanel)                                  │
  ├──────────┬──────────────────────────────┬───────────────────────────┤
  │ 历史结果  │      当前模块结果             │       帮助               │ Bottom Tabs
  ├──────────┴──────────────────────────────┴───────────────────────────┤
  │ ● 空闲 │ 状态消息                       │ 节点: 0 │ 15:30:00      │ Status Bar
  └─────────────────────────────────────────────────────────────────────┘
"""

import os
from datetime import datetime

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QSplitter, QAction, QActionGroup,
                              QToolBar, QStatusBar, QLabel, QTabWidget,
                              QMessageBox, QFileDialog, QApplication,
                              QPushButton, QFrame, QMenuBar, QMenu,
                              QToolButton, QSizePolicy, QShortcut)
from PyQt5.QtCore import Qt, QSize, QTimer, QSettings, pyqtSignal
from PyQt5.QtGui import QFont, QKeySequence

from core.node_base import NodeBase, VisionNodeData, SrcFilesVisionNodeData, ROINodeData
from core.workflow import WorkflowEngine
from core.project import project_service
from core.events import EventType, event_system
from core.registry import node_registry

from gui.theme import theme_manager
from gui.toolbox_panel import ToolboxPanel
from gui.property_panel import PropertyPanel
from gui.result_panel import ResultPanel
from gui.image_viewer import ImageViewerPanel
from gui.log_panel import LogPanel
from gui.flow_resource_panel import FlowResourcePanel
from gui.node_editor.editor_widget import DiagramEditorWidget


# ── Panel size persistence keys ──────────────────────────────────────────

class PanelState:
    """Persistent panel size/visibility state backed by QSettings."""
    SETTINGS_GROUP = "PanelState"

    def __init__(self):
        self._s = QSettings()

    def _key(self, name: str) -> str:
        return f"{self.SETTINGS_GROUP}/{name}"

    def get_int(self, name: str, default: int = 0) -> int:
        return int(self._s.value(self._key(name), default) or default)

    def set_int(self, name: str, value: int):
        self._s.setValue(self._key(name), value)

    def get_bool(self, name: str, default: bool = True) -> bool:
        v = self._s.value(self._key(name), default)
        if isinstance(v, str):
            return v.lower() == "true"
        return bool(v) if v is not None else default

    def set_bool(self, name: str, value: bool):
        self._s.setValue(self._key(name), "true" if value else "false")


_panel_state = PanelState()


# ── Collapsible Panel Container ──────────────────────────────────────────

class CollapsiblePanel(QWidget):
    """A panel that can be collapsed/expanded with a toggle button.

    Used for the left toolbox area, right property area, and bottom result area.
    """

    collapse_toggled = pyqtSignal(bool)  # True = expanded

    def __init__(self, title: str, content: QWidget, parent=None,
                 collapsible: bool = True, initially_expanded: bool = True):
        super().__init__(parent)
        self._title = title
        self._collapsible = collapsible
        self._expanded = initially_expanded
        self._content = content
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title_bar = QWidget()
        title_bar.setFixedHeight(30)
        title_bar.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(8, 0, 4, 0)
        tb_layout.setSpacing(4)

        lbl = QLabel(f"  {self._title}")
        lbl.setStyleSheet("color: #dcdcdc; font-size: 12px; font-weight: bold;")
        tb_layout.addWidget(lbl, 1)

        if self._collapsible:
            self._collapse_btn = QPushButton("◀" if self._expanded else "▶")
            self._collapse_btn.setFixedSize(22, 22)
            self._collapse_btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; color: #999; font-size: 10px; }
                QPushButton:hover { color: #dcdcdc; }
            """)
            self._collapse_btn.clicked.connect(self._toggle)
            tb_layout.addWidget(self._collapse_btn)

        layout.addWidget(title_bar)
        layout.addWidget(self._content, 1)
        self._content.setVisible(self._expanded)

    def _toggle(self):
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._collapse_btn.setText("◀" if self._expanded else "▶")
        self.collapse_toggled.emit(self._expanded)

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def expand(self):
        if not self._expanded:
            self._toggle()

    def collapse(self):
        if self._expanded:
            self._toggle()


# ── Main Window ──────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Main application window matching WPF VisionMaster layout."""

    def __init__(self):
        super().__init__()
        self._workflow: WorkflowEngine | None = None
        self._selected_node: NodeBase | None = None
        self._diagram_tabs: dict[str, WorkflowEngine] = {}  # multi-diagram support
        self._panel_state = _panel_state

        self._setup_window()
        self._setup_caption_bar()
        self._setup_command_bar()
        self._setup_content()
        self._setup_bottom_result_area()
        self._setup_status_bar()
        self._connect_events()
        self._restore_panel_state()

        # Clock timer for status bar
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)

        # Create initial empty project
        self._on_new_project()

    # ── Window Setup ─────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("VisionFlow - 视觉流程编辑器")
        self.resize(
            self._panel_state.get_int("window_width", 1400),
            self._panel_state.get_int("window_height", 900),
        )
        self.setMinimumSize(1000, 600)

        palette = theme_manager.colors.to_palette()
        self.setPalette(palette)
        self.setStyleSheet(theme_manager.get_stylesheet())

        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - self.width()) // 2,
                  (screen.height() - self.height()) // 2)

    def closeEvent(self, event):
        self._panel_state.set_int("window_width", self.width())
        self._panel_state.set_int("window_height", self.height())
        self._clock_timer.stop()
        super().closeEvent(event)

    # ── Custom Caption Bar ───────────────────────────────────────────

    def _setup_caption_bar(self):
        """Custom caption bar with logo, menus, and window controls.

        Ported from WPF MainWindow.CaptionTempate - integrates menu bar
        and project title into a unified caption area.
        """
        caption = QWidget()
        caption.setFixedHeight(36)
        caption.setStyleSheet("background: #1e1e1e; border-bottom: 1px solid #3f3f46;")
        cap_layout = QHBoxLayout(caption)
        cap_layout.setContentsMargins(8, 0, 0, 0)
        cap_layout.setSpacing(0)

        # App logo / icon placeholder
        logo = QLabel(" ◆")
        logo.setStyleSheet("color: #0078d4; font-size: 16px; padding: 0 6px;")
        cap_layout.addWidget(logo)

        # App title
        app_title = QLabel("VisionFlow")
        app_title.setStyleSheet("color: #dcdcdc; font-size: 13px; font-weight: bold; padding: 0 8px;")
        cap_layout.addWidget(app_title)

        # Menu bar embedded in caption
        self._caption_menu = QMenuBar()
        self._caption_menu.setStyleSheet("""
            QMenuBar { background: transparent; color: #dcdcdc; padding: 0; }
            QMenuBar::item { padding: 6px 12px; background: transparent; }
            QMenuBar::item:selected { background: #3e3e42; }
            QMenu { background: #2d2d30; color: #dcdcdc; border: 1px solid #505050; }
            QMenu::item { padding: 6px 30px 6px 16px; }
            QMenu::item:selected { background: #0078d4; }
            QMenu::separator { height: 1px; background: #505050; margin: 4px 10px; }
        """)
        self._build_menus()
        cap_layout.addWidget(self._caption_menu, 1)

        # Project title display in caption
        self._caption_project_label = QLabel("  新建项目  ")
        self._caption_project_label.setStyleSheet("color: #0078d4; font-size: 12px; padding: 0 12px;")
        cap_layout.addWidget(self._caption_project_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #505050;")
        sep.setFixedWidth(1)
        cap_layout.addWidget(sep)

        # Window control buttons
        win_ctrl_style = """
            QPushButton { background: transparent; border: none; color: #999; font-size: 12px;
                          padding: 0 14px; }
            QPushButton:hover { background: #3e3e42; color: #dcdcdc; }
            QPushButton#close_btn:hover { background: #e81123; color: white; }
        """
        min_btn = QPushButton("─")
        min_btn.setStyleSheet(win_ctrl_style)
        min_btn.clicked.connect(self.showMinimized)
        cap_layout.addWidget(min_btn)

        max_btn = QPushButton("□")
        max_btn.setStyleSheet(win_ctrl_style)
        max_btn.clicked.connect(self._toggle_maximize)
        cap_layout.addWidget(max_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("close_btn")
        close_btn.setStyleSheet(win_ctrl_style)
        close_btn.clicked.connect(self.close)
        cap_layout.addWidget(close_btn)

        # Set as menu bar (Qt renders it at the top)
        self.setMenuWidget(caption)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ── Menus ────────────────────────────────────────────────────────

    def _build_menus(self):
        """Build all menus matching the WPF version."""
        menubar = self._caption_menu

        # === 文件 (File) ===
        file_menu = menubar.addMenu("文件(&F)")

        new_act = QAction("新建项目(&N)", self)
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self._on_new_project)
        file_menu.addAction(new_act)

        open_act = QAction("打开项目(&O)...", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._on_open_project)
        file_menu.addAction(open_act)

        save_act = QAction("保存项目(&S)", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self._on_save_project)
        file_menu.addAction(save_act)

        save_as_act = QAction("另存为(&A)...", self)
        save_as_act.setShortcut("Ctrl+Shift+S")
        save_as_act.triggered.connect(self._on_save_as_project)
        file_menu.addAction(save_as_act)

        file_menu.addSeparator()

        # Recent projects
        self.recent_menu = file_menu.addMenu("最近的项目(&R)")
        self.recent_menu.aboutToShow.connect(self._update_recent_menu)

        file_menu.addSeparator()

        exit_act = QAction("退出(&X)", self)
        exit_act.setShortcut("Alt+F4")
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # === 编辑 (Edit) ===
        edit_menu = menubar.addMenu("编辑(&E)")

        undo_act = QAction("撤销(&U)", self)
        undo_act.setShortcut("Ctrl+Z")
        edit_menu.addAction(undo_act)

        redo_act = QAction("重做(&R)", self)
        redo_act.setShortcut("Ctrl+Y")
        edit_menu.addAction(redo_act)

        edit_menu.addSeparator()

        delete_act = QAction("删除选中(&D)", self)
        delete_act.setShortcut("Delete")
        edit_menu.addAction(delete_act)

        select_all_act = QAction("全选(&A)", self)
        select_all_act.setShortcut("Ctrl+A")
        edit_menu.addAction(select_all_act)

        # === 运行 (Run) ===
        run_menu = menubar.addMenu("运行(&R)")

        run_act = QAction("运行流程(&F)", self)
        run_act.setShortcut("F5")
        run_act.triggered.connect(self._on_run_workflow)
        run_menu.addAction(run_act)

        stop_act = QAction("停止(&S)", self)
        stop_act.setShortcut("Shift+F5")
        stop_act.triggered.connect(self._on_stop_workflow)
        run_menu.addAction(stop_act)

        step_act = QAction("单步执行(&T)", self)
        step_act.setShortcut("F10")
        run_menu.addAction(step_act)

        # === 系统 (System) ===
        sys_menu = menubar.addMenu("系统(&S)")

        settings_act = QAction("设置(&S)...", self)
        sys_menu.addAction(settings_act)

        theme_act = QAction("主题设置(&T)", self)
        sys_menu.addAction(theme_act)

        sys_menu.addSeparator()

        toggle_toolbox = QAction("切换工具箱", self)
        toggle_toolbox.setCheckable(True)
        toggle_toolbox.setChecked(True)
        sys_menu.addAction(toggle_toolbox)

        toggle_property = QAction("切换属性面板", self)
        toggle_property.setCheckable(True)
        toggle_property.setChecked(True)
        sys_menu.addAction(toggle_property)

        sys_menu.addSeparator()

        flow_list_act = QAction("流程功能列表", self)
        sys_menu.addAction(flow_list_act)

        # === 帮助 (Help) ===
        help_menu = menubar.addMenu("帮助(&H)")

        guide_act = QAction("使用指南(&G)", self)
        help_menu.addAction(guide_act)

        check_update_act = QAction("检查更新(&U)", self)
        help_menu.addAction(check_update_act)

        help_menu.addSeparator()

        about_act = QAction("关于 VisionFlow(&A)", self)
        about_act.triggered.connect(self._on_about)
        help_menu.addAction(about_act)

        contact_act = QAction("联系我们(&C)", self)
        help_menu.addAction(contact_act)

    def _update_recent_menu(self):
        self.recent_menu.clear()
        project_service.cleanup_recent_projects()

        if not project_service.recent_projects:
            empty = QAction("(无最近项目)", self)
            empty.setEnabled(False)
            self.recent_menu.addAction(empty)
            return

        for path in project_service.recent_projects:
            action = QAction(os.path.basename(path), self)
            action.setToolTip(path)
            action.triggered.connect(lambda checked, p=path: self._open_project(p))
            self.recent_menu.addAction(action)

        self.recent_menu.addSeparator()
        clear_act = QAction("清空最近项目", self)
        clear_act.triggered.connect(project_service.clear_recent_projects)
        self.recent_menu.addAction(clear_act)

    # ── Command Bar ──────────────────────────────────────────────────

    def _setup_command_bar(self):
        """Two-tier command bar matching the WPF toolbar area.

        Row 1: Project operations | Run controls | Zoom controls
        Row 2: [implied by first row + project name]
        """
        cmd = QWidget()
        cmd.setFixedHeight(34)
        cmd.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        cmd_layout = QHBoxLayout(cmd)
        cmd_layout.setContentsMargins(6, 0, 6, 0)
        cmd_layout.setSpacing(4)

        btn_style = """
            QPushButton { background: transparent; border: 1px solid #505050;
                          border-radius: 3px; padding: 3px 10px; color: #dcdcdc;
                          font-size: 11px; }
            QPushButton:hover { background: #3e3e42; border-color: #0078d4; }
            QPushButton:pressed { background: #0078d4; }
        """

        # Project ops
        for text, slot in [("新建", self._on_new_project),
                           ("打开", self._on_open_project),
                           ("保存", self._on_save_project)]:
            btn = QPushButton(text)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(slot)
            cmd_layout.addWidget(btn)

        self._add_cmd_sep(cmd_layout)

        # Run controls
        self._run_btn = QPushButton("▶ 运行")
        self._run_btn.setStyleSheet(btn_style.replace("#0078d4", "#4caf50"))
        self._run_btn.clicked.connect(self._on_run_workflow)
        cmd_layout.addWidget(self._run_btn)

        self._stop_btn = QPushButton("■ 停止")
        self._stop_btn.setStyleSheet(btn_style.replace("#0078d4", "#f44336"))
        self._stop_btn.clicked.connect(self._on_stop_workflow)
        cmd_layout.addWidget(self._stop_btn)

        self._add_cmd_sep(cmd_layout)

        # Zoom controls
        for text, slot in [("放大", lambda: self.image_panel.viewer.zoom_in()),
                           ("缩小", lambda: self.image_panel.viewer.zoom_out()),
                           ("适应", lambda: self.image_panel.viewer.fit_to_window()),
                           ("1:1", lambda: self.image_panel.viewer.zoom_to_100())]:
            btn = QPushButton(text)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(slot)
            cmd_layout.addWidget(btn)

        self._add_cmd_sep(cmd_layout)

        # Undo/Redo
        undo_btn = QPushButton("↩ 撤销")
        undo_btn.setStyleSheet(btn_style)
        cmd_layout.addWidget(undo_btn)

        redo_btn = QPushButton("↪ 重做")
        redo_btn.setStyleSheet(btn_style)
        cmd_layout.addWidget(redo_btn)

        cmd_layout.addStretch()

        # Context-sensitive project name
        self._cmd_project_label = QLabel("新建项目")
        self._cmd_project_label.setStyleSheet("color: #0078d4; font-size: 12px; font-weight: bold; padding: 0 8px;")
        cmd_layout.addWidget(self._cmd_project_label)

        self.addToolBar(Qt.TopToolBarArea, self._make_toolbar_from_widget(cmd, "命令栏"))

    def _add_cmd_sep(self, layout: QHBoxLayout):
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #505050;")
        sep.setFixedWidth(1)
        layout.addWidget(sep)

    def _make_toolbar_from_widget(self, widget: QWidget, name: str) -> QToolBar:
        toolbar = QToolBar(name)
        toolbar.setMovable(False)
        toolbar.addWidget(widget)
        return toolbar

    # ── Main Content ─────────────────────────────────────────────────

    def _setup_content(self):
        """Main content: horizontal splitter with left panels / center / right panels."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Top: Main horizontal splitter ──
        self._main_splitter = QSplitter(Qt.Horizontal)
        self._main_splitter.setHandleWidth(2)
        self._main_splitter.setStyleSheet("QSplitter::handle { background: #505050; }")

        # Left: Toolbox + Flow Resource tree
        self._left_tabs = QTabWidget()
        self._left_tabs.setFixedWidth(260)
        self._left_tabs.setStyleSheet(self._tab_style())

        self._toolbox = ToolboxPanel()
        self._left_tabs.addTab(self._toolbox, "工具箱")

        self._log_panel = LogPanel()
        self._left_tabs.addTab(self._log_panel, "日志")

        self._main_splitter.addWidget(self._left_tabs)

        # Center: Diagram Editor + Image Viewer
        self._center_tabs = QTabWidget()
        self._center_tabs.setStyleSheet(self._tab_style())

        self._diagram_editor = DiagramEditorWidget()
        self._center_tabs.addTab(self._diagram_editor, "流程编辑")

        self.image_panel = ImageViewerPanel()
        self._center_tabs.addTab(self.image_panel, "图像预览")

        self._main_splitter.addWidget(self._center_tabs)

        # Right: Diagram Flow Tabs + Property/Result/Help
        self._right_tabs = QTabWidget()
        self._right_tabs.setFixedWidth(320)
        self._right_tabs.setStyleSheet(self._tab_style())

        self._property_panel = PropertyPanel()
        self._right_tabs.addTab(self._property_panel, "属性")

        self._result_panel = ResultPanel()
        self._right_tabs.addTab(self._result_panel, "结果")

        self._main_splitter.addWidget(self._right_tabs)

        # Restore splitter sizes
        left_w = self._panel_state.get_int("splitter_left", 260)
        right_w = self._panel_state.get_int("splitter_right", 320)
        total_w = self.width()
        center_w = max(400, total_w - left_w - right_w - 6)
        self._main_splitter.setSizes([left_w, center_w, right_w])
        self._main_splitter.splitterMoved.connect(self._save_splitter_state)

        main_layout.addWidget(self._main_splitter, 1)

        # ── Bottom: Flow Resource Panel ──
        self._resource_panel = FlowResourcePanel()
        self._resource_panel.setFixedHeight(120)
        self._resource_panel.setVisible(False)
        main_layout.addWidget(self._resource_panel)

        # ── Connect signals ──
        self._toolbox.node_type_selected.connect(self._on_node_type_selected)
        self._property_panel.property_changed.connect(self._on_property_changed)
        self._diagram_editor.node_selected.connect(self._on_editor_node_selected)
        self._diagram_editor.node_deselected.connect(lambda: self._select_node(None))
        self._property_panel.set_image_viewer(self.image_panel.viewer)

    def _tab_style(self) -> str:
        return """
            QTabWidget::pane { border: 1px solid #3f3f46; background: #252526; }
            QTabBar::tab { background: #2d2d30; color: #dcdcdc; padding: 6px 12px;
                           border: none; border-bottom: 2px solid transparent; }
            QTabBar::tab:selected { background: #252526; border-bottom: 2px solid #0078d4; }
            QTabBar::tab:hover { background: #3e3e42; }
        """

    def _save_splitter_state(self):
        sizes = self._main_splitter.sizes()
        if len(sizes) >= 3:
            self._panel_state.set_int("splitter_left", sizes[0])
            self._panel_state.set_int("splitter_right", sizes[2])

    def _restore_panel_state(self):
        """Restore panel visibility from QSettings."""
        left_visible = self._panel_state.get_bool("left_visible", True)
        right_visible = self._panel_state.get_bool("right_visible", True)
        self._left_tabs.setVisible(left_visible)
        self._right_tabs.setVisible(right_visible)

    # ── Bottom Result Area ───────────────────────────────────────────

    def _setup_bottom_result_area(self):
        """Bottom area with History / Current Result / Help tabs.

        This is embedded within the right panel's result tab
        as a nested tab widget for a compact layout.
        Done in _setup_content via the ResultPanel which already
        has three tabs internally.
        """
        pass  # ResultPanel already has the 3-tab structure (历史结果/当前结果/帮助)

    # ── Status Bar ───────────────────────────────────────────────────

    def _setup_status_bar(self):
        """Blue status bar matching WPF MainWindow."""
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: #007acc; color: white; padding: 2px 8px; font-size: 11px;
            }
            QStatusBar::item { border: none; }
        """)
        self.setStatusBar(self.status_bar)

        self._state_label = QLabel("● 空闲")
        self._state_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        self.status_bar.addWidget(self._state_label)

        self.status_bar.addWidget(self._make_status_sep())

        self._message_label = QLabel("就绪")
        self.status_bar.addWidget(self._message_label, 1)

        self.status_bar.addWidget(self._make_status_sep())

        self._node_count_label = QLabel("节点: 0")
        self.status_bar.addPermanentWidget(self._node_count_label)

        self._time_label = QLabel("")
        self.status_bar.addPermanentWidget(self._time_label)

    def _make_status_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.3);")
        return sep

    def _update_clock(self):
        self._time_label.setText(datetime.now().strftime("%H:%M:%S"))

    # ── Events ───────────────────────────────────────────────────────

    def _connect_events(self):
        event_system.subscribe(EventType.NODE_SELECTED, self._on_event_node_selected)
        event_system.subscribe(EventType.DIAGRAM_CHANGED, self._on_event_diagram_changed)
        event_system.subscribe(EventType.WORKFLOW_STARTED, self._on_workflow_started)
        event_system.subscribe(EventType.WORKFLOW_COMPLETED, self._on_workflow_completed)
        event_system.subscribe(EventType.WORKFLOW_ERROR, self._on_workflow_error)
        event_system.subscribe(EventType.PROJECT_LOADED, self._on_project_loaded)
        event_system.subscribe(EventType.PROJECT_SAVED, self._on_project_saved)

    def _on_event_node_selected(self, sender, **kwargs):
        node = kwargs.get("node", sender)
        self._select_node(node)

    def _on_event_diagram_changed(self, sender, **kwargs):
        if self._workflow:
            nodes = self._workflow.get_all_nodes()
            self._node_count_label.setText(f"节点: {len(nodes)}")

    def _on_workflow_started(self, sender, **kwargs):
        self._state_label.setText("● 运行中")
        self._state_label.setStyleSheet("color: #2196f3; font-weight: bold;")
        self._message_label.setText("流程运行中...")
        self._run_btn.setEnabled(False)

    def _on_workflow_completed(self, sender, **kwargs):
        self._state_label.setText("● 完成")
        self._state_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        self._message_label.setText("流程执行完成")
        self._run_btn.setEnabled(True)

    def _on_workflow_error(self, sender, **kwargs):
        self._state_label.setText("● 错误")
        self._state_label.setStyleSheet("color: #f44336; font-weight: bold;")
        result = kwargs.get("result")
        msg = str(result) if result else "流程执行错误"
        self._message_label.setText(msg)
        self._run_btn.setEnabled(True)

    def _on_project_loaded(self, sender, **kwargs):
        project = kwargs.get("project")
        if project:
            self._update_project_labels(project)
            self._workflow = project.workflow
            self._diagram_editor.bind_workflow(self._workflow)
            self._select_node(None)

    def _on_project_saved(self, sender, **kwargs):
        project = kwargs.get("project")
        if project:
            self._update_project_labels(project)

    def _update_project_labels(self, project):
        name = project.display_name
        self._caption_project_label.setText(f"  {name}  ")
        self._cmd_project_label.setText(name)

    # ── Node Selection ───────────────────────────────────────────────

    def _select_node(self, node: NodeBase | None):
        self._selected_node = node

        self._property_panel.set_node(node)

        if isinstance(node, VisionNodeData):
            self._result_panel.show_node_results(node)
            self._result_panel.show_help(node)
        else:
            self._result_panel.show_node_results(None)
            self._result_panel.show_help(None)

        if isinstance(node, SrcFilesVisionNodeData):
            self._resource_panel.set_node(node)
            self._resource_panel.setVisible(True)
        else:
            self._resource_panel.setVisible(False)

        if isinstance(node, VisionNodeData) and node.mat is not None:
            self.image_panel.set_image(node.mat)
        elif isinstance(node, VisionNodeData) and node._result_image_source is not None:
            self.image_panel.set_image(node._result_image_source)
        else:
            self.image_panel.set_image(None)

        if isinstance(node, ROINodeData):
            self.image_panel.set_roi_rect(node.get_active_roi_rect(), label=node.roi.name)
        else:
            self.image_panel.clear_roi_rect()

    def _on_node_type_selected(self, type_name: str):
        if self._workflow is None:
            return
        node = node_registry.create(type_name)
        if node:
            group_name = self._get_group_for_type(type_name)
            self._diagram_editor.add_node(node, group_name=group_name)
            self._workflow.add_node(node)
            self._log_panel.info(f"添加节点: {node.name}")
            self._node_count_label.setText(f"节点: {len(self._workflow.get_all_nodes())}")

    def _on_editor_node_selected(self, node_data: NodeBase):
        self._select_node(node_data)

    def _get_group_for_type(self, type_name: str) -> str:
        from core.node_group import node_data_group_manager
        for group in node_data_group_manager.get_all_groups():
            for nt in group.node_types:
                if nt.__name__ == type_name:
                    return group.name
        return ""

    def _on_property_changed(self, name: str, old_value, new_value):
        if self._selected_node:
            if isinstance(self._selected_node, ROINodeData):
                self.image_panel.set_roi_rect(
                    self._selected_node.get_active_roi_rect(),
                    label=self._selected_node.roi.name,
                )
            event_system.publish(EventType.NODE_PROPERTY_CHANGED,
                               sender=self._selected_node,
                               name=name, old=old_value, new=new_value)

    # ── Project Operations ───────────────────────────────────────────

    def _on_new_project(self):
        project = project_service.new_project()
        self._workflow = project.workflow
        self._diagram_editor.bind_workflow(self._workflow)
        self._update_project_labels(project)
        self._select_node(None)
        self._log_panel.info("新建项目")

    def _on_open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开项目", "", project_service.FILE_FILTER)
        if path:
            self._open_project(path)

    def _open_project(self, path: str):
        if not path or not os.path.exists(path):
            project_service.remove_recent(path)
            QMessageBox.warning(self, "打开失败", f"项目文件不存在：\n{path}")
            return

        project = project_service.load(path)
        if project:
            self._workflow = project.workflow
            self._update_project_labels(project)
            self._select_node(None)
            self._log_panel.success(f"已打开: {path}")

    def open_project(self, file_path: str):
        """Public method to open a project (called by main.py)."""
        self._open_project(file_path)

    def _on_save_project(self):
        if project_service.current_project:
            if project_service.current_project.is_saved:
                project_service.save()
                self._log_panel.success("项目已保存")
            else:
                self._on_save_as_project()

    def _on_save_as_project(self):
        project = project_service.current_project or project_service.new_project()
        path, _ = QFileDialog.getSaveFileName(
            self, "另存为...", f"{project.display_name}.json", project_service.FILE_FILTER)
        if path:
            if project.workflow is None:
                project.workflow = self._workflow
            project_service.save_as(project, path)
            self._log_panel.success(f"项目已保存至: {path}")

    # ── Workflow Operations ──────────────────────────────────────────

    def _on_run_workflow(self):
        if self._workflow is None:
            return
        self._log_panel.info("开始执行流程...")
        result = self._workflow.execute()
        if result.is_ok:
            self._log_panel.success(f"流程完成: {result.message}")
        elif result.is_error:
            self._log_panel.error(f"流程错误: {result.message}")

    def _on_stop_workflow(self):
        if self._workflow:
            self._workflow.stop()
            self._log_panel.warning("流程已停止")

    # ── Multi-Diagram Tab Support ────────────────────────────────────

    def add_diagram_tab(self, name: str, workflow: WorkflowEngine):
        """Add a new diagram tab (for multi-diagram projects)."""
        self._diagram_tabs[name] = workflow

    def remove_diagram_tab(self, name: str):
        """Remove a diagram tab."""
        self._diagram_tabs.pop(name, None)

    def switch_to_diagram(self, name: str):
        """Switch to a named diagram."""
        workflow = self._diagram_tabs.get(name)
        if workflow:
            self._workflow = workflow
            self._diagram_editor.bind_workflow(workflow)

    @property
    def active_workflow(self) -> WorkflowEngine | None:
        return self._workflow

    # ── Panel Toggle ─────────────────────────────────────────────────

    def toggle_left_panel(self):
        visible = not self._left_tabs.isVisible()
        self._left_tabs.setVisible(visible)
        self._panel_state.set_bool("left_visible", visible)

    def toggle_right_panel(self):
        visible = not self._right_tabs.isVisible()
        self._right_tabs.setVisible(visible)
        self._panel_state.set_bool("right_visible", visible)

    # ── Help ─────────────────────────────────────────────────────────

    def _on_about(self):
        QMessageBox.about(self, "关于 VisionFlow",
                          "<h2>VisionFlow 2.0</h2>"
                          "<p>视觉流程编辑器</p>"
                          "<p>移植自 WPF-VisionMaster (HeBianGu)</p>"
                          "<p>使用 Python + PyQt5 + OpenCV</p>"
                          "<hr>"
                          "<p>开源项目 | MIT License</p>")

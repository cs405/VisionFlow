"""Main window - exact WPF MainWindow.xaml layout.

Ported from:
  - H.App.VisionMaster.OpenCV/MainWindow.xaml(.cs)
  - H.Windows.Main/MainWindow

Exact WPF layout:
  ┌──────────────────────────────────────────────────────────────────────┐
  │ [◆ VisionFlow] 文件 编辑 运行 系统 帮助    [项目名称]  [_][□][✕]   │ Caption
  ├──────────────────────────────────────────────────────────────────────┤
  │ [新建][打开][保存] │ ▶运行 ■停止 │ 放大 缩小 适应 1:1 │ ↩ ↪ │ 项目  │ CmdBar
  ├──────────┬────────────────────────────────────────┬──────────────────┤
  │ 工具箱    │  [流程编辑 | 图像预览 | 模块结果]       │ 流程图标签页      │
  │          │  ┌────────────────────────────────┐   │ [Tab1][Tab2][+] │
  │ [搜索]   │  │ 节点画布 / 图像查看器           │   │ ┌──────────────┐│
  │          │  │                                │   │ │ Diagram      ││
  │ ★ 收藏   │  └────────────────────────────────┘   │ │ Zoombox      ││
  │          │  [图像源文件列表 (隐藏/显示)]          │ │              ││
  │ 数据源    │                                       │ └──────────────┘│
  │ 预处理    │                                       │ ▶开始 ■停止 ↺  │
  │ ...      │                                       │                │
  ├──────────┴────────────────────────────────────────┴──────────────────┤
  │ [历史结果 | 当前模块结果 | 帮助]  ← 底部折叠面板                      │
  ├──────────────────────────────────────────────────────────────────────┤
  │ ● 空闲 │ 就绪                         │ 节点: 0 │ 15:30:00         │
  └──────────────────────────────────────────────────────────────────────┘
"""

import os
from datetime import datetime

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QSplitter, QAction, QActionGroup,
                              QToolBar, QStatusBar, QLabel, QTabWidget,
                              QMessageBox, QFileDialog, QApplication,
                              QPushButton, QFrame, QMenuBar, QMenu,
                              QToolButton, QSizePolicy, QShortcut,
                              QDockWidget, QTextEdit)
from PyQt5.QtCore import Qt, QSize, QTimer, QSettings, pyqtSignal
from PyQt5.QtGui import QFont, QKeySequence, QColor

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
from gui.dock_manager import DockManager
from gui.log_panel import LogPanel
from gui.flow_resource_panel import FlowResourcePanel
from gui.node_editor.editor_widget import DiagramEditorWidget


# ═══════════════════════════════════════════════════════════════════════════
# Panel state persistence
# ═══════════════════════════════════════════════════════════════════════════

class PanelState:
    """QSettings-backed persistent panel dimensions."""
    GRP = "PanelState"

    def __init__(self):
        self.s = QSettings()

    def _k(self, key): return f"{self.GRP}/{key}"
    def get_i(self, k, d=0): return int(self.s.value(self._k(k), d) or d)
    def set_i(self, k, v): self.s.setValue(self._k(k), v)
    def get_b(self, k, d=True):
        v = self.s.value(self._k(k), d)
        return str(v).lower() == "true" if isinstance(v, str) else bool(v) if v is not None else d
    def set_b(self, k, v): self.s.setValue(self._k(k), "true" if v else "false")


_ps = PanelState()

# ═══════════════════════════════════════════════════════════════════════════
# Helper widgets
# ═══════════════════════════════════════════════════════════════════════════

class _Sep(QFrame):
    def __init__(self, v=True):
        super().__init__()
        self.setFrameShape(QFrame.VLine if v else QFrame.HLine)
        self.setStyleSheet("color: #505050;")
        self.setFixedWidth(1) if v else self.setFixedHeight(1)


def _hsep(): return _Sep(True)
def _vsep(): return _Sep(False)


_CMD_BTN = """
    QPushButton { background: transparent; border: 1px solid #505050;
                  border-radius: 3px; padding: 3px 10px; color: #dcdcdc; font-size: 11px; }
    QPushButton:hover { background: #3e3e42; border-color: #0078d4; }
    QPushButton:pressed { background: #0078d4; }
"""

_TAB_STYLE = """
    QTabWidget::pane { border: 1px solid #3f3f46; background: #252526; }
    QTabBar::tab { background: #2d2d30; color: #dcdcdc; padding: 6px 12px;
                   border: none; border-bottom: 2px solid transparent; }
    QTabBar::tab:selected { background: #252526; border-bottom: 2px solid #0078d4; }
    QTabBar::tab:hover { background: #3e3e42; }
"""

# ═══════════════════════════════════════════════════════════════════════════
# MainWindow
# ═══════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """Main application window matching WPF VisionMaster layout exactly."""

    # ── Construction ──────────────────────────────────────────────────

    def __init__(self):
        super().__init__()
        self._workflow: WorkflowEngine | None = None
        self._selected_node: NodeBase | None = None
        self._diagram_tabs: dict[str, WorkflowEngine] = {}

        self._setup_window()
        self._setup_caption_bar()
        self._setup_command_bar()
        self._setup_central_area()
        self._setup_status_bar()
        self._wire_signals()
        self._connect_events()

        self._clock = QTimer(self)
        self._clock.timeout.connect(self._update_clock)
        self._clock.start(1000)

        self._on_new_project()

    # ── Window ────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("VisionFlow - 视觉流程编辑器")
        w = _ps.get_i("window_width", 1400)
        h = _ps.get_i("window_height", 900)
        self.resize(w, h)
        self.setMinimumSize(1024, 640)
        self.setPalette(theme_manager.colors.to_palette())
        self.setStyleSheet(theme_manager.get_stylesheet())
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - w) // 2, (screen.height() - h) // 2)

    def closeEvent(self, ev):
        _ps.set_i("window_width", self.width())
        _ps.set_i("window_height", self.height())
        if hasattr(self, '_bottom_splitter'):
            sizes = self._bottom_splitter.sizes()
            if len(sizes) >= 2:
                _ps.set_i("bottom_height", sizes[1])
        self._clock.stop()
        super().closeEvent(ev)

    # ── Caption Bar ───────────────────────────────────────────────────

    def _setup_caption_bar(self):
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet("background: #1e1e1e; border-bottom: 1px solid #3f3f46;")
        lo = QHBoxLayout(bar); lo.setContentsMargins(8, 0, 0, 0); lo.setSpacing(0)

        lo.addWidget(self._lbl(" ◆", "#0078d4", 16))
        lo.addWidget(self._lbl("VisionFlow", "#dcdcdc", 13, bold=True, pad="0 8px"))

        # Menus in caption
        mb = QMenuBar()
        mb.setStyleSheet("""
            QMenuBar { background: transparent; color: #dcdcdc; padding: 0; }
            QMenuBar::item { padding: 6px 12px; background: transparent; }
            QMenuBar::item:selected { background: #3e3e42; }
            QMenu { background: #2d2d30; color: #dcdcdc; border: 1px solid #505050; }
            QMenu::item { padding: 6px 30px 6px 16px; }
            QMenu::item:selected { background: #0078d4; }
            QMenu::separator { height: 1px; background: #505050; margin: 4px 10px; }
        """)
        self._build_menus(mb)
        lo.addWidget(mb, 1)

        self._cap_proj_lbl = self._lbl("新建项目", "#0078d4", 12, bold=True, pad="0 12px")
        lo.addWidget(self._cap_proj_lbl)
        lo.addWidget(_hsep())

        # Window controls
        ws = """
            QPushButton { background: transparent; border: none; color: #999; font-size: 12px; padding: 0 14px; }
            QPushButton:hover { background: #3e3e42; color: #dcdcdc; }
            QPushButton#cb:hover { background: #e81123; color: white; }
        """
        for t, s in [("─", self.showMinimized), ("□", self._toggle_max),
                      ("✕", self.close)]:
            b = QPushButton(t); b.setStyleSheet(ws)
            if t == "✕": b.setObjectName("cb")
            b.clicked.connect(s); lo.addWidget(b)

        self.setMenuWidget(bar)

    def _lbl(self, t, c, fs, bold=False, pad=""):
        l = QLabel(t)
        l.setStyleSheet(f"color: {c}; font-size: {fs}px; {'font-weight: bold;' if bold else ''} padding: {pad};")
        return l

    def _toggle_max(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    # ── Menus ─────────────────────────────────────────────────────────

    def _build_menus(self, mb: QMenuBar):
        # File
        fm = mb.addMenu("文件(&F)")
        for t, s, sc in [("新建项目(&N)", self._on_new_project, "Ctrl+N"),
                          ("打开项目(&O)...", self._on_open_project, "Ctrl+O"),
                          ("保存项目(&S)", self._on_save_project, "Ctrl+S"),
                          ("另存为(&A)...", self._on_save_as_project, "Ctrl+Shift+S")]:
            a = QAction(t, self); a.setShortcut(sc); a.triggered.connect(s); fm.addAction(a)
        fm.addSeparator()
        self._recent_menu = fm.addMenu("最近的项目(&R)")
        self._recent_menu.aboutToShow.connect(self._refresh_recent)
        fm.addSeparator()
        a = QAction("退出(&X)", self); a.setShortcut("Alt+F4"); a.triggered.connect(self.close); fm.addAction(a)

        # Edit
        em = mb.addMenu("编辑(&E)")
        for t, sc in [("撤销(&U)", "Ctrl+Z"), ("重做(&R)", "Ctrl+Y")]:
            a = QAction(t, self); a.setShortcut(sc); em.addAction(a)
        em.addSeparator()
        for t, sc in [("删除选中(&D)", "Delete"), ("全选(&A)", "Ctrl+A")]:
            a = QAction(t, self); a.setShortcut(sc); em.addAction(a)

        # Run
        rm = mb.addMenu("运行(&R)")
        for t, sc, s in [("运行流程(&F)", "F5", self._on_run_workflow),
                          ("停止(&S)", "Shift+F5", self._on_stop_workflow),
                          ("单步执行(&T)", "F10", None)]:
            a = QAction(t, self)
            a.setShortcut(sc)
            if s:
                a.triggered.connect(s)
            rm.addAction(a)

        # System
        sm = mb.addMenu("系统(&S)")
        sm.addAction("设置(&S)...")
        sm.addAction("主题设置(&T)")
        sm.addSeparator()
        a = QAction("切换工具箱", self); a.setCheckable(True); a.setChecked(True); sm.addAction(a)
        a = QAction("切换属性面板", self); a.setCheckable(True); a.setChecked(True); sm.addAction(a)
        sm.addSeparator()
        sm.addAction("流程功能列表")

        # Help
        hm = mb.addMenu("帮助(&H)")
        hm.addAction("使用指南(&G)")
        hm.addAction("检查更新(&U)")
        hm.addSeparator()
        a = QAction("关于 VisionFlow(&A)", self); a.triggered.connect(self._on_about); hm.addAction(a)
        hm.addAction("联系我们(&C)")

    def _refresh_recent(self):
        self._recent_menu.clear()
        project_service.cleanup_recent_projects()
        if not project_service.recent_projects:
            a = QAction("(无最近项目)", self); a.setEnabled(False); self._recent_menu.addAction(a); return
        for p in project_service.recent_projects:
            a = QAction(os.path.basename(p), self); a.setToolTip(p)
            a.triggered.connect(lambda c, pp=p: self._open_project(pp)); self._recent_menu.addAction(a)
        self._recent_menu.addSeparator()
        a = QAction("清空最近项目", self); a.triggered.connect(project_service.clear_recent_projects)
        self._recent_menu.addAction(a)

    # ── Command Bar ───────────────────────────────────────────────────

    def _setup_command_bar(self):
        w = QWidget(); w.setFixedHeight(34)
        w.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        lo = QHBoxLayout(w); lo.setContentsMargins(6, 0, 6, 0); lo.setSpacing(4)

        for t, s in [("新建", self._on_new_project), ("打开", self._on_open_project),
                      ("保存", self._on_save_project)]:
            b = QPushButton(t); b.setStyleSheet(_CMD_BTN); b.clicked.connect(s); lo.addWidget(b)
        lo.addWidget(_hsep())

        self._run_btn = QPushButton("▶ 运行"); self._run_btn.setStyleSheet(_CMD_BTN.replace("#0078d4", "#4caf50"))
        self._run_btn.clicked.connect(self._on_run_workflow); lo.addWidget(self._run_btn)
        self._stop_btn = QPushButton("■ 停止"); self._stop_btn.setStyleSheet(_CMD_BTN.replace("#0078d4", "#f44336"))
        self._stop_btn.clicked.connect(self._on_stop_workflow); lo.addWidget(self._stop_btn)
        lo.addWidget(_hsep())

        for t, s in [("放大", lambda: self._img_panel.viewer.zoom_in()),
                      ("缩小", lambda: self._img_panel.viewer.zoom_out()),
                      ("适应", lambda: self._img_panel.viewer.fit_to_window()),
                      ("1:1", lambda: self._img_panel.viewer.zoom_to_100())]:
            b = QPushButton(t); b.setStyleSheet(_CMD_BTN); b.clicked.connect(s); lo.addWidget(b)
        lo.addWidget(_hsep())

        for t in ["↩ 撤销", "↪ 重做"]:
            b = QPushButton(t); b.setStyleSheet(_CMD_BTN); lo.addWidget(b)

        lo.addStretch()
        self._cmd_proj_lbl = self._lbl("新建项目", "#0078d4", 12, bold=True, pad="0 8px")
        lo.addWidget(self._cmd_proj_lbl)

        tb = QToolBar("命令栏"); tb.setMovable(False); tb.addWidget(w)
        self.addToolBar(Qt.TopToolBarArea, tb)

    # ── Central Area ──────────────────────────────────────────────────

    def _setup_central_area(self):
        """Build content with QDockWidget left/right + center (top+bottom splitter)."""
        # ── CENTER widget (vertical splitter: top area | bottom result) ──
        cw = QWidget()
        root = QVBoxLayout(cw); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self._bottom_splitter = QSplitter(Qt.Vertical)
        self._bottom_splitter.setHandleWidth(2)
        self._bottom_splitter.setStyleSheet("QSplitter::handle { background: #505050; }")

        self._setup_center_panel()    # diagram editor / image viewer / module results

        self._bottom_splitter.addWidget(self._center_widget)

        # Bottom: tabbed result area
        self._setup_bottom_panel()
        bh = _ps.get_i("bottom_height", 160)
        self._bottom_splitter.setSizes([self.height() - bh - 80, bh])

        root.addWidget(self._bottom_splitter, 1)
        self.setCentralWidget(cw)

        # ── QDockWidget-based LEFT & RIGHT panels ──
        self._dock_mgr = DockManager(self)

        # Left dock: toolbox + log
        lw = QTabWidget()
        lw.setStyleSheet(_TAB_STYLE)
        self._toolbox = ToolboxPanel()
        lw.addTab(self._toolbox, "工具箱")
        self._log_panel = LogPanel()
        lw.addTab(self._log_panel, "日志")
        self._dock_mgr.register("left_toolbox", "工具箱 / 日志", lw,
                                Qt.LeftDockWidgetArea, True, 260, True, False)
        self._dock_mgr.attach("left_toolbox")

        # Right dock: diagram flow tabs
        self._setup_right_panel()
        self._dock_mgr.register("right_diagram", "流程图标签", self._diagram_right_widget,
                                Qt.RightDockWidgetArea, True, 280, True, False)
        self._dock_mgr.attach("right_diagram")

        # Restore saved dock state
        self._dock_mgr.restore_state()

    def closeEvent(self, ev):
        self._dock_mgr.save_state()
        _ps.set_i("window_width", self.width())
        _ps.set_i("window_height", self.height())
        if hasattr(self, '_bottom_splitter'):
            sizes = self._bottom_splitter.sizes()
            if len(sizes) >= 2:
                _ps.set_i("bottom_height", sizes[1])
        self._clock.stop()
        super().closeEvent(ev)

    # ── CENTER PANEL ──────────────────────────────────────────────────

    def _setup_center_panel(self):
        """Center: tabbed [Diagram Editor | Image Preview | Module Results] +
        bottom image source resource panel."""
        w = QWidget()
        lo = QVBoxLayout(w); lo.setContentsMargins(0, 0, 0, 0); lo.setSpacing(0)

        self._center_tabs = QTabWidget()
        self._center_tabs.setStyleSheet(_TAB_STYLE)

        self._diagram_editor = DiagramEditorWidget()
        self._center_tabs.addTab(self._diagram_editor, "流程编辑")

        self._img_panel = ImageViewerPanel()
        self._center_tabs.addTab(self._img_panel, "图像预览")

        self._property_panel = PropertyPanel()
        self._center_tabs.addTab(self._property_panel, "模块结果")

        lo.addWidget(self._center_tabs, 1)

        self._resource_panel = FlowResourcePanel()
        self._resource_panel.setFixedHeight(110)
        self._resource_panel.setVisible(False)
        lo.addWidget(self._resource_panel)

        self._center_widget = w

    # ── RIGHT PANEL (Diagram Flow Tabs) ──────────────────────────────

    def _setup_right_panel(self):
        """Right side: diagram flow tab bar with Start/Stop/Reset per tab."""
        w = QWidget()
        lo = QVBoxLayout(w); lo.setContentsMargins(0, 0, 0, 0); lo.setSpacing(0)

        self._diagram_tab_widget = QTabWidget()
        self._diagram_tab_widget.setStyleSheet(_TAB_STYLE)
        self._diagram_tab_widget.setTabsClosable(True)
        self._diagram_tab_widget.tabCloseRequested.connect(self._on_close_diagram_tab)
        self._diagram_tab_widget.currentChanged.connect(self._on_diagram_tab_changed)

        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #0078d4; font-size: 16px; font-weight: bold; } QPushButton:hover { color: #1a8ad4; }")
        add_btn.clicked.connect(self._on_add_diagram)
        self._diagram_tab_widget.setCornerWidget(add_btn, Qt.TopRightCorner)

        self._diagram_tab_widget.addTab(QLabel("主流程图"), "main")
        lo.addWidget(self._diagram_tab_widget, 1)

        ctrl = QWidget()
        ctrl.setFixedHeight(32)
        ctrl.setStyleSheet("background: #2d2d30; border-top: 1px solid #3f3f46;")
        clo = QHBoxLayout(ctrl); clo.setContentsMargins(4, 0, 4, 0); clo.setSpacing(4)

        for t, s in [("▶ 开始", self._on_run_workflow), ("■ 停止", self._on_stop_workflow),
                      ("↺ 重置", None)]:
            b = QPushButton(t)
            b.setStyleSheet(_CMD_BTN)
            if s:
                b.clicked.connect(s)
            clo.addWidget(b)
        clo.addStretch()

        lo.addWidget(ctrl)
        self._diagram_right_widget = w

    def _on_add_diagram(self):
        name = f"流程图{self._diagram_tab_widget.count()}"
        self._diagram_tab_widget.addTab(QLabel(name), name)
        self._diagram_tab_widget.setCurrentIndex(self._diagram_tab_widget.count() - 1)

    def _on_close_diagram_tab(self, idx):
        if self._diagram_tab_widget.count() > 1:
            self._diagram_tab_widget.removeTab(idx)

    def _on_diagram_tab_changed(self, idx):
        pass  # Future: switch workflow

    # ── BOTTOM PANEL (History | Current Results | Help) ──────────────

    def _setup_bottom_panel(self):
        """Bottom tabbed area matching WPF's History/Current/Help tabs exactly."""
        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.setStyleSheet(_TAB_STYLE)
        self._bottom_tabs.setMinimumHeight(100)

        # History Results
        self._history_widget = self._create_history_view()
        self._bottom_tabs.addTab(self._history_widget, "历史结果")

        # Current Module Results
        self._current_result_view = self._create_current_results_view()
        self._bottom_tabs.addTab(self._current_result_view, "当前模块结果")

        # Help
        self._help_view = QTextEdit()
        self._help_view.setReadOnly(True)
        self._help_view.setStyleSheet("background: #252526; color: #dcdcdc; border: none; padding: 8px; font-size: 12px;")
        self._help_view.setPlaceholderText("选择节点查看帮助信息")
        self._bottom_tabs.addTab(self._help_view, "帮助")

        # Toggle button to collapse bottom panel
        self._bottom_visible = True
        self._bottom_toggle = QPushButton("▼")
        self._bottom_toggle.setFixedSize(24, 18)
        self._bottom_toggle.setStyleSheet("QPushButton { background: #2d2d30; border: 1px solid #3f3f46; color: #999; font-size: 9px; } QPushButton:hover { color: #dcdcdc; }")
        self._bottom_toggle.clicked.connect(self._toggle_bottom)
        self._bottom_tabs.setCornerWidget(self._bottom_toggle, Qt.TopLeftCorner)

        self._bottom_splitter.addWidget(self._bottom_tabs)

    def _toggle_bottom(self):
        sizes = self._bottom_splitter.sizes()
        if len(sizes) < 2: return
        if self._bottom_visible:
            _ps.set_i("bottom_height_saved", sizes[1])
            self._bottom_splitter.setSizes([sizes[0] + sizes[1], 0])
            self._bottom_toggle.setText("▲")
        else:
            saved = _ps.get_i("bottom_height_saved", 160)
            total = sum(sizes)
            bh = min(saved, total - 200)
            self._bottom_splitter.setSizes([total - bh, bh])
            self._bottom_toggle.setText("▼")
        self._bottom_visible = not self._bottom_visible

    def _create_history_view(self):
        """History results matching WPF DataGrid columns: # | Time | Module | Result."""
        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        t = QTableWidget(0, 4)
        t.setHorizontalHeaderLabels(["#", "时间", "模块", "结果"])
        t.setColumnWidth(0, 35); t.setColumnWidth(1, 75); t.setColumnWidth(2, 110)
        t.horizontalHeader().setStretchLastSection(True)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.setStyleSheet("""
            QTableWidget { background: #252526; color: #dcdcdc; border: none; gridline-color: #3f3f46;
                           alternate-background-color: #2a2a2c; }
            QHeaderView::section { background: #2d2d30; color: #999; padding: 4px 8px;
                                   border: none; border-bottom: 1px solid #3f3f46; font-size: 11px; }
            QTableWidget::item { padding: 2px 8px; font-size: 11px; }
            QTableWidget::item:selected { background: #094771; }
        """)
        t.cellDoubleClicked.connect(self._on_history_double_click)
        self._history_table = t
        self._history_rows: list[dict] = []
        return t

    def _create_current_results_view(self):
        """Current module results table: Property | Value."""
        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        t = QTableWidget(0, 2)
        t.setHorizontalHeaderLabels(["参数", "值"])
        t.horizontalHeader().setStretchLastSection(True)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.setStyleSheet("""
            QTableWidget { background: #252526; color: #dcdcdc; border: none; gridline-color: #3f3f46;
                           alternate-background-color: #2a2a2c; }
            QHeaderView::section { background: #2d2d30; color: #999; padding: 4px 8px;
                                   border: none; border-bottom: 1px solid #3f3f46; font-size: 11px; }
            QTableWidget::item { padding: 2px 8px; font-size: 11px; }
        """)
        self._current_result_table = t
        return t

    def _on_history_double_click(self, row, col):
        """Double-click history entry to jump to the source node."""
        if 0 <= row < len(self._history_rows):
            entry = self._history_rows[row]
            node_id = entry.get("node_id", "")
            if node_id and self._workflow:
                node = self._workflow.get_node(node_id)
                if node:
                    self._select_node(node)
                    self._center_tabs.setCurrentIndex(0)  # switch to diagram tab

    # ── Status Bar ────────────────────────────────────────────────────

    def _setup_status_bar(self):
        sb = QStatusBar()
        sb.setStyleSheet("QStatusBar { background: #007acc; color: white; padding: 2px 8px; font-size: 11px; } QStatusBar::item { border: none; }")
        self.setStatusBar(sb)

        self._state_lbl = QLabel("● 空闲"); self._state_lbl.setStyleSheet("color: #4caf50; font-weight: bold;")
        sb.addWidget(self._state_lbl)
        sb.addWidget(_hsep())
        self._msg_lbl = QLabel("就绪"); sb.addWidget(self._msg_lbl, 1)
        sb.addWidget(_hsep())
        self._node_cnt_lbl = QLabel("节点: 0"); sb.addPermanentWidget(self._node_cnt_lbl)
        self._time_lbl = QLabel(""); sb.addPermanentWidget(self._time_lbl)

    def _update_clock(self):
        self._time_lbl.setText(datetime.now().strftime("%H:%M:%S"))

    # ── Signal Wiring ─────────────────────────────────────────────────

    def _wire_signals(self):
        self._toolbox.node_type_selected.connect(self._on_node_type_selected)
        self._property_panel.property_changed.connect(self._on_property_changed)
        self._diagram_editor.node_selected.connect(self._on_editor_node_selected)
        self._diagram_editor.node_deselected.connect(lambda: self._select_node(None))
        self._property_panel.set_image_viewer(self._img_panel.viewer)
        # Log panel: jump to node on entry click
        self._log_panel.node_jump_requested.connect(self._jump_to_node)
        # Result panel: also support node jump from history
        if hasattr(self, '_history_table'):
            pass  # history click handled in _on_history_double_click

    # ── Events ────────────────────────────────────────────────────────

    def _connect_events(self):
        event_system.subscribe(EventType.NODE_SELECTED, self._on_ev_node_sel)
        event_system.subscribe(EventType.DIAGRAM_CHANGED, self._on_ev_diag_chg)
        event_system.subscribe(EventType.WORKFLOW_STARTED, self._on_wf_start)
        event_system.subscribe(EventType.WORKFLOW_COMPLETED, self._on_wf_done)
        event_system.subscribe(EventType.WORKFLOW_ERROR, self._on_wf_err)
        event_system.subscribe(EventType.PROJECT_LOADED, self._on_proj_load)
        event_system.subscribe(EventType.PROJECT_SAVED, self._on_proj_save)

    def _on_ev_node_sel(self, s, **kw):
        self._select_node(kw.get("node", s))

    def _on_ev_diag_chg(self, s, **kw):
        if self._workflow:
            self._node_cnt_lbl.setText(f"节点: {len(self._workflow.get_all_nodes())}")

    def _on_wf_start(self, s, **kw):
        self._state_lbl.setText("● 运行中"); self._state_lbl.setStyleSheet("color: #2196f3; font-weight: bold;")
        self._msg_lbl.setText("流程运行中..."); self._run_btn.setEnabled(False)

    def _on_wf_done(self, s, **kw):
        self._state_lbl.setText("● 完成"); self._state_lbl.setStyleSheet("color: #4caf50; font-weight: bold;")
        self._msg_lbl.setText("流程执行完成"); self._run_btn.setEnabled(True)

    def _on_wf_err(self, s, **kw):
        self._state_lbl.setText("● 错误"); self._state_lbl.setStyleSheet("color: #f44336; font-weight: bold;")
        r = kw.get("result"); self._msg_lbl.setText(str(r) if r else "流程错误"); self._run_btn.setEnabled(True)

    def _on_proj_load(self, s, **kw):
        p = kw.get("project")
        if p:
            self._sync_proj_labels(p)
            self._workflow = p.workflow
            self._diagram_editor.bind_workflow(self._workflow)
            self._select_node(None)

    def _on_proj_save(self, s, **kw):
        p = kw.get("project")
        if p: self._sync_proj_labels(p)

    def _sync_proj_labels(self, p):
        n = p.display_name
        self._cap_proj_lbl.setText(f"  {n}  ")
        self._cmd_proj_lbl.setText(n)

    # ── Node Selection ────────────────────────────────────────────────

    def _select_node(self, node: NodeBase | None):
        self._selected_node = node

        # Property panel (center tab "模块结果")
        self._property_panel.set_node(node)

        # Bottom: current module results
        self._populate_current_results(node)
        self._populate_help(node)

        # Flow resource panel visibility
        if isinstance(node, SrcFilesVisionNodeData):
            self._resource_panel.set_node(node)
            self._resource_panel.setVisible(True)
        else:
            self._resource_panel.setVisible(False)

        # Image viewer
        if isinstance(node, VisionNodeData) and node.mat is not None:
            self._img_panel.set_image(node.mat)
        elif isinstance(node, VisionNodeData) and node._result_image_source is not None:
            self._img_panel.set_image(node._result_image_source)
        else:
            self._img_panel.set_image(None)

        if isinstance(node, ROINodeData):
            self._img_panel.set_roi_rect(node.get_active_roi_rect(), label=node.roi.name)
        else:
            self._img_panel.clear_roi_rect()

        # Add to history
        if isinstance(node, VisionNodeData):
            self._add_history_entry(node)

    def _populate_current_results(self, node):
        """Fill the bottom '当前模块结果' table."""
        from PyQt5.QtWidgets import QTableWidgetItem
        t = self._current_result_table
        t.setRowCount(0)
        if node is None: return
        rows = [
            ("名称", node.name if hasattr(node, 'name') else type(node).__name__),
            ("类型", type(node).__name__),
            ("消息", getattr(node, 'message', '-') or '-'),
            ("节点ID", getattr(node, 'node_id', '-')),
        ]
        for k, v in rows:
            r = t.rowCount(); t.insertRow(r)
            ki = QTableWidgetItem(str(k)); ki.setForeground(QColor("#999")); t.setItem(r, 0, ki)
            vi = QTableWidgetItem(str(v)); vi.setForeground(QColor("#dcdcdc")); t.setItem(r, 1, vi)

    def _populate_help(self, node):
        if node is None:
            self._help_view.setHtml('<p style="color: #666;">选择节点查看帮助信息</p>'); return
        if hasattr(node, 'create_help_presenter'):
            hi = node.create_help_presenter()
            if isinstance(hi, dict):
                html = f"""<h3 style="color: #0078d4;">{node.name}</h3>
                <p style="color: #999;">类型: {type(node).__name__}</p><hr style="border-color: #3f3f46;">
                <p style="color: #dcdcdc;">{hi.get('description', '暂无描述')}</p>
                <p style="color: #999; font-size: 11px;">帮助: {hi.get('url', '暂无帮助链接')}</p>"""
            else:
                html = f"""<h3 style="color: #0078d4;">{node.name}</h3>
                <p style="color: #999;">类型: {type(node).__name__}</p><hr style="border-color: #3f3f46;">
                <p style="color: #dcdcdc;">暂无详细帮助信息</p>"""
            self._help_view.setHtml(html)

    def _add_history_entry(self, node):
        """Add to the bottom '历史结果' table."""
        from PyQt5.QtWidgets import QTableWidgetItem
        import datetime
        entry = {
            "node_id": node.node_id if hasattr(node, 'node_id') else "",
            "name": node.name if hasattr(node, 'name') else type(node).__name__,
            "msg": getattr(node, 'message', '') or '',
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
        }
        self._history_rows.append(entry)
        if len(self._history_rows) > 200:
            self._history_rows = self._history_rows[-200:]

        t = self._history_table
        t.setRowCount(0)
        for i, e in enumerate(self._history_rows):
            r = t.rowCount(); t.insertRow(r)
            for ci, (v, c) in enumerate([(str(i+1), "#666"), (e["time"], "#999"),
                                          (e["name"], "#dcdcdc"), (e["msg"] or "成功", "#4caf50")]):
                it = QTableWidgetItem(v); it.setForeground(QColor(c)); t.setItem(r, ci, it)
        t.scrollToBottom()

    # ── Node Type Selected (Toolbox → Canvas) ────────────────────────

    def _on_node_type_selected(self, tn: str):
        if not self._workflow: return
        n = node_registry.create(tn)
        if n:
            g = self._get_group(tn)
            self._diagram_editor.add_node(n, group_name=g)
            self._workflow.add_node(n)
            self._log_panel.info(f"添加节点: {n.name}")
            self._node_cnt_lbl.setText(f"节点: {len(self._workflow.get_all_nodes())}")

    def _on_editor_node_selected(self, nd: NodeBase):
        self._select_node(nd)

    def _get_group(self, tn: str) -> str:
        from core.node_group import node_data_group_manager
        for g in node_data_group_manager.get_all_groups():
            for nt in g.node_types:
                if nt.__name__ == tn: return g.name
        return ""

    def _on_property_changed(self, name, old, new):
        if self._selected_node:
            if isinstance(self._selected_node, ROINodeData):
                self._img_panel.set_roi_rect(self._selected_node.get_active_roi_rect(),
                                              label=self._selected_node.roi.name)
            event_system.publish(EventType.NODE_PROPERTY_CHANGED,
                                 sender=self._selected_node, name=name, old=old, new=new)

    # ── Project Ops ───────────────────────────────────────────────────

    def _on_new_project(self):
        p = project_service.new_project()
        self._workflow = p.workflow
        self._diagram_editor.bind_workflow(self._workflow)
        self._sync_proj_labels(p)
        self._select_node(None)
        self._log_panel.info("新建项目")

    def _on_open_project(self):
        p, _ = QFileDialog.getOpenFileName(self, "打开项目", "", project_service.FILE_FILTER)
        if p: self._open_project(p)

    def _open_project(self, path: str):
        if not path or not os.path.exists(path):
            project_service.remove_recent(path)
            QMessageBox.warning(self, "打开失败", f"文件不存在: {path}"); return
        p = project_service.load(path)
        if p:
            self._workflow = p.workflow; self._sync_proj_labels(p)
            self._select_node(None); self._log_panel.success(f"已打开: {path}")

    def open_project(self, fp: str): self._open_project(fp)

    def _on_save_project(self):
        if project_service.current_project:
            if project_service.current_project.is_saved:
                project_service.save(); self._log_panel.success("项目已保存")
            else: self._on_save_as_project()

    def _on_save_as_project(self):
        p = project_service.current_project or project_service.new_project()
        path, _ = QFileDialog.getSaveFileName(self, "另存为...", f"{p.display_name}.json", project_service.FILE_FILTER)
        if path:
            if p.workflow is None: p.workflow = self._workflow
            project_service.save_as(p, path); self._log_panel.success(f"已保存至: {path}")

    # ── Workflow Ops ──────────────────────────────────────────────────

    def _on_run_workflow(self):
        if not self._workflow: return
        self._log_panel.info("开始执行流程...")
        r = self._workflow.execute()
        if r.is_ok: self._log_panel.success(f"流程完成: {r.message}")
        elif r.is_error: self._log_panel.error(f"流程错误: {r.message}")

    def _on_stop_workflow(self):
        if self._workflow: self._workflow.stop(); self._log_panel.warning("流程已停止")

    def _jump_to_node(self, node_id: str):
        """Jump to and select a node by its ID."""
        if self._workflow:
            node = self._workflow.get_node(node_id)
            if node:
                self._select_node(node)
                self._center_tabs.setCurrentIndex(0)  # switch to diagram tab

    # ── Panel Toggle ──────────────────────────────────────────────────

    def toggle_left_panel(self):
        if hasattr(self, '_dock_mgr'):
            self._dock_mgr.toggle("left_toolbox")

    def toggle_right_panel(self):
        if hasattr(self, '_dock_mgr'):
            self._dock_mgr.toggle("right_diagram")

    @property
    def active_workflow(self) -> WorkflowEngine | None:
        return self._workflow

    def add_diagram_tab(self, name: str, workflow: WorkflowEngine):
        self._diagram_tabs[name] = workflow
        self._diagram_tab_widget.addTab(QLabel(name), name)

    def remove_diagram_tab(self, name: str):
        self._diagram_tabs.pop(name, None)

    # ── Help ──────────────────────────────────────────────────────────

    def _on_about(self):
        QMessageBox.about(self, "关于 VisionFlow",
                          "<h2>VisionFlow 2.0</h2><p>视觉流程编辑器</p>"
                          "<p>移植自 WPF-VisionMaster (HeBianGu)</p>"
                          "<p>使用 Python + PyQt5 + OpenCV</p><hr>"
                          "<p>开源项目 | MIT License</p>")

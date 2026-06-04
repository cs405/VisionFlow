"""Main window — 100% WPF MainWindow.xaml pixel-level alignment.

Ported from:
  - H.App.VisionMaster.OpenCV/MainWindow.xaml(.cs)
  - H.Windows.Main/MainWindow

WPF-aligned layout:
  ┌── CAPTION (66px, 2-row UniformGrid) ───────────────────────────────────────┐
  │ Row1: [◆ VF] 文件 编辑 运行 系统 帮助   项目名称：xxx    [⚙][🎨][ℹ][📖][_][□][✕] │
  │ Row2: [新建][打开][保存]│[▶运行][■停止]│[放大][缩小][适应][1:1]│[↩][↪] │ 项目名│
  ├── LEFT ───────────┬── CENTER ────────────────────┬── RIGHT ────────────────┤
  │ 流程资源 (Tab)     │ TabControl [图像|模块结果]    │ 流程图  [+]             │
  │ ┌────────────────┐│ ┌──────────────────────────┐│ [Tab1][Tab2][×]         │
  │ │ Tree/List view ││ │ 图像: Zoombox with       ││ ┌──────────────────────┐│
  │ │ NodeGroups     ││ │  - ResultType overlay    ││ │ DiagramEditorWidget  ││
  │ │ ★ Favorites    ││ │  - File info bar         ││ │ (Flow Chart Canvas)  ││
  │ │ 🔍 Search      ││ │ 模块结果: PropertyPanel  ││ │ - Nodes + Edges      ││
  │ │ Stats footer   ││ └──────────────────────────┘│ │ - Zoom/Pan           ││
  │ └────────────────┘│ FlowResourcePanel (底)      │ │ - Minimap            ││
  │ 日志 (Tab)         │                            │ └──────────────────────┘│
  │                    │                            │ ▶开始 ■停止 ↺           │
  ├────────────────────┴────────────────────────────┴──────────────────────────┤
  │ BOTTOM TABS (collapsible): [历史结果 | 当前模块结果 | 帮助]          ⇄ ▼  │
  ├────────────────────────────────────────────────────────────────────────────┤
  │ ● 空闲 │ 就绪                              │ 节点: 0 │ 15:30:00          │
  └────────────────────────────────────────────────────────────────────────────┘
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
from PyQt5.QtGui import QFont, QKeySequence, QColor, QIcon, QPixmap

from core.node_base import NodeBase, VisionNodeData, SrcFilesVisionNodeData, ROINodeData
from core.workflow import WorkflowEngine
from core.project import project_service, DiagramData, ProjectItem
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
from gui.start_page import StartPage
from gui.help_panel import HelpPanel


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
        self._project_loaded: bool = False

        self._setup_window()
        self._setup_caption_bar()
        self._setup_central_area()
        self._setup_status_bar()
        self._wire_signals()
        self._connect_events()

        self._clock = QTimer(self)
        self._clock.timeout.connect(self._update_clock)
        self._clock.start(1000)

        # Show start page initially (no project auto-created)
        self._show_start_page()

    # ── Window ────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("VisionFlow - 视觉流程编辑器")
        w = _ps.get_i("window_width", 1400)
        h = _ps.get_i("window_height", 900)
        self.resize(w, h)
        self.setMinimumSize(1024, 640)
        self.setPalette(theme_manager.colors.to_palette())
        self.setStyleSheet(theme_manager.get_stylesheet())
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
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

    # ── Caption Bar (WPF double-row: Row1=Menu+Title+Actions, Row2=CommandBar) ──

    def _setup_caption_bar(self):
        """WPF-aligned 2-row caption: Row1 menus + project name + action buttons,
        Row2 command bar (New/Open/Save | Run/Stop | Zoom | Undo/Redo)."""
        bar = QWidget()
        bar.setFixedHeight(66)
        bar.setStyleSheet("background: #1e1e1e; border-bottom: 1px solid #3f3f46;")
        main_lo = QVBoxLayout(bar); main_lo.setContentsMargins(0, 0, 0, 0); main_lo.setSpacing(0)

        # ── Row 1: Logo + Menu + Project Name + Action buttons ──
        r1 = QWidget()
        r1.setFixedHeight(32)
        r1_lo = QHBoxLayout(r1); r1_lo.setContentsMargins(8, 0, 0, 0); r1_lo.setSpacing(0)

        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "logo.png")
        if os.path.exists(logo_path):
            logo = QLabel()
            logo.setPixmap(QPixmap(logo_path).scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo.setStyleSheet("padding: 0 6px 0 0;")
            r1_lo.addWidget(logo)
        else:
            r1_lo.addWidget(self._lbl(" ◆", "#0078d4", 16))
        r1_lo.addWidget(self._lbl("VisionFlow", "#dcdcdc", 13, bold=True, pad="0 8px"))

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
        r1_lo.addWidget(mb, 1)

        proj_prefix = self._lbl("项目名称：", "#c8c8c8", 11, pad="0 4px")
        r1_lo.addWidget(proj_prefix)
        self._cap_proj_lbl = self._lbl("新建项目", "#0078d4", 12, bold=True, pad="0 12px")
        r1_lo.addWidget(self._cap_proj_lbl)
        r1_lo.addWidget(_hsep())

        # Action buttons (WPF: Theme, Setting, About, Guide)
        ab_style = """
            QPushButton { background: transparent; border: none; color: #999; font-size: 13px; padding: 0 8px; }
            QPushButton:hover { background: #3e3e42; color: #dcdcdc; }
        """
        for icon, tip in [("⚙", "设置"), ("🎨", "主题"), ("ℹ", "关于"), ("📖", "帮助")]:
            ab = QPushButton(icon); ab.setStyleSheet(ab_style); ab.setToolTip(tip)
            r1_lo.addWidget(ab)

        # Window controls
        ws = """
            QPushButton { background: transparent; border: none; color: #999; font-size: 12px; padding: 0 14px; }
            QPushButton:hover { background: #3e3e42; color: #dcdcdc; }
            QPushButton#cb:hover { background: #e81123; color: white; }
        """
        for t, s in [("─", self.showMinimized), ("□", self._toggle_max), ("✕", self.close)]:
            b = QPushButton(t); b.setStyleSheet(ws)
            if t == "✕": b.setObjectName("cb")
            b.clicked.connect(s); r1_lo.addWidget(b)

        main_lo.addWidget(r1)

        # ── Row 2: Command Bar (matching WPF second caption row) ──
        r2 = QWidget()
        r2.setStyleSheet("background: #2d2d30; border-top: 1px solid #3f3f46;")
        clo = QHBoxLayout(r2); clo.setContentsMargins(8, 2, 8, 2); clo.setSpacing(4)

        for t, s in [("新建", self._on_new_project), ("打开", self._on_open_project),
                      ("保存", self._on_save_project)]:
            b = QPushButton(t); b.setStyleSheet(_CMD_BTN); b.clicked.connect(s); clo.addWidget(b)
        clo.addWidget(_hsep())

        self._run_btn = QPushButton("▶ 运行"); self._run_btn.setStyleSheet(_CMD_BTN.replace("#0078d4", "#4caf50"))
        self._run_btn.clicked.connect(self._on_run_workflow); clo.addWidget(self._run_btn)
        self._stop_btn = QPushButton("■ 停止"); self._stop_btn.setStyleSheet(_CMD_BTN.replace("#0078d4", "#f44336"))
        self._stop_btn.clicked.connect(self._on_stop_workflow); clo.addWidget(self._stop_btn)
        clo.addWidget(_hsep())

        for t, s in [("放大", lambda: self._active_visual_target().zoom_in()),
                      ("缩小", lambda: self._active_visual_target().zoom_out()),
                      ("适应", lambda: self._active_visual_target().fit_to_window()),
                      ("1:1", lambda: self._active_visual_target().zoom_to_100())]:
            b = QPushButton(t); b.setStyleSheet(_CMD_BTN); b.clicked.connect(s); clo.addWidget(b)
        clo.addWidget(_hsep())

        undo_btn = QPushButton("↩ 撤销"); undo_btn.setStyleSheet(_CMD_BTN); undo_btn.clicked.connect(self._on_undo_diagram); clo.addWidget(undo_btn)
        redo_btn = QPushButton("↪ 重做"); redo_btn.setStyleSheet(_CMD_BTN); redo_btn.clicked.connect(self._on_redo_diagram); clo.addWidget(redo_btn)

        clo.addStretch()
        self._cmd_proj_lbl = self._lbl("新建项目", "#0078d4", 12, bold=True, pad="0 8px")
        clo.addWidget(self._cmd_proj_lbl)

        main_lo.addWidget(r2)
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

    # ── Central Area ──────────────────────────────────────────────────

    def _setup_central_area(self):
        """Build content with QDockWidget left/right + center (top+bottom splitter)."""
        from PyQt5.QtWidgets import QStackedWidget
        # ── CENTER widget (vertical splitter: top area | bottom result) ──
        cw = QWidget()
        root = QVBoxLayout(cw); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self._bottom_splitter = QSplitter(Qt.Vertical)
        self._bottom_splitter.setHandleWidth(2)
        self._bottom_splitter.setStyleSheet("QSplitter::handle { background: #505050; }")

        self._setup_center_panel()    # diagram editor / image viewer / module results

        # Stacked widget to switch between start page and editor
        self._center_stack = QStackedWidget()
        self._start_page = StartPage()
        self._start_page.new_project_requested.connect(self._on_new_project)
        self._start_page.open_project_requested.connect(self._on_open_project)
        self._start_page.project_open_requested.connect(self._open_project)
        self._center_stack.addWidget(self._start_page)
        self._center_stack.addWidget(self._center_widget)
        self._center_stack.setCurrentIndex(0)  # start page visible initially

        self._bottom_splitter.addWidget(self._center_stack)

        # Bottom: tabbed result area
        self._setup_bottom_panel()
        bh = _ps.get_i("bottom_height", 160)
        self._bottom_splitter.setSizes([self.height() - bh - 80, bh])

        root.addWidget(self._bottom_splitter, 1)
        self.setCentralWidget(cw)

        # ── QDockWidget-based LEFT & RIGHT panels ──
        self._dock_mgr = DockManager(self)

        # Left dock: flow resources + log (matching WPF "流程资源" GroupBox)
        lw = QTabWidget()
        lw.setStyleSheet(_TAB_STYLE)
        self._toolbox = ToolboxPanel()
        lw.addTab(self._toolbox, "流程资源")
        self._log_panel = LogPanel()
        lw.addTab(self._log_panel, "日志")
        self._dock_mgr.register("left_toolbox", "流程资源 / 日志", lw,
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

    # ── CENTER PANEL (Image Preview | Module Results — matching WPF [图像][模块结果] tabs) ──

    def _setup_center_panel(self):
        """Center: Image viewer + module result parameters + image source list.

        Exact WPF alignment:
          - Top: TabControl [图像 | 模块结果]
          - Bottom: Expander for image/video source file list
        """
        w = QWidget()
        lo = QVBoxLayout(w); lo.setContentsMargins(0, 0, 0, 0); lo.setSpacing(0)

        self._center_tabs = QTabWidget()
        self._center_tabs.setStyleSheet(_TAB_STYLE)
        self._center_tabs.setTabPosition(QTabWidget.North)

        # Tab "图像" — Zoombox with image + overlays (matching WPF 图像 tab)
        self._img_panel = ImageViewerPanel()
        self._center_tabs.addTab(self._img_panel, "图像")

        # Tab "模块结果" — Property form + result panel (matching WPF 模块结果 tab)
        self._property_panel = PropertyPanel()
        self._center_tabs.addTab(self._property_panel, "模块结果")

        lo.addWidget(self._center_tabs, 1)

        # Image/video source file list at bottom (matching WPF Expander with horizontal ListBox)
        self._resource_panel = FlowResourcePanel()
        self._resource_panel.setFixedHeight(118)
        self._resource_panel.setVisible(False)
        lo.addWidget(self._resource_panel)

        self._center_widget = w

    # ── RIGHT PANEL (Diagram Flow Tabs) ──────────────────────────────

    def _setup_right_panel(self):
        """Right side: Diagram tab bar + Flow chart canvas (matching WPF TabControl + Zoombox)."""
        w = QWidget()
        lo = QVBoxLayout(w); lo.setContentsMargins(0, 0, 0, 0); lo.setSpacing(0)

        # Header row with diagram icon + add button (matching WPF tab header panel)
        header = QWidget()
        header.setFixedHeight(30)
        header.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        hl = QHBoxLayout(header); hl.setContentsMargins(8, 0, 4, 0); hl.setSpacing(4)

        icon_lbl = QLabel("")
        icon_lbl.setStyleSheet("color: #4caf50; font-size: 13px;")
        hl.addWidget(icon_lbl)
        title_lbl = QLabel("流程图")
        title_lbl.setStyleSheet("color: #dcdcdc; font-size: 12px; font-weight: bold;")
        hl.addWidget(title_lbl, 1)

        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setToolTip("新建流程图")
        add_btn.setStyleSheet("QPushButton { background: transparent; border: 1px solid #505050; border-radius: 2px; color: #dcdcdc; font-size: 14px; font-weight: bold; } QPushButton:hover { background: #3e3e42; border-color: #0078d4; }")
        add_btn.clicked.connect(self._on_add_diagram)
        hl.addWidget(add_btn)
        lo.addWidget(header)

        # Diagram tab bar
        self._diagram_tab_widget = QTabWidget()
        self._diagram_tab_widget.setStyleSheet(_TAB_STYLE)
        self._diagram_tab_widget.setTabsClosable(True)
        self._diagram_tab_widget.tabCloseRequested.connect(self._on_close_diagram_tab)
        self._diagram_tab_widget.currentChanged.connect(self._on_diagram_tab_changed)
        lo.addWidget(self._diagram_tab_widget)

        # Flow chart canvas — the main DiagramEditor (matching WPF Zoombox + DiagramPresenter)
        self._diagram_editor = DiagramEditorWidget()
        lo.addWidget(self._diagram_editor, 1)

        # Run controls row at bottom (matching WPF per-tab ▶ ■ ↺ buttons)
        ctrl = QWidget()
        ctrl.setFixedHeight(32)
        ctrl.setStyleSheet("background: #2d2d30; border-top: 1px solid #3f3f46;")
        clo = QHBoxLayout(ctrl); clo.setContentsMargins(4, 0, 4, 0); clo.setSpacing(4)

        for t, s in [("▶ 开始", self._on_run_workflow), ("■ 停止", self._on_stop_workflow),
                      ("↺ 重置", self._on_reset_workflow_view)]:
            b = QPushButton(t)
            b.setStyleSheet(_CMD_BTN)
            if s:
                b.clicked.connect(s)
            clo.addWidget(b)
        clo.addStretch()

        lo.addWidget(ctrl)
        self._diagram_right_widget = w

    def _on_add_diagram(self):
        """Add a new diagram to the project (mirrors WPF AddDiagramCommand)."""
        p = project_service.current_project
        if p:
            self._sync_workflow_to_project()
            d = p.add_diagram()
            self._bind_project_diagram(p)
            self._log_panel.info(f"新建流程图: {d.name}")
        else:
            name = f"流程图{self._diagram_tab_widget.count()+1}"
            self._diagram_tab_widget.addTab(QLabel(name), name)

    def _on_close_diagram_tab(self, idx):
        """Remove a diagram from the project (mirrors WPF DeleteDiagramCommand)."""
        p = project_service.current_project
        if p:
            self._sync_workflow_to_project()
            if 0 <= idx < len(p.diagrams):
                d = p.diagrams[idx]
                if p.delete_diagram(d):
                    self._bind_project_diagram(p)
                    self._log_panel.info(f"已删除流程图: {d.name}")
        else:
            if self._diagram_tab_widget.count() > 1:
                self._diagram_tab_widget.removeTab(idx)

    def _on_diagram_tab_changed(self, idx):
        """Switch selected diagram when tab changes."""
        p = project_service.current_project
        if p and 0 <= idx < len(p.diagrams):
            self._sync_workflow_to_project()
            p.selected_diagram_index = idx
            d = p.selected_diagram
            if d and d.workflow:
                self._workflow = d.workflow
                self._diagram_editor.bind_workflow(self._workflow)
            self._sync_proj_labels(p)

    # ── BOTTOM PANEL (History | Current Results | Help) ──────────────

    def _setup_bottom_panel(self):
        """Bottom tabbed area matching WPF's History/Current/Help tabs exactly."""
        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.setStyleSheet(_TAB_STYLE)
        self._bottom_tabs.setMinimumHeight(100)

        self._result_panel = ResultPanel()
        self._result_panel.set_image_viewer(self._img_panel.viewer)
        self._result_panel.node_jump_requested.connect(self._jump_to_node)
        self._bottom_tabs.addTab(self._result_panel._history_table, "历史结果")
        self._bottom_tabs.addTab(self._result_panel._current_table, "当前模块结果")
        self._help_panel = HelpPanel()
        self._bottom_tabs.addTab(self._help_panel, "帮助")

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

    def _on_history_double_click(self, row, col):
        """Double-click history entry to jump to the source node."""
        item = self._result_panel._history_table.item(row, 0) if hasattr(self, '_result_panel') else None
        if item:
            node_id = item.data(Qt.UserRole)
            if node_id:
                self._jump_to_node(node_id)

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
            self._bind_project_diagram(p)
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

    def _populate_help(self, node):
        self._help_panel.set_node(node)

    # ── Node Type Selected (Toolbox → Canvas) ────────────────────────

    def _on_node_type_selected(self, tn: str):
        if not self._workflow: return
        n = node_registry.create(tn)
        if n:
            g = self._get_group(tn)
            self._diagram_editor.add_node(n, group_name=g)
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

    def _show_start_page(self):
        """Show the welcome/start page, hide editor."""
        if hasattr(self, '_center_stack'):
            self._center_stack.setCurrentIndex(0)
        self._start_page.refresh_recent(project_service)
        self._project_loaded = False
        self._sync_proj_labels(None)

    def _show_editor(self):
        """Switch from start page to editor view."""
        if hasattr(self, '_center_stack'):
            self._center_stack.setCurrentIndex(1)
        self._project_loaded = True

    def _bind_project_diagram(self, project: ProjectItem):
        """Bind the selected diagram's workflow to the editor."""
        d = project.selected_diagram
        if d and d.workflow is None:
            d.workflow = WorkflowEngine(name=d.name)
        self._refresh_diagram_tabs(project)
        if d and d.workflow:
            self._workflow = d.workflow
            self._diagram_editor.bind_workflow(self._workflow)
        self._show_editor()
        self._sync_proj_labels(project)

    def _refresh_diagram_tabs(self, project: ProjectItem):
        """Sync the right-side tab widget with project diagrams."""
        tw = self._diagram_tab_widget
        tw.blockSignals(True)
        while tw.count() > 1:
            tw.removeTab(0)
        if tw.count() == 1:
            tw.removeTab(0)
        for i, d in enumerate(project.diagrams):
            tw.addTab(QWidget(), d.name)
            if i == project.selected_diagram_index:
                tw.setCurrentIndex(i)
        tw.blockSignals(False)

    def _on_new_project(self):
        p = project_service.new_project()
        self._bind_project_diagram(p)
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
            self._bind_project_diagram(p)
            self._select_node(None)
            self._log_panel.success(f"已打开: {path}")

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
            self._sync_workflow_to_project()
            project_service.save_as(p, path); self._log_panel.success(f"已保存至: {path}")

    def _sync_workflow_to_project(self):
        """Save editor state back to the current project diagram."""
        p = project_service.current_project
        if p and p.selected_diagram and self._workflow:
            self._diagram_editor.save_to_workflow()
            p.selected_diagram.workflow = self._workflow

    def _sync_proj_labels(self, project: ProjectItem | None):
        """Update caption and command bar project labels."""
        if project is None:
            name = "VisionFlow"
            dname = "无项目"
        else:
            name = project.display_name
            sd = project.selected_diagram
            dname = sd.name if sd else name
        self.setWindowTitle(f"{name} — VisionFlow")
        if hasattr(self, '_cap_proj_lbl'):
            self._cap_proj_lbl.setText(dname)
        if hasattr(self, '_cmd_proj_lbl'):
            self._cmd_proj_lbl.setText(dname)

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
            node = self._workflow.get_node_by_id(node_id)
            if node:
                self._select_node(node)
                self._center_tabs.setCurrentIndex(0)  # switch to image preview tab

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
        """Add a diagram tab manually (public API for backward compat)."""
        self._diagram_tabs[name] = workflow
        p = project_service.current_project
        if p:
            d = DiagramData(name=name)
            d.workflow = workflow
            p.diagrams.append(d)
            p.selected_diagram_index = len(p.diagrams) - 1
        self._diagram_tab_widget.addTab(QWidget(), name)
        self._diagram_tab_widget.setCurrentIndex(self._diagram_tab_widget.count() - 1)
        return name

    def remove_diagram_tab(self, name: str):
        """Remove a diagram tab by name."""
        p = project_service.current_project
        if p:
            for i, d in enumerate(p.diagrams):
                if d.name == name:
                    p.delete_diagram(d)
                    break
        for i in range(self._diagram_tab_widget.count()):
            if self._diagram_tab_widget.tabText(i) == name:
                self._diagram_tab_widget.removeTab(i)
                break

    def switch_to_diagram(self, name_or_index: str | int):
        """Switch to diagram by name or index."""
        if isinstance(name_or_index, int):
            idx = name_or_index
        else:
            idx = -1
            for i in range(self._diagram_tab_widget.count()):
                if self._diagram_tab_widget.tabText(i) == name_or_index:
                    idx = i
                    break
        if 0 <= idx < self._diagram_tab_widget.count():
            self._diagram_tab_widget.setCurrentIndex(idx)

    def _active_visual_target(self):
        return self._diagram_editor.view

    def _on_reset_workflow_view(self):
        if self._workflow:
            self._diagram_editor.bind_workflow(self._workflow)
            self._log_panel.info("已重置当前流程图视图")

    def _on_undo_diagram(self):
        if hasattr(self, '_diagram_editor'):
            self._diagram_editor._on_undo()

    def _on_redo_diagram(self):
        if hasattr(self, '_diagram_editor'):
            self._diagram_editor._on_redo()

    # ── Help ──────────────────────────────────────────────────────────

    def _on_about(self):
        QMessageBox.about(self, "关于 VisionFlow",
                          "<h2>VisionFlow 2.0</h2><p>视觉流程编辑器</p>"
                          "<p>移植自 WPF-VisionMaster (HeBianGu)</p>"
                          "<p>使用 Python + PyQt5 + OpenCV</p><hr>"
                          "<p>开源项目 | MIT License</p>")

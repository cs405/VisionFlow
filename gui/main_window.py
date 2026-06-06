"""Main window aligned toward WPF `MainWindow.xaml` region semantics.

重点对齐：
  - 左：流程资源 / 日志
  - 中：流程图多标签画布
  - 右：图像 / 模块结果 + 底部历史/当前/帮助
"""

import ctypes
import os
import json
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QAction,
    QLabel, QTabWidget, QMessageBox, QFileDialog, QApplication, QFormLayout,
    QPushButton, QFrame, QMenuBar, QMenu, QLineEdit, QStackedWidget, QTabBar,
    QDialog, QScrollArea, QGroupBox, QGridLayout, QCheckBox, QListWidgetItem,
    QListWidget
)
from PyQt5.QtCore import Qt, QTimer, QSettings, pyqtSignal, QEvent
from PyQt5.QtGui import QIcon, QPixmap, QCursor, QFont

from core.node_base import NodeBase, VisionNodeData, SrcFilesVisionNodeData, ROINodeData
from core.workflow import WorkflowEngine
from core.project import project_service, DiagramData, ProjectItem
from core.events import EventType, event_system
from core.registry import node_registry
from gui.font_icons import FontIcons, FontIconButton, FontIconTextBlock, FontIconToggleButton

from gui.theme import theme_manager, ThemePickerDialog
from gui.theme_data import resolve_colors
from gui.toolbox_panel import ToolboxPanel
from gui.property_panel import PropertyPanel
from gui.result_panel import ResultPanel
from gui.image_viewer import ImageViewerPanel
from gui.log_panel import LogPanel
from gui.widgets.grid_splitter_box import GridSplitterBox
from gui.flow_resource_panel import FlowResourcePanel
from gui.node_editor.editor_widget import DiagramEditorWidget
from gui.start_page import StartPage
from gui.help_panel import HelpPanel

# ── Windows frameless window border resize ──────────────────────────
WM_NCHITTEST = 0x0084
WM_NCCALCSIZE = 0x0083
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
HTCAPTION = 2

_BORDER = 8  # resize margin in pixels (WPF ResizeBorderThickness)


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("_pad", ctypes.c_uint),
        ("wParam", ctypes.c_ulonglong),
        ("lParam", ctypes.c_longlong),
    ]


class PanelState:
    GRP = "PanelState"

    def __init__(self):
        self.s = QSettings()

    def _k(self, key):
        return f"{self.GRP}/{key}"

    def get_i(self, key, default=0):
        return int(self.s.value(self._k(key), default) or default)

    def set_i(self, key, value):
        self.s.setValue(self._k(key), value)

    def get_b(self, key, default=True):
        value = self.s.value(self._k(key), default)
        return str(value).lower() == "true" if isinstance(value, str) else bool(value) if value is not None else default

    def set_b(self, key, value):
        self.s.setValue(self._k(key), "true" if value else "false")


_ps = PanelState()


class _Sep(QFrame):
    def __init__(self, vertical=True):
        super().__init__()
        self.setFrameShape(QFrame.VLine if vertical else QFrame.HLine)
        self.setStyleSheet("color: #505050;")
        if vertical:
            self.setFixedWidth(1)
        else:
            self.setFixedHeight(1)


def _hsep():
    return _Sep(True)


def _cmd_btn_qss():
    """Toolbar command button QSS — dynamic from theme."""
    return f"""
    QPushButton {{
        background: transparent;
        border: none;
        border-radius: 2px;
        padding: 5px 0;
        color: {theme_manager.color('text_primary').name()};
    }}
    QPushButton:hover {{ background: {theme_manager.color('bg_surface_hover').name()}; }}
    QPushButton:pressed {{ background: {theme_manager.color('accent').name()}; }}
"""

def _tab_qss():
    """Tab widget QSS — dynamic from theme. Tab text uses text_title for clarity."""
    c = theme_manager
    return f"""
    QTabWidget::pane {{ border: none; background: {c.color('bg_surface').name()}; }}
    QTabBar::tab {{
        background: {c.color('bg_surface_raised').name()};
        color: {c.color('text_title').name()};
        padding: 3px 8px;
        border: none;
        border-bottom: 2px solid transparent;
        font-size: 11px;
    }}
    QTabBar::tab:selected {{ background: {c.color('bg_surface').name()}; border-bottom: 2px solid {c.color('accent').name()}; }}
    QTabBar::tab:hover {{ background: {c.color('bg_surface_hover').name()}; }}
    QTabBar::close-button {{
        subcontrol-position: right;
        padding: 3px;
        margin-left: 4px;
    }}
    QTabBar::close-button:hover {{ background: #c42b1c; border-radius: 3px; }}
"""

_CMD_BTN = _cmd_btn_qss()
_TAB_STYLE = _tab_qss()


def find_child_by_tip(parent, tip):
    """Recursively find a visible widget by its toolTip."""
    try:
        for w in parent.findChildren(QWidget):
            try:
                if w.isVisible() and hasattr(w, 'toolTip') and w.toolTip() == tip:
                    return w
            except Exception:
                continue
    except Exception:
        pass
    return None


class _InlineStatusStrip(QWidget):
    def __init__(self, accent: str = "#4caf50", parent=None):
        super().__init__(parent)
        self._accent = accent
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)
        self.setStyleSheet("background: #1f1f1f; border-top: 1px solid #3f3f46;")

        self._icon = QLabel("●")
        self._icon.setStyleSheet(f"color: {accent}; font-weight: bold;")
        layout.addWidget(self._icon)

        self._label = QLabel("就绪")
        self._label.setStyleSheet("color: #d0d0d0; font-size: 11px;")
        layout.addWidget(self._label, 1)

    def set_status(self, text: str, color: str | None = None):
        self._label.setText(text)
        self._icon.setStyleSheet(f"color: {color or self._accent}; font-weight: bold;")


class _DiagramTabHeader(QWidget):
    rename_requested = pyqtSignal(str)
    run_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(0)

        self._name_edit = QLineEdit(name)
        self._name_edit.setFrame(False)
        self._name_edit.setFixedHeight(22)
        self._name_edit.setMinimumWidth(60)
        self._name_edit.editingFinished.connect(self._emit_rename)
        self._refresh_qss()
        layout.addWidget(self._name_edit, 1)

    def _refresh_qss(self):
        tm = theme_manager
        self._name_edit.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {tm.color('text_title').name()};"
            f" border: none; padding: 0 2px; font-family: 'Microsoft YaHei'; font-size: 12px; }}"
            f"QLineEdit:focus {{ border-bottom: 1px solid {tm.color('accent').name()}; }}"
        )

    def _emit_rename(self):
        self.rename_requested.emit(self._name_edit.text().strip())

    def set_name(self, name: str):
        if self._name_edit.text() != name:
            self._name_edit.setText(name)

    def set_active(self, active: bool):
        pass


class _SettingsDialog(QDialog):
    """Settings dialog -- WPF SettingViewPresenter 1:1 port.

    Layout: QTabWidget group tabs + NavigationBox per tab + bottom buttons.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统设置")
        self.setMinimumSize(720, 500)
        self._original_theme = theme_manager.current_theme_id
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        self._group_tabs = QTabWidget()
        layout.addWidget(self._group_tabs, 1)
        self._build_theme_tab()
        self._build_basic_tab()
        self._build_display_tab()
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(10, 8, 10, 8)
        btn_row.addStretch()
        restore_btn = QPushButton("恢复默认")
        restore_btn.clicked.connect(self._on_restore_default)
        btn_row.addWidget(restore_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(cancel_btn)
        ok_btn = QPushButton("确定")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    # -- NavigationBox helper (WPF: left nav list + right content stack) --
    def _make_nav_box(self):
        box = QSplitter(Qt.Horizontal)
        nav = QListWidget()
        nav.setFixedWidth(130)
        nav.setSpacing(0)
        stack = QStackedWidget()
        box.addWidget(nav)
        box.addWidget(stack)
        nav.currentRowChanged.connect(stack.setCurrentIndex)
        return box, nav, stack

    @staticmethod
    def _add_nav_item(nav, stack, name, page):
        nav.addItem(QListWidgetItem(name))
        stack.addWidget(page)

    # -- Tab 1: 主题 (WPF ThemeOptions) --
    def _build_theme_tab(self):
        box, nav, stack = self._make_nav_box()
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QScrollArea.NoFrame)
        pw = QWidget()
        vl = QVBoxLayout(pw)
        vl.setSpacing(10)
        vl.addWidget(QLabel("选择颜色主题，即时预览："))
        groups = {}
        for t in theme_manager.available_themes:
            groups.setdefault(t.group, []).append(t)
        for group_name in ["强力推荐", "纯色", "外部主题"]:
            if group_name not in groups:
                continue
            gb = QGroupBox(group_name)
            grid = QGridLayout()
            grid.setSpacing(8)
            for i, tdef in enumerate(groups[group_name]):
                card = self._make_theme_card(tdef)
                grid.addWidget(card, i // 2, i % 2)
            gb.setLayout(grid)
            vl.addWidget(gb)
        vl.addStretch()
        page.setWidget(pw)
        self._add_nav_item(nav, stack, "颜色主题", page)
        nav.setCurrentRow(0)
        self._group_tabs.addTab(box, "主题")

    def _make_theme_card(self, tdef):
        c = resolve_colors(tdef)
        card = QFrame()
        card.setFixedSize(200, 100)
        card.setCursor(Qt.PointingHandCursor)
        card.setToolTip(f"{tdef.name} - {tdef.description}")
        is_current = tdef.id == theme_manager.current_theme_id
        border = c.get("accent", "#3399FF") if is_current else c.get("border", "#555")
        bw = 2 if is_current else 1
        card.setStyleSheet(
            f"QFrame {{ background: {c.get('bg_surface','#333')}; "
            f"border: {bw}px solid {border}; border-radius: 6px; }}")
        card.mousePressEvent = lambda e, tid=tdef.id: self._on_theme_select(tid)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(8, 6, 8, 6)
        inner.setSpacing(3)
        p = QLabel(f"[{tdef.prompt or tdef.name}]")
        p.setAlignment(Qt.AlignCenter)
        p.setStyleSheet(f"color: {c.get('text_title','#ccc')}; font-weight: bold; "
                        f"border: none; background: transparent;")
        inner.addWidget(p)
        n = QLabel(tdef.name)
        n.setAlignment(Qt.AlignCenter)
        n.setStyleSheet(f"color: {c.get('text_primary','#ccc')}; border: none; background: transparent;")
        inner.addWidget(n)
        d = QLabel(tdef.description or "")
        d.setAlignment(Qt.AlignCenter)
        d.setWordWrap(True)
        d.setStyleSheet(f"color: {c.get('text_secondary','#999')}; font-size: 9px; "
                        f"border: none; background: transparent;")
        inner.addWidget(d)
        return card

    def _on_theme_select(self, theme_id):
        theme_manager.set_theme(theme_id)

    # -- Tab 2: 基本设置 (WPF GroupBase) --
    def _build_basic_tab(self):
        box, nav, stack = self._make_nav_box()
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QScrollArea.NoFrame)
        pw = QWidget()
        vl = QVBoxLayout(pw)
        gb = QGroupBox("通用设置")
        form = QFormLayout(gb)
        self._chk_auto_start = QCheckBox()
        form.addRow("开机自动启动：", self._chk_auto_start)
        self._chk_tray = QCheckBox()
        form.addRow("任务栏显示图标：", self._chk_tray)
        self._chk_theme_btn = QCheckBox()
        form.addRow("显示主题按钮：", self._chk_theme_btn)
        vl.addWidget(gb)
        vl.addStretch()
        page.setWidget(pw)
        self._add_nav_item(nav, stack, "通用设置", page)
        nav.setCurrentRow(0)
        self._group_tabs.addTab(box, "基本设置")

    # -- Tab 3: 显示设置 (WPF GroupStyle) --
    def _build_display_tab(self):
        box, nav, stack = self._make_nav_box()
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QScrollArea.NoFrame)
        pw = QWidget()
        vl = QVBoxLayout(pw)
        gb = QGroupBox("画布设置")
        form = QFormLayout(gb)
        self._chk_show_grid = QCheckBox()
        form.addRow("显示画布网格：", self._chk_show_grid)
        vl.addWidget(gb)
        vl.addStretch()
        page.setWidget(pw)
        self._add_nav_item(nav, stack, "画布设置", page)
        nav.setCurrentRow(0)
        self._group_tabs.addTab(box, "显示设置")

    # -- Persistence (WPF SettableBase.Load/Save) --
    def _config_path(self):
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "app_config.json")

    def _load_settings(self):
        try:
            with open(self._config_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        self._chk_auto_start.setChecked(data.get("auto_start", False))
        self._chk_tray.setChecked(data.get("show_tray", True))
        self._chk_theme_btn.setChecked(data.get("show_theme_btn", True))
        self._chk_show_grid.setChecked(data.get("show_grid", True))

    def _save_settings(self):
        data = {
            "auto_start": self._chk_auto_start.isChecked(),
            "show_tray": self._chk_tray.isChecked(),
            "show_theme_btn": self._chk_theme_btn.isChecked(),
            "show_grid": self._chk_show_grid.isChecked(),
        }
        with open(self._config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _on_restore_default(self):
        self._chk_auto_start.setChecked(False)
        self._chk_tray.setChecked(True)
        self._chk_theme_btn.setChecked(False)
        self._chk_show_grid.setChecked(True)
        if self._original_theme != theme_manager.current_theme_id:
            theme_manager.set_theme(self._original_theme)

    def _on_cancel(self):
        if self._original_theme != theme_manager.current_theme_id:
            theme_manager.set_theme(self._original_theme)
        self._load_settings()
        self.reject()

    def accept(self):
        self._save_settings()
        super().accept()


class MainWindow(QMainWindow):
    """主窗口：按 WPF `MainWindow.xaml` 的区域语义重构。

    Args:
        ctx: AppContext DI container. If None, uses get_app_context() fallback.
    """

    def __init__(self, ctx=None):
        super().__init__()
        if ctx is None:
            from services.app_context import get_app_context
            ctx = get_app_context()
        self._ctx = ctx
        self._workflow: WorkflowEngine | None = None
        self._selected_node: NodeBase | None = None
        self._diagram_editor: DiagramEditorWidget | None = None
        self._diagram_pages: dict[str, QWidget] = {}
        self._diagram_headers: dict[str, _DiagramTabHeader] = {}
        self._project_loaded = False
        self._left_panel_visible = True
        self._right_panel_visible = True
        self._saved_right_width = _ps.get_i("right_width", 420)
        self._saved_right_width = _ps.get_i("right_width", 420)

        self._setup_window()
        self._setup_caption_bar()
        self._setup_main_surface()
        self._setup_status_bar()
        self._wire_signals()
        self._connect_events()

        self._clock = QTimer(self)
        self._clock.timeout.connect(self._update_clock)
        self._clock.start(1000)

        self._show_start_page()
        self._apply_settings()
        self._load_templates_on_startup()

    def _setup_window(self):
        self.setWindowTitle("VisionFlow — VisionFlow")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        width = _ps.get_i("window_width", 1460)
        height = _ps.get_i("window_height", 900)
        self.resize(width, height)
        self.setMinimumSize(1180, 720)
        self.setPalette(theme_manager.colors.to_palette())
        self.setStyleSheet(theme_manager.get_stylesheet())
        # WPF SelectionChanged → RefreshThemeCommand: apply theme immediately
        theme_manager.theme_changed.connect(lambda _: self._apply_theme())
        # WPF SystemKeys.FontFamily = Microsoft YaHei
        font = QFont("Microsoft YaHei", 9)
        self.setFont(font)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        screen = QApplication.primaryScreen()
        if screen is not None:
            geometry = screen.geometry()
            self.move((geometry.width() - width) // 2, (geometry.height() - height) // 2)

        self._init_dwm_shadow()

    def _init_dwm_shadow(self):
        """Extend DWM frame into client area for native drop-shadow."""
        try:
            hwnd = int(self.winId())
            margins = (ctypes.c_int * 4)(-1, -1, -1, -1)
            ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, margins)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._init_dwm_shadow()

    def changeEvent(self, event):
        """Toggle Maximize ↔ Restore visibility on window state change (WPF triggers)."""
        if event.type() == QEvent.WindowStateChange:
            maximized = self.isMaximized()
            if hasattr(self, '_max_btn'):
                self._max_btn.setVisible(not maximized)
            if hasattr(self, '_restore_btn'):
                self._restore_btn.setVisible(maximized)
        super().changeEvent(event)

    def _setup_caption_bar(self):
        """1:1 port of WPF CaptionTemplate lines 22-203.

        Outer DockPanel (DataContext=Project):
          Separator(H=20, Right) | ActionDockPanel(Right) | UniformGrid(Rows=2)
            Row0: DockPanel:  Menu(Left) | "项目名称:XXX"(Center)
            Row1: Border(top) | DockPanel(LastChildFill=False): 4 button groups
        """
        bar = QWidget()
        bar.setFixedHeight(85)
        bar.setStyleSheet("background: #1e1e1e;")

        # ── WPF outer DockPanel (line 24) ──
        outer = QHBoxLayout(bar)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ══════════ Column 0: Icon + Title (Framework MainWindow.xaml lines 108-133) ══════════
        col0 = QWidget()
        col0_layout = QHBoxLayout(col0)
        col0_layout.setContentsMargins(10, 20, 0, 20)  # WPF TitleMargin="10 20"
        col0_layout.setSpacing(0)

        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "logo.png")
        if os.path.exists(logo_path):
            logo = QLabel()
            logo.setPixmap(QPixmap(logo_path).scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo.setStyleSheet("padding: 0 5px 0 0;")  # WPF Margin="0,0,5,0"
            col0_layout.addWidget(logo)

        title_lbl = QLabel("VisionFlow")
        title_lbl.setStyleSheet("color: #dcdcdc; font-size: 30px; font-weight: bold; padding: 0 0 0 5px;")
        col0_layout.addWidget(title_lbl)

        outer.addWidget(col0)

        # ══════════ UniformGrid Rows="2" Margin="0,2" (lines 41-42) — fills remaining space ══════════
        grid = QWidget()
        grid_layout = QVBoxLayout(grid)
        grid_layout.setContentsMargins(0, 2, 0, 2)
        grid_layout.setSpacing(0)

        # ---- Row 0: DockPanel with Menu(left) + "项目名称:XXX"(center) (lines 43-145) ----
        row0 = QWidget()
        r0 = QHBoxLayout(row0)
        r0.setContentsMargins(8, 0, 0, 0)
        r0.setSpacing(0)

        # Menu — HorizontalAlignment="Left", Background="Transparent", Margin="0,1" (lines 44-47)
        menu_bar = QMenuBar()
        menu_bar.setStyleSheet(
            "QMenuBar { background: transparent; color: #dcdcdc; padding: 0; margin: 1px 0; }"
            "QMenuBar::item { padding: 6px 12px; background: transparent; }"
            "QMenuBar::item:selected { background: #3e3e42; }"
            "QMenu { background: #2d2d30; color: #dcdcdc; border: 1px solid #505050; }"
            "QMenu::item { padding: 6px 30px 6px 16px; }"
            "QMenu::item:selected { background: #0078d4; }"
            "QMenu::separator { height: 1px; background: #505050; margin: 4px 10px; }"
        )
        self._build_menus(menu_bar)
        r0.addWidget(menu_bar)  # NO stretch → left-aligned (WPF HorizontalAlignment="Left")

        # "项目名称：XXX" — Margin="10,0", HorizontalAlignment="Center" (lines 137-144)
        r0.addStretch(1)
        r0.addWidget(self._lbl("项目名称：", "#c8c8c8", 12, pad="0 4px"))
        self._cap_proj_lbl = self._lbl("无项目", "#0078d4", 12, bold=True, pad="0 12px")
        r0.addWidget(self._cap_proj_lbl)
        r0.addStretch(1)

        grid_layout.addWidget(row0)

        # ---- Row 1: Border(top) + DockPanel toolbar (lines 146-200) ----
        row1 = QWidget()
        row1.setStyleSheet("background:#2d2d30; border-top:1px solid #3f3f46;")
        r1 = QHBoxLayout(row1)
        r1.setContentsMargins(0, 1, 0, 0)  # WPF Margin="0,1" (line 149)
        r1.setSpacing(0)

        # Inner DockPanel LastChildFill="False" → 4 groups (lines 149-199)
        toolbar = QWidget()
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(6, 3, 6, 3)
        tb.setSpacing(2)

        # Group 1 — New | Open | Edit | Save (lines 155-158)
        for icon, tip, slot in [
            (FontIcons.Page,                "新建项目", self._on_new_project),
            (FontIcons.OpenFolderHorizontal, "打开项目", self._on_open_project),
            (FontIcons.Edit,                 "编辑项目", self._on_edit_project),
            (FontIcons.Save,                 "保存项目", self._on_save_project),
        ]:
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            btn.setStyleSheet(_CMD_BTN)
            btn.clicked.connect(slot)
            tb.addWidget(btn)
        tb.addWidget(_hsep())

        # Group 2 — project-level commands (VisionProjectItemBase, 7 commands) (lines 161-175)
        self._tool_project_cmds = QWidget()
        self._tool_project_cmds.setLayout(QHBoxLayout())
        self._tool_project_cmds.layout().setContentsMargins(0, 0, 0, 0)
        self._tool_project_cmds.layout().setSpacing(2)
        for icon, tip, slot in [
            (FontIcons.Add,           "新建流程图",           self._on_add_diagram),
            (FontIcons.Ethernet,      "运行模式",             self._on_cycle_run_mode),
            (FontIcons.Copy,          "重复流程图",           self._on_duplicate_diagram),
            (FontIcons.DictionaryAdd, "从模板添加流程图",     self._on_add_from_template),
            (FontIcons.Manage,        "模板管理",             self._on_manage_templates),
            (FontIcons.SaveAs,        "流程图另存为模板",     self._on_save_as_template),
            (FontIcons.Cancel,        "删除流程图",           self._on_delete_diagram),
        ]:
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            btn.setStyleSheet(_CMD_BTN)
            if slot:
                btn.clicked.connect(slot)
            self._tool_project_cmds.layout().addWidget(btn)
        tb.addWidget(self._tool_project_cmds)
        tb.addWidget(_hsep())

        # Group 3 — diagram commands (DiagramDataBase hierarchy, 9 commands) (lines 179-193)
        self._tool_diagram_cmds = QWidget()
        self._tool_diagram_cmds.setLayout(QHBoxLayout())
        self._tool_diagram_cmds.layout().setContentsMargins(0, 0, 0, 0)
        self._tool_diagram_cmds.layout().setSpacing(2)

        for icon, tip, slot in [
            (FontIcons.Replay,         "开始",         self._on_run_workflow),
            (FontIcons.Location,       "停止",         self._on_stop_workflow),
            (FontIcons.Refresh,        "重置",         self._on_reset_workflow_view),
            (FontIcons.EditMirrored,   "编辑面板",     None),
            (FontIcons.View,           "查看面板",     None),
            (FontIcons.DisconnectDrive,"删除选中节点", None),
            (FontIcons.Delete,         "清空节点",     None),
            (FontIcons.Zoom,           "缩放定位",     None),
            (FontIcons.AlignCenter,    "对齐节点",     None),
        ]:
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            btn.setStyleSheet(_CMD_BTN)
            if slot:
                btn.clicked.connect(slot)
            self._tool_diagram_cmds.layout().addWidget(btn)
        # Keep _run_btn/_stop_btn refs for workflow state handlers
        self._run_btn = self._tool_diagram_cmds.layout().itemAt(0).widget()
        self._stop_btn = self._tool_diagram_cmds.layout().itemAt(1).widget()

        tb.addWidget(self._tool_diagram_cmds)
        tb.addWidget(_hsep())

        # Group 4 — View | TabEdit (lines 195-198)
        self._tool_view_btn = FontIconButton(FontIcons.View, tooltip="查看", font_size=16)
        self._tool_view_btn.setStyleSheet(_CMD_BTN)
        tb.addWidget(self._tool_view_btn)

        tb.addStretch(1)
        r1.addWidget(toolbar)
        grid_layout.addWidget(row1)

        outer.addWidget(grid, 1)  # stretch=1 → fills remaining space (WPF LastChildFill)

        # ══════════ Right-docked action buttons — WPF FontIconButtonKeys.Command (lines 28-39) ══════════
        # Same style as Row 2 toolbar — _CMD_BTN matches WPF ButtonKeys.Default + FontIconButtonKeys.Default
        # Color → Setting (lines 30-34) — WPF ShowColorThemeViewCommand
        for icon, tip, slot in [
            (FontIcons.Color,   "颜色主题", self._on_show_theme_dialog),
            (FontIcons.Setting, "设置",     self._on_open_settings),
        ]:
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            btn.setStyleSheet(_CMD_BTN)
            if slot:
                btn.clicked.connect(slot)
            outer.addWidget(btn)

        # ISwitchThemeViewPresenter — Brightness(sun)=checked, QuietHours(moon)=unchecked (line 35)
        self._theme_toggle = FontIconToggleButton(FontIcons.Brightness, FontIcons.QuietHours, font_size=16)
        self._theme_toggle.setToolTip("切换明/暗主题")
        self._theme_toggle.setStyleSheet(_CMD_BTN + """
            FontIconToggleButton:checked { color: #dcdcdc; }
            FontIconToggleButton:checked:hover { background: #3e3e42; }
        """)
        self._theme_toggle.setChecked(theme_manager.is_dark)
        self._theme_toggle.toggled.connect(lambda _: self._on_toggle_theme())
        outer.addWidget(self._theme_toggle)

        # About → Guide (lines 36-39)
        for icon, tip, slot in [
            (FontIcons.Info,  "关于",     self._on_about),
            (FontIcons.Smartcard, "新手向导", self._on_open_guide),
        ]:
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            btn.setStyleSheet(_CMD_BTN)
            if slot:
                btn.clicked.connect(slot)
            outer.addWidget(btn)

        # ══════════ Rightmost 20px separator (lines 25-27) ══════════
        sep20 = QFrame()
        sep20.setFrameShape(QFrame.VLine)
        sep20.setStyleSheet("color: #505050;")
        sep20.setFixedSize(1, 20)
        outer.addWidget(sep20)

        # ══════════ Window chrome buttons (from Framework/MainWindow.xaml Column 2) ══════════
        _WIN = (
            "QPushButton { background:transparent; border:none; color:#999;"
            " font-family:'Segoe Fluent Icons','Segoe MDL2 Assets','Segoe UI Symbol';"
            " font-size:14px; min-width:46px; min-height:32px; }"
            "QPushButton:hover { background:#3e3e42; color:#dcdcdc; }"
            "QPushButton#close_btn:hover { background:#e81123; color:white; }"
        )
        for icon, tip, slot, btn_attr in [
            (FontIcons.ChromeMinimize, "最小化", self.showMinimized, None),
            (FontIcons.ChromeMaximize, "最大化", self._toggle_max, "_max_btn"),
            (FontIcons.ChromeRestore,  "还原",   self._toggle_max, "_restore_btn"),
            (FontIcons.ChromeClose,    "关闭",   self._on_close_window, None),
        ]:
            btn = QPushButton(icon)
            btn.setToolTip(tip)
            btn.setStyleSheet(_WIN)
            if icon == FontIcons.ChromeClose:
                btn.setObjectName("close_btn")
            btn.clicked.connect(slot)
            if btn_attr:
                setattr(self, btn_attr, btn)
            outer.addWidget(btn)
        self._restore_btn.hide()

        # ── drag support ──
        self._caption_bar = bar
        bar.installEventFilter(self)
        for child in bar.findChildren(QWidget):
            child.installEventFilter(self)

        self.setMenuWidget(bar)

    def eventFilter(self, obj, event):
        """Intercept mouse events on caption widgets for window drag / double-click."""
        etype = event.type()
        if etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            if self._is_interactive_widget(obj):
                return False
            self._drag_pos = event.globalPos()
            self._caption_bar.grabMouse()
            return True

        if etype == QEvent.MouseMove and hasattr(self, '_drag_pos'):
            delta = event.globalPos() - self._drag_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self._drag_pos = event.globalPos()
            return True

        if etype == QEvent.MouseButtonRelease and hasattr(self, '_drag_pos'):
            del self._drag_pos
            self._caption_bar.releaseMouse()
            return True

        if etype == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
            if not self._is_interactive_widget(obj):
                self._toggle_max()
                return True

        return False

    def _is_caption_descendant(self, widget) -> bool:
        """Return True if *widget* is the caption bar or any of its descendants."""
        while widget is not None:
            if widget is self._caption_bar:
                return True
            widget = widget.parentWidget()
        return False

    def _is_interactive_widget(self, widget) -> bool:
        """Return True if *widget* is a button/menu-item that needs mouse events."""
        w = widget
        while w is not None and w is not self._caption_bar:
            if isinstance(w, QPushButton):
                return True
            if isinstance(w, QMenuBar):
                cp = w.mapFromGlobal(QCursor.pos())
                return w.actionAt(cp) is not None
            if isinstance(w, QLineEdit):
                return True
            w = w.parentWidget()
        return False

    def nativeEvent(self, eventType, message):
        """Handle WM_NCHITTEST (resize handles) + WM_NCCALCSIZE (remove white border)."""
        if eventType != b"windows_generic_MSG":
            return False, 0

        msg_ptr = ctypes.cast(int(message), ctypes.POINTER(_MSG))
        msg = msg_ptr.contents

        # Remove non-client area to eliminate frameless-window white border
        if msg.message == WM_NCCALCSIZE:
            return True, 0

        if msg.message != WM_NCHITTEST:
            return False, 0

        # Convert screen coords from lParam (handles sign extension for multi-monitor)
        x_raw = msg.lParam & 0xFFFF
        y_raw = (msg.lParam >> 16) & 0xFFFF
        x = x_raw - 65536 if x_raw > 32767 else x_raw
        y = y_raw - 65536 if y_raw > 32767 else y_raw

        g = self.geometry()
        on_left = x < g.x() + _BORDER
        on_right = x > g.x() + g.width() - _BORDER
        on_top = y < g.y() + _BORDER
        on_bottom = y > g.y() + g.height() - _BORDER

        if on_top and on_left:
            return True, HTTOPLEFT
        if on_top and on_right:
            return True, HTTOPRIGHT
        if on_bottom and on_left:
            return True, HTBOTTOMLEFT
        if on_bottom and on_right:
            return True, HTBOTTOMRIGHT
        if on_left:
            return True, HTLEFT
        if on_right:
            return True, HTRIGHT
        if on_top:
            return True, HTTOP
        if on_bottom:
            return True, HTBOTTOM

        return False, 0

    def _setup_main_surface(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._root_stack = QStackedWidget()
        self._start_page = StartPage()
        self._start_page.new_project_requested.connect(self._on_new_project)
        self._start_page.open_project_requested.connect(self._on_open_project)
        self._start_page.project_open_requested.connect(self._open_project)
        self._root_stack.addWidget(self._start_page)

        self._editor_surface = QWidget()
        editor_layout = QVBoxLayout(self._editor_surface)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        self._left_box = self._build_left_panel()

        self._center_right_splitter = QSplitter(Qt.Horizontal)
        self._center_right_splitter.setHandleWidth(2)
        self._center_right_splitter.setStyleSheet("QSplitter::handle { background: #505050; }")

        self._diagram_panel = self._build_diagram_panel()
        self._center_right_splitter.addWidget(self._diagram_panel)

        self._right_panel = self._build_side_panel()
        self._right_panel.setFixedWidth(850)
        self._center_right_splitter.addWidget(self._right_panel)

        # WPF Grid layout: GridSplitterBox | center+right splitter
        workspace = QWidget()
        ws_layout = QHBoxLayout(workspace)
        ws_layout.setContentsMargins(0, 0, 0, 0)
        ws_layout.setSpacing(0)
        ws_layout.addWidget(self._left_box)
        ws_layout.addWidget(self._center_right_splitter, 1)
        editor_layout.addWidget(workspace, 1)

        self._root_stack.addWidget(self._editor_surface)
        root_layout.addWidget(self._root_stack, 1)
        self.setCentralWidget(root)

        self._apply_splitter_state()

    def _build_side_panel(self):
        self._center_splitter = QSplitter(Qt.Vertical)
        self._center_splitter.setHandleWidth(2)
        self._center_splitter.setStyleSheet("QSplitter::handle { background: #505050; }")
        center_panel = self._build_center_panel()
        center_panel.setFixedHeight(800)
        self._center_splitter.addWidget(center_panel)
        self._center_splitter.addWidget(self._build_bottom_panel())

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._center_splitter, 1)
        return panel

    def _build_left_panel(self):
        self._toolbox = ToolboxPanel()
        self._log_panel = LogPanel()  # hidden, kept for API compatibility

        box = GridSplitterBox()
        box.set_content(self._toolbox)
        return box

    def _build_center_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._center_tabs = QTabWidget()
        self._center_tabs.setStyleSheet(_TAB_STYLE)

        self._img_panel = ImageViewerPanel()
        self._center_tabs.addTab(self._img_panel, "图像")

        module_page = QWidget()
        module_layout = QVBoxLayout(module_page)
        module_layout.setContentsMargins(0, 0, 0, 0)
        module_layout.setSpacing(0)

        self._module_result_title = QLabel("模块名称 <未选择>")
        self._module_result_title.setStyleSheet(
            "background: #2d2d30; color: #dcdcdc; padding: 8px 10px;"
            "font-size: 12px; font-weight: bold; border-bottom: 1px solid #3f3f46;"
        )
        module_layout.addWidget(self._module_result_title)

        self._property_panel = PropertyPanel()
        module_layout.addWidget(self._property_panel, 1)
        self._center_tabs.addTab(module_page, "模块结果")

        layout.addWidget(self._center_tabs, 1)

        self._resource_panel = FlowResourcePanel()
        self._resource_panel.setFixedHeight(118)
        self._resource_panel.setVisible(False)
        layout.addWidget(self._resource_panel)

        self._side_status_strip = _InlineStatusStrip("#4caf50")
        self._side_status_strip.set_status("等待选择节点")
        layout.addWidget(self._side_status_strip)
        return panel

    def _build_bottom_panel(self):
        # Use ResultPanel's built-in 3-tab layout (历史/当前/帮助) — WPF aligned
        self._result_panel = ResultPanel()
        self._result_panel.set_image_viewer(self._img_panel.viewer)
        self._result_panel.node_jump_requested.connect(self._jump_to_node)
        self._result_panel.image_update_requested.connect(self._on_result_image_update)
        # Wrap in a container so toggle/corner button works
        self._bottom_tabs = self._result_panel._tabs
        self._bottom_tabs.setStyleSheet(_TAB_STYLE)
        self._bottom_tabs.setMinimumHeight(120)

        self._help_panel = HelpPanel()  # keep for backward-compat direct usage

        self._bottom_visible = True
        self._bottom_toggle = QPushButton("▼")
        self._bottom_toggle.setFixedSize(24, 18)
        self._bottom_toggle.setStyleSheet(
            "QPushButton { background: #2d2d30; border: 1px solid #3f3f46; color: #999; font-size: 9px; }"
            "QPushButton:hover { color: #dcdcdc; }"
        )
        self._bottom_toggle.clicked.connect(self._toggle_bottom)
        self._bottom_tabs.setCornerWidget(self._bottom_toggle, Qt.TopLeftCorner)
        return self._bottom_tabs

    def _build_diagram_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._diagram_tab_widget = QTabWidget()
        self._diagram_tab_widget.setStyleSheet(_TAB_STYLE)
        self._diagram_tab_widget.setTabsClosable(False)
        self._diagram_tab_widget.tabCloseRequested.connect(self._on_close_diagram_tab)
        self._diagram_tab_widget.currentChanged.connect(self._on_diagram_tab_changed)
        self._diagram_tab_widget.setDocumentMode(True)
        layout.addWidget(self._diagram_tab_widget, 1)

        self._diagram_status_strip = _InlineStatusStrip("#4caf50")
        self._diagram_status_strip.set_status("流程图就绪")
        layout.addWidget(self._diagram_status_strip)
        return panel

    def _setup_status_bar(self):
        status = self.statusBar()
        status.setStyleSheet(
            "QStatusBar { background: #007acc; color: white; padding: 2px 8px; font-size: 11px; }"
            "QStatusBar::item { border: none; }"
        )

        self._state_lbl = QLabel(f"{FontIcons.Completed} 空闲")
        self._state_lbl.setStyleSheet("color: #4caf50; font-weight: bold;")
        status.addWidget(self._state_lbl)
        status.addWidget(_hsep())

        self._msg_lbl = QLabel("就绪")
        status.addWidget(self._msg_lbl, 1)
        status.addWidget(_hsep())

        self._node_cnt_lbl = QLabel("节点: 0")
        status.addPermanentWidget(self._node_cnt_lbl)
        self._time_lbl = QLabel("")
        status.addPermanentWidget(self._time_lbl)

    def _wire_signals(self):
        self._toolbox.node_type_selected.connect(self._on_node_type_selected)
        self._property_panel.property_changed.connect(self._on_property_changed)
        self._property_panel.set_image_viewer(self._img_panel.viewer)
        self._resource_panel.file_selected.connect(self._on_resource_file_selected)
        self._resource_panel.file_double_clicked.connect(self._on_resource_file_double_clicked)

    def _connect_events(self):
        event_system.subscribe(EventType.NODE_SELECTED, self._on_ev_node_sel)
        event_system.subscribe(EventType.DIAGRAM_CHANGED, self._on_ev_diag_chg)
        event_system.subscribe(EventType.WORKFLOW_STARTED, self._on_wf_start)
        event_system.subscribe(EventType.WORKFLOW_COMPLETED, self._on_wf_done)
        event_system.subscribe(EventType.WORKFLOW_ERROR, self._on_wf_err)
        event_system.subscribe(EventType.PROJECT_LOADED, self._on_proj_load)
        event_system.subscribe(EventType.PROJECT_SAVED, self._on_proj_save)

    def closeEvent(self, event):
        self._sync_workflow_to_project()
        _ps.set_i("window_width", self.width())
        _ps.set_i("window_height", self.height())
        if hasattr(self, "_left_box"):
            _ps.set_i("left_width", self._left_box.menu_width())
            inner_sizes = self._center_right_splitter.sizes()
            if len(inner_sizes) >= 2 and self._right_panel_visible:
                _ps.set_i("right_width", inner_sizes[1])
            center_sizes = self._center_splitter.sizes()
            if len(center_sizes) >= 2:
                _ps.set_i("bottom_height", center_sizes[1])
        _ps.set_b("left_visible", self._left_panel_visible)
        _ps.set_b("right_visible", self._right_panel_visible)
        self._clock.stop()
        super().closeEvent(event)

    def _apply_splitter_state(self):
        left_width = _ps.get_i("left_width", 280)
        right_width = _ps.get_i("right_width", 420)
        bottom_height = _ps.get_i("bottom_height", 180)

        self._left_box.set_menu_width(left_width)
        self._center_right_splitter.setSizes([max(640, self.width() - left_width - right_width), right_width])
        self._center_splitter.setSizes([max(380, self.height() - bottom_height - 140), bottom_height])

        self._left_panel_visible = _ps.get_b("left_visible", True)
        self._right_panel_visible = _ps.get_b("right_visible", True)
        if not self._left_panel_visible:
            self.toggle_left_panel()
        if not self._right_panel_visible:
            self.toggle_right_panel()

    def _lbl(self, text, color, size, bold=False, pad=""):
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {color}; font-size: {size}px; {'font-weight: bold;' if bold else ''} padding: {pad};"
        )
        return label

    def _toggle_max(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def _build_menus(self, menu_bar: QMenuBar):
        file_menu = menu_bar.addMenu("文件(&F)")
        for text, slot, shortcut in [
            ("新建项目(&N)", self._on_new_project, "Ctrl+N"),
            ("打开项目(&O)...", self._on_open_project, "Ctrl+O"),
            ("保存项目(&S)", self._on_save_project, "Ctrl+S"),
            ("另存为(&A)...", self._on_save_as_project, "Ctrl+Shift+S"),
        ]:
            action = QAction(text, self)
            action.setShortcut(shortcut)
            action.triggered.connect(slot)
            file_menu.addAction(action)
        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu("最近的项目(&R)")
        self._recent_menu.aboutToShow.connect(self._refresh_recent)
        file_menu.addSeparator()
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self._on_close_window)
        file_menu.addAction(exit_action)

        edit_menu = menu_bar.addMenu("编辑(&E)")
        undo_action = QAction("撤销(&U)", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self._on_undo_diagram)
        edit_menu.addAction(undo_action)
        redo_action = QAction("重做(&R)", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self._on_redo_diagram)
        edit_menu.addAction(redo_action)

        run_menu = menu_bar.addMenu("运行(&R)")
        run_action = QAction("运行流程(&F)", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self._on_run_workflow)
        run_menu.addAction(run_action)
        stop_action = QAction("停止(&S)", self)
        stop_action.setShortcut("Shift+F5")
        stop_action.triggered.connect(self._on_stop_workflow)
        run_menu.addAction(stop_action)

        system_menu = menu_bar.addMenu("系统(&S)")
        proj_edit_action = QAction("项目属性...", self)
        proj_edit_action.triggered.connect(self._on_edit_project)
        system_menu.addAction(proj_edit_action)
        system_menu.addSeparator()
        left_toggle = QAction("切换左侧流程资源", self)
        left_toggle.triggered.connect(self.toggle_left_panel)
        system_menu.addAction(left_toggle)
        right_toggle = QAction("切换右侧图像结果区", self)
        right_toggle.triggered.connect(self.toggle_right_panel)
        system_menu.addAction(right_toggle)

        help_menu = menu_bar.addMenu("帮助(&H)")
        guide_action = QAction("使用指南(&G)", self)
        help_menu.addAction(guide_action)
        help_menu.addSeparator()
        about_action = QAction("关于 VisionFlow(&A)", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _refresh_recent(self):
        self._recent_menu.clear()
        project_service.cleanup_recent_projects()
        if not project_service.recent_projects:
            empty_action = QAction("(无最近项目)", self)
            empty_action.setEnabled(False)
            self._recent_menu.addAction(empty_action)
            return
        for path in project_service.recent_projects:
            action = QAction(os.path.basename(path), self)
            action.setToolTip(path)
            action.triggered.connect(lambda checked=False, current_path=path: self._open_project(current_path))
            self._recent_menu.addAction(action)
        self._recent_menu.addSeparator()
        clear_action = QAction("清空最近项目", self)
        clear_action.triggered.connect(project_service.clear_recent_projects)
        self._recent_menu.addAction(clear_action)

    def _wire_diagram_editor(self, editor: DiagramEditorWidget):
        editor.node_selected.connect(self._on_editor_node_selected)
        editor.node_deselected.connect(lambda: self._select_node(None))
        editor.node_double_clicked.connect(self._on_editor_node_double_clicked)
        editor.node_properties_requested.connect(self._on_editor_node_double_clicked)
        editor.node_help_requested.connect(self._on_editor_node_help_requested)
        editor.node_executed.connect(self._on_node_executed)
        editor.scene.status_message.connect(self._on_editor_status)

    def _create_diagram_page(self, diagram: DiagramData) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        editor = DiagramEditorWidget()
        self._wire_diagram_editor(editor)
        if diagram.workflow is None:
            diagram.workflow = WorkflowEngine(name=diagram.name)
        editor.bind_workflow(diagram.workflow)
        layout.addWidget(editor, 1)
        page.diagram_id = diagram.id
        page.workflow = diagram.workflow
        page.editor = editor
        return page

    def _show_start_page(self):
        self._root_stack.setCurrentWidget(self._start_page)
        self._start_page.refresh_recent(project_service)
        self._project_loaded = False
        self._workflow = None
        self._diagram_editor = None
        self._select_node(None)
        self._sync_proj_labels(None)
        self._diagram_status_strip.set_status("流程图就绪", "#4caf50")
        self._side_status_strip.set_status("等待选择节点", "#4caf50")

    def _show_editor(self):
        self._root_stack.setCurrentWidget(self._editor_surface)
        self._project_loaded = True

    def _bind_project_diagram(self, project: ProjectItem):
        if not project.diagrams:
            project.add_diagram(project.name)
        # Always sync global templates (loaded after node discovery)
        if project_service._templates:
            project._templates = list(project_service._templates)
        self._refresh_diagram_tabs(project)
        self._show_editor()
        self._sync_proj_labels(project)
        self._select_node(None)

    def _refresh_diagram_tabs(self, project: ProjectItem):
        self._diagram_pages.clear()
        self._diagram_headers.clear()
        self._diagram_tab_widget.blockSignals(True)
        self._diagram_tab_widget.clear()
        for diagram in project.diagrams:
            page = self._create_diagram_page(diagram)
            self._diagram_pages[diagram.id] = page
            index = self._diagram_tab_widget.addTab(page, "")
            self._install_diagram_tab_header(index, diagram)
        target_index = max(0, min(project.selected_diagram_index, self._diagram_tab_widget.count() - 1))
        if self._diagram_tab_widget.count() > 0:
            self._diagram_tab_widget.setCurrentIndex(target_index)
        self._diagram_tab_widget.blockSignals(False)
        self._on_diagram_tab_changed(target_index)

    def _install_diagram_tab_header(self, index: int, diagram: DiagramData):
        header = _DiagramTabHeader(diagram.name, self._diagram_tab_widget.tabBar())
        header.rename_requested.connect(lambda text, current=diagram: self._rename_diagram(current, text))
        header.run_requested.connect(lambda current=diagram: self._run_diagram(current.id))
        header.stop_requested.connect(lambda current=diagram: self._stop_diagram(current.id))
        header.reset_requested.connect(lambda current=diagram: self._reset_diagram_view(current.id))
        self._diagram_tab_widget.setTabToolTip(index, diagram.name)
        self._diagram_tab_widget.tabBar().setTabButton(index, QTabBar.LeftSide, header)

        # Custom close button — custom styled for dark theme visibility
        close_btn = QPushButton("×")
        close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {theme_manager.color('text_secondary').name()};"
            f" font-size: 14px; padding: 0; }}"
            f"QPushButton:hover {{ background: #c42b1c; color: white; border-radius: 2px; }}"
        )
        close_btn.clicked.connect(lambda checked, idx=index: self._on_close_diagram_tab(idx))
        self._diagram_tab_widget.tabBar().setTabButton(index, QTabBar.RightSide, close_btn)

        self._diagram_headers[diagram.id] = header

    def _rename_diagram(self, diagram: DiagramData, text: str):
        name = (text or "").strip() or diagram.name
        diagram.name = name
        if diagram.workflow is not None:
            diagram.workflow.name = name
        project = project_service.current_project
        if project is not None:
            for index, item in enumerate(project.diagrams):
                if item.id == diagram.id:
                    self._diagram_tab_widget.setTabToolTip(index, name)
                    break
        header = self._diagram_headers.get(diagram.id)
        if header is not None:
            header.set_name(name)
        self._sync_proj_labels(project_service.current_project)

    def _refresh_diagram_tab_headers(self):
        current_id = getattr(self._current_diagram_page(), "diagram_id", None)
        for diagram_id, header in self._diagram_headers.items():
            header.set_active(diagram_id == current_id)

    def _run_diagram(self, diagram_id: str):
        project = project_service.current_project
        if project is None:
            return
        for index, diagram in enumerate(project.diagrams):
            if diagram.id == diagram_id:
                self._diagram_tab_widget.setCurrentIndex(index)
                self._on_run_workflow()
                return

    def _stop_diagram(self, diagram_id: str):
        project = project_service.current_project
        if project is None:
            return
        for index, diagram in enumerate(project.diagrams):
            if diagram.id == diagram_id:
                self._diagram_tab_widget.setCurrentIndex(index)
                self._on_stop_workflow()
                return

    def _reset_diagram_view(self, diagram_id: str):
        project = project_service.current_project
        if project is None:
            return
        for index, diagram in enumerate(project.diagrams):
            if diagram.id == diagram_id:
                self._diagram_tab_widget.setCurrentIndex(index)
                self._on_reset_workflow_view()
                return

    def _current_diagram_page(self):
        page = self._diagram_tab_widget.currentWidget()
        return page if page is not None else None

    def _current_diagram_editor(self) -> DiagramEditorWidget | None:
        page = self._current_diagram_page()
        return getattr(page, "editor", None) if page is not None else None

    def _current_diagram_data(self) -> DiagramData | None:
        project = project_service.current_project
        if project is None:
            return None
        return project.selected_diagram

    def _on_add_diagram(self):
        project = project_service.current_project
        if project is None:
            project = project_service.new_project()
        self._sync_workflow_to_project()
        diagram = project.add_diagram()
        self._refresh_diagram_tabs(project)
        self._log_panel.info(f"新建流程图: {diagram.name}")
        self._sync_proj_labels(project)

    def _on_duplicate_diagram(self):
        """Duplicate current diagram (WPF DuplicationDiagramCommand)."""
        project = project_service.current_project
        if project is None:
            return
        self._sync_workflow_to_project()
        clone = project.duplicate_diagram()
        if clone:
            self._refresh_diagram_tabs(project)
            self._log_panel.success(f"已复制流程图: {clone.name}")

    def _on_add_from_template(self):
        """Add diagram from template (WPF AddDiagramByTemplateCommand).

        WPF flow:
          1. Guard: no templates → show "不存在模板，请先添加模板"
          2. Show DiagramTemplates selection dialog (ListBox DataTemplate)
          3. On submit: add SelectedDiagramTemplate.Diagram to DiagramDatas

        Python: reuses TemplateManagerDialog for selection.
        """
        project = project_service.current_project
        if project is None:
            return
        if not project.templates:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "不存在模板，请先将流程图另存为模板")
            return
        from gui.template_dialog import TemplateManagerDialog
        dlg = TemplateManagerDialog(project, self)
        dlg.exec_()
        if dlg.added_diagram:
            self._refresh_diagram_tabs(project)
            self._log_panel.success(f"从模板创建: {dlg.added_diagram.name}")

    def _on_manage_templates(self):
        """Open template management dialog (WPF ManageTemplatesCommand)."""
        project = project_service.current_project
        if project is None:
            return
        from gui.template_dialog import TemplateManagerDialog
        dlg = TemplateManagerDialog(project, self)
        dlg.exec_()
        self._persist_templates()  # persist any deletions
        if dlg.added_diagram:
            self._refresh_diagram_tabs(project)
            self._log_panel.success(f"从模板创建: {dlg.added_diagram.name}")

    def _load_templates_on_startup(self):
        """Load global templates on app startup (WPF LoadDiagramTemplates).

        Must run AFTER _discover_nodes() populates node_registry, otherwise
        node_registry.create() returns None for all types and nodes are lost.
        """
        project_service._templates = project_service.load_templates()
        project = project_service.current_project
        if project is not None:
            project._templates = list(project_service._templates)

    def _persist_templates(self):
        """Persist templates to disk (WPF: save diagramtemplates.json)."""
        project = project_service.current_project
        if project is None:
            return
        # Sync to global store + persist
        project_service._templates = list(project._templates)
        project_service.save_templates(project._templates)

    def _on_save_as_template(self):
        """Save current diagram as template (WPF SaveAsDiagramTemplateCommand).

        WPF: TextBoxPresenter dialog with Title="保存模板名称", pre-filled with diagram name.
        Python: QInputDialog with same behavior.

        Guard: warns if diagram has no nodes to prevent saving empty templates.
        """
        project = project_service.current_project
        if project is None:
            return
        diagram = project.selected_diagram
        if diagram is None:
            return

        node_count = len(diagram.workflow.get_all_nodes()) if diagram.workflow else 0
        if node_count == 0:
            reply = QMessageBox.question(
                self, "空流程图",
                "当前流程图没有任何节点，保存为模板后添加时将显示空白画布。\n\n确定要保存空模板吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, "保存模板名称",
            "请输入模板名称：",
            text=diagram.name)
        if ok and name.strip():
            self._sync_workflow_to_project()
            project.save_diagram_as_template(diagram=diagram, name=name.strip())
            self._persist_templates()
            self._log_panel.success(f"模板已保存: {name.strip()} ({node_count} 个节点)")

    def _on_delete_diagram(self):
        """Delete current diagram."""
        project = project_service.current_project
        if project is None:
            return
        self._sync_workflow_to_project()
        if project.delete_diagram():
            self._refresh_diagram_tabs(project)
            self._log_panel.info("已删除当前流程图")
        else:
            self._log_panel.warning("至少需要保留一个流程图")
        self._sync_proj_labels(project)

    def _on_close_diagram_tab(self, index: int):
        project = project_service.current_project
        if project is None:
            return
        self._sync_workflow_to_project()
        if 0 <= index < len(project.diagrams):
            diagram = project.diagrams[index]
            if project.delete_diagram(diagram):
                self._refresh_diagram_tabs(project)
                self._log_panel.info(f"已删除流程图: {diagram.name}")
            else:
                self._log_panel.warning("至少需要保留一个流程图")
        self._sync_proj_labels(project)

    def _on_diagram_tab_changed(self, index: int):
        project = project_service.current_project
        if project is None or not (0 <= index < len(project.diagrams)):
            self._workflow = None
            self._diagram_editor = None
            self._diagram_status_strip.set_status("流程图就绪", "#4caf50")
            return
        project.selected_diagram_index = index
        diagram = project.selected_diagram
        page = self._current_diagram_page()
        self._workflow = diagram.workflow if diagram else None
        self._diagram_editor = getattr(page, "editor", None)
        self._node_cnt_lbl.setText(f"节点: {len(self._workflow.get_all_nodes()) if self._workflow else 0}")
        self._sync_proj_labels(project)
        self._refresh_diagram_tab_headers()
        self._diagram_status_strip.set_status(f"当前流程图：{diagram.display_name}", "#4caf50")

    def _sync_proj_labels(self, project: ProjectItem | None):
        if project is None:
            project_name = "无项目"
            diagram_name = "无流程图"
            self.setWindowTitle("VisionFlow — VisionFlow")
        else:
            project_name = project.name or project.display_name
            diagram_name = project.selected_diagram.display_name if project.selected_diagram else "无流程图"
            self.setWindowTitle(f"{project_name} — VisionFlow")
        if hasattr(self, "_cap_proj_lbl"):
            self._cap_proj_lbl.setText(project_name)
        if hasattr(self, "_cmd_proj_lbl"):
            self._cmd_proj_lbl.setText(diagram_name)

    def _sync_workflow_to_project(self):
        project = project_service.current_project
        if project is None:
            return
        for index, diagram in enumerate(project.diagrams):
            if index < self._diagram_tab_widget.count():
                page = self._diagram_tab_widget.widget(index)
                editor = getattr(page, "editor", None)
                if editor is not None:
                    editor.save_to_workflow()
                    diagram.workflow = editor._workflow

    def _select_node(self, node: NodeBase | None):
        self._selected_node = node
        self._property_panel.set_node(node)
        self._help_panel.set_node(node)
        self._module_result_title.setText(f"模块名称 <{node.name}>" if node else "模块名称 <未选择>")
        if isinstance(node, VisionNodeData):
            self._result_panel.show_node_results(node)
            self._result_panel.show_help(node)
        else:
            self._result_panel.show_node_results(None)
            self._result_panel.show_help(None)
        self._update_image_context(node)

        if isinstance(node, SrcFilesVisionNodeData):
            self._resource_panel.set_node(node)
            self._resource_panel.setVisible(True)
        else:
            self._resource_panel.setVisible(False)
            self._resource_panel.set_node(None)

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

        if node is not None:
            self._side_status_strip.set_status(f"已选择模块：{node.name}", "#0078d4")
        else:
            self._side_status_strip.set_status("等待选择节点", "#4caf50")

    def _on_node_type_selected(self, type_name: str):
        if not self._workflow:
            return
        node = self._ctx.node_registry.create(type_name) if self._ctx.node_registry else None
        editor = self._current_diagram_editor()
        if node is not None and editor is not None:
            editor.add_node(node, group_name=self._get_group(type_name))
            self._toolbox.record_use(type_name)
            self._log_panel.info(f"添加节点: {node.name}")
            self._node_cnt_lbl.setText(f"节点: {len(self._workflow.get_all_nodes())}")

    def _on_editor_node_selected(self, node_data: NodeBase):
        self._select_node(node_data)

    def _on_editor_node_double_clicked(self, node_data: NodeBase):
        """Handle node double-click — open tabbed property dialog (WPF ShowTabEditCommand).

        Decoupled: calls open_node_dialog which uses get_property_presenter()
        to resolve the settings object. Different node types can override
        get_property_presenter() to provide custom settings panels.
        """
        from gui.property_panel import open_node_dialog
        self._select_node(node_data)
        open_node_dialog(node_data, parent=self)

    def _on_node_executed(self, node_data, state: str, time_span: str):
        """Log node execution to history (WPF Messages.Add)."""
        if isinstance(node_data, VisionNodeData):
            src_path = ""
            if hasattr(node_data, 'src_file_path'):
                src_path = node_data.src_file_path or ""
            self._result_panel.add_to_history(node_data, state, time_span, src_path)

    def _on_editor_node_help_requested(self, node_data: NodeBase):
        """Handle right-click → 帮助 — switch to help tab and show node help."""
        self._select_node(node_data)
        # Switch to help tab
        if hasattr(self, '_bottom_tabs'):
            self._bottom_tabs.setCurrentIndex(2)  # index 2 = 帮助
        # Show help content
        if hasattr(self, '_help_panel'):
            self._help_panel.set_node(node_data)

    def _on_editor_status(self, message: str):
        self._msg_lbl.setText(message)
        if message:
            self._diagram_status_strip.set_status(message, "#0078d4")

    def _get_group(self, type_name: str) -> str:
        from core.node_group import node_data_group_manager
        for group in node_data_group_manager.get_all_groups():
            for node_type in group.node_types:
                if node_type.__name__ == type_name:
                    return group.name
        return ""

    def _on_property_changed(self, name, old, new):
        if self._selected_node:
            if isinstance(self._selected_node, ROINodeData):
                self._img_panel.set_roi_rect(self._selected_node.get_active_roi_rect(), label=self._selected_node.roi.name)
            event_system.publish(EventType.NODE_PROPERTY_CHANGED, sender=self._selected_node, name=name, old=old, new=new)

    def _on_ev_node_sel(self, sender, **kwargs):
        self._select_node(kwargs.get("node", sender))

    def _on_ev_diag_chg(self, sender, **kwargs):
        if self._workflow:
            self._node_cnt_lbl.setText(f"节点: {len(self._workflow.get_all_nodes())}")

    def _on_wf_start(self, sender, **kwargs):
        self._wf_start_time = __import__('time').time()
        self._state_lbl.setText(f"{FontIcons.Sync} 运行中")
        self._state_lbl.setStyleSheet("color: #2196f3; font-weight: bold;")
        self._msg_lbl.setText("流程运行中...")
        self._run_btn.setEnabled(False)
        self._diagram_status_strip.set_status("流程图运行中...", "#2196f3")
        self._side_status_strip.set_status("结果区正在等待输出...", "#2196f3")

    def _on_wf_done(self, sender, **kwargs):
        elapsed = self._format_elapsed()
        self._state_lbl.setText(f"{FontIcons.Completed} 完成")
        self._state_lbl.setStyleSheet("color: #4caf50; font-weight: bold;")
        self._msg_lbl.setText(f"流程执行完成 (用时: {elapsed})")
        self._run_btn.setEnabled(True)
        self._diagram_status_strip.set_status(f"流程图执行完成 · 用时: {elapsed}", "#4caf50")
        self._side_status_strip.set_status("结果区已更新", "#4caf50")

    def _on_wf_err(self, sender, **kwargs):
        elapsed = self._format_elapsed()
        self._state_lbl.setText(f"{FontIcons.Error} 错误")
        self._state_lbl.setStyleSheet("color: #f44336; font-weight: bold;")
        result = kwargs.get("result")
        self._msg_lbl.setText(f"{str(result) if result else '流程错误'} (用时: {elapsed})")
        self._run_btn.setEnabled(True)
        self._diagram_status_strip.set_status(f"流程图错误：{self._msg_lbl.text()}", "#f44336")
        self._side_status_strip.set_status("结果区收到错误消息", "#f44336")

    def _format_elapsed(self) -> str:
        """Format elapsed workflow time (WPF TimeSpan display)."""
        import time
        start = getattr(self, '_wf_start_time', None)
        if start is None:
            return "00:00:00"
        seconds = time.time() - start
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _on_proj_load(self, sender, **kwargs):
        project = kwargs.get("project")
        if project:
            self._bind_project_diagram(project)

    def _on_proj_save(self, sender, **kwargs):
        project = kwargs.get("project")
        if project:
            self._sync_proj_labels(project)

    def _update_clock(self):
        self._time_lbl.setText(datetime.now().strftime("%H:%M:%S"))

    def _on_new_project(self):
        project = project_service.new_project()
        self._bind_project_diagram(project)
        self._log_panel.info("新建项目")

    def _on_open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开项目", "", project_service.FILE_FILTER)
        if path:
            self._open_project(path)

    def _open_project(self, path: str):
        if not path or not os.path.exists(path):
            project_service.remove_recent(path)
            QMessageBox.warning(self, "打开失败", f"文件不存在: {path}")
            return
        project = project_service.load(path)
        if project:
            self._bind_project_diagram(project)
            self._log_panel.success(f"已打开: {path}")

    def open_project(self, file_path: str):
        self._open_project(file_path)

    def _on_save_project(self):
        project = project_service.current_project
        if project is None:
            return
        self._sync_workflow_to_project()
        if project.file_path:
            if project_service.save(project):
                self._log_panel.success(f"项目已保存: {os.path.basename(project.file_path)}")
            else:
                self._log_panel.error("项目保存失败")
        else:
            self._on_save_as_project()

    def _on_save_as_project(self):
        project = project_service.current_project or project_service.new_project()
        path, _ = QFileDialog.getSaveFileName(self, "另存为...", f"{project.name}.json", project_service.FILE_FILTER)
        if path:
            project.file_path = path
            self._sync_workflow_to_project()
            if project_service.save_as(project, path):
                self._log_panel.success(f"已保存至: {path}")
                self._sync_proj_labels(project)

    def _on_run_workflow(self):
        if not self._workflow:
            return
        self._sync_workflow_to_project()
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
            self._diagram_status_strip.set_status("流程图已停止", "#ff9800")
            self._side_status_strip.set_status("结果区已停止等待", "#ff9800")

    def _on_cycle_run_mode(self):
        """Cycle through run modes: Node → Link → Port → Node."""
        if not self._workflow:
            return
        from core.workflow import DiagramFlowableMode
        _MODE_LABELS = {
            DiagramFlowableMode.NODE: "运行模式: 按节点",
            DiagramFlowableMode.LINK: "运行模式: 节点+连线",
            DiagramFlowableMode.PORT: "运行模式: 节点+连线+端口",
        }
        _NEXT = {
            DiagramFlowableMode.NODE: DiagramFlowableMode.LINK,
            DiagramFlowableMode.LINK: DiagramFlowableMode.PORT,
            DiagramFlowableMode.PORT: DiagramFlowableMode.NODE,
        }
        current = self._workflow.flowable_mode
        self._workflow.flowable_mode = _NEXT[current]
        new_label = _MODE_LABELS[self._workflow.flowable_mode]
        self._log_panel.info(new_label)
        self._diagram_status_strip.set_status(new_label, "#0078d4")

    def _jump_to_node(self, node_id: str):
        project = project_service.current_project
        if project is None:
            return
        for index, diagram in enumerate(project.diagrams):
            workflow = diagram.workflow
            if workflow and workflow.get_node_by_id(node_id):
                self._diagram_tab_widget.setCurrentIndex(index)
                editor = self._current_diagram_editor()
                if editor is None:
                    return
                item = editor.scene.get_node_item(node_id)
                if item is not None:
                    editor.scene.clearSelection()
                    item.setSelected(True)
                    editor.view.centerOn(item)
                    self._select_node(item.node_data)
                return

    def _on_resource_file_selected(self, path: str):
        if not path:
            return
        try:
            import cv2
            image = cv2.imread(path, cv2.IMREAD_COLOR)
            if image is not None:
                h, w = image.shape[:2]
                self._img_panel.set_image(image)
                self._img_panel.set_image_info(path, w, h)
                self._center_tabs.setCurrentIndex(0)
        except Exception:
            pass

    def _on_result_image_update(self, image):
        """Handle history row click — update main image display (WPF selection linkage)."""
        import numpy as np
        if image is not None:
            self._img_panel.set_image(image)
            self._center_tabs.setCurrentIndex(0)  # switch to image tab

    def _on_resource_file_double_clicked(self, path: str):
        """Open full-size zoom viewer for the image file (WPF ShowZoomViewImageFileCommand)."""
        if not path or not os.path.exists(path):
            return
        # Switch to image tab + load full resolution
        self._on_resource_file_selected(path)
        self._center_tabs.setCurrentIndex(0)
        # Fit image to viewer
        if hasattr(self._img_panel, 'viewer'):
            self._img_panel.viewer.fit_to_window()

    def toggle_left_panel(self):
        """Toggle left panel via GridSplitterBox (WPF Mode=Extend)."""
        self._left_box.toggle_expand()
        self._left_panel_visible = self._left_box.is_expanded

    def toggle_right_panel(self):
        if self._right_panel_visible:
            self._right_panel.setVisible(False)
            self._right_panel_visible = False
        else:
            self._right_panel.setVisible(True)
            self._right_panel_visible = True

    @property
    def active_workflow(self) -> WorkflowEngine | None:
        return self._workflow

    def add_diagram_tab(self, name: str, workflow: WorkflowEngine):
        project = project_service.current_project
        if project is None:
            project = project_service.new_project()
        diagram = DiagramData(name=name)
        diagram.workflow = workflow
        project.diagrams.append(diagram)
        project.selected_diagram_index = len(project.diagrams) - 1
        self._refresh_diagram_tabs(project)
        return name

    def remove_diagram_tab(self, name: str):
        project = project_service.current_project
        if project is None:
            return
        for diagram in list(project.diagrams):
            if diagram.name == name:
                project.delete_diagram(diagram)
                break
        self._refresh_diagram_tabs(project)

    def switch_to_diagram(self, name_or_index: str | int):
        if isinstance(name_or_index, int):
            if 0 <= name_or_index < self._diagram_tab_widget.count():
                self._diagram_tab_widget.setCurrentIndex(name_or_index)
            return
        project = project_service.current_project
        if project is None:
            return
        for index, diagram in enumerate(project.diagrams):
            if diagram.name == name_or_index:
                self._diagram_tab_widget.setCurrentIndex(index)
                return

    def _active_visual_target(self):
        focus = QApplication.focusWidget()
        editor = self._current_diagram_editor()
        if editor is not None and focus is not None:
            current = focus
            while current is not None:
                if current is editor or current is editor.view:
                    return editor.view
                current = current.parentWidget()
        if self._center_tabs.currentIndex() == 0:
            return self._img_panel.viewer
        return editor.view if editor is not None else self._img_panel.viewer

    def _on_reset_workflow_view(self):
        editor = self._current_diagram_editor()
        if editor is not None and self._workflow is not None:
            editor.bind_workflow(self._workflow)
            self._log_panel.info("已重置当前流程图视图")

    def _on_undo_diagram(self):
        editor = self._current_diagram_editor()
        if editor is not None:
            editor._on_undo()

    def _on_redo_diagram(self):
        editor = self._current_diagram_editor()
        if editor is not None:
            editor._on_redo()

    def _toggle_bottom(self):
        sizes = self._center_splitter.sizes()
        if len(sizes) < 2:
            return
        if self._bottom_visible:
            _ps.set_i("bottom_height_saved", sizes[1])
            self._center_splitter.setSizes([sizes[0] + sizes[1], 0])
            self._bottom_toggle.setText("▲")
        else:
            saved = _ps.get_i("bottom_height_saved", 180)
            total = sum(sizes)
            height = min(saved, total - 220)
            self._center_splitter.setSizes([total - height, height])
            self._bottom_toggle.setText("▼")
        self._bottom_visible = not self._bottom_visible

    def _update_image_context(self, node: NodeBase | None):
        if node is None:
            self._img_panel.clear_context_info()
            return

        badge = "无结果"
        badge_color = "#3f3f46"
        if isinstance(node, SrcFilesVisionNodeData):
            badge = "原始图像"
            badge_color = "#0078d4"
        elif isinstance(node, VisionNodeData) and (node.mat is not None or node.result_image_source is not None):
            badge = "模块结果"
            badge_color = "#4caf50"

        source_path, source_hint = self._find_source_context(node)
        self._img_panel.set_result_badge(badge, badge_color)
        self._img_panel.set_source_hint(source_hint)
        self._img_panel.set_message_banner(getattr(node, "message", ""))
        if source_path:
            pixel_w = getattr(node, 'pixel_width', 0) or 0
            pixel_h = getattr(node, 'pixel_height', 0) or 0
            self._img_panel.set_image_info(source_path, pixel_w, pixel_h)
        else:
            self._img_panel.set_image_info(None)

    def _find_source_context(self, node: NodeBase | None) -> tuple[str | None, str]:
        if node is None:
            return None, ""

        candidates: list[SrcFilesVisionNodeData] = []
        if isinstance(node, SrcFilesVisionNodeData):
            candidates.append(node)
        if hasattr(node, "get_all_from_node_datas"):
            candidates.extend(
                upstream for upstream in node.get_all_from_node_datas()
                if isinstance(upstream, SrcFilesVisionNodeData)
            )

        seen: set[str] = set()
        for source_node in candidates:
            if source_node.node_id in seen:
                continue
            seen.add(source_node.node_id)
            path = getattr(source_node, "src_file_path", "")
            paths = getattr(source_node, "src_file_paths", []) or []
            if not path:
                continue
            hint = ""
            if paths:
                try:
                    hint = f"图像源 {paths.index(path) + 1}/{len(paths)}"
                except ValueError:
                    hint = f"图像源 1/{len(paths)}"
            return path, hint
        return None, ""

    def _format_file_info(self, path: str | None) -> str:
        if not path or not os.path.exists(path):
            return ""
        try:
            size = os.path.getsize(path)
            modified = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
            filename = os.path.basename(path)
            size_text = f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.2f} MB"
            return f"{filename}    |    {size_text}    |    {modified}"
        except OSError:
            return os.path.basename(path)

    def _on_close_window(self):
        """WPF CloseAfterSaveWindowCommand: save project then close."""
        try:
            if project_service.current_project:
                self._on_save_project()
        except Exception:
            pass
        self.close()

    def _on_open_guide(self):
        """Open interactive guide overlay — WPF ShowGuideCommand."""
        from gui.guide_overlay import GuideOverlay
        overlay = GuideOverlay(self)
        # Pass actual widget references directly
        overlay.add_step("创建项目",
            "点击这里创建一个新的视觉检测项目。\n项目用于组织流程图、图像和设置。",
            widget=find_child_by_tip(self, "新建项目"))
        overlay.add_step("节点工具箱",
            "左侧工具箱列出了所有可用的视觉处理节点。\n拖拽节点到画布上即可开始构建流程图。",
            widget=find_child_by_tip(self, "搜索节点..."))
        overlay.add_step("切换主题",
            "点击调色板按钮选择颜色主题。\n支持深色、浅色、科技蓝等多种风格。",
            widget=find_child_by_tip(self, "颜色主题"))
        overlay.add_step("开始运行",
            "构建好流程图后，点击「开始」运行整个流程。\n结果将显示在右侧面板中。",
            widget=find_child_by_tip(self, "开始"))
        overlay.start()

    def _on_open_settings(self):
        """Open settings dialog — WPF ShowSettingCommand."""
        dlg = _SettingsDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self._apply_settings()
        self._apply_theme()
        if hasattr(self, '_theme_toggle'):
            self._theme_toggle.blockSignals(True)
            self._theme_toggle.setChecked(theme_manager.is_dark)
            self._theme_toggle.blockSignals(False)

    def _apply_settings(self):
        """Apply persisted settings to the UI — WPF IocSetting.Load()."""
        import json, os
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app_config.json")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

        # Show/hide theme toggle button
        if hasattr(self, '_theme_toggle'):
            show = data.get("show_theme_btn", True)
            self._theme_toggle.setVisible(show)

        # Toggle canvas grid
        show_grid = data.get("show_grid", True)
        editors = []
        if self._diagram_editor is not None:
            editors.append(self._diagram_editor)
        for page in self._diagram_pages.values():
            ed = getattr(page, 'editor', None)
            if ed is not None:
                editors.append(ed)
        for editor in editors:
            s = editor.scene
            if s is not None and hasattr(s, '_show_grid'):
                if s._show_grid != show_grid:
                    s.toggle_grid()

        # System tray
        tray_enabled = data.get("show_tray", True)
        if hasattr(self, '_tray_icon'):
            self._tray_icon.setVisible(tray_enabled)

    def _on_show_theme_dialog(self):
        """Open color theme picker dialog — WPF ShowColorThemeViewCommand."""
        dlg = ThemePickerDialog(self)
        if dlg.exec_():
            self._apply_theme()
        if hasattr(self, '_theme_toggle'):
            self._theme_toggle.blockSignals(True)
            self._theme_toggle.setChecked(theme_manager.is_dark)
            self._theme_toggle.blockSignals(False)

    def _on_toggle_theme(self):
        """Toggle between dark and light themes (WPF SwitchThemeViewPresenter)."""
        theme_manager.toggle()
        self._apply_theme()
        if hasattr(self, '_theme_toggle'):
            self._theme_toggle.blockSignals(True)
            self._theme_toggle.setChecked(theme_manager.is_dark)
            self._theme_toggle.blockSignals(False)

    def _reapply_widget_styles(self):
        """Re-apply dynamic QSS to widgets with inline styles."""
        global _CMD_BTN, _TAB_STYLE
        _CMD_BTN = _cmd_btn_qss()
        _TAB_STYLE = _tab_qss()
        tm = theme_manager
        # Toggle button
        if hasattr(self, '_theme_toggle'):
            self._theme_toggle.setStyleSheet(_CMD_BTN + f"""
                FontIconToggleButton:checked {{ color: {tm.color('text_primary').name()}; }}
                FontIconToggleButton:checked:hover {{ background: {tm.color('bg_surface_hover').name()}; }}
            """)
        # Diagram tab widget (holds "新项目", flowchart tabs)
        if hasattr(self, '_diagram_tab_widget'):
            self._diagram_tab_widget.setStyleSheet(_TAB_STYLE)
        # Center tabs (图像 / 模块结果 / 帮助)
        if hasattr(self, '_center_tabs'):
            self._center_tabs.setStyleSheet(_TAB_STYLE)

    def _apply_theme(self):
        """Reapply theme to ALL controls — WPF RefreshTheme() via DynamicResource."""
        tm = theme_manager
        c = tm.colors
        qss = tm.get_stylesheet()

        # 1. Global QSS — covers ALL windows, dialogs, and standard widget types
        QApplication.instance().setStyleSheet(qss)

        # 2. Main window palette + stylesheet
        self.setPalette(c.to_palette())
        self.setStyleSheet(qss)

        # 3. Re-apply toolbar buttons (each has own QSS set at creation)
        self._reapply_widget_styles()
        cmd = _CMD_BTN  # current theme QSS
        for btn in self.findChildren(QPushButton):
            s = btn.styleSheet()
            if s and 'transparent' in s and 'border-radius' in s:
                btn.setStyleSheet(cmd)

        # 4. Force repaint all QWidget children
        for child in self.findChildren(QWidget):
            try:
                child.style().unpolish(child)
                child.style().polish(child)
                child.update()
            except Exception:
                pass

        # 5. Diagram scene — re-apply checkerboard background brush
        from PyQt5.QtWidgets import QGraphicsView
        from gui.node_editor.scene import _make_checker_brush
        for view in self.findChildren(QGraphicsView):
            scene = view.scene()
            if scene:
                scene.setBackgroundBrush(_make_checker_brush())
                scene.update()
            view.viewport().update()

        # 6. Image viewer — re-apply info strip background
        from gui.image_viewer import ImageViewerPanel
        for iv in self.findChildren(ImageViewerPanel):
            if hasattr(iv, '_setup_ui') and hasattr(iv, 'viewer'):
                iv.viewer.viewport().update()

        # 7. Diagram tab headers (custom widgets in tab bar)
        for header in self._diagram_headers.values():
            if hasattr(header, '_refresh_qss'):
                header._refresh_qss()

        # 8. Title bar
        if hasattr(self, '_title_bar'):
            self._title_bar.update()

    def _on_edit_project(self):
        """Open project settings dialog (WPF ShowEditProjectCommand)."""
        project = project_service.current_project
        if project is None:
            project = project_service.new_project()
        from PyQt5.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("项目属性")
        dlg.setMinimumWidth(400)
        dlg.setStyleSheet("QDialog { background: #2d2d30; color: #dcdcdc; }")
        form = QFormLayout(dlg)

        name_edit = QLineEdit(project.display_name)
        form.addRow("项目名称:", name_edit)

        desc_edit = QLineEdit(getattr(project, 'description', ''))
        form.addRow("描述:", desc_edit)

        author_edit = QLineEdit(getattr(project, 'author', ''))
        form.addRow("作者:", author_edit)

        info = QLabel(f"流程图: {len(project.diagrams)} 个\n节点总数: {sum(len(d.workflow.get_all_nodes()) if d.workflow else 0 for d in project.diagrams)}")
        info.setStyleSheet("color: #999; font-size: 11px;")
        form.addRow(info)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        if dlg.exec_() == dlg.Accepted:
            old_name = project.name
            project.name = name_edit.text().strip() or project.name
            project.description = desc_edit.text()
            project.author = author_edit.text()
            # Update file_path to reflect new name (WPF: GetFilePath uses Title)
            if project.file_path and project.name != old_name:
                d = os.path.dirname(project.file_path)
                project.file_path = os.path.join(d, f"{project.name}.json")
            self._sync_proj_labels(project)
            self._log_panel.info(f"项目已重命名: {old_name} → {project.name}")

    def _show_notification(self, level: str, title: str, message: str):
        """Show desktop notification (WPF ShowXxxNotifyMessageOutputNodeData)."""
        from PyQt5.QtWidgets import QSystemTrayIcon
        if QSystemTrayIcon.isSystemTrayAvailable() and QSystemTrayIcon.supportsMessages():
            if not hasattr(self, '_tray_icon'):
                self._tray_icon = QSystemTrayIcon(self)
                icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "logo.png")
                if os.path.exists(icon_path):
                    self._tray_icon.setIcon(QIcon(icon_path))
                self._tray_icon.show()
            icon_map = {"Info": 1, "Warning": 2, "Error": 3, "Success": 1}
            self._tray_icon.showMessage(title, message, icon_map.get(level, 1), 3000)
        else:
            # Fallback: status bar message
            self._log_panel.info(f"[{level}] {title}: {message}")

    def _on_about(self):
        QMessageBox.about(
            self,
            "关于 VisionFlow",
            "<h2>VisionFlow 2.0</h2><p>视觉流程编辑器</p>"
            "<p>移植自 WPF-VisionMaster (HeBianGu)</p>"
            "<p>使用 Python + PyQt5 + OpenCV</p><hr>"
            "<p>当前版本仍在持续做 WPF 对齐修复。</p>",
        )

import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                             QMenuBar, QFrame, QPushButton)
from gui.theme import theme_manager, cmd_btn_qss, vsep
from gui.font_icons import FontIcons, FontIconButton, FontIconToggleButton


class CaptionBar(QWidget):
    """Custom title bar with logo, menu, toolbar buttons, theme toggle, and window controls."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._mw = main_window
        self.setFixedHeight(85)
        self._setup_ui()
        self._install_drag_support()

    def _setup_ui(self):
        mw = self._mw
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- 第一行图标+标题 ----
        col0 = QWidget()
        col0_layout = QHBoxLayout(col0)
        col0_layout.setContentsMargins(10, 20, 0, 20)
        col0_layout.setSpacing(0)

        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "logo.png")
        if os.path.exists(logo_path):
            logo = QLabel()
            logo.setPixmap(QPixmap(logo_path).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo.setStyleSheet("padding: 0 5px 0 0;")
            col0_layout.addWidget(logo)

        self._app_title_lbl = QLabel("VisionFlow")
        self._app_title_lbl.setStyleSheet("font-size: 30px; font-weight: bold; padding: 0 0 0 5px;")
        col0_layout.addWidget(self._app_title_lbl)
        outer.addWidget(col0)

        # ---- 网格容器 ----
        grid = QWidget()
        grid_layout = QVBoxLayout(grid)
        grid_layout.setContentsMargins(0, 2, 0, 2)
        grid_layout.setSpacing(0)

        # ---- 第0行：菜单 + 项目名称 ----
        row0 = QWidget()
        r0 = QHBoxLayout(row0)
        r0.setContentsMargins(8, 0, 0, 0)
        r0.setSpacing(0)

        self._menu_bar = QMenuBar()
        mw._build_menus(self._menu_bar)
        r0.addWidget(self._menu_bar)

        r0.addStretch(1)
        r0.addWidget(self._make_lbl("项目名称：", "#c8c8c8", 12, pad="0 4px"))
        self._cap_proj_lbl = self._make_lbl("无项目", "#0078d4", 12, bold=True, pad="0 12px")
        r0.addWidget(self._cap_proj_lbl)
        r0.addStretch(1)

        grid_layout.addWidget(row0)

        # ---- 第1行：顶部边框 + 工具栏 ----
        self._toolbar_row = QWidget()
        r1 = QHBoxLayout(self._toolbar_row)
        r1.setContentsMargins(0, 1, 0, 0)
        r1.setSpacing(0)

        toolbar = QWidget()
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(6, 3, 6, 3)
        tb.setSpacing(2)

        cmd = cmd_btn_qss()

        for icon, tip, slot in [
            (FontIcons.Page,                "新建项目", mw._on_new_project),
            (FontIcons.OpenFolderHorizontal, "打开项目", mw._on_open_project),
            (FontIcons.Edit,                 "编辑项目", mw._on_edit_project),
            (FontIcons.Save,                 "保存项目", mw._on_save_project),
        ]:
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            btn.setStyleSheet(cmd)
            btn.clicked.connect(slot)
            tb.addWidget(btn)
        tb.addWidget(vsep())

        # 按钮组2 — 项目级命令
        self._tool_project_cmds = QWidget()
        self._tool_project_cmds.setLayout(QHBoxLayout())
        self._tool_project_cmds.layout().setContentsMargins(0, 0, 0, 0)
        self._tool_project_cmds.layout().setSpacing(2)
        for icon, tip, slot in [
            (FontIcons.Add,           "新建流程图",           mw._on_add_diagram),
            (FontIcons.Ethernet,      "运行模式",             mw._on_cycle_run_mode),
            (FontIcons.Copy,          "重复流程图",           mw._on_duplicate_diagram),
            (FontIcons.DictionaryAdd, "从模板添加流程图",     mw._on_add_from_template),
            (FontIcons.Manage,        "模板管理",             mw._on_manage_templates),
            (FontIcons.SaveAs,        "流程图另存为模板",     mw._on_save_as_template),
            (FontIcons.Cancel,        "删除流程图",           mw._on_delete_diagram),
        ]:
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            btn.setStyleSheet(cmd)
            if slot:
                btn.clicked.connect(slot)
            if tip == "删除流程图":
                self._delete_diagram_btn = btn
            self._tool_project_cmds.layout().addWidget(btn)
        tb.addWidget(self._tool_project_cmds)
        tb.addWidget(vsep())

        # 按钮组3 — 图表命令
        self._tool_diagram_cmds = QWidget()
        self._tool_diagram_cmds.setLayout(QHBoxLayout())
        self._tool_diagram_cmds.layout().setContentsMargins(0, 0, 0, 0)
        self._tool_diagram_cmds.layout().setSpacing(2)

        for icon, tip, slot in [
            (FontIcons.Replay, "单次执行", mw._on_run_workflow),
            (FontIcons.Sync, "连续执行", mw._on_continuous_run),
            (FontIcons.Location, "停止", mw._on_stop_workflow),
            (FontIcons.Refresh, "重置", mw._on_reset_workflow_view),
        ]:
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            btn.setStyleSheet(cmd)
            if slot:
                btn.clicked.connect(slot)
            self._tool_diagram_cmds.layout().addWidget(btn)

        self._run_btn = self._tool_diagram_cmds.layout().itemAt(0).widget()
        self._continuous_btn = self._tool_diagram_cmds.layout().itemAt(1).widget()
        self._stop_btn = self._tool_diagram_cmds.layout().itemAt(2).widget()
        self._reset_btn = self._tool_diagram_cmds.layout().itemAt(3).widget()

        self._stop_btn.setEnabled(False)
        self._reset_btn.setEnabled(False)

        tb.addWidget(self._tool_diagram_cmds)
        tb.addWidget(vsep())

        tb.addStretch(1)
        r1.addWidget(toolbar)
        grid_layout.addWidget(self._toolbar_row)

        outer.addWidget(grid, 1)

        # ---- 右侧停靠的动作按钮 ----
        for icon, tip, slot in [
            (FontIcons.Color, "颜色主题", mw._on_show_theme_dialog),
            (FontIcons.Setting, "设置", mw._on_open_settings),
        ]:
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            btn.setStyleSheet(cmd)
            if slot:
                btn.clicked.connect(slot)
            outer.addWidget(btn)

        # 主题切换按钮
        self._theme_toggle = FontIconToggleButton(FontIcons.Brightness, FontIcons.QuietHours, font_size=16)
        self._theme_toggle.setToolTip("切换明/暗主题")
        self._theme_toggle.setStyleSheet(cmd + """
                    FontIconToggleButton:checked { color: #dcdcdc; }
                    FontIconToggleButton:checked:hover { background: #3e3e42; }
                """)
        self._theme_toggle.setChecked(theme_manager.is_dark)
        self._theme_toggle.toggled.connect(lambda _: mw._on_toggle_theme())
        outer.addWidget(self._theme_toggle)

        for icon, tip, slot in [
            (FontIcons.Info,  "关于",     mw._on_about),
            (FontIcons.Smartcard, "新手向导", mw._on_open_guide),
        ]:
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            btn.setStyleSheet(cmd)
            if slot:
                btn.clicked.connect(slot)
            outer.addWidget(btn)

        # 分隔符
        sep20 = QFrame()
        sep20.setFrameShape(QFrame.VLine)
        sep20.setStyleSheet("color: #505050;")
        sep20.setFixedSize(1, 20)
        outer.addWidget(sep20)

        # ---- 窗口标题栏按钮 ----
        _WIN = (
            "QPushButton { background:transparent; border:none; color:#999;"
            " font-family:'Segoe Fluent Icons','Segoe MDL2 Assets','Segoe UI Symbol';"
            " font-size:14px; min-width:46px; min-height:32px; }"
            "QPushButton:hover { background:#3e3e42; color:#dcdcdc; }"
            "QPushButton#close_btn:hover { background:#e81123; color:white; }"
        )
        for icon, tip, slot, btn_attr in [
            (FontIcons.ChromeMinimize, "最小化", mw.showMinimized, None),
            (FontIcons.ChromeMaximize, "最大化", mw._toggle_max, "_max_btn"),
            (FontIcons.ChromeRestore,  "还原",   mw._toggle_max, "_restore_btn"),
            (FontIcons.ChromeClose,    "关闭",   mw._on_close_window, None),
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

    def _install_drag_support(self):
        """安装事件过滤器以支持标题栏拖动窗口"""
        mw = self._mw
        self.installEventFilter(mw)
        for child in self.findChildren(QWidget):
            child.installEventFilter(mw)

    def _make_lbl(self, text, color, size, bold=False, pad=""):
        """创建样式化标签"""
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {color}; font-size: {size}px; {'font-weight: bold;' if bold else ''} padding: {pad};"
        )
        return label

    def refresh_qss(self):
        """将主题颜色应用到标题栏（菜单栏 + 工具栏行）"""
        tm = theme_manager
        text = tm.color("text_primary").name()
        text_title = tm.color("text_title").name()
        bg_hover = tm.color("bg_surface_hover").name()
        bg_raised = tm.color("bg_surface_raised").name()
        bg_title = tm.color("bg_title_bar").name()
        accent = tm.color("accent").name()
        border = tm.color("border").name()

        # 标题栏整体背景
        self.setStyleSheet(f"background: {bg_title};")

        # 应用标题
        if hasattr(self, '_app_title_lbl'):
            self._app_title_lbl.setStyleSheet(
                f"color: {text_title}; font-size: 30px; font-weight: bold; padding: 0 0 0 5px;"
            )

        # 菜单栏
        if hasattr(self, '_menu_bar'):
            self._menu_bar.setStyleSheet(
                f"QMenuBar {{ background: transparent; color: {text}; padding: 0; margin: 1px 0; }}"
                f"QMenuBar::item {{ padding: 6px 12px; background: transparent; }}"
                f"QMenuBar::item:selected {{ background: {bg_hover}; }}"
                f"QMenu {{ background: {bg_raised}; color: {text}; border: 1px solid {border}; }}"
                f"QMenu::item {{ padding: 6px 30px 6px 16px; }}"
                f"QMenu::item:selected {{ background: {accent}; }}"
                f"QMenu::separator {{ height: 1px; background: {border}; margin: 4px 10px; }}"
            )

        # 工具栏行
        if hasattr(self, '_toolbar_row'):
            self._toolbar_row.setStyleSheet(
                f"background: {bg_raised}; border-top: 1px solid {border};"
            )

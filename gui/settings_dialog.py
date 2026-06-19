"""系统设置对话框 — 主题选择、通用设置、显示设置

依照 crop_dialog.py 模式：一个文件一个 QDialog 子类。
"""

import json

from PyQt5.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout,
                             QSplitter, QLabel, QTabWidget,
                             QPushButton, QFrame, QStackedWidget, QListWidget,
                             QListWidgetItem, QScrollArea, QGroupBox, QGridLayout,
                             QCheckBox, QFormLayout)
from PyQt5.QtCore import Qt

from gui.theme import theme_manager
from gui.constants import app_config_path


class SettingsDialog(QDialog):
    """系统设置对话框

    布局：QTabWidget（主题 / 基本设置 / 显示设置）+ 底部按钮行
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

    # ── 导航框 ──────────────────────────────────────────

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

    # ── Tab 1: 主题 ─────────────────────────────────────

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
        c = tdef.resolve()
        card = QFrame()
        card.setFixedSize(200, 100)
        card.setCursor(Qt.PointingHandCursor)
        card.setToolTip(f"{tdef.name} - {tdef.description}")

        is_current = tdef.id == theme_manager.current_theme_id
        border = c.get("accent", "#3399FF") if is_current else c.get("border", "#555")
        bw = 2 if is_current else 1
        card.setStyleSheet(
            f"QFrame {{ background: {c.get('bg_surface', '#333')}; "
            f"border: {bw}px solid {border}; border-radius: 6px; }}")
        card.mousePressEvent = lambda e, tid=tdef.id: self._on_theme_select(tid)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(8, 6, 8, 6)
        inner.setSpacing(3)

        p = QLabel(f"[{tdef.prompt or tdef.name}]")
        p.setAlignment(Qt.AlignCenter)
        p.setStyleSheet(f"color: {c.get('text_title', '#ccc')}; font-weight: bold; "
                        f"border: none; background: transparent;")
        inner.addWidget(p)

        n = QLabel(tdef.name)
        n.setAlignment(Qt.AlignCenter)
        n.setStyleSheet(f"color: {c.get('text_primary', '#ccc')}; border: none; background: transparent;")
        inner.addWidget(n)

        d = QLabel(tdef.description or "")
        d.setAlignment(Qt.AlignCenter)
        d.setWordWrap(True)
        d.setStyleSheet(f"color: {c.get('text_secondary', '#999')}; font-size: 9px; "
                        f"border: none; background: transparent;")
        inner.addWidget(d)
        return card

    def _on_theme_select(self, theme_id):
        theme_manager.set_theme(theme_id)

    # ── Tab 2: 基本设置 ─────────────────────────────────

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

    # ── Tab 3: 显示设置 ─────────────────────────────────

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

    # ── 持久化 ──────────────────────────────────────────

    def _load_settings(self):
        try:
            with open(app_config_path(), "r", encoding="utf-8") as f:
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
        with open(app_config_path(), "w", encoding="utf-8") as f:
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

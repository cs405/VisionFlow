"""主题系统

数据驱动的主题引擎：
  - 5个内置主题（暗色、亮色、默认、科技蓝、紫色）
  - color(key) → QColor 统一访问器
  - 持久化：保存/加载主题选择到用户配置
  - 可扩展：通过向 theme_data.py 添加条目来增加主题
"""

from __future__ import annotations

import json
from pathlib import Path

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import Qt, pyqtSignal, QObject

from gui.theme_data import THEMES, ThemeDef


def _config_path() -> str:
    candidates = [
        Path(__file__).parent.parent / "theme_config.json",
        Path.home() / ".visionflow_theme.json",
    ]
    for p in candidates:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            return str(p)
        except Exception:
            continue
    return str(candidates[0])


# ═══════════════════════════════════════════════════════════════════════════
# 调色板 / 样式表构建器
# ═══════════════════════════════════════════════════════════════════════════

def _build_palette(tm: "ThemeManager") -> QPalette:
    """从当前主题颜色构建 QPalette"""
    c = tm.color
    p = QPalette()
    p.setColor(QPalette.Window, c("bg_surface"))
    p.setColor(QPalette.WindowText, c("text_primary"))
    p.setColor(QPalette.Base, c("bg_surface_deep"))
    p.setColor(QPalette.AlternateBase, c("bg_surface"))
    if c("bg_surface_deep").lightness() < 128:
        p.setColor(QPalette.ToolTipBase, QColor(60, 60, 60))
    else:
        p.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    p.setColor(QPalette.ToolTipText, c("text_primary"))
    p.setColor(QPalette.Text, c("text_primary"))
    p.setColor(QPalette.Button, c("bg_surface"))
    p.setColor(QPalette.ButtonText, c("text_primary"))
    p.setColor(QPalette.Link, c("accent"))
    p.setColor(QPalette.Highlight, c("accent"))
    p.setColor(QPalette.HighlightedText, c("accent_text"))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(128, 128, 128))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(128, 128, 128))
    return p


def _build_stylesheet(tm: "ThemeManager") -> str:
    """从当前主题颜色构建全局 QSS 样式表"""
    c = tm.color
    return f"""
        /* ── 全局默认值 ── */
        QWidget {{ background: {c("bg_surface").name()}; color: {c("text_primary").name()}; }}
        QMainWindow {{ background: {c("bg_surface_deep").name()}; }}
        QMainWindow::separator {{ background: {c("border").name()}; width: 1px; height: 1px; }}

        /* ── 工具提示 ── */
        QToolTip {{ color: {c("text_primary").name()}; background: {c("bg_surface_input").name()}; border: 1px solid {c("border").name()}; padding: 4px; }}

        /* ── 菜单 ── */
        QMenuBar {{ background: {c("bg_surface").name()}; color: {c("text_primary").name()}; }}
        QMenuBar::item:selected {{ background: {c("bg_surface_hover").name()}; }}
        QMenu {{ background: {c("bg_surface").name()}; color: {c("text_primary").name()}; border: 1px solid {c("border").name()}; }}
        QMenu::item:selected {{ background: {c("accent").name()}; color: {c("accent_text").name()}; }}
        QMenu::separator {{ height: 1px; background: {c("border").name()}; margin: 4px 10px; }}

        /* ── 状态栏 ── */
        QStatusBar {{ background: #007acc; color: white; }}

        /* ── 滚动条 ── */
        QScrollBar:vertical {{ background: {c("scroll_bg").name()}; width: 10px; }}
        QScrollBar::handle:vertical {{ background: {c("scroll_handle").name()}; min-height: 20px; border-radius: 5px; }}
        QScrollBar::handle:vertical:hover {{ background: {c("scroll_handle_hover").name()}; }}
        QScrollBar:horizontal {{ background: {c("scroll_bg").name()}; height: 10px; }}
        QScrollBar::handle:horizontal {{ background: {c("scroll_handle").name()}; min-width: 20px; border-radius: 5px; }}
        QScrollBar::handle:horizontal:hover {{ background: {c("scroll_handle_hover").name()}; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}

        /* ── 树/列表 ── */
        QTreeWidget, QTreeView, QListView, QListWidget {{ background: {c("bg_surface").name()}; color: {c("text_primary").name()}; border: none; outline: none; }}
        QTreeWidget::item:hover, QTreeView::item:hover, QListView::item:hover, QListWidget::item:hover {{ background: {c("bg_surface_hover").name()}; }}
        QTreeWidget::item:selected, QTreeView::item:selected, QListWidget::item:selected {{ background: #094771; color: white; }}

        /* ── 分割器 ── */
        QSplitter::handle {{ background: {c("border").name()}; }}

        /* ── 标签页 ── */
        QTabWidget::pane {{ border: 1px solid {c("border").name()}; background: {c("bg_surface").name()}; }}
        QTabBar::tab {{ background: {c("bg_surface_raised").name()}; color: {c("text_primary").name()}; padding: 6px 12px; border-bottom: 2px solid transparent; }}
        QTabBar::tab:selected {{ background: {c("bg_surface").name()}; border-bottom: 2px solid {c("accent").name()}; }}
        QTabBar::tab:hover {{ background: {c("bg_surface_hover").name()}; }}

        /* ── 表格 ── */
        QTableView, QTableWidget {{ background: {c("bg_surface").name()}; color: {c("text_primary").name()}; border: 1px solid {c("border").name()}; gridline-color: {c("border").name()}; selection-background-color: #094771; }}
        QHeaderView::section {{ background: {c("bg_surface_raised").name()}; color: {c("text_primary").name()}; padding: 4px 8px; border: none; border-right: 1px solid {c("border").name()}; border-bottom: 1px solid {c("border").name()}; }}

        /* ── 输入框 ── */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{ background: {c("bg_surface_input").name()}; color: {c("text_primary").name()}; border: 1px solid {c("border").name()}; padding: 4px 8px; border-radius: 3px; selection-background-color: {c("accent").name()}; }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {c("accent").name()}; }}
        QComboBox QAbstractItemView {{ background: {c("bg_surface").name()}; color: {c("text_primary").name()}; selection-background-color: {c("accent").name()}; }}
        QComboBox::drop-down {{ border: none; }}

        /* ── 按钮 ── */
        QPushButton {{ background: {c("accent").name()}; color: {c("accent_text").name()}; border: none; padding: 6px 16px; border-radius: 3px; }}
        QPushButton:hover {{ background: #1a8ad4; }}
        QPushButton:pressed {{ background: #005a9e; }}
        QPushButton:disabled {{ background: {c("border").name()}; color: {c("text_disabled").name()}; }}
        QToolButton {{ background: transparent; border: none; color: {c("text_primary").name()}; }}
        QToolButton:hover {{ background: {c("bg_surface_hover").name()}; }}

        /* ── 复选框/单选按钮 ── */
        QCheckBox, QRadioButton {{ color: {c("text_primary").name()}; }}

        /* ── 标签 ── */
        QLabel {{ color: {c("text_primary").name()}; }}

        /* ── 分组框 ── */
        QGroupBox {{ color: {c("text_primary").name()}; border: 1px solid {c("border").name()}; margin-top: 12px; padding-top: 16px; font-weight: bold; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 6px; }}

        /* ── 框架/分隔线 ── */
        QFrame[frameShape=\"4\"] {{ color: {c("border").name()}; }}  /* HLine */
        QFrame[frameShape=\"5\"] {{ color: {c("border").name()}; }}  /* VLine */

        /* ── 对话框 ── */
        QDialog {{ background: {c("bg_surface").name()}; }}
    """


# ═══════════════════════════════════════════════════════════════════════════
# 主题管理器
# ═══════════════════════════════════════════════════════════════════════════

class ThemeManager(QObject):
    """中央主题服务

    用法：
        # 统一访问器
        accent = theme_manager.color("accent")

        # 切换主题
        theme_manager.set_theme("light")
        theme_manager.toggle_dark()

        # 列出可用主题
        for t in theme_manager.available_themes:
            print(t.id, t.name, t.group)
    """

    theme_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._theme_id: str = "dark"
        self._active_colors: dict[str, str] = {}
        self._theme_def: ThemeDef | None = None

        loaded = self._load()
        if loaded and loaded in THEMES:
            self._theme_id = loaded
        self._apply()

    # ── 公共 API ──────────────────────────────────────────────────────

    def color(self, key: str) -> QColor:
        """统一颜色访问器。如果键未知，返回黑色"""
        hex_val = self._active_colors.get(key)
        if hex_val is None:
            return QColor(0, 0, 0)
        return QColor(hex_val)

    def to_palette(self) -> QPalette:
        """构建当前主题的 QPalette"""
        return _build_palette(self)

    def get_stylesheet(self) -> str:
        """构建当前主题的 QSS 样式表"""
        return _build_stylesheet(self)

    def set_theme(self, theme_id: str):
        """切换到指定主题"""
        if theme_id == self._theme_id:
            return
        if theme_id not in THEMES:
            return
        self._theme_id = theme_id
        self._apply()
        self._save()

    def toggle_dark(self):
        """在暗色/亮色之间切换"""
        current = THEMES.get(self._theme_id)
        if current is None:
            self.set_theme("dark")
            return
        target_is_dark = not current.is_dark
        for tid, tdef in THEMES.items():
            if tdef.is_dark == target_is_dark and tdef.group == "强力推荐":
                self.set_theme(tid)
                return
        for tid, tdef in THEMES.items():
            if tdef.is_dark == target_is_dark:
                self.set_theme(tid)
                return

    @property
    def current_theme_id(self) -> str:
        return self._theme_id

    @property
    def current_theme_name(self) -> str:
        t = THEMES.get(self._theme_id)
        return t.name if t else self._theme_id

    @property
    def is_dark(self) -> bool:
        t = THEMES.get(self._theme_id)
        return t.is_dark if t else True

    @property
    def available_themes(self) -> list[ThemeDef]:
        return sorted(THEMES.values(), key=lambda t: t.order)

    # ── 内部 ────────────────────────────────────────────────────────

    def _apply(self):
        tdef = THEMES.get(self._theme_id)
        if tdef is None:
            tdef = THEMES["dark"]
            self._theme_id = "dark"
        self._theme_def = tdef
        self._active_colors = tdef.resolve()
        self.theme_changed.emit(self._theme_id)

    def _save(self):
        try:
            data = {"theme": self._theme_id}
            with open(_config_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load(self) -> str | None:
        for path in [
            Path(__file__).parent.parent / "theme_config.json",
            Path.home() / ".visionflow_theme.json",
        ]:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    theme_id = data.get("theme", "")
                    if theme_id in THEMES:
                        return theme_id
            except Exception:
                continue
        return None


# 全局单例
theme_manager = ThemeManager()


# ═══════════════════════════════════════════════════════════════════════════
# 主题感知辅助
# ═══════════════════════════════════════════════════════════════════════════

def connect_theme(refresh_fn):
    """注册主题变化时的回调，并立即执行一次

    用法：
        connect_theme(self._refresh_qss)
    """
    refresh_fn()
    theme_manager.theme_changed.connect(lambda _: refresh_fn())


# ═══════════════════════════════════════════════════════════════════════════
# 主题选择对话框
# ═══════════════════════════════════════════════════════════════════════════

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QGroupBox, QScrollArea, QWidget,
                               QGridLayout, QFrame)
from PyQt5.QtCore import Qt as QtCore_Qt

class ThemePickerDialog(QDialog):
    """颜色主题选择器

    布局：分组框 + 卡片网格。
    点击卡片 → 立即预览。确定 = 保留，取消 = 恢复到原始。
    """

    CARD_W = 250
    CARD_H = 150
    COLS = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("颜色主题")
        self.setMinimumSize(580, 480)
        self._original_theme = theme_manager.current_theme_id
        self._selected_id: str | None = None
        self._cards: dict[str, QFrame] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(14)

        groups: dict[str, list] = {}
        for t in theme_manager.available_themes:
            groups.setdefault(t.group, []).append(t)

        for group_name in ["强力推荐", "纯色", "外部主题", "自定义"]:
            if group_name not in groups:
                continue
            group_box = QGroupBox(group_name)
            group_box.setStyleSheet(f"""
                QGroupBox {{ font-weight: bold; border: 1px solid {theme_manager.color('border').name()};
                             margin-top: 14px; padding-top: 18px; }}
                QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; }}
            """)
            grid = QGridLayout()
            grid.setSpacing(10)
            for i, tdef in enumerate(groups[group_name]):
                card = self._make_card(tdef)
                grid.addWidget(card, i // self.COLS, i % self.COLS)
            group_box.setLayout(grid)
            container_layout.addWidget(group_box)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(cancel_btn)
        ok_btn = QPushButton("确定")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        self._update_card_highlights()

    def _make_card(self, tdef) -> QFrame:
        """构建 250x150 主题预览卡片"""
        c = tdef.resolve()

        card = QFrame()
        card.setFixedSize(self.CARD_W, self.CARD_H)
        card.setCursor(QtCore_Qt.PointingHandCursor)
        card.setToolTip(f"{tdef.name} — {tdef.description}")

        card.setStyleSheet(f"""
            QFrame {{
                background: {c.get('bg_surface', '#333')};
                border: 1px solid {c.get('border', '#555')};
                border-radius: 6px;
            }}
        """)

        card.mousePressEvent = lambda e, tid=tdef.id: self._select(tid)
        self._cards[tdef.id] = card

        inner = QVBoxLayout(card)
        inner.setContentsMargins(10, 10, 10, 10)
        inner.setSpacing(4)

        prompt = tdef.prompt or tdef.name
        p_lbl = QLabel(f"【{prompt}】")
        p_lbl.setAlignment(QtCore_Qt.AlignCenter)
        p_lbl.setStyleSheet(f"color: {c.get('text_title', c.get('text_primary','#ccc'))}; "
                            f"font-weight: bold; font-size: 12px; border: none; background: transparent;")
        inner.addWidget(p_lbl)

        n_lbl = QLabel(tdef.name)
        n_lbl.setAlignment(QtCore_Qt.AlignCenter)
        n_lbl.setStyleSheet(f"color: {c.get('text_primary', '#ccc')}; font-size: 11px; "
                            f"border: none; background: transparent;")
        inner.addWidget(n_lbl)

        desc = tdef.description or f"{'深色' if tdef.is_dark else '浅色'}主题"
        d_lbl = QLabel(desc)
        d_lbl.setAlignment(QtCore_Qt.AlignCenter)
        d_lbl.setWordWrap(True)
        d_lbl.setStyleSheet(f"color: {c.get('text_secondary', '#999')}; font-size: 9px; "
                            f"border: none; background: transparent;")
        inner.addWidget(d_lbl)

        inner.addStretch()

        btn = QPushButton("默认按钮")
        btn.setEnabled(False)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {c.get('bg_caption', c.get('bg_surface_raised','#444'))};
                color: {c.get('text_caption', c.get('text_primary','#ccc'))};
                border: 1px solid {c.get('border', '#555')};
                border-radius: 3px; padding: 3px 12px; font-size: 10px;
            }}
        """)
        inner.addWidget(btn)

        return card

    def _select(self, theme_id: str):
        """点击时立即预览主题"""
        theme_manager.set_theme(theme_id)
        self._selected_id = theme_id
        self._update_card_highlights()

    def _update_card_highlights(self):
        """更新卡片边框高亮"""
        current = theme_manager.current_theme_id
        for tid, card in self._cards.items():
            tdef = next((t for t in theme_manager.available_themes if t.id == tid), None)
            if tdef is None:
                continue
            c = tdef.resolve()
            border = c.get('accent', '#3399FF') if tid == current else c.get('border', '#555')
            width = 3 if tid == current else 1
            card.setStyleSheet(f"""
                QFrame {{ background: {c.get('bg_surface', '#333')};
                         border: {width}px solid {border}; border-radius: 6px; }}
            """)

    def _on_accept(self):
        self.accept()

    def _on_cancel(self):
        if self._original_theme != theme_manager.current_theme_id:
            theme_manager.set_theme(self._original_theme)
        self.reject()

    def exec_(self) -> int:
        result = super().exec_()
        if result != QDialog.Accepted:
            self._on_cancel()
        return bool(self._selected_id) or (result == QDialog.Accepted)

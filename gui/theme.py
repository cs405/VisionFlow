"""Theme system — WPF H.Themes + ThemeOptions 1:1 port.

Data-driven theme engine with:
  - 5 built-in themes (Dark, Light, Default, Technology Blue, Purple)
  - color(key) → QColor unified accessor (replaces hardcoded QColor)
  - Persistence: save/load theme choice to user config
  - Backward compatible: colors property, get_stylesheet(), to_palette()
  - Extensible: add themes by adding entries to theme_data.py

WPF alignment:
  - ThemeOptions.Instance.ColorResource ↔ ThemeManager.current_theme_id
  - ThemeOptions.RefreshTheme()       ↔ ThemeManager._apply()
  - ColorKeys + BrushKeys             ↔ COLOR_KEYS + resolve_colors()
  - ResourceDictionary swap           ↔ _active_colors dict replace
  - Persistence                       ↔ JSON save/load
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import Qt, pyqtSignal, QObject

from gui.theme_data import (
    THEMES, COLOR_KEYS, ThemeDef, resolve_colors, get_theme_ids, get_theme_by_id,
)


# Config path — saved next to the app or in user home
def _config_path() -> str:
    """Get theme config file path (WPF AppPaths.UserSetting equivalent)."""
    candidates = [
        Path(__file__).parent.parent / "theme_config.json",   # project root
        Path.home() / ".visionflow_theme.json",               # user home
    ]
    for p in candidates:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            return str(p)
        except Exception:
            continue
    return str(candidates[0])


# ═══════════════════════════════════════════════════════════════════════════
# Legacy-style colors object — backward compat with existing code
# ═══════════════════════════════════════════════════════════════════════════

class _ThemeColorsProxy:
    """Backward-compatible attribute-access wrapper over the active color map.

    Existing code like `theme_manager.colors.node_bg` continues to work.
    New code should prefer `theme_manager.color("node_bg")`.
    """

    def __init__(self, manager: "ThemeManager"):
        self._manager = manager

    def __getattr__(self, name: str):
        # Map legacy attribute names to color key IDs
        key = _LEGACY_TO_KEY.get(name, name)
        val = self._manager._active_colors.get(key)
        if val is None:
            return QColor()
        return QColor(val)

    def __dir__(self):
        return list(COLOR_KEYS.keys())

    # ── Palette + Stylesheet (delegated from legacy ThemeColors) ──────────

    def to_palette(self) -> QPalette:
        return _build_palette(self)

    @property
    def stylesheet(self) -> str:
        return _build_stylesheet(self)


# Map old attribute names → new ColorKey IDs
_LEGACY_TO_KEY = {
    "window_bg":         "bg_window",
    "title_bar_bg":      "bg_title_bar",
    "title_bar_text":    "text_title",
    "surface":           "bg_surface",
    "surface_raised":    "bg_surface_raised",
    "surface_hover":     "bg_surface_hover",
    "surface_input":     "bg_surface_input",
    "surface_deep":      "bg_surface_deep",
    "status_ok":         "status_ok",
    "status_error":      "status_error",
    "status_running":    "status_running",
    "status_idle":       "status_idle",
    "port_input":        "port_input",
    "port_output":       "port_output",
    "link":              "edge",
    "link_selected":     "edge_selected",
    "checker_base":      "canvas_checker_base",
    "checker_alt":       "canvas_checker_alt",
    "canvas_bg":         "canvas_bg",
    "node_bg":           "node_bg",
    "node_bg_hover":     "node_bg_hover",
    "node_bg_selected":  "node_bg_selected",
    "node_border":       "node_border",
    "node_border_selected": "node_border_selected",
    "node_text":         "node_text",
    "node_flag_default": "gray",
    "node_shadow":       "node_shadow",
    "scroll_bg":         "scroll_bg",
    "scroll_handle":     "scroll_handle",
    "scroll_handle_hover": "scroll_handle_hover",
}


# ═══════════════════════════════════════════════════════════════════════════
# Palette builder — independent from proxy class
# ═══════════════════════════════════════════════════════════════════════════

def _build_palette(colors) -> QPalette:
    """Build QPalette from resolved colors (WPF to_palette equivalent)."""
    p = QPalette()
    p.setColor(QPalette.Window, QColor(colors.surface))
    p.setColor(QPalette.WindowText, QColor(colors.text_primary))
    p.setColor(QPalette.Base, QColor(colors.surface_deep))
    p.setColor(QPalette.AlternateBase, QColor(colors.surface))
    p.setColor(QPalette.ToolTipBase, QColor(60, 60, 60) if colors.surface_deep.lightness() < 128 else QColor(255, 255, 255))
    p.setColor(QPalette.ToolTipText, QColor(colors.text_primary))
    p.setColor(QPalette.Text, QColor(colors.text_primary))
    p.setColor(QPalette.Button, QColor(colors.surface))
    p.setColor(QPalette.ButtonText, QColor(colors.text_primary))
    p.setColor(QPalette.Link, QColor(colors.accent))
    p.setColor(QPalette.Highlight, QColor(colors.accent))
    p.setColor(QPalette.HighlightedText, QColor(colors.accent_text))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(128, 128, 128))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(128, 128, 128))
    return p


def _build_stylesheet(colors) -> str:
    """Build QSS from resolved colors (WPF ThemeColors.stylesheet equivalent)."""
    c = colors   # shorthand
    return f"""
        QToolTip {{ color: {c.text_primary.name()}; background: {c.bg_surface_input.name()}; border: 1px solid {c.border.name()}; padding: 4px; }}
        QMenuBar {{ background: {c.bg_surface.name()}; color: {c.text_primary.name()}; }}
        QMenuBar::item:selected {{ background: {c.bg_surface_hover.name()}; }}
        QMenu {{ background: {c.bg_surface.name()}; color: {c.text_primary.name()}; border: 1px solid {c.border.name()}; }}
        QMenu::item:selected {{ background: {c.accent.name()}; }}
        QMenu::separator {{ height: 1px; background: {c.border.name()}; margin: 4px 10px; }}
        QStatusBar {{ background: #007acc; color: white; }}
        QScrollBar:vertical {{ background: {c.scroll_bg.name()}; width: 10px; }}
        QScrollBar::handle:vertical {{ background: {c.scroll_handle.name()}; min-height: 20px; border-radius: 5px; }}
        QScrollBar::handle:vertical:hover {{ background: {c.scroll_handle_hover.name()}; }}
        QScrollBar:horizontal {{ background: {c.scroll_bg.name()}; height: 10px; }}
        QScrollBar::handle:horizontal {{ background: {c.scroll_handle.name()}; min-width: 20px; border-radius: 5px; }}
        QScrollBar::handle:horizontal:hover {{ background: {c.scroll_handle_hover.name()}; }}
        QTreeWidget {{ background: {c.bg_surface.name()}; color: {c.text_primary.name()}; border: none; }}
        QTreeWidget::item:hover {{ background: {c.bg_surface_hover.name()}; }}
        QTreeWidget::item:selected {{ background: #094771; }}
        QSplitter::handle {{ background: {c.border.name()}; }}
        QTabWidget::pane {{ border: 1px solid {c.border.name()}; background: {c.bg_surface.name()}; }}
        QTabBar::tab {{ background: {c.bg_surface_raised.name()}; color: {c.text_primary.name()}; padding: 6px 12px; border-bottom: 2px solid transparent; }}
        QTabBar::tab:selected {{ background: {c.bg_surface.name()}; border-bottom: 2px solid {c.accent.name()}; }}
        QTabBar::tab:hover {{ background: {c.bg_surface_hover.name()}; }}
        QTableView, QTableWidget {{ background: {c.bg_surface.name()}; color: {c.text_primary.name()}; border: 1px solid {c.border.name()}; gridline-color: {c.border.name()}; selection-background-color: #094771; }}
        QHeaderView::section {{ background: {c.bg_surface_raised.name()}; color: {c.text_primary.name()}; padding: 4px 8px; border: none; border-right: 1px solid {c.border.name()}; border-bottom: 1px solid {c.border.name()}; }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {c.bg_surface_input.name()}; color: {c.text_primary.name()}; border: 1px solid {c.border.name()}; padding: 4px 8px; border-radius: 3px; }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {c.accent.name()}; }}
        QComboBox QAbstractItemView {{ background: {c.bg_surface.name()}; color: {c.text_primary.name()}; selection-background-color: {c.accent.name()}; }}
        QCheckBox {{ color: {c.text_primary.name()}; }}
        QPushButton {{ background: {c.accent.name()}; color: {c.accent_text.name()}; border: none; padding: 6px 16px; border-radius: 3px; }}
        QPushButton:hover {{ background: #1a8ad4; }}
        QPushButton:pressed {{ background: #005a9e; }}
        QPushButton:disabled {{ background: {c.border.name()}; color: {c.text_disabled.name()}; }}
        QLabel {{ color: {c.text_primary.name()}; }}
    """


# ═══════════════════════════════════════════════════════════════════════════
# ThemeManager — WPF ThemeOptions + ThemeService
# ═══════════════════════════════════════════════════════════════════════════

class ThemeManager(QObject):
    """Central theme service — WPF ThemeOptions + ILoadThemeOptionsService.

    Manages the active theme, provides color access, and persists choice.

    Usage:
        # Unified accessor (preferred for new code)
        accent = theme_manager.color("accent")

        # Backward-compatible attribute access
        accent = theme_manager.colors.accent

        # Switch themes
        theme_manager.set_theme("light")
        theme_manager.set_theme("technology_blue")
        theme_manager.toggle_dark()    # toggle between dark/light

        # List available themes for UI
        for t in theme_manager.available_themes:
            print(t.id, t.name, t.group)
    """

    theme_changed = pyqtSignal(str)   # emits new theme_id

    def __init__(self):
        super().__init__()
        self._theme_id: str = "dark"                            # active theme ID
        self._active_colors: dict[str, str] = {}                # resolved key→hex
        self._theme_def: ThemeDef | None = None                 # active ThemeDef
        self.colors = _ThemeColorsProxy(self)                   # backward compat proxy

        # Load persisted choice, fall back to dark
        loaded = self._load()
        if loaded and loaded in THEMES:
            self._theme_id = loaded
        self._apply()

    # ── Public API ──────────────────────────────────────────────────────

    def color(self, key: str) -> QColor:
        """Unified color accessor — WPF {DynamicResource BrushKeys.Xxx}.

        All GUI code should use this instead of hardcoding QColor("#...").
        Returns black if key is unknown (safe fallback).
        """
        hex_val = self._active_colors.get(key)
        if hex_val is None:
            return QColor(0, 0, 0)
        return QColor(hex_val)

    def set_theme(self, theme_id: str):
        """Switch to a different theme — WPF ThemeOptions.ColorResource setter."""
        if theme_id == self._theme_id:
            return
        if theme_id not in THEMES:
            return
        self._theme_id = theme_id
        self._apply()
        self._save()

    def toggle_dark(self):
        """Toggle between dark/light — WPF ThemeOptions.SwitchDark()."""
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

    def toggle(self):
        """Backward-compat alias for toggle_dark()."""
        self.toggle_dark()

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
        """All registered themes in display order — WPF ThemeOptions.ColorResources."""
        return sorted(THEMES.values(), key=lambda t: t.order)

    def get_stylesheet(self) -> str:
        """Current theme QSS stylesheet (backward compat)."""
        return self.colors.stylesheet

    # ── Internal ────────────────────────────────────────────────────────

    def _apply(self):
        """Resolve colors for the current theme and notify — WPF RefreshTheme()."""
        tdef = THEMES.get(self._theme_id)
        if tdef is None:
            tdef = THEMES["dark"]
            self._theme_id = "dark"
        self._theme_def = tdef
        self._active_colors = resolve_colors(tdef)
        self.theme_changed.emit(self._theme_id)

    def _save(self):
        """Persist theme choice to JSON — WPF ThemeOptions.Save()."""
        try:
            data = {"theme": self._theme_id}
            with open(_config_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass   # non-critical — don't crash if config can't be written

    def _load(self) -> str | None:
        """Load persisted theme choice — WPF ThemeOptions.Load()."""
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


# Global singleton — WPF ThemeOptions.Instance
theme_manager = ThemeManager()


# ═══════════════════════════════════════════════════════════════════════════
# Theme Picker Dialog — WPF ColorThemeViewPresenter
# ═══════════════════════════════════════════════════════════════════════════

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QGroupBox, QScrollArea, QWidget,
                               QGridLayout, QFrame)
from PyQt5.QtCore import Qt as QtCore_Qt

class ThemePickerDialog(QDialog):
    """Color theme picker — WPF ColorThemeViewPresenter 1:1 port.

    Layout: GroupBox groups with WrapPanel-style card grid.
    Each card = 250x150 QFrame rendered in the theme's OWN colors.
    Click a card → immediate preview (WPF SelectionChanged → RefreshThemeCommand).
    OK = keep, Cancel = revert to original.
    """

    CARD_W, CARD_H = 250, 150
    COLS = 2  # cards per row in group grid

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

        # Group themes by GroupName (WPF CollectionViewSource GroupDescriptions)
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

        # Bottom buttons
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

        # Highlight the currently active theme card
        self._update_card_highlights()

    # ── Card factory (WPF ItemTemplate 250×150 Border) ──────────────────

    def _make_card(self, tdef) -> QFrame:
        """Build a 250x150 preview card rendered in the theme's own colors.

        WPF XAML:
          Border 250x150, Background={DynamicResource ColorKeys.Background}
            UniformGrid (1 col):
              TextBlock 【Prompt】 (ForegroundTitle)
              TextBlock Name    (Foreground)
              TextBlock Desc    (ForegroundAssist, wrap)
              UniformGrid (1 row): Button "默认按钮" (CaptionBackground/CaptionForeground)
        """
        from gui.theme_data import resolve_colors
        c = resolve_colors(tdef)  # full resolved color map for this theme

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

        # Click → select + immediate apply
        card.mousePressEvent = lambda e, tid=tdef.id: self._select(tid)
        self._cards[tdef.id] = card

        inner = QVBoxLayout(card)
        inner.setContentsMargins(10, 10, 10, 10)
        inner.setSpacing(4)

        # Row 1: 【Prompt】 (WPF ForegroundTitle)
        prompt = tdef.prompt or tdef.name
        p_lbl = QLabel(f"【{prompt}】")
        p_lbl.setAlignment(QtCore_Qt.AlignCenter)
        p_lbl.setStyleSheet(f"color: {c.get('text_title', c.get('text_primary','#ccc'))}; "
                            f"font-weight: bold; font-size: 12px; border: none; background: transparent;")
        inner.addWidget(p_lbl)

        # Row 2: Name (WPF Foreground)
        n_lbl = QLabel(tdef.name)
        n_lbl.setAlignment(QtCore_Qt.AlignCenter)
        n_lbl.setStyleSheet(f"color: {c.get('text_primary', '#ccc')}; font-size: 11px; "
                            f"border: none; background: transparent;")
        inner.addWidget(n_lbl)

        # Row 3: Description (WPF ForegroundAssist, wrap + ellipsis)
        desc = tdef.description or f"{'深色' if tdef.is_dark else '浅色'}主题"
        d_lbl = QLabel(desc)
        d_lbl.setAlignment(QtCore_Qt.AlignCenter)
        d_lbl.setWordWrap(True)
        d_lbl.setStyleSheet(f"color: {c.get('text_secondary', '#999')}; font-size: 9px; "
                            f"border: none; background: transparent;")
        inner.addWidget(d_lbl)

        inner.addStretch()

        # Row 4: "默认按钮" (WPF CaptionBackground / CaptionForeground)
        btn = QPushButton("默认按钮")
        btn.setEnabled(False)   # display-only, not interactive
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

    # ── Selection (WPF SelectionChanged → RefreshThemeCommand) ──────────

    def _select(self, theme_id: str):
        """Immediate apply on click — WPF TwoWay SelectedItem binding."""
        theme_manager.set_theme(theme_id)
        self._selected_id = theme_id
        self._update_card_highlights()

    def _update_card_highlights(self):
        """Update card borders: accent border for selected, normal for others."""
        current = theme_manager.current_theme_id
        for tid, card in self._cards.items():
            tdef = next((t for t in theme_manager.available_themes if t.id == tid), None)
            if tdef is None:
                continue
            from gui.theme_data import resolve_colors
            c = resolve_colors(tdef)
            border = c.get('accent', '#3399FF') if tid == current else c.get('border', '#555')
            width = 3 if tid == current else 1
            card.setStyleSheet(f"""
                QFrame {{ background: {c.get('bg_surface', '#333')};
                         border: {width}px solid {border}; border-radius: 6px; }}
            """)

    # ── Accept / Cancel ──────────────────────────────────────────────────

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


"""内联状态栏控件 — 彩色圆点 + 状态文字，支持主题切换"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from gui.theme import theme_manager, connect_theme


class InlineStatusStrip(QWidget):
    """底部内联状态栏：● 图标 + 文本标签，主题感知"""

    def __init__(self, accent: str = "#4caf50", parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        self._accent = accent
        self._current_icon_color = accent

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        self._icon = QLabel("●")
        layout.addWidget(self._icon)

        self._label = QLabel("就绪")
        self._label.setFont(QFont("Microsoft YaHei", 11))
        layout.addWidget(self._label, 1)

        connect_theme(self._refresh_qss)

    def _refresh_qss(self):
        tm = theme_manager
        self.setStyleSheet(
            f"background: {tm.color('bg_surface_deep').name()}; border-top: 1px solid {tm.color('border').name()}; outline: none;"
        )
        self._label.setStyleSheet(
            f"color: {tm.color('text_primary').name()}; font-size: 11px; background: transparent;"
        )
        self._icon.setStyleSheet(
            f"color: {self._current_icon_color}; font-weight: bold; background: transparent;"
        )

    def set_status(self, text: str, color: str | None = None):
        self._label.setText(text)
        self._current_icon_color = color or self._accent
        self._icon.setStyleSheet(
            f"color: {self._current_icon_color}; font-weight: bold; background: transparent;"
        )

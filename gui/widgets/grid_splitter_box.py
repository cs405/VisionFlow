from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame)

from gui.constants import MENU_MIN_WIDTH
from gui.theme import theme_manager, connect_theme


class GridSplitterBox(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(MENU_MIN_WIDTH)

        self._content_area = QWidget()
        content_vl = QVBoxLayout(self._content_area)
        content_vl.setContentsMargins(0, 0, 0, 0)
        content_vl.setSpacing(0)

        self._content_host = QWidget()
        self._content_host.setStyleSheet("background: transparent;")
        self._host_layout = QVBoxLayout(self._content_host)
        self._host_layout.setContentsMargins(0, 0, 0, 0)
        self._host_layout.setSpacing(0)
        content_vl.addWidget(self._content_host, 1)

        self._handle = QFrame()
        self._handle.setFrameShape(QFrame.VLine)
        self._handle.setFixedWidth(3)
        self._handle.setCursor(Qt.SplitHCursor)

        self._refresh_qss()
        connect_theme(lambda: self._refresh_qss())

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._content_area, 1)
        main_layout.addWidget(self._handle)


    def _refresh_qss(self):
        """主题变化时重新应用颜色"""
        bg = theme_manager.color("bg_surface").name()
        border = theme_manager.color("border").name()
        self._content_area.setStyleSheet(f"background: {bg};")
        self._handle.setStyleSheet(f"background: {border}; border: none;")

    def set_content(self, widget: QWidget):
        """设置此容器内部显示的主要内容控件"""
        while self._host_layout.count():
            item = self._host_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._host_layout.addWidget(widget)





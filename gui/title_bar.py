"""
自定义窗口标题栏 — WPF VisionMaster风格
支持拖拽移动、双击最大化、自定义按钮
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QFont, QMouseEvent, QIcon

from .theme import Colors, Fonts


class TitleBar(QWidget):
    """自定义标题栏"""

    # 信号
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, parent_window, title: str = "VisionFlow", icon: str = None):
        super().__init__()
        self.parent_window = parent_window
        self._dragging = False
        self._drag_pos = QPoint()

        self.setFixedHeight(32)
        self.setObjectName("titleBar")
        self.setStyleSheet(f"""
            #titleBar {{
                background-color: {Colors.BackgroundLight};
                border-bottom: 1px solid {Colors.Border};
            }}
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(0)

        # 窗口图标 + 标题
        title_label = QLabel(f"  {title}")
        title_label.setFont(Fonts.make(11))
        title_label.setStyleSheet(f"color: {Colors.Foreground}; border: none; background: transparent;")

        layout.addWidget(title_label)
        layout.addStretch()

        # 窗口控制按钮
        btn_style = f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Colors.ForegroundDim};
                font-size: 14px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BorderLight};
                color: {Colors.Foreground};
            }}
            QPushButton#btnClose:hover {{
                background-color: {Colors.Red};
                color: white;
            }}
        """

        btn_min = QPushButton("—")
        btn_min.setFixedSize(46, 32)
        btn_min.setStyleSheet(btn_style)
        btn_min.clicked.connect(self.minimize_clicked)
        btn_min.setToolTip("最小化")

        btn_max = QPushButton("□")
        btn_max.setFixedSize(46, 32)
        btn_max.setStyleSheet(btn_style)
        btn_max.clicked.connect(self.maximize_clicked)
        btn_max.setToolTip("最大化")

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(46, 32)
        btn_close.setObjectName("btnClose")
        btn_close.setStyleSheet(btn_style)
        btn_close.clicked.connect(self.close_clicked)
        btn_close.setToolTip("关闭")

        layout.addWidget(btn_min)
        layout.addWidget(btn_max)
        layout.addWidget(btn_close)

        self.setLayout(layout)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.parent_window.move(
                self.parent_window.x() + delta.x(),
                self.parent_window.y() + delta.y()
            )
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._dragging = False

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.maximize_clicked.emit()

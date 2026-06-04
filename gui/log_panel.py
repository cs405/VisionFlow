"""
日志面板 - 显示系统日志
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QHBoxLayout,
    QPushButton, QComboBox, QLabel  # 添加 QLabel
)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QColor, QTextCursor

from core.events import EventBus, Event, EventType


class LogPanel(QWidget):
    """日志面板"""

    LEVEL_COLORS = {
        "DEBUG": QColor(150, 150, 150),
        "INFO": QColor(100, 200, 100),
        "WARNING": QColor(200, 200, 100),
        "ERROR": QColor(200, 100, 100),
    }

    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)

        self.event_bus = event_bus
        self.min_level = "INFO"  # 最低显示级别

        # 布局
        layout = QVBoxLayout()

        # 工具栏
        toolbar = QHBoxLayout()

        self.level_combo = QComboBox()
        self.level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.level_combo.setCurrentText("INFO")
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        toolbar.addWidget(QLabel("日志级别:"))  # 现在 QLabel 已导入
        toolbar.addWidget(self.level_combo)

        toolbar.addStretch()

        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        # 文本显示
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFontFamily("Consolas")
        self.text_edit.setFontPointSize(10)
        layout.addWidget(self.text_edit)

        self.setLayout(layout)

        # 订阅事件
        self.event_bus.subscribe(EventType.LOG_MESSAGE, self._on_log_message)

    def _on_level_changed(self, level: str):
        """级别改变"""
        self.min_level = level

    def _on_log_message(self, event: Event):
        """收到日志消息"""
        data = event.data
        level = data.get("level", "INFO")
        message = data.get("message", "")
        module = data.get("module", "")

        # 级别过滤
        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if levels.index(level) < levels.index(self.min_level):
            return

        # 格式化消息
        time_str = QDateTime.currentDateTime().toString("HH:mm:ss.zzz")
        color = self.LEVEL_COLORS.get(level, QColor(200, 200, 200))

        formatted = f'<span style="color: #808080;">[{time_str}]</span> '
        formatted += f'<span style="color: {color.name()};">[{level}]</span> '
        if module:
            formatted += f'<span style="color: #6060ff;">[{module}]</span> '
        formatted += f'<span style="color: #ffffff;">{message}</span>'

        self.text_edit.append(formatted)

        # 自动滚动到底部
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_edit.setTextCursor(cursor)

    def clear(self):
        """清空日志"""
        self.text_edit.clear()

    def log(self, level: str, message: str, module: str = ""):
        """手动添加日志"""
        self.event_bus.emit_log(level, message, module)
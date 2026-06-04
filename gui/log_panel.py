"""Log panel - displays running log messages with filtering.

Ported from H.Modules.Messages.Notice + H.Services.Message.
"""

from datetime import datetime
from enum import Enum

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QHBoxLayout,
                              QPushButton, QToolBar, QAction)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QTextCursor, QColor, QFont

from core.events import EventType, event_system


class LogLevel(Enum):
    INFO = ("信息", QColor("#dcdcdc"))
    SUCCESS = ("成功", QColor("#4caf50"))
    WARN = ("警告", QColor("#ff9800"))
    ERROR = ("错误", QColor("#f44336"))
    FATAL = ("严重", QColor("#d32f2f"))


class LogPanel(QWidget):
    """Scrollable log panel with colored messages and filtering."""

    MAX_LINES = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_events()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar with clear/filter buttons
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 2)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setFixedHeight(24)
        self.clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(self.clear_btn)

        toolbar.addStretch()

        self.filter_info = QPushButton("信息")
        self.filter_info.setFixedHeight(24)
        self.filter_info.setCheckable(True)
        self.filter_info.setChecked(True)
        toolbar.addWidget(self.filter_info)

        self.filter_success = QPushButton("成功")
        self.filter_success.setFixedHeight(24)
        self.filter_success.setCheckable(True)
        self.filter_success.setChecked(True)
        toolbar.addWidget(self.filter_success)

        self.filter_warn = QPushButton("警告")
        self.filter_warn.setFixedHeight(24)
        self.filter_warn.setCheckable(True)
        self.filter_warn.setChecked(True)
        toolbar.addWidget(self.filter_warn)

        self.filter_error = QPushButton("错误")
        self.filter_error.setFixedHeight(24)
        self.filter_error.setCheckable(True)
        self.filter_error.setChecked(True)
        toolbar.addWidget(self.filter_error)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar)
        toolbar_widget.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        layout.addWidget(toolbar_widget)

        # Text edit for log display
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Consolas", 9))
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #dcdcdc;
                border: none;
                padding: 4px;
            }
        """)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        layout.addWidget(self.text_edit)

        # Style for filter buttons
        btn_style = """
            QPushButton {
                background: #3c3c3c;
                border: none;
                border-radius: 2px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QPushButton:checked {
                background: #0078d4;
                color: white;
            }
        """
        for btn in [self.filter_info, self.filter_success, self.filter_warn, self.filter_error]:
            btn.setStyleSheet(btn_style)

        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #505050;
                border-radius: 2px;
                padding: 2px 10px;
                font-size: 11px;
                color: #dcdcdc;
            }
            QPushButton:hover { background: #3e3e42; }
        """)

    def _connect_events(self):
        """Connect to event system for automatic logging."""
        event_system.subscribe(EventType.NODE_STARTED,
                               lambda s, **kw: self.info(f"节点开始: {s.name if s else '?'}"))
        event_system.subscribe(EventType.NODE_COMPLETED,
                               lambda s, **kw: self.success(f"节点完成: {s.name if s else '?'}"))
        event_system.subscribe(EventType.NODE_ERROR,
                               lambda s, **kw: self.error(f"节点错误: {s.name if s else '?'} - {kw.get('result', '')}"))
        event_system.subscribe(EventType.WORKFLOW_STARTED,
                               lambda s, **kw: self.info(f"流程开始: {s.name if s else '?'}"))
        event_system.subscribe(EventType.WORKFLOW_COMPLETED,
                               lambda s, **kw: self.success(f"流程完成: {s.name if s else '?'}"))
        event_system.subscribe(EventType.WORKFLOW_ERROR,
                               lambda s, **kw: self.error(f"流程错误: {kw.get('result', '')}"))
        event_system.subscribe(EventType.MESSAGE_INFO,
                               lambda s, **kw: self.info(kw.get('message', '')))
        event_system.subscribe(EventType.MESSAGE_WARN,
                               lambda s, **kw: self.warning(kw.get('message', '')))
        event_system.subscribe(EventType.MESSAGE_ERROR,
                               lambda s, **kw: self.error(kw.get('message', '')))
        event_system.subscribe(EventType.MESSAGE_SUCCESS,
                               lambda s, **kw: self.success(kw.get('message', '')))

    def log(self, level: LogLevel, message: str):
        """Append a colored log message."""
        now = datetime.now().strftime("%H:%M:%S")
        color = level.value[1]

        # Check if this level is filtered out
        level_map = {
            LogLevel.INFO: self.filter_info,
            LogLevel.SUCCESS: self.filter_success,
            LogLevel.WARN: self.filter_warn,
            LogLevel.ERROR: self.filter_error,
            LogLevel.FATAL: self.filter_error,
        }
        btn = level_map.get(level)
        if btn and not btn.isChecked():
            return

        self.text_edit.moveCursor(QTextCursor.End)
        self.text_edit.setTextColor(color)
        self.text_edit.insertPlainText(f"[{now}] [{level.value[0]}] {message}\n")

        # Trim old lines
        block_count = self.text_edit.document().blockCount()
        if block_count > self.MAX_LINES:
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor,
                              block_count - self.MAX_LINES)
            cursor.removeSelectedText()

    def info(self, message: str):
        self.log(LogLevel.INFO, message)

    def success(self, message: str):
        self.log(LogLevel.SUCCESS, message)

    def warning(self, message: str):
        self.log(LogLevel.WARN, message)

    def error(self, message: str):
        self.log(LogLevel.ERROR, message)

    def fatal(self, message: str):
        self.log(LogLevel.FATAL, message)

    def clear(self):
        """Clear all log entries."""
        self.text_edit.clear()

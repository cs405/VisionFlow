"""Log panel - displays running log messages with filtering, source tracking, export.

Ported from H.Modules.Messages.Notice + H.Services.Message.

Features:
  - Colored log messages with timestamps
  - Source tracking (node/module origin)
  - Level-based filtering
  - Copy to clipboard / Export to file
  - Jump-to-node on log entry click
  - Auto-scroll with configurable max lines
"""

import os
from datetime import datetime
from enum import Enum

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QHBoxLayout,
                              QPushButton, QToolBar, QAction, QMenu,
                              QApplication, QFileDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings
from PyQt5.QtGui import QTextCursor, QColor, QFont

from core.events import EventType, event_system


class LogLevel(Enum):
    INFO = ("信息", QColor("#dcdcdc"))
    SUCCESS = ("成功", QColor("#4caf50"))
    WARN = ("警告", QColor("#ff9800"))
    ERROR = ("错误", QColor("#f44336"))
    FATAL = ("严重", QColor("#d32f2f"))


class LogPanel(QWidget):
    """Scrollable log panel with colored messages, source tracking, and export.

    Signals:
        node_jump_requested(str) - emitted when user requests jump to a node_id
    """

    MAX_LINES = 5000

    # Emitted when user wants to jump to a specific node
    node_jump_requested = pyqtSignal(str)  # node_id

    SETTINGS_KEY_FILTERS = "LogPanel/Filters"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._log_entries: list[dict] = []  # raw entries for export
        self._filters: dict[str, bool] = {}
        self._load_filters()
        self._setup_ui()
        self._connect_events()

    # ── Filter Persistence ────────────────────────────────────────────

    def _load_filters(self):
        s = QSettings()
        self._filters = {
            "info": True,
            "success": True,
            "warn": True,
            "error": True,
        }
        for k in self._filters:
            val = s.value(f"{self.SETTINGS_KEY_FILTERS}/{k}")
            if val is not None:
                self._filters[k] = str(val).lower() == "true" if isinstance(val, str) else bool(val)

    def _save_filters(self):
        s = QSettings()
        for k, v in self._filters.items():
            s.setValue(f"{self.SETTINGS_KEY_FILTERS}/{k}", v)

    # ── UI ────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 2)
        toolbar.setSpacing(4)

        self._clear_btn = QPushButton("清空")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(self._clear_btn)

        # Export button
        self._export_btn = QPushButton("导出")
        self._export_btn.setFixedHeight(24)
        self._export_btn.clicked.connect(self._export_log)
        toolbar.addWidget(self._export_btn)

        # Copy button
        self._copy_btn = QPushButton("复制")
        self._copy_btn.setFixedHeight(24)
        self._copy_btn.clicked.connect(self._copy_to_clipboard)
        toolbar.addWidget(self._copy_btn)

        toolbar.addStretch()

        # Filter buttons
        filter_style = """
            QPushButton {
                background: #3c3c3c; border: none; border-radius: 2px;
                padding: 2px 8px; font-size: 11px; color: #dcdcdc;
            }
            QPushButton:checked { background: #0078d4; color: white; }
        """

        self._filter_info = QPushButton("信息")
        self._filter_info.setFixedHeight(24)
        self._filter_info.setCheckable(True)
        self._filter_info.setChecked(self._filters.get("info", True))
        self._filter_info.toggled.connect(lambda v: self._set_filter("info", v))
        self._filter_info.setStyleSheet(filter_style)
        toolbar.addWidget(self._filter_info)

        self._filter_success = QPushButton("成功")
        self._filter_success.setFixedHeight(24)
        self._filter_success.setCheckable(True)
        self._filter_success.setChecked(self._filters.get("success", True))
        self._filter_success.toggled.connect(lambda v: self._set_filter("success", v))
        self._filter_success.setStyleSheet(filter_style)
        toolbar.addWidget(self._filter_success)

        self._filter_warn = QPushButton("警告")
        self._filter_warn.setFixedHeight(24)
        self._filter_warn.setCheckable(True)
        self._filter_warn.setChecked(self._filters.get("warn", True))
        self._filter_warn.toggled.connect(lambda v: self._set_filter("warn", v))
        self._filter_warn.setStyleSheet(filter_style)
        toolbar.addWidget(self._filter_warn)

        self._filter_error = QPushButton("错误")
        self._filter_error.setFixedHeight(24)
        self._filter_error.setCheckable(True)
        self._filter_error.setChecked(self._filters.get("error", True))
        self._filter_error.toggled.connect(lambda v: self._set_filter("error", v))
        self._filter_error.setStyleSheet(filter_style)
        toolbar.addWidget(self._filter_error)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar)
        toolbar_widget.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        layout.addWidget(toolbar_widget)

        # Log text display
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QFont("Consolas", 9))
        self._text_edit.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e; color: #dcdcdc; border: none; padding: 4px;
            }
        """)
        self._text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._text_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        self._text_edit.customContextMenuRequested.connect(self._on_log_context_menu)
        layout.addWidget(self._text_edit)

        # Button styling
        btn_style = """
            QPushButton {
                background: transparent; border: 1px solid #505050; border-radius: 2px;
                padding: 2px 10px; font-size: 11px; color: #dcdcdc;
            }
            QPushButton:hover { background: #3e3e42; }
        """
        self._clear_btn.setStyleSheet(btn_style)
        self._export_btn.setStyleSheet(btn_style)
        self._copy_btn.setStyleSheet(btn_style)

    # ── Event Connections ─────────────────────────────────────────────

    def _connect_events(self):
        event_system.subscribe(EventType.NODE_STARTED,
                               lambda s, **kw: self.info(
                                   f"节点开始: {self._node_label(s)}", source=self._node_source(s)))
        event_system.subscribe(EventType.NODE_COMPLETED,
                               lambda s, **kw: self.success(
                                   f"节点完成: {self._node_label(s)}", source=self._node_source(s)))
        event_system.subscribe(EventType.NODE_ERROR,
                               lambda s, **kw: self.error(
                                   f"节点错误: {self._node_label(s)} - {kw.get('result', '')}",
                                   source=self._node_source(s)))
        event_system.subscribe(EventType.WORKFLOW_STARTED,
                               lambda s, **kw: self.info("流程开始", source={"type": "workflow"}))
        event_system.subscribe(EventType.WORKFLOW_COMPLETED,
                               lambda s, **kw: self.success("流程完成", source={"type": "workflow"}))
        event_system.subscribe(EventType.WORKFLOW_ERROR,
                               lambda s, **kw: self.error(
                                   f"流程错误: {kw.get('result', '')}", source={"type": "workflow"}))
        event_system.subscribe(EventType.MESSAGE_INFO,
                               lambda s, **kw: self.info(
                                   kw.get("message", ""),
                                   source=kw.get("source", {"type": "system"}),
                                   node_id=kw.get("node_id", "")))
        event_system.subscribe(EventType.MESSAGE_WARN,
                               lambda s, **kw: self.warning(
                                   kw.get("message", ""),
                                   source=kw.get("source", {"type": "system"}),
                                   node_id=kw.get("node_id", "")))
        event_system.subscribe(EventType.MESSAGE_ERROR,
                               lambda s, **kw: self.error(
                                   kw.get("message", ""),
                                   source=kw.get("source", {"type": "system"}),
                                   node_id=kw.get("node_id", "")))
        event_system.subscribe(EventType.MESSAGE_SUCCESS,
                               lambda s, **kw: self.success(
                                   kw.get("message", ""),
                                   source=kw.get("source", {"type": "system"}),
                                   node_id=kw.get("node_id", "")))

    @staticmethod
    def _node_label(sender) -> str:
        return getattr(sender, "name", str(sender))

    @staticmethod
    def _node_source(sender) -> dict:
        return {"type": "node", "name": getattr(sender, "name", "?"),
                "node_id": getattr(sender, "node_id", "")}

    # ── Logging API ───────────────────────────────────────────────────

    def log(self, level: LogLevel, message: str, source: dict = None, node_id: str = ""):
        """Append a colored log message with source tracking."""
        now = datetime.now().strftime("%H:%M:%S")
        color = level.value[1]

        # Check filter
        level_key = {
            LogLevel.INFO: "info",
            LogLevel.SUCCESS: "success",
            LogLevel.WARN: "warn",
            LogLevel.ERROR: "error",
            LogLevel.FATAL: "error",
        }.get(level, "info")
        if not self._filters.get(level_key, True):
            return

        source = source or {"type": "system"}
        source_name = source.get("name", source.get("type", "system"))
        node_id = node_id or source.get("node_id", "")

        # Structured entry for export
        entry = {
            "time": now,
            "level": level.value[0],
            "message": message,
            "source": source_name,
            "node_id": node_id,
        }
        self._log_entries.append(entry)
        if len(self._log_entries) > self.MAX_LINES:
            self._log_entries = self._log_entries[-self.MAX_LINES:]

        # Build display line
        line = f"[{now}] [{level.value[0]}] [{source_name}] {message}\n"

        self._text_edit.moveCursor(QTextCursor.End)
        self._text_edit.setTextColor(color)
        self._text_edit.insertPlainText(line)

        # Trim lines from display
        block_count = self._text_edit.document().blockCount()
        if block_count > self.MAX_LINES:
            cursor = self._text_edit.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor,
                              block_count - self.MAX_LINES)
            cursor.removeSelectedText()

    def info(self, message: str, source: dict = None, node_id: str = ""):
        self.log(LogLevel.INFO, message, source, node_id)

    def success(self, message: str, source: dict = None, node_id: str = ""):
        self.log(LogLevel.SUCCESS, message, source, node_id)

    def warning(self, message: str, source: dict = None, node_id: str = ""):
        self.log(LogLevel.WARN, message, source, node_id)

    def error(self, message: str, source: dict = None, node_id: str = ""):
        self.log(LogLevel.ERROR, message, source, node_id)

    def fatal(self, message: str, source: dict = None, node_id: str = ""):
        self.log(LogLevel.FATAL, message, source, node_id)

    # ── Actions ───────────────────────────────────────────────────────

    def clear(self):
        """Clear all log entries."""
        self._text_edit.clear()
        self._log_entries.clear()

    def _set_filter(self, key: str, enabled: bool):
        self._filters[key] = enabled
        self._save_filters()

    def _copy_to_clipboard(self):
        """Copy selected or all log text to clipboard."""
        cursor = self._text_edit.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
        else:
            text = self._text_edit.toPlainText()
        QApplication.clipboard().setText(text)

    def _export_log(self):
        """Export log entries to a text file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "visionflow_log.txt",
            "文本文件 (*.txt);;日志文件 (*.log);;CSV文件 (*.csv)")
        if not path:
            return

        try:
            _, ext = os.path.splitext(path)
            if ext.lower() == ".csv":
                self._export_csv(path)
            else:
                self._export_text(path)
        except Exception as e:
            self.error(f"导出日志失败: {e}")

    def _export_text(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            for entry in self._log_entries:
                f.write(f"[{entry['time']}] [{entry['level']}] [{entry['source']}] {entry['message']}\n")

    def _export_csv(self, path: str):
        import csv
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["time", "level", "source", "node_id", "message"])
            writer.writeheader()
            writer.writerows(self._log_entries)

    def _on_log_context_menu(self, pos):
        """Right-click context menu on log entries."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #2d2d30; color: #dcdcdc; border: 1px solid #505050; }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background: #0078d4; }
        """)

        copy_act = QAction("复制选中", self)
        copy_act.triggered.connect(self._copy_to_clipboard)
        menu.addAction(copy_act)

        copy_all_act = QAction("复制全部", self)
        copy_all_act.triggered.connect(lambda: QApplication.clipboard().setText(
            self._text_edit.toPlainText()))
        menu.addAction(copy_all_act)

        menu.addSeparator()

        export_act = QAction("导出日志...", self)
        export_act.triggered.connect(self._export_log)
        menu.addAction(export_act)

        menu.addSeparator()

        clear_act = QAction("清空日志", self)
        clear_act.triggered.connect(self.clear)
        menu.addAction(clear_act)

        menu.exec_(self._text_edit.viewport().mapToGlobal(pos))

    # ── External API ──────────────────────────────────────────────────

    def get_entries(self) -> list[dict]:
        """Get all log entries (for external analysis)."""
        return list(self._log_entries)

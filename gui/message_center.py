"""Message center - notice / snack / dialog message patterns.

Ported from:
  - H.Modules.Messages.Notice
  - H.Modules.Messages.Snack
  - H.Modules.Messages.Dialog
  - H.Services.Message

Provides three message display modes:
  - Notice: transient popup in the corner (auto-dismiss)
  - Snack: inline bar at the bottom of a panel
  - Dialog: modal confirmation/error dialog

All messages go through this center, which routes them to the
appropriate display based on severity and context.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from PyQt5.QtWidgets import (QWidget, QLabel, QPushButton, QHBoxLayout,
                              QVBoxLayout, QMessageBox, QApplication)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve, pyqtSignal
from PyQt5.QtGui import QColor

from core.events import EventType, event_system


# ═══════════════════════════════════════════════════════════════════════════
# Message types
# ═══════════════════════════════════════════════════════════════════════════

class MessageType(Enum):
    INFO = ("信息", QColor("#2196f3"), QMessageBox.Information)
    SUCCESS = ("成功", QColor("#4caf50"), QMessageBox.Information)
    WARNING = ("警告", QColor("#ff9800"), QMessageBox.Warning)
    ERROR = ("错误", QColor("#f44336"), QMessageBox.Critical)
    FATAL = ("严重", QColor("#d32f2f"), QMessageBox.Critical)


# ═══════════════════════════════════════════════════════════════════════════
# Notice popup
# ═══════════════════════════════════════════════════════════════════════════

class NoticePopup(QWidget):
    """Transient notification popup that appears in the top-right corner.

    Auto-dismisses after a configurable duration. Supports click-to-dismiss.
    """

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setFixedWidth(320)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

        lo = QHBoxLayout(self)
        lo.setContentsMargins(12, 8, 12, 8)
        lo.setSpacing(8)

        self._icon = QLabel("●")
        self._icon.setFixedWidth(20)
        lo.addWidget(self._icon)

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setStyleSheet("color: white; font-size: 12px;")
        lo.addWidget(self._label, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: rgba(255,255,255,0.7); font-size: 12px; } QPushButton:hover { color: white; }")
        close_btn.clicked.connect(self._fade_out)
        lo.addWidget(close_btn)

    def show_message(self, msg_type: MessageType, text: str, duration_ms: int = 4000):
        """Display a notice message."""
        color = msg_type.value[1]
        self._icon.setStyleSheet(f"color: {color.name()}; font-size: 14px;")

        prefix = msg_type.value[0]
        self._label.setText(f"<b>{prefix}</b>  {text}")

        bg = "#333337"
        if msg_type == MessageType.ERROR:
            bg = "#5c1a1a"
        elif msg_type == MessageType.SUCCESS:
            bg = "#1a4c1a"
        elif msg_type == MessageType.WARNING:
            bg = "#5c3a1a"
        self.setStyleSheet(f"background: {bg}; border: 1px solid #505050; border-radius: 6px;")

        self.adjustSize()
        # Position at top-right of parent
        if self.parent():
            pgeo = self.parent().geometry()
            self.move(pgeo.right() - self.width() - 20, pgeo.top() + 50)

        self.show()
        self._timer.start(duration_ms)

    def _fade_out(self):
        self._timer.stop()
        self.hide()
        self.closed.emit()

    def mousePressEvent(self, ev):
        self._fade_out()


# ═══════════════════════════════════════════════════════════════════════════
# Snack bar (inline bottom bar)
# ═══════════════════════════════════════════════════════════════════════════

class SnackBar(QWidget):
    """Inline notification bar for a panel bottom."""

    action_triggered = pyqtSignal(str)  # action_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(0)
        self.setVisible(False)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide_bar)

        lo = QHBoxLayout(self)
        lo.setContentsMargins(12, 6, 12, 6)
        lo.setSpacing(8)

        self._label = QLabel()
        self._label.setStyleSheet("color: white; font-size: 12px;")
        lo.addWidget(self._label, 1)

        self._action_btn = QPushButton()
        self._action_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #ffd700; font-size: 12px; font-weight: bold; } QPushButton:hover { text-decoration: underline; }")
        self._action_btn.clicked.connect(lambda: self.action_triggered.emit("action"))
        self._action_btn.setVisible(False)
        lo.addWidget(self._action_btn)

    def show_message(self, msg_type: MessageType, text: str,
                     action_text: str = "", action_id: str = "",
                     duration_ms: int = 5000):
        color = msg_type.value[1]
        self.setStyleSheet(f"background: {color.darker(180).name()}; border-top: 2px solid {color.name()};")
        self._label.setText(f"<b>{msg_type.value[0]}</b>  {text}")

        if action_text:
            self._action_btn.setText(action_text)
            self._action_btn.setVisible(True)

        self.setFixedHeight(36)
        self.setVisible(True)
        self._timer.start(duration_ms)

    def hide_bar(self):
        self._timer.stop()
        self.setFixedHeight(0)
        self.setVisible(False)


# ═══════════════════════════════════════════════════════════════════════════
# Message Center (unified facade)
# ═══════════════════════════════════════════════════════════════════════════

class MessageCenter(QWidget):
    """Central message service combining notice/snack/dialog patterns.

    Usage:
        center = MessageCenter(main_window)
        center.info("操作完成")
        center.error("处理失败", dialog=True)
        center.snack("项目已保存", action_text="撤销", action_id="undo_save")
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notice = NoticePopup(parent)
        self._snack = SnackBar(self)
        self._snack.action_triggered.connect(self._on_snack_action)

        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.addStretch()
        lo.addWidget(self._snack)

        # Wire to event system
        self._wire_events()

    def _wire_events(self):
        event_system.subscribe(EventType.MESSAGE_INFO,
                               lambda s, **kw: self.info(kw.get("message", ""),
                                                         dialog=kw.get("dialog", False)))
        event_system.subscribe(EventType.MESSAGE_WARN,
                               lambda s, **kw: self.warning(kw.get("message", ""),
                                                            dialog=kw.get("dialog", False)))
        event_system.subscribe(EventType.MESSAGE_ERROR,
                               lambda s, **kw: self.error(kw.get("message", ""),
                                                          dialog=kw.get("dialog", True)))
        event_system.subscribe(EventType.MESSAGE_SUCCESS,
                               lambda s, **kw: self.success(kw.get("message", "")))

    # ── Notice API ────────────────────────────────────────────────────

    def notice(self, msg_type: MessageType, text: str, duration_ms: int = 4000):
        self._notice.show_message(msg_type, text, duration_ms)

    def info(self, text: str, dialog: bool = False):
        if dialog: self.dialog(MessageType.INFO, text)
        else: self.notice(MessageType.INFO, text)

    def success(self, text: str):
        self.notice(MessageType.SUCCESS, text, 3000)

    def warning(self, text: str, dialog: bool = False):
        if dialog: self.dialog(MessageType.WARNING, text)
        else: self.notice(MessageType.WARNING, text, 5000)

    def error(self, text: str, dialog: bool = True):
        if dialog: self.dialog(MessageType.ERROR, text)
        else: self.notice(MessageType.ERROR, text, 8000)

    def fatal(self, text: str):
        self.dialog(MessageType.FATAL, text)

    # ── Snack Bar API ─────────────────────────────────────────────────

    def snack(self, text: str, msg_type: MessageType = MessageType.INFO,
              action_text: str = "", action_id: str = ""):
        self._snack.show_message(msg_type, text, action_text, action_id)

    def _on_snack_action(self, action_id: str):
        """Override in subclass or connect to handle snack actions."""
        pass

    # ── Dialog API ────────────────────────────────────────────────────

    def dialog(self, msg_type: MessageType, text: str, title: str = ""):
        icon = msg_type.value[2]
        title = title or msg_type.value[0]
        QMessageBox(icon, title, text, QMessageBox.Ok, self.parent()).exec_()

    def confirm(self, text: str, title: str = "确认") -> bool:
        r = QMessageBox.question(self.parent(), title, text,
                                 QMessageBox.Yes | QMessageBox.No,
                                 QMessageBox.No)
        return r == QMessageBox.Yes

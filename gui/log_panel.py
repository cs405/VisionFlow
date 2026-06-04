"""
日志面板 - 显示系统日志
严格解耦：只通过EventBus与Core层通信
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QHBoxLayout,
    QPushButton, QComboBox, QLabel
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

    LEVEL_ICONS = {
        "DEBUG": "🔍",
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
    }

    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)

        self.event_bus = event_bus
        self.min_level = "INFO"
        self.log_entries = []  # 存储日志用于导出

        # 订阅事件
        self.event_bus.subscribe(EventType.LOG_MESSAGE, self._on_log_message)

        # 创建UI
        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #2D2D2D; border-bottom: 1px solid #3D3D3D;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)

        toolbar_layout.addWidget(QLabel("级别:"))

        self.level_combo = QComboBox()
        self.level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.level_combo.setCurrentText("INFO")
        self.level_combo.setFixedWidth(80)
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        toolbar_layout.addWidget(self.level_combo)

        toolbar_layout.addStretch()

        clear_btn = QPushButton("清空")
        clear_btn.setFixedSize(60, 26)
        clear_btn.clicked.connect(self.clear)
        toolbar_layout.addWidget(clear_btn)

        export_btn = QPushButton("导出")
        export_btn.setFixedSize(60, 26)
        export_btn.clicked.connect(self._on_export)
        toolbar_layout.addWidget(export_btn)

        layout.addWidget(toolbar)

        # 文本显示区域
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFontFamily("Consolas")
        self.text_edit.setFontPointSize(10)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: none;
            }
        """)
        layout.addWidget(self.text_edit)

        self.setLayout(layout)

        # 欢迎消息
        self._add_log("INFO", "VisionFlow 日志系统已启动", "System")

    def _on_level_changed(self, level: str):
        """级别改变"""
        self.min_level = level
        self._refresh_display()

    def _on_log_message(self, event: Event):
        """收到日志消息"""
        data = event.data
        level = data.get("level", "INFO")
        message = data.get("message", "")
        module = data.get("module", "")

        # 存储日志
        self.log_entries.append({
            "timestamp": QDateTime.currentDateTime(),
            "level": level,
            "message": message,
            "module": module
        })

        # 限制日志数量
        if len(self.log_entries) > 10000:
            self.log_entries = self.log_entries[-5000:]

        # 刷新显示
        self._refresh_display()

    def _refresh_display(self):
        """刷新显示"""
        self.text_edit.clear()

        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        min_level_index = levels.index(self.min_level)

        for entry in self.log_entries[-1000:]:  # 显示最近1000条
            level = entry["level"]
            if levels.index(level) < min_level_index:
                continue

            time_str = entry["timestamp"].toString("HH:mm:ss.zzz")
            color = self.LEVEL_COLORS.get(level, QColor(200, 200, 200))
            icon = self.LEVEL_ICONS.get(level, "📝")

            formatted = f'<span style="color: #808080;">[{time_str}]</span> '
            formatted += f'<span style="color: {color.name()};">{icon} [{level}]</span> '

            if entry["module"]:
                formatted += f'<span style="color: #6060ff;">[{entry["module"]}]</span> '

            formatted += f'<span style="color: #E0E0E0;">{entry["message"]}</span>'

            self.text_edit.append(formatted)

        # 滚动到底部
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.text_edit.setTextCursor(cursor)

    def _add_log(self, level: str, message: str, module: str = ""):
        """添加日志（内部使用）"""
        self.log_entries.append({
            "timestamp": QDateTime.currentDateTime(),
            "level": level,
            "message": message,
            "module": module
        })
        self._refresh_display()

    def _on_export(self):
        """导出日志"""
        from PySide6.QtWidgets import QFileDialog

        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "", "文本文件 (*.txt);;CSV文件 (*.csv)"
        )

        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    for entry in self.log_entries:
                        time_str = entry["timestamp"].toString("yyyy-MM-dd HH:mm:ss.zzz")
                        f.write(f"[{time_str}] [{entry['level']}] ")
                        if entry["module"]:
                            f.write(f"[{entry['module']}] ")
                        f.write(f"{entry['message']}\n")

                self._add_log("INFO", f"日志已导出: {filepath}", "LogPanel")
            except Exception as e:
                self._add_log("ERROR", f"导出失败: {str(e)}", "LogPanel")

    def clear(self):
        """清空日志"""
        self.log_entries.clear()
        self._refresh_display()
        self._add_log("INFO", "日志已清空", "LogPanel")

    def log(self, level: str, message: str, module: str = ""):
        """手动添加日志"""
        self.event_bus.emit_log(level, message, module)
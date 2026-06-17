"""图表标签页头部 — 可编辑名称 + 运行/停止/重置信号"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLineEdit
from PyQt5.QtCore import pyqtSignal

from gui.theme import theme_manager


class DiagramTabHeader(QWidget):
    """自定义标签页头部控件：可编辑的流程图名称，带重命名/运行/停止/重置信号"""

    rename_requested = pyqtSignal(str)
    run_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(0)

        self._name_edit = QLineEdit(name)
        self._name_edit.setFrame(False)
        self._name_edit.setFixedHeight(22)
        self._name_edit.setMinimumWidth(60)
        self._name_edit.editingFinished.connect(self._emit_rename)
        self._refresh_qss()
        layout.addWidget(self._name_edit, 1)

    def _refresh_qss(self):
        tm = theme_manager
        self._name_edit.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {tm.color('text_title').name()};"
            f" border: none; padding: 0 2px; font-family: 'Microsoft YaHei'; font-size: 12px; }}"
            f"QLineEdit:focus {{ border-bottom: 1px solid {tm.color('accent').name()}; }}"
        )

    def _emit_rename(self):
        name = self._name_edit.text().strip()
        self.rename_requested.emit(name)

    def set_name(self, name: str):
        if self._name_edit.text() != name:
            self._name_edit.setText(name)

    def set_active(self, active: bool):
        pass

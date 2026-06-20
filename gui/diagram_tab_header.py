"""图表标签页头部 — 可编辑名称 + 运行/停止/重置信号"""
from PyQt5.QtCore import pyqtSignal, QEvent, Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QTabBar

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
        self._name_edit.setReadOnly(True)
        self._name_edit.installEventFilter(self)
        self._name_edit.editingFinished.connect(self._emit_rename)
        self._refresh_qss()
        layout.addWidget(self._name_edit, 1)

    def _refresh_qss(self):
        tm = theme_manager
        self._name_edit.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {tm.color('text_title').name()};"
            f" border: none; padding: 0 2px; font-family: 'Microsoft YaHei'; font-size: 12px; }}"
        )

    def eventFilter(self, obj, event):
        if obj == self._name_edit:
            if event.type() == QEvent.MouseButtonDblClick:
                self._name_edit.setReadOnly(False)
                self._name_edit.selectAll()
                self._name_edit.setFocus()
                return True
            elif event.type() == QEvent.MouseButtonPress:
                self._switch_to_this_tab()
            elif event.type() == QEvent.KeyPress and event.key() == Qt.Key_Return:
                self._name_edit.clearFocus()  # 触发 editingFinished → _emit_rename
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        self._switch_to_this_tab()
        super().mousePressEvent(event)

    def _switch_to_this_tab(self):
        tab_bar = self.parent()
        if isinstance(tab_bar, QTabBar):
            for i in range(tab_bar.count()):
                if tab_bar.tabButton(i, QTabBar.LeftSide) == self:
                    tab_bar.setCurrentIndex(i)
                    break

    def _emit_rename(self):
        name = self._name_edit.text().strip()
        self._name_edit.setReadOnly(True)
        self.rename_requested.emit(name)

    def set_name(self, name: str):
        if self._name_edit.text() != name:
            self._name_edit.setText(name)



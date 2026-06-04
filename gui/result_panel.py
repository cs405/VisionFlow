"""Result panel - table display of node execution results.

Ported from H.VisionMaster.ResultPresenter (DataGridResultPresenter, ValueResultPresenter).
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
                              QTabWidget, QLabel, QHeaderView)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from core.node_base import VisionNodeData


class ResultPanel(QWidget):
    """Right panel showing execution results for the selected node.

    Contains two tabs:
      - 历史结果 (History Results)
      - 当前结果 (Current Module Results)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title = QLabel("  结果面板")
        title.setStyleSheet("""
            QLabel {
                background: #2d2d30;
                color: #dcdcdc;
                padding: 8px;
                font-size: 13px;
                font-weight: bold;
                border-bottom: 1px solid #3f3f46;
            }
        """)
        layout.addWidget(title)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #252526;
            }
            QTabBar::tab {
                padding: 6px 12px;
                font-size: 11px;
            }
        """)

        # History tab
        self.history_table = self._create_table()
        self.tabs.addTab(self.history_table, "历史结果")

        # Current result tab
        self.current_table = self._create_table()
        self.tabs.addTab(self.current_table, "当前结果")

        layout.addWidget(self.tabs)

        # Help tab
        self.help_label = QLabel("选择节点查看帮助信息")
        self.help_label.setAlignment(Qt.AlignCenter)
        self.help_label.setStyleSheet("color: #666; font-size: 12px; padding: 10px;")
        self.help_label.setWordWrap(True)
        self.tabs.addTab(self.help_label, "帮助")

    def _create_table(self) -> QTableWidget:
        """Create a styled result table."""
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["参数", "值"])
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                background: #252526;
                color: #dcdcdc;
                border: none;
                gridline-color: #3f3f46;
                alternate-background-color: #2a2a2c;
            }
            QHeaderView::section {
                background: #2d2d30;
                color: #999;
                padding: 4px 8px;
                border: none;
                border-bottom: 1px solid #3f3f46;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 2px 8px;
                font-size: 11px;
            }
        """)
        return table

    def show_node_results(self, node: VisionNodeData | None):
        """Display results for a vision node."""
        self.current_table.setRowCount(0)

        if node is None:
            return

        # Basic info
        info = [
            ("名称", node.name),
            ("类型", type(node).__name__),
            ("消息", node.message or "-"),
            ("节点ID", node.node_id),
        ]
        self._add_rows(self.current_table, info)

        # Result images
        for img in node.result_images:
            self._add_rows(self.current_table, [(f"输出图像: {img.name}",
                                                  f"{img.image.shape if img.image is not None else 'None'}")])

        # Add to history
        self._add_rows(self.history_table, info)
        # Separate history entries
        self.history_table.setRowCount(self.history_table.rowCount() + 1)  # blank row

    def show_help(self, node: VisionNodeData | None):
        """Show help information for a node."""
        if node is None:
            self.help_label.setText("选择节点查看帮助信息")
            return

        help_info = node.create_help_presenter()
        if isinstance(help_info, dict):
            text = f"模块: {node.name}\n类型: {type(node).__name__}\n\n帮助: {help_info.get('url', '暂无帮助')}"
        else:
            text = f"模块: {node.name}\n类型: {type(node).__name__}"

        self.help_label.setText(text)

    def _add_rows(self, table: QTableWidget, rows: list[tuple]):
        """Append rows to a table."""
        for key, value in rows:
            row = table.rowCount()
            table.insertRow(row)

            key_item = QTableWidgetItem(str(key))
            key_item.setForeground(QColor("#999"))
            table.setItem(row, 0, key_item)

            val_item = QTableWidgetItem(str(value))
            val_item.setForeground(QColor("#dcdcdc"))
            table.setItem(row, 1, val_item)

    def clear(self):
        """Clear all result displays."""
        self.current_table.setRowCount(0)
        self.history_table.setRowCount(0)

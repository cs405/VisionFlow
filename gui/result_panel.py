"""Result panel - table display of node execution results with image viewer linkage.

Ported from H.VisionMaster.ResultPresenter (DataGridResultPresenter, ValueResultPresenter).

Layout (three zones matching WPF):
  - 历史结果 (History Results): scrollable log of all past results
  - 当前结果 (Current Module Results): detailed view of selected node
  - 帮助 (Help): module help/documentation

Features:
  - Displays ResultItem hierarchy (value, rectangle, line, score-rect, image, table)
  - Click geometry items to highlight on the image viewer
  - Click value items in history to jump to source node
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
                              QTabWidget, QLabel, QHeaderView, QTextEdit,
                              QSplitter, QTreeWidget, QTreeWidgetItem)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from core.node_base import VisionNodeData
from gui.image_viewer import OverlayType
from core.result_presenter import (ResultItem, RectangleResultItem, LineResultItem,
                                    ScoreRectangleResultItem, NodeResult,
                                    ResultItemType)

# Geometry item colors
GEOM_COLORS = {
    ResultItemType.RECTANGLE: QColor("#0078d4"),
    ResultItemType.SCORE_RECTANGLE: QColor("#4caf50"),
    ResultItemType.LINE: QColor("#ff9800"),
}


class ResultPanel(QWidget):
    """Right panel showing execution results for the selected node.

    Three-zone layout:
      - History tab: chronological log of all node results
      - Current tab: detailed result items for the active selection
      - Help tab: module documentation

    Signals:
        item_selected(uid) - emitted when a geometry item is selected for image link
        node_jump_requested(node_id) - emitted to jump to a node from history
    """

    item_selected = pyqtSignal(str)  # overlay uid for image viewer
    node_jump_requested = pyqtSignal(str)  # node_id to select

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_viewer = None
        self._overlay_map: dict[int, str] = {}  # row_index -> overlay uid
        self._history_results: list[NodeResult] = []
        self._setup_ui()

    def set_image_viewer(self, viewer):
        """Set the image viewer for geometry overlay linkage."""
        self._image_viewer = viewer

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title = QLabel("  结果面板")
        title.setStyleSheet("""
            QLabel {
                background: #2d2d30; color: #dcdcdc; padding: 8px;
                font-size: 13px; font-weight: bold; border-bottom: 1px solid #3f3f46;
            }
        """)
        layout.addWidget(title)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #252526; }
            QTabBar::tab { padding: 6px 12px; font-size: 11px; }
        """)

        # ── History tab ──
        self._history_table = self._create_table(["#", "时间", "模块", "结果"])
        self._history_table.setColumnWidth(0, 30)
        self._history_table.setColumnWidth(1, 70)
        self._history_table.setColumnWidth(2, 100)
        self._history_table.cellClicked.connect(self._on_history_cell_clicked)
        self._tabs.addTab(self._history_table, "历史结果")

        # ── Current result tab ──
        self._current_table = self._create_table(["参数", "值", "类型"])
        self._current_table.setColumnWidth(0, 90)
        self._current_table.setColumnWidth(2, 80)
        self._current_table.cellClicked.connect(self._on_current_result_clicked)
        self._tabs.addTab(self._current_table, "当前结果")

        # ── Help tab ──
        self._help_edit = QTextEdit()
        self._help_edit.setReadOnly(True)
        self._help_edit.setStyleSheet("""
            QTextEdit {
                background: #252526; color: #dcdcdc; border: none;
                padding: 8px; font-size: 12px;
            }
        """)
        self._help_edit.setPlaceholderText("选择节点查看帮助信息")
        self._tabs.addTab(self._help_edit, "帮助")

        layout.addWidget(self._tabs)

    def _create_table(self, headers: list[str]) -> QTableWidget:
        """Create a styled result table."""
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setStyleSheet("""
            QTableWidget {
                background: #252526; color: #dcdcdc; border: none;
                gridline-color: #3f3f46; alternate-background-color: #2a2a2c;
            }
            QHeaderView::section {
                background: #2d2d30; color: #999; padding: 4px 8px;
                border: none; border-bottom: 1px solid #3f3f46; font-size: 11px;
            }
            QTableWidget::item {
                padding: 2px 8px; font-size: 11px;
            }
            QTableWidget::item:selected {
                background: #094771; color: #dcdcdc;
            }
        """)
        return table

    # ── Node Results Display ──────────────────────────────────────────

    def show_node_results(self, node: VisionNodeData | None):
        """Display results for a vision node in the current tab."""
        self._current_table.setRowCount(0)
        self._overlay_map.clear()

        if node is None:
            return

        # Collect result items
        items: list[ResultItem] = []

        # Basic info
        items.append(ResultItem("名称", node.name, ResultItemType.VALUE))
        items.append(ResultItem("类型", type(node).__name__, ResultItemType.VALUE))
        items.append(ResultItem("消息", node.message or "-", ResultItemType.VALUE))
        items.append(ResultItem("节点ID", node.node_id, ResultItemType.VALUE))

        # Geometry results from result_images
        for img in node.result_images:
            shape = img.image.shape if img.image is not None else ()
            items.append(ResultItem(f"输出图像: {img.name}",
                                    f"{shape}" if shape else "None",
                                    ResultItemType.IMAGE))

        # If node has detection results, display them
        if hasattr(node, 'detections') and node.detections:
            for i, det in enumerate(node.detections):
                if hasattr(det, 'rect'):
                    rect = det.rect
                    score = getattr(det, 'confidence', 0.0)
                    label = getattr(det, 'label', f"检测{i}")
                    items.append(ScoreRectangleResultItem(
                        name=label,
                        x=rect[0], y=rect[1], width=rect[2], height=rect[3],
                        score=score,
                    ))

        # Build rows
        for item in items:
            row = self._current_table.rowCount()
            self._current_table.insertRow(row)

            name_item = QTableWidgetItem(item.name)
            name_item.setForeground(QColor("#999"))
            self._current_table.setItem(row, 0, name_item)

            val_item = QTableWidgetItem(str(item.value) if item.value is not None else "-")
            val_item.setForeground(QColor("#dcdcdc"))
            self._current_table.setItem(row, 1, val_item)

            type_item = QTableWidgetItem(item.item_type.value)
            if item.item_type in GEOM_COLORS:
                type_item.setForeground(GEOM_COLORS[item.item_type])
            else:
                type_item.setForeground(QColor("#666"))
            self._current_table.setItem(row, 2, type_item)

            # Map geometry items to overlay for image viewer linkage
            if isinstance(item, (RectangleResultItem, ScoreRectangleResultItem, LineResultItem)):
                self._overlay_map[row] = item

        # Switch to current tab
        self._tabs.setCurrentIndex(1)

        # Add to history
        entry = NodeResult(
            node_id=node.node_id,
            node_name=node.name,
            node_type=type(node).__name__,
            message=node.message or "",
        )
        self._add_to_history(entry)

    def _add_to_history(self, entry: NodeResult):
        """Add a result entry to the history table."""
        import datetime
        entry.timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self._history_results.append(entry)
        if len(self._history_results) > 100:
            self._history_results = self._history_results[-100:]

        row = self._history_table.rowCount()
        self._history_table.insertRow(row)

        idx_item = QTableWidgetItem(str(len(self._history_results)))
        idx_item.setForeground(QColor("#666"))
        idx_item.setData(Qt.UserRole, entry.node_id)
        self._history_table.setItem(row, 0, idx_item)

        time_item = QTableWidgetItem(entry.timestamp)
        time_item.setForeground(QColor("#999"))
        time_item.setData(Qt.UserRole, entry.node_id)
        self._history_table.setItem(row, 1, time_item)

        name_item = QTableWidgetItem(entry.node_name)
        name_item.setForeground(QColor("#dcdcdc"))
        name_item.setData(Qt.UserRole, entry.node_id)
        self._history_table.setItem(row, 2, name_item)

        result_text = entry.message or ("成功" if entry.success else "失败")
        result_item = QTableWidgetItem(result_text)
        color = QColor("#4caf50") if entry.success else QColor("#f44336")
        result_item.setForeground(color)
        result_item.setData(Qt.UserRole, entry.node_id)
        self._history_table.setItem(row, 3, result_item)

        self._history_table.scrollToBottom()

    # ── Help Display ──────────────────────────────────────────────────

    def show_help(self, node: VisionNodeData | None):
        """Show help information for a node."""
        if node is None:
            self._help_edit.setHtml(
                '<p style="color: #666;">选择节点查看帮助信息</p>'
            )
            return

        help_info = node.create_help_presenter()
        if isinstance(help_info, dict):
            html = f"""
            <h3 style="color: #0078d4;">{node.name}</h3>
            <p style="color: #999;">类型: {type(node).__name__}</p>
            <hr style="border-color: #3f3f46;">
            <p style="color: #dcdcdc;">{help_info.get('description', '暂无描述')}</p>
            <p style="color: #999; font-size: 11px;">
                帮助: {help_info.get('url', '暂无帮助链接')}
            </p>
            """
        else:
            html = f"""
            <h3 style="color: #0078d4;">{node.name}</h3>
            <p style="color: #999;">类型: {type(node).__name__}</p>
            <hr style="border-color: #3f3f46;">
            <p style="color: #dcdcdc;">暂无详细帮助信息</p>
            """

        self._help_edit.setHtml(html)

    # ── Interaction ───────────────────────────────────────────────────

    def _on_current_result_clicked(self, row: int, col: int):
        """Handle click on current result table - link geometry items to viewer."""
        if row in self._overlay_map and self._image_viewer:
            item = self._overlay_map[row]
            if isinstance(item, (RectangleResultItem, ScoreRectangleResultItem)):
                rect = (int(item.x), int(item.y), int(item.width), int(item.height))
                ov_type = OverlayType.DETECTION if getattr(item, 'score', 0.0) > 0 else OverlayType.RECT
                uid = self._image_viewer.add_rect_overlay(
                    rect,
                    label=item.name,
                    color=GEOM_COLORS.get(item.item_type, QColor("#0078d4")),
                    score=getattr(item, 'score', 0.0),
                    overlay_type=ov_type,
                )
                self._image_viewer.zoom_to_rect(rect, padding=0.15, animate=True)
                self.item_selected.emit(uid)
            elif isinstance(item, LineResultItem):
                uid = self._image_viewer.add_line_overlay(
                    item.x1, item.y1, item.x2, item.y2,
                    label=item.name,
                    color=GEOM_COLORS.get(item.item_type, QColor("#ff9800")),
                )
                self.item_selected.emit(uid)

    def _on_history_cell_clicked(self, row: int, col: int):
        """Handle click on history table - jump to source node."""
        item = self._history_table.item(row, 0)
        if item:
            node_id = item.data(Qt.UserRole)
            if node_id:
                self.node_jump_requested.emit(node_id)

    # ── Clear ─────────────────────────────────────────────────────────

    def clear(self):
        """Clear all result displays."""
        self._current_table.setRowCount(0)
        self._history_table.setRowCount(0)
        self._overlay_map.clear()
        self._history_results.clear()

"""Result panel — WPF DataGrid + ResultPresenter 1:1 port.

Ported from WPF MainWindow.xaml bottom panel DataGrid + H.VisionMaster.ResultPresenter.

Layout:
  - 历史结果 Tab: DataGrid with columns [执行序号|执行时间|模块|结果数据]
    - 结果数据 column has FontIcon state icon + message text
    - State icons: Info (default), Error (red), Completed (green)
    - Click history row → update main image + switch to image tab
  - 当前模块结果 Tab: detailed result items table
    - Click geometry item → overlay on main image + zoom
  - 帮助 Tab: node documentation with clickable links
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
                              QTabWidget, QLabel, QHeaderView, QTextEdit,
                              QStyledItemDelegate, QStyle)
from PyQt5.QtCore import Qt, pyqtSignal, QRect
from gui.theme import theme_manager, connect_theme
from PyQt5.QtGui import QColor, QFont, QPainter, QPixmap

from core.node_base import VisionNodeData
from gui.image_viewer import OverlayType
from core.result_presenter import (ResultItem, RectangleResultItem, LineResultItem,
                                    ScoreRectangleResultItem, NodeResult,
                                    ResultItemType)
from gui.font_icons import FontIcons, ICON_FONT_FAMILY


# ── Color mapping for item types ───────────────────────────────────────────

GEOM_COLORS = {
    ResultItemType.RECTANGLE: QColor("#0078d4"),
    ResultItemType.SCORE_RECTANGLE: QColor("#4caf50"),
    ResultItemType.LINE: QColor("#ff9800"),
}

# State → FontIcon mapping (WPF DataGrid icon column)
STATE_ICONS = {
    "Success": FontIcons.Completed,
    "Error": FontIcons.Error,
    "Warning": FontIcons.Warning,
    "Info": FontIcons.Info,
    "Running": FontIcons.Sync,
}
STATE_COLORS = {
    "Success": "#4caf50",
    "Error": "#f44336",
    "Warning": "#ff9800",
    "Info": "#dcdcdc",
    "Running": "#2196f3",
}


# ── Custom delegate for icon+text cell in history table ───────────────────

class IconTextDelegate(QStyledItemDelegate):
    """Delegate that draws FontIcon + text in a single table cell.

    Matches WPF DataGridTemplateColumn with FontIconTextBlock + TextBlock.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icons: dict[int, str] = {}   # row → icon glyph
        self._colors: dict[int, str] = {}  # row → icon color

    def set_row_icon(self, row: int, icon: str, color: str = "#dcdcdc"):
        self._icons[row] = icon
        self._colors[row] = color

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # Background — from theme
        tm = theme_manager
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#094771"))
        else:
            bg = tm.color('bg_surface') if index.row() % 2 == 0 else tm.color('bg_alternating')
            painter.fillRect(option.rect, bg)

        row = index.row()
        icon = self._icons.get(row, "")
        color = self._colors.get(row, tm.color('text_primary').name())

        x = option.rect.left() + 6

        # Draw FontIcon (WPF: FontIconTextBlock with DataTrigger for state)
        if icon:
            font = QFont(ICON_FONT_FAMILY, 11)
            font.setStyleStrategy(QFont.PreferAntialias)
            painter.setFont(font)
            painter.setPen(QColor(color))
            icon_rect = QRect(x, option.rect.top(), 20, option.rect.height())
            painter.drawText(icon_rect, Qt.AlignVCenter | Qt.AlignLeft, icon)
            x += 22

        # Draw text
        text = index.data(Qt.DisplayRole) or ""
        font = QFont("Segoe UI", 10)
        painter.setFont(font)
        painter.setPen(theme_manager.color('text_primary'))
        text_rect = QRect(x, option.rect.top(),
                          option.rect.right() - x - 4, option.rect.height())
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft,
                         painter.fontMetrics().elidedText(text, Qt.ElideRight, text_rect.width()))

        painter.restore()


# ═══════════════════════════════════════════════════════════════════════════
# Main ResultPanel
# ═══════════════════════════════════════════════════════════════════════════

class ResultPanel(QWidget):
    """WPF-aligned result panel: history, current results, and help.

    Signals:
        item_selected(uid) — overlay uid for image viewer linkage
        node_jump_requested(node_id) — jump to node from history
        image_update_requested(image) — request main image panel to display this image
    """

    item_selected = pyqtSignal(str)
    node_jump_requested = pyqtSignal(str)
    image_update_requested = pyqtSignal(object)  # numpy array or QPixmap

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_viewer = None
        self._overlay_map: dict[int, str] = {}  # row → overlay uid
        self._history_results: list[NodeResult] = []
        self._current_node: VisionNodeData | None = None
        self._icon_delegate: IconTextDelegate | None = None
        self._setup_ui()

    def set_image_viewer(self, viewer):
        self._image_viewer = viewer

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
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
        self._history_table = QTableWidget(0, 4)
        self._history_table.setHorizontalHeaderLabels(["执行序号", "执行时间", "模块", "结果数据"])
        self._history_table.setColumnWidth(0, 60)
        self._history_table.setColumnWidth(1, 75)
        self._history_table.setColumnWidth(2, 100)
        self._history_table.horizontalHeader().setStretchLastSection(True)

        # Install custom delegate for column 3 (结果数据) which shows icon+text
        self._icon_delegate = IconTextDelegate(self._history_table)
        self._history_table.setItemDelegateForColumn(3, self._icon_delegate)

        self._history_table.verticalHeader().setVisible(False)
        self._history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._history_table.setSelectionMode(QTableWidget.SingleSelection)
        self._history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._history_table.setAlternatingRowColors(True)
        self._history_table.setStyleSheet("""
            QTableWidget {
                background: #252526; color: #dcdcdc; border: none;
                gridline-color: #3f3f46; alternate-background-color: #2a2a2c;
            }
            QHeaderView::section {
                background: #2d2d30; color: #999; padding: 4px 8px;
                border: none; border-bottom: 1px solid #3f3f46; font-size: 11px;
            }
            QTableWidget::item { padding: 3px 6px; font-size: 11px; }
            QTableWidget::item:selected { background: #094771; color: #dcdcdc; }
        """)
        self._history_table.cellClicked.connect(self._on_history_cell_clicked)
        self._tabs.addTab(self._history_table, "历史结果")

        # ── Current result tab ──
        self._current_table = QTableWidget(0, 3)
        self._current_table.setHorizontalHeaderLabels(["参数", "值", "类型"])
        self._current_table.setColumnWidth(0, 100)
        self._current_table.setColumnWidth(2, 70)
        self._current_table.horizontalHeader().setStretchLastSection(True)
        self._current_table.verticalHeader().setVisible(False)
        self._current_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._current_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._current_table.setAlternatingRowColors(True)
        self._current_table.setStyleSheet("""
            QTableWidget {
                background: #252526; color: #dcdcdc; border: none;
                gridline-color: #3f3f46; alternate-background-color: #2a2a2c;
            }
            QHeaderView::section {
                background: #2d2d30; color: #999; padding: 4px 8px;
                border: none; border-bottom: 1px solid #3f3f46; font-size: 11px;
            }
            QTableWidget::item { padding: 3px 6px; font-size: 11px; }
            QTableWidget::item:selected { background: #094771; }
        """)
        self._current_table.cellClicked.connect(self._on_current_result_clicked)
        self._tabs.addTab(self._current_table, "当前模块结果")

        # ── Help tab ──
        self._help_text = QTextEdit()
        self._help_text.setReadOnly(True)
        self._help_text.setStyleSheet("""
            QTextEdit {
                background: #252526; color: #dcdcdc; border: none;
                padding: 12px; font-size: 12px;
            }
        """)
        self._help_text.setPlaceholderText("选择节点后在此查看帮助信息")
        self._tabs.addTab(self._help_text, "帮助")

        layout.addWidget(self._tabs)
        self._title_label = title
        connect_theme(self._refresh_qss)

    def _refresh_qss(self):
        tm = theme_manager
        self._title_label.setStyleSheet(f"""
            QLabel {{ background: {tm.color('bg_surface_raised').name()}; color: {tm.color('text_primary').name()};
                      padding: 8px; font-size: 13px; font-weight: bold;
                      border-bottom: 1px solid {tm.color('border').name()}; }}
        """)
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {tm.color('bg_surface').name()}; }}
            QTabWidget:focus {{ outline: 0; }}
            QTabWidget::pane:focus {{ outline: 0; border: none; }}
            QTabBar:focus {{ outline: 0; }}
            QTabBar::tab {{ padding: 6px 12px; font-size: 11px; }}
            QTabBar::tab:focus {{ outline: 0; }}
        """)
        if hasattr(self, '_history_table'):
            self._history_table.setStyleSheet(f"""
                QTableWidget {{ background: {tm.color('bg_surface').name()}; color: {tm.color('text_primary').name()};
                               border: none; gridline-color: {tm.color('border').name()};
                               alternate-background-color: {tm.color('bg_alternating').name()}; }}
                QHeaderView::section {{ background: {tm.color('bg_surface_raised').name()};
                                       color: {tm.color('text_secondary').name()}; padding: 4px 8px;
                                       border: none; border-bottom: 1px solid {tm.color('border').name()}; font-size: 11px; }}
                QTableWidget::item {{ padding: 3px 6px; font-size: 11px; }}
                QTableWidget::item:selected {{ background: #094771; color: {tm.color('text_primary').name()}; }}
            """)
        if hasattr(self, '_help_text'):
            self._help_text.setStyleSheet(f"""
                QTextEdit, QPlainTextEdit {{ background: {tm.color('bg_surface').name()};
                    color: {tm.color('text_secondary').name()}; border: none; padding: 12px; font-size: 12px; }}
            """)

    # ── Current node results (6.4) ──────────────────────────────────────

    def show_node_results(self, node: VisionNodeData | None):
        """Display results for the selected node in the current tab."""
        self._current_table.setRowCount(0)
        self._overlay_map.clear()
        self._current_node = node

        if node is None:
            return

        items: list[ResultItem] = []
        items.append(ResultItem("名称", node.name, ResultItemType.VALUE))
        items.append(ResultItem("类型", type(node).__name__, ResultItemType.VALUE))
        items.append(ResultItem("消息", node.message or "-", ResultItemType.VALUE))
        items.append(ResultItem("节点ID", node.node_id, ResultItemType.VALUE))

        for img in node.result_images:
            shape = img.image.shape if img.image is not None else ()
            items.append(ResultItem(f"输出图像: {img.name}",
                                    f"{shape}" if shape else "None",
                                    ResultItemType.IMAGE))

        if hasattr(node, 'detections') and node.detections:
            for i, det in enumerate(node.detections):
                if hasattr(det, 'rect'):
                    rect = det.rect
                    score = getattr(det, 'confidence', 0.0)
                    label = getattr(det, 'label', f"检测{i}")
                    items.append(ScoreRectangleResultItem(
                        name=label, x=rect[0], y=rect[1],
                        width=rect[2], height=rect[3], score=score))

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
            type_color = GEOM_COLORS.get(item.item_type, QColor("#666"))
            type_item.setForeground(type_color)
            self._current_table.setItem(row, 2, type_item)

            if isinstance(item, (RectangleResultItem, ScoreRectangleResultItem, LineResultItem)):
                self._overlay_map[row] = item

    # ── History ─────────────────────────────────────────────────────────

    def add_to_history(self, node: VisionNodeData, state: str = "Success",
                       time_span: str = "", src_path: str = ""):
        """Add a node execution result to the history table (WPF Messages.Add).

        Args:
            node: the executed node
            state: "Success" / "Error" / "Running"
            time_span: formatted time string
            src_path: source file path at time of execution
        """
        import datetime
        entry = NodeResult(
            node_id=node.node_id,
            node_name=node.name,
            node_type=type(node).__name__,
            message=node.message or "",
        )
        entry.success = (state == "Success")
        entry.timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self._history_results.append(entry)
        if len(self._history_results) > 200:
            self._history_results = self._history_results[-200:]

        row = self._history_table.rowCount()
        self._history_table.insertRow(row)

        # 执行序号
        idx_item = QTableWidgetItem(str(len(self._history_results)))
        idx_item.setForeground(QColor("#666"))
        idx_item.setData(Qt.UserRole, node.node_id)
        idx_item.setTextAlignment(Qt.AlignCenter)
        self._history_table.setItem(row, 0, idx_item)

        # 执行时间
        time_item = QTableWidgetItem(time_span or entry.timestamp)
        time_item.setForeground(QColor("#999"))
        time_item.setData(Qt.UserRole, node.node_id)
        self._history_table.setItem(row, 1, time_item)

        # 模块
        name_item = QTableWidgetItem(node.name)
        name_item.setForeground(QColor("#dcdcdc"))
        name_item.setData(Qt.UserRole, node.node_id)
        self._history_table.setItem(row, 2, name_item)

        # 结果数据 — icon + text via delegate
        msg_text = node.message or ("完成" if entry.success else "失败")
        msg_item = QTableWidgetItem(msg_text)
        msg_item.setData(Qt.UserRole, node.node_id)
        icon = STATE_ICONS.get(state, FontIcons.Info)
        color = STATE_COLORS.get(state, theme_manager.color('text_primary').name())
        self._icon_delegate.set_row_icon(row, icon, color)
        self._history_table.setItem(row, 3, msg_item)

        # Also store result image for selection linkage
        self._history_results[-1]._result_image_source = getattr(
            node, '_result_image_source', None)
        self._history_results[-1]._src_path = src_path

        self._history_table.scrollToBottom()

    def update_history_state(self, node_id: str, state: str, message: str = ""):
        """Update the last history entry for a given node (for real-time updates)."""
        for row in range(self._history_table.rowCount() - 1, -1, -1):
            item = self._history_table.item(row, 0)
            if item and item.data(Qt.UserRole) == node_id:
                icon = STATE_ICONS.get(state, FontIcons.Info)
                color = STATE_COLORS.get(state, theme_manager.color('text_primary').name())
                self._icon_delegate.set_row_icon(row, icon, color)
                if message:
                    msg_item = self._history_table.item(row, 3)
                    if msg_item:
                        msg_item.setText(message)
                break

    def _on_history_cell_clicked(self, row: int, col: int):
        """Handle history row click — update main image + jump to node."""
        item = self._history_table.item(row, 0)
        if item is None:
            return
        node_id = item.data(Qt.UserRole)

        # Switch to image tab if there's a result image stored
        if 0 <= row < len(self._history_results):
            entry = self._history_results[row]
            result_image = getattr(entry, '_result_image_source', None)
            if result_image is not None:
                self.image_update_requested.emit(result_image)

        if node_id:
            self.node_jump_requested.emit(node_id)

    # ── Interaction (6.4 ZoomToRect) ───────────────────────────────────

    def _on_current_result_clicked(self, row: int, col: int):
        """Handle result click — overlay on image viewer + zoom to rect."""
        if row not in self._overlay_map or self._image_viewer is None:
            return
        geo_item = self._overlay_map[row]

        if isinstance(geo_item, (RectangleResultItem, ScoreRectangleResultItem)):
            rect = (int(geo_item.x), int(geo_item.y),
                    int(geo_item.width), int(geo_item.height))
            ov_type = OverlayType.DETECTION if getattr(geo_item, 'score', 0.0) > 0 else OverlayType.RECT
            uid = self._image_viewer.add_rect_overlay(
                rect, label=geo_item.name,
                color=GEOM_COLORS.get(geo_item.item_type, QColor("#0078d4")),
                score=getattr(geo_item, 'score', 0.0),
                overlay_type=ov_type)
            self._image_viewer.zoom_to_rect(rect, padding=0.15, animate=True)
            self.item_selected.emit(uid)
        elif isinstance(geo_item, LineResultItem):
            uid = self._image_viewer.add_line_overlay(
                geo_item.x1, geo_item.y1, geo_item.x2, geo_item.y2,
                label=geo_item.name,
                color=GEOM_COLORS.get(geo_item.item_type, QColor("#ff9800")))
            self.item_selected.emit(uid)

    # ── Help display (6.3) ──────────────────────────────────────────────

    def show_help(self, node: VisionNodeData | None):
        """Show WPF-aligned help for a node with clickable documentation link."""
        if node is None:
            self._help_text.setHtml(
                '<p style="color: #666; font-size: 13px;">'
                f'{FontIcons.Info}  选择一个节点以查看帮助信息</p>'
            )
            return

        help_info = {}
        if hasattr(node, 'create_help_presenter'):
            try:
                help_info = node.create_help_presenter() or {}
            except Exception:
                pass

        name = help_info.get("name", getattr(node, 'name', type(node).__name__))
        description = help_info.get("description", "")
        url = help_info.get("url", "")
        source = help_info.get("source", "")
        cls = type(node)
        bases = [b.__name__ for b in cls.__mro__[1:6] if b.__name__ != 'object']

        html = f"""<html><body style="color:#dcdcdc; font-family:'Segoe UI'; font-size:12px;">
<h2 style="color:#0078d4; margin-bottom:4px;">{FontIcons.Help}  {name}</h2>
<p style="color:#999; margin-top:0;"><b>类型:</b> {cls.__name__}</p>
<p style="color:#aaa;">{description}</p>
<hr style="border-color:#3f3f46;">
<h4>继承链</h4>
<p style="color:#999;">{' → '.join(bases)}</p>
<h4>参数列表</h4>
<table style="width:100%; border-collapse:collapse;">"""

        # Parameter table from Property descriptors
        for attr_name in sorted(dir(cls)):
            if attr_name.startswith('_'):
                continue
            try:
                attr = getattr(cls, attr_name)
                if hasattr(attr, 'display_name') and hasattr(attr, 'group'):
                    val = getattr(node, attr_name, "")
                    val_str = str(val) if val else "—"
                    if isinstance(val, str) and len(val_str) > 50:
                        val_str = val_str[:50] + "..."
                    html += (
                        f'<tr style="border-bottom:1px solid #3f3f46;">'
                        f'<td style="padding:3px 8px; color:#ccc;">{attr.display_name or attr_name}</td>'
                        f'<td style="padding:3px 8px; color:#999;">{val_str}</td>'
                        f'<td style="padding:3px 8px; color:#666; font-size:10px;">{attr.group or ""}</td>'
                        f'</tr>'
                    )
            except Exception:
                pass

        html += "</table>"

        if url:
            html += (
                f'<p style="margin-top:12px;">'
                f'{FontIcons.Link}  <a href="{url}" style="color:#0078d4;">在线文档</a>'
                f'</p>'
            )
        if source:
            html += f'<p style="color:#666; font-size:10px;">源文件: {source}</p>'

        html += "</body></html>"
        self._help_text.setHtml(html)

    # ── Clear ──────────────────────────────────────────────────────────

    def clear(self):
        """Clear all tables and state."""
        self._current_table.setRowCount(0)
        self._history_table.setRowCount(0)
        self._overlay_map.clear()
        self._history_results.clear()
        self._current_node = None

    def clear_history(self):
        """Clear only the history table (WPF: Messages.Clear on diagram switch).

        WPF: Messages is an ObservableCollection<IVisionMessage> on DiagramData.
        Each diagram has its own Messages — switching diagrams clears the table.
        """
        self._history_table.setRowCount(0)
        self._history_results.clear()

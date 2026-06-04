"""Toolbox panel - tree/grid display of available nodes.

Ported from H.Controls.FavoriteBox + H.Controls.TreeListView.
Shows nodes grouped by category. Supports drag to canvas.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                              QLineEdit, QHBoxLayout, QLabel, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData
from PyQt5.QtGui import QDrag, QFont, QColor

from core.node_group import node_data_group_manager, NodeGroup
from core.registry import node_registry


class ToolboxPanel(QWidget):
    """Left panel showing available node types in categorized groups.

    Supports dragging nodes onto the canvas to create them.
    """

    # Emitted when a node type is selected (for drag-drop or double-click creation)
    node_type_selected = pyqtSignal(str)  # node type name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_groups()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title = QLabel("  流程功能列表")
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

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索模块...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background: #333337;
                color: #dcdcdc;
                border: none;
                border-bottom: 1px solid #3f3f46;
                padding: 6px 8px;
                font-size: 12px;
            }
        """)
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(12)
        self.tree.setDragEnabled(True)
        self.tree.setDragDropMode(self.tree.DragOnly)
        self.tree.setFont(QFont("Segoe UI", 10))
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

    def _load_groups(self):
        """Load all node groups into the tree."""
        self.tree.clear()

        for group in node_data_group_manager.get_all_groups():
            if not group.node_types:
                continue

            group_item = QTreeWidgetItem(self.tree)
            group_item.setText(0, f"{group.name}  ({len(group.node_types)})")
            group_item.setData(0, Qt.UserRole, "")  # Empty = it's a group, not a node
            group_item.setFlags(group_item.flags() & ~Qt.ItemIsDragEnabled)

            # Style the group header
            font = QFont("Segoe UI", 10, QFont.Bold)
            group_item.setFont(0, font)
            group_item.setForeground(0, QColor("#0078d4"))

            for node_type in group.node_types:
                node_item = QTreeWidgetItem(group_item)
                # display_name is a property descriptor on the class; use __name__ as fallback
                dn = node_type.__name__
                node_item.setText(0, dn)
                node_item.setData(0, Qt.UserRole, node_type.__name__)
                node_item.setToolTip(0, (node_type.__doc__ or '') or group.description)

                # Color based on group category
                node_item.setForeground(0, QColor("#dcdcdc"))

            group_item.setExpanded(True)

    def _on_search(self, text: str):
        """Filter tree items by search text."""
        for i in range(self.tree.topLevelItemCount()):
            group_item = self.tree.topLevelItem(i)
            group_visible = False

            for j in range(group_item.childCount()):
                child = group_item.child(j)
                if not text or text.lower() in child.text(0).lower():
                    child.setHidden(False)
                    group_visible = True
                else:
                    child.setHidden(True)

            group_item.setHidden(not group_visible)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Emit signal when a node item is double-clicked."""
        type_name = item.data(0, Qt.UserRole)
        if type_name:
            self.node_type_selected.emit(type_name)

    def refresh(self):
        """Reload groups (e.g., after plugins are loaded)."""
        self._load_groups()

    def get_selected_node_type(self) -> str | None:
        """Get the currently selected node type name."""
        items = self.tree.selectedItems()
        if items:
            type_name = items[0].data(0, Qt.UserRole)
            if type_name:
                return type_name
        return None

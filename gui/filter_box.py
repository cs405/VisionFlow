"""Filter box - text search and column filtering for data tables.

Ported from WPF H.Controls.FilterBox / H.Controls.FilterColumnDataGrid.
Provides a compact filter bar with:
  - Full-text search across all columns
  - Column-specific filter fields
  - Filter clear button
  - Match count display
  - Debounced filtering
"""

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QLineEdit, QPushButton,
                              QLabel, QComboBox, QMenu, QAction)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon


class FilterBox(QWidget):
    """Compact filter bar for searching and filtering tabular data.

    Signals:
      filter_changed(dict): emitted with active filters {column_name: text_pattern}
      filter_cleared(): emitted when filters are reset
    """

    filter_changed = pyqtSignal(dict)
    filter_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns: list[str] = []
        self._active_filters: dict[str, str] = {}
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._emit_filter_changed)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Search icon / label
        icon_lbl = QLabel("🔍")
        icon_lbl.setStyleSheet("font-size: 13px; background: transparent;")
        layout.addWidget(icon_lbl)

        # Main search field (searches all columns)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索所有列...")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setStyleSheet("""
            QLineEdit {
                background: #3c3c3c; color: #dcdcdc; border: 1px solid #505050;
                border-radius: 3px; padding: 3px 6px; font-size: 12px;
            }
            QLineEdit:focus { border-color: #0078d4; }
        """)
        self._search_edit.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self._search_edit, 2)

        # Column filter button
        self._column_btn = QPushButton("列过滤 ▾")
        self._column_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: 1px solid #505050; border-radius: 3px;
                padding: 3px 8px; color: #dcdcdc; font-size: 11px;
            }
            QPushButton:hover { background: #3e3e42; }
        """)
        self._column_btn.clicked.connect(self._show_column_menu)
        layout.addWidget(self._column_btn)

        # Column-specific filter input (appears when column filter selected)
        self._col_filter = QLineEdit()
        self._col_filter.setPlaceholderText("按列过滤...")
        self._col_filter.setClearButtonEnabled(True)
        self._col_filter.setStyleSheet(self._search_edit.styleSheet())
        self._col_filter.setFixedWidth(150)
        self._col_filter.setVisible(False)
        self._col_filter.textChanged.connect(self._on_col_filter_changed)
        layout.addWidget(self._col_filter)

        # Active column filter label
        self._active_col_label = QLabel()
        self._active_col_label.setStyleSheet("color: #0078d4; font-size: 11px; background: #1e3a5c; padding: 2px 6px; border-radius: 2px;")
        self._active_col_label.setVisible(False)
        layout.addWidget(self._active_col_label)

        # Clear all filters
        clear_btn = QPushButton("✕")
        clear_btn.setFixedSize(22, 22)
        clear_btn.setToolTip("清除所有过滤条件")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none; color: #999; font-size: 12px;
            }
            QPushButton:hover { color: #f44336; }
        """)
        clear_btn.clicked.connect(self.clear_filters)
        layout.addWidget(clear_btn)

        # Match count
        self._count_label = QLabel()
        self._count_label.setStyleSheet("color: #999; font-size: 11px; background: transparent;")
        layout.addWidget(self._count_label)

    # -- Public API --

    def set_columns(self, columns: list[str]):
        """Set the available columns for filtering."""
        self._columns = columns

    def set_match_count(self, total: int, filtered: int):
        """Update the match count display."""
        if self.has_active_filters():
            self._count_label.setText(f"{filtered}/{total}")
        else:
            self._count_label.setText(f"{total} 项")

    def has_active_filters(self) -> bool:
        """Check if any filter is active."""
        return bool(self._search_edit.text().strip()) or bool(self._active_filters)

    def get_filters(self) -> dict:
        """Get the current filter state.

        Returns:
            dict with optional keys:
              - '_search': full-text search string
              - 'column_name': column-specific filter values
        """
        filters = {}
        search_text = self._search_edit.text().strip()
        if search_text:
            filters["_search"] = search_text
        filters.update(self._active_filters)
        return filters

    def clear_filters(self):
        """Reset all filters."""
        self._search_edit.clear()
        self._active_filters.clear()
        self._active_col_label.setVisible(False)
        self._col_filter.setVisible(False)
        self._col_filter.clear()
        self._count_label.clear()
        self.filter_cleared.emit()

    # -- Slots --

    def _on_search_text_changed(self, text: str):
        self._debounce_timer.start()

    def _on_col_filter_changed(self, text: str):
        col_name = self._active_col_label.text()
        if col_name:
            if text.strip():
                self._active_filters[col_name] = text.strip()
            else:
                self._active_filters.pop(col_name, None)
                if not self._active_filters:
                    self._active_col_label.setVisible(False)
                    self._col_filter.setVisible(False)
        self._debounce_timer.start()

    def _emit_filter_changed(self):
        self.filter_changed.emit(self.get_filters())

    def _show_column_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #2d2d30; color: #dcdcdc; border: 1px solid #505050; }
            QMenu::item { padding: 4px 20px; }
            QMenu::item:selected { background: #0078d4; }
        """)

        all_action = QAction("(全部列 — 全文搜索)", self)
        all_action.triggered.connect(lambda: self._select_column_filter(""))
        menu.addAction(all_action)
        menu.addSeparator()

        for col in self._columns:
            action = QAction(col, self)
            action.triggered.connect(lambda checked, c=col: self._select_column_filter(c))
            if col in self._active_filters:
                action.setIcon(QIcon())  # could add checkmark icon
            menu.addAction(action)

        menu.exec_(self._column_btn.mapToGlobal(self._column_btn.rect().bottomLeft()))

    def _select_column_filter(self, column: str):
        if column:
            self._active_col_label.setText(column)
            self._active_col_label.setVisible(True)
            self._col_filter.setVisible(True)
            self._col_filter.setPlaceholderText(f"过滤 {column}...")
            if column in self._active_filters:
                self._col_filter.setText(self._active_filters[column])
            else:
                self._col_filter.clear()
            self._col_filter.setFocus()
        else:
            self._active_col_label.setVisible(False)
            self._col_filter.setVisible(False)

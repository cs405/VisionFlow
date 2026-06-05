"""Help panel - structured node documentation display.

Ported from WPF IHelpPresenter / HelpNodeDataBase.
Displays node metadata, parameter documentation, and help URL in
a rich text widget with sections for:
  - Node name & description
  - Parameter table (name, type, default, description)
  - Input/output ports
  - Help URL / external documentation link
  - Source file reference
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QTextBrowser, QPushButton, QTableWidget,
                              QTableWidgetItem, QHeaderView, QSplitter)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QFont

from gui.theme import theme_manager, connect_theme


class HelpPanel(QWidget):
    """Standalone help panel widget showing node documentation.

    Can be embedded in a tab or shown as a separate dialog.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_node = None
        self._setup_ui()
        connect_theme(self._refresh_qss)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        header = QHBoxLayout()

        self._title_label = QLabel("节点帮助")
        header.addWidget(self._title_label)

        header.addStretch()

        self._source_label = QLabel("")
        self._source_label.setWordWrap(True)
        header.addWidget(self._source_label)

        layout.addLayout(header)

        # Description
        self._desc_label = QLabel("选择一个节点以查看帮助信息")
        self._desc_label.setWordWrap(True)
        layout.addWidget(self._desc_label)

        # Splitter: parameter table | detail text
        self._splitter = QSplitter(Qt.Vertical)

        # Parameter table
        self._param_table = QTableWidget(0, 4)
        self._param_table.setHorizontalHeaderLabels(["参数名", "类型/默认值", "分组", "说明"])
        self._param_table.horizontalHeader().setStretchLastSection(True)
        self._param_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._param_table.verticalHeader().setVisible(False)
        self._param_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._param_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._splitter.addWidget(self._param_table)

        # Detail text browser
        self._detail_browser = QTextBrowser()
        self._detail_browser.setOpenExternalLinks(True)
        self._splitter.addWidget(self._detail_browser)

        layout.addWidget(self._splitter, 1)

        # Bottom bar
        bottom = QHBoxLayout()

        self._url_btn = QPushButton("\U0001F4D6 在线文档")
        self._url_btn.clicked.connect(self._open_help_url)
        self._url_btn.setVisible(False)
        bottom.addWidget(self._url_btn)

        bottom.addStretch()

        self._status_label = QLabel("")
        bottom.addWidget(self._status_label)

        layout.addLayout(bottom)

        # Apply initial QSS
        self._refresh_qss()

    # ── Theme refresh ──────────────────────────────────────────────────

    def _refresh_qss(self):
        """Re-apply all QSS using theme colors."""
        text_primary = theme_manager.color('text_primary').name()
        text_secondary = theme_manager.color('text_secondary').name()
        bg_surface = theme_manager.color('bg_surface').name()
        bg_raised = theme_manager.color('bg_surface_raised').name()
        border = theme_manager.color('border').name()
        scroll_handle = theme_manager.color('scroll_handle').name()
        accent = theme_manager.color('accent').name()
        hover_bg = theme_manager.color('bg_surface_hover').name()

        # Title label
        self._title_label.setStyleSheet(
            f"color: {text_primary}; font-size: 16px; font-weight: bold; background: transparent;"
        )

        # Source label
        self._source_label.setStyleSheet(
            f"color: {text_secondary}; font-size: 10px; background: transparent;"
        )

        # Description label
        self._desc_label.setStyleSheet(
            f"color: {text_secondary}; font-size: 13px; padding: 4px 0; background: transparent;"
        )

        # Splitter handle
        self._splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {scroll_handle}; }}"
        )

        # Parameter table
        self._param_table.setStyleSheet(f"""
            QTableWidget {{
                background: {bg_surface}; color: {text_primary}; border: 1px solid {border};
                gridline-color: {border}; font-size: 12px;
            }}
            QTableWidget::item {{ padding: 3px 6px; }}
            QHeaderView::section {{
                background: {bg_raised}; color: {text_primary}; border: none;
                border-bottom: 1px solid {border}; padding: 4px;
            }}
        """)

        # Detail browser
        self._detail_browser.setStyleSheet(f"""
            QTextBrowser {{
                background: {bg_surface}; color: {text_primary}; border: 1px solid {border};
                font-size: 12px; padding: 8px;
            }}
        """)

        # URL button
        self._url_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {scroll_handle}; border-radius: 3px;
                padding: 4px 12px; color: {accent}; font-size: 11px;
            }}
            QPushButton:hover {{ background: {hover_bg}; }}
        """)

        # Status label
        self._status_label.setStyleSheet(
            f"color: {text_secondary}; font-size: 11px; background: transparent;"
        )

    # -- Public API --

    def set_node(self, node):
        """Display help information for a node."""
        self._current_node = node
        if node is None:
            self._clear()
            return

        # Gather help info from node's create_help_presenter
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

        self._title_label.setText(f"\U0001F4CB {name}")
        self._desc_label.setText(description or f"{type(node).__name__} — 视觉处理节点")
        self._source_label.setText(source)

        # Parameter table
        self._populate_param_table(node, help_info)

        # Detail text
        self._populate_detail(node, help_info)

        # URL
        if url:
            self._help_url = url
            self._url_btn.setVisible(True)
        else:
            self._help_url = ""
            self._url_btn.setVisible(False)

        self._status_label.setText(f"类型: {type(node).__name__}")

    def _populate_param_table(self, node, help_info: dict):
        """Fill the parameter table from node's Property descriptors."""
        self._param_table.setRowCount(0)
        rows = []

        # Collect Property descriptors from the node class
        for attr_name in dir(type(node)):
            if attr_name.startswith('_'):
                continue
            try:
                attr = getattr(type(node), attr_name)
                if hasattr(attr, 'display_name') and hasattr(attr, 'group'):
                    val = getattr(node, attr_name, "")
                    val_str = self._format_value(val, attr)
                    rows.append((
                        attr.display_name or attr_name,
                        val_str,
                        attr.group or "",
                        attr.description or "",
                    ))
            except Exception:
                pass

        # Sort by group then name
        rows.sort(key=lambda r: (r[2], r[0]))

        self._param_table.setRowCount(len(rows))
        for i, (pname, pval, pgroup, pdesc) in enumerate(rows):
            self._param_table.setItem(i, 0, QTableWidgetItem(pname))
            self._param_table.setItem(i, 1, QTableWidgetItem(pval))
            self._param_table.setItem(i, 2, QTableWidgetItem(pgroup))
            self._param_table.setItem(i, 3, QTableWidgetItem(pdesc))

    def _format_value(self, val, attr) -> str:
        if val is None:
            return "—"
        if isinstance(val, bool):
            return "True" if val else "False"
        if isinstance(val, (int, float)):
            default = getattr(attr, 'default', None)
            return f"{val} (默认: {default})" if default is not None else str(val)
        if isinstance(val, str) and len(val) > 40:
            return val[:40] + "..."
        return str(val) if val else "—"

    def _populate_detail(self, node, help_info: dict):
        """Populate the detail text browser."""
        text_primary = theme_manager.color('text_primary').name()
        html_parts = [f"<html><body style='color:{text_primary}; font-size:12px;'>"]

        cls = type(node)
        html_parts.append(f"<h3>{cls.__name__}</h3>")

        # Base classes
        bases = [b.__name__ for b in cls.__mro__[1:6] if b.__name__ != 'object']
        if bases:
            html_parts.append(f"<p><b>继承链:</b> {' → '.join(bases)}</p>")

        # Help sections from create_help_presenter
        sections = help_info.get("sections", [])
        if sections:
            for section in sections:
                title = section.get("title", "")
                content = section.get("content", "")
                if title and content:
                    html_parts.append(f"<h4>{title}</h4>")
                    html_parts.append(f"<p>{content}</p>")

        # Ports information
        if hasattr(node, 'ports') and node.ports:
            html_parts.append("<h4>端口</h4><ul>")
            for port in node.ports:
                html_parts.append(f"<li>{port.name} ({port.port_type.value})</li>")
            html_parts.append("</ul>")

        # Group info
        group = getattr(cls, '__group__', '')
        if group:
            html_parts.append(f"<p><b>节点分组:</b> {group}</p>")

        html_parts.append("</body></html>")
        self._detail_browser.setHtml("".join(html_parts))

    def _clear(self):
        self._title_label.setText("节点帮助")
        self._desc_label.setText("选择一个节点以查看帮助信息")
        self._source_label.setText("")
        self._param_table.setRowCount(0)
        self._detail_browser.clear()
        self._url_btn.setVisible(False)
        self._status_label.setText("")

    def _open_help_url(self):
        if self._help_url:
            QDesktopServices.openUrl(QUrl(self._help_url))

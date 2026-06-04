"""
底部结果面板 — WPF风格，包含历史结果/当前模块结果/帮助三个Tab
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QTextBrowser,
    QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from core.events import EventBus, Event, EventType

from .theme import Colors, Fonts


class ResultPanel(QWidget):
    """底部结果面板"""

    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self._messages = []  # 历史执行记录

        self._setup_ui()
        self._subscribe_events()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                background-color: {Colors.BackgroundDark};
                border: none;
                border-top: 1px solid {Colors.Border};
            }}
            QTabBar::tab {{
                background-color: {Colors.BackgroundLight};
                color: {Colors.ForegroundDim};
                padding: 6px 20px;
                font: 11px "{Fonts.Family}";
                border: none;
                border-bottom: 2px solid transparent;
                min-width: 80px;
            }}
            QTabBar::tab:selected {{
                color: {Colors.Foreground};
                border-bottom-color: {Colors.Accent};
            }}
            QTabBar::tab:hover:!selected {{
                color: {Colors.Foreground};
                background-color: {Colors.Border};
            }}
        """)

        # Tab 1: 历史结果
        self.history_tab = self._create_history_tab()
        self.tab_widget.addTab(self.history_tab, "历史结果")

        # Tab 2: 当前模块结果
        self.module_tab = self._create_module_tab()
        self.tab_widget.addTab(self.module_tab, "当前模块结果")

        # Tab 3: 帮助
        self.help_tab = self._create_help_tab()
        self.tab_widget.addTab(self.help_tab, "帮助")

        layout.addWidget(self.tab_widget)
        self.setLayout(layout)

    def _create_history_tab(self):
        """创建历史结果Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["执行序号", "执行时间", "模块", "结果数据"])
        self.history_table.setShowGrid(True)
        self.history_table.setAlternatingRowColors(False)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)

        # 列宽
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.history_table.setColumnWidth(0, 100)
        self.history_table.setColumnWidth(1, 120)
        self.history_table.setColumnWidth(2, 100)

        self.history_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.BackgroundDark};
                color: {Colors.Foreground};
                border: none;
                gridline-color: {Colors.Border};
                font: 11px "{Fonts.Family}";
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {Colors.Accent};
            }}
            QHeaderView::section {{
                background-color: {Colors.BackgroundLight};
                color: {Colors.Foreground};
                border: none;
                border-right: 1px solid {Colors.Border};
                border-bottom: 1px solid {Colors.Border};
                padding: 6px 8px;
                font: bold 10px "{Fonts.Family}";
            }}
        """)

        layout.addWidget(self.history_table)
        return widget

    def _create_module_tab(self):
        """创建当前模块结果Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        group = QGroupBox("当前模块信息")
        form = QFormLayout(group)
        form.setSpacing(8)

        self.module_name_label = QLabel("—")
        self.module_type_label = QLabel("—")
        self.module_status_label = QLabel("未执行")

        form.addRow("模块名称:", self.module_name_label)
        form.addRow("模块类型:", self.module_type_label)
        form.addRow("状态:", self.module_status_label)

        layout.addWidget(group)
        layout.addStretch()

        return widget

    def _create_help_tab(self):
        """创建帮助Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        self.help_browser = QTextBrowser()
        self.help_browser.setOpenExternalLinks(True)
        self.help_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {Colors.BackgroundDark};
                color: {Colors.Foreground};
                border: none;
                font: 11px "{Fonts.Family}";
            }}
        """)
        self.help_browser.setHtml("""
        <h3 style="color: #4A6A9A;">VisionFlow 帮助</h3>
        <p>选择一个节点查看其帮助信息。</p>
        <hr>
        <p><b>快捷键:</b></p>
        <ul>
            <li><b>F5</b> — 执行工作流</li>
            <li><b>F10</b> — 单步执行</li>
            <li><b>Ctrl+Z</b> — 撤销</li>
            <li><b>Ctrl+Y</b> — 重做</li>
            <li><b>Ctrl+S</b> — 保存项目</li>
            <li><b>Ctrl+滚轮</b> — 缩放</li>
            <li><b>Delete</b> — 删除选中项</li>
        </ul>
        """)

        layout.addWidget(self.help_browser)
        return widget

    def _subscribe_events(self):
        """订阅事件"""
        self.event_bus.subscribe(EventType.NODE_SELECTED, self._on_node_selected)
        self.event_bus.subscribe(EventType.NODE_EXECUTED, self._on_node_executed)
        self.event_bus.subscribe(EventType.WORKFLOW_EXECUTED, self._on_workflow_executed)

    def _on_node_selected(self, event: Event):
        """节点选中"""
        meta = event.data.get("node_metadata", {})
        self.module_name_label.setText(meta.get("name", "—"))
        self.module_type_label.setText(meta.get("category", "—"))
        self.module_status_label.setText("已选中")

        # 更新帮助
        desc = meta.get("description", "")
        params = meta.get("parameters", [])
        param_html = ""
        for p in params:
            param_html += f"<li><b>{p.get('label', p.get('name'))}</b> ({p.get('type')}) — 默认: {p.get('default')}</li>"

        self.help_browser.setHtml(f"""
        <h3 style="color: #4A6A9A;">{meta.get('name', '未知节点')}</h3>
        <p>{desc}</p>
        <p><b>分类:</b> {meta.get('category', '通用')}</p>
        <hr>
        <p><b>参数列表:</b></p>
        <ul>{param_html or '<li>无参数</li>'}</ul>
        """)

    def _on_node_executed(self, event: Event):
        """节点执行完成"""
        node_id = event.data.get("node_id", "")[:8]
        self.add_history_entry(
            index=len(self._messages) + 1,
            time_span="—",
            node_type=f"节点-{node_id}",
            state="Success",
            message=f"节点 {node_id} 执行完成"
        )

    def _on_workflow_executed(self, event: Event):
        """工作流执行完成"""
        results = event.data.get("results", {})
        self.add_history_entry(
            index=len(self._messages) + 1,
            time_span="—",
            node_type="工作流",
            state="Success",
            message=f"工作流执行完成，共 {len(results)} 个节点"
        )

    def add_history_entry(self, index: int, time_span: str, node_type: str,
                          state: str, message: str):
        """添加历史执行记录"""
        self._messages.append({
            "index": index, "time_span": time_span,
            "node_type": node_type, "state": state, "message": message
        })

        row = self.history_table.rowCount()
        self.history_table.insertRow(row)

        # 序号
        idx_item = QTableWidgetItem(str(index))
        idx_item.setTextAlignment(Qt.AlignCenter)

        # 时间
        from PySide6.QtCore import QDateTime
        time_item = QTableWidgetItem(QDateTime.currentDateTime().toString("HH:mm:ss.zzz"))

        # 模块
        type_item = QTableWidgetItem(node_type)

        # 结果数据
        msg_item = QTableWidgetItem(message)

        # 状态着色
        if state == "Error":
            color = QColor(Colors.Red)
            idx_item.setForeground(color)
            time_item.setForeground(color)
            type_item.setForeground(color)
            msg_item.setForeground(color)
        elif state == "Success":
            color = QColor(Colors.Green)
            idx_item.setForeground(color)
            type_item.setForeground(color)

        self.history_table.setItem(row, 0, idx_item)
        self.history_table.setItem(row, 1, time_item)
        self.history_table.setItem(row, 2, type_item)
        self.history_table.setItem(row, 3, msg_item)

        # 滚动到底部
        self.history_table.scrollToBottom()

        # 限制行数
        while self.history_table.rowCount() > 1000:
            self.history_table.removeRow(0)

    def update_module_result(self, name: str, category: str, status: str):
        """更新模块结果显示"""
        self.module_name_label.setText(name)
        self.module_type_label.setText(category)
        self.module_status_label.setText(status)

        if status == "执行成功":
            self.module_status_label.setStyleSheet(f"color: {Colors.Green};")
        elif "失败" in status or status == "错误":
            self.module_status_label.setStyleSheet(f"color: {Colors.Red};")
        else:
            self.module_status_label.setStyleSheet(f"color: {Colors.Foreground};")

    def clear_history(self):
        """清空历史"""
        self.history_table.setRowCount(0)
        self._messages.clear()

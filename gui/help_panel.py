"""帮助面板 - 结构化节点文档显示。

在富文本控件中显示节点元数据、参数文档和帮助URL，包含以下部分：
  - 节点名称与描述
  - 参数表格（名称、类型/默认值、分组、说明）
  - 输入/输出端口
  - 帮助URL / 外部文档链接
  - 源文件引用
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QTextBrowser, QPushButton, QTableWidget,
                              QTableWidgetItem, QHeaderView, QSplitter)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices

from gui.theme import theme_manager, connect_theme


class HelpPanel(QWidget):
    """独立的帮助面板控件，显示节点文档。

    可以嵌入到标签页中或作为独立对话框显示。
    """
    def __init__(self, parent=None):
        """初始化帮助面板

        参数：
            parent: 父对象
        """
        super().__init__(parent)
        self._current_node = None
        self._help_url = ""
        self._setup_ui()
        connect_theme(self._refresh_qss)

    def _setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 头部水平布局
        header = QHBoxLayout()

        self._title_label = QLabel("节点帮助")
        header.addWidget(self._title_label)

        header.addStretch()

        self._source_label = QLabel("")
        self._source_label.setWordWrap(True)
        header.addWidget(self._source_label)

        layout.addLayout(header)

        self._desc_label = QLabel("选择一个节点以查看帮助信息")
        self._desc_label.setWordWrap(True)

        layout.addWidget(self._desc_label)

        # 分割器：参数表格 | 详细文本
        self._splitter = QSplitter(Qt.Vertical)

        # 参数表格
        self._param_table = QTableWidget(0, 4)
        # 设置表头标签
        self._param_table.setHorizontalHeaderLabels(["参数名", "类型/默认值", "分组", "说明"])
        self._param_table.horizontalHeader().setStretchLastSection(True)
        # 设置列宽为适应内容
        self._param_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        # 隐藏垂直表头
        self._param_table.verticalHeader().setVisible(False)
        # 选择行为为选择行
        self._param_table.setSelectionBehavior(QTableWidget.SelectRows)
        # 禁止编辑
        self._param_table.setEditTriggers(QTableWidget.NoEditTriggers)
        # 添加到分割器
        self._splitter.addWidget(self._param_table)

        # 详细文本浏览器
        self._detail_browser = QTextBrowser()
        # 允许打开外部链接
        self._detail_browser.setOpenExternalLinks(True)
        self._splitter.addWidget(self._detail_browser)

        layout.addWidget(self._splitter, 1)

        # 底部栏
        bottom = QHBoxLayout()

        # 在线文档按钮
        self._url_btn = QPushButton("\U0001F4D6 在线文档")
        self._url_btn.clicked.connect(self._open_help_url)
        self._url_btn.setVisible(False)

        bottom.addWidget(self._url_btn)

        bottom.addStretch()

        # 状态标签
        self._status_label = QLabel("")
        bottom.addWidget(self._status_label)

        layout.addLayout(bottom)

        self._refresh_qss()

    # ── 主题刷新 ──────────────────────────────────────────────────

    def _refresh_qss(self):
        """使用主题颜色重新应用所有QSS样式"""
        # 从主题管理器获取各种颜色
        text_primary = theme_manager.color('text_primary').name()      # 主文本色
        text_secondary = theme_manager.color('text_secondary').name()  # 次要文本色
        bg_surface = theme_manager.color('bg_surface').name()          # 表面背景色
        bg_raised = theme_manager.color('bg_surface_raised').name()    # 凸起背景色
        border = theme_manager.color('border').name()                  # 边框颜色
        scroll_handle = theme_manager.color('scroll_handle').name()    # 滚动条手柄色
        accent = theme_manager.color('accent').name()                  # 强调色
        hover_bg = theme_manager.color('bg_surface_hover').name()      # 悬停背景色

        # 标题标签样式
        self._title_label.setStyleSheet(
            f"color: {text_primary}; font-size: 16px; font-weight: bold; background: transparent;"
        )

        # 源文件标签样式
        self._source_label.setStyleSheet(
            f"color: {text_secondary}; font-size: 10px; background: transparent;"
        )

        # 描述标签样式
        self._desc_label.setStyleSheet(
            f"color: {text_secondary}; font-size: 13px; padding: 4px 0; background: transparent;"
        )

        # 分割器手柄样式
        self._splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {scroll_handle}; }}"
        )

        # 参数表格样式
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

        # 详细文本浏览器样式
        self._detail_browser.setStyleSheet(f"""
            QTextBrowser {{
                background: {bg_surface}; color: {text_primary}; border: 1px solid {border};
                font-size: 12px; padding: 8px;
            }}
        """)

        # 在线文档按钮样式
        self._url_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {scroll_handle}; border-radius: 3px;
                padding: 4px 12px; color: {accent}; font-size: 11px;
            }}
            QPushButton:hover {{ background: {hover_bg}; }}
        """)

        # 状态标签样式
        self._status_label.setStyleSheet(
            f"color: {text_secondary}; font-size: 11px; background: transparent;"
        )

    # -- 公共API --

    def set_node(self, node):
        """
        显示节点的帮助信息
        参数：
            node: 节点数据对象
        """
        self._current_node = node

        if node is None:
            self._clear()
            return

        # 从节点的 create_help_presenter 方法获取帮助信息
        help_info = {}
        # 如果节点有 create_help_presenter 方法
        if hasattr(node, 'create_help_presenter'):
            try:
                # 调用方法获取帮助信息
                help_info = node.create_help_presenter() or {}
            except Exception:
                pass

        # 获取节点名称
        name = help_info.get("name", getattr(node, 'name', type(node).__name__))
        # 获取描述信息
        description = help_info.get("description", "")
        # 获取帮助URL
        url = help_info.get("url", "")
        # 获取源文件路径
        source = help_info.get("source", "")

        # 设置标题
        self._title_label.setText(f"\U0001F4CB {name}")
        # 设置描述
        self._desc_label.setText(description or f"{type(node).__name__} — 视觉处理节点")
        # 设置源文件标签
        self._source_label.setText(source)

        # 填充参数表格
        self._populate_param_table(node, help_info)

        # 填充详细文本
        self._populate_detail(node, help_info)

        # 处理URL
        if url:
            self._help_url = url
            self._url_btn.setVisible(True)
        else:
            self._help_url = ""
            self._url_btn.setVisible(False)

        # 设置状态标签
        self._status_label.setText(f"类型: {type(node).__name__}")

    def _populate_param_table(self, node, help_info: dict):
        """
        从节点的Property描述符填充参数表格
        参数：
            node: 节点对象
            help_info: 帮助信息字典（未使用）
        """
        # 清空表格
        self._param_table.setRowCount(0)
        # 行数据列表
        rows = []

        # 从节点类收集Property描述符
        for attr_name, attr in node.get_property_descriptors():
            try:
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

        # 按分组排序，然后按参数名排序
        rows.sort(key=lambda r: (r[2], r[0]))

        # 设置表格行数
        self._param_table.setRowCount(len(rows))
        # 遍历行数据
        for i, (pname, pval, pgroup, pdesc) in enumerate(rows):
            # 设置参数名
            self._param_table.setItem(i, 0, QTableWidgetItem(pname))
            # 设置值
            self._param_table.setItem(i, 1, QTableWidgetItem(pval))
            # 设置分组
            self._param_table.setItem(i, 2, QTableWidgetItem(pgroup))
            # 设置说明
            self._param_table.setItem(i, 3, QTableWidgetItem(pdesc))

    def _format_value(self, val, attr) -> str:
        """
        格式化属性值显示
        参数：
            val: 属性值
            attr: 属性描述符

        返回：
            格式化后的字符串
        """
        # 如果值为None
        if val is None:
            return "—"
        # 如果是布尔值
        if isinstance(val, bool):
            return "True" if val else "False"
        # 如果是数字
        if isinstance(val, (int, float)):
            # 获取默认值
            default = getattr(attr, 'default', None)
            # 如果有默认值，显示值和默认值
            if default is not None:
                return f"{val} (默认: {default})"
            # 否则只显示值
            return str(val)
        # 如果是字符串且长度超过40
        if isinstance(val, str) and len(val) > 40:
            # 截断并添加省略号
            return val[:40] + "..."
        # 其他情况
        return str(val) if val else "—"

    def _populate_detail(self, node, help_info: dict):
        """
        填充详细文本浏览器
        参数：
            node: 节点对象
            help_info: 帮助信息字典
        """
        # 从主题获取主文本色
        text_primary = theme_manager.color('text_primary').name()
        # 构建HTML
        html_parts = [f"<html><body style='color:{text_primary}; font-size:12px;'>"]

        # 获取节点类
        cls = type(node)
        # 添加类名标题
        html_parts.append(f"<h3>{cls.__name__}</h3>")

        # 获取基类列表（不包含object）
        bases = [b.__name__ for b in cls.__mro__[1:6] if b.__name__ != 'object']
        # 如果有基类
        if bases:
            # 添加继承链
            html_parts.append(f"<p><b>继承链:</b> {' → '.join(bases)}</p>")

        # 从 create_help_presenter 获取的帮助章节
        sections = help_info.get("sections", [])
        # 如果有章节
        if sections:
            # 遍历章节
            for section in sections:
                # 获取标题
                title = section.get("title", "")
                # 获取内容
                content = section.get("content", "")
                # 如果标题和内容都有
                if title and content:
                    # 添加标题
                    html_parts.append(f"<h4>{title}</h4>")
                    # 添加内容
                    html_parts.append(f"<p>{content}</p>")

        # 端口信息
        if hasattr(node, 'ports') and node.ports:
            # 添加端口标题
            html_parts.append("<h4>端口</h4><ul>")
            # 遍历端口
            for port in node.ports:
                # 添加端口项
                html_parts.append(f"<li>{port.name} ({port.port_type.value})</li>")
            # 关闭列表
            html_parts.append("</ul>")

        # 分组信息
        group = getattr(cls, '__group__', '')
        if group:
            # 添加分组信息
            html_parts.append(f"<p><b>节点分组:</b> {group}</p>")

        # 关闭body和html
        html_parts.append("</body></html>")
        # 设置HTML内容
        self._detail_browser.setHtml("".join(html_parts))

    def _clear(self):
        """清空所有显示内容"""
        # 重置标题
        self._title_label.setText("节点帮助")
        # 重置描述
        self._desc_label.setText("选择一个节点以查看帮助信息")
        # 清空源文件标签
        self._source_label.setText("")
        # 清空表格
        self._param_table.setRowCount(0)
        # 清空详细浏览器
        self._detail_browser.clear()
        # 隐藏在线文档按钮
        self._url_btn.setVisible(False)
        # 清空状态标签
        self._status_label.setText("")

    def _open_help_url(self):
        """打开帮助URL"""
        # 如果帮助URL存在
        if self._help_url:
            # 使用系统默认浏览器打开URL
            QDesktopServices.openUrl(QUrl(self._help_url))
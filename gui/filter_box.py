"""过滤框 - 数据表的文本搜索和列过滤。

提供一个紧凑的过滤栏，包含：
  - 所有列的全文本搜索
  - 列特定的过滤字段
  - 过滤清除按钮
  - 匹配数量显示
  - 防抖过滤
"""

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QLineEdit, QPushButton,
                              QLabel, QComboBox, QMenu, QAction)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon


class FilterBox(QWidget):
    """用于搜索和过滤表格数据的紧凑过滤栏。

    信号：
        filter_changed(dict): 活动过滤条件改变时发出 {列名: 文本模式}
        filter_cleared(): 过滤条件被重置时发出
    """

    # 过滤条件变化信号，携带当前过滤条件字典
    filter_changed = pyqtSignal(dict)
    # 过滤条件清除信号
    filter_cleared = pyqtSignal()

    def __init__(self, parent=None):
        """初始化过滤框

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 列名列表
        self._columns: list[str] = []
        # 活动的列过滤条件字典
        self._active_filters: dict[str, str] = {}
        # 防抖定时器
        self._debounce_timer = QTimer(self)
        # 设置为单次触发
        self._debounce_timer.setSingleShot(True)
        # 设置防抖间隔300毫秒
        self._debounce_timer.setInterval(300)
        # 连接定时器超时信号到发送过滤条件信号
        self._debounce_timer.timeout.connect(self._emit_filter_changed)
        # 设置UI界面
        self._setup_ui()

    def _setup_ui(self):
        """设置UI界面"""
        # 创建水平布局
        layout = QHBoxLayout(self)
        # 设置布局边距
        layout.setContentsMargins(4, 2, 4, 2)
        # 设置布局间距
        layout.setSpacing(4)

        # 搜索图标/标签
        icon_lbl = QLabel("🔍")
        # 设置图标样式
        icon_lbl.setStyleSheet("font-size: 13px; background: transparent;")
        # 添加到布局
        layout.addWidget(icon_lbl)

        # 主搜索框（搜索所有列）
        self._search_edit = QLineEdit()
        # 设置占位符文本
        self._search_edit.setPlaceholderText("搜索所有列...")
        # 启用清除按钮
        self._search_edit.setClearButtonEnabled(True)
        # 设置样式表
        self._search_edit.setStyleSheet("""
            QLineEdit {
                background: #3c3c3c; color: #dcdcdc; border: 1px solid #505050;
                border-radius: 3px; padding: 3px 6px; font-size: 12px;
            }
            QLineEdit:focus { border-color: #0078d4; }
        """)
        # 连接文本变化信号
        self._search_edit.textChanged.connect(self._on_search_text_changed)
        # 添加到布局，拉伸因子为2
        layout.addWidget(self._search_edit, 2)

        # 列过滤按钮
        self._column_btn = QPushButton("列过滤 ▾")
        # 设置按钮样式
        self._column_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: 1px solid #505050; border-radius: 3px;
                padding: 3px 8px; color: #dcdcdc; font-size: 11px;
            }
            QPushButton:hover { background: #3e3e42; }
        """)
        # 连接点击信号
        self._column_btn.clicked.connect(self._show_column_menu)
        # 添加到布局
        layout.addWidget(self._column_btn)

        # 列特定过滤输入框（当选择列过滤时显示）
        self._col_filter = QLineEdit()
        # 设置占位符文本
        self._col_filter.setPlaceholderText("按列过滤...")
        # 启用清除按钮
        self._col_filter.setClearButtonEnabled(True)
        # 使用与主搜索框相同的样式
        self._col_filter.setStyleSheet(self._search_edit.styleSheet())
        # 设置固定宽度150像素
        self._col_filter.setFixedWidth(150)
        # 初始不可见
        self._col_filter.setVisible(False)
        # 连接文本变化信号
        self._col_filter.textChanged.connect(self._on_col_filter_changed)
        # 添加到布局
        layout.addWidget(self._col_filter)

        # 活动列过滤标签
        self._active_col_label = QLabel()
        # 设置样式
        self._active_col_label.setStyleSheet("color: #0078d4; font-size: 11px; background: #1e3a5c; padding: 2px 6px; border-radius: 2px;")
        # 初始不可见
        self._active_col_label.setVisible(False)
        # 添加到布局
        layout.addWidget(self._active_col_label)

        # 清除所有过滤条件按钮
        clear_btn = QPushButton("✕")
        # 设置固定大小22x22
        clear_btn.setFixedSize(22, 22)
        # 设置工具提示
        clear_btn.setToolTip("清除所有过滤条件")
        # 设置按钮样式
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none; color: #999; font-size: 12px;
            }
            QPushButton:hover { color: #f44336; }
        """)
        # 连接点击信号
        clear_btn.clicked.connect(self.clear_filters)
        # 添加到布局
        layout.addWidget(clear_btn)

        # 匹配数量标签
        self._count_label = QLabel()
        # 设置样式
        self._count_label.setStyleSheet("color: #999; font-size: 11px; background: transparent;")
        # 添加到布局
        layout.addWidget(self._count_label)

    # -- 公共API --

    def set_columns(self, columns: list[str]):
        """设置可用的列名列表（用于过滤）"""
        # 保存列名列表
        self._columns = columns

    def set_match_count(self, total: int, filtered: int):
        """更新匹配数量显示"""
        # 如果有活动过滤条件
        if self.has_active_filters():
            # 显示过滤后的数量/总数
            self._count_label.setText(f"{filtered}/{total}")
        else:
            # 只显示总数
            self._count_label.setText(f"{total} 项")

    def has_active_filters(self) -> bool:
        """检查是否有任何活动过滤条件"""
        # 返回搜索框是否有文本或活动过滤条件字典是否非空
        return bool(self._search_edit.text().strip()) or bool(self._active_filters)

    def get_filters(self) -> dict:
        """获取当前过滤条件状态

        返回：
            包含以下可选键的字典：
              - '_search': 全文本搜索字符串
              - '列名': 列特定过滤值
        """
        # 创建过滤器字典
        filters = {}
        # 获取搜索框文本并去除首尾空格
        search_text = self._search_edit.text().strip()
        # 如果搜索文本不为空
        if search_text:
            # 添加到过滤器字典，键为"_search"
            filters["_search"] = search_text
        # 更新列过滤条件
        filters.update(self._active_filters)
        # 返回过滤器字典
        return filters

    def clear_filters(self):
        """重置所有过滤条件"""
        # 清空搜索框
        self._search_edit.clear()
        # 清空活动过滤条件字典
        self._active_filters.clear()
        # 隐藏活动列标签
        self._active_col_label.setVisible(False)
        # 隐藏列过滤输入框
        self._col_filter.setVisible(False)
        # 清空列过滤输入框
        self._col_filter.clear()
        # 清空计数标签
        self._count_label.clear()
        # 发出过滤条件清除信号
        self.filter_cleared.emit()

    # -- 槽函数 --

    def _on_search_text_changed(self, text: str):
        """搜索框文本变化时的回调"""
        # 启动防抖定时器
        self._debounce_timer.start()

    def _on_col_filter_changed(self, text: str):
        """列过滤输入框文本变化时的回调"""
        # 获取活动列标签的文本
        col_name = self._active_col_label.text()
        # 如果列名存在
        if col_name:
            # 如果文本去除空格后不为空
            if text.strip():
                # 将列过滤条件添加到活动过滤器字典
                self._active_filters[col_name] = text.strip()
            else:
                # 从活动过滤器字典中移除该列
                self._active_filters.pop(col_name, None)
                # 如果活动过滤器字典为空
                if not self._active_filters:
                    # 隐藏活动列标签
                    self._active_col_label.setVisible(False)
                    # 隐藏列过滤输入框
                    self._col_filter.setVisible(False)
        # 启动防抖定时器
        self._debounce_timer.start()

    def _emit_filter_changed(self):
        """发送过滤条件变化信号"""
        # 发出过滤条件变化信号，携带当前过滤器字典
        self.filter_changed.emit(self.get_filters())

    def _show_column_menu(self):
        """显示列选择菜单"""
        # 创建菜单对象
        menu = QMenu(self)
        # 设置菜单样式
        menu.setStyleSheet("""
            QMenu { background: #2d2d30; color: #dcdcdc; border: 1px solid #505050; }
            QMenu::item { padding: 4px 20px; }
            QMenu::item:selected { background: #0078d4; }
        """)

        # 全部列选项（使用全文搜索）
        all_action = QAction("(全部列 — 全文搜索)", self)
        # 连接触发信号，传入空字符串
        all_action.triggered.connect(lambda: self._select_column_filter(""))
        # 添加到菜单
        menu.addAction(all_action)
        # 添加分隔线
        menu.addSeparator()

        # 遍历所有列名
        for col in self._columns:
            # 创建菜单动作
            action = QAction(col, self)
            # 连接触发信号，捕获列名
            action.triggered.connect(lambda checked, c=col: self._select_column_filter(c))
            # 如果该列有活动过滤条件
            if col in self._active_filters:
                # 可以添加选中图标（暂未实现）
                action.setIcon(QIcon())
            # 添加到菜单
            menu.addAction(action)

        # 在列过滤按钮的左下角显示菜单
        menu.exec_(self._column_btn.mapToGlobal(self._column_btn.rect().bottomLeft()))

    def _select_column_filter(self, column: str):
        """选择要过滤的列

        参数：
            column: 列名，空字符串表示清除列过滤
        """
        # 如果指定了列名
        if column:
            # 设置活动列标签文本
            self._active_col_label.setText(column)
            # 显示活动列标签
            self._active_col_label.setVisible(True)
            # 显示列过滤输入框
            self._col_filter.setVisible(True)
            # 设置列过滤输入框的占位符
            self._col_filter.setPlaceholderText(f"过滤 {column}...")
            # 如果该列已有活动过滤条件
            if column in self._active_filters:
                # 设置列过滤输入框的文本为已有的过滤值
                self._col_filter.setText(self._active_filters[column])
            else:
                # 清空列过滤输入框
                self._col_filter.clear()
            # 设置焦点到列过滤输入框
            self._col_filter.setFocus()
        else:
            # 隐藏活动列标签
            self._active_col_label.setVisible(False)
            # 隐藏列过滤输入框
            self._col_filter.setVisible(False)
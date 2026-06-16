"""日志面板 - 显示运行日志消息，支持过滤、来源追踪、导出。

从 H.Modules.Messages.Notice + H.Services.Message 移植。

功能：
  - 带时间戳的彩色日志消息
  - 来源追踪（节点/模块来源）
  - 基于级别的过滤
  - 复制到剪贴板 / 导出到文件
  - 点击日志条目跳转到节点
  - 自动滚动，可配置最大行数
"""

import os
from datetime import datetime
from enum import Enum

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QHBoxLayout,
                              QPushButton, QToolBar, QAction, QMenu,
                              QApplication, QFileDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings
from PyQt5.QtGui import QTextCursor, QColor, QFont

from core.events import EventType, event_system
from gui.theme import theme_manager, connect_theme


class LogLevel(Enum):
    """日志级别枚举，包含显示名称和颜色"""
    # 信息级别：灰色
    INFO = ("信息", QColor("#dcdcdc"))
    # 成功级别：绿色
    SUCCESS = ("成功", QColor("#4caf50"))
    # 警告级别：橙色
    WARN = ("警告", QColor("#ff9800"))
    # 错误级别：红色
    ERROR = ("错误", QColor("#f44336"))
    # 严重级别：深红色
    FATAL = ("严重", QColor("#d32f2f"))


class LogPanel(QWidget):
    """可滚动的日志面板，支持彩色消息、来源追踪和导出。

    信号：
        node_jump_requested(str) - 用户请求跳转到某个节点时发出
    """

    # 最大日志行数限制
    MAX_LINES = 5000

    # 用户请求跳转到节点时发出的信号
    node_jump_requested = pyqtSignal(str)  # node_id

    # QSettings中过滤器的键名
    SETTINGS_KEY_FILTERS = "LogPanel/Filters"

    def __init__(self, parent=None):
        """初始化日志面板

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        self._event_handlers: list[tuple] = []  # 存储 (event_type, handler) 用于取消订阅
        super().__init__(parent)
        # 原始日志条目列表（用于导出）
        self._log_entries: list[dict] = []
        # 过滤器字典
        self._filters: dict[str, bool] = {}
        # 从QSettings加载过滤器设置
        self._load_filters()
        # 设置UI界面
        self._setup_ui()
        # 连接事件系统
        self._connect_events()
        # 连接主题变化信号
        connect_theme(self._refresh_qss)

    # ── 过滤器持久化 ────────────────────────────────────────────

    def _load_filters(self):
        """从QSettings加载过滤器设置"""
        # 创建QSettings对象
        s = QSettings()
        # 初始化过滤器默认值（全部启用）
        self._filters = {
            "info": True,      # 信息级别
            "success": True,   # 成功级别
            "warn": True,      # 警告级别
            "error": True,     # 错误级别
        }
        # 遍历每个过滤器键
        for k in self._filters:
            # 从QSettings获取值
            val = s.value(f"{self.SETTINGS_KEY_FILTERS}/{k}")
            # 如果值存在
            if val is not None:
                # 转换为布尔值并保存
                self._filters[k] = str(val).lower() == "true" if isinstance(val, str) else bool(val)

    def _save_filters(self):
        """保存过滤器设置到QSettings"""
        # 创建QSettings对象
        s = QSettings()
        # 遍历过滤器字典
        for k, v in self._filters.items():
            # 保存值
            s.setValue(f"{self.SETTINGS_KEY_FILTERS}/{k}", v)

    # ── UI ────────────────────────────────────────────────────────────

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 2)
        toolbar.setSpacing(4)

        # 清空按钮
        self._clear_btn = QPushButton("清空")
        # 设置固定高度24像素
        self._clear_btn.setFixedHeight(24)
        # 连接点击信号
        self._clear_btn.clicked.connect(self.clear)
        # 添加到工具栏
        toolbar.addWidget(self._clear_btn)

        # 导出按钮
        self._export_btn = QPushButton("导出")
        # 设置固定高度24像素
        self._export_btn.setFixedHeight(24)
        # 连接点击信号
        self._export_btn.clicked.connect(self._export_log)
        # 添加到工具栏
        toolbar.addWidget(self._export_btn)

        # 复制按钮
        self._copy_btn = QPushButton("复制")
        # 设置固定高度24像素
        self._copy_btn.setFixedHeight(24)
        # 连接点击信号
        self._copy_btn.clicked.connect(self._copy_to_clipboard)
        # 添加到工具栏
        toolbar.addWidget(self._copy_btn)

        # 添加弹性空间
        toolbar.addStretch()

        # 过滤器按钮组
        # 信息级别按钮
        self._filter_info = QPushButton("信息")
        # 设置固定高度24像素
        self._filter_info.setFixedHeight(24)
        # 设置为可选中
        self._filter_info.setCheckable(True)
        # 设置选中状态
        self._filter_info.setChecked(self._filters.get("info", True))
        # 连接切换信号
        self._filter_info.toggled.connect(lambda v: self._set_filter("info", v))
        # 添加到工具栏
        toolbar.addWidget(self._filter_info)

        # 成功级别按钮
        self._filter_success = QPushButton("成功")
        # 设置固定高度24像素
        self._filter_success.setFixedHeight(24)
        # 设置为可选中
        self._filter_success.setCheckable(True)
        # 设置选中状态
        self._filter_success.setChecked(self._filters.get("success", True))
        # 连接切换信号
        self._filter_success.toggled.connect(lambda v: self._set_filter("success", v))
        # 添加到工具栏
        toolbar.addWidget(self._filter_success)

        # 警告级别按钮
        self._filter_warn = QPushButton("警告")
        # 设置固定高度24像素
        self._filter_warn.setFixedHeight(24)
        # 设置为可选中
        self._filter_warn.setCheckable(True)
        # 设置选中状态
        self._filter_warn.setChecked(self._filters.get("warn", True))
        # 连接切换信号
        self._filter_warn.toggled.connect(lambda v: self._set_filter("warn", v))
        # 添加到工具栏
        toolbar.addWidget(self._filter_warn)

        # 错误级别按钮
        self._filter_error = QPushButton("错误")
        # 设置固定高度24像素
        self._filter_error.setFixedHeight(24)
        # 设置为可选中
        self._filter_error.setCheckable(True)
        # 设置选中状态
        self._filter_error.setChecked(self._filters.get("error", True))
        # 连接切换信号
        self._filter_error.toggled.connect(lambda v: self._set_filter("error", v))
        # 添加到工具栏
        toolbar.addWidget(self._filter_error)

        # 创建工具栏控件
        self._toolbar_widget = QWidget()
        # 设置布局
        self._toolbar_widget.setLayout(toolbar)
        # 添加到主布局
        layout.addWidget(self._toolbar_widget)

        # 日志文本显示区
        self._text_edit = QTextEdit()
        # 设置为只读
        self._text_edit.setReadOnly(True)
        # 设置字体为Consolas，大小9
        self._text_edit.setFont(QFont("Consolas", 9))
        # 设置垂直滚动条始终显示
        self._text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # 设置自定义上下文菜单策略
        self._text_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        # 连接右键菜单请求信号
        self._text_edit.customContextMenuRequested.connect(self._on_log_context_menu)
        # 添加到布局
        layout.addWidget(self._text_edit)

        # 应用初始样式
        self._refresh_qss()

    # ── 主题刷新 ──────────────────────────────────────────────────

    def _refresh_qss(self):
        """使用主题颜色重新应用所有QSS样式"""
        # 从主题管理器获取各种颜色
        bg_raised = theme_manager.color('bg_surface_raised').name()   # 凸起背景色
        border = theme_manager.color('border').name()                 # 边框色
        bg_deep = theme_manager.color('bg_surface_deep').name()       # 深层背景色
        bg_surface = theme_manager.color('bg_surface').name()         # 表面背景色
        text_primary = theme_manager.color('text_primary').name()     # 主文本色
        text_secondary = theme_manager.color('text_secondary').name() # 次要文本色
        accent = theme_manager.color('accent').name()                 # 强调色
        scroll_handle = theme_manager.color('scroll_handle').name()   # 滚动条手柄色
        hover_bg = theme_manager.color('bg_surface_hover').name()     # 悬停背景色
        input_bg = theme_manager.color('bg_surface_input').name()     # 输入框背景色

        # 过滤器按钮样式
        filter_style = f"""
            QPushButton {{
                background: {input_bg}; border: none; border-radius: 2px;
                padding: 2px 8px; font-size: 11px; color: {text_primary};
            }}
            QPushButton:checked {{ background: {accent}; color: white; }}
        """
        # 遍历所有过滤器按钮，应用样式
        for btn in [self._filter_info, self._filter_success,
                     self._filter_warn, self._filter_error]:
            btn.setStyleSheet(filter_style)

        # 工具栏背景样式
        self._toolbar_widget.setStyleSheet(
            f"background: {bg_raised}; border-bottom: 1px solid {border};"
        )

        # 日志文本区域样式
        self._text_edit.setStyleSheet(f"""
            QTextEdit {{
                background: {bg_surface}; color: {text_primary}; border: none; padding: 4px;
            }}
        """)

        # 动作按钮样式（清空、导出、复制）
        btn_style = f"""
            QPushButton {{
                background: transparent; border: 1px solid {scroll_handle}; border-radius: 2px;
                padding: 2px 10px; font-size: 11px; color: {text_primary};
            }}
            QPushButton:hover {{ background: {hover_bg}; }}
        """
        # 遍历所有动作按钮，应用样式
        for btn in [self._clear_btn, self._export_btn, self._copy_btn]:
            btn.setStyleSheet(btn_style)

    # ── 事件连接 ─────────────────────────────────────────────────────────────

    def _connect_events(self):
        """连接事件系统的各种事件，并保存处理函数引用以便取消订阅"""
        # 节点开始事件
        h1 = lambda s, **kw: self.info(
            f"节点开始: {self._node_label(s)}", source=self._node_source(s))
        event_system.subscribe(EventType.NODE_STARTED, h1)
        self._event_handlers.append((EventType.NODE_STARTED, h1))

        # 节点完成事件
        h2 = lambda s, **kw: self.success(
            f"节点完成: {self._node_label(s)}", source=self._node_source(s))
        event_system.subscribe(EventType.NODE_COMPLETED, h2)
        self._event_handlers.append((EventType.NODE_COMPLETED, h2))

        # 节点错误事件
        h3 = lambda s, **kw: self.error(
            f"节点错误: {self._node_label(s)} - {kw.get('result', '')}",
            source=self._node_source(s))
        event_system.subscribe(EventType.NODE_ERROR, h3)
        self._event_handlers.append((EventType.NODE_ERROR, h3))

        # 工作流开始事件
        h4 = lambda s, **kw: self.info("流程开始", source={"type": "workflow"})
        event_system.subscribe(EventType.WORKFLOW_STARTED, h4)
        self._event_handlers.append((EventType.WORKFLOW_STARTED, h4))

        # 工作流完成事件
        h5 = lambda s, **kw: self.success("流程完成", source={"type": "workflow"})
        event_system.subscribe(EventType.WORKFLOW_COMPLETED, h5)
        self._event_handlers.append((EventType.WORKFLOW_COMPLETED, h5))

        # 工作流错误事件
        h6 = lambda s, **kw: self.error(
            f"流程错误: {kw.get('result', '')}", source={"type": "workflow"})
        event_system.subscribe(EventType.WORKFLOW_ERROR, h6)
        self._event_handlers.append((EventType.WORKFLOW_ERROR, h6))

        # 信息消息事件
        h7 = lambda s, **kw: self.info(
            kw.get("message", ""),
            source=kw.get("source", {"type": "system"}),
            node_id=kw.get("node_id", ""))
        event_system.subscribe(EventType.MESSAGE_INFO, h7)
        self._event_handlers.append((EventType.MESSAGE_INFO, h7))

        # 警告消息事件
        h8 = lambda s, **kw: self.warning(
            kw.get("message", ""),
            source=kw.get("source", {"type": "system"}),
            node_id=kw.get("node_id", ""))
        event_system.subscribe(EventType.MESSAGE_WARN, h8)
        self._event_handlers.append((EventType.MESSAGE_WARN, h8))

        # 错误消息事件
        h9 = lambda s, **kw: self.error(
            kw.get("message", ""),
            source=kw.get("source", {"type": "system"}),
            node_id=kw.get("node_id", ""))
        event_system.subscribe(EventType.MESSAGE_ERROR, h9)
        self._event_handlers.append((EventType.MESSAGE_ERROR, h9))

        # 成功消息事件
        h10 = lambda s, **kw: self.success(
            kw.get("message", ""),
            source=kw.get("source", {"type": "system"}),
            node_id=kw.get("node_id", ""))
        event_system.subscribe(EventType.MESSAGE_SUCCESS, h10)
        self._event_handlers.append((EventType.MESSAGE_SUCCESS, h10))

    def _disconnect_events(self):
        """取消所有事件订阅"""
        for event_type, handler in self._event_handlers:
            event_system.unsubscribe(event_type, handler)
        self._event_handlers.clear()

    def closeEvent(self, event):
        """关闭时取消所有事件订阅"""
        self._disconnect_events()
        super().closeEvent(event)

    @staticmethod
    def _node_label(sender) -> str:
        """获取节点标签"""
        # 返回节点的name属性，否则返回字符串表示
        return getattr(sender, "name", str(sender))

    @staticmethod
    def _node_source(sender) -> dict:
        """获取节点来源信息"""
        # 返回包含类型、名称和节点ID的字典
        return {"type": "node", "name": getattr(sender, "name", "?"),
                "node_id": getattr(sender, "node_id", "")}

    # ── 日志API ───────────────────────────────────────────────────

    def log(self, level: LogLevel, message: str, source: dict = None, node_id: str = ""):
        """添加带来源追踪的彩色日志消息

        参数：
            level: 日志级别
            message: 日志消息
            source: 来源信息
            node_id: 节点ID
        """
        # 获取当前时间，格式 HH:MM:SS
        now = datetime.now().strftime("%H:%M:%S")
        # 获取日志级别对应的颜色
        color = level.value[1]

        # 检查过滤器
        level_key = {
            LogLevel.INFO: "info",       # 信息
            LogLevel.SUCCESS: "success", # 成功
            LogLevel.WARN: "warn",       # 警告
            LogLevel.ERROR: "error",     # 错误
            LogLevel.FATAL: "error",     # 严重（归为错误）
        }.get(level, "info")
        # 如果过滤器禁用该级别，直接返回
        if not self._filters.get(level_key, True):
            return

        # 设置默认来源
        source = source or {"type": "system"}
        # 获取来源名称
        source_name = source.get("name", source.get("type", "system"))
        # 获取节点ID
        node_id = node_id or source.get("node_id", "")

        # 结构化条目（用于导出）
        entry = {
            "time": now,                    # 时间
            "level": level.value[0],        # 级别名称
            "message": message,             # 消息内容
            "source": source_name,          # 来源名称
            "node_id": node_id,             # 节点ID
        }
        # 添加到日志条目列表
        self._log_entries.append(entry)
        # 如果超过最大行数限制
        if len(self._log_entries) > self.MAX_LINES:
            # 只保留最后MAX_LINES条
            self._log_entries = self._log_entries[-self.MAX_LINES:]

        # 构建显示行
        line = f"[{now}] [{level.value[0]}] [{source_name}] {message}\n"

        # 移动到文本末尾
        self._text_edit.moveCursor(QTextCursor.End)
        # 设置文本颜色
        self._text_edit.setTextColor(color)
        # 插入纯文本
        self._text_edit.insertPlainText(line)

        # 限制显示区域的行数
        block_count = self._text_edit.document().blockCount()
        if block_count > self.MAX_LINES:
            # 获取光标
            cursor = self._text_edit.textCursor()
            # 移动到开头
            cursor.movePosition(QTextCursor.Start)
            # 选中超出数量的行
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor,
                              block_count - self.MAX_LINES)
            # 删除选中的文本
            cursor.removeSelectedText()

    def info(self, message: str, source: dict = None, node_id: str = ""):
        """添加信息级别日志

        参数：
            message: 日志消息
            source: 来源信息
            node_id: 节点ID
        """
        self.log(LogLevel.INFO, message, source, node_id)

    def success(self, message: str, source: dict = None, node_id: str = ""):
        """添加成功级别日志

        参数：
            message: 日志消息
            source: 来源信息
            node_id: 节点ID
        """
        self.log(LogLevel.SUCCESS, message, source, node_id)

    def warning(self, message: str, source: dict = None, node_id: str = ""):
        """添加警告级别日志

        参数：
            message: 日志消息
            source: 来源信息
            node_id: 节点ID
        """
        self.log(LogLevel.WARN, message, source, node_id)

    def error(self, message: str, source: dict = None, node_id: str = ""):
        """添加错误级别日志

        参数：
            message: 日志消息
            source: 来源信息
            node_id: 节点ID
        """
        self.log(LogLevel.ERROR, message, source, node_id)

    def fatal(self, message: str, source: dict = None, node_id: str = ""):
        """添加严重级别日志

        参数：
            message: 日志消息
            source: 来源信息
            node_id: 节点ID
        """
        self.log(LogLevel.FATAL, message, source, node_id)

    # ── 操作 ───────────────────────────────────────────────────────

    def clear(self):
        """清空所有日志条目"""
        # 清空文本显示区
        self._text_edit.clear()
        # 清空日志条目列表
        self._log_entries.clear()

    def _set_filter(self, key: str, enabled: bool):
        """设置过滤器

        参数：
            key: 过滤器键名
            enabled: 是否启用
        """
        # 保存过滤器状态
        self._filters[key] = enabled
        # 保存到QSettings
        self._save_filters()

    def _copy_to_clipboard(self):
        """复制选中或全部日志文本到剪贴板"""
        # 获取光标
        cursor = self._text_edit.textCursor()
        # 如果有选中的文本
        if cursor.hasSelection():
            # 获取选中的文本
            text = cursor.selectedText()
        else:
            # 获取全部纯文本
            text = self._text_edit.toPlainText()
        # 设置剪贴板文本
        QApplication.clipboard().setText(text)

    def _export_log(self):
        """导出日志条目到文本文件"""
        # 打开保存文件对话框
        path, _ = QFileDialog.getSaveFileName(
            self, "导出日志", "visionflow_log.txt",
            "文本文件 (*.txt);;日志文件 (*.log);;CSV文件 (*.csv)")
        # 如果未选择路径，返回
        if not path:
            return

        try:
            # 获取文件扩展名
            _, ext = os.path.splitext(path)
            # 如果是CSV格式
            if ext.lower() == ".csv":
                self._export_csv(path)
            else:
                # 否则导出为文本格式
                self._export_text(path)
        except Exception as e:
            # 导出失败时记录错误
            self.error(f"导出日志失败: {e}")

    def _export_text(self, path: str):
        """导出为文本格式

        参数：
            path: 文件路径
        """
        # 以UTF-8编码打开文件
        with open(path, "w", encoding="utf-8") as f:
            # 遍历所有日志条目
            for entry in self._log_entries:
                # 写入一行日志
                f.write(f"[{entry['time']}] [{entry['level']}] [{entry['source']}] {entry['message']}\n")

    def _export_csv(self, path: str):
        """导出为CSV格式

        参数：
            path: 文件路径
        """
        import csv
        # 以UTF-8 with BOM编码打开文件
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            # 创建CSV写入器
            writer = csv.DictWriter(f, fieldnames=["time", "level", "source", "node_id", "message"])
            # 写入表头
            writer.writeheader()
            # 写入所有数据行
            writer.writerows(self._log_entries)

    def _on_log_context_menu(self, pos):
        """日志区域右键上下文菜单

        参数：
            pos: 右键点击位置
        """
        # 从主题管理器获取各种颜色
        bg_raised = theme_manager.color('bg_surface_raised').name()
        text_primary = theme_manager.color('text_primary').name()
        scroll_handle = theme_manager.color('scroll_handle').name()
        accent = theme_manager.color('accent').name()

        # 创建菜单
        menu = QMenu(self)
        # 设置菜单样式
        menu.setStyleSheet(f"""
            QMenu {{ background: {bg_raised}; color: {text_primary}; border: 1px solid {scroll_handle}; }}
            QMenu::item {{ padding: 6px 20px; }}
            QMenu::item:selected {{ background: {accent}; }}
        """)

        # 复制选中动作
        copy_act = QAction("复制选中", self)
        copy_act.triggered.connect(self._copy_to_clipboard)
        menu.addAction(copy_act)

        # 复制全部动作
        copy_all_act = QAction("复制全部", self)
        copy_all_act.triggered.connect(lambda: QApplication.clipboard().setText(
            self._text_edit.toPlainText()))
        menu.addAction(copy_all_act)

        # 分隔线
        menu.addSeparator()

        # 导出日志动作
        export_act = QAction("导出日志...", self)
        export_act.triggered.connect(self._export_log)
        menu.addAction(export_act)

        # 分隔线
        menu.addSeparator()

        # 清空日志动作
        clear_act = QAction("清空日志", self)
        clear_act.triggered.connect(self.clear)
        menu.addAction(clear_act)

        # 在鼠标位置显示菜单
        menu.exec_(self._text_edit.viewport().mapToGlobal(pos))

    # ── 外部API ──────────────────────────────────────────────────

    def get_entries(self) -> list[dict]:
        """获取所有日志条目（供外部分析使用）

        返回：
            日志条目列表
        """
        # 返回日志条目的副本
        return list(self._log_entries)
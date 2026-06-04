"""
WPF CaptionTemplate 精确还原 — 85px标题栏
Row1: QMenuBar(左) + 项目名(中) + 系统按钮(右)
Row2: 工具栏(新建/打开/保存 | 全局命令 | 流程图命令 | 视图切换)
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMenuBar, QMenu,
    QLabel, QPushButton, QToolButton, QSizePolicy, QFrame
)
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QAction, QFont, QMouseEvent, QKeySequence

from core.events import EventBus, Event, EventType
from .theme import Colors


class TitleBar(QWidget):
    """WPF CaptionTemplate — 85px标题栏区域"""

    # 窗口控制信号
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    # 操作信号
    new_project = Signal()
    open_project = Signal()
    save_project = Signal()
    edit_project = Signal()
    execute_workflow = Signal()
    setting_clicked = Signal()
    about_clicked = Signal()

    def __init__(self, parent_window, event_bus: EventBus, title="VisionFlow"):
        super().__init__()
        self._parent = parent_window
        self.event_bus = event_bus
        self._dragging = False
        self._drag_pos = QPoint()

        self.setFixedHeight(85)
        self.setObjectName("captionTemplate")

        self._setup_ui()
        self._setup_menus()

    def _setup_ui(self):
        """构建2行标题栏布局"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ====== Row1: 菜单栏 + 项目名 + 系统按钮 (~40px) ======
        row1 = QWidget()
        row1.setFixedHeight(42)
        row1.setStyleSheet(f"background-color: {Colors.BackgroundLight};")
        row1_layout = QHBoxLayout()
        row1_layout.setContentsMargins(0, 0, 4, 0)
        row1_layout.setSpacing(0)

        # 菜单栏(嵌入标题栏)
        self.menubar = QMenuBar()
        self.menubar.setNativeMenuBar(False)
        self.menubar.setStyleSheet(f"""
            QMenuBar {{
                background: transparent;
                color: {Colors.Foreground};
                font: 12px "Microsoft YaHei";
                padding: 2px 0;
            }}
            QMenuBar::item {{
                padding: 6px 12px;
                background: transparent;
                border-radius: 3px;
            }}
            QMenuBar::item:selected {{
                background-color: {Colors.Accent};
            }}
            QMenu {{
                background-color: {Colors.BackgroundLight};
                color: {Colors.Foreground};
                border: 1px solid {Colors.Border};
                font: 12px "Microsoft YaHei";
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 6px 36px 6px 20px;
            }}
            QMenu::item:selected {{
                background-color: {Colors.Accent};
            }}
            QMenu::separator {{
                height: 1px;
                background: {Colors.Border};
                margin: 5px 10px;
            }}
        """)
        row1_layout.addWidget(self.menubar)

        # 项目名称(居中)
        self.project_name_label = QLabel("项目名称：未命名项目")
        self.project_name_label.setAlignment(Qt.AlignCenter)
        self.project_name_label.setStyleSheet(f"""
            color: {Colors.ForegroundDim};
            font: 11px "Microsoft YaHei";
            background: transparent;
            border: none;
        """)
        row1_layout.addWidget(self.project_name_label, 1)

        # 系统按钮(右上角)
        sys_btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {Colors.ForegroundDim};
                border: none;
                font-size: 10px;
                padding: 4px 8px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {Colors.BorderLight};
                color: {Colors.Foreground};
            }}
        """

        for text, signal, tip in [
            ("主题", self.setting_clicked, "颜色主题"),
            ("设置", self.setting_clicked, "系统设置"),
            ("关于", self.about_clicked, "关于"),
            ("引导", None, "使用引导"),
        ]:
            btn = QPushButton(text)
            btn.setStyleSheet(sys_btn_style)
            btn.setToolTip(tip)
            if signal:
                btn.clicked.connect(signal)
            row1_layout.addWidget(btn)

        # 窗口控制按钮
        win_btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {Colors.ForegroundDim};
                border: none;
                font-size: 14px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background: {Colors.BorderLight};
                color: {Colors.Foreground};
            }}
            QPushButton#btnClose:hover {{
                background: {Colors.Red};
                color: white;
            }}
        """

        btn_min = QPushButton("—")
        btn_min.setStyleSheet(win_btn_style)
        btn_min.clicked.connect(self.minimize_clicked)

        btn_max = QPushButton("□")
        btn_max.setStyleSheet(win_btn_style)
        btn_max.clicked.connect(self.maximize_clicked)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("btnClose")
        btn_close.setStyleSheet(win_btn_style)
        btn_close.clicked.connect(self.close_clicked)

        row1_layout.addWidget(btn_min)
        row1_layout.addWidget(btn_max)
        row1_layout.addWidget(btn_close)

        row1.setLayout(row1_layout)
        main_layout.addWidget(row1)

        # ====== 分隔线 ======
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background: {Colors.Border}; border: none;")
        sep.setFixedHeight(1)
        main_layout.addWidget(sep)

        # ====== Row2: 工具栏行 (~42px) ======
        row2 = QWidget()
        row2.setFixedHeight(42)
        row2.setStyleSheet(f"background-color: {Colors.BackgroundLight};")
        row2_layout = QHBoxLayout()
        row2_layout.setContentsMargins(4, 3, 4, 3)
        row2_layout.setSpacing(4)

        toolbar_btn_style = f"""
            QToolButton {{
                background: transparent;
                color: {Colors.Foreground};
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font: 11px "Microsoft YaHei";
            }}
            QToolButton:hover {{
                background: {Colors.BorderLight};
            }}
            QToolButton:pressed {{
                background: {Colors.Accent};
            }}
        """

        # 文件操作
        for text, signal, tip in [
            ("📄 新建", self.new_project, "新建项目"),
            ("📂 打开", self.open_project, "打开项目"),
            ("✏️ 编辑", self.edit_project, "编辑项目"),
            ("💾 保存", self.save_project, "保存项目"),
        ]:
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tip)
            btn.setStyleSheet(toolbar_btn_style)
            btn.clicked.connect(signal)
            row2_layout.addWidget(btn)

        # 分隔
        sep_v = QFrame()
        sep_v.setFrameShape(QFrame.VLine)
        sep_v.setStyleSheet(f"background: {Colors.Border}; border: none;")
        sep_v.setFixedWidth(1)
        row2_layout.addWidget(sep_v)

        # 全局命令区(占位)
        self.global_cmds_label = QLabel("")
        self.global_cmds_label.setStyleSheet(f"color: {Colors.ForegroundDim}; font: 10px 'Microsoft YaHei'; background: transparent;")
        row2_layout.addWidget(self.global_cmds_label)

        # 弹性空间
        row2_layout.addStretch()

        # 流程图命令区(占位)
        self.diagram_cmds_label = QLabel("")
        self.diagram_cmds_label.setStyleSheet(f"color: {Colors.ForegroundDim}; font: 10px 'Microsoft YaHei'; background: transparent;")
        row2_layout.addWidget(self.diagram_cmds_label)

        # 分隔
        sep_v2 = QFrame()
        sep_v2.setFrameShape(QFrame.VLine)
        sep_v2.setStyleSheet(f"background: {Colors.Border}; border: none;")
        sep_v2.setFixedWidth(1)
        row2_layout.addWidget(sep_v2)

        # 执行按钮
        run_btn = QToolButton()
        run_btn.setText("▶ 执行")
        run_btn.setToolTip("执行工作流 (F5)")
        run_btn.setStyleSheet(f"""
            QToolButton {{
                background: {Colors.Accent};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 14px;
                font: 11px "Microsoft YaHei";
            }}
            QToolButton:hover {{
                background: {Colors.AccentLight};
            }}
        """)
        run_btn.clicked.connect(self.execute_workflow)
        row2_layout.addWidget(run_btn)

        row2.setLayout(row2_layout)
        main_layout.addWidget(row2)

        self.setLayout(main_layout)

    def _setup_menus(self):
        """构建WPF风格的菜单结构"""
        # === 文件菜单 ===
        file_menu = self.menubar.addMenu("文件")

        file_menu.addAction("新建项目(N)", self.new_project.emit, QKeySequence.New)
        file_menu.addAction("打开项目(O)...", self.open_project.emit, QKeySequence.Open)
        file_menu.addAction("编辑项目", self.edit_project.emit)
        file_menu.addAction("保存项目(S)", self.save_project.emit, QKeySequence.Save)

        recent_menu = file_menu.addMenu("最近的项目")
        recent_menu.addAction("(空)")

        file_menu.addSeparator()
        exit_action = file_menu.addAction("退出(X)", self.close_clicked.emit, QKeySequence.Quit)

        # === 编辑菜单 ===
        edit_menu = self.menubar.addMenu("编辑")
        edit_menu.addAction("撤销(U)", None, QKeySequence.Undo)
        edit_menu.addAction("重做(R)", None, QKeySequence.Redo)
        edit_menu.addSeparator()
        edit_menu.addAction("剪切(T)", None, QKeySequence.Cut)
        edit_menu.addAction("复制(C)", None, QKeySequence.Copy)
        edit_menu.addAction("粘贴(P)", None, QKeySequence.Paste)
        edit_menu.addAction("删除(D)", None, QKeySequence.Delete)

        # === 运行菜单 ===
        run_menu = self.menubar.addMenu("运行")
        run_menu.addAction("执行(E)", self.execute_workflow.emit, "F5")
        run_menu.addAction("单步执行(S)", None, "F10")
        run_menu.addAction("暂停(P)", None, "F6")
        run_menu.addAction("停止(T)", None, "F7")
        run_menu.addSeparator()
        run_menu.addAction("连续执行(C)")

        # === 系统菜单 ===
        sys_menu = self.menubar.addMenu("系统")
        sys_menu.addAction("设置...", self.setting_clicked.emit)
        sys_menu.addAction("日志路径")
        sys_menu.addAction("颜色主题", self.setting_clicked.emit)
        sys_menu.addSeparator()
        sys_menu.addAction("流程功能列表")

        # === 帮助菜单 ===
        help_menu = self.menubar.addMenu("帮助")
        help_menu.addAction("帮助文档(D)", None, QKeySequence.HelpContents)
        help_menu.addSeparator()
        help_menu.addAction("检查更新")
        help_menu.addAction("注册")
        help_menu.addSeparator()

        contact_menu = help_menu.addMenu("联系我们")
        contact_menu.addAction("Github")
        contact_menu.addAction("提交Issue")
        contact_menu.addAction("QQ群")
        contact_menu.addAction("发送邮件")
        contact_menu.addAction("博客")
        contact_menu.addAction("播客")

        privacy_menu = help_menu.addMenu("隐私")
        privacy_menu.addAction("用户协议")
        privacy_menu.addAction("隐私政策")

        help_menu.addSeparator()
        help_menu.addAction("赞助")
        help_menu.addAction("关于(A)", self.about_clicked.emit)

    # ========== 拖拽移动窗口 ==========

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and event.position().y() < 42:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self._parent.move(self._parent.x() + delta.x(), self._parent.y() + delta.y())
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._dragging = False

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and event.position().y() < 42:
            self.maximize_clicked.emit()

    # ========== 公开API ==========

    def set_project_name(self, name: str):
        self.project_name_label.setText(f"项目名称：{name}")

    def set_global_commands(self, count: int):
        self.global_cmds_label.setText(f"全局命令: {count}" if count > 0 else "")

    def set_diagram_commands(self, count: int):
        self.diagram_cmds_label.setText(f"流程图命令: {count}" if count > 0 else "")

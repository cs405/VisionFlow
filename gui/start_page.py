"""起始页 - 欢迎屏幕，显示最近项目和快速操作。

在没有项目打开时显示，包含：
  - Logo / 应用标题
  - 新建项目 / 打开项目 按钮
  - 带元数据的最近项目列表
  - 点击打开最近项目
"""

import os

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QListWidget, QListWidgetItem,
                              QFrame, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap


class StartPage(QWidget):
    """带最近项目和快速操作的欢迎页面

    信号：
        new_project_requested: 用户点击"新建项目"
        open_project_requested: 用户点击"打开项目"
        project_open_requested(str): 用户点击最近项目路径
    """

    # 新建项目请求信号
    new_project_requested = pyqtSignal()
    # 打开项目请求信号
    open_project_requested = pyqtSignal()
    # 项目打开请求信号，携带项目路径
    project_open_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        """初始化起始页

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 设置背景样式为深色
        self.setStyleSheet("background: #1e1e1e;")
        # 设置UI界面
        self._setup_ui()

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)

        # 中心容器
        center = QWidget()
        # 设置背景透明
        center.setStyleSheet("background: transparent;")
        # 创建垂直布局
        center_layout = QVBoxLayout(center)
        # 设置居中对齐
        center_layout.setAlignment(Qt.AlignCenter)
        # 设置布局间距为16
        center_layout.setSpacing(16)

        # 顶部弹性空间（拉伸因子2）
        center_layout.addStretch(2)

        # Logo / 标题
        # 获取Logo图片路径
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "logo.png")
        # 如果Logo文件存在
        if os.path.exists(logo_path):
            # 创建Logo标签
            logo = QLabel()
            # 设置居中对齐
            logo.setAlignment(Qt.AlignCenter)
            # 加载并缩放Logo图片（72x72，保持宽高比，平滑变换）
            logo.setPixmap(QPixmap(logo_path).scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            # 设置背景透明
            logo.setStyleSheet("background: transparent;")
            # 添加到布局
            center_layout.addWidget(logo)

        # 应用标题
        title = QLabel("VisionFlow")
        # 设置居中对齐
        title.setAlignment(Qt.AlignCenter)
        # 设置标题样式
        title.setStyleSheet("color: #0078d4; font-size: 32px; font-weight: bold; background: transparent;")
        # 添加到布局
        center_layout.addWidget(title)

        # 副标题
        subtitle = QLabel("视觉工作流编辑器")
        # 设置居中对齐
        subtitle.setAlignment(Qt.AlignCenter)
        # 设置副标题样式
        subtitle.setStyleSheet("color: #aaaaaa; font-size: 14px; background: transparent;")
        # 添加到布局
        center_layout.addWidget(subtitle)

        # 版本号
        version = QLabel("v2.0.0")
        # 设置居中对齐
        version.setAlignment(Qt.AlignCenter)
        # 设置版本号样式
        version.setStyleSheet("color: #666666; font-size: 11px; background: transparent;")
        # 添加到布局
        center_layout.addWidget(version)

        # 添加间距24像素
        center_layout.addSpacing(24)

        # 动作按钮行
        btn_row = QHBoxLayout()
        # 设置居中对齐
        btn_row.setAlignment(Qt.AlignCenter)
        # 设置按钮间距为12
        btn_row.setSpacing(12)

        # 按钮基础样式
        btn_style = """
            QPushButton {
                background: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 28px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1a8ad4; }
            QPushButton:pressed { background: #0060a8; }
        """

        # 新建项目按钮
        new_btn = QPushButton("新建项目")
        # 设置样式
        new_btn.setStyleSheet(btn_style)
        # 设置光标为手指形状
        new_btn.setCursor(Qt.PointingHandCursor)
        # 连接点击信号
        new_btn.clicked.connect(self.new_project_requested.emit)
        # 添加到按钮行
        btn_row.addWidget(new_btn)

        # 打开项目按钮（样式稍暗）
        open_btn = QPushButton("打开项目...")
        # 设置样式（替换背景色为深灰色）
        open_btn.setStyleSheet(btn_style.replace("#0078d4", "#3e3e42"))
        # 设置光标为手指形状
        open_btn.setCursor(Qt.PointingHandCursor)
        # 连接点击信号
        open_btn.clicked.connect(self.open_project_requested.emit)
        # 添加到按钮行
        btn_row.addWidget(open_btn)

        # 添加按钮行到中心布局
        center_layout.addLayout(btn_row)

        # 添加间距32像素
        center_layout.addSpacing(32)

        # 最近项目部分
        recent_label = QLabel("最近项目")
        # 设置居中对齐
        recent_label.setAlignment(Qt.AlignCenter)
        # 设置标签样式
        recent_label.setStyleSheet("color: #888888; font-size: 12px; font-weight: bold; background: transparent;")
        # 添加到中心布局
        center_layout.addWidget(recent_label)

        # 最近项目列表
        self.recent_list = QListWidget()
        # 设置固定大小420x200
        self.recent_list.setFixedSize(420, 200)
        # 设置列表样式
        self.recent_list.setStyleSheet("""
            QListWidget {
                background: #2d2d30;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                color: #dcdcdc;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #3f3f46;
            }
            QListWidget::item:hover { background: #3e3e42; }
            QListWidget::item:selected { background: #094771; }
        """)
        # 连接双击信号
        self.recent_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        # 添加到中心布局，居中对齐
        center_layout.addWidget(self.recent_list, alignment=Qt.AlignCenter)

        # 空状态提示标签
        self._empty_label = QLabel("暂无最近项目\n使用「打开项目」加载已有项目，或「新建项目」开始")
        # 设置居中对齐
        self._empty_label.setAlignment(Qt.AlignCenter)
        # 设置样式
        self._empty_label.setStyleSheet("color: #666666; font-size: 12px; background: transparent;")
        # 设置固定高度60像素
        self._empty_label.setFixedHeight(60)
        # 添加到中心布局
        center_layout.addWidget(self._empty_label)
        # 初始隐藏空状态标签
        self._empty_label.hide()

        # 底部弹性空间（拉伸因子3）
        center_layout.addStretch(3)

        # 添加中心容器到主布局
        layout.addWidget(center)

    def refresh_recent(self, project_service):
        """从项目服务刷新最近项目列表

        参数：
            project_service: 项目服务对象
        """
        # 清空列表
        self.recent_list.clear()
        # 清理不存在的最近项目
        project_service.cleanup_recent_projects()
        # 获取最近项目信息列表
        recent_info = project_service.get_recent_projects_info()

        # 如果没有最近项目
        if not recent_info:
            # 隐藏列表
            self.recent_list.hide()
            # 显示空状态标签
            self._empty_label.show()
            return

        # 显示列表
        self._empty_label.hide()
        self.recent_list.show()

        # 遍历最近项目信息
        for info in recent_info:
            # 构建显示文本：名称 + 路径 + 修改时间
            text = f"{info['name']}\n{info['path']}  —  {info['modified']}"
            # 创建列表项
            item = QListWidgetItem(text)
            # 存储项目路径到用户数据
            item.setData(Qt.UserRole, info["path"])
            # 设置工具提示为完整路径
            item.setToolTip(info["path"])
            # 添加到列表
            self.recent_list.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """列表项双击事件处理

        参数：
            item: 被双击的列表项
        """
        # 获取存储的项目路径
        path = item.data(Qt.UserRole)
        # 如果路径存在且文件存在
        if path and os.path.exists(path):
            # 发出项目打开请求信号
            self.project_open_requested.emit(path)
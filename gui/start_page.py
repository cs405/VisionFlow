"""Start page - welcome screen with recent projects and quick actions.

Shown when no project is open, with:
  - Logo / app title
  - New Project / Open Project buttons
  - Recent projects list with metadata
  - Click-to-open recent projects
"""

import os

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QListWidget, QListWidgetItem,
                              QFrame, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap


class StartPage(QWidget):
    """Welcome page with recent projects and quick actions.

    Signals:
      new_project_requested: user clicked "新建项目"
      open_project_requested: user clicked "打开项目"
      project_open_requested(str): user clicked a recent project path
    """

    new_project_requested = pyqtSignal()
    open_project_requested = pyqtSignal()
    project_open_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #1e1e1e;")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Center container
        center = QWidget()
        center.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center)
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setSpacing(16)

        # Spacer top
        center_layout.addStretch(2)

        # Logo / Title
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "logo.png")
        if os.path.exists(logo_path):
            logo = QLabel()
            logo.setAlignment(Qt.AlignCenter)
            logo.setPixmap(QPixmap(logo_path).scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo.setStyleSheet("background: transparent;")
            center_layout.addWidget(logo)

        title = QLabel("VisionFlow")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #0078d4; font-size: 32px; font-weight: bold; background: transparent;")
        center_layout.addWidget(title)

        subtitle = QLabel("视觉工作流编辑器")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #aaaaaa; font-size: 14px; background: transparent;")
        center_layout.addWidget(subtitle)

        version = QLabel("v2.0.0")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("color: #666666; font-size: 11px; background: transparent;")
        center_layout.addWidget(version)

        center_layout.addSpacing(24)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.setSpacing(12)

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

        new_btn = QPushButton("新建项目")
        new_btn.setStyleSheet(btn_style)
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.clicked.connect(self.new_project_requested.emit)
        btn_row.addWidget(new_btn)

        open_btn = QPushButton("打开项目...")
        open_btn.setStyleSheet(btn_style.replace("#0078d4", "#3e3e42"))
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(self.open_project_requested.emit)
        btn_row.addWidget(open_btn)

        center_layout.addLayout(btn_row)

        center_layout.addSpacing(32)

        # Recent projects section
        recent_label = QLabel("最近项目")
        recent_label.setAlignment(Qt.AlignCenter)
        recent_label.setStyleSheet("color: #888888; font-size: 12px; font-weight: bold; background: transparent;")
        center_layout.addWidget(recent_label)

        # Recent list
        self.recent_list = QListWidget()
        self.recent_list.setFixedSize(420, 200)
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
        self.recent_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        center_layout.addWidget(self.recent_list, alignment=Qt.AlignCenter)

        # Empty state hint
        self._empty_label = QLabel("暂无最近项目\n使用「打开项目」加载已有项目，或「新建项目」开始")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #666666; font-size: 12px; background: transparent;")
        self._empty_label.setFixedHeight(60)
        center_layout.addWidget(self._empty_label)
        self._empty_label.hide()

        # Spacer bottom
        center_layout.addStretch(3)

        layout.addWidget(center)

    def refresh_recent(self, project_service):
        """Refresh the recent projects list from project_service."""
        self.recent_list.clear()
        project_service.cleanup_recent_projects()
        recent_info = project_service.get_recent_projects_info()

        if not recent_info:
            self.recent_list.hide()
            self._empty_label.show()
            return

        self._empty_label.hide()
        self.recent_list.show()

        for info in recent_info:
            text = f"{info['name']}\n{info['path']}  —  {info['modified']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, info["path"])
            item.setToolTip(info["path"])
            self.recent_list.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path and os.path.exists(path):
            self.project_open_requested.emit(path)

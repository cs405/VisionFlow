"""Flow resource panel - image source file list with horizontal thumbnail view.

Ported from the bottom image source panel in MainWindow.xaml.
Displays source image file paths with navigation controls.
"""

import os

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                              QListWidgetItem, QPushButton, QLabel, QToolBar,
                              QCheckBox, QAction, QFileDialog)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QFont


class FlowResourcePanel(QWidget):
    """Bottom panel showing source image file list for the selected source node.

    Mirrors the WPF version:
      - Horizontal scrollable thumbnail list
      - Add/Remove/Clear file buttons
      - Auto-switch / Run-all toggle
      - Page left/right navigation
    """

    # Signals
    file_selected = pyqtSignal(str)       # Selected file path
    files_changed = pyqtSignal()          # File list changed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_node: "SrcFilesVisionNodeData | None" = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar with title and controls
        header = QHBoxLayout()
        header.setContentsMargins(8, 2, 8, 2)

        self.title_label = QLabel("图像源")
        self.title_label.setStyleSheet("color: #999; font-size: 11px; font-weight: bold;")
        header.addWidget(self.title_label)

        self.index_label = QLabel("0/0")
        self.index_label.setStyleSheet("color: #999; font-size: 11px;")
        header.addWidget(self.index_label)

        header.addStretch()

        # Run all checkbox
        self.run_all_cb = QCheckBox("运行全部")
        self.run_all_cb.setStyleSheet("color: #999; font-size: 11px;")
        self.run_all_cb.toggled.connect(self._on_run_all_toggled)
        header.addWidget(self.run_all_cb)

        # Auto switch checkbox
        self.auto_switch_cb = QCheckBox("自动切换")
        self.auto_switch_cb.setStyleSheet("color: #999; font-size: 11px;")
        self.auto_switch_cb.setChecked(True)
        self.auto_switch_cb.toggled.connect(self._on_auto_switch_toggled)
        header.addWidget(self.auto_switch_cb)

        # Toolbar buttons
        btn_style = """
            QPushButton {
                background: transparent;
                border: 1px solid #505050;
                border-radius: 2px;
                padding: 2px 8px;
                color: #dcdcdc;
                font-size: 11px;
            }
            QPushButton:hover { background: #3e3e42; }
        """

        add_file_btn = QPushButton("添加文件")
        add_file_btn.setStyleSheet(btn_style)
        add_file_btn.clicked.connect(self._add_files)
        header.addWidget(add_file_btn)

        add_folder_btn = QPushButton("添加文件夹")
        add_folder_btn.setStyleSheet(btn_style)
        add_folder_btn.clicked.connect(self._add_folder)
        header.addWidget(add_folder_btn)

        del_btn = QPushButton("删除")
        del_btn.setStyleSheet(btn_style)
        del_btn.clicked.connect(self._delete_current)
        header.addWidget(del_btn)

        clear_btn = QPushButton("清空")
        clear_btn.setStyleSheet(btn_style)
        clear_btn.clicked.connect(self._clear_files)
        header.addWidget(clear_btn)

        header_widget = QWidget()
        header_widget.setLayout(header)
        header_widget.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        layout.addWidget(header_widget)

        # Horizontal list widget
        self.file_list = QListWidget()
        self.file_list.setFlow(QListWidget.LeftToRight)  # Horizontal scroll
        self.file_list.setViewMode(QListWidget.ListMode)
        self.file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.file_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.file_list.setFixedHeight(90)
        self.file_list.setStyleSheet("""
            QListWidget {
                background: #1e1e1e;
                border: none;
                color: #dcdcdc;
            }
            QListWidget::item {
                width: 75px;
                padding: 2px;
            }
            QListWidget::item:selected {
                background: #094771;
            }
        """)
        self.file_list.currentItemChanged.connect(self._on_item_selected)
        layout.addWidget(self.file_list)

        # Navigation bar
        nav = QHBoxLayout()
        nav.setContentsMargins(4, 0, 4, 0)

        left_btn = QPushButton("<")
        left_btn.setFixedSize(30, 22)
        left_btn.setStyleSheet(btn_style)
        left_btn.clicked.connect(self._page_left)
        nav.addWidget(left_btn)

        nav.addStretch()

        right_btn = QPushButton(">")
        right_btn.setFixedSize(30, 22)
        right_btn.setStyleSheet(btn_style)
        right_btn.clicked.connect(self._page_right)
        nav.addWidget(right_btn)

        nav_widget = QWidget()
        nav_widget.setLayout(nav)
        nav_widget.setStyleSheet("background: #252526;")
        layout.addWidget(nav_widget)

    # -- Node binding --

    def set_node(self, node: "SrcFilesVisionNodeData | None"):
        """Bind to a source file node."""
        self._current_node = node
        self._refresh_list()

    def _refresh_list(self):
        """Reload the file list from the node."""
        self.file_list.clear()
        if self._current_node is None:
            self.title_label.setText("图像源")
            self.index_label.setText("0/0")
            return

        # Differentiate image vs video source
        is_video = "video" in type(self._current_node).__name__.lower()
        src_type = "视频源" if is_video else "图像源"
        self.title_label.setText(f"{src_type} - {self._current_node.name}")

        # Video file extensions
        VIDEO_EXTS = {'.avi', '.mp4', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}

        for path in self._current_node.src_file_paths:
            ext = os.path.splitext(path)[1].lower()
            is_vid = ext in VIDEO_EXTS
            display = f"{'🎬' if is_vid else '🖼'} {os.path.basename(path)}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, path)
            item.setToolTip(f"{'视频' if is_vid else '图像'}: {path}")
            self.file_list.addItem(item)

        total = len(self._current_node.src_file_paths)
        current_idx = 0
        if self._current_node.src_file_path:
            try:
                current_idx = self._current_node.src_file_paths.index(self._current_node.src_file_path) + 1
            except ValueError:
                pass
        self.index_label.setText(f"{current_idx}/{total}")

        # Select current item
        for i in range(self.file_list.count()):
            if self.file_list.item(i).data(Qt.UserRole) == self._current_node.src_file_path:
                self.file_list.setCurrentRow(i)
                break

        # Sync UI controls
        self.run_all_cb.blockSignals(True)
        self.run_all_cb.setChecked(self._current_node.use_all_image)
        self.run_all_cb.blockSignals(False)

        self.auto_switch_cb.blockSignals(True)
        self.auto_switch_cb.setChecked(self._current_node.use_auto_switch)
        self.auto_switch_cb.blockSignals(False)

    # -- Slots --

    def _on_item_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        if current and self._current_node:
            path = current.data(Qt.UserRole)
            if path:
                self._current_node.src_file_path = path
                self.file_selected.emit(path)

    def _on_run_all_toggled(self, checked: bool):
        if self._current_node:
            self._current_node.use_all_image = checked

    def _on_auto_switch_toggled(self, checked: bool):
        if self._current_node:
            self._current_node.use_auto_switch = checked

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图像文件", "",
            "图像文件 (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp);;所有文件 (*.*)"
        )
        if paths and self._current_node:
            self._current_node.add_files(paths)
            self._refresh_list()
            self.files_changed.emit()

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图像文件夹")
        if folder and self._current_node:
            self._current_node.add_files_from_folder(folder)
            self._refresh_list()
            self.files_changed.emit()

    def _delete_current(self):
        if self._current_node:
            self._current_node.delete_current_file()
            self._refresh_list()
            self.files_changed.emit()

    def _clear_files(self):
        if self._current_node:
            self._current_node.clear_files()
            self._refresh_list()
            self.files_changed.emit()

    def _page_left(self):
        """Scroll one page left."""
        sb = self.file_list.horizontalScrollBar()
        sb.setValue(sb.value() - self.file_list.viewport().width())

    def _page_right(self):
        """Scroll one page right."""
        sb = self.file_list.horizontalScrollBar()
        sb.setValue(sb.value() + self.file_list.viewport().width())

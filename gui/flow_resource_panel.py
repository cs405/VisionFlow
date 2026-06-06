"""Flow resource panel — WPF 图像源 Expander 1:1 port.

Ported from WPF MainWindow.xaml lines 302-413 (OpenCVSrcFilesNodeDataBase DataTemplate).

Layout (horizontal):
  ┌─────────────────────────────────────────────────┐
  │ 图像源 1/10   [运行全部] [自动切换] [文件][夹][删][清] │ ← header
  ├─────────────────────────────────────────────────┤
  │ ◀ │ [img1][img2][img3][img4]... │ ▶           │ ← thumbnail strip + page btns
  └─────────────────────────────────────────────────┘

Features:
  - 75×75 QPixmap thumbnails loaded asynchronously via QThread
  - Horizontal scrolling with Shift+wheel support
  - Page left/right floating navigation buttons (matches WPF FontIcons.PageLeft/PageRight)
  - Selection syncs to main image viewer
  - Double-click opens full-size zoom viewer
  - Toolbar: Add File / Add Folder / Delete / Clear + ToggleButtons
"""

import os
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
                              QPushButton, QLabel, QCheckBox, QFrame,
                              QFileDialog, QMessageBox, QSizePolicy, QGridLayout, QScrollBar)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QSize, QTimer, QPoint
from PyQt5.QtGui import QPixmap, QImage, QFont, QColor, QPainter

from gui.font_icons import FontIcons, FontIconButton, FontIconTextBlock

# ── Thumbnail constants matching WPF ───────────────────────────────────────

THUMB_SIZE = 75         # WPF: Width="75" Height="75"
THUMB_MARGIN = 2
STRIP_HEIGHT = 106      # 90 for list + top/bottom padding
PAGE_BTN_SIZE = 30       # WPF: FontSize="25" with margin


# ── Async thumbnail loader ────────────────────────────────────────────────

# Video file extensions (used for thumbnail detection)
VIDEO_EXTENSIONS = {'.avi', '.mp4', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}

class ThumbnailLoader(QThread):
    """Background thread for loading image/video thumbnails from file paths.

    For image files: loads and scales to 75×75.
    For video files: captures first frame and scales.
    """
    thumbnail_ready = pyqtSignal(str, QPixmap)   # file_path, pixmap

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths: list[str] = []
        self._running = True

    def set_paths(self, paths: list[str]):
        self._paths = list(paths)

    def stop(self):
        self._running = False

    def run(self):
        for path in self._paths:
            if not self._running:
                break
            try:
                ext = os.path.splitext(path)[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    img = self._capture_video_frame(path)
                else:
                    img = cv2.imread(path, cv2.IMREAD_COLOR)

                if img is None:
                    continue
                h, w = img.shape[:2]
                # Scale to fit 75x75, maintaining aspect ratio
                scale = min(THUMB_SIZE / max(w, 1), THUMB_SIZE / max(h, 1))
                if scale < 1.0:
                    new_w, new_h = int(w * scale), int(h * scale)
                    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

                # Convert BGR → RGB → QImage → QPixmap
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)

                self.thumbnail_ready.emit(path, pixmap)
            except Exception:
                continue

    def _capture_video_frame(self, path: str) -> np.ndarray | None:
        """Capture first frame of a video file as thumbnail."""
        try:
            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                return None
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                # Add small "▶" overlay indicator for videos
                return frame
            return None
        except Exception:
            return None


# ── Thumbnail widget ──────────────────────────────────────────────────────

class ThumbnailButton(QPushButton):
    """Clickable 75×75 thumbnail matching WPF Image item template."""

    clicked_with_path = pyqtSignal(str)
    double_clicked_path = pyqtSignal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._pixmap: QPixmap | None = None
        self._selected = False

        self.setFixedSize(THUMB_SIZE + 6, THUMB_SIZE + 6)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(file_path)
        self.setStyleSheet("""
            ThumbnailButton {
                background: #2d2d30;
                border: 2px solid #3f3f46;
                border-radius: 2px;
                padding: 2px;
            }
            ThumbnailButton:hover {
                border-color: #0078d4;
                background: #3e3e42;
            }
            ThumbnailButton[selected="true"] {
                border-color: #0078d4;
                background: #094771;
            }
        """)

        self.clicked.connect(lambda: self.clicked_with_path.emit(self.file_path))

    def set_thumbnail(self, pixmap: QPixmap):
        """Set the loaded thumbnail pixmap."""
        self._pixmap = pixmap
        self.update()

    def set_selected(self, selected: bool):
        self._selected = selected
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._pixmap and not self._pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            # Center the scaled pixmap in the button
            pw, ph = self._pixmap.width(), self._pixmap.height()
            x = (self.width() - pw) // 2
            y = (self.height() - ph) // 2
            painter.drawPixmap(x, y, self._pixmap)
        else:
            # Draw placeholder
            painter = QPainter(self)
            painter.setPen(QColor("#555"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(self.rect(), Qt.AlignCenter, "...")

    def mouseDoubleClickEvent(self, event):
        self.double_clicked_path.emit(self.file_path)
        event.accept()


# ═══════════════════════════════════════════════════════════════════════════
# Main panel
# ═══════════════════════════════════════════════════════════════════════════

class FlowResourcePanel(QWidget):
    """WPF-aligned image source panel with thumbnail strip.

    Mirrors the WPF MainWindow.xaml bottom image source area:
      - Header: title + index + toolbar buttons + toggles
      - Body: horizontal scrollable 75×75 thumbnail strip
      - Page left/right overlay navigation buttons
      - Async thumbnail loading

    Signals:
        file_selected(str) — emitted when a thumbnail is clicked (= selected)
        file_double_clicked(str) — emitted for full-size zoom viewer
        files_changed() — emitted after add/remove/clear operations
    """

    file_selected = pyqtSignal(str)
    file_double_clicked = pyqtSignal(str)
    files_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_node: "SrcFilesVisionNodeData | None" = None
        self._thumbnails: dict[str, ThumbnailButton] = {}
        self._pixmaps: dict[str, QPixmap] = {}
        self._loader: ThumbnailLoader | None = None
        self._selected_path: str = ""

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header bar ──
        header = QWidget()
        header.setFixedHeight(34)
        header.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 4, 6, 4)
        h_layout.setSpacing(4)

        # Title + index
        self._title_label = QLabel("图像源")
        self._title_label.setStyleSheet("color: #dcdcdc; font-size: 11px; font-weight: bold; background: transparent;")
        h_layout.addWidget(self._title_label)

        self._index_label = QLabel("0/0")
        self._index_label.setStyleSheet("color: #999; font-size: 11px; background: transparent;")
        h_layout.addWidget(self._index_label)

        h_layout.addStretch(1)

        # Toggle buttons (matching WPF ToggleButton style)
        toggle_style = """
            QPushButton {
                background: transparent; border: 1px solid #505050; border-radius: 2px;
                padding: 3px 8px; color: #999; font-size: 11px;
            }
            QPushButton:hover { background: #3e3e42; color: #dcdcdc; }
            QPushButton:checked { background: #094771; color: #dcdcdc; border-color: #0078d4; }
        """

        self._run_all_btn = QPushButton("运行全部")
        self._run_all_btn.setCheckable(True)
        self._run_all_btn.setStyleSheet(toggle_style)
        self._run_all_btn.setFixedHeight(24)
        self._run_all_btn.toggled.connect(self._on_run_all_toggled)
        h_layout.addWidget(self._run_all_btn)

        self._auto_switch_btn = QPushButton("自动切换")
        self._auto_switch_btn.setCheckable(True)
        self._auto_switch_btn.setChecked(True)
        self._auto_switch_btn.setStyleSheet(toggle_style)
        self._auto_switch_btn.setFixedHeight(24)
        self._auto_switch_btn.toggled.connect(self._on_auto_switch_toggled)
        h_layout.addWidget(self._auto_switch_btn)

        # Toolbar separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("background: #505050;")
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        h_layout.addWidget(sep)

        # FontIcon action buttons (WPF: AddImageData / AddImageDatas / DeleteImageData / ClearImageDatas commands)
        btn_style = """
            QPushButton {
                background: transparent; border: 1px solid transparent; border-radius: 3px;
                color: #dcdcdc; padding: 2px 6px; font-size: 13px;
            }
            QPushButton:hover { background: #3e3e42; border-color: #505050; }
            QPushButton:disabled { color: #666; background: transparent; }
        """

        self._add_file_btn = FontIconButton(FontIcons.OpenFile, tooltip="添加文件", font_size=13)
        self._add_file_btn.setStyleSheet(btn_style)
        self._add_file_btn.clicked.connect(self._add_files)
        h_layout.addWidget(self._add_file_btn)

        self._add_folder_btn = FontIconButton(FontIcons.OpenFolderHorizontal, tooltip="添加文件夹", font_size=13)
        self._add_folder_btn.setStyleSheet(btn_style)
        self._add_folder_btn.clicked.connect(self._add_folder)
        h_layout.addWidget(self._add_folder_btn)

        self._del_btn = FontIconButton(FontIcons.Cancel, tooltip="删除", font_size=13)
        self._del_btn.setStyleSheet(btn_style)
        self._del_btn.clicked.connect(self._delete_current)
        self._del_btn.setEnabled(False)  # WPF: CanExecute → disabled when no files
        h_layout.addWidget(self._del_btn)

        self._clear_btn = FontIconButton(FontIcons.Delete, tooltip="清空", font_size=13)
        self._clear_btn.setStyleSheet(btn_style)
        self._clear_btn.clicked.connect(self._clear_files)
        self._clear_btn.setEnabled(False)  # WPF: CanExecute → disabled when no files
        h_layout.addWidget(self._clear_btn)

        layout.addWidget(header)

        # ── Thumbnail strip with overlay page buttons ──
        strip_container = QFrame()
        strip_container.setFrameShape(QFrame.NoFrame)
        strip_container.setStyleSheet("background: #1e1e1e;")
        strip_layout = QVBoxLayout(strip_container)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(0)

        # Scroll area holding thumbnails
        self._scroll_area = QScrollArea()
        self._scroll_area.setFixedHeight(THUMB_SIZE + 14)
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setStyleSheet("""
            QScrollArea { background: #1e1e1e; border: none; }
            QScrollBar:horizontal {
                background: #2d2d30; height: 10px;
            }
            QScrollBar::handle:horizontal {
                background: #505050; border-radius: 3px; min-width: 30px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        # Allow horizontal scroll with Shift+wheel (WPF: ScrollViewerBebavior UseHorizontalMouseWheel)
        self._scroll_area.wheelEvent = self._scroll_wheel_event

        # Thumbnail container widget
        self._thumb_container = QWidget()
        self._thumb_layout = QHBoxLayout(self._thumb_container)
        self._thumb_layout.setContentsMargins(36, 4, 36, 4)  # space for page buttons
        self._thumb_layout.setSpacing(2)
        self._thumb_layout.addStretch(1)

        self._scroll_area.setWidget(self._thumb_container)
        strip_layout.addWidget(self._scroll_area)

        # ── Page navigation overlay buttons ──
        # Left page button (floating on left edge)
        self._page_left_btn = QPushButton(FontIcons.PageLeft)
        self._page_left_btn.setFont(QFont("Segoe Fluent Icons", 14))
        self._page_left_btn.setFixedSize(PAGE_BTN_SIZE, PAGE_BTN_SIZE)
        self._page_left_btn.setCursor(Qt.PointingHandCursor)
        self._page_left_btn.setStyleSheet("""
            QPushButton {
                background: rgba(45, 45, 48, 0.85); border: 1px solid #505050;
                border-radius: 3px; color: #dcdcdc;
            }
            QPushButton:hover { background: #3e3e42; border-color: #0078d4; }
        """)
        self._page_left_btn.clicked.connect(self._page_left)

        # Right page button (floating on right edge)
        self._page_right_btn = QPushButton(FontIcons.PageRight)
        self._page_right_btn.setFont(QFont("Segoe Fluent Icons", 14))
        self._page_right_btn.setFixedSize(PAGE_BTN_SIZE, PAGE_BTN_SIZE)
        self._page_right_btn.setCursor(Qt.PointingHandCursor)
        self._page_right_btn.setStyleSheet("""
            QPushButton {
                background: rgba(45, 45, 48, 0.85); border: 1px solid #505050;
                border-radius: 3px; color: #dcdcdc;
            }
            QPushButton:hover { background: #3e3e42; border-color: #0078d4; }
        """)
        self._page_right_btn.clicked.connect(self._page_right)

        # Overlay the page buttons on the scroll area
        # Use absolute positioning within strip_container
        self._page_left_btn.setParent(self._scroll_area)
        self._page_left_btn.move(4, (self._scroll_area.height() - PAGE_BTN_SIZE) // 2)
        self._page_left_btn.show()

        self._page_right_btn.setParent(self._scroll_area)
        self._page_right_btn.move(
            self._scroll_area.width() - PAGE_BTN_SIZE - 4,
            (self._scroll_area.height() - PAGE_BTN_SIZE) // 2,
        )
        self._page_right_btn.show()

        layout.addWidget(strip_container)
        self.setFixedHeight(STRIP_HEIGHT + 34)

    # ── Scroll with Shift+wheel (WPF behavior) ──────────────────────────

    def _scroll_wheel_event(self, event):
        """Override QScrollArea wheelEvent: Shift+wheel → horizontal scroll."""
        if event.modifiers() & Qt.ShiftModifier:
            delta = event.angleDelta().y()
            bar = self._scroll_area.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
            event.accept()
        else:
            QScrollArea.wheelEvent(self._scroll_area, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reposition page buttons
        if hasattr(self, '_page_right_btn'):
            self._page_right_btn.move(
                self._scroll_area.width() - PAGE_BTN_SIZE - 4,
                (self._scroll_area.height() - PAGE_BTN_SIZE) // 2,
            )

    # ── Page navigation ─────────────────────────────────────────────────

    def _page_left(self):
        bar = self._scroll_area.horizontalScrollBar()
        bar.setValue(bar.value() - self._scroll_area.viewport().width())

    def _page_right(self):
        bar = self._scroll_area.horizontalScrollBar()
        bar.setValue(bar.value() + self._scroll_area.viewport().width())

    # ── Node binding ────────────────────────────────────────────────────

    def set_node(self, node: "SrcFilesVisionNodeData | None"):
        """Bind to a source file node and load its thumbnails."""
        self._stop_loader()
        self._current_node = node
        self._clear_thumbnails()
        self._build_thumbnails()   # create buttons first, then load images
        self._refresh_header()

        if node is None:
            return

        paths = getattr(node, 'src_file_paths', []) or []
        if not paths:
            return

        # Start async loading — buttons already exist, pixmaps will fill in
        self._loader = ThumbnailLoader(self)
        self._loader.set_paths(paths)
        self._loader.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._loader.start()

    def _stop_loader(self):
        if self._loader and self._loader.isRunning():
            self._loader.stop()
            self._loader.wait(1000)
        self._loader = None

    def _on_thumbnail_ready(self, file_path: str, pixmap: QPixmap):
        """Receive a loaded thumbnail from the background thread."""
        self._pixmaps[file_path] = pixmap
        btn = self._thumbnails.get(file_path)
        if btn:
            btn.set_thumbnail(pixmap)

    def _refresh_header(self):
        """Update header title, index, toggle state, and action button states.

        WPF: bindings auto-refresh all UI elements.
        VisionFlow: explicit refresh call.
        """
        node = self._current_node
        if node is None:
            self._title_label.setText("图像源")
            self._index_label.setText("0/0")
            self._run_all_btn.blockSignals(True)
            self._run_all_btn.setChecked(False)
            self._run_all_btn.blockSignals(False)
            self._auto_switch_btn.blockSignals(True)
            self._auto_switch_btn.setChecked(False)
            self._auto_switch_btn.blockSignals(False)
            self._update_action_buttons()
            return

        is_video = "video" in type(node).__name__.lower()
        self._title_label.setText("视频源" if is_video else "图像源")

        paths = getattr(node, 'src_file_paths', []) or []
        current = getattr(node, 'src_file_path', '')
        total = len(paths)
        idx = 0
        if current and current in paths:
            idx = paths.index(current) + 1

        # Show file size for current file (WPF: [12.3 MB] filename)
        size_text = ""
        if current and os.path.exists(current):
            try:
                size = os.path.getsize(current)
                size_text = f"[{size / 1024 / 1024:.1f} MB]" if size >= 1024 * 1024 else f"[{size / 1024:.1f} KB]"
            except OSError:
                pass
        self._index_label.setText(f"{idx}/{total}  {size_text}")

        self._run_all_btn.blockSignals(True)
        self._run_all_btn.setChecked(getattr(node, 'use_all_image', False))
        self._run_all_btn.blockSignals(False)

        self._auto_switch_btn.blockSignals(True)
        self._auto_switch_btn.setChecked(getattr(node, 'use_auto_switch', True))
        self._auto_switch_btn.blockSignals(False)

        self._update_action_buttons()

    def _clear_thumbnails(self):
        """Remove all thumbnail buttons and cached pixmaps."""
        for btn in list(self._thumbnails.values()):
            btn.deleteLater()
        self._thumbnails.clear()
        self._pixmaps.clear()
        # Keep only the stretch item
        while self._thumb_layout.count() > 1:
            item = self._thumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._selected_path = ""

    def _build_thumbnails(self):
        """Create thumbnail buttons for all file paths."""
        node = self._current_node
        if node is None:
            return

        paths = getattr(node, 'src_file_paths', []) or []
        current = getattr(node, 'src_file_path', '')

        for path in paths:
            btn = ThumbnailButton(path)
            btn.clicked_with_path.connect(self._on_thumbnail_clicked)
            btn.double_clicked_path.connect(self.file_double_clicked.emit)

            # Apply already-loaded pixmap
            if path in self._pixmaps:
                btn.set_thumbnail(self._pixmaps[path])

            if path == current:
                btn.set_selected(True)
                self._selected_path = path

            # Insert before the stretch
            self._thumb_layout.insertWidget(self._thumb_layout.count() - 1, btn)
            self._thumbnails[path] = btn

        # Re-drop the stretch at end
        self._thumb_layout.addStretch(1)

    # ── Interaction ─────────────────────────────────────────────────────

    def _on_thumbnail_clicked(self, file_path: str):
        """Handle thumbnail selection."""
        if self._current_node and hasattr(self._current_node, 'src_file_path'):
            self._current_node.src_file_path = file_path

        # Update selection highlight
        self._selected_path = file_path
        for path, btn in self._thumbnails.items():
            btn.set_selected(path == file_path)

        self._refresh_header()
        self.file_selected.emit(file_path)

    def _on_run_all_toggled(self, checked: bool):
        if self._current_node:
            self._current_node.use_all_image = checked

    def _on_auto_switch_toggled(self, checked: bool):
        if self._current_node:
            self._current_node.use_auto_switch = checked

    # ── File operations (WPF-aligned) ────────────────────────────────────

    # Image file filter — WPF: ShowOpenImageFiles() internal filter
    IMAGE_FILTER = "图像文件 (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp);;所有文件 (*.*)"
    IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp")

    def _add_files(self):
        """WPF AddImageDataCommand → AddFile() → IOFileDialog.ShowOpenImageFiles().

        Decoupled: QFileDialog is used here (GUI layer), but node.add_files()
        remains pure data operation. The node doesn't know about Qt.
        """
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图像文件", "", self.IMAGE_FILTER
        )
        if not paths or not self._current_node:
            return
        had_existing = bool(self._current_node.src_file_paths)
        self._current_node.add_files(list(paths))

        # WPF: add files → binding auto-refreshes ListBox
        # VisionFlow: incremental thumbnail build + header refresh
        self._add_thumbnails_incremental(list(paths))
        self._refresh_header()
        self._update_action_buttons()

        # WPF: auto-select first file if none was selected
        if not had_existing:
            first = self._current_node.src_file_path
            self._selected_path = first
            self.file_selected.emit(first)

        self.files_changed.emit()

    def _add_folder(self):
        """WPF AddImageDatasCommand → AddFiles() → IOFolderDialog.ShowOpenFolderAction().

        WPF implementation details:
          - selectedFolderPath.GetAllImages()  →  recursive scan via DirectoryEx.GetAllFiles()
          - SrcFilePaths.AddRange(images)       →  batch add
          - Skips hidden & system files         →  !HasFlag(Hidden|System)
          - Supported extensions: jpg jpeg png gif pdf tga tif svg bmp dds eps webp

        VisionFlow: delegates to node.add_files_from_folder(recursive=True) which
        mirrors WPF's recursive GetAllFiles + IsImage filtering.
        """
        folder = QFileDialog.getExistingDirectory(self, "选择图像文件夹")
        if not folder or not self._current_node:
            return

        had_existing = bool(self._current_node.src_file_paths)
        old_count = len(self._current_node.src_file_paths)

        # WPF: selectedFolderPath.GetAllImages() → recursive + hidden-filtered
        self._current_node.add_files_from_folder(folder, recursive=True)

        new_count = len(self._current_node.src_file_paths)
        added = new_count - old_count
        if added == 0:
            return

        # Determine which paths are new (those just appended)
        new_paths = self._current_node.src_file_paths[old_count:]

        # WPF: binding auto-refreshes ItemsControl
        # VisionFlow: incremental thumbnail build for added files only
        self._add_thumbnails_incremental(new_paths)
        self._refresh_header()
        self._update_action_buttons()

        if not had_existing and self._current_node.src_file_path:
            self._selected_path = self._current_node.src_file_path
            self.file_selected.emit(self._current_node.src_file_path)

        self.files_changed.emit()

    def _delete_current(self):
        """WPF DeleteImageDataCommand → ShowDeleteDialog → Remove + select adjacent.

        Shows confirmation dialog before removing the current file.
        WPF: int index = SrcFilePaths.IndexOf(SrcFilePath)
             SrcFilePaths.Remove(SrcFilePath)
             SrcFilePath = find ?? SrcFilePaths.FirstOrDefault()
        """
        if not self._current_node:
            return
        current = self._current_node.src_file_path
        if not current:
            return

        # WPF: IocMessage.Dialog.ShowDeleteDialog() — confirmation
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除当前图像吗？\n{os.path.basename(current)}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._current_node.delete_current_file()

        # Remove thumbnail button (incremental delete, no full rebuild)
        btn = self._thumbnails.pop(current, None)
        if btn:
            self._thumb_layout.removeWidget(btn)
            btn.deleteLater()
        self._pixmaps.pop(current, None)

        self._refresh_header()
        self._update_action_buttons()
        self.files_changed.emit()

        # Emit selection for the newly selected adjacent file
        new_current = self._current_node.src_file_path
        if new_current:
            self._selected_path = new_current
            self.file_selected.emit(new_current)

    def _clear_files(self):
        """WPF ClearImageDatasCommand → ShowDeleteAllDialog → SrcFilePaths.Clear().

        Shows confirmation before clearing all files.
        WPF CanExecute: requires SrcFilePaths.Count > 0.
        """
        if not self._current_node:
            return
        count = len(self._current_node.src_file_paths)
        if count == 0:
            return

        # WPF: IocMessage.Dialog.ShowDeleteAllDialog() — confirmation
        reply = QMessageBox.question(
            self, "确认清空",
            f"确定要清空所有图像文件吗？\n当前共有 {count} 个文件",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._current_node.clear_files()

        # Clear all thumbnails
        self._clear_thumbnails()
        self._refresh_header()
        self._update_action_buttons()
        self._selected_path = ""
        self.files_changed.emit()

    # ── Incremental thumbnail builder (WPF binding auto-update equivalent) ─

    def _add_thumbnails_incremental(self, new_paths: list[str]):
        """Add new thumbnail buttons without rebuilding existing ones.

        WPF: data binding auto-refreshes the ItemsControl when SrcFilePaths changes.
        VisionFlow: must explicitly create buttons for new files only.
        """
        for path in new_paths:
            if path in self._thumbnails:
                continue  # already exists
            btn = ThumbnailButton(path)
            btn.clicked_with_path.connect(self._on_thumbnail_clicked)
            btn.double_clicked_path.connect(self.file_double_clicked.emit)

            if path in self._pixmaps:
                btn.set_thumbnail(self._pixmaps[path])

            # Insert before the stretch
            stretch_idx = self._thumb_layout.count() - 1
            self._thumb_layout.insertWidget(max(stretch_idx, 0), btn)
            self._thumbnails[path] = btn

        # Ensure stretch is at end
        if not self._thumb_layout.itemAt(self._thumb_layout.count() - 1) or \
           self._thumb_layout.itemAt(self._thumb_layout.count() - 1).widget() is not None:
            self._thumb_layout.addStretch(1)

        # Start async loading for new paths only
        if new_paths:
            loader = ThumbnailLoader(self)
            loader.set_paths(new_paths)
            loader.thumbnail_ready.connect(self._on_thumbnail_ready)
            loader.start()

    # ── Button state management (WPF CanExecute equivalent) ──────────────

    def _update_action_buttons(self):
        """Enable/disable delete & clear buttons based on file list state.

        WPF:
          ClearImageDatasCommand.CanExecute → this.SrcFilePaths?.Count > 0
          DeleteImageDataCommand — always available if node is set
        """
        node = self._current_node
        has_files = node is not None and len(getattr(node, 'src_file_paths', []) or []) > 0
        has_selection = bool(getattr(node, 'src_file_path', '') if node else '')
        self._del_btn.setEnabled(has_files and has_selection)
        self._clear_btn.setEnabled(has_files)

    # ── Public API ──────────────────────────────────────────────────────

    def refresh(self):
        """Force full refresh of thumbnails from current node."""
        self._stop_loader()
        self._clear_thumbnails()
        self._build_thumbnails()
        self._refresh_header()

        node = self._current_node
        if node is None:
            return
        paths = getattr(node, 'src_file_paths', []) or []
        if paths:
            self._loader = ThumbnailLoader(self)
            self._loader.set_paths(paths)
            self._loader.thumbnail_ready.connect(self._on_thumbnail_ready)
            self._loader.start()

    def refresh_selection(self):
        """Lightweight refresh — update header index + thumbnail highlight only.

        WPF "自动切换" equivalent: during "运行全部", when UseAutoSwitch=ON,
        the SrcFilePath binding causes the thumbnail ListBox to update its
        selected item automatically. In VisionFlow, we call this explicitly
        from the FILE_ITERATION_NEXT event handler when auto_switch is ON.
        """
        node = self._current_node
        if node is None:
            return

        current = getattr(node, 'src_file_path', '')
        # Update header index/filename
        self._refresh_header()

        # Update thumbnail selection highlight (WPF: SelectedItem="{Binding SrcFilePath}")
        for path, btn in self._thumbnails.items():
            btn.set_selected(path == current)

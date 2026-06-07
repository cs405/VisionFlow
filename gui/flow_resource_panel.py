"""Flow resource panel —  图像源 Expander 1:1 port.

Layout (horizontal):
  ┌─────────────────────────────────────────────────┐
  │ 图像源 1/10   [运行全部] [自动切换] [文件][夹][删][清] │ ← header
  ├─────────────────────────────────────────────────┤
  │ ◀ │ [img1][img2][img3][img4]... │ ▶             │ ← thumbnail strip + page btns
  └─────────────────────────────────────────────────┘

Features:
  - 75×75 QPixmap thumbnails loaded asynchronously via QThread
  - Horizontal scrolling with Shift+wheel support
  - Page left/right floating navigation buttons
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

from gui.font_icons import FontIcons, FontIconButton, FontIconTextBlock, ICON_FONT_FAMILY
from gui.theme import theme_manager, connect_theme

# ═══════════════════════════════════════════════════════════════════════════
# Architecture summary (ported from WPF MainWindow.xaml lines 355-502):
#
# Thumbnail strip — 9 WPF features → VisionFlow equivalents:
#   1. VirtualizingStackPanel   → all ThumbnailButtons created upfront (>100: known limit)
#   2. Focusable="false"        → QScrollArea.setFocusPolicy(Qt.NoFocus)
#   3. UseHorizontalMouseWheel  → _scroll_wheel_event (Shift+wheel)
#   4. ItemTemplate + Converter → ThumbnailLoader async QThread
#   5. PageLeft/PageRight       → _page_left_btn / _page_right_btn overlay
#   6. SelectionChanged         → _on_thumbnail_clicked → file_selected signal
#   7. MouseDoubleClick         → double_clicked_path signal → zoom viewer
#   8. Header index "1/10"      → _refresh_header() manual calc
#   9. ToolTip="{Binding}"      → setToolTip(file_path)
#
# Single-step navigation ("上一张"/"下一张"):
#   - _step_left_btn / _step_right_btn → _step_left() / _step_right()
#   - calls node.move_prev() / node.move_next()
#   - use_all_image=False blocks wrap-around (node returns False at bounds)
#
# Page navigation ("上一页"/"下一页"):
#   - _page_left_btn / _page_right_btn → _page_left() / _page_right()
#   - scrolls thumbnail strip by one viewport width, overlay on QScrollArea
# ═══════════════════════════════════════════════════════════════════════════

# ── Thumbnail constants matching  ───────────────────────────────────────

THUMB_SIZE = 75
THUMB_MARGIN = 2
STRIP_HEIGHT = 106      # 90 for list + top/bottom padding
PAGE_BTN_SIZE = 40


# ── Async thumbnail loader ────────────────────────────────────────────────

# Video file extensions (used for thumbnail detection)
VIDEO_EXTENSIONS = {'.avi', '.mp4', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}

class ThumbnailLoader(QThread):
    """Background thread for loading image/video thumbnails from file paths.

    For image files: loads and scales to 75×75.
    For video files: captures first frame and scales.

    Emits QImage (not QPixmap) for thread safety — QPixmap must only be
    created in the GUI thread because its Windows GDI handles are thread-affine.
    """
    thumbnail_ready = pyqtSignal(str, QImage)   # file_path, qimage (thread-safe)

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

                # Convert BGR → RGB → QImage (deep copy for thread safety)
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()

                self.thumbnail_ready.emit(path, qimg)
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
    """Clickable 75×75 thumbnail

    Colors follow theme via connect_theme
    """

    clicked_with_path = pyqtSignal(str)
    double_clicked_path = pyqtSignal(str)

    # Theme QSS template — regenerated when theme changes
    THEME_QSS = """
        ThumbnailButton {{
            background: {bg_normal}; border: 2px solid {border_normal}; border-radius: 2px; padding: 2px;
        }}
        ThumbnailButton:hover {{
            border-color: {accent}; background: {bg_hover};
        }}
        ThumbnailButton[selected="true"] {{
            border-color: {accent}; background: {bg_selected};
        }}
    """

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._pixmap: QPixmap | None = None
        self._selected = False

        self.setFixedSize(THUMB_SIZE + 6, THUMB_SIZE + 6)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(file_path)

        from gui.theme import theme_manager as _tm
        self._theme_manager = _tm
        self._refresh_qss()
        self._theme_manager.theme_changed.connect(lambda _: self._refresh_qss())

        self.clicked.connect(lambda: self.clicked_with_path.emit(self.file_path))

    def _refresh_qss(self):
        tm = self._theme_manager
        self.setStyleSheet(self.THEME_QSS.format(
            bg_normal=tm.color("bg_surface_raised").name(),
            border_normal=tm.color("border").name(),
            accent=tm.color("accent").name(),
            bg_hover=tm.color("bg_surface_hover").name(),
            bg_selected=tm.color("bg_surface_input").name(),
        ))

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
            pw, ph = self._pixmap.width(), self._pixmap.height()
            x = (self.width() - pw) // 2
            y = (self.height() - ph) // 2
            painter.drawPixmap(x, y, self._pixmap)
        else:
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
    """aligned image source panel with thumbnail strip.

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
        self._header_bar = QWidget()
        self._header_bar.setFixedHeight(34)
        h_layout = QHBoxLayout(self._header_bar)
        h_layout.setContentsMargins(8, 4, 6, 4)
        h_layout.setSpacing(4)

        # Title + index
        self._title_label = QLabel("图像源")
        self._title_label.setStyleSheet("font-size: 11px; font-weight: bold; background: transparent;")
        h_layout.addWidget(self._title_label)

        self._index_label = QLabel("0/0")
        self._index_label.setStyleSheet("font-size: 11px; background: transparent;")
        h_layout.addWidget(self._index_label)

        h_layout.addStretch(1)

        # Toggle buttons
        self._run_all_btn = QPushButton("运行全部")
        self._run_all_btn.setCheckable(True)
        self._run_all_btn.setFixedHeight(24)
        self._run_all_btn.setFocusPolicy(Qt.NoFocus)
        self._run_all_btn.toggled.connect(self._on_run_all_toggled)
        h_layout.addWidget(self._run_all_btn)

        self._auto_switch_btn = QPushButton("自动切换")
        self._auto_switch_btn.setCheckable(True)
        self._auto_switch_btn.setChecked(True)
        self._auto_switch_btn.setFixedHeight(24)
        self._auto_switch_btn.setFocusPolicy(Qt.NoFocus)
        self._auto_switch_btn.toggled.connect(self._on_auto_switch_toggled)
        h_layout.addWidget(self._auto_switch_btn)

        # Toolbar separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("background: #505050;")
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        h_layout.addWidget(sep)

        # FontIcon action buttons
        # QSS regenerated in _refresh_header_qss(); initial style set here
        self._add_file_btn = FontIconButton(FontIcons.OpenFile, tooltip="添加文件", font_size=13)
        self._add_file_btn.clicked.connect(self._add_files)
        h_layout.addWidget(self._add_file_btn)

        self._add_folder_btn = FontIconButton(FontIcons.OpenFolderHorizontal, tooltip="添加文件夹", font_size=13)
        self._add_folder_btn.clicked.connect(self._add_folder)
        h_layout.addWidget(self._add_folder_btn)

        self._del_btn = FontIconButton(FontIcons.Cancel, tooltip="删除", font_size=13)
        self._del_btn.clicked.connect(self._delete_current)
        self._del_btn.setEnabled(False)
        h_layout.addWidget(self._del_btn)

        self._clear_btn = FontIconButton(FontIcons.Delete, tooltip="清空", font_size=13)
        self._clear_btn.clicked.connect(self._clear_files)
        self._clear_btn.setEnabled(False)
        h_layout.addWidget(self._clear_btn)

        # Step navigation separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("background: #505050;")
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(20)
        h_layout.addWidget(sep2)

        # Single-step navigation — "上一张" / "下一张"
        self._step_left_btn = FontIconButton(FontIcons.ChevronLeft, tooltip="上一张", font_size=14)
        self._step_left_btn.clicked.connect(self._step_left)
        self._step_left_btn.setEnabled(False)
        h_layout.addWidget(self._step_left_btn)

        self._step_right_btn = FontIconButton(FontIcons.ChevronRight, tooltip="下一张", font_size=14)
        self._step_right_btn.clicked.connect(self._step_right)
        self._step_right_btn.setEnabled(False)
        h_layout.addWidget(self._step_right_btn)

        layout.addWidget(self._header_bar)

        # ── Thumbnail strip with overlay page buttons ──
        self._strip_container = QFrame()
        self._strip_container.setFrameShape(QFrame.NoFrame)
        strip_layout = QVBoxLayout(self._strip_container)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(0)

        # Scroll area holding thumbnails
        # Qt: setWidgetResizable(True) fills viewport height; minimumSize controls width
        self._scroll_area = QScrollArea()
        self._scroll_area.setFixedHeight(THUMB_SIZE + 14)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setFocusPolicy(Qt.NoFocus)

        # Allow horizontal scroll with Shift+wheel
        self._scroll_area.wheelEvent = self._scroll_wheel_event

        # Thumbnail container widget
        self._thumb_container = QWidget()
        self._thumb_layout = QHBoxLayout(self._thumb_container)
        self._thumb_layout.setContentsMargins(36, 4, 36, 4)  # space for page buttons
        self._thumb_layout.setSpacing(2)
        self._thumb_layout.setAlignment(Qt.AlignLeft)
        # stretch is NOT added here — stretch inside QScrollArea would compress thumbnails

        self._scroll_area.setWidget(self._thumb_container)
        strip_layout.addWidget(self._scroll_area)

        # ── Page navigation overlay ──
        # Font rendered via QSS font-family (setStyleSheet overrides setFont)
        self._page_left_btn = QPushButton(FontIcons.PageLeft)
        self._page_left_btn.setFixedSize(PAGE_BTN_SIZE, PAGE_BTN_SIZE)
        self._page_left_btn.setCursor(Qt.PointingHandCursor)
        self._page_left_btn.setFocusPolicy(Qt.NoFocus)
        self._page_left_btn.setToolTip("上一页")
        self._page_left_btn.clicked.connect(self._page_left)

        self._page_right_btn = QPushButton(FontIcons.PageRight)
        self._page_right_btn.setFixedSize(PAGE_BTN_SIZE, PAGE_BTN_SIZE)
        self._page_right_btn.setCursor(Qt.PointingHandCursor)
        self._page_right_btn.setFocusPolicy(Qt.NoFocus)
        self._page_right_btn.setToolTip("下一页")
        self._page_right_btn.clicked.connect(self._page_right)

        # Overlay page buttons on scroll area
        self._page_left_btn.setParent(self._scroll_area)
        self._page_left_btn.move(2, (self._scroll_area.height() - PAGE_BTN_SIZE) // 2)
        self._page_left_btn.show()

        self._page_right_btn.setParent(self._scroll_area)
        QTimer.singleShot(100, self._reposition_page_buttons)  # wait for layout
        self._page_right_btn.show()

        # Theme-aware styling
        connect_theme(self._refresh_all_qss)

        layout.addWidget(self._strip_container)
        self.setFixedHeight(STRIP_HEIGHT + 34)

    def _refresh_all_qss(self):
        """Update all hardcoded colors to current theme"""
        tm = theme_manager
        bg_raised = tm.color("bg_surface_raised").name()
        bg_deep = tm.color("bg_surface_deep").name()
        bg_hover = tm.color("bg_surface_hover").name()
        border = tm.color("border").name()
        accent = tm.color("accent").name()
        text = tm.color("text_primary").name()
        text_secondary = tm.color("text_secondary").name()
        text_title = tm.color("text_title").name()

        # ── Header bar ──
        self._header_bar.setStyleSheet(
            f"background: {bg_raised}; border-bottom: 1px solid {border};"
        )
        self._title_label.setStyleSheet(
            f"color: {text_title}; font-size: 11px; font-weight: bold; background: transparent;"
        )
        self._index_label.setStyleSheet(
            f"color: {text_secondary}; font-size: 11px; background: transparent;"
        )

        # ── Toggle buttons ──
        toggle_qss = f"""
            QPushButton {{
                background: transparent; border: 1px solid {border}; border-radius: 2px;
                padding: 3px 8px; color: {text_secondary}; font-size: 11px;
            }}
            QPushButton:hover {{ background: {bg_hover}; color: {text}; }}
            QPushButton:checked {{ background: {accent}; color: white; border-color: {accent}; }}
        """
        self._run_all_btn.setStyleSheet(toggle_qss)
        self._auto_switch_btn.setStyleSheet(toggle_qss)

        # ── Action buttons ──
        action_qss = f"""
            QPushButton {{
                background: transparent; border: 1px solid transparent; border-radius: 3px;
                color: {text}; padding: 2px 6px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {bg_hover}; border-color: {border}; }}
            QPushButton:disabled {{ color: {text_secondary}; background: transparent; }}
        """
        for btn in (self._add_file_btn, self._add_folder_btn, self._del_btn, self._clear_btn,
                     self._step_left_btn, self._step_right_btn):
            if btn is not None:
                btn.setStyleSheet(action_qss)

        # ── Thumbnail strip container ──
        self._strip_container.setStyleSheet(f"background: {bg_deep};")

        # ── Scroll area ──
        self._scroll_area.setStyleSheet(f"""
            QScrollArea {{ background: {bg_deep}; border: none; }}
            QScrollBar:horizontal {{
                background: {bg_raised}; height: 10px;
            }}
            QScrollBar::handle:horizontal {{
                background: {border}; border-radius: 3px; min-width: 30px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """)

        # ── Page navigation buttons ──
        # Must declare font-family in QSS — setStyleSheet() overrides setFont()
        page_qss = f"""
            QPushButton {{
                background: rgba(45, 45, 48, 0.85); border: 1px solid {border};
                border-radius: 3px; color: {text};
                font-family: "{ICON_FONT_FAMILY}"; font-size: 18px;
            }}
            QPushButton:hover {{ background: {bg_hover}; border-color: {accent}; }}
        """
        self._page_left_btn.setStyleSheet(page_qss)
        self._page_right_btn.setStyleSheet(page_qss)

    # ── Scroll with Shift+wheel ──────────────────────────

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
        self._reposition_page_buttons()

    def _reposition_page_buttons(self):
        """Position page buttons at left/right edges of the panel."""
        if not hasattr(self, '_page_right_btn') or self._page_right_btn is None:
            return
        pw = self.width()                               # full panel width
        sh = self._scroll_area.height()
        cy = (sh - PAGE_BTN_SIZE) // 2                  # vertical center
        self._page_left_btn.move(2, cy)
        self._page_right_btn.move(pw - PAGE_BTN_SIZE - 2, cy)

    # ── Page navigation ────────────

    def _page_left(self):
        """Scroll thumbnail strip left by one viewport width."""
        bar = self._scroll_area.horizontalScrollBar()
        bar.setValue(bar.value() - self._scroll_area.viewport().width())

    def _page_right(self):
        """Scroll thumbnail strip right by one viewport width."""
        bar = self._scroll_area.horizontalScrollBar()
        bar.setValue(bar.value() + self._scroll_area.viewport().width())

    # ── Step navigation ─────────

    def _step_left(self):
        """Single-step to the previous file — "上一张".

        WPF: ISrcFilesNodeData.MoveNext() extension method (reverse direction).
        Calls node.move_prev() then updates thumbnail selection and header.
        """
        node = self._current_node
        if node is None or not node.src_file_paths:
            return
        if not node.move_prev():
            return  # use_all_image=False and already at first → no-op

        new_path = node.src_file_path
        self._selected_path = new_path
        for path, btn in self._thumbnails.items():
            btn.set_selected(path == new_path)
        self._scroll_to_thumbnail(new_path)
        self._refresh_header()
        self._update_action_buttons()
        self.file_selected.emit(new_path)

    def _step_right(self):
        """Single-step to the next file — "下一张".

        Calls node.move_next() then updates thumbnail selection and header.
        """
        node = self._current_node
        if node is None or not node.src_file_paths:
            return
        if not node.move_next():
            return  # use_all_image=False and already at last → no-op

        new_path = node.src_file_path
        self._selected_path = new_path
        for path, btn in self._thumbnails.items():
            btn.set_selected(path == new_path)
        self._scroll_to_thumbnail(new_path)
        self._refresh_header()
        self._update_action_buttons()
        self.file_selected.emit(new_path)

    def _scroll_to_thumbnail(self, file_path: str):
        """Scroll the strip so the given thumbnail is visible."""
        btn = self._thumbnails.get(file_path)
        if btn is None:
            return
        self._scroll_area.ensureWidgetVisible(btn, xMargin=40, yMargin=0)

    # ── Node binding ────────────────────────────────────────────────────

    def set_node(self, node: "SrcFilesVisionNodeData | None"):
        """Bind to a source file node and load its thumbnails.

        VisionFlow: explicit rebuild + showEvent ensures correct sizing.
        """
        self._stop_loader()
        self._current_node = node
        self._clear_thumbnails()
        self._build_thumbnails()   # create buttons + update_container_size
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

    def showEvent(self, event):
        """Re-size container when panel becomes visible — guaranteed post-layout."""
        super().showEvent(event)
        QTimer.singleShot(0, self._update_container_size)  # singleShot(0) = next event loop tick

    def _stop_loader(self):
        if self._loader and self._loader.isRunning():
            self._loader.stop()
            self._loader.wait(1000)
        self._loader = None

    def _on_thumbnail_ready(self, file_path: str, qimg: QImage):
        """Receive a loaded thumbnail QImage and convert to QPixmap in GUI thread."""
        pixmap = QPixmap.fromImage(qimg)
        self._pixmaps[file_path] = pixmap
        btn = self._thumbnails.get(file_path)
        if btn:
            btn.set_thumbnail(pixmap)

    def _refresh_header(self):
        """Update header title, index, toggle state, and action button states.

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

        # Show file size for current file
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
            btn.hide()           # hide immediately before deferred delete
            btn.deleteLater()
        self._thumbnails.clear()
        self._pixmaps.clear()
        # Remove all layout items (no stretch to preserve)
        while self._thumb_layout.count():
            item = self._thumb_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()         # hide immediately before deferred delete
                w.deleteLater()
        self._selected_path = ""
        self._update_container_size()

    def _build_thumbnails(self):
        """Create thumbnail buttons for all file paths.

        VisionFlow: manually create ThumbnailButton for each path.
        """
        node = self._current_node
        if node is None:
            return

        paths = getattr(node, 'src_file_paths', []) or []
        current = getattr(node, 'src_file_path', '')

        for path in paths:
            btn = ThumbnailButton(path)
            btn.clicked_with_path.connect(self._on_thumbnail_clicked)
            btn.double_clicked_path.connect(self.file_double_clicked.emit)

            if path in self._pixmaps:
                btn.set_thumbnail(self._pixmaps[path])

            if path == current:
                btn.set_selected(True)
                self._selected_path = path

            self._thumb_layout.addWidget(btn)
            self._thumbnails[path] = btn

        self._update_container_size()
        QTimer.singleShot(50, self._update_container_size)  # deferred re-size after layout settles

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

    # ── File operations────────────────────────────────────

    # Image file filter
    IMAGE_FILTER = "图像文件 (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp);;所有文件 (*.*)"
    IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp")

    def _add_files(self):
        """
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

        # VisionFlow: incremental thumbnail build + header refresh
        self._add_thumbnails_incremental(list(paths))
        self._refresh_header()
        self._update_action_buttons()

        if not had_existing:
            first = self._current_node.src_file_path
            self._selected_path = first
            self.file_selected.emit(first)

        self.files_changed.emit()

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图像文件夹")
        if not folder or not self._current_node:
            return

        had_existing = bool(self._current_node.src_file_paths)
        old_count = len(self._current_node.src_file_paths)

        self._current_node.add_files_from_folder(folder, recursive=True)

        new_count = len(self._current_node.src_file_paths)
        added = new_count - old_count
        if added == 0:
            return

        # Determine which paths are new (those just appended)
        new_paths = self._current_node.src_file_paths[old_count:]
        # VisionFlow: incremental thumbnail build for added files only
        self._add_thumbnails_incremental(new_paths)
        self._refresh_header()
        self._update_action_buttons()

        if not had_existing and self._current_node.src_file_path:
            self._selected_path = self._current_node.src_file_path
            self.file_selected.emit(self._current_node.src_file_path)

        self.files_changed.emit()

    def _delete_current(self):
        """
        Shows confirmation dialog before removing the current file.
        """
        if not self._current_node:
            return
        current = self._current_node.src_file_path
        if not current:
            return

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
        self._update_container_size()

        self._refresh_header()
        self._update_action_buttons()
        self.files_changed.emit()

        # Emit selection for the newly selected adjacent file
        new_current = self._current_node.src_file_path
        if new_current:
            self._selected_path = new_current
            self.file_selected.emit(new_current)

    def _clear_files(self):
        """
        Shows confirmation before clearing all files.
        """
        if not self._current_node:
            return
        count = len(self._current_node.src_file_paths)
        if count == 0:
            return

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

    # ── Incremental thumbnail builder ─

    def _add_thumbnails_incremental(self, new_paths: list[str]):
        """Add new thumbnail buttons without rebuilding existing ones.
        VisionFlow: must explicitly create buttons for new files only.
        """
        for path in new_paths:
            if path in self._thumbnails:
                continue
            btn = ThumbnailButton(path)
            btn.clicked_with_path.connect(self._on_thumbnail_clicked)
            btn.double_clicked_path.connect(self.file_double_clicked.emit)

            if path in self._pixmaps:
                btn.set_thumbnail(self._pixmaps[path])

            self._thumb_layout.addWidget(btn)
            self._thumbnails[path] = btn

        self._update_container_size()
        QTimer.singleShot(50, self._update_container_size)  # deferred re-size

        if new_paths:
            loader = ThumbnailLoader(self)
            loader.set_paths(new_paths)
            loader.thumbnail_ready.connect(self._on_thumbnail_ready)
            loader.start()

    # ── Button state management ──────────────

    def _update_container_size(self):
        """Set container minimum width from thumbnail count + spacing + margins.

        Calculated explicitly to avoid Qt layout sizeHint() timing issues.
        count * (btn_w + spacing) - spacing + margins.left + margins.right
        """
        count = len(self._thumbnails)
        if count == 0:
            self._thumb_container.setMinimumSize(0, 0)
            return
        btn_w = THUMB_SIZE + 6
        spacing = self._thumb_layout.spacing()
        margins = self._thumb_layout.contentsMargins()
        total_w = count * (btn_w + spacing) - spacing + margins.left() + margins.right()
        self._thumb_container.setMinimumSize(total_w, 0)

    def _update_action_buttons(self):
        """Enable/disable action & step buttons based on file list state.
        """
        node = self._current_node
        has_files = node is not None and len(getattr(node, 'src_file_paths', []) or []) > 0
        has_selection = bool(getattr(node, 'src_file_path', '') if node else '')
        self._del_btn.setEnabled(has_files and has_selection)
        self._clear_btn.setEnabled(has_files)
        self._step_left_btn.setEnabled(has_files and has_selection)
        self._step_right_btn.setEnabled(has_files and has_selection)

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

        "自动切换" equivalent: during "运行全部", when UseAutoSwitch=ON,
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

        # Update thumbnail selection highlight
        for path, btn in self._thumbnails.items():
            btn.set_selected(path == current)

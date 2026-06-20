import os
import cv2
import numpy as np
from collections import OrderedDict

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
                             QPushButton, QLabel, QFrame, QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QPixmap, QImage, QFont, QColor, QPainter

from gui.constants import THUMB_SIZE, PAGE_BTN_SIZE, STRIP_HEIGHT, VIDEO_EXTENSIONS
from gui.font_icons import FontIcons, FontIconButton
from gui.theme import theme_manager, connect_theme


class ThumbnailLoader(QThread):
    """
    后台线程，用于从文件路径加载图像/视频缩略图。
    对于图像文件：加载并缩放到 75×75。
    对于视频文件：捕获第一帧并缩放。
    发出 QImage（而不是 QPixmap）以确保线程安全 — QPixmap 必须在 GUI 线程中创建，
    因为其 Windows GDI 句柄是线程相关的。
    """
    # 缩略图就绪信号：文件路径，QImage（线程安全）
    thumbnail_ready = pyqtSignal(str, QImage)

    def __init__(self, parent=None):
        """初始化缩略图加载器

        参数：
            parent: 父对象
        """
        super().__init__(parent)     # 调用父类QThread的构造函数
        self._paths: list[str] = []  # 文件路径列表
        self._running = True         # 运行标志

    def set_paths(self, paths: list[str]):
        """设置要加载的文件路径列表"""
        self._paths = list(paths)

    def stop(self):
        """停止加载"""
        self._running = False

    def run(self):
        """线程运行方法"""
        for path in self._paths:   # 遍历所有文件路径
            if not self._running:  # 如果收到停止信号,退出循环
                break
            try:
                ext = os.path.splitext(path)[1].lower()                      # 获取文件扩展名（小写）
                if ext in VIDEO_EXTENSIONS:                                  # 如果是视频文件
                    img = self._capture_video_frame(path)                    # 捕获视频帧作为缩略图
                else:
                    img = cv2.imread(path, cv2.IMREAD_COLOR)                 # 否则读取图像文件（彩色模式）

                if img is None:                                              # 如果图像为空,跳过
                    continue
                h, w = img.shape[:2]                                         # 获取图像高度和宽度
                scale = min(THUMB_SIZE / max(w, 1), THUMB_SIZE / max(h, 1))  # 计算缩放比例,使图像适配75x75
                if scale < 1.0:                                              # 如果需要缩小
                    new_w, new_h = int(w * scale), int(h * scale)            # 计算新尺寸
                    img = cv2.resize(img, (new_w, new_h),              # 缩放图像
                                     interpolation=cv2.INTER_AREA)           # 使用INTER_AREA插值

                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)                  # BGR转RGB
                h, w, ch = rgb.shape                                        # 获取高度宽度通道数
                bytes_per_line = ch * w                                     # 计算每行字节数
                qimg = QImage(rgb.data, w, h,                               # 创建QImage
                              bytes_per_line, QImage.Format_RGB888).copy()  # 深拷贝保证线程安全
                self.thumbnail_ready.emit(path, qimg)                       # 发出缩略图就绪信号
            except Exception:
                continue                                                    # 发生异常时跳过

    def _capture_video_frame(self, path: str) -> np.ndarray | None:
        """捕获视频文件的第一帧作为缩略图

        参数：
            path: 视频文件路径

        返回：
            第一帧图像，失败则返回 None
        """
        try:
            cap = cv2.VideoCapture(path)   # 打开视频文件
            if not cap.isOpened():         # 如果打开失败,返回None
                return None
            ret, frame = cap.read()        # 读取第一帧
            cap.release()                  # 释放视频捕获对象
            if ret and frame is not None:  # 如果读取成功且帧不为空
                return frame               # 返回帧图像
            return None
        except Exception:
            return None


# ── 缩略图控件 ──────────────────────────────────────────────────────

class ThumbnailButton(QPushButton):
    """可点击的75×75缩略图按钮

    颜色通过 connect_theme 跟随主题变化
    """

    # 点击时发出的信号，携带文件路径
    clicked_with_path = pyqtSignal(str)
    # 双击时发出的信号，携带文件路径
    double_clicked_path = pyqtSignal(str)

    # 主题QSS模板 — 主题变化时重新生成
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
        """初始化缩略图按钮

        参数：
            file_path: 文件路径
            parent: 父对象
        """
        super().__init__(parent)                                                  # 调用父类QPushButton的构造函数
        self.file_path = file_path                                                # 保存文件路径
        self._pixmap: QPixmap | None = None                                       # 像素图对象，初始为None
        self._selected = False                                                    # 选中状态标志，初始为False

        self.setFixedSize(THUMB_SIZE + 6, THUMB_SIZE + 6)                         # 设置固定大小（THUMB_SIZE + 6边距）
        self.setCursor(Qt.PointingHandCursor)                                     # 设置光标为手指形状
        self.setToolTip(file_path)                                                # 设置工具提示为文件路径

        from gui.theme import theme_manager as _tm                                # 导入主题管理器
        self._theme_manager = _tm                                                 # 保存主题管理器引用
        self._refresh_qss()                                                       # 刷新样式表
        self._theme_manager.theme_changed.connect(lambda _: self._refresh_qss())  # 连接主题变化信号

        self.clicked.connect(lambda: self.clicked_with_path.emit(self.file_path))  # 连接点击信号，发出带文件路径的点击信号

    def _refresh_qss(self):
        """刷新样式表"""
        tm = self._theme_manager                              # 获取主题管理器
        self.setStyleSheet(self.THEME_QSS.format(             # 设置样式表，使用主题颜色
            bg_normal=tm.color("bg_surface_raised").name(),   # 背景正常色
            border_normal=tm.color("border").name(),          # 边框正常色
            accent=tm.color("accent").name(),                 # 强调色
            bg_hover=tm.color("bg_surface_hover").name(),     # 悬停背景色
            bg_selected=tm.color("bg_surface_input").name(),  # 选中背景色
        ))

    def set_thumbnail(self, pixmap: QPixmap):
        """设置加载的缩略图像素图

        参数：
            pixmap: 像素图对象
        """
        self._pixmap = pixmap  # 保存像素图
        self.update()          # 触发重绘

    def set_selected(self, selected: bool):
        """设置选中状态

        参数：
            selected: 是否选中
        """
        self._selected = selected                                            # 保存选中状态
        self.setProperty("selected", "true" if selected else "false")  # 设置属性"selected"，用于样式表选择器
        self.style().unpolish(self)                                          # 取消样式应用
        self.style().polish(self)                                            # 重新应用样式
        self.update()                                                        # 触发重绘

    def paintEvent(self, event):
        """绘制事件

        参数：
            event: 绘制事件对象
        """
        super().paintEvent(event)
        # 像素图有效时
        if self._pixmap and not self._pixmap.isNull():
            painter = QPainter(self)                               # 创建绘图对象
            painter.setRenderHint(QPainter.SmoothPixmapTransform)  # 启用平滑像素图变换
            pw, ph = self._pixmap.width(), self._pixmap.height()   # 获取像素图宽度和高度
            x = (self.width() - pw) // 2                           # 计算居中显示的X坐标
            y = (self.height() - ph) // 2                          # 计算居中显示的Y坐标
            painter.drawPixmap(x, y, self._pixmap)                 # 绘制像素图
        else:
            painter = QPainter(self)                              # 像素图不存在，显示占位符
            painter.setPen(QColor("#555"))                        # 设置画笔颜色为灰色
            painter.setFont(QFont("Segoe UI", 9))                 # 设置字体
            painter.drawText(self.rect(), Qt.AlignCenter, "...")  # 在按钮中央绘制"..."

    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件

        参数：
            event: 鼠标事件对象
        """
        self.double_clicked_path.emit(self.file_path)  # 发出双击信号，携带文件路径
        event.accept()                                 # 接受事件


# ═══════════════════════════════════════════════════════════════════════════
# 主面板
# ═══════════════════════════════════════════════════════════════════════════

class FlowResourcePanel(QWidget):
    """
    对齐的图像源面板，带有缩略图条。
    信号：
        file_selected(str) — 点击缩略图时发出（= 选中）
        file_selected 的作用是：在资源面板点击缩略图 → 右侧图像面板显示该图片
        file_double_clicked(str) — 双击时发出，用于全尺寸缩放查看器
        双击资源面板缩略图 → 右边显示图片并自动全尺寸缩放
        files_changed() — 添加/删除/清空操作后发出
    """
    file_selected = pyqtSignal(str)
    file_double_clicked = pyqtSignal(str)
    files_changed = pyqtSignal()

    def __init__(self, parent=None):
        """初始化流程资源面板

        参数：
            parent: 父对象
        """
        super().__init__(parent)
        self._current_node = None                              # 当前绑定的源文件节点，初始为None
        self._thumbnails: dict[str, ThumbnailButton] = {}      # 缩略图字典：键为文件路径，值为ThumbnailButton对象
        self._pixmap_cache_max = 500                           # LRU 缓存：最大缩略图数量
        self._pixmaps: OrderedDict[str, QPixmap] = OrderedDict()  # LRU 像素图 OrderedDict，最近访问的在末尾
        self._loader: ThumbnailLoader | None = None            # 缩略图加载器，初始为None
        self._incremental_loaders: list[ThumbnailLoader] = []  # 增量加载器列表（用于追踪并停止）
        self._selected_path: str = ""                          # 当前选中的文件路径
        self._setup_ui()                                       # 设置UI界面
        self._refresh_qss()                                    # 应用主题样式
        connect_theme(lambda: self._refresh_qss())             # 主题切换时刷新样式

    def _refresh_qss(self):
        """主题变化时重新应用面板颜色"""
        tm = theme_manager
        bg_raised = tm.color("bg_surface_raised").name()
        bg_deep = tm.color("bg_surface_deep").name()
        border = tm.color("border").name()
        text = tm.color("text_primary").name()
        accent = tm.color("accent").name()

        self.setStyleSheet(f"FlowResourcePanel {{ background: {bg_deep}; }}")
        self._header_bar.setStyleSheet(
            f"background: {bg_raised}; border-bottom: 1px solid {border};"
        )
        self._strip_container.setStyleSheet(f"background: {bg_deep};")

    def _setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 头部栏 ──
        self._header_bar = QWidget()
        self._header_bar.setFixedHeight(34)
        h_layout = QHBoxLayout(self._header_bar)
        h_layout.setContentsMargins(8, 4, 6, 4)
        h_layout.setSpacing(4)

        self._title_label = QLabel("图像源")
        self._title_label.setStyleSheet("font-size: 11px; font-weight: bold; background: transparent;")
        h_layout.addWidget(self._title_label)
        self._index_label = QLabel("0/0")
        self._index_label.setStyleSheet("font-size: 11px; background: transparent;")
        h_layout.addWidget(self._index_label)

        h_layout.addStretch(1)

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

        # 工具栏分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("background: #505050;")
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        h_layout.addWidget(sep)

        # 字体图标动作按钮
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

        # 单步导航分隔线
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("background: #505050;")
        sep2.setFixedWidth(1)
        sep2.setFixedHeight(20)
        h_layout.addWidget(sep2)

        # 单步导航按钮
        self._step_left_btn = FontIconButton(FontIcons.ChevronLeft, tooltip="上一张", font_size=14)
        self._step_left_btn.clicked.connect(self._step_left)
        self._step_left_btn.setEnabled(False)
        h_layout.addWidget(self._step_left_btn)

        self._step_right_btn = FontIconButton(FontIcons.ChevronRight, tooltip="下一张", font_size=14)
        self._step_right_btn.clicked.connect(self._step_right)
        self._step_right_btn.setEnabled(False)
        h_layout.addWidget(self._step_right_btn)

        layout.addWidget(self._header_bar)

        # ── 带有叠加翻页按钮的缩略图条 ──
        self._strip_container = QFrame()
        self._strip_container.setFrameShape(QFrame.NoFrame)
        strip_layout = QVBoxLayout(self._strip_container)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setFixedHeight(THUMB_SIZE + 24)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setFocusPolicy(Qt.NoFocus)

        self._scroll_area.wheelEvent = self._scroll_wheel_event
        self._thumb_container = QWidget()
        self._thumb_layout = QHBoxLayout(self._thumb_container)
        self._thumb_layout.setContentsMargins(36, 4, 36, 4)
        self._thumb_layout.setSpacing(2)
        self._thumb_layout.setAlignment(Qt.AlignLeft)

        self._scroll_area.setWidget(self._thumb_container)
        strip_layout.addWidget(self._scroll_area)

        # ── 翻页导航叠加按钮 ──
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

        self._page_left_btn.setParent(self._scroll_area)
        self._page_left_btn.move(2, (self._scroll_area.height() - PAGE_BTN_SIZE) // 2)
        self._page_left_btn.show()

        self._page_right_btn.setParent(self._scroll_area)
        QTimer.singleShot(100, lambda: self._reposition_page_buttons())
        self._page_right_btn.show()

        connect_theme(self._refresh_all_qss)

        layout.addWidget(self._strip_container)
        self.setFixedHeight(STRIP_HEIGHT + 4)

    def _refresh_all_qss(self):
        """将所有硬编码颜色更新为当前主题"""
        tm = theme_manager                                   # 获取主题管理器
        bg_raised = tm.color("bg_surface_raised").name()     # 凸起背景色
        bg_deep = tm.color("bg_surface_deep").name()         # 深层背景色
        bg_hover = tm.color("bg_surface_hover").name()       # 悬停背景色
        border = tm.color("border").name()                   # 边框颜色
        accent = tm.color("accent").name()                   # 强调色
        text = tm.color("text_primary").name()               # 主文本色
        text_secondary = tm.color("text_secondary").name()   # 次要文本色
        text_title = tm.color("text_title").name()           # 标题文本色

        # ── 头部栏样式 ──
        self._header_bar.setStyleSheet(
            f"background: {bg_raised}; border-bottom: 1px solid {border};"
        )
        # 标题标签样式
        self._title_label.setStyleSheet(
            f"color: {text_title}; font-size: 11px; font-weight: bold; background: transparent;"
        )
        # 索引标签样式
        self._index_label.setStyleSheet(
            f"color: {text_secondary}; font-size: 11px; background: transparent;"
        )

        # ── 切换按钮样式 ──
        toggle_qss = f"""
            QPushButton {{
                background: transparent; border: 1px solid {border}; border-radius: 2px;
                padding: 3px 8px; color: {text_secondary}; font-size: 11px;
            }}
            QPushButton:hover {{ background: {bg_hover}; color: {text}; }}
            QPushButton:checked {{ background: {accent}; color: white; border-color: {accent}; }}
        """
        self._run_all_btn.setStyleSheet(toggle_qss)                             # 应用切换按钮样式
        self._auto_switch_btn.setStyleSheet(toggle_qss)

        # ── 动作按钮样式 ──
        action_qss = f"""
            QPushButton {{
                background: transparent; border: 1px solid transparent; border-radius: 3px;
                color: {text}; padding: 2px 6px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {bg_hover}; border-color: {border}; }}
            QPushButton:disabled {{ color: {text_secondary}; background: transparent; }}
        """
        # 遍历所有动作按钮，应用样式
        for btn in (self._add_file_btn, self._add_folder_btn, self._del_btn, self._clear_btn,
                     self._step_left_btn, self._step_right_btn):
            if btn is not None:
                btn.setStyleSheet(action_qss)

        # ── 缩略图条容器样式 ──
        self._strip_container.setStyleSheet(f"background: {bg_deep};")

        # ── 滚动区域样式 ──
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

        # ── 翻页导航按钮样式 ──
        # 必须在 QSS 中声明 font-family — setStyleSheet() 会覆盖 setFont()
        page_qss = f"""
            QPushButton {{
                background: rgba(45, 45, 48, 0.85); border: 1px solid {border};
                border-radius: 3px; color: {text};
                font-family: "Segoe MDL2 Assets"; font-size: 18px;
            }}
            QPushButton:hover {{ background: {bg_hover}; border-color: {accent}; }}
        """
        self._page_left_btn.setStyleSheet(page_qss)                             # 应用翻页按钮样式
        self._page_right_btn.setStyleSheet(page_qss)

    # ── Shift+滚轮 水平滚动 ──────────────────────────

    def _scroll_wheel_event(self, event):
        """重写 QScrollArea 的 wheelEvent：Shift+滚轮 → 水平滚动

        参数：
            event: 滚轮事件对象
        """
        # 如果按下了Shift键
        if event.modifiers() & Qt.ShiftModifier:
            # 获取滚轮的垂直滚动量
            delta = event.angleDelta().y()
            # 获取水平滚动条
            bar = self._scroll_area.horizontalScrollBar()
            # 设置滚动条值（反向滚动）
            bar.setValue(bar.value() - delta)
            # 接受事件
            event.accept()
        else:
            QScrollArea.wheelEvent(self._scroll_area, event)                 # 否则调用父类的wheelEvent

    def _reposition_page_buttons(self):
        """翻页按钮水平居中放在滚动区域左右两端"""
        if not hasattr(self, '_page_right_btn') or self._page_right_btn is None:
            return
        sw = self._scroll_area.width()
        sh = self._scroll_area.height()
        cy = (sh - PAGE_BTN_SIZE) // 2
        self._page_left_btn.move(2, cy - 3)
        self._page_right_btn.move(sw - PAGE_BTN_SIZE, cy - 3)

    # ── 翻页导航 ────────────

    def _page_left(self):
        """向左滚动缩略图条一个视口宽度"""
        bar = self._scroll_area.horizontalScrollBar()                           # 获取水平滚动条
        bar.setValue(bar.value() - self._scroll_area.viewport().width())     # 设置滚动条值：当前位置减去视口宽度

    def _page_right(self):
        """向右滚动缩略图条一个视口宽度"""
        bar = self._scroll_area.horizontalScrollBar()                           # 获取水平滚动条
        bar.setValue(bar.value() + self._scroll_area.viewport().width())     # 设置滚动条值：当前位置加上视口宽度

    # ── 单步导航 ─────────

    def _step_left(self):
        """单步切换到上一个文件 — "上一张"

        调用 node.move_prev()，然后更新缩略图选中状态和头部。
        """

        node = self._current_node                    # 获取当前绑定的节点
        if node is None or not node.src_file_paths:  # 如果节点为空或文件列表为空，返回
            return

        if not node.move_prev():                     # 切换到上一个文件，如果失败（边界且use_all_image=False）则返回
            return


        new_path = node.src_file_path               # 获取新的当前文件路径
        self._selected_path = new_path              # 更新选中路径
        for path, btn in self._thumbnails.items():  # 遍历所有缩略图，更新选中状态
            btn.set_selected(path == new_path)

        self._scroll_to_thumbnail(new_path)         # 滚动使当前缩略图可见
        self._refresh_header()                      # 刷新头部
        self._update_action_buttons()               # 更新动作按钮状态
        self.file_selected.emit(new_path)           # 发出文件选中信号

    def _step_right(self):
        """
        单步切换到下一个文件 — "下一张"
        调用 node.move_next()，然后更新缩略图选中状态和头部。
        """
        node = self._current_node                    # 获取当前绑定的节点
        if node is None or not node.src_file_paths:  # 如果节点为空或文件列表为空，返回
            return

        if not node.move_next():                     # 切换到下一个文件，如果失败（边界且use_all_image=False）则返回
            return


        new_path = node.src_file_path                # 获取新的当前文件路径
        self._selected_path = new_path               # 更新选中路径
        for path, btn in self._thumbnails.items():   # 遍历所有缩略图，更新选中状态
            btn.set_selected(path == new_path)

        self._scroll_to_thumbnail(new_path)          # 滚动使当前缩略图可见
        self._refresh_header()                       # 刷新头部
        self._update_action_buttons()                # 更新动作按钮状态
        self.file_selected.emit(new_path)            # 发出文件选中信号

    def _scroll_to_thumbnail(self, file_path: str):
        """
        滚动缩略图条，使指定缩略图可见
        参数：
            file_path: 文件路径
        """
        btn = self._thumbnails.get(file_path)  # 获取对应的缩略图按钮
        if btn is None:                        # 如果按钮不存在，返回
            return

        self._scroll_area.ensureWidgetVisible(btn, xMargin=40, yMargin=0)  # 滚动确保按钮可见（左右各留40像素边距）

    # ── 节点绑定 ────────────────────────────────────────────────────

    def set_node(self, node):
        """
        绑定到源文件节点并加载其缩略图
        VisionFlow：显式重建 + showEvent 确保正确的尺寸
        """

        self._stop_loader()         # 停止当前加载器
        self._current_node = node   # 保存当前节点引用
        self._clear_thumbnails()    # 清除所有缩略图
        self._build_thumbnails()    # 构建缩略图（创建按钮 + 更新容器尺寸）
        self._refresh_header()      # 刷新头部

        # 节点为空时返回
        if node is None:
            return

        paths = getattr(node, 'src_file_paths', []) or []                   # 获取文件路径列表
        if not paths:
            return

        self._loader = ThumbnailLoader(self)                            # 启动异步加载器（按钮已存在，像素图将逐步填充）
        self._loader.set_paths(paths)                                   # 设置要加载的文件路径列表
        self._loader.thumbnail_ready.connect(self._on_thumbnail_ready)  # 连接缩略图就绪信号
        self._loader.start()                                                 # 启动线程

    def showEvent(self, event):
        """当面板变为可见时重新调整容器大小 — 保证布局完成后执行"""
        super().showEvent(event)                                             # 调用父类的showEvent
        QTimer.singleShot(0, self._update_container_size)                   # 在下一个事件循环中更新容器尺寸（确保布局完成）

    def _stop_loader(self):
        """停止所有缩略图加载器（主加载器和增量加载器）"""
        # 停止增量加载器
        for loader in self._incremental_loaders:
            if loader.isRunning():
                loader.stop()
                loader.wait(1000)
        self._incremental_loaders.clear()

        # 停止主加载器
        if self._loader and self._loader.isRunning():
            self._loader.stop()
            self._loader.wait(1000)
        self._loader = None

    def _on_thumbnail_ready(self, file_path: str, qimg: QImage):
        """收到加载完成的缩略图，在GUI线程中转换为QPixmap

        参数：
            file_path: 文件路径
            qimg: 缩略图QImage对象
        """
        pixmap = QPixmap.fromImage(qimg)                                     # 将QImage转换为QPixmap
        # LRU 缓存淘汰并保存（OrderedDict O(1) 操作）
        self._pixmaps[file_path] = pixmap
        self._pixmaps.move_to_end(file_path)
        while len(self._pixmaps) > self._pixmap_cache_max:
            self._pixmaps.popitem(last=False)
        btn = self._thumbnails.get(file_path)                                # 获取对应的缩略图按钮
        # 按钮存在时设置缩略图
        if btn:
            btn.set_thumbnail(pixmap)

    def _refresh_header(self):
        """更新头部标题、索引、切换按钮状态和动作按钮状态

        VisionFlow：显式刷新调用
        """
        node = self._current_node                                            # 获取当前节点
        # 节点为空时
        if node is None:
            self._title_label.setText("图像源")                               # 设置标题为"图像源"
            self._index_label.setText("0/0")                                  # 设置索引为"0/0"
            # 运行全部按钮取消选中
            self._run_all_btn.blockSignals(True)
            self._run_all_btn.setChecked(False)
            self._run_all_btn.blockSignals(False)
            # 自动切换按钮取消选中
            self._auto_switch_btn.blockSignals(True)
            self._auto_switch_btn.setChecked(False)
            self._auto_switch_btn.blockSignals(False)
            self._update_action_buttons()                                    # 更新动作按钮状态
            return

        is_video = "video" in type(node).__name__.lower()                    # 判断是否为视频源
        self._title_label.setText("视频源" if is_video else "图像源")          # 设置标题

        paths = getattr(node, 'src_file_paths', []) or []                    # 获取文件路径列表
        current = getattr(node, 'src_file_path', '')                         # 获取当前路径
        total = len(paths)                                                   # 总数
        idx = 0                                                              # 当前索引（从1开始）
        # 当前路径有效时
        if current and current in paths:
            idx = paths.index(current) + 1

        size_text = ""                                                        # 显示当前文件大小
        if current:
            try:
                size = os.path.getsize(current)                               # 获取文件大小，try/except 替代 TOCTOU
                # 格式化显示
                if size >= 1024 * 1024:
                    size_text = f"[{size / 1024 / 1024:.1f} MB]"
                else:
                    size_text = f"[{size / 1024:.1f} KB]"
            except OSError:
                pass
        self._index_label.setText(f"{idx}/{total}  {size_text}")             # 设置索引标签

        # 刷新运行全部按钮状态
        self._run_all_btn.blockSignals(True)
        self._run_all_btn.setChecked(getattr(node, 'use_all_image', False))
        self._run_all_btn.blockSignals(False)

        # 刷新自动切换按钮状态
        self._auto_switch_btn.blockSignals(True)
        self._auto_switch_btn.setChecked(getattr(node, 'use_auto_switch', True))
        self._auto_switch_btn.blockSignals(False)

        self._update_action_buttons()                                         # 更新动作按钮状态

    def _clear_thumbnails(self):
        """移除所有缩略图按钮和缓存的像素图"""
        # 清理缩略图按钮
        for btn in list(self._thumbnails.values()):
            btn.hide()                                                       # 立即隐藏
            btn.deleteLater()                                                # 延迟删除
        self._thumbnails.clear()                                             # 清空缩略图字典
        self._pixmaps.clear()                                                # 清空像素图字典
        # 移除所有布局项
        while self._thumb_layout.count():
            item = self._thumb_layout.takeAt(0)                              # 获取布局项
            w = item.widget()                                                # 获取控件
            # 控件存在时清理
            if w:
                w.hide()                                                     # 立即隐藏
                w.deleteLater()                                              # 延迟删除
        self._selected_path = ""                                             # 清空选中的路径
        self._update_container_size()                                        # 更新容器尺寸

    def _build_thumbnails(self):
        """为所有文件路径创建缩略图按钮

        VisionFlow：为每个路径手动创建 ThumbnailButton
        """
        node = self._current_node                                            # 获取当前节点
        # 节点为空时返回
        if node is None:
            return

        paths = getattr(node, 'src_file_paths', []) or []                    # 获取文件路径列表
        current = getattr(node, 'src_file_path', '')                         # 获取当前路径

        # 去重遍历文件路径
        seen = set()
        for path in paths:
            # 跳过重复
            if path in seen:
                continue
            seen.add(path)

            btn = ThumbnailButton(path)                                       # 创建缩略图按钮
            btn.clicked_with_path.connect(self._on_thumbnail_clicked)         # 连接点击信号
            btn.double_clicked_path.connect(self.file_double_clicked.emit)    # 连接双击信号

            # 设置已缓存的像素图
            if path in self._pixmaps:
                btn.set_thumbnail(self._pixmaps[path])

            # 设置为当前选中状态
            if path == current:
                btn.set_selected(True)
                self._selected_path = path

            self._thumb_layout.addWidget(btn)                                 # 添加到布局
            self._thumbnails[path] = btn                                      # 保存到字典

        self._update_container_size()                                         # 更新容器尺寸
        QTimer.singleShot(50, self._update_container_size)                   # 延迟50毫秒后再次更新（布局稳定后）

    # ── 交互 ─────────────────────────────────────────────────────

    def _on_thumbnail_clicked(self, file_path: str):
        """处理缩略图点击选中

        参数：
            file_path: 点击的文件路径
        """
        # 节点支持 src_file_path 时更新
        if self._current_node and hasattr(self._current_node, 'src_file_path'):
            self._current_node.src_file_path = file_path                      # 更新节点的当前文件路径

        self._selected_path = file_path                                       # 更新选中高亮
        # 更新所有缩略图选中状态
        for path, btn in self._thumbnails.items():
            btn.set_selected(path == file_path)

        self._refresh_header()                                                # 刷新头部
        self.file_selected.emit(file_path)                                    # 发出文件选中信号

    def _on_run_all_toggled(self, checked: bool):
        """运行全部按钮切换回调

        参数：
            checked: 是否选中
        """
        # 有当前节点时更新 use_all_image
        if self._current_node:
            self._current_node.use_all_image = checked                       # 更新节点的use_all_image属性

    def _on_auto_switch_toggled(self, checked: bool):
        """自动切换按钮切换回调

        参数：
            checked: 是否选中
        """
        # 有当前节点时更新 use_auto_switch
        if self._current_node:
            self._current_node.use_auto_switch = checked                     # 更新节点的use_auto_switch属性

    # ── 文件操作 ────────────────────────────────────

    # 图像文件过滤器
    IMAGE_FILTER = "图像文件 (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp);;所有文件 (*.*)"

    def _add_files(self):
        """添加文件

        解耦：QFileDialog 在 GUI 层使用，但 node.add_files() 保持纯数据操作。
        节点不知道 Qt 的存在。
        """
        paths, _ = QFileDialog.getOpenFileNames(                                # 打开文件选择对话框
            self, "选择图像文件", "", self.IMAGE_FILTER
        )
        # 无文件或无节点时返回
        if not paths or not self._current_node:
            return
        had_existing = bool(self._current_node.src_file_paths)                # 记录是否有已有文件
        self._current_node.add_files(list(paths))                             # 添加文件到节点

        # 增量添加缩略图并刷新
        self._add_thumbnails_incremental(list(paths))
        self._refresh_header()
        self._update_action_buttons()

        # 首次添加时选中第一个文件
        if not had_existing:
            first = self._current_node.src_file_path
            self._selected_path = first
            self.file_selected.emit(first)

        self.files_changed.emit()                                              # 发出文件列表变化信号

    def _add_folder(self):
        """添加文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择图像文件夹")      # 打开文件夹选择对话框
        # 无文件夹或无节点时返回
        if not folder or not self._current_node:
            return

        had_existing = bool(self._current_node.src_file_paths)                # 记录是否有已有文件
        old_count = len(self._current_node.src_file_paths)                    # 记录原文件数量

        self._current_node.add_files_from_folder(folder, recursive=True)      # 从文件夹添加文件（递归）

        new_count = len(self._current_node.src_file_paths)                    # 获取新文件数量
        added = new_count - old_count                                         # 计算新增数量
        # 无新增文件时返回
        if added == 0:
            return

        new_paths = self._current_node.src_file_paths[old_count:]             # 获取新增的文件路径
        # 增量添加缩略图并刷新
        self._add_thumbnails_incremental(new_paths)
        self._refresh_header()
        self._update_action_buttons()

        # 首次添加时选中第一个文件
        if not had_existing and self._current_node.src_file_path:
            self._selected_path = self._current_node.src_file_path
            self.file_selected.emit(self._current_node.src_file_path)

        self.files_changed.emit()                                              # 发出文件列表变化信号

    def _delete_current(self):
        """删除当前文件

        删除前显示确认对话框。
        """
        # 无节点时返回
        if not self._current_node:
            return
        current = self._current_node.src_file_path                           # 获取当前文件路径
        # 无当前文件时返回
        if not current:
            return

        # 显示确认对话框
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除当前图像吗？\n{os.path.basename(current)}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        # 用户不确认时返回
        if reply != QMessageBox.Yes:
            return

        self._current_node.delete_current_file()                              # 从节点删除当前文件

        btn = self._thumbnails.pop(current, None)                              # 增量删除缩略图按钮
        if btn:
            self._thumb_layout.removeWidget(btn)
            btn.deleteLater()
        self._pixmaps.pop(current, None)                                       # 从像素图字典移除
        self._update_container_size()                                          # 更新容器尺寸

        self._refresh_header()                                                 # 刷新头部
        self._update_action_buttons()                                          # 更新动作按钮状态
        self.files_changed.emit()                                              # 发出文件列表变化信号

        new_current = self._current_node.src_file_path                         # 获取相邻文件路径
        if new_current:
            self._selected_path = new_current
            self.file_selected.emit(new_current)                               # 发出新选中文件信号

    def _clear_files(self):
        """清空所有文件

        清空前显示确认对话框。
        """
        # 无节点时返回
        if not self._current_node:
            return
        count = len(self._current_node.src_file_paths)                       # 获取文件数量
        # 无文件时返回
        if count == 0:
            return

        # 显示确认对话框
        reply = QMessageBox.question(
            self, "确认清空",
            f"确定要清空所有图像文件吗？\n当前共有 {count} 个文件",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        # 用户不确认时返回
        if reply != QMessageBox.Yes:
            return

        self._current_node.clear_files()                                      # 清空节点的所有文件

        self._clear_thumbnails()                                               # 清空所有缩略图
        self._refresh_header()                                                 # 刷新头部
        self._update_action_buttons()                                          # 更新动作按钮状态
        self._selected_path = ""                                               # 清空选中路径
        self.files_changed.emit()                                              # 发出文件列表变化信号

    # ── 增量缩略图构建器 ─

    def _add_thumbnails_incremental(self, new_paths: list[str]):
        """添加新的缩略图按钮，不重建已有的

        VisionFlow：必须为新增文件显式创建按钮
        """
        # 遍历新文件路径
        for path in new_paths:
            # 已存在则跳过
            if path in self._thumbnails:
                continue

            btn = ThumbnailButton(path)  # 创建缩略图按钮
            btn.clicked_with_path.connect(self._on_thumbnail_clicked)  # 连接点击信号
            btn.double_clicked_path.connect(self.file_double_clicked.emit)  # 连接双击信号

            # 设置已缓存的像素图
            if path in self._pixmaps:
                btn.set_thumbnail(self._pixmaps[path])

            self._thumb_layout.addWidget(btn)                                 # 添加到布局
            self._thumbnails[path] = btn                                      # 保存到字典

        self._update_container_size()                                         # 更新容器尺寸
        QTimer.singleShot(50, self._update_container_size)                   # 延迟50毫秒后再次更新

        # 启动加载器加载新缩略图
        if new_paths:
            loader = ThumbnailLoader(self)                                     # 创建新加载器并追踪
            loader.set_paths(new_paths)
            loader.thumbnail_ready.connect(self._on_thumbnail_ready)
            self._incremental_loaders.append(loader)
            # 加载完成时自动从列表移除
            loader.finished.connect(lambda l=loader: self._incremental_loaders.remove(l)
                                    if l in self._incremental_loaders else None)
            loader.start()

    # ── 按钮状态管理 ──────────────

    def _update_container_size(self):
        """
        设置容器最小宽度（根据缩略图数量 + 间距 + 边距）
        显式计算以避免 Qt 布局 sizeHint() 的时序问题。
        计算公式：数量 * (按钮宽 + 间距) - 间距 + 左边距 + 右边距
        """
        count = len(self._thumbnails)                                          # 获取缩略图数量
        # 无缩略图时
        if count == 0:
            self._thumb_container.setMinimumSize(0, 0)  # 设置最小尺寸为0
            return

        btn_w = THUMB_SIZE + 6  # 按钮宽度（THUMB_SIZE + 6）
        spacing = self._thumb_layout.spacing()  # 布局间距
        margins = self._thumb_layout.contentsMargins()  # 布局边距
        total_w = count * (btn_w + spacing) - spacing + margins.left() + margins.right()  # 计算总宽度
        self._thumb_container.setMinimumSize(total_w, 0)  # 设置容器最小宽度

    def _update_action_buttons(self):
        """根据文件列表状态启用/禁用动作按钮和步进按钮"""
        node = self._current_node                                            # 获取当前节点
        has_files = node is not None and len(getattr(node, 'src_file_paths', []) or []) > 0  # 是否有文件
        has_selection = bool(getattr(node, 'src_file_path', '') if node else '')              # 是否有选中的文件
        self._del_btn.setEnabled(has_files and has_selection)         # 设置删除按钮启用状态
        self._clear_btn.setEnabled(has_files)                         # 设置清空按钮启用状态
        self._step_left_btn.setEnabled(has_files and has_selection)   # 设置上一张按钮启用状态
        self._step_right_btn.setEnabled(has_files and has_selection)  # 设置下一张按钮启用状态

    # ── 公共API ──────────────────────────────────────────────────────

    def refresh(self):
        """强制从当前节点完全刷新缩略图"""
        self._stop_loader()       # 停止加载器
        self._clear_thumbnails()  # 清除所有缩略图
        self._build_thumbnails()  # 构建缩略图
        self._refresh_header()

        node = self._current_node                                            # 获取当前节点
        if node is None:
            return

        paths = getattr(node, 'src_file_paths', []) or []
        # 有文件时启动加载器
        if paths:
            self._loader = ThumbnailLoader(self)
            self._loader.set_paths(paths)
            self._loader.thumbnail_ready.connect(self._on_thumbnail_ready)
            self._loader.start()

    def refresh_selection(self):
        """
        轻量级刷新 — 仅更新头部索引和缩略图高亮
        "自动切换" 等效：在"运行全部"过程中，当 UseAutoSwitch=ON 时，
        SrcFilePath 绑定会自动更新缩略图 ListBox 的选中项。
        在 VisionFlow 中，我们在 auto_switch 为 ON 时从 FILE_ITERATION_NEXT
        事件处理器显式调用此方法。
        """
        node = self._current_node                                            # 获取当前节点
        if node is None:
            return

        current = getattr(node, 'src_file_path', '')                         # 获取当前文件路径
        self._refresh_header()  # 刷新头部（更新索引/文件名）
        for path, btn in self._thumbnails.items():
            btn.set_selected(path == current)
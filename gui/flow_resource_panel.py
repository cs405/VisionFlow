"""流程资源面板 — 图像源展开器 1:1 移植。

布局（水平方向）：
  ┌─────────────────────────────────────────────────────────────────────┐
  │ 图像源 1/10   [运行全部] [自动切换] [文件][夹][删][清]                    │ ← 头部
  ├─────────────────────────────────────────────────────────────────────┤
  │ ◀ │ [img1][img2][img3][img4]... │                                ▶  │ ← 缩略图条 + 翻页按钮
  └─────────────────────────────────────────────────────────────────────┘

功能：
  - 通过 QThread 异步加载 75×75 QPixmap 缩略图
  - 支持 Shift+滚轮水平滚动
  - 左右浮动翻页导航按钮
  - 选中状态与主图像查看器同步
  - 双击打开全尺寸缩放查看器
  - 工具栏：添加文件 / 添加文件夹 / 删除 / 清空 + 切换按钮
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
# 架构摘要：
#
# 缩略图条
#   1. VirtualizingStackPanel   → 所有 ThumbnailButton 预先创建（超过100个时已知限制）
#   2. Focusable="false"        → QScrollArea.setFocusPolicy(Qt.NoFocus)
#   3. UseHorizontalMouseWheel  → _scroll_wheel_event（Shift+滚轮）
#   4. ItemTemplate + Converter → ThumbnailLoader 异步 QThread
#   5. PageLeft/PageRight       → _page_left_btn / _page_right_btn 叠加按钮
#   6. SelectionChanged         → _on_thumbnail_clicked → file_selected 信号
#   7. MouseDoubleClick         → double_clicked_path 信号 → 缩放查看器
#   8. Header index "1/10"      → _refresh_header() 手动计算
#   9. ToolTip="{Binding}"       → setToolTip(file_path)
#
# 单步导航（"上一张"/"下一张"）：
#   - _step_left_btn / _step_right_btn → _step_left() / _step_right()
#   - 调用 node.move_prev() / node.move_next()
#   - use_all_image=False 时阻止循环（节点在边界返回 False）
#
# 翻页导航（"上一页"/"下一页"）：
#   - _page_left_btn / _page_right_btn → _page_left() / _page_right()
#   - 将缩略图条滚动一个视口宽度，叠加在 QScrollArea 上
# ═══════════════════════════════════════════════════════════════════════════

# ── 缩略图常量 ───────────────────────────────────────

# 缩略图大小（像素）
THUMB_SIZE = 75
# 缩略图边距（像素）
THUMB_MARGIN = 2
# 缩略图条高度（90px列表 + 顶部/底部内边距）
STRIP_HEIGHT = 106
# 翻页按钮大小
PAGE_BTN_SIZE = 40


# ── 异步缩略图加载器 ────────────────────────────────────────────────

# 视频文件扩展名（用于缩略图检测）
VIDEO_EXTENSIONS = {'.avi', '.mp4', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg'}

class ThumbnailLoader(QThread):
    """后台线程，用于从文件路径加载图像/视频缩略图。

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
        # 调用父类QThread的构造函数
        super().__init__(parent)
        # 文件路径列表
        self._paths: list[str] = []
        # 运行标志
        self._running = True

    def set_paths(self, paths: list[str]):
        """设置要加载的文件路径列表"""
        self._paths = list(paths)

    def stop(self):
        """停止加载"""
        self._running = False

    def run(self):
        """线程运行方法"""
        # 遍历所有文件路径
        for path in self._paths:
            # 如果收到停止信号，退出循环
            if not self._running:
                break
            try:
                # 获取文件扩展名（小写）
                ext = os.path.splitext(path)[1].lower()
                # 如果是视频文件
                if ext in VIDEO_EXTENSIONS:
                    # 捕获视频帧作为缩略图
                    img = self._capture_video_frame(path)
                else:
                    # 否则读取图像文件（彩色模式）
                    img = cv2.imread(path, cv2.IMREAD_COLOR)

                # 如果图像为空，跳过
                if img is None:
                    continue
                # 获取图像高度和宽度
                h, w = img.shape[:2]
                # 计算缩放比例，使图像适配75x75（保持宽高比）
                scale = min(THUMB_SIZE / max(w, 1), THUMB_SIZE / max(h, 1))
                # 如果需要缩小
                if scale < 1.0:
                    # 计算新尺寸
                    new_w, new_h = int(w * scale), int(h * scale)
                    # 缩放图像（使用INTER_AREA插值）
                    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

                # BGR → RGB 转换，然后创建 QImage（为线程安全进行深拷贝）
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                # 获取高度、宽度、通道数
                h, w, ch = rgb.shape
                # 计算每行字节数
                bytes_per_line = ch * w
                # 创建 QImage 并进行深拷贝
                qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                # 发出缩略图就绪信号
                self.thumbnail_ready.emit(path, qimg)
            except Exception:
                # 发生异常时跳过
                continue

    def _capture_video_frame(self, path: str) -> np.ndarray | None:
        """捕获视频文件的第一帧作为缩略图

        参数：
            path: 视频文件路径

        返回：
            第一帧图像，失败则返回 None
        """
        try:
            # 打开视频文件
            cap = cv2.VideoCapture(path)
            # 如果打开失败，返回 None
            if not cap.isOpened():
                return None
            # 读取第一帧
            ret, frame = cap.read()
            # 释放视频捕获对象
            cap.release()
            # 如果读取成功且帧不为空
            if ret and frame is not None:
                # 返回帧图像（稍后可添加 ▶ 叠加指示器表示视频）
                return frame
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
        # 调用父类QPushButton的构造函数
        super().__init__(parent)
        # 保存文件路径
        self.file_path = file_path
        # 像素图对象，初始为None
        self._pixmap: QPixmap | None = None
        # 选中状态标志，初始为False
        self._selected = False

        # 设置固定大小（THUMB_SIZE + 6边距）
        self.setFixedSize(THUMB_SIZE + 6, THUMB_SIZE + 6)
        # 设置光标为手指形状
        self.setCursor(Qt.PointingHandCursor)
        # 设置工具提示为文件路径
        self.setToolTip(file_path)

        # 导入主题管理器
        from gui.theme import theme_manager as _tm
        # 保存主题管理器引用
        self._theme_manager = _tm
        # 刷新样式表
        self._refresh_qss()
        # 连接主题变化信号，主题变化时刷新样式表
        self._theme_manager.theme_changed.connect(lambda _: self._refresh_qss())

        # 连接点击信号，发出带文件路径的点击信号
        self.clicked.connect(lambda: self.clicked_with_path.emit(self.file_path))

    def _refresh_qss(self):
        """刷新样式表"""
        # 获取主题管理器
        tm = self._theme_manager
        # 设置样式表，使用主题颜色
        self.setStyleSheet(self.THEME_QSS.format(
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
        # 保存像素图
        self._pixmap = pixmap
        # 触发重绘
        self.update()

    def set_selected(self, selected: bool):
        """设置选中状态

        参数：
            selected: 是否选中
        """
        # 保存选中状态
        self._selected = selected
        # 设置属性"selected"，用于样式表选择器
        self.setProperty("selected", "true" if selected else "false")
        # 取消样式应用
        self.style().unpolish(self)
        # 重新应用样式
        self.style().polish(self)
        # 触发重绘
        self.update()

    def paintEvent(self, event):
        """绘制事件

        参数：
            event: 绘制事件对象
        """
        # 调用父类的paintEvent（绘制按钮背景）
        super().paintEvent(event)
        # 如果像素图存在且有效
        if self._pixmap and not self._pixmap.isNull():
            # 创建绘图对象
            painter = QPainter(self)
            # 启用平滑像素图变换
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            # 获取像素图宽度和高度
            pw, ph = self._pixmap.width(), self._pixmap.height()
            # 计算居中显示的X坐标
            x = (self.width() - pw) // 2
            # 计算居中显示的Y坐标
            y = (self.height() - ph) // 2
            # 绘制像素图
            painter.drawPixmap(x, y, self._pixmap)
        else:
            # 如果像素图不存在，显示占位符
            painter = QPainter(self)
            # 设置画笔颜色为灰色
            painter.setPen(QColor("#555"))
            # 设置字体
            painter.setFont(QFont("Segoe UI", 9))
            # 在按钮中央绘制"..."
            painter.drawText(self.rect(), Qt.AlignCenter, "...")

    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件

        参数：
            event: 鼠标事件对象
        """
        # 发出双击信号，携带文件路径
        self.double_clicked_path.emit(self.file_path)
        # 接受事件
        event.accept()


# ═══════════════════════════════════════════════════════════════════════════
# 主面板
# ═══════════════════════════════════════════════════════════════════════════

class FlowResourcePanel(QWidget):
    """对齐的图像源面板，带有缩略图条。

    信号：
        file_selected(str) — 点击缩略图时发出（= 选中）
        file_double_clicked(str) — 双击时发出，用于全尺寸缩放查看器
        files_changed() — 添加/删除/清空操作后发出
    """

    # 文件选中信号
    file_selected = pyqtSignal(str)
    # 文件双击信号
    file_double_clicked = pyqtSignal(str)
    # 文件列表变化信号
    files_changed = pyqtSignal()

    def __init__(self, parent=None):
        """初始化流程资源面板

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 当前绑定的源文件节点，初始为None
        self._current_node: "SrcFilesVisionNodeData | None" = None
        # 缩略图字典：键为文件路径，值为ThumbnailButton对象
        self._thumbnails: dict[str, ThumbnailButton] = {}
        # 像素图字典：键为文件路径，值为QPixmap对象
        self._pixmaps: dict[str, QPixmap] = {}
        # 缩略图加载器，初始为None
        self._loader: ThumbnailLoader | None = None
        # 当前选中的文件路径
        self._selected_path: str = ""

        # 设置UI界面
        self._setup_ui()

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

        # ── 头部栏 ──
        # 创建头部控件
        self._header_bar = QWidget()
        # 设置头部固定高度34像素
        self._header_bar.setFixedHeight(34)
        # 创建水平布局
        h_layout = QHBoxLayout(self._header_bar)
        # 设置布局边距
        h_layout.setContentsMargins(8, 4, 6, 4)
        # 设置布局间距
        h_layout.setSpacing(4)

        # 标题标签
        self._title_label = QLabel("图像源")
        # 设置样式
        self._title_label.setStyleSheet("font-size: 11px; font-weight: bold; background: transparent;")
        # 添加到布局
        h_layout.addWidget(self._title_label)

        # 索引标签（显示当前/总数）
        self._index_label = QLabel("0/0")
        # 设置样式
        self._index_label.setStyleSheet("font-size: 11px; background: transparent;")
        # 添加到布局
        h_layout.addWidget(self._index_label)

        # 添加弹性空间（将后续按钮推到右侧）
        h_layout.addStretch(1)

        # 切换按钮组
        # 运行全部按钮（可选中）
        self._run_all_btn = QPushButton("运行全部")
        # 设置为可选中
        self._run_all_btn.setCheckable(True)
        # 设置固定高度24像素
        self._run_all_btn.setFixedHeight(24)
        # 设置焦点策略为无焦点（避免Tab键聚焦）
        self._run_all_btn.setFocusPolicy(Qt.NoFocus)
        # 连接切换信号
        self._run_all_btn.toggled.connect(self._on_run_all_toggled)
        # 添加到布局
        h_layout.addWidget(self._run_all_btn)

        # 自动切换按钮（可选中）
        self._auto_switch_btn = QPushButton("自动切换")
        # 设置为可选中
        self._auto_switch_btn.setCheckable(True)
        # 默认选中
        self._auto_switch_btn.setChecked(True)
        # 设置固定高度24像素
        self._auto_switch_btn.setFixedHeight(24)
        # 设置焦点策略为无焦点
        self._auto_switch_btn.setFocusPolicy(Qt.NoFocus)
        # 连接切换信号
        self._auto_switch_btn.toggled.connect(self._on_auto_switch_toggled)
        # 添加到布局
        h_layout.addWidget(self._auto_switch_btn)

        # 工具栏分隔线
        sep = QFrame()
        # 设置为垂直线
        sep.setFrameShape(QFrame.VLine)
        # 设置样式
        sep.setStyleSheet("background: #505050;")
        # 设置固定宽度1像素
        sep.setFixedWidth(1)
        # 设置固定高度20像素
        sep.setFixedHeight(20)
        # 添加到布局
        h_layout.addWidget(sep)

        # 字体图标动作按钮
        # 添加文件按钮
        self._add_file_btn = FontIconButton(FontIcons.OpenFile, tooltip="添加文件", font_size=13)
        # 连接点击信号
        self._add_file_btn.clicked.connect(self._add_files)
        # 添加到布局
        h_layout.addWidget(self._add_file_btn)

        # 添加文件夹按钮
        self._add_folder_btn = FontIconButton(FontIcons.OpenFolderHorizontal, tooltip="添加文件夹", font_size=13)
        # 连接点击信号
        self._add_folder_btn.clicked.connect(self._add_folder)
        # 添加到布局
        h_layout.addWidget(self._add_folder_btn)

        # 删除按钮
        self._del_btn = FontIconButton(FontIcons.Cancel, tooltip="删除", font_size=13)
        # 连接点击信号
        self._del_btn.clicked.connect(self._delete_current)
        # 初始设为禁用
        self._del_btn.setEnabled(False)
        # 添加到布局
        h_layout.addWidget(self._del_btn)

        # 清空按钮
        self._clear_btn = FontIconButton(FontIcons.Delete, tooltip="清空", font_size=13)
        # 连接点击信号
        self._clear_btn.clicked.connect(self._clear_files)
        # 初始设为禁用
        self._clear_btn.setEnabled(False)
        # 添加到布局
        h_layout.addWidget(self._clear_btn)

        # 单步导航分隔线
        sep2 = QFrame()
        # 设置为垂直线
        sep2.setFrameShape(QFrame.VLine)
        # 设置样式
        sep2.setStyleSheet("background: #505050;")
        # 设置固定宽度1像素
        sep2.setFixedWidth(1)
        # 设置固定高度20像素
        sep2.setFixedHeight(20)
        # 添加到布局
        h_layout.addWidget(sep2)

        # 单步导航 — "上一张" / "下一张"
        # 上一张按钮
        self._step_left_btn = FontIconButton(FontIcons.ChevronLeft, tooltip="上一张", font_size=14)
        # 连接点击信号
        self._step_left_btn.clicked.connect(self._step_left)
        # 初始设为禁用
        self._step_left_btn.setEnabled(False)
        # 添加到布局
        h_layout.addWidget(self._step_left_btn)

        # 下一张按钮
        self._step_right_btn = FontIconButton(FontIcons.ChevronRight, tooltip="下一张", font_size=14)
        # 连接点击信号
        self._step_right_btn.clicked.connect(self._step_right)
        # 初始设为禁用
        self._step_right_btn.setEnabled(False)
        # 添加到布局
        h_layout.addWidget(self._step_right_btn)

        # 头部栏添加到主布局
        layout.addWidget(self._header_bar)

        # ── 带有叠加翻页按钮的缩略图条 ──
        # 创建缩略图条容器
        self._strip_container = QFrame()
        # 设置无边框
        self._strip_container.setFrameShape(QFrame.NoFrame)
        # 创建垂直布局
        strip_layout = QVBoxLayout(self._strip_container)
        # 设置布局边距为0
        strip_layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        strip_layout.setSpacing(0)

        # 滚动区域（用于放置缩略图）
        self._scroll_area = QScrollArea()
        # 设置固定高度（THUMB_SIZE + 14）
        self._scroll_area.setFixedHeight(THUMB_SIZE + 14)
        # 设置控件可调整大小
        self._scroll_area.setWidgetResizable(True)
        # 水平滚动条始终显示
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # 垂直滚动条始终关闭
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 设置无边框
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        # 设置焦点策略为无焦点
        self._scroll_area.setFocusPolicy(Qt.NoFocus)

        # 允许使用 Shift+滚轮 水平滚动
        self._scroll_area.wheelEvent = self._scroll_wheel_event

        # 缩略图容器控件
        self._thumb_container = QWidget()
        # 创建水平布局用于放置缩略图
        self._thumb_layout = QHBoxLayout(self._thumb_container)
        # 设置布局边距（为翻页按钮留空间）
        self._thumb_layout.setContentsMargins(36, 4, 36, 4)
        # 设置布局间距
        self._thumb_layout.setSpacing(2)
        # 设置左对齐
        self._thumb_layout.setAlignment(Qt.AlignLeft)

        # 设置滚动区域的控件为缩略图容器
        self._scroll_area.setWidget(self._thumb_container)
        # 添加到条布局
        strip_layout.addWidget(self._scroll_area)

        # ── 翻页导航叠加按钮 ──
        # 上一页按钮
        self._page_left_btn = QPushButton(FontIcons.PageLeft)
        # 设置固定大小
        self._page_left_btn.setFixedSize(PAGE_BTN_SIZE, PAGE_BTN_SIZE)
        # 设置光标为手指形状
        self._page_left_btn.setCursor(Qt.PointingHandCursor)
        # 设置焦点策略为无焦点
        self._page_left_btn.setFocusPolicy(Qt.NoFocus)
        # 设置工具提示
        self._page_left_btn.setToolTip("上一页")
        # 连接点击信号
        self._page_left_btn.clicked.connect(self._page_left)

        # 下一页按钮
        self._page_right_btn = QPushButton(FontIcons.PageRight)
        # 设置固定大小
        self._page_right_btn.setFixedSize(PAGE_BTN_SIZE, PAGE_BTN_SIZE)
        # 设置光标为手指形状
        self._page_right_btn.setCursor(Qt.PointingHandCursor)
        # 设置焦点策略为无焦点
        self._page_right_btn.setFocusPolicy(Qt.NoFocus)
        # 设置工具提示
        self._page_right_btn.setToolTip("下一页")
        # 连接点击信号
        self._page_right_btn.clicked.connect(self._page_right)

        # 将翻页按钮叠加到滚动区域上
        self._page_left_btn.setParent(self._scroll_area)
        # 设置初始位置（左上角偏移2，垂直居中）
        self._page_left_btn.move(2, (self._scroll_area.height() - PAGE_BTN_SIZE) // 2)
        # 显示按钮
        self._page_left_btn.show()

        self._page_right_btn.setParent(self._scroll_area)
        # 延迟100毫秒后重新定位按钮（等待布局完成）
        QTimer.singleShot(100, self._reposition_page_buttons)
        # 显示按钮
        self._page_right_btn.show()

        # 主题感知样式
        connect_theme(self._refresh_all_qss)

        # 添加到主布局
        layout.addWidget(self._strip_container)
        # 设置面板固定高度（缩略图条高度+头部高度）
        self.setFixedHeight(STRIP_HEIGHT + 34)

    def _refresh_all_qss(self):
        """将所有硬编码颜色更新为当前主题"""
        # 获取主题管理器
        tm = theme_manager
        # 获取各种主题颜色
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
        # 应用样式
        self._run_all_btn.setStyleSheet(toggle_qss)
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
                font-family: "{ICON_FONT_FAMILY}"; font-size: 18px;
            }}
            QPushButton:hover {{ background: {bg_hover}; border-color: {accent}; }}
        """
        # 应用样式
        self._page_left_btn.setStyleSheet(page_qss)
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
            # 否则调用父类的wheelEvent
            QScrollArea.wheelEvent(self._scroll_area, event)

    def resizeEvent(self, event):
        """窗口大小改变事件

        参数：
            event: 大小改变事件对象
        """
        # 调用父类的resizeEvent
        super().resizeEvent(event)
        # 重新定位翻页按钮
        self._reposition_page_buttons()

    def _reposition_page_buttons(self):
        """将翻页按钮定位在面板的左右边缘"""
        # 如果没有翻页按钮属性或按钮为None，返回
        if not hasattr(self, '_page_right_btn') or self._page_right_btn is None:
            return
        # 获取面板总宽度
        pw = self.width()
        # 获取滚动区域高度
        sh = self._scroll_area.height()
        # 计算垂直居中位置
        cy = (sh - PAGE_BTN_SIZE) // 2
        # 移动上一页按钮到左侧
        self._page_left_btn.move(2, cy)
        # 移动下一页按钮到右侧
        self._page_right_btn.move(pw - PAGE_BTN_SIZE - 2, cy)

    # ── 翻页导航 ────────────

    def _page_left(self):
        """向左滚动缩略图条一个视口宽度"""
        # 获取水平滚动条
        bar = self._scroll_area.horizontalScrollBar()
        # 设置滚动条值：当前位置减去视口宽度
        bar.setValue(bar.value() - self._scroll_area.viewport().width())

    def _page_right(self):
        """向右滚动缩略图条一个视口宽度"""
        # 获取水平滚动条
        bar = self._scroll_area.horizontalScrollBar()
        # 设置滚动条值：当前位置加上视口宽度
        bar.setValue(bar.value() + self._scroll_area.viewport().width())

    # ── 单步导航 ─────────

    def _step_left(self):
        """单步切换到上一个文件 — "上一张"

        WPF: ISrcFilesNodeData.MoveNext() 扩展方法（反向方向）。
        调用 node.move_prev()，然后更新缩略图选中状态和头部。
        """
        # 获取当前绑定的节点
        node = self._current_node
        # 如果节点为空或文件列表为空，返回
        if node is None or not node.src_file_paths:
            return
        # 切换到上一个文件，如果失败（边界且use_all_image=False）则返回
        if not node.move_prev():
            return

        # 获取新的当前文件路径
        new_path = node.src_file_path
        # 更新选中路径
        self._selected_path = new_path
        # 遍历所有缩略图，更新选中状态
        for path, btn in self._thumbnails.items():
            btn.set_selected(path == new_path)
        # 滚动使当前缩略图可见
        self._scroll_to_thumbnail(new_path)
        # 刷新头部
        self._refresh_header()
        # 更新动作按钮状态
        self._update_action_buttons()
        # 发出文件选中信号
        self.file_selected.emit(new_path)

    def _step_right(self):
        """单步切换到下一个文件 — "下一张"

        调用 node.move_next()，然后更新缩略图选中状态和头部。
        """
        # 获取当前绑定的节点
        node = self._current_node
        # 如果节点为空或文件列表为空，返回
        if node is None or not node.src_file_paths:
            return
        # 切换到下一个文件，如果失败（边界且use_all_image=False）则返回
        if not node.move_next():
            return

        # 获取新的当前文件路径
        new_path = node.src_file_path
        # 更新选中路径
        self._selected_path = new_path
        # 遍历所有缩略图，更新选中状态
        for path, btn in self._thumbnails.items():
            btn.set_selected(path == new_path)
        # 滚动使当前缩略图可见
        self._scroll_to_thumbnail(new_path)
        # 刷新头部
        self._refresh_header()
        # 更新动作按钮状态
        self._update_action_buttons()
        # 发出文件选中信号
        self.file_selected.emit(new_path)

    def _scroll_to_thumbnail(self, file_path: str):
        """滚动缩略图条，使指定缩略图可见

        参数：
            file_path: 文件路径
        """
        # 获取对应的缩略图按钮
        btn = self._thumbnails.get(file_path)
        # 如果按钮不存在，返回
        if btn is None:
            return
        # 滚动确保按钮可见（左右各留40像素边距）
        self._scroll_area.ensureWidgetVisible(btn, xMargin=40, yMargin=0)

    # ── 节点绑定 ────────────────────────────────────────────────────

    def set_node(self, node: "SrcFilesVisionNodeData | None"):
        """绑定到源文件节点并加载其缩略图

        VisionFlow：显式重建 + showEvent 确保正确的尺寸
        """
        # 停止当前加载器
        self._stop_loader()
        # 保存当前节点引用
        self._current_node = node
        # 清除所有缩略图
        self._clear_thumbnails()
        # 构建缩略图（创建按钮 + 更新容器尺寸）
        self._build_thumbnails()
        # 刷新头部
        self._refresh_header()

        # 如果节点为空，返回
        if node is None:
            return

        # 获取文件路径列表
        paths = getattr(node, 'src_file_paths', []) or []
        # 如果没有文件，返回
        if not paths:
            return

        # 启动异步加载器（按钮已存在，像素图将逐步填充）
        self._loader = ThumbnailLoader(self)
        # 设置要加载的文件路径列表
        self._loader.set_paths(paths)
        # 连接缩略图就绪信号
        self._loader.thumbnail_ready.connect(self._on_thumbnail_ready)
        # 启动线程
        self._loader.start()

    def showEvent(self, event):
        """当面板变为可见时重新调整容器大小 — 保证布局完成后执行"""
        # 调用父类的showEvent
        super().showEvent(event)
        # 在下一个事件循环中更新容器尺寸（确保布局完成）
        QTimer.singleShot(0, self._update_container_size)

    def _stop_loader(self):
        """停止缩略图加载器"""
        # 如果加载器存在且正在运行
        if self._loader and self._loader.isRunning():
            # 发送停止信号
            self._loader.stop()
            # 等待线程结束（最多1秒）
            self._loader.wait(1000)
        # 清空加载器引用
        self._loader = None

    def _on_thumbnail_ready(self, file_path: str, qimg: QImage):
        """收到加载完成的缩略图，在GUI线程中转换为QPixmap

        参数：
            file_path: 文件路径
            qimg: 缩略图QImage对象
        """
        # 将QImage转换为QPixmap
        pixmap = QPixmap.fromImage(qimg)
        # 保存到像素图字典
        self._pixmaps[file_path] = pixmap
        # 获取对应的缩略图按钮
        btn = self._thumbnails.get(file_path)
        # 如果按钮存在，设置缩略图
        if btn:
            btn.set_thumbnail(pixmap)

    def _refresh_header(self):
        """更新头部标题、索引、切换按钮状态和动作按钮状态

        VisionFlow：显式刷新调用
        """
        # 获取当前节点
        node = self._current_node
        # 如果节点为空
        if node is None:
            # 设置标题为"图像源"
            self._title_label.setText("图像源")
            # 设置索引为"0/0"
            self._index_label.setText("0/0")
            # 阻止信号，设置运行全部按钮为未选中
            self._run_all_btn.blockSignals(True)
            self._run_all_btn.setChecked(False)
            self._run_all_btn.blockSignals(False)
            # 阻止信号，设置自动切换按钮为未选中
            self._auto_switch_btn.blockSignals(True)
            self._auto_switch_btn.setChecked(False)
            self._auto_switch_btn.blockSignals(False)
            # 更新动作按钮状态
            self._update_action_buttons()
            return

        # 判断是否为视频源（根据类名）
        is_video = "video" in type(node).__name__.lower()
        # 设置标题
        self._title_label.setText("视频源" if is_video else "图像源")

        # 获取文件路径列表和当前路径
        paths = getattr(node, 'src_file_paths', []) or []
        current = getattr(node, 'src_file_path', '')
        # 总数
        total = len(paths)
        # 当前索引（从1开始）
        idx = 0
        # 如果当前路径存在且有效
        if current and current in paths:
            idx = paths.index(current) + 1

        # 显示当前文件大小
        size_text = ""
        # 如果当前文件存在
        if current and os.path.exists(current):
            try:
                # 获取文件大小
                size = os.path.getsize(current)
                # 格式化显示
                if size >= 1024 * 1024:
                    size_text = f"[{size / 1024 / 1024:.1f} MB]"
                else:
                    size_text = f"[{size / 1024:.1f} KB]"
            except OSError:
                pass
        # 设置索引标签
        self._index_label.setText(f"{idx}/{total}  {size_text}")

        # 设置运行全部按钮状态
        self._run_all_btn.blockSignals(True)
        self._run_all_btn.setChecked(getattr(node, 'use_all_image', False))
        self._run_all_btn.blockSignals(False)

        # 设置自动切换按钮状态
        self._auto_switch_btn.blockSignals(True)
        self._auto_switch_btn.setChecked(getattr(node, 'use_auto_switch', True))
        self._auto_switch_btn.blockSignals(False)

        # 更新动作按钮状态
        self._update_action_buttons()

    def _clear_thumbnails(self):
        """移除所有缩略图按钮和缓存的像素图"""
        # 遍历所有缩略图按钮
        for btn in list(self._thumbnails.values()):
            # 立即隐藏
            btn.hide()
            # 延迟删除
            btn.deleteLater()
        # 清空缩略图字典
        self._thumbnails.clear()
        # 清空像素图字典
        self._pixmaps.clear()
        # 移除所有布局项
        while self._thumb_layout.count():
            # 获取布局项
            item = self._thumb_layout.takeAt(0)
            # 获取控件
            w = item.widget()
            # 如果控件存在
            if w:
                # 立即隐藏
                w.hide()
                # 延迟删除
                w.deleteLater()
        # 清空选中的路径
        self._selected_path = ""
        # 更新容器尺寸
        self._update_container_size()

    def _build_thumbnails(self):
        """为所有文件路径创建缩略图按钮

        VisionFlow：为每个路径手动创建 ThumbnailButton
        """
        # 获取当前节点
        node = self._current_node
        # 如果节点为空，返回
        if node is None:
            return

        # 获取文件路径列表和当前路径
        paths = getattr(node, 'src_file_paths', []) or []
        current = getattr(node, 'src_file_path', '')

        # 遍历所有文件路径
        for path in paths:
            # 创建缩略图按钮
            btn = ThumbnailButton(path)
            # 连接点击信号
            btn.clicked_with_path.connect(self._on_thumbnail_clicked)
            # 连接双击信号
            btn.double_clicked_path.connect(self.file_double_clicked.emit)

            # 如果已有缓存的像素图，设置到按钮
            if path in self._pixmaps:
                btn.set_thumbnail(self._pixmaps[path])

            # 如果是当前选中的文件，设置选中状态
            if path == current:
                btn.set_selected(True)
                self._selected_path = path

            # 添加到布局
            self._thumb_layout.addWidget(btn)
            # 保存到字典
            self._thumbnails[path] = btn

        # 更新容器尺寸
        self._update_container_size()
        # 延迟50毫秒后再次更新（布局稳定后）
        QTimer.singleShot(50, self._update_container_size)

    # ── 交互 ─────────────────────────────────────────────────────

    def _on_thumbnail_clicked(self, file_path: str):
        """处理缩略图点击选中

        参数：
            file_path: 点击的文件路径
        """
        # 如果有当前节点且支持设置src_file_path
        if self._current_node and hasattr(self._current_node, 'src_file_path'):
            # 更新节点的当前文件路径
            self._current_node.src_file_path = file_path

        # 更新选中高亮
        self._selected_path = file_path
        # 遍历所有缩略图，更新选中状态
        for path, btn in self._thumbnails.items():
            btn.set_selected(path == file_path)

        # 刷新头部
        self._refresh_header()
        # 发出文件选中信号
        self.file_selected.emit(file_path)

    def _on_run_all_toggled(self, checked: bool):
        """运行全部按钮切换回调

        参数：
            checked: 是否选中
        """
        # 如果有当前节点
        if self._current_node:
            # 更新节点的use_all_image属性
            self._current_node.use_all_image = checked

    def _on_auto_switch_toggled(self, checked: bool):
        """自动切换按钮切换回调

        参数：
            checked: 是否选中
        """
        # 如果有当前节点
        if self._current_node:
            # 更新节点的use_auto_switch属性
            self._current_node.use_auto_switch = checked

    # ── 文件操作 ────────────────────────────────────

    # 图像文件过滤器
    IMAGE_FILTER = "图像文件 (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp);;所有文件 (*.*)"
    # 支持的图像扩展名
    IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp")

    def _add_files(self):
        """添加文件

        解耦：QFileDialog 在 GUI 层使用，但 node.add_files() 保持纯数据操作。
        节点不知道 Qt 的存在。
        """
        # 打开文件选择对话框
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图像文件", "", self.IMAGE_FILTER
        )
        # 如果没有选择文件或没有当前节点，返回
        if not paths or not self._current_node:
            return
        # 记录是否有已有文件
        had_existing = bool(self._current_node.src_file_paths)
        # 添加文件到节点
        self._current_node.add_files(list(paths))

        # 增量添加缩略图 + 刷新头部
        self._add_thumbnails_incremental(list(paths))
        self._refresh_header()
        self._update_action_buttons()

        # 如果之前没有文件，选中第一个文件并发出信号
        if not had_existing:
            first = self._current_node.src_file_path
            self._selected_path = first
            self.file_selected.emit(first)

        # 发出文件列表变化信号
        self.files_changed.emit()

    def _add_folder(self):
        """添加文件夹"""
        # 打开文件夹选择对话框
        folder = QFileDialog.getExistingDirectory(self, "选择图像文件夹")
        # 如果没有选择文件夹或没有当前节点，返回
        if not folder or not self._current_node:
            return

        # 记录是否有已有文件
        had_existing = bool(self._current_node.src_file_paths)
        # 记录原文件数量
        old_count = len(self._current_node.src_file_paths)

        # 从文件夹添加文件（递归）
        self._current_node.add_files_from_folder(folder, recursive=True)

        # 获取新文件数量
        new_count = len(self._current_node.src_file_paths)
        # 计算新增数量
        added = new_count - old_count
        # 如果没有新增文件，返回
        if added == 0:
            return

        # 获取新增的文件路径
        new_paths = self._current_node.src_file_paths[old_count:]
        # 只为新增文件增量添加缩略图
        self._add_thumbnails_incremental(new_paths)
        self._refresh_header()
        self._update_action_buttons()

        # 如果之前没有文件，选中第一个文件并发出信号
        if not had_existing and self._current_node.src_file_path:
            self._selected_path = self._current_node.src_file_path
            self.file_selected.emit(self._current_node.src_file_path)

        # 发出文件列表变化信号
        self.files_changed.emit()

    def _delete_current(self):
        """删除当前文件

        删除前显示确认对话框。
        """
        # 如果没有当前节点，返回
        if not self._current_node:
            return
        # 获取当前文件路径
        current = self._current_node.src_file_path
        # 如果没有当前文件，返回
        if not current:
            return

        # 显示确认对话框
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除当前图像吗？\n{os.path.basename(current)}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        # 如果用户不确认，返回
        if reply != QMessageBox.Yes:
            return

        # 从节点删除当前文件
        self._current_node.delete_current_file()

        # 增量删除缩略图按钮（不重建全部）
        btn = self._thumbnails.pop(current, None)
        if btn:
            self._thumb_layout.removeWidget(btn)
            btn.deleteLater()
        # 从像素图字典移除
        self._pixmaps.pop(current, None)
        # 更新容器尺寸
        self._update_container_size()

        # 刷新头部
        self._refresh_header()
        # 更新动作按钮状态
        self._update_action_buttons()
        # 发出文件列表变化信号
        self.files_changed.emit()

        # 发出新选中文件（相邻文件）的信号
        new_current = self._current_node.src_file_path
        if new_current:
            self._selected_path = new_current
            self.file_selected.emit(new_current)

    def _clear_files(self):
        """清空所有文件

        清空前显示确认对话框。
        """
        # 如果没有当前节点，返回
        if not self._current_node:
            return
        # 获取文件数量
        count = len(self._current_node.src_file_paths)
        # 如果没有文件，返回
        if count == 0:
            return

        # 显示确认对话框
        reply = QMessageBox.question(
            self, "确认清空",
            f"确定要清空所有图像文件吗？\n当前共有 {count} 个文件",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        # 如果用户不确认，返回
        if reply != QMessageBox.Yes:
            return

        # 清空节点的所有文件
        self._current_node.clear_files()

        # 清空所有缩略图
        self._clear_thumbnails()
        # 刷新头部
        self._refresh_header()
        # 更新动作按钮状态
        self._update_action_buttons()
        # 清空选中路径
        self._selected_path = ""
        # 发出文件列表变化信号
        self.files_changed.emit()

    # ── 增量缩略图构建器 ─

    def _add_thumbnails_incremental(self, new_paths: list[str]):
        """添加新的缩略图按钮，不重建已有的

        VisionFlow：必须为新增文件显式创建按钮
        """
        # 遍历新文件路径
        for path in new_paths:
            # 如果已存在，跳过
            if path in self._thumbnails:
                continue
            # 创建缩略图按钮
            btn = ThumbnailButton(path)
            # 连接点击信号
            btn.clicked_with_path.connect(self._on_thumbnail_clicked)
            # 连接双击信号
            btn.double_clicked_path.connect(self.file_double_clicked.emit)

            # 如果已有缓存的像素图，设置到按钮
            if path in self._pixmaps:
                btn.set_thumbnail(self._pixmaps[path])

            # 添加到布局
            self._thumb_layout.addWidget(btn)
            # 保存到字典
            self._thumbnails[path] = btn

        # 更新容器尺寸
        self._update_container_size()
        # 延迟50毫秒后再次更新
        QTimer.singleShot(50, self._update_container_size)

        # 如果有新文件，启动加载器加载它们的缩略图
        if new_paths:
            # 创建新加载器
            loader = ThumbnailLoader(self)
            # 设置文件路径
            loader.set_paths(new_paths)
            # 连接就绪信号
            loader.thumbnail_ready.connect(self._on_thumbnail_ready)
            # 启动线程
            loader.start()

    # ── 按钮状态管理 ──────────────

    def _update_container_size(self):
        """设置容器最小宽度（根据缩略图数量 + 间距 + 边距）

        显式计算以避免 Qt 布局 sizeHint() 的时序问题。
        计算公式：数量 * (按钮宽 + 间距) - 间距 + 左边距 + 右边距
        """
        # 获取缩略图数量
        count = len(self._thumbnails)
        # 如果没有缩略图
        if count == 0:
            # 设置最小尺寸为0
            self._thumb_container.setMinimumSize(0, 0)
            return
        # 按钮宽度（THUMB_SIZE + 6）
        btn_w = THUMB_SIZE + 6
        # 布局间距
        spacing = self._thumb_layout.spacing()
        # 布局边距
        margins = self._thumb_layout.contentsMargins()
        # 计算总宽度
        total_w = count * (btn_w + spacing) - spacing + margins.left() + margins.right()
        # 设置容器最小宽度
        self._thumb_container.setMinimumSize(total_w, 0)

    def _update_action_buttons(self):
        """根据文件列表状态启用/禁用动作按钮和步进按钮"""
        # 获取当前节点
        node = self._current_node
        # 是否有文件
        has_files = node is not None and len(getattr(node, 'src_file_paths', []) or []) > 0
        # 是否有选中的文件
        has_selection = bool(getattr(node, 'src_file_path', '') if node else '')
        # 设置删除按钮启用状态
        self._del_btn.setEnabled(has_files and has_selection)
        # 设置清空按钮启用状态
        self._clear_btn.setEnabled(has_files)
        # 设置上一张按钮启用状态
        self._step_left_btn.setEnabled(has_files and has_selection)
        # 设置下一张按钮启用状态
        self._step_right_btn.setEnabled(has_files and has_selection)

    # ── 公共API ──────────────────────────────────────────────────────

    def refresh(self):
        """强制从当前节点完全刷新缩略图"""
        # 停止加载器
        self._stop_loader()
        # 清除所有缩略图
        self._clear_thumbnails()
        # 构建缩略图
        self._build_thumbnails()
        # 刷新头部
        self._refresh_header()

        # 获取当前节点
        node = self._current_node
        # 如果节点为空，返回
        if node is None:
            return
        # 获取文件路径列表
        paths = getattr(node, 'src_file_paths', []) or []
        # 如果有文件
        if paths:
            # 创建加载器
            self._loader = ThumbnailLoader(self)
            # 设置文件路径
            self._loader.set_paths(paths)
            # 连接就绪信号
            self._loader.thumbnail_ready.connect(self._on_thumbnail_ready)
            # 启动线程
            self._loader.start()

    def refresh_selection(self):
        """轻量级刷新 — 仅更新头部索引和缩略图高亮

        "自动切换" 等效：在"运行全部"过程中，当 UseAutoSwitch=ON 时，
        SrcFilePath 绑定会自动更新缩略图 ListBox 的选中项。
        在 VisionFlow 中，我们在 auto_switch 为 ON 时从 FILE_ITERATION_NEXT
        事件处理器显式调用此方法。
        """
        # 获取当前节点
        node = self._current_node
        # 如果节点为空，返回
        if node is None:
            return

        # 获取当前文件路径
        current = getattr(node, 'src_file_path', '')
        # 刷新头部（更新索引/文件名）
        self._refresh_header()

        # 更新缩略图选中高亮
        for path, btn in self._thumbnails.items():
            btn.set_selected(path == current)
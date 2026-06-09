"""节点列表视图
宽模式(>90px)：
  ┌─────────────────────────────┐
  │ 流程资源            [≡|⊞]    │  ← 头部 + FontIconToggleButton（树/网格视图切换）
  ├─────────────────────────────┤
  │ 🔍 搜索模块...               │  ← 搜索框
  ├─────────────────────────────┤
  │ ★ 收藏                      │  ← 收藏部分
  │   [icon] [icon] ...         │
  │ 图像数据源                    │  ← 分组
  │   [icon] [icon] ...         │
  │ ...                         │
  ├─────────────────────────────┤
  │  5 个分组 · 32 个节点 ★ 3    │  ← 统计页脚
  └─────────────────────────────┘

窄模式(≤90px)：
  ┌────┐
  │ S  │  ← 紧凑的垂直纯图标列表
  │ P  │     悬停时显示工具提示
  │ B  │
  │ M  │
  │ ...│
  └────┘

树形视图：QTreeWidget 包含分组 → 节点，名称 + 描述列
网格视图：QScrollArea + QGridLayout 平铺图标按钮（现有的 ToolboxPanel 模式）
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QScrollArea, QFrame, QGridLayout,
                              QTreeWidget, QTreeWidgetItem, QPushButton,
                              QSizePolicy, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings, QMimeData, QPoint, QSize
from PyQt5.QtGui import QDrag, QFont, QColor, QIcon, QPainter, QPixmap

from core.node_group import node_data_group_manager, NodeGroup
from core.node_base import NodeBase
from gui.font_icons import FontIcons, FontIconTextBlock, FontIconToggleButton, icon_font


# ── 分组元数据 ─────────────────────────────────────

# 分组元数据字典：定义每个分组的颜色和图标
GROUP_META = {
    # 图像数据源分组：蓝色，Photo2图标
    "图像数据源":   {"color": "#4a9eff", "icon": FontIcons.Photo2},
    # 系统数据源分组：深蓝色，Folder图标
    "系统数据源":   {"color": "#5c6bc0", "icon": FontIcons.Folder},
    # 图像预处理模块分组：橙色，Color图标
    "图像预处理模块": {"color": "#ff8c00", "icon": FontIcons.Color},
    # 滤波模块分组：紫色，Filter图标
    "滤波模块":     {"color": "#9c27b0", "icon": FontIcons.Filter},
    # 图像分割提取模块分组：粉色，Cut图标
    "图像分割提取模块": {"color": "#e91e63", "icon": FontIcons.Cut},
    # 形态学模块分组：青色，⬒符号
    "形态学模块":   {"color": "#00bcd4", "icon": "⬒"},
    # 逻辑模块分组：深橙色，⇄符号
    "逻辑模块":     {"color": "#ff5722", "icon": "⇄"},
    # 模板匹配模块分组：绿色，⌖符号
    "模板匹配模块": {"color": "#4caf50", "icon": "⌖"},
    # 对象识别模块分组：红色，◉符号
    "对象识别模块": {"color": "#f44336", "icon": "◉"},
    # 特征提取模块分组：橙色，✣符号
    "特征提取模块": {"color": "#ff9800", "icon": "✣"},
    # 网络通讯模块分组：棕色，⌁符号
    "网络通讯模块": {"color": "#795548", "icon": "⌁"},
    # 结果输出模块分组：灰蓝色，↗符号
    "结果输出模块": {"color": "#607d8b", "icon": "↗"},
    # Onnx通用模型分组：深粉色，AI文字
    "Onnx通用模型": {"color": "#c2185b", "icon": "AI"},
    # 其他模块分组：灰蓝色，◇符号
    "其他模块":     {"color": "#607d8b", "icon": "◇"},
    # 视频处理模块分组：棕色，Video图标
    "视频处理模块": {"color": "#8d6e63", "icon": FontIcons.Video},
    # 收藏分组：金色，FavoriteStar图标
    "★ 收藏":      {"color": "#d7ba7d", "icon": FontIcons.FavoriteStar},
}


def _group_meta(group_name: str):
    """获取分组元数据，如果找不到则返回默认值"""
    # 从GROUP_META中获取分组元数据，如果不存在则返回默认的灰色和🧩图标
    return GROUP_META.get(group_name, {"color": "#607d8b", "icon": "🧩"})


# ── 节点瓷砖（网格视图）──────────────────────────────────────────────────

class NodeTileButton(QFrame):
    """网格视图的平铺节点按钮 — 拖拽源 + 点击添加"""

    # 激活信号：双击时发出，携带节点类型名称
    activated = pyqtSignal(str)
    # 选中信号：单击时发出，携带节点类型名称
    selected = pyqtSignal(str)
    # 收藏切换信号：收藏按钮点击时发出，携带节点类型名称
    favorite_toggled = pyqtSignal(str)

    # 瓷砖宽度（像素）
    TILE_W = 108
    # 瓷砖高度（像素）
    TILE_H = 78

    def __init__(self, type_name: str, display_name: str, description: str,
                 group_name: str, is_favorite: bool = False, parent=None):
        """初始化节点瓷砖按钮

        参数：
            type_name: 节点类型名称
            display_name: 显示名称
            description: 描述信息
            group_name: 分组名称
            is_favorite: 是否为收藏节点
            parent: 父对象
        """
        # 调用父类QFrame的构造函数
        super().__init__(parent)
        # 保存节点类型名称
        self.type_name = type_name
        # 保存显示名称
        self.display_name = display_name
        # 保存描述信息
        self.description = description
        # 保存分组名称
        self.group_name = group_name
        # 保存是否为收藏
        self.is_favorite = is_favorite
        # 选中状态标志，初始为False
        self._selected = False
        # 拖拽起始位置
        self._drag_start_pos = QPoint()
        # 拖拽是否已开始标志
        self._drag_started = False

        # 获取分组元数据
        meta = _group_meta(group_name)
        # 保存分组颜色
        self._color = meta["color"]
        # 保存分组图标
        self._icon_text = meta["icon"]

        # 设置光标为张开手形状
        self.setCursor(Qt.OpenHandCursor)
        # 设置固定大小
        self.setFixedSize(self.TILE_W, self.TILE_H)
        # 设置无边框
        self.setFrameShape(QFrame.NoFrame)
        # 构建UI界面
        self._build_ui()
        # 刷新样式
        self._refresh_style()

    def _build_ui(self):
        """构建UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距
        layout.setContentsMargins(8, 7, 8, 7)
        # 设置布局间距
        layout.setSpacing(4)

        # 创建顶部水平布局
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        # 图标徽章
        icon_badge = QLabel(self._icon_text)
        # 设置图标居中对齐
        icon_badge.setAlignment(Qt.AlignCenter)
        # 设置固定大小28x28
        icon_badge.setFixedSize(28, 28)
        # 设置图标徽章样式：背景色，圆角，白色文字
        icon_badge.setStyleSheet(
            f"background: {self._color}; border-radius: 6px; color: white;"
            "font-size: 14px; font-weight: 700;"
            "font-family: 'Segoe UI Symbol', 'Microsoft YaHei UI';"
        )
        # 添加到顶部布局
        top.addWidget(icon_badge)
        # 添加弹性空间
        top.addStretch()

        # 星标（收藏标记）
        fav = QLabel(FontIcons.FavoriteStar if self.is_favorite else "")
        # 设置星标样式：金色
        fav.setStyleSheet("color: #d7ba7d; font-size: 12px; font-weight: bold;")
        # 添加到顶部布局
        top.addWidget(fav)
        # 将顶部布局添加到主布局
        layout.addLayout(top)

        # 标题标签
        title = QLabel(self.display_name)
        # 允许换行
        title.setWordWrap(True)
        # 设置对齐方式：左对齐，顶部对齐
        title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        # 设置标题样式
        title.setStyleSheet("color: #dcdcdc; font-size: 11px; font-weight: 600;")
        # 设置描述信息为工具提示
        title.setToolTip(self.description)
        # 添加标题到布局，拉伸因子为1（占据剩余空间）
        layout.addWidget(title, 1)

        # 设置整体工具提示
        self.setToolTip(f"{self.display_name}\n{self.description}\n类型: {self.type_name}")

    def set_selected(self, selected: bool):
        """设置选中状态"""
        # 保存选中状态
        self._selected = selected
        # 刷新样式
        self._refresh_style()

    def _refresh_style(self):
        """刷新样式"""
        # 根据选中状态、收藏状态确定边框颜色
        if self._selected:
            border = "#0078d4"  # 选中时：蓝色
        elif self.is_favorite:
            border = "#d7ba7d"  # 收藏时：金色
        else:
            border = "#3f3f46"  # 默认：深灰色
        # 根据选中状态确定背景颜色
        bg = "#2f3640" if self._selected else "#252526"
        # 设置样式表
        self.setStyleSheet(
            f"NodeTileButton {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}"
            f"NodeTileButton:hover {{ background: #2d2d30; border-color: #0078d4; }}"
        )

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        # 如果按下的是左键
        if event.button() == Qt.LeftButton:
            # 记录拖拽起始位置
            self._drag_start_pos = event.pos()
            # 重置拖拽已开始标志
            self._drag_started = False
            # 发出选中信号
            self.selected.emit(self.type_name)
            # 设置光标为握紧手形状
            self.setCursor(Qt.ClosedHandCursor)
            # 接受事件
            event.accept()
            return
        # 调用父类的mousePressEvent
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        # 如果不是左键按下，调用父类方法
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        # 如果移动距离小于拖拽起始距离阈值
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
        # 设置拖拽已开始标志
        self._drag_started = True
        # 开始拖拽
        self._start_drag()
        # 设置光标为张开手形状
        self.setCursor(Qt.OpenHandCursor)
        # 接受事件
        event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        # 设置光标为张开手形状
        self.setCursor(Qt.OpenHandCursor)
        # 如果是左键释放且没有拖拽过
        if event.button() == Qt.LeftButton and not self._drag_started:
            # 发出选中信号
            self.selected.emit(self.type_name)
            # 接受事件
            event.accept()
            return
        # 调用父类的mouseReleaseEvent
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件"""
        # 如果是左键双击
        if event.button() == Qt.LeftButton:
            # 发出激活信号
            self.activated.emit(self.type_name)
            # 接受事件
            event.accept()
            return
        # 调用父类的mouseDoubleClickEvent
        super().mouseDoubleClickEvent(event)

    def _start_drag(self):
        """开始拖拽操作"""
        # 创建拖拽对象
        drag = QDrag(self)
        # 创建MIME数据
        mime = QMimeData()
        # 设置拖拽文本为节点类型名称
        mime.setText(self.type_name)
        # 设置MIME数据
        drag.setMimeData(mime)
        # 设置拖拽时的预览图像为当前控件的截图
        drag.setPixmap(self.grab())
        # 设置热点为控件中心
        drag.setHotSpot(self.rect().center())
        # 执行拖拽（复制动作）
        drag.exec_(Qt.CopyAction)


# ── 紧凑窄模式瓷砖 ───────────────────────────────────────────────

class NarrowNodeButton(QPushButton):
    """窄模式（≤90px）垂直列表的紧凑纯图标按钮"""

    # 激活信号：单击时发出，携带节点类型名称
    activated = pyqtSignal(str)

    def __init__(self, type_name: str, display_name: str, group_name: str,
                 parent=None):
        """初始化窄模式按钮

        参数：
            type_name: 节点类型名称
            display_name: 显示名称
            group_name: 分组名称
            parent: 父对象
        """
        # 调用父类QPushButton的构造函数
        super().__init__(parent)
        # 保存节点类型名称
        self.type_name = type_name
        # 保存显示名称
        self.display_name = display_name
        # 获取分组元数据
        meta = _group_meta(group_name)
        # 保存分组颜色
        self._color = meta["color"]
        # 保存分组图标
        self._icon = meta["icon"]

        # 设置按钮文本为图标
        self.setText(self._icon)
        # 设置工具提示：显示名称和分组
        self.setToolTip(f"{display_name}\n{group_name}")
        # 设置固定大小28x28
        self.setFixedSize(28, 28)
        # 设置光标为手指形状
        self.setCursor(Qt.PointingHandCursor)

        # 设置样式表
        self.setStyleSheet(
            f"NarrowNodeButton {{ background: transparent; border: 1px solid #3f3f46;"
            f"border-radius: 4px; color: {self._color}; font-size: 14px; font-weight: bold;"
            f"font-family: 'Segoe UI Symbol', 'Microsoft YaHei UI'; }}"
            f"NarrowNodeButton:hover {{ background: #3e3e42; border-color: #0078d4; }}"
        )
        # 连接点击信号到激活信号
        self.clicked.connect(lambda: self.activated.emit(self.type_name))


# ═══════════════════════════════════════════════════════════════════════════
# 主组合控件
# ═══════════════════════════════════════════════════════════════════════════

class NodeListView(QWidget):
    """完整的节点列表，包含头部、搜索、树/网格切换和窄模式。

    这是放入 GridSplitterBox 的内容控件。内部通过堆叠视图处理宽模式(>90px)和窄模式(≤90px)。

    信号：
        node_type_selected(str): 用户选中节点类型时发出
        node_type_activated(str): 用户双击/确认时发出
    """

    # 节点类型选中信号
    node_type_selected = pyqtSignal(str)
    # 节点类型激活信号
    node_type_activated = pyqtSignal(str)
    # 收藏列表变化信号
    favorites_changed = pyqtSignal()

    # QSettings中收藏列表的键名
    FAVORITES_KEY = "Toolbox/Favorites"
    # QSettings中最近使用列表的键名
    RECENTS_KEY = "Toolbox/Recents"
    # 收藏分组显示名称
    FAVORITES_GROUP_NAME = "★ 收藏"
    # 最近使用分组显示名称
    RECENTS_GROUP_NAME = "🕐 最近使用"
    # 最大最近使用记录数量
    MAX_RECENTS = 10

    def __init__(self, parent=None):
        """初始化节点列表视图

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 收藏列表，存储节点类型名称
        self._favorites: list[str] = []
        # 最近使用列表，存储节点类型名称
        self._recents: list[str] = []
        # 当前选中的节点类型名称
        self._selected_type: str | None = None
        # 瓷砖按钮字典：键为节点类型名称，值为NodeTileButton对象
        self._tile_widgets: dict[str, NodeTileButton] = {}
        # 窄模式按钮字典：键为节点类型名称，值为NarrowNodeButton对象
        self._narrow_buttons: dict[str, NarrowNodeButton] = {}
        # 视图是否为树形视图（False=网格视图，默认）
        self._view_is_tree = False

        # 加载持久化存储的列表
        self._load_persisted_lists()
        # 设置UI界面
        self._setup_ui()
        # 刷新视图
        self.refresh()

    # ── 持久化存储 ─────────────────────────────────────────────────────

    def _load_persisted_lists(self):
        """从QSettings加载收藏列表和最近使用列表"""
        # 创建QSettings对象
        s = QSettings()
        # 获取收藏列表
        favs = s.value(self.FAVORITES_KEY, [])
        # 如果是字符串，转换为列表
        if isinstance(favs, str):
            favs = [favs] if favs else []
        # 保存收藏列表
        self._favorites = list(favs) if favs else []

        # 获取最近使用列表
        recs = s.value(self.RECENTS_KEY, [])
        # 如果是字符串，转换为列表
        if isinstance(recs, str):
            recs = [recs] if recs else []
        # 保存最近使用列表
        self._recents = list(recs) if recs else []

    def _save_favorites(self):
        """保存收藏列表到QSettings"""
        # 创建QSettings对象
        s = QSettings()
        # 保存收藏列表
        s.setValue(self.FAVORITES_KEY, self._favorites)
        # 同步到磁盘
        s.sync()
        # 发出收藏变化信号
        self.favorites_changed.emit()

    def _save_recents(self):
        """保存最近使用列表到QSettings"""
        # 创建QSettings对象
        s = QSettings()
        # 保存最近使用列表（只保存前MAX_RECENTS条）
        s.setValue(self.RECENTS_KEY, self._recents[:self.MAX_RECENTS])
        # 同步到磁盘
        s.sync()

    def is_favorite(self, type_name: str) -> bool:
        """判断节点是否为收藏"""
        return type_name in self._favorites

    def add_favorite(self, type_name: str):
        """添加节点到收藏"""
        # 如果节点类型不为空且不在收藏列表中
        if type_name and type_name not in self._favorites:
            # 添加到收藏列表
            self._favorites.append(type_name)
            # 保存收藏列表
            self._save_favorites()
            # 刷新视图
            self.refresh()

    def remove_favorite(self, type_name: str):
        """从收藏中移除节点"""
        # 如果节点在收藏列表中
        if type_name in self._favorites:
            # 从收藏列表移除
            self._favorites.remove(type_name)
            # 保存收藏列表
            self._save_favorites()
            # 刷新视图
            self.refresh()

    def toggle_favorite(self, type_name: str):
        """切换收藏状态"""
        # 如果已经是收藏，则移除；否则添加
        if self.is_favorite(type_name):
            self.remove_favorite(type_name)
        else:
            self.add_favorite(type_name)

    def record_use(self, type_name: str):
        """记录节点类型使用（用于最近使用列表）"""
        # 如果已在最近使用列表中，先移除
        if type_name in self._recents:
            self._recents.remove(type_name)
        # 插入到列表开头
        self._recents.insert(0, type_name)
        # 限制列表长度
        self._recents = self._recents[:self.MAX_RECENTS]
        # 保存最近使用列表
        self._save_recents()

    # ── UI设置 ────────────────────────────────────────────────────────

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

        # ── 头部栏："流程资源" + 右侧的树/网格切换按钮 ──
        # 创建头部控件
        header = QWidget()
        # 设置头部固定高度32像素
        header.setFixedHeight(32)
        # 设置头部样式表
        header.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        # 创建水平布局
        h_layout = QHBoxLayout(header)
        # 设置布局边距
        h_layout.setContentsMargins(8, 0, 2, 0)
        # 设置布局间距
        h_layout.setSpacing(2)

        # 标题标签
        title = QLabel("流程资源")
        # 设置标题样式
        title.setStyleSheet("color: #dcdcdc; font-size: 12px; font-weight: bold; background: transparent;")
        # 添加到布局，拉伸因子为1
        h_layout.addWidget(title, 1)

        # 视图切换按钮：树形视图（AlignLeft）/ 网格视图（CaretBottomRightSolidCenter8）
        self._view_toggle = FontIconToggleButton(
            checked_icon=FontIcons.AlignLeft,                      # 选中状态图标：左对齐（树形视图）
            unchecked_icon=FontIcons.CaretBottomRightSolidCenter8, # 未选中状态图标：右下角箭头（网格视图）
            font_size=12,                                          # 图标字体大小
        )
        # 默认：网格视图（未选中）
        self._view_toggle.setChecked(False)
        # 设置工具提示
        self._view_toggle.setToolTip("切换树/网格视图")
        # 设置固定大小
        self._view_toggle.setFixedSize(26, 24)
        # 设置样式表
        self._view_toggle.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #999; padding: 2px; }"
            "QPushButton:hover { background: #3e3e42; color: #dcdcdc; }"
            "QPushButton:checked { color: #dcdcdc; }"
        )
        # 连接切换信号到处理函数
        self._view_toggle.toggled.connect(self._on_view_toggled)
        # 添加到布局
        h_layout.addWidget(self._view_toggle)
        # 头部添加到主布局
        layout.addWidget(header)

        # ── 搜索框 ──
        # 创建搜索框
        self._search_box = QLineEdit()
        # 设置占位符文本
        self._search_box.setPlaceholderText("搜索模块 / 中文名称...")
        # 设置样式表
        self._search_box.setStyleSheet(
            "QLineEdit { background: #333337; color: #dcdcdc; border: none;"
            "border-bottom: 1px solid #3f3f46; padding: 6px 8px; font-size: 12px; }"
            "QLineEdit:focus { border-bottom: 1px solid #0078d4; }"
        )
        # 连接文本变化信号到刷新方法
        self._search_box.textChanged.connect(lambda: self.refresh())
        # 添加到主布局
        layout.addWidget(self._search_box)

        # ── 堆叠视图：树形视图 / 网格视图 ──
        # 创建堆叠容器
        self._view_stack = QFrame()
        # 设置无边框
        self._view_stack.setFrameShape(QFrame.NoFrame)
        # 创建垂直布局
        view_stack_layout = QVBoxLayout(self._view_stack)
        # 设置布局边距为0
        view_stack_layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        view_stack_layout.setSpacing(0)

        # 树形视图
        self._tree = self._create_tree_view()
        # 添加到布局
        view_stack_layout.addWidget(self._tree)

        # 网格视图（滚动区域）
        self._grid_scroll = QScrollArea()
        # 设置控件可调整大小
        self._grid_scroll.setWidgetResizable(True)
        # 设置无边框
        self._grid_scroll.setFrameShape(QFrame.NoFrame)
        # 设置样式表
        self._grid_scroll.setStyleSheet("QScrollArea { background: #252526; border: none; }")
        # 禁用水平滚动条
        self._grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 网格内容容器
        self._grid_content = QWidget()
        # 创建垂直布局
        self._grid_content_layout = QVBoxLayout(self._grid_content)
        # 设置布局边距
        self._grid_content_layout.setContentsMargins(8, 8, 8, 8)
        # 设置布局间距
        self._grid_content_layout.setSpacing(10)
        # 设置滚动区域的控件
        self._grid_scroll.setWidget(self._grid_content)
        # 添加到布局
        view_stack_layout.addWidget(self._grid_scroll)

        # 默认：网格视图可见，树形视图隐藏
        self._tree.hide()
        self._grid_scroll.show()

        # 堆叠视图添加到主布局，拉伸因子为1
        layout.addWidget(self._view_stack, 1)

        # ── 统计标签（页脚）──
        self._stats_label = QLabel()
        # 设置样式表
        self._stats_label.setStyleSheet(
            "color: #666; font-size: 10px; padding: 3px 8px; background: #1e1e1e;"
            "border-top: 1px solid #3f3f46;"
        )
        # 添加到主布局
        layout.addWidget(self._stats_label)

    # ── 树形视图 ───────────────────────────────────────────────────────

    def _create_tree_view(self) -> QTreeWidget:
        """创建树形视图控件"""
        # 创建树形控件
        tree = QTreeWidget()
        # 设置表头标签
        tree.setHeaderLabels(["模块名称", "描述"])
        # 设置列宽
        tree.setColumnWidth(0, 130)
        tree.setColumnWidth(1, 120)
        # 设置缩进
        tree.setIndentation(16)
        # 设置根节点可装饰
        tree.setRootIsDecorated(True)
        # 启用动画效果
        tree.setAnimated(True)
        # 双击可展开
        tree.setExpandsOnDoubleClick(True)
        # 设置样式表
        tree.setStyleSheet("""
            QTreeWidget {
                background: #252526; color: #dcdcdc; border: none;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 3px 4px;
                border: none;
            }
            QTreeWidget::item:hover {
                background: #2d2d30;
            }
            QTreeWidget::item:selected {
                background: #094771;
            }
            QTreeWidget::branch {
                background: transparent;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                border-image: none;
            }
            QHeaderView::section {
                background: #2d2d30; color: #999; padding: 4px 8px;
                border: none; border-bottom: 1px solid #3f3f46; font-size: 11px;
            }
        """)
        # 启用拖拽
        tree.setDragEnabled(True)
        # 连接项点击信号
        tree.itemClicked.connect(self._on_tree_item_clicked)
        # 连接项双击信号
        tree.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        # 返回树形控件
        return tree

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, col: int):
        """树形视图项点击事件处理"""
        # 获取节点类型名称
        type_name = item.data(0, Qt.UserRole)
        # 如果是节点项（有type_name）
        if type_name:
            # 发出节点类型选中信号
            self.node_type_selected.emit(type_name)

    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, col: int):
        """树形视图项双击事件处理"""
        # 获取节点类型名称
        type_name = item.data(0, Qt.UserRole)
        # 如果是节点项（有type_name）
        if type_name:
            # 发出节点类型激活信号
            self.node_type_activated.emit(type_name)

    # ── 视图切换 ────────────────────────────────────────────────────

    def _on_view_toggled(self, checked: bool):
        """视图切换按钮状态变化处理"""
        # 更新视图模式标志
        self._view_is_tree = checked
        # 根据checked状态显示/隐藏树形视图和网格视图
        self._tree.setVisible(checked)
        self._grid_scroll.setVisible(not checked)
        # 刷新视图
        self.refresh()

    def set_view_mode(self, tree: bool):
        """以编程方式切换视图模式

        参数：
            tree: True表示树形视图，False表示网格视图
        """
        # 设置切换按钮的选中状态
        self._view_toggle.setChecked(tree)

    # ── 数据构建 ──────────────────────────────────────────────────

    def _all_node_metas(self, keyword: str = "") -> list[dict]:
        """收集所有节点类型元数据，可选关键字过滤

        参数：
            keyword: 搜索关键字

        返回：
            节点元数据字典列表
        """
        # 结果列表
        result = []
        # 类型注册表
        type_registry = {}

        # 遍历所有分组
        for group in node_data_group_manager.get_all_groups():
            # 遍历分组中的节点类型
            for node_type in group.node_types:
                # 获取类型名称
                type_name = node_type.__name__
                # 记录到注册表
                type_registry[type_name] = node_type

                # 解析显示名称
                display_name = type_name
                try:
                    # 尝试实例化节点获取显示名称
                    instance = node_type()
                    candidate = getattr(instance, 'display_name', '') or getattr(instance, 'name', '')
                    if isinstance(candidate, str) and candidate.strip():
                        display_name = candidate.strip()
                except Exception:
                    pass

                # 获取文档字符串作为描述
                doc = (node_type.__doc__ or '').strip().splitlines()
                description = doc[0] if doc else display_name

                # 获取分组元数据
                meta = _group_meta(group.name)
                # 添加到结果列表
                result.append({
                    "type_name": type_name,           # 类型名称
                    "display_name": display_name,     # 显示名称
                    "description": description,       # 描述
                    "group_name": group.name,         # 分组名称
                    "color": meta["color"],           # 颜色
                    "icon": meta["icon"],             # 图标
                    "is_favorite": self.is_favorite(type_name),  # 是否收藏
                    "is_recent": type_name in self._recents,     # 是否最近使用
                })

        # 如果有搜索关键字
        if keyword:
            kw = keyword.lower()
            # 过滤结果
            result = [
                m for m in result
                if kw in f"{m['display_name']} {m['description']} {m['type_name']} {m['group_name']}".lower()
            ]

        return result

    # ── 刷新 ────────────────────────────────────────────────────────

    def refresh(self):
        """重建当前活动的视图（树形视图或网格视图）"""
        # 根据当前视图模式刷新对应的视图
        if self._view_is_tree:
            self._refresh_tree()
        else:
            self._refresh_grid()

    def _refresh_tree(self):
        """填充树形视图"""
        # 清空树形控件
        self._tree.clear()
        # 获取搜索关键字
        keyword = self.search_keyword

        # 收集所有节点元数据
        all_metas = self._all_node_metas(keyword)
        # 按分组分组
        grouped: dict[str, list[dict]] = {}
        for m in all_metas:
            grouped.setdefault(m["group_name"], []).append(m)

        # 首先添加特殊部分
        # 最近使用部分
        if self._recents:
            recent_metas = [m for m in all_metas if m["type_name"] in self._recents]
            if recent_metas:
                # 按最近使用顺序排序
                recent_metas.sort(key=lambda m: self._recents.index(m["type_name"]))
                # 添加分组
                parent = self._add_tree_group(self._tree, self.RECENTS_GROUP_NAME, "#d7ba7d")
                # 添加节点
                for m in recent_metas:
                    self._add_tree_node(parent, m)

        # 收藏部分
        if self._favorites:
            fav_metas = [m for m in all_metas if m["is_favorite"]]
            if fav_metas:
                # 添加分组
                parent = self._add_tree_group(self._tree, self.FAVORITES_GROUP_NAME, "#d7ba7d")
                # 添加节点
                for m in fav_metas:
                    self._add_tree_node(parent, m)

        # 按顺序添加标准分组
        for group in node_data_group_manager.get_all_groups():
            metas = grouped.get(group.name, [])
            if not metas:
                continue
            # 添加分组
            parent = self._add_tree_group(self._tree, group.name, _group_meta(group.name)["color"])
            # 添加节点
            for m in metas:
                self._add_tree_node(parent, m)

        # 展开所有分组
        self._tree.expandAll()
        # 更新统计信息
        self._update_stats(all_metas)

    def _add_tree_group(self, tree: QTreeWidget, name: str, color: str) -> QTreeWidgetItem:
        """添加树形视图分组"""
        # 创建分组项
        item = QTreeWidgetItem(tree)
        # 设置名称
        item.setText(0, name)
        # 设置前景色
        item.setForeground(0, QColor(color))
        # 获取字体
        font = item.font(0)
        # 设置粗体
        font.setBold(True)
        # 设置字体
        item.setFont(0, font)
        # 禁用拖拽
        item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled)
        # 返回分组项
        return item

    def _add_tree_node(self, parent: QTreeWidgetItem, meta: dict):
        """添加树形视图节点"""
        # 创建节点项
        item = QTreeWidgetItem(parent)
        # 设置名称
        item.setText(0, meta["display_name"])
        # 设置描述
        item.setText(1, meta["description"])
        # 存储节点类型名称到第一列的用户数据
        item.setData(0, Qt.UserRole, meta["type_name"])
        # 设置工具提示
        item.setToolTip(0, f"{meta['display_name']}\n{meta['description']}\n类型: {meta['type_name']}")
        item.setToolTip(1, meta["description"])
        # 设置第一列的前景色为分组颜色
        item.setForeground(0, QColor(meta["color"]))
        # 返回节点项
        return item

    def _refresh_grid(self):
        """填充网格视图"""
        # 清空格子内容布局
        while self._grid_content_layout.count():
            item = self._grid_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # 清空瓷砖按钮字典
        self._tile_widgets.clear()

        # 获取搜索关键字
        keyword = self.search_keyword
        # 收集所有节点元数据
        all_metas = self._all_node_metas(keyword)

        # 可见分组计数
        visible_groups = 0
        # 可见节点计数
        visible_nodes = 0

        # 最近使用部分
        if self._recents:
            recent_metas = [m for m in all_metas if m["type_name"] in self._recents]
            if recent_metas:
                # 按最近使用顺序排序
                recent_metas.sort(key=lambda m: self._recents.index(m["type_name"]))
                # 构建分组
                count = self._build_grid_group(self.RECENTS_GROUP_NAME, recent_metas)
                visible_groups += 1
                visible_nodes += count

        # 收藏部分
        if self._favorites:
            fav_metas = [m for m in all_metas if m["is_favorite"]]
            if fav_metas:
                # 构建分组
                count = self._build_grid_group(self.FAVORITES_GROUP_NAME, fav_metas)
                visible_groups += 1
                visible_nodes += count

        # 标准分组
        grouped: dict[str, list[dict]] = {}
        for m in all_metas:
            grouped.setdefault(m["group_name"], []).append(m)

        # 遍历所有分组
        for group in node_data_group_manager.get_all_groups():
            metas = grouped.get(group.name, [])
            if not metas:
                continue
            # 构建分组
            count = self._build_grid_group(group.name, metas)
            visible_groups += 1
            visible_nodes += count

        # 添加弹性空间到底部
        self._grid_content_layout.addStretch(1)
        # 更新统计信息
        self._update_stats(all_metas, visible_groups, visible_nodes)

    def _build_grid_group(self, group_name: str, metas: list[dict]) -> int:
        """构建网格视图分组。返回可见节点数量"""
        # 如果没有节点，返回0
        if not metas:
            return 0

        # 获取分组元数据
        meta = _group_meta(group_name)
        # 创建分组容器
        section = QWidget()
        # 创建垂直布局
        section_layout = QVBoxLayout(section)
        # 设置布局边距
        section_layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距
        section_layout.setSpacing(6)

        # 创建分组合头
        header = QLabel(f"{meta['icon']}  {group_name}")
        # 设置头样式
        header.setStyleSheet(
            f"color: {meta['color']}; font-size: 12px; font-weight: bold; padding: 2px 2px;"
        )
        # 添加到布局
        section_layout.addWidget(header)

        # 创建网格容器
        grid_host = QWidget()
        # 创建网格布局
        grid = QGridLayout(grid_host)
        # 设置布局边距
        grid.setContentsMargins(0, 0, 0, 0)
        # 设置水平间距
        grid.setHorizontalSpacing(8)
        # 设置垂直间距
        grid.setVerticalSpacing(8)

        # 遍历节点元数据
        for i, m in enumerate(metas):
            # 创建瓷砖按钮
            tile = NodeTileButton(
                type_name=m["type_name"],
                display_name=m["display_name"],
                description=m["description"],
                group_name=m["group_name"],
                is_favorite=m["is_favorite"],
            )
            # 连接激活信号
            tile.activated.connect(self._on_tile_activated)
            # 连接选中信号
            tile.selected.connect(self._set_selected_type)
            # 连接收藏切换信号
            tile.favorite_toggled.connect(self.toggle_favorite)
            # 保存瓷砖按钮
            self._tile_widgets[m["type_name"]] = tile
            # 计算行和列（每行2个）
            row, col = divmod(i, 2)
            # 添加到网格布局
            grid.addWidget(tile, row, col)

            # 如果节点是当前选中的，设置选中状态
            if m["type_name"] == self._selected_type:
                tile.set_selected(True)

        # 将网格容器添加到分组布局
        section_layout.addWidget(grid_host)
        # 将分组添加到内容布局
        self._grid_content_layout.addWidget(section)
        # 返回节点数量
        return len(metas)

    def _set_selected_type(self, type_name: str):
        """设置选中的节点类型"""
        # 保存选中的类型名称
        self._selected_type = type_name
        # 更新所有瓷砖按钮的选中状态
        for current, tile in self._tile_widgets.items():
            tile.set_selected(current == type_name)

    def _on_tile_activated(self, type_name: str):
        """瓷砖按钮激活（双击）事件"""
        # 发出节点类型激活信号
        self.node_type_activated.emit(type_name)

    def _update_stats(self, metas: list[dict], groups: int = 0, nodes: int = 0):
        """更新统计信息"""
        # 获取搜索关键字
        keyword = self.search_keyword
        # 如果没有传入分组和节点数量，则计算
        if not groups:
            groups_set = set(m["group_name"] for m in metas)
            groups = len(groups_set)
            nodes = len(metas)
        # 构建统计文本部分
        parts = [f"  {groups} 个分组 · {nodes} 个节点"]
        # 如果有收藏
        if self._favorites:
            parts.append(f"★ 收藏 {len(self._favorites)} 个")
        # 如果有最近使用
        if self._recents:
            parts.append(f"🕐 最近 {len(self._recents)} 个")
        # 设置统计标签文本
        self._stats_label.setText(" · ".join(parts))

    # ── 窄模式 ─────────────────────────────────────────────────────

    def create_narrow_widget(self) -> QWidget:
        """创建紧凑的窄模式垂直图标列表（≤90px）

        返回适合 GridSplitterBox.set_narrow_content() 的 QWidget
        """
        # 创建容器控件
        widget = QWidget()
        # 创建垂直布局
        layout = QVBoxLayout(widget)
        # 设置布局边距
        layout.setContentsMargins(4, 12, 4, 4)
        # 设置布局间距
        layout.setSpacing(4)

        # 收集所有节点元数据
        all_metas = self._all_node_metas()
        # 按分组分组
        grouped: dict[str, list[dict]] = {}
        for m in all_metas:
            grouped.setdefault(m["group_name"], []).append(m)

        # 首先显示收藏，然后显示分组
        # 收藏部分
        if self._favorites:
            fav_metas = [m for m in all_metas if m["is_favorite"]]
            for m in fav_metas[:6]:  # 窄模式下限制数量
                # 创建窄模式按钮
                btn = NarrowNodeButton(m["type_name"], m["display_name"], m["group_name"])
                # 连接激活信号
                btn.activated.connect(self.node_type_activated.emit)
                # 添加到布局
                layout.addWidget(btn)
                # 保存按钮引用
                self._narrow_buttons[m["type_name"]] = btn

        # 遍历所有分组
        for group in node_data_group_manager.get_all_groups():
            metas = grouped.get(group.name, [])
            for m in metas[:3]:  # 窄模式下每个分组限制3个
                # 创建窄模式按钮
                btn = NarrowNodeButton(m["type_name"], m["display_name"], m["group_name"])
                # 连接激活信号
                btn.activated.connect(self.node_type_activated.emit)
                # 添加到布局
                layout.addWidget(btn)
                # 保存按钮引用
                self._narrow_buttons[m["type_name"]] = btn

        # 添加弹性空间
        layout.addStretch(1)
        # 返回容器控件
        return widget

    # ── 属性 ─────────────────────────────────────────────────────

    @property
    def search_keyword(self) -> str:
        """获取搜索关键字（已转换为小写并去除首尾空格）"""
        return self._search_box.text().strip().lower()

    def get_selected_node_type(self) -> str | None:
        """获取当前选中的节点类型名称"""
        return self._selected_type
"""工具箱面板 — GridSplitterBox + GroupBox"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QScrollArea, QFrame, QGridLayout,
                              QTreeWidget, QTreeWidgetItem, QPushButton,
                              QApplication, QLayout)
from PyQt5.QtCore import Qt, QEvent, pyqtSignal, QSettings, QMimeData, QPoint, QRect, QSize
from PyQt5.QtGui import QDrag, QColor

from core.node_group import node_data_group_manager
from gui.font_icons import FontIcons, FontIconToggleButton, ICON_FONT_FAMILY
from gui.widgets.grid_splitter_box import GridSplitterBox, WIDTH_THRESHOLD
from core.constants import get_group_meta as _group_meta
from gui.theme import theme_manager, connect_theme


# ── 节点瓷砖按钮（网格视图）───────────────────────────────────────────

class _NodeTileButton(QFrame):
    """网格视图的平铺节点按钮。拖拽源 + 点击/双击。"""

    # 激活信号（双击时发出）
    activated = pyqtSignal(str)
    # 选中信号（单击时发出）
    selected = pyqtSignal(str)
    # 收藏切换信号
    favorite_toggled = pyqtSignal(str)

    def __init__(self, type_name: str, display_name: str, description: str,
                 group_name: str, is_favorite: bool = False, parent=None):
        """初始化节点瓷砖按钮

        参数：
            type_name: 节点类型名称
            display_name: 显示名称
            description: 描述
            group_name: 分组名称
            is_favorite: 是否为收藏
            parent: 父对象
        """
        # 调用父类QFrame的构造函数
        super().__init__(parent)
        # 保存节点类型名称
        self.type_name = type_name
        # 保存是否为收藏
        self.is_favorite = is_favorite
        # 选中状态标志，初始为False
        self._selected = False
        # 拖拽起始点
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
        # 设置固定大小130x32
        self.setFixedSize(130, 32)
        # 设置无边框
        self.setFrameShape(QFrame.NoFrame)
        # 构建UI
        self._build_ui(display_name, description)
        # 刷新样式
        self._refresh_style()

    def _build_ui(self, display_name: str, description: str):
        """构建UI界面

        参数：
            display_name: 显示名称
            description: 描述
        """
        # 创建水平布局
        layout = QHBoxLayout(self)
        # 设置布局边距
        layout.setContentsMargins(6, 4, 6, 4)
        # 设置布局间距为6
        layout.setSpacing(6)

        # 左侧：图标
        icon = QLabel(self._icon_text)
        # 设置居中对齐
        icon.setAlignment(Qt.AlignCenter)
        # 设置固定大小22x22
        icon.setFixedSize(22, 22)
        # 设置样式
        icon.setStyleSheet(
            f"color: {self._color}; font-size: 15px; font-weight: bold;"
            f"font-family: '{ICON_FONT_FAMILY}';"
            "background: transparent; border: none;"
        )
        # 添加到布局
        layout.addWidget(icon)

        # 中间：标题文本（较大，左对齐）
        title = QLabel(display_name)
        # 设置左对齐、垂直居中
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        # 设置样式
        title.setStyleSheet("color: #000000; font-size: 12px; font-weight: 700;")
        # 设置工具提示为描述
        title.setToolTip(description)
        # 添加到布局，拉伸因子为1
        layout.addWidget(title, 1)

        # 右侧：收藏星标
        fav = QLabel(FontIcons.FavoriteStar if self.is_favorite else "")
        # 设置样式
        fav.setStyleSheet("color: #d7ba7d; font-size: 12px; font-weight: bold;")
        # 添加到布局
        layout.addWidget(fav)

        # 设置整体工具提示
        self.setToolTip(f"{display_name}\n{description}\n类型: {self.type_name}")

    def set_selected(self, selected: bool):
        """设置选中状态

        参数：
            selected: 是否选中
        """
        # 保存选中状态
        self._selected = selected
        # 刷新样式
        self._refresh_style()

    def _refresh_style(self):
        """刷新样式"""
        # 根据状态确定边框颜色
        if self._selected:
            border = "#0078d4"           # 选中：蓝色
        elif self.is_favorite:
            border = "#d7ba7d"           # 收藏：金色
        else:
            border = "#d0d0d0"           # 默认：浅灰色
        # 根据状态确定背景色
        bg = "#e8f0fe" if self._selected else "#ffffff"
        # 设置样式表
        self.setStyleSheet(
            f"_NodeTileButton {{ background: {bg}; border: 1px solid {border}; border-radius: 4px; }}"
            f"_NodeTileButton:hover {{ background: #f0f0f0; border-color: #0078d4; }}"
        )

    def mousePressEvent(self, event):
        """鼠标按下事件

        参数：
            event: 鼠标事件对象
        """
        # 如果按下的是左键
        if event.button() == Qt.LeftButton:
            # 记录拖拽起始点
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
        """鼠标移动事件

        参数：
            event: 鼠标事件对象
        """
        # 如果不是左键按下，调用父类方法
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        # 如果移动距离小于拖拽起始距离阈值
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
        # 设置拖拽已开始标志
        self._drag_started = True
        # 创建拖拽对象
        drag = QDrag(self)
        # 创建MIME数据
        mime = QMimeData()
        # 设置文本为节点类型名称
        mime.setText(self.type_name)
        # 设置MIME数据
        drag.setMimeData(mime)
        # 设置拖拽预览图像
        drag.setPixmap(self.grab())
        # 设置热点为控件中心
        drag.setHotSpot(self.rect().center())
        # 执行拖拽
        drag.exec_(Qt.CopyAction)
        # 设置光标为张开手形状
        self.setCursor(Qt.OpenHandCursor)
        # 接受事件
        event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件

        参数：
            event: 鼠标事件对象
        """
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
        """鼠标双击事件

        参数：
            event: 鼠标事件对象
        """
        # 如果是左键双击
        if event.button() == Qt.LeftButton:
            # 发出激活信号
            self.activated.emit(self.type_name)
            # 接受事件
            event.accept()
            return
        # 调用父类的mouseDoubleClickEvent
        super().mouseDoubleClickEvent(event)


# ── 窄模式：分组图标按钮 + 弹窗 ──────

# 跟踪当前活动的窄弹窗以实现互斥
_active_popup_button = None


class _DraggableCard(QPushButton):
    """弹窗节点卡片，支持单击选择和拖拽到画布"""

    def __init__(self, type_name: str, display_name: str, color: str, icon: str, parent=None):
        """初始化可拖拽卡片

        参数：
            type_name: 节点类型名称
            display_name: 显示名称
            color: 颜色
            icon: 图标
            parent: 父对象
        """
        # 调用父类QPushButton的构造函数
        super().__init__(parent)
        # 保存节点类型名称
        self._type_name = type_name
        # 拖拽起始点
        self._drag_start_pos = QPoint()
        # 拖拽是否已开始标志
        self._drag_started = False

        # 设置固定大小130x32
        self.setFixedSize(130, 32)
        # 设置光标为手指形状
        self.setCursor(Qt.PointingHandCursor)
        # 设置工具提示
        self.setToolTip(f"{display_name}\n类型: {type_name}")
        # 设置样式
        self.setStyleSheet(
            "QPushButton {"
            "background: white; border: 1px solid #d0d0d0; border-radius: 4px;"
            "}"
            "QPushButton:hover {"
            "background: #f0f0f0; border-color: #0078d4;"
            "}"
        )

        # 创建内部水平布局
        inner = QHBoxLayout(self)
        # 设置布局边距
        inner.setContentsMargins(6, 4, 6, 4)
        # 设置布局间距为6
        inner.setSpacing(6)

        # 图标标签
        icon_lbl = QLabel(icon)
        # 设置居中对齐
        icon_lbl.setAlignment(Qt.AlignCenter)
        # 设置固定大小22x22
        icon_lbl.setFixedSize(22, 22)
        # 设置样式
        icon_lbl.setStyleSheet(
            f"color: {color}; font-size: 15px; font-weight: bold;"
            f"font-family: '{ICON_FONT_FAMILY}';"
            "background: transparent; border: none;"
        )
        # 添加到布局
        inner.addWidget(icon_lbl)

        # 文本标签
        text_lbl = QLabel(display_name)
        # 设置左对齐、垂直居中
        text_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        # 设置样式
        text_lbl.setStyleSheet(
            "color: #000000; font-size: 12px; font-weight: 700; background: transparent; border: none;"
        )
        # 添加到布局，拉伸因子为1
        inner.addWidget(text_lbl, 1)

    def mousePressEvent(self, event):
        """鼠标按下事件

        参数：
            event: 鼠标事件对象
        """
        # 如果按下的是左键
        if event.button() == Qt.LeftButton:
            # 记录拖拽起始点
            self._drag_start_pos = event.pos()
            # 重置拖拽已开始标志
            self._drag_started = False
            # 接受事件
            event.accept()
            return
        # 调用父类的mousePressEvent
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件

        参数：
            event: 鼠标事件对象
        """
        # 如果不是左键按下，调用父类方法
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        # 如果移动距离小于拖拽起始距离阈值
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
        # 设置拖拽已开始标志
        self._drag_started = True
        # 创建拖拽对象
        drag = QDrag(self)
        # 创建MIME数据
        mime = QMimeData()
        # 设置文本为节点类型名称
        mime.setText(self._type_name)
        # 设置MIME数据
        drag.setMimeData(mime)
        # 设置拖拽预览图像
        drag.setPixmap(self.grab())
        # 设置热点为控件中心
        drag.setHotSpot(self.rect().center())
        # 执行拖拽
        drag.exec_(Qt.CopyAction)
        # 接受事件
        event.accept()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件

        参数：
            event: 鼠标事件对象
        """
        # 如果是左键释放且没有拖拽过
        if event.button() == Qt.LeftButton and not self._drag_started:
            # 发出点击信号
            self.clicked.emit()
        # 调用父类的mouseReleaseEvent
        super().mouseReleaseEvent(event)


class _NarrowGroupPopup(QFrame):
    """
    窄模式下的分组弹出窗口
    """

    # 节点类型选择信号
    node_type_selected = pyqtSignal(str)

    def __init__(self, group_name: str, icon: str, color: str, metas: list[dict], parent=None):
        """初始化窄模式分组弹出窗口

        参数：
            group_name: 分组名称
            icon: 分组图标
            color: 分组颜色
            metas: 节点元信息列表
            parent: 父对象
        """
        # 调用父类QFrame的构造函数，设置窗口标志为Popup（弹出窗口）+ FramelessWindowHint（无边框）
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint)
        # 设置属性：背景不透明（否则阴影无法正常显示）
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        # 设置样式表
        self.setStyleSheet(
            "_NarrowGroupPopup { "
            "background: #2d2d30; "           # 深色背景
            "border: 1px solid #555; "        # 灰色边框
            "border-radius: 6px; "            # 圆角
            "}"
        )

        # 创建垂直布局作为主布局
        layout = QVBoxLayout(self)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

        # 头部容器
        header = QWidget()
        # 设置头部样式：深灰色背景，顶部两个角圆角6px，底部直角
        header.setStyleSheet(
            "background: #353538; "
            "border-radius: 6px 6px 0 0;"
        )
        # 创建头部水平布局
        hl = QHBoxLayout(header)
        # 设置布局边距
        hl.setContentsMargins(10, 6, 8, 6)
        # 设置布局间距为4px
        hl.setSpacing(4)

        # 分组名称标签
        name_lbl = QLabel(group_name)
        # 设置名称标签样式
        name_lbl.setStyleSheet(
            f"color: {color}; "                # 文字颜色
            f"font-size: 12px; "              # 字体大小12px
            f"font-weight: bold; "            # 粗体
            "background: transparent; "       # 透明背景
            "border: none; "                  # 无边框
        )
        # 添加到头部布局，拉伸因子为1（占满剩余空间）
        hl.addWidget(name_lbl, 1)

        # 图标标签
        icon_lbl = QLabel(icon)
        # 设置图标标签样式
        icon_lbl.setStyleSheet(
            f"color: {color}; "                # 图标颜色
            f"font-size: 14px; "              # 字体大小14px
            f"font-weight: bold; "            # 粗体
            f"font-family: '{ICON_FONT_FAMILY}'; "  # 图标字体
            "background: transparent; "       # 透明背景
            "border: none; "                  # 无边框
        )
        # 添加到头部布局
        hl.addWidget(icon_lbl)

        # 将头部添加到主布局
        layout.addWidget(header)

        # 主体容器
        body = QWidget()
        # 设置主体样式：深灰色背景，底部两个角圆角6px，顶部直角
        body.setStyleSheet(
            "background: #2d2d30; "
            "border-radius: 0 0 6px 6px;"
        )
        # 创建主体垂直布局
        bl = QVBoxLayout(body)
        # 设置布局边距为8px
        bl.setContentsMargins(8, 8, 8, 8)
        # 设置布局间距为6px
        bl.setSpacing(6)

        # 网格容器
        grid_widget = QWidget()
        # 创建网格布局
        grid = QGridLayout(grid_widget)
        # 设置网格布局边距为0
        grid.setContentsMargins(0, 0, 0, 0)
        # 设置网格水平间距为6px
        grid.setHorizontalSpacing(6)
        # 设置网格垂直间距为6px
        grid.setVerticalSpacing(6)

        # 遍历节点元信息列表
        for i, m in enumerate(metas):
            # 计算行列（每行2个）
            row, col = divmod(i, 2)
            # 创建节点卡片并添加到网格
            grid.addWidget(self._make_node_card(m), row, col)

        # 将网格容器添加到主体布局
        bl.addWidget(grid_widget)
        # 将主体容器添加到主布局
        layout.addWidget(body)
        # 调整弹出窗口大小以适应内容
        self.adjustSize()

    def _make_node_card(self, m: dict) -> QPushButton:
        """创建节点卡片

        参数：
            m: 节点元信息字典

        返回：
            _DraggableCard 按钮
        """
        # 创建可拖拽卡片
        btn = _DraggableCard(m["type_name"], m["display_name"], m["color"], m["icon"])
        # 连接点击信号，点击时关闭弹出窗口
        btn.clicked.connect(lambda: self.close())
        return btn


class _NarrowGroupButton(QPushButton):
    """
    窄模式下的图标组按钮
    无边框，无背景——仅显示大号图标。
    互斥：一次只能打开一个按钮的弹出窗口。
    """

    # 节点类型选择信号
    node_type_selected = pyqtSignal(str)

    def __init__(self, group_name: str, icon: str, color: str, metas: list[dict], parent=None):
        """初始化窄模式分组按钮

        参数：
            group_name: 分组名称
            icon: 分组图标
            color: 分组颜色
            metas: 节点元信息列表
            parent: 父对象
        """
        # 调用父类QPushButton的构造函数
        super().__init__(parent)
        # 保存分组名称
        self._group_name = group_name
        # 保存图标
        self._icon = icon
        # 保存颜色
        self._color = color
        # 保存节点元信息列表
        self._metas = metas
        # 弹出窗口实例，初始为None
        self._popup = None

        # 设置按钮文本为图标
        self.setText(icon)
        # 设置工具提示为分组名称
        self.setToolTip(group_name)
        # 设置为可选中（切换状态）
        self.setCheckable(True)
        # 设置光标为手指形状
        self.setCursor(Qt.PointingHandCursor)
        # 设置按钮样式
        self.setStyleSheet(
            f"_NarrowGroupButton {{"
            f"background: transparent; "      # 透明背景
            f"border: none; "                 # 无边框
            f"color: {color}; "               # 图标颜色
            f"font-size: 25px; "              # 字体大小25px
            f"font-family: '{ICON_FONT_FAMILY}'; "  # 图标字体
            f"padding: 2px 0; "               # 上下内边距2px
            f"}}"
            f"_NarrowGroupButton:hover {{ color: #dcdcdc; }}"  # 悬停：亮灰色
            f"_NarrowGroupButton:checked {{ color: #0078d4; }}"  # 选中：蓝色
        )
        # 连接切换状态信号
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        """按钮切换状态回调

        参数：
            checked: 是否选中
        """
        if checked:
            # 如果选中，显示弹出窗口
            self._show_popup()
        else:
            # 如果取消选中，隐藏弹出窗口
            self._hide_popup()

    def _show_popup(self):
        """显示弹出窗口"""
        # 声明全局变量，跟踪当前活跃的弹出按钮
        global _active_popup_button
        # 互斥：如果已经有活跃的弹出按钮且不是当前按钮
        if _active_popup_button and _active_popup_button is not self:
            # 取消之前按钮的选中状态，触发其隐藏弹窗
            _active_popup_button.setChecked(False)
        # 将当前按钮设置为活跃按钮
        _active_popup_button = self

        # 确保没有残留的弹出窗口
        self._hide_popup()
        # 获取当前分组元数据
        gmeta = _group_meta(self._group_name)
        # 优先使用分组元数据中的图标，如果没有则使用按钮的图标
        icon = gmeta.get("icon", self._icon)
        # 创建弹出窗口实例
        self._popup = _NarrowGroupPopup(self._group_name, icon, self._color, self._metas)
        # 连接节点选择信号
        self._popup.node_type_selected.connect(self._on_node_selected)
        # 安装事件过滤器（用于检测弹窗关闭）
        self._popup.installEventFilter(self)
        # 计算弹窗位置：按钮右侧偏移4px
        pos = self.mapToGlobal(QPoint(self.width() + 4, 0))
        # 移动弹窗到计算的位置
        self._popup.move(pos)
        # 显示弹窗
        self._popup.show()

    def _hide_popup(self):
        """隐藏弹出窗口"""
        # 声明全局变量
        global _active_popup_button
        # 如果当前按钮是活跃按钮
        if _active_popup_button is self:
            # 重置活跃按钮
            _active_popup_button = None
        # 如果弹出窗口存在
        if self._popup:
            # 移除事件过滤器
            self._popup.removeEventFilter(self)
            # 关闭弹出窗口
            self._popup.close()
            # 删除弹出窗口实例
            self._popup.deleteLater()
            # 重置引用
            self._popup = None

    def _on_node_selected(self, type_name: str):
        """节点选择回调

        参数：
            type_name: 节点类型名称
        """
        # 发出节点类型选择信号
        self.node_type_selected.emit(type_name)
        # 取消按钮选中状态
        self.setChecked(False)

    def eventFilter(self, obj, event):
        """事件过滤器

        参数：
            obj: 事件对象
            event: 事件

        返回：
            是否过滤事件
        """
        # 如果事件来自弹出窗口且类型为Hide（隐藏）
        if obj is self._popup and event.type() == QEvent.Hide:
            # 取消按钮选中状态
            self.setChecked(False)
        # 调用父类事件过滤器
        return super().eventFilter(obj, event)


# ── 流式布局 ────────────────────────────────────────

class FlowLayout(QLayout):
    """水平流式布局 — 项超出宽度时换行到下一行"""

    def __init__(self, parent=None, margin=0, h_spacing=8, v_spacing=8):
        """初始化流式布局

        参数：
            parent: 父对象
            margin: 边距
            h_spacing: 水平间距
            v_spacing: 垂直间距
        """
        # 调用父类QLayout的构造函数
        super().__init__(parent)
        # 布局项列表
        self._items: list[QLayout] = []
        # 水平间距
        self._h_spacing = h_spacing
        # 垂直间距
        self._v_spacing = v_spacing
        # 设置内容边距
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        """添加布局项

        参数：
            item: 布局项
        """
        self._items.append(item)

    def count(self):
        """返回布局项数量

        返回：
            布局项数量
        """
        return len(self._items)

    def itemAt(self, index):
        """获取指定索引的布局项

        参数：
            index: 索引

        返回：
            布局项或None
        """
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        """移除并返回指定索引的布局项

        参数：
            index: 索引

        返回：
            被移除的布局项或None
        """
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        """返回布局的扩展方向

        返回：
            无扩展方向
        """
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        """是否支持根据宽度计算高度

        返回：
            True
        """
        return True

    def heightForWidth(self, width):
        """根据给定宽度计算所需高度

        参数：
            width: 宽度

        返回：
            所需高度
        """
        # 干运行布局计算高度
        return self._do_layout(QRect(0, 0, width, 0), dry_run=True)

    def setGeometry(self, rect):
        """设置布局几何

        参数：
            rect: 矩形区域
        """
        # 调用父类的setGeometry
        super().setGeometry(rect)
        # 实际布局
        self._do_layout(rect, dry_run=False)

    def sizeHint(self):
        """返回建议大小

        返回：
            最小大小
        """
        return self.minimumSize()

    def minimumSize(self):
        """返回最小大小

        返回：
            最小大小
        """
        # 创建空尺寸
        s = QSize()
        # 遍历所有布局项，找到最大尺寸
        for item in self._items:
            s = s.expandedTo(item.minimumSize())
        # 获取内容边距
        m = self.contentsMargins()
        # 返回加上边距后的尺寸
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect: QRect, dry_run: bool) -> int:
        """执行布局计算

        参数：
            rect: 布局矩形
            dry_run: 是否为干运行（只计算不实际布局）

        返回：
            布局高度
        """
        # 获取内容边距
        m = self.contentsMargins()
        # 当前行起始X坐标
        x = rect.x() + m.left()
        # 当前行起始Y坐标
        y = rect.y() + m.top()
        # 当前行高度
        line_h = 0
        # 右边界
        right = rect.right() - m.right()

        # 遍历所有布局项
        for item in self._items:
            # 获取项的建议大小
            hint = item.sizeHint()
            # 如果不是行首，需要添加水平间距
            space_x = self._h_spacing if x > rect.x() + m.left() else 0
            # 如果当前行放不下该项
            if x + space_x + hint.width() > right and line_h > 0:
                # 换行：X重置为左边界
                x = rect.x() + m.left()
                # Y增加当前行高度 + 垂直间距
                y += line_h + self._v_spacing
                # 重置行高度
                line_h = 0
                # 重置间距
                space_x = 0
            # 如果不是干运行
            if not dry_run:
                # 设置项的位置和大小
                item.setGeometry(QRect(QPoint(x + space_x, y), hint))
            # X坐标向右移动
            x += space_x + hint.width()
            # 更新当前行高度
            line_h = max(line_h, hint.height())

        # 返回总高度
        return y + line_h - rect.y() + m.bottom()


# ── 可折叠分组 ────────────────────────────

class _CollapsibleGroup(QWidget):
    """可折叠分组面板

    头部：展开箭头 + 图标 + 分组名称，可点击。
    主体：_NodeTileButton 的流式布局，折叠时隐藏。
    默认：IsExpanded="False"。
    """

    def __init__(self, group_name: str, icon: str, color: str,
                 metas: list[dict], expanded: bool = False, parent=None):
        """初始化可折叠分组

        参数：
            group_name: 分组名称
            icon: 分组图标
            color: 分组颜色
            metas: 节点元信息列表
            expanded: 是否展开
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 保存展开状态
        self._expanded = expanded

        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

        # ── 头部（可点击切换）──
        # 创建头部按钮
        self._header = QPushButton()
        # 设置为扁平按钮
        self._header.setFlat(True)
        # 设置光标为手指形状
        self._header.setCursor(Qt.PointingHandCursor)
        # 设置头部样式
        self._header.setStyleSheet(
            "QPushButton { background: #2d2d30; border: none;"
            "border-bottom: 1px solid #3f3f46; padding: 5px 6px; text-align: left; }"
            "QPushButton:hover { background: #353538; }"
        )
        # 连接点击信号到_toggle方法
        self._header.clicked.connect(self._toggle)

        # 创建头部水平布局
        hl = QHBoxLayout(self._header)
        # 设置布局边距为0
        hl.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为4px
        hl.setSpacing(4)

        # 箭头标签
        self._arrow = QLabel("▾" if self._expanded else "▸")
        # 设置固定宽度14px
        self._arrow.setFixedWidth(14)
        # 设置箭头样式
        self._arrow.setStyleSheet(
            "color: #999; font-size: 10px; background: transparent; border: none;"
        )
        # 添加到头部布局
        hl.addWidget(self._arrow)

        # 图标标签
        icon_lbl = QLabel(icon)
        # 设置图标样式
        icon_lbl.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: bold;"
            f"font-family: '{ICON_FONT_FAMILY}';"
            "background: transparent; border: none;"
        )
        # 添加到头部布局
        hl.addWidget(icon_lbl)

        # 名称标签
        name_lbl = QLabel(group_name)
        # 设置名称样式
        name_lbl.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        # 添加到头部布局，拉伸因子为1
        hl.addWidget(name_lbl, 1)

        # 数量标签
        count_lbl = QLabel(str(len(metas)))
        # 设置数量样式
        count_lbl.setStyleSheet(
            "color: #888; font-size: 10px; background: transparent; border: none;"
        )
        # 添加到头部布局
        hl.addWidget(count_lbl)

        # 将头部添加到主布局
        layout.addWidget(self._header)

        # ── 主体（可折叠，2列网格）──
        # 创建主体容器
        self._body = QWidget()
        # 设置透明背景
        self._body.setStyleSheet("background: transparent;")
        # 创建网格布局
        self._body_grid = QGridLayout(self._body)
        # 设置布局边距
        self._body_grid.setContentsMargins(6, 6, 6, 6)
        # 设置水平间距为4px
        self._body_grid.setHorizontalSpacing(4)
        # 设置垂直间距为4px
        self._body_grid.setVerticalSpacing(4)
        # 设置第0列拉伸因子为1
        self._body_grid.setColumnStretch(0, 1)
        # 设置第1列拉伸因子为1
        self._body_grid.setColumnStretch(1, 1)
        # 根据展开状态设置可见性
        self._body.setVisible(self._expanded)
        # 添加到主布局
        layout.addWidget(self._body)

    def _toggle(self):
        """切换展开/折叠状态"""
        # 取反展开状态
        self._expanded = not self._expanded
        # 设置主体可见性
        self._body.setVisible(self._expanded)
        # 更新箭头符号
        self._arrow.setText("▾" if self._expanded else "▸")

    def add_tile(self, tile, index: int):
        """添加瓷砖按钮

        参数：
            tile: 瓷砖按钮
            index: 索引（用于计算行列）
        """
        # 计算行列（每行2列）
        row, col = divmod(index, 2)
        # 添加到网格布局
        self._body_grid.addWidget(tile, row, col)


# ── 可拖拽树形控件 ──────────────────────────────────────────────────

class _DraggableTreeWidget(QTreeWidget):
    """带有正确拖拽MIME数据的QTreeWidget，用于节点类型名称。"""

    def mimeData(self, items):
        """创建MIME数据

        参数：
            items: 选中的项列表

        返回：
            QMimeData对象
        """
        # 调用父类方法创建MIME数据
        mime = super().mimeData(items)
        # 如果有选中的项
        if items:
            # 获取第一项用户数据中的节点类型名称
            type_name = items[0].data(0, Qt.UserRole)
            # 如果类型名称存在
            if type_name:
                # 设置MIME数据的文本
                mime.setText(type_name)
        return mime


# ═══════════════════════════════════════════════════════════════════════════
# 主工具箱面板
# ═══════════════════════════════════════════════════════════════════════════

class ToolboxPanel(QWidget):
    """
    公共 API（向后兼容现有的 MainWindow 用法）：
    - node_type_selected 信号
    - refresh()
    - set_view_mode(tree: bool)
    """

    # 节点类型选择信号
    node_type_selected = pyqtSignal(str)
    # 收藏夹变更信号
    favorites_changed = pyqtSignal()

    # QSettings中收藏夹的键名
    FAVORITES_KEY = "Toolbox/Favorites"
    # QSettings中最近使用的键名
    RECENTS_KEY = "Toolbox/Recents"
    # 视图模式键名：'tree' 或 'grid'
    VIEW_MODE_KEY = "Toolbox/ViewMode"
    # 最大最近使用记录数量
    MAX_RECENTS = 10

    def __init__(self, parent=None):
        """初始化工具箱面板

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 收藏夹列表
        self._favorites: list[str] = []
        # 最近使用列表
        self._recents: list[str] = []
        # 当前选中的节点类型
        self._selected_type: str | None = None
        # 节点类型到瓷砖按钮的映射
        self._tile_widgets: dict[str, _NodeTileButton] = {}
        # 当前视图模式：树形视图或网格视图
        self._view_is_tree = False

        # 加载持久化数据：收藏夹、最近、视图模式
        self._load_persisted()
        # 设置主页面UI
        self._setup_ui()
        # 刷新显示内容
        self.refresh()
        # 连接主题变更信号，刷新样式表
        connect_theme(self._refresh_qss)

    # ── 持久化 ────────────────────────────────────────────────────

    def _load_persisted(self):
        """从QSettings加载持久化数据"""
        # 创建QSettings对象
        s = QSettings()
        # 获取收藏夹列表
        favs = s.value(self.FAVORITES_KEY, [])
        # 如果是字符串（兼容旧版本），转换为列表
        if isinstance(favs, str):
            favs = [favs] if favs else []
        # 确保收藏夹是列表
        self._favorites = list(favs) if favs else []

        # 获取最近使用列表
        recs = s.value(self.RECENTS_KEY, [])
        # 如果是字符串（兼容旧版本），转换为列表
        if isinstance(recs, str):
            recs = [recs] if recs else []
        # 确保最近使用是列表
        self._recents = list(recs) if recs else []

        # 获取视图模式，默认为False（网格视图）
        tree_mode = s.value(self.VIEW_MODE_KEY, "false")
        # 转换为布尔值
        self._view_is_tree = str(tree_mode).lower() == "true"

    def _save_favorites(self):
        """保存收藏夹到QSettings"""
        # 创建QSettings对象
        s = QSettings()
        # 保存收藏夹列表
        s.setValue(self.FAVORITES_KEY, self._favorites)
        # 同步到磁盘
        s.sync()
        # 发出收藏夹变更信号
        self.favorites_changed.emit()

    def _save_recents(self):
        """保存最近使用列表到QSettings"""
        # 创建QSettings对象
        s = QSettings()
        # 保存最近使用列表（只保留前MAX_RECENTS条）
        s.setValue(self.RECENTS_KEY, self._recents[:self.MAX_RECENTS])
        # 同步到磁盘
        s.sync()

    def _save_view_mode(self):
        """保存视图模式到QSettings"""
        # 创建QSettings对象
        s = QSettings()
        # 保存视图模式（'true'表示树形视图）
        s.setValue(self.VIEW_MODE_KEY, "true" if self._view_is_tree else "false")
        # 同步到磁盘（立即写入磁盘）
        s.sync()

    def is_favorite(self, type_name: str) -> bool:
        """判断节点是否为收藏

        参数：
            type_name: 节点类型名称

        返回：
            是否为收藏
        """
        return type_name in self._favorites

    def add_favorite(self, type_name: str):
        """添加节点到收藏

        参数：
            type_name: 节点类型名称
        """
        if type_name and type_name not in self._favorites:
            self._favorites.append(type_name)
            self._save_favorites()
            self.refresh()

    def remove_favorite(self, type_name: str):
        """从收藏中移除节点

        参数：
            type_name: 节点类型名称
        """
        if type_name in self._favorites:
            self._favorites.remove(type_name)
            self._save_favorites()
            self.refresh()

    def toggle_favorite(self, type_name: str):
        """切换收藏状态

        参数：
            type_name: 节点类型名称
        """
        if self.is_favorite(type_name):
            self.remove_favorite(type_name)
        else:
            self.add_favorite(type_name)

    def record_use(self, type_name: str):
        """记录节点使用（用于最近使用列表）

        参数：
            type_name: 节点类型名称
        """
        if type_name in self._recents:
            self._recents.remove(type_name)
        self._recents.insert(0, type_name)
        self._recents = self._recents[:self.MAX_RECENTS]
        self._save_recents()

    # ── UI设置 ───────────────────────────────────────────────────────

    def _setup_ui(self):
        """设置UI界面"""
        # 创建主垂直布局
        main_layout = QVBoxLayout(self)
        # 设置布局边距为0
        main_layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        main_layout.setSpacing(0)

        # ── 头部："流程资源" + 树形/网格切换按钮（窄模式隐藏）──
        # 创建头部容器
        self._header = QWidget()
        # 设置固定高度32像素
        self._header.setFixedHeight(32)
        # 设置头部样式
        self._header.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        # 创建头部水平布局
        h_layout = QHBoxLayout(self._header)
        # 设置布局边距
        h_layout.setContentsMargins(8, 0, 2, 0)
        # 设置布局间距为2
        h_layout.setSpacing(2)

        # 标题标签
        title = QLabel("流程资源")
        # 设置标题样式
        title.setStyleSheet("color: #dcdcdc; font-size: 12px; font-weight: bold; background: transparent; border: none;")
        # 添加到布局，拉伸因子为1
        h_layout.addWidget(title, 1)

        # 创建视图切换按钮：使用字体图标实现两种状态间的切换
        # 选中状态（checked）显示左对齐图标（树形视图）
        # 未选中状态（unchecked）显示右下角实心箭头图标（网格视图）
        # 图标字体大小设置为12像素
        self._view_toggle = FontIconToggleButton(
            checked_icon=FontIcons.AlignLeft,                       # 选中状态图标：左对齐（树形视图）
            unchecked_icon=FontIcons.CaretBottomRightSolidCenter8,  # 未选中状态图标：右下角实心箭头（网格视图）
            font_size=12,                                           # 图标字体大小
        )
        # 根据当前视图模式设置切换按钮的状态
        self._view_toggle.setChecked(self._view_is_tree)
        # 设置工具提示
        self._view_toggle.setToolTip("树形 / 网格切换")
        # 设置固定大小26x24
        self._view_toggle.setFixedSize(26, 24)
        # 设置切换按钮的样式表
        self._view_toggle.setStyleSheet(
            # 正常状态：透明背景、无边框、浅灰色文字、内边距2px
            "QPushButton { background: transparent; border: none; color: #999; padding: 2px; }"
            # 悬停状态：深灰色背景、亮灰色文字（视觉反馈）
            "QPushButton:hover { background: #3e3e42; color: #dcdcdc; }"
            # 选中状态（checked）：亮灰色文字（与悬停状态文字颜色一致）
            "QPushButton:checked { color: #dcdcdc; }"
        )
        # 连接切换按钮的toggled信号到处理函数
        self._view_toggle.toggled.connect(self._on_view_toggled)
        # 添加到头部布局
        h_layout.addWidget(self._view_toggle)
        # 将头部添加到主布局
        main_layout.addWidget(self._header)

        # ── 搜索框 ──
        self._search_box = QLineEdit()
        # 设置占位符文本
        self._search_box.setPlaceholderText("搜索模块 / 中文名称...")
        # 设置搜索框样式
        self._search_box.setStyleSheet(
            # 正常状态：深灰色背景、无边框、亮灰色文字
            "QLineEdit { background: #333337; color: #dcdcdc; border: none;"
            # 底部边框：深灰色下划线，内边距：上下6px，左右8px，字体大小12像素
            "border-bottom: 1px solid #3f3f46; padding: 6px 8px; font-size: 12px; }"
            # 获得焦点时：底部边框变为蓝色
            "QLineEdit:focus { border-bottom: 1px solid #0078d4; }"
        )
        # 文本改变时刷新显示内容
        self._search_box.textChanged.connect(lambda: self.refresh())
        # 添加到主布局
        main_layout.addWidget(self._search_box)

        # ── 堆叠视图：树形视图 | 网格视图 | 窄模式 ──
        self._view_frame = QFrame()
        # 设置无边框
        self._view_frame.setFrameShape(QFrame.NoFrame)
        # 创建垂直布局
        vf_layout = QVBoxLayout(self._view_frame)
        # 设置布局边距为0
        vf_layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        vf_layout.setSpacing(0)

        # 树形视图
        self._tree = self._create_tree()
        vf_layout.addWidget(self._tree)

        # 网格视图（滚动区域）
        self._grid_scroll = QScrollArea()
        # 设置控件可调整大小
        self._grid_scroll.setWidgetResizable(True)
        # 设置无边框
        self._grid_scroll.setFrameShape(QFrame.NoFrame)
        # 设置样式
        self._grid_scroll.setStyleSheet("QScrollArea { background: #252526; border: none; }")
        # 禁用水平滚动条
        self._grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 创建网格内容容器
        self._grid_content = QWidget()
        # 创建垂直布局
        self._grid_layout = QVBoxLayout(self._grid_content)
        # 设置布局边距
        self._grid_layout.setContentsMargins(8, 8, 8, 8)
        # 设置布局间距为10
        self._grid_layout.setSpacing(10)
        # 设置滚动区域的控件
        self._grid_scroll.setWidget(self._grid_content)
        # 添加到布局
        vf_layout.addWidget(self._grid_scroll)

        # 窄模式（紧凑的垂直图标列表 — 上下文菜单展示器）
        self._narrow_widget = QWidget()
        # 创建垂直布局
        self._narrow_layout = QVBoxLayout(self._narrow_widget)
        # 设置布局边距
        self._narrow_layout.setContentsMargins(0, 20, 0, 0)
        # 设置布局间距为5
        self._narrow_layout.setSpacing(5)
        # 设置水平居中、顶部对齐
        self._narrow_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        # 添加到布局
        vf_layout.addWidget(self._narrow_widget)

        # 初始状态：隐藏树形视图，显示网格视图，隐藏窄模式
        self._tree.hide()
        self._grid_scroll.show()
        self._narrow_widget.hide()
        # 将视图框架添加到主布局，拉伸因子为1
        main_layout.addWidget(self._view_frame, 1)

    # ── 树形视图 ─────────────────────────────────────────────────────

    def _create_tree(self) -> QTreeWidget:
        """创建树形视图控件

        返回：
            树形视图对象
        """
        # 创建可拖拽树形控件
        tree = _DraggableTreeWidget()
        # 设置表头标签
        tree.setHeaderLabels(["模块名称", "描述"])
        # 设置列宽
        tree.setColumnWidth(0, 140)
        # 设置缩进
        tree.setIndentation(16)
        # 设置根节点可装饰
        tree.setRootIsDecorated(True)
        # 启用动画效果
        tree.setAnimated(True)
        # 双击可展开
        tree.setExpandsOnDoubleClick(True)
        # 设置树形控件样式
        tree.setStyleSheet("""
            QTreeWidget {
                background: #252526; color: #dcdcdc; border: none; font-size: 11px;
            }
            QTreeWidget::item { padding: 3px 4px; border: none; }
            QTreeWidget::item:hover { background: #2d2d30; }
            QTreeWidget::item:selected { background: #094771; }
            QTreeWidget::branch { background: transparent; }
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
        return tree

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, col: int):
        """树形视图项点击事件处理

        参数：
            item: 被点击的项
            col: 列号
        """
        # 获取节点类型名称
        type_name = item.data(0, Qt.UserRole)
        if type_name:
            self._set_selected_type(type_name)

    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, col: int):
        """树形视图项双击事件处理（暂不处理）"""
        pass

    # ── 视图切换 ──────────────────────────────────────────────────

    def _on_view_toggled(self, checked: bool):
        """视图切换按钮状态变化处理

        参数：
            checked: 是否选中
        """
        # 更新当前视图模式
        self._view_is_tree = checked
        # 保存视图模式到设置
        self._save_view_mode()
        # 应用视图切换
        self._apply_view()

    def set_view_mode(self, tree: bool):
        """以编程方式切换视图模式

        参数：
            tree: True表示树形视图，False表示网格视图
        """
        # 如果切换按钮状态与目标不同
        if self._view_toggle.isChecked() != tree:
            # 设置切换按钮状态
            self._view_toggle.setChecked(tree)

    def _apply_view(self):
        """
        根据宽度和切换状态显示正确的视图。
        数据触发器：菜单宽度 < 90 → 隐藏分组框，显示图标栏。
        """
        # 获取当前菜单宽度
        w = self.width()
        # 如果宽度小于等于阈值，进入窄模式
        if w <= WIDTH_THRESHOLD:
            # 窄模式：隐藏标题栏和搜索框
            self._header.hide()
            self._search_box.hide()
            # 隐藏树形视图和网格视图
            self._tree.hide()
            self._grid_scroll.hide()
            # 显示窄模式组件
            self._narrow_widget.show()
        # 树形模式
        elif self._view_is_tree:
            # 显示标题栏和搜索框
            self._header.show()
            self._search_box.show()
            # 显示树形视图
            self._tree.show()
            # 隐藏网格视图和窄模式
            self._grid_scroll.hide()
            self._narrow_widget.hide()
        # 网格模式（默认）
        else:
            # 显示标题栏和搜索框
            self._header.show()
            self._search_box.show()
            # 隐藏树形视图
            self._tree.hide()
            # 显示网格视图
            self._grid_scroll.show()
            # 隐藏窄模式
            self._narrow_widget.hide()

    def resizeEvent(self, event):
        """响应宽度变化 — 在宽模式和窄模式之间切换

        参数：
            event: 大小改变事件对象
        """
        # 调用父类的resizeEvent
        super().resizeEvent(event)
        # 应用视图切换
        self._apply_view()
        # 如果宽度发生变化
        if event.oldSize().width() != event.size().width():
            # 刷新显示内容
            self.refresh()

    # ── 数据构建 ────────────────────────────────────────────────

    def _all_node_metas(self) -> list[dict]:
        """获取所有节点元信息（根据搜索关键字过滤）

        返回：
            节点元信息列表
        """
        # 获取搜索文本并转换为小写
        keyword = self._search_box.text().strip().lower()
        # 结果列表
        result = []
        # 遍历所有分组
        for group in node_data_group_manager.get_all_groups():
            # 遍历分组中的节点类型
            for node_type in group.node_types:
                # 获取类型名称
                type_name = node_type.__name__
                # 显示名称
                display_name = type_name
                try:
                    # 尝试实例化获取显示名称
                    instance = node_type()
                    candidate = getattr(instance, 'display_name', '') or getattr(instance, 'name', '')
                    if isinstance(candidate, str) and candidate.strip():
                        display_name = candidate.strip()
                except Exception:
                    pass

                # 获取文档字符串作为描述
                doc = (node_type.__doc__ or '').strip().splitlines()
                description = doc[0] if doc else display_name

                # 如果有搜索关键字且不匹配
                if keyword and keyword not in f"{display_name} {description} {type_name} {group.name}".lower():
                    continue

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
                })
        return result

    # ── 刷新 ──────────────────────────────────────────────────────

    def refresh(self):
        """重建活动视图"""
        # 获取当前菜单宽度
        w = self.width()
        # 窄模式
        if w <= WIDTH_THRESHOLD:
            self._refresh_narrow()
        # 树形模式
        elif self._view_is_tree:
            self._refresh_tree()
        # 网格模式（默认）
        else:
            self._refresh_grid()

    def _refresh_tree(self):
        """刷新树形视图"""
        # 清空树形控件
        self._tree.clear()
        # 获取所有节点元信息
        metas = self._all_node_metas()
        # 按分组分组
        grouped: dict[str, list[dict]] = {}
        for m in metas:
            grouped.setdefault(m["group_name"], []).append(m)

        # 最近使用部分
        recents = [m for m in metas if m["type_name"] in self._recents]
        if recents:
            # 按最近使用顺序排序
            recents.sort(key=lambda m: self._recents.index(m["type_name"]))
            # 添加分组
            p = self._add_tree_group("🕐 最近使用", "#d7ba7d")
            # 添加节点
            for m in recents:
                self._add_tree_node(p, m)

        # 收藏部分
        favs = [m for m in metas if m["is_favorite"]]
        if favs:
            # 添加分组
            p = self._add_tree_group("★ 收藏", "#d7ba7d")
            # 添加节点
            for m in favs:
                self._add_tree_node(p, m)

        # 遍历所有分组
        for grp in node_data_group_manager.get_all_groups():
            items = grouped.get(grp.name, [])
            if not items:
                continue
            # 添加分组
            p = self._add_tree_group(grp.name, _group_meta(grp.name)["color"])
            # 添加节点
            for m in items:
                self._add_tree_node(p, m)

        # 展开所有分组
        self._tree.expandAll()

    def _add_tree_group(self, name: str, color: str) -> QTreeWidgetItem:
        """添加树形视图分组

        参数：
            name: 分组名称
            color: 分组颜色

        返回：
            分组项
        """
        # 创建分组项
        item = QTreeWidgetItem(self._tree)
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
        return item

    def _add_tree_node(self, parent: QTreeWidgetItem, meta: dict):
        """添加树形视图节点

        参数：
            parent: 父节点
            meta: 节点元信息
        """
        # 创建节点项
        item = QTreeWidgetItem(parent)
        # 设置名称
        item.setText(0, meta["display_name"])
        # 设置描述
        item.setText(1, meta["description"])
        # 存储节点类型名称到用户数据
        item.setData(0, Qt.UserRole, meta["type_name"])
        # 设置工具提示
        item.setToolTip(0, f"{meta['display_name']}\n{meta['description']}")
        # 设置前景色
        item.setForeground(0, QColor(meta["color"]))
        return item

    def _refresh_grid(self):
        """刷新网格视图"""
        # 清空网格布局
        while self._grid_layout.count():
            w = self._grid_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
        # 清空瓷砖按钮映射
        self._tile_widgets.clear()

        # 获取所有节点元信息
        metas = self._all_node_metas()
        # 按分组分组
        grouped: dict[str, list[dict]] = {}
        for m in metas:
            grouped.setdefault(m["group_name"], []).append(m)

        # 最近使用部分
        recents = [m for m in metas if m["type_name"] in self._recents]
        if recents:
            # 按最近使用顺序排序
            recents.sort(key=lambda m: self._recents.index(m["type_name"]))
            self._build_grid_group("🕐 最近使用", recents)

        # 收藏部分
        favs = [m for m in metas if m["is_favorite"]]
        if favs:
            self._build_grid_group("★ 收藏", favs)

        # 遍历所有分组
        for grp in node_data_group_manager.get_all_groups():
            items = grouped.get(grp.name, [])
            if not items:
                continue
            self._build_grid_group(grp.name, items)

        # 添加弹性空间
        self._grid_layout.addStretch(1)

    def _build_grid_group(self, group_name: str, metas: list[dict]) -> int:
        """构建可折叠分组部分（展开器 + 换行面板）

        参数：
            group_name: 分组名称
            metas: 节点元信息列表

        返回：
            节点数量
        """
        if not metas:
            return 0
        # 获取分组元数据
        meta = _group_meta(group_name)
        # 创建可折叠分组
        section = _CollapsibleGroup(group_name, meta["icon"], meta["color"], metas)

        # 遍历节点元信息
        for i, m in enumerate(metas):
            # 创建瓷砖按钮
            tile = _NodeTileButton(m["type_name"], m["display_name"], m["description"],
                                    m["group_name"], m["is_favorite"])
            # 连接选中信号
            tile.selected.connect(self._set_selected_type)
            # 连接收藏切换信号
            tile.favorite_toggled.connect(self.toggle_favorite)
            # 保存到映射
            self._tile_widgets[m["type_name"]] = tile
            # 如果节点是当前选中的，设置选中状态
            if m["type_name"] == self._selected_type:
                tile.set_selected(True)
            # 添加到分组
            section.add_tile(tile, i)

        # 添加到网格布局
        self._grid_layout.addWidget(section)
        return len(metas)

    def _refresh_narrow(self):
        """
        构建简洁的组图标列表（上下文菜单展示器）。
        每个节点组对应一个按钮。点击组图标会弹出一个窗口，
        以两列网格的形式显示该组的节点。
        """
        # 清空窄模式布局
        while self._narrow_layout.count():
            w = self._narrow_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        # 获取所有节点元信息
        metas = self._all_node_metas()
        # 按分组分组
        grouped: dict[str, list[dict]] = {}
        for m in metas:
            grouped.setdefault(m["group_name"], []).append(m)

        # 遍历所有分组
        for grp in node_data_group_manager.get_all_groups():
            items = grouped.get(grp.name, [])
            if not items:
                continue
            # 获取分组元数据
            gmeta = _group_meta(grp.name)
            # 创建窄模式分组按钮
            btn = _NarrowGroupButton(grp.name, gmeta["icon"], gmeta["color"], items)
            # 连接节点类型选择信号
            btn.node_type_selected.connect(self.node_type_selected.emit)
            # 添加到布局
            self._narrow_layout.addWidget(btn)

        # 添加弹性空间
        self._narrow_layout.addStretch(1)

    def _set_selected_type(self, type_name: str):
        """设置选中的节点类型

        参数：
            type_name: 节点类型名称
        """
        # 保存选中的类型名称
        self._selected_type = type_name
        # 更新所有瓷砖按钮的选中状态
        for current, tile in self._tile_widgets.items():
            tile.set_selected(current == type_name)

    # ── 公共API ──────────────────────────────────────────────────

    def get_selected_node_type(self) -> str | None:
        """获取当前选中的节点类型名称

        返回：
            节点类型名称或None
        """
        return self._selected_type

    def _refresh_qss(self):
        """主题变化时重新应用面板QSS — DynamicResource刷新"""
        # 获取主题管理器
        tm = theme_manager
        # 刷新搜索框样式
        if hasattr(self, '_search_box'):
            self._search_box.setStyleSheet(
                f"QLineEdit {{ background: {tm.color('bg_surface_input').name()}; "
                f"color: {tm.color('text_primary').name()}; "
                f"border: 1px solid {tm.color('border').name()}; "
                f"border-radius: 4px; padding: 6px 10px; font-size: 12px; }}"
                f"QLineEdit:focus {{ border-color: {tm.color('accent').name()}; }}"
            )
        # 刷新网格滚动区域样式
        if hasattr(self, '_grid_scroll'):
            self._grid_scroll.setStyleSheet(
                f"QScrollArea {{ background: {tm.color('bg_surface').name()}; border: none; }}"
            )
        # 刷新树形滚动区域样式
        if hasattr(self, '_tree_scroll'):
            self._tree_scroll.setStyleSheet(
                f"QScrollArea {{ background: {tm.color('bg_surface').name()}; border: none; }}"
            )
        # 刷新树形视图样式
        if hasattr(self, '_tree'):
            self._tree.setStyleSheet(
                f"QTreeWidget {{ background: {tm.color('bg_surface').name()}; "
                f"color: {tm.color('text_primary').name()}; border: none; }}"
                f"QTreeWidget::item:hover {{ background: {tm.color('bg_surface_hover').name()}; }}"
                f"QTreeWidget::item:selected {{ background: #094771; color: white; }}"
            )
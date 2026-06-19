from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QScrollArea, QFrame, QGridLayout,
                              QPushButton, QApplication)
from PyQt5.QtCore import Qt, QEvent, pyqtSignal, QMimeData, QPoint
from PyQt5.QtGui import QDrag

from core.node_group import node_data_group_manager
from core.constants import get_group_meta as _group_meta
from gui.theme import theme_manager, connect_theme

_active_popup_button = None


class _DraggableCard(QPushButton):
    """弹窗节点卡片，支持单击选择和拖拽到画布"""

    def __init__(self, type_name: str, display_name: str, color: str, icon: str, parent=None):
        """
        初始化可拖拽卡片
        参数：
            type_name: 节点类型名称
            display_name: 显示名称
            color: 颜色
            icon: 图标
            parent: 父对象
        """
        super().__init__(parent)
        self._type_name = type_name
        self._drag_start_pos = QPoint()
        self._drag_started = False

        # 设置固定大小130x32
        self.setFixedSize(130, 32)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{display_name}\n类型: {type_name}")
        tm = theme_manager
        self.setStyleSheet(
            f"QPushButton {{"
            f"background: {tm.color('bg_surface').name()}; "
            f"border: 1px solid {tm.color('border').name()}; border-radius: 4px;"
            f"}}"
            f"QPushButton:hover {{"
            f"background: {tm.color('bg_surface_hover').name()}; "
            f"border-color: {tm.color('accent').name()};"
            f"}}"
        )

        inner = QHBoxLayout(self)
        inner.setContentsMargins(6, 4, 6, 4)
        inner.setSpacing(6)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFixedSize(22, 22)
        icon_lbl.setStyleSheet(
            f"color: {color}; font-size: 15px; font-weight: bold;"
            f"font-family: 'Segoe MDL2 Assets';"
            "background: transparent; border: none;"
        )
        inner.addWidget(icon_lbl)

        text_lbl = QLabel(display_name)
        text_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        text_lbl.setStyleSheet(
            f"color: {tm.color('text_primary').name()}; font-size: 12px; "
            "font-weight: 700; background: transparent; border: none;"
        )
        inner.addWidget(text_lbl, 1)

    """
    鼠标事件：
    mousePressEvent - 鼠标按下事件，当鼠标按下，记录鼠标当前位置，将拖拽标志self._drag_started设为false，并标记事件被接受
    mouseMoveEvent - 鼠标移动事件，当移动距离超过阈值记为拖拽，创建QDrag对象，设置拖拽数据为节点类型名称，执行拖拽操作
                    drag = QDrag(self)创建拖拽对象，mime = QMimeData()准备要传输的数据，mime.setText(self._type_name)设置数据
                    内容为节点类型名称，drag.setMimeData(mime)将数据关联到拖拽对象，drag.setPixmap(self.grab())设置拖拽时显示的图标，
                    drag.exec_(Qt.CopyAction)执行拖拽操作，允许复制，drag.exec_(Qt.CopyAction)执行拖拽（阻塞！），直到用户释放
    mouseReleaseEvent - 鼠标释放事件，重置拖拽标志。如果鼠标点击且没有移动，执行self.clicked.emit()表示点击，否则视为拖拽
    拖拽时，qt接管鼠标，拖拽的节点会在不同页面上移动，当移动到某个页面释放时，如果该页面接收拖拽就会接收数据。在gui/node_editor/editor_widget.py中
    DiagramEditorView在初始化是self.setAcceptDrops(True)表示它接受拖拽事件，于是节点到DiagramEditorView页面上，释放时会触发DiagramEditorView
    的dragEnterEvent和dropEvent事件，完成节点的创建。DiagramEditorView/dragEnterEvent用于接收拖拽进入到view的事件
    toolbox:                 Qt/OS:                   editor_widget:
                                                  
    mime.setText("X")   →   Qt 持有 mime 对象
    drag.exec_()            Qt 进入拖放循环
    (阻塞中...)           鼠标移到 view 上方
                         → 发现 view 有 AcceptDrops
                         → 把 mime 传给 dragEnterEvent(event)  ← event.mimeData() 就是同一个 mime
                        鼠标释放
                         → 把 mime 传给 dropEvent(event)       ← 读 event.mimeData().text() = "X"
    (exec_ 返回)          Qt 退出拖放循环

    """

    def mousePressEvent(self, event):
        """
        鼠标按下事件
        参数：
            event: 鼠标事件对象
        """
        # 如果按下的是左键
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self._drag_started = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """
        鼠标移动事件，当用户从工具箱拖拽一个节点到画布时触发
        检查是否按住左键，且移动距离超过系统拖拽阈值
        创建 QDrag 对象，将节点类型名称作为 MIME 数据
        调用 drag.exec_() 启动拖拽操作（阻塞直到释放鼠标）
        参数：
            event: 鼠标事件对象
        """
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return

        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        self._drag_started = True

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self._type_name)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(self.rect().center())
        drag.exec_(Qt.CopyAction)
        event.accept()

    def mouseReleaseEvent(self, event):
        """
        鼠标释放事件
        参数：
            event: 鼠标事件对象
        """
        if event.button() == Qt.LeftButton and not self._drag_started:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class _NarrowGroupPopup(QFrame):
    """
    窄模式下的分组弹出窗口
    """

    # 节点类型选择信号
    node_type_selected = pyqtSignal(str)

    def __init__(self, group_name: str, icon: str, color: str, metas: list[dict]):
        """
        初始化窄模式分组弹出窗口
        参数：
            group_name: 分组名称
            icon: 分组图标
            color: 分组颜色
            metas: 节点元信息列表
            parent: 父对象
        """
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        tm = theme_manager
        self.setStyleSheet(
            f"_NarrowGroupPopup {{"
            f"background: {tm.color('bg_surface_raised').name()}; "
            f"border: 1px solid {tm.color('border').name()}; "
            f"border-radius: 6px;"
            f"}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(
            f"background: {tm.color('bg_surface_hover').name()}; "
            f"border-radius: 6px 6px 0 0;"
        )

        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 6, 8, 6)
        hl.setSpacing(4)

        # 分组名称标签
        name_lbl = QLabel(group_name)
        name_lbl.setStyleSheet(
            f"color: {color}; "                # 文字颜色
            f"font-size: 12px; "              # 字体大小12px
            f"font-weight: bold; "            # 粗体
            "background: transparent; "       # 透明背景
            "border: none; "                  # 无边框
        )

        hl.addWidget(name_lbl, 1)

        # 图标标签
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(
            f"color: {color}; "                # 图标颜色
            f"font-size: 14px; "              # 字体大小14px
            f"font-weight: bold; "            # 粗体
            f"font-family: 'Segoe MDL2 Assets'; "  # 图标字体
            "background: transparent; "       # 透明背景
            "border: none; "                  # 无边框
        )

        hl.addWidget(icon_lbl)

        layout.addWidget(header)

        # 主体容器
        body = QWidget()
        body.setStyleSheet(
            f"background: {tm.color('bg_surface_raised').name()}; "
            f"border-radius: 0 0 6px 6px;"
        )

        bl = QVBoxLayout(body)
        bl.setContentsMargins(8, 8, 8, 8)
        bl.setSpacing(6)

        # 网格容器
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        # 遍历节点元信息列表
        for i, m in enumerate(metas):
            row, col = divmod(i, 2)
            grid.addWidget(self._make_node_card(m), row, col)

        bl.addWidget(grid_widget)
        layout.addWidget(body)
        self.adjustSize()

    def _make_node_card(self, m: dict) -> QPushButton:
        """
        创建节点卡片
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

    def  __init__(self, group_name: str, icon: str, color: str, metas: list[dict], parent=None):
        """
        初始化窄模式分组按钮
        参数：
            group_name: 分组名称
            icon: 分组图标
            color: 分组颜色
            metas: 节点元信息列表
            parent: 父对象
        """
        super().__init__(parent)
        self._group_name = group_name                            # 保存分组名称
        self._icon = icon                                        # 保存图标
        self._color = color                                      # 保存颜色
        self._metas = metas                                      # 保存节点元信息列表
        self._popup = None                                       # 弹出窗口实例，初始为None
        self.setText(icon)                                       # 设置按钮文本为图标
        self.setToolTip(group_name)                              # 设置工具提示为分组名称
        self.setCheckable(True)                                  # 设置为可选中（切换状态）
        self.setCursor(Qt.PointingHandCursor)                    # 设置光标为手指形状
        tm = theme_manager
        self.setStyleSheet(
            f"_NarrowGroupButton {{"
            f"background: transparent; "
            f"border: none; "
            f"color: {color}; "
            f"font-size: 25px; "
            f"font-family: 'Segoe MDL2 Assets'; "
            f"padding: 2px 0; "
            f"}}"
            f"_NarrowGroupButton:hover {{ color: {tm.color('text_title').name()}; }}"
            f"_NarrowGroupButton:checked {{ color: {tm.color('accent').name()}; }}"
        )
        self.toggled.connect(self._on_toggled)                   # 连接切换状态信号

    def _on_toggled(self, checked: bool):
        """
        按钮切换状态回调
        参数：
            checked: 是否选中
        """
        if checked:  # 如果选中，显示弹出窗口
            self._show_popup()
        else:        # 如果取消选中，隐藏弹出窗口
            self._hide_popup()

    def _show_popup(self):
        """显示弹出窗口"""
        global _active_popup_button  # 声明全局变量，跟踪当前活跃的弹出按钮
        # 互斥：如果已经有活跃的弹出按钮且不是当前按钮
        if _active_popup_button and _active_popup_button is not self:
            # 取消之前按钮的选中状态，触发其隐藏弹窗
            _active_popup_button.setChecked(False)
        # 将当前按钮设置为活跃按钮
        _active_popup_button = self

        # 确保没有残留的弹出窗口
        self._hide_popup()
        gmeta = _group_meta(self._group_name)  # 获取当前分组元数据
        icon = gmeta.get("icon", self._icon)  # 优先使用分组元数据中的图标，如果没有则使用按钮的图标
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
        """
        节点选择回调
        参数：
            type_name: 节点类型名称
        """
        # 发出节点类型选择信号
        self.node_type_selected.emit(type_name)
        # 取消按钮选中状态
        self.setChecked(False)

    def eventFilter(self, obj, event):
        """
        事件过滤器
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


class ToolboxPanel(QWidget):
    # 节点类型选择信号
    node_type_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        """初始化工具箱面板

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        self._favorites: list[str] = []                     # 收藏夹列表
        self._recents: list[str] = []                       # 最近使用列表
        self._selected_type: str | None = None              # 当前选中的节点类型
        self._tile_widgets = {}                             # 节点类型到瓷砖按钮的映射
        self._view_is_tree = False                          # 当前视图模式：树形视图或网格视图
        self._setup_ui()                                    # 设置主页面UI
        connect_theme(self._refresh_qss)                    # 连接主题变更信号，刷新样式表
        self.refresh()                                      # 刷新界面显示

    def _setup_ui(self):
        """设置UI界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

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


        # 网格视图（滚动区域）
        self._grid_scroll = QScrollArea()
        # 设置控件可调整大小
        self._grid_scroll.setWidgetResizable(True)
        # 设置无边框
        self._grid_scroll.setFrameShape(QFrame.NoFrame)
        # 设置样式
        tm = theme_manager
        self._grid_scroll.setStyleSheet(
            f"QScrollArea {{ background: {tm.color('bg_surface').name()}; border: none; }}"
        )
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

        # 显示网格视图
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("搜索节点...")
        self._search_box.setToolTip("搜索节点...")
        self._search_box.hide()  # 窄模式下隐藏
        self.setToolTip("节点工具箱")  # 供引导覆盖层查找
        self._grid_scroll.hide()
        self._narrow_widget.show()
        # 将视图框架添加到主布局，拉伸因子为1
        main_layout.addWidget(self._view_frame, 1)


    # ── 数据构建 ────────────────────────────────────────────────

    def _all_node_metas(self) -> list[dict]:
        """
        获取所有节点元信息（根据搜索关键字过滤）
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
                # 显示名称: 优先实例化获取中文名称，其次 __display_name__，最后类名
                display_name = type_name
                try:
                    instance = node_type()
                    candidate = getattr(instance, 'display_name', '') or getattr(instance, 'name', '')
                    if isinstance(candidate, str) and candidate.strip():
                        display_name = candidate.strip()
                except Exception:
                    display_name = getattr(node_type, '__display_name__', None) or type_name

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
                    "type_name": type_name,  # 类型名称
                    "display_name": display_name,  # 显示名称
                    "description": description,  # 描述
                    "group_name": group.name,  # 分组名称
                    "color": meta["color"],  # 颜色
                    "icon": meta["icon"],  # 图标
                })
        return result

    def refresh(self):
        """重建活动视图"""
        self._refresh_narrow()

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


    # ── 公共API ──────────────────────────────────────────────────

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
                f"QTreeWidget::item:selected {{ background: {tm.color('accent').name()}; color: white; }}"
            )
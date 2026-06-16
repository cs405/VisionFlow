"""GridSplitterBox

可折叠侧边栏容器，具有以下特性：
  - 模式="扩展"：面板在最小/最大宽度之间调整大小（从不隐藏）
  - 右侧边缘的拖拽手柄供用户调整大小
  - 底部的固定切换按钮
  - 90px宽度阈值信号（展开视图 ↔ 图标栏）

作为MainWindow中左侧面板的容器，替代手动操作QSplitter。
宽度阈值切换仍在ToolboxPanel内部进行（当GridSplitterBox宽度变化时响应resizeEvent）。
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

from gui.font_icons import FontIcons, FontIconToggleButton

# 菜单最大宽度（像素）
MENU_MAX_WIDTH = 300
# 菜单最小宽度（像素）- 窄模式紧凑宽度
MENU_MIN_WIDTH = 50
# 宽度阈值（像素）- 当宽度大于90px时进入宽模式
WIDTH_THRESHOLD = 90
# 默认宽度（像素）
DEFAULT_WIDTH = 280

# 边框画刷颜色
BORDER_BRUSH = "#3f3f46"
# 背景颜色
BACKGROUND = "#252526"


class GridSplitterBox(QWidget):
    """
    可折叠侧边栏容器类

    信号：
        width_changed(int): 面板宽度变化时发出
        threshold_crossed(bool): 进入宽模式(>90px)时为True，窄模式时为False
        expand_toggled(bool): 展开时为True，收起时为False
    """

    # 宽度变化信号
    width_changed = pyqtSignal(int)
    # 阈值跨越信号（True=宽模式>90px）
    threshold_crossed = pyqtSignal(bool)
    # 展开/收起切换信号
    expand_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        """初始化GridSplitterBox

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 菜单宽度，初始为默认宽度
        self._menu_width = DEFAULT_WIDTH
        # 是否展开，初始为True
        self._is_expanded = True
        # 是否宽模式（宽度>90px），初始为True
        self._is_wide = True
        # 保存的宽度（用于展开时恢复），初始为默认宽度
        self._saved_width = DEFAULT_WIDTH

        # 设置最小宽度为MENU_MIN_WIDTH(50)
        self.setMinimumWidth(MENU_MIN_WIDTH)
        # 设置最大宽度为MENU_MAX_WIDTH(300)
        self.setMaximumWidth(MENU_MAX_WIDTH)
        # 设置固定宽度为默认宽度(280)
        self.setFixedWidth(DEFAULT_WIDTH)

        # ── 布局：[内容区域 + 切换按钮] + 拖拽手柄 ──
        # 创建水平布局作为主布局
        main_layout = QHBoxLayout(self)
        # 设置布局边距为0
        main_layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        main_layout.setSpacing(0)

        # 内容区域（垂直布局：内容控件 | 切换按钮）
        self._content_area = QWidget()
        # 设置内容区域的样式表（背景色）
        self._content_area.setStyleSheet(f"background: {BACKGROUND};")
        # 创建内容区域的垂直布局
        content_vl = QVBoxLayout(self._content_area)
        # 设置布局边距为0
        content_vl.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        content_vl.setSpacing(0)

        # 内容插槽（用于放置用户控件）
        self._content_host = QWidget()
        # 设置内容宿主背景透明
        self._content_host.setStyleSheet("background: transparent;")
        # 创建宿主的垂直布局
        self._host_layout = QVBoxLayout(self._content_host)
        # 设置布局边距为0
        self._host_layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        self._host_layout.setSpacing(0)
        # 将内容宿主添加到内容区域布局中，拉伸因子为1（占据剩余空间）
        content_vl.addWidget(self._content_host, 1)

        # 底部的固定/切换按钮
        # 展开状态：显示Pin图标（已固定），收起状态：显示GlobalNavButton（列表/菜单）
        self._toggle_btn = FontIconToggleButton(
            checked_icon=FontIcons.Pin,              # 选中状态图标：图钉
            unchecked_icon=FontIcons.GlobalNavButton, # 未选中状态图标：全局导航按钮
            font_size=14,                            # 图标字体大小
        )
        # 初始设置为选中状态（展开）
        self._toggle_btn.setChecked(True)
        # 设置工具提示文本
        self._toggle_btn.setToolTip("锁定面板 / 收起面板")
        # 设置按钮固定高度为26像素
        self._toggle_btn.setFixedHeight(26)
        # 设置按钮样式表
        self._toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none;"
            "border-top: 1px solid #3f3f46; color: #888; padding: 3px 0; }"
            "QPushButton:hover { background: #3e3e42; color: #dcdcdc; }"
            "QPushButton:checked { color: #dcdcdc; }"
        )
        # 连接按钮的toggle信号到_on_toggle_btn方法
        self._toggle_btn.toggled.connect(self._on_toggle_btn)
        # 将切换按钮添加到内容区域布局中
        content_vl.addWidget(self._toggle_btn)

        # 将内容区域添加到主布局，拉伸因子为1
        main_layout.addWidget(self._content_area, 1)

        # 右侧边缘的拖拽手柄
        self._handle = QFrame()
        # 设置手柄形状为垂直线
        self._handle.setFrameShape(QFrame.VLine)
        # 设置手柄样式表（边框色，无边框）
        self._handle.setStyleSheet(f"background: {BORDER_BRUSH}; border: none;")
        # 设置手柄固定宽度为3像素
        self._handle.setFixedWidth(3)
        # 设置手柄光标为水平分割光标
        self._handle.setCursor(Qt.SplitHCursor)
        # 将手柄添加到主布局
        main_layout.addWidget(self._handle)

        # ── 调整大小防抖定时器 ──
        # 创建定时器对象
        self._resize_timer = QTimer(self)
        # 设置定时器为单次触发
        self._resize_timer.setSingleShot(True)
        # 设置定时器间隔为50毫秒
        self._resize_timer.setInterval(50)
        # 连接定时器的timeout信号到_check_threshold方法
        self._resize_timer.timeout.connect(self._check_threshold)

        # 拖拽起始X坐标
        self._drag_start_x = 0
        # 拖拽起始宽度
        self._drag_start_width = 0
        # 拖拽进行中标志
        self._is_dragging = False

    # ── 公共API ──────────────────────────────────────────────────────────

    def set_content(self, widget: QWidget):
        """设置此容器内部显示的主要内容控件"""
        # 清空内容宿主的布局中的所有子控件
        while self._host_layout.count():
            # 获取布局中的第一个项
            item = self._host_layout.takeAt(0)
            # 如果项有控件
            if item.widget():
                # 将控件的父对象设为None（解除引用）
                item.widget().setParent(None)
        # 将新控件添加到宿主布局中
        self._host_layout.addWidget(widget)

    def set_menu_width(self, width: int):
        """以编程方式设置面板宽度（会被限制在最小/最大范围内）"""
        # 将宽度限制在最小和最大之间
        width = max(MENU_MIN_WIDTH, min(MENU_MAX_WIDTH, width))
        # 保存菜单宽度
        self._menu_width = width
        # 设置固定宽度
        self.setFixedWidth(width)
        # 发出宽度变化信号
        self.width_changed.emit(width)
        # 如果宽度大于阈值，保存当前宽度
        if width > WIDTH_THRESHOLD:
            self._saved_width = width
        # 检查阈值变化
        self._check_threshold()

    def menu_width(self) -> int:
        """获取当前菜单宽度"""
        return self._menu_width

    @property
    def is_expanded(self) -> bool:
        """是否处于展开状态"""
        return self._is_expanded

    @property
    def is_wide(self) -> bool:
        """当前宽度是否大于90px（宽模式）"""
        return self._is_wide

    def toggle_expand(self):
        """在展开（保存的宽度）和收起（最小宽度）之间切换"""
        # 如果当前是展开状态
        if self._is_expanded:
            # 调用收起方法
            self.collapse()
        else:
            # 调用展开方法
            self.expand()

    def expand(self):
        """展开到保存的宽度（模式=扩展）"""
        # 如果当前不是展开状态
        if not self._is_expanded:
            # 设置展开标志为True
            self._is_expanded = True
            # 获取保存的宽度，如果保存的宽度小于阈值则使用默认宽度
            w = self._saved_width if self._saved_width > WIDTH_THRESHOLD else DEFAULT_WIDTH
            # 设置菜单宽度
            self.set_menu_width(w)
            # 同步切换按钮状态
            self._sync_toggle_btn()
            # 发出展开状态变化信号（True表示展开）
            self.expand_toggled.emit(True)

    def collapse(self):
        """收起到最小宽度（模式=扩展）"""
        # 如果当前是展开状态
        if self._is_expanded:
            # 保存当前宽度
            self._saved_width = self._menu_width
            # 设置展开标志为False
            self._is_expanded = False
            # 设置菜单宽度为最小宽度
            self.set_menu_width(MENU_MIN_WIDTH)
            # 同步切换按钮状态
            self._sync_toggle_btn()
            # 发出展开状态变化信号（False表示收起）
            self.expand_toggled.emit(False)

    # ── 固定/切换按钮 ────────────────────────────────────────────────────

    def _on_toggle_btn(self, checked: bool):
        """切换按钮点击处理"""
        # 如果按钮被选中且当前不是展开状态
        if checked and not self._is_expanded:
            # 展开面板
            self.expand()
        # 如果按钮未被选中且当前是展开状态
        elif not checked and self._is_expanded:
            # 收起面板
            self.collapse()

    def _sync_toggle_btn(self):
        """同步切换按钮的选中状态与面板展开状态"""
        # 阻止按钮信号触发
        self._toggle_btn.blockSignals(True)
        # 设置按钮选中状态与展开状态一致
        self._toggle_btn.setChecked(self._is_expanded)
        # 恢复按钮信号触发
        self._toggle_btn.blockSignals(False)

    # ── 拖拽调整大小 ──────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        # 如果鼠标在手柄上或在手柄区域内
        if self._handle.underMouse() or self._in_handle_zone(event.pos()):
            # 记录拖拽起始全局X坐标
            self._drag_start_x = event.globalX()
            # 记录拖拽起始面板宽度
            self._drag_start_width = self.width()
            # 设置拖拽进行中标志
            self._is_dragging = True
            # 接受事件
            event.accept()
            return
        # 调用父类的mousePressEvent
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        # 如果正在拖拽中
        if self._is_dragging:
            # 计算鼠标移动的偏移量
            delta = event.globalX() - self._drag_start_x
            # 计算新的宽度（限制在最小和最大之间）
            new_w = max(MENU_MIN_WIDTH, min(MENU_MAX_WIDTH,
                         self._drag_start_width + delta))
            # 设置新的菜单宽度
            self.set_menu_width(new_w)
            # 如果新宽度大于阈值且当前不是展开状态
            if new_w > WIDTH_THRESHOLD and not self._is_expanded:
                # 设置展开标志为True
                self._is_expanded = True
                # 同步切换按钮状态
                self._sync_toggle_btn()
                # 发出展开状态变化信号
                self.expand_toggled.emit(True)
            # 如果新宽度小于等于阈值且当前是展开状态
            elif new_w <= WIDTH_THRESHOLD and self._is_expanded:
                # 设置展开标志为False
                self._is_expanded = False
                # 同步切换按钮状态
                self._sync_toggle_btn()
                # 发出展开状态变化信号
                self.expand_toggled.emit(False)
            # 接受事件
            event.accept()
            return
        # 调用父类的mouseMoveEvent
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        # 如果正在拖拽中
        if self._is_dragging:
            # 重置拖拽状态
            self._drag_start_x = 0
            self._is_dragging = False
            # 接受事件
            event.accept()
            return
        # 调用父类的mouseReleaseEvent
        super().mouseReleaseEvent(event)

    def _in_handle_zone(self, pos) -> bool:
        """检查位置是否在右侧边缘6像素内（拖拽区域）"""
        # 返回True如果鼠标X坐标在距离右边缘6像素内
        return self.width() - pos.x() <= 6

    def enterEvent(self, event):
        """鼠标进入控件事件"""
        # 如果鼠标在手柄区域内
        if self._in_handle_zone(event.pos()):
            # 设置光标为水平分割光标
            self.setCursor(Qt.SplitHCursor)
        else:
            # 设置光标为箭头
            self.setCursor(Qt.ArrowCursor)
        # 调用父类的enterEvent
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开控件事件"""
        # 设置光标为箭头
        self.setCursor(Qt.ArrowCursor)
        # 调用父类的leaveEvent
        super().leaveEvent(event)

    # ── 宽度阈值 ─────────────────────────────────────────────────────

    def resizeEvent(self, event):
        """控件大小改变事件"""
        # 调用父类的resizeEvent
        super().resizeEvent(event)
        # 更新菜单宽度为当前宽度
        self._menu_width = self.width()
        # 发出宽度变化信号
        self.width_changed.emit(self._menu_width)
        # 启动防抖定时器
        self._resize_timer.start()

    def _check_threshold(self):
        """检查宽度是否超过90px阈值，并在变化时发出信号"""
        # 保存之前的宽模式状态
        was_wide = self._is_wide
        # 更新当前宽模式状态（宽度大于阈值）
        self._is_wide = self._menu_width > WIDTH_THRESHOLD
        # 如果宽模式状态发生变化
        if self._is_wide != was_wide:
            # 发出阈值跨越信号
            self.threshold_crossed.emit(self._is_wide)
        # 如果是宽模式且宽度大于最小宽度
        if self._is_wide and self._menu_width > MENU_MIN_WIDTH:
            # 保存当前宽度
            self._saved_width = self._menu_width
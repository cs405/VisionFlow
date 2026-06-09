"""面板管理器 - 基于QDockWidget的面板停靠，支持浮动/自动隐藏。

提供：
  - 基于QDockWidget的停靠（浮动/停靠/标签页）
  - 面板窄时的自动隐藏
  - 位置和大小的QSettings持久化
  - 带动画状态过渡的面板显示/隐藏
"""

from PyQt5.QtWidgets import QDockWidget, QWidget, QMainWindow, QTabWidget
from PyQt5.QtCore import Qt, QSettings, pyqtSignal, QObject


class DockPanelInfo:
    """可停靠面板的元数据"""
    def __init__(self, key: str, title: str, widget: QWidget,
                 area: Qt.DockWidgetArea = Qt.LeftDockWidgetArea,
                 default_visible: bool = True,
                 default_width: int = 260,
                 allow_float: bool = True,
                 allow_close: bool = False):
        """
        初始化面板元数据

        参数：
            key: 面板唯一标识符
            title: 面板标题
            widget: 面板内容控件
            area: 默认停靠区域
            default_visible: 默认是否可见
            default_width: 默认宽度
            allow_float: 是否允许浮动
            allow_close: 是否允许关闭
        """
        # 面板唯一标识符
        self.key = key
        # 面板标题
        self.title = title
        # 面板内容控件
        self.widget = widget
        # 默认停靠区域
        self.area = area
        # 默认是否可见
        self.default_visible = default_visible
        # 默认宽度
        self.default_width = default_width
        # 是否允许浮动
        self.allow_float = allow_float
        # 是否允许关闭
        self.allow_close = allow_close
        # QDockWidget对象，初始为None
        self.dock: QDockWidget | None = None


class DockManager(QObject):
    """基于QDockWidget的面板停靠的中央管理器

    用法：
        dm = DockManager(main_window)
        dm.register("toolbox", "工具箱", toolbox_widget, Qt.LeftDockWidgetArea)
        dm.register("property", "属性", property_widget, Qt.RightDockWidgetArea)
        dm.restore_all()
    """

    # 面板切换信号：键名，可见性
    panel_toggled = pyqtSignal(str, bool)
    # 布局变化信号
    layout_changed = pyqtSignal()

    # QSettings中存储的组名
    SETTINGS_GROUP = "DockManager"

    def __init__(self, main_window: QMainWindow):
        """初始化面板管理器

        参数：
            main_window: 主窗口对象
        """
        # 调用父类QObject的构造函数
        super().__init__(main_window)
        # 保存主窗口引用
        self._mw = main_window
        # 创建QSettings对象
        self._settings = QSettings()
        # 面板字典：键为面板标识符，值为面板元数据
        self._panels: dict[str, DockPanelInfo] = {}

    # ── 注册 ──────────────────────────────────────────────────

    def register(self, key: str, title: str, widget: QWidget,
                 area: Qt.DockWidgetArea = Qt.LeftDockWidgetArea,
                 default_visible: bool = True,
                 default_width: int = 260,
                 allow_float: bool = True,
                 allow_close: bool = False) -> QDockWidget:
        """注册一个面板并创建其QDockWidget

        参数：
            key: 面板唯一标识符
            title: 面板标题
            widget: 面板内容控件
            area: 默认停靠区域
            default_visible: 默认是否可见
            default_width: 默认宽度
            allow_float: 是否允许浮动
            allow_close: 是否允许关闭

        返回：
            创建的QDockWidget对象，供进一步配置
        """
        # 创建面板元数据对象
        info = DockPanelInfo(key, title, widget, area,
                            default_visible, default_width,
                            allow_float, allow_close)

        # 创建QDockWidget对象
        dock = QDockWidget(title, self._mw)
        # 设置对象名（用于状态保存）
        dock.setObjectName(f"dock_{key}")
        # 设置内容控件
        dock.setWidget(widget)
        # 设置允许的停靠区域
        dock.setAllowedAreas(Qt.AllDockWidgetAreas if allow_float else area)
        # 设置停靠窗口特性
        dock.setFeatures(self._dock_features(info))

        # 从持久化存储恢复状态
        self._restore_dock_state(info, dock)

        # 保存dock引用
        info.dock = dock
        # 添加到面板字典
        self._panels[key] = info

        # 监听可见性变化
        dock.visibilityChanged.connect(lambda v: self._on_visibility_changed(key, v))

        # 返回dock对象
        return dock

    def _dock_features(self, info: DockPanelInfo):
        """获取停靠窗口的特性标志

        参数：
            info: 面板元数据

        返回：
            特性标志的组合
        """
        # 导入QDockWidget类并设置别名
        from PyQt5.QtWidgets import QDockWidget as D
        # 如果允许关闭，添加可关闭标志，否则无特性
        f = D.DockWidgetClosable if info.allow_close else D.NoDockWidgetFeatures
        # 如果允许浮动，添加可浮动和可移动标志
        if info.allow_float:
            f |= D.DockWidgetFloatable | D.DockWidgetMovable
        # 返回特性标志
        return f

    # ── 添加到主窗口 ────────────────────────────────────────────

    def attach(self, key: str, area: Qt.DockWidgetArea = None):
        """将已注册面板的停靠窗口添加到主窗口

        参数：
            key: 面板标识符
            area: 停靠区域，如果为None则使用元数据中的默认区域
        """
        # 获取面板元数据
        info = self._panels.get(key)
        # 如果面板不存在或dock为空，返回
        if info is None or info.dock is None:
            return
        # 如果未指定区域，使用元数据中的默认区域
        area = area or info.area
        # 将dock添加到主窗口的指定区域
        self._mw.addDockWidget(area, info.dock)

    def attach_all(self):
        """将所有已注册面板添加到主窗口"""
        # 遍历所有面板键
        for key in self._panels:
            # 添加面板
            self.attach(key)

    # ── 可见性 ────────────────────────────────────────────────────

    def show(self, key: str):
        """显示面板

        参数：
            key: 面板标识符
        """
        # 获取面板元数据
        info = self._panels.get(key)
        # 如果面板存在且dock不为空
        if info and info.dock:
            # 显示dock
            info.dock.show()
            # 保存可见性状态
            self._save_visibility(key, True)

    def hide(self, key: str):
        """隐藏面板

        参数：
            key: 面板标识符
        """
        # 获取面板元数据
        info = self._panels.get(key)
        # 如果面板存在且dock不为空
        if info and info.dock:
            # 隐藏dock
            info.dock.hide()
            # 保存可见性状态
            self._save_visibility(key, False)

    def toggle(self, key: str):
        """切换面板显示/隐藏状态

        参数：
            key: 面板标识符
        """
        # 获取面板元数据
        info = self._panels.get(key)
        # 如果面板存在且dock不为空
        if info and info.dock:
            # 如果当前可见则隐藏，否则显示
            if info.dock.isVisible():
                self.hide(key)
            else:
                self.show(key)

    def is_visible(self, key: str) -> bool:
        """检查面板是否可见

        参数：
            key: 面板标识符

        返回：
            可见返回True，否则返回False
        """
        # 获取面板元数据
        info = self._panels.get(key)
        # 如果面板存在且dock不为空，返回dock可见性，否则返回False
        return info.dock.isVisible() if (info and info.dock) else False

    def _on_visibility_changed(self, key: str, visible: bool):
        """可见性变化回调

        参数：
            key: 面板标识符
            visible: 新的可见性状态
        """
        # 保存可见性状态
        self._save_visibility(key, visible)
        # 发出面板切换信号
        self.panel_toggled.emit(key, visible)
        # 发出布局变化信号
        self.layout_changed.emit()

    # ── 标签页停靠 ────────────────────────────────────────────────────────

    def tabify(self, key1: str, key2: str):
        """将两个面板堆叠为标签页

        参数：
            key1: 第一个面板标识符
            key2: 第二个面板标识符
        """
        # 获取两个面板的元数据
        d1 = self._panels.get(key1)
        d2 = self._panels.get(key2)
        # 如果两个面板都存在且dock都不为空
        if d1 and d2 and d1.dock and d2.dock:
            # 将第二个dock标签页化到第一个dock
            self._mw.tabifyDockWidget(d1.dock, d2.dock)

    # ── 持久化 ───────────────────────────────────────────────────

    def _state_key(self, key: str, suffix: str) -> str:
        """获取状态存储的键名

        参数：
            key: 面板标识符
            suffix: 后缀

        返回：
            完整的键名
        """
        return f"{self.SETTINGS_GROUP}/{key}/{suffix}"

    def _save_visibility(self, key: str, visible: bool):
        """保存面板可见性到QSettings

        参数：
            key: 面板标识符
            visible: 可见性状态
        """
        # 存储可见性值
        self._settings.setValue(self._state_key(key, "visible"), visible)
        # 同步到磁盘
        self._settings.sync()

    def _restore_dock_state(self, info: DockPanelInfo, dock: QDockWidget):
        """从QSettings恢复停靠窗口状态

        参数：
            info: 面板元数据
            dock: QDockWidget对象
        """
        # 从QSettings获取可见性值
        vis = self._settings.value(self._state_key(info.key, "visible"))
        # 如果存在持久化的可见性值
        if vis is not None:
            # 将值转换为布尔型
            v = str(vis).lower() == "true" if isinstance(vis, str) else bool(vis)
            # 设置dock可见性
            dock.setVisible(v)
        else:
            # 使用默认可见性
            dock.setVisible(info.default_visible)

    def save_all(self):
        """持久化所有面板的可见性"""
        # 遍历所有面板
        for key, info in self._panels.items():
            # 如果dock存在
            if info.dock:
                # 保存可见性
                self._save_visibility(key, info.dock.isVisible())

    def restore_state(self):
        """从QSettings恢复主窗口的停靠状态"""
        # 从QSettings获取保存的窗口状态
        state = self._settings.value(f"{self.SETTINGS_GROUP}/windowState")
        # 如果状态存在
        if state:
            # 恢复主窗口状态
            self._mw.restoreState(state)

    def save_state(self):
        """保存主窗口的停靠状态到QSettings"""
        # 保存主窗口状态
        self._settings.setValue(f"{self.SETTINGS_GROUP}/windowState",
                               self._mw.saveState())
        # 同步到磁盘
        self._settings.sync()

    # ── 访问 ────────────────────────────────────────────────────────

    def get_dock(self, key: str) -> QDockWidget | None:
        """获取面板的QDockWidget对象

        参数：
            key: 面板标识符

        返回：
            QDockWidget对象，如果不存在则返回None
        """
        # 获取面板元数据
        info = self._panels.get(key)
        # 如果存在则返回dock，否则返回None
        return info.dock if info else None

    def keys(self) -> list[str]:
        """获取所有已注册面板的键名列表"""
        # 返回面板字典的键列表
        return list(self._panels.keys())
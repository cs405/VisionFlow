"""展示器模板系统
提供：
  - PresenterRegistry: 类型 → QWidget 工厂映射（类似 DataTemplate）
  - ContentPresenter: 自动解析内容类型并嵌入展示器的 QWidget
  - 内置展示器：PropertyPresenter, HelpPresenter, ROIPresenter, ResultPresenter
"""

from typing import Any, Callable, Type

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel


# ═══════════════════════════════════════════════════════════════════════════
# PresenterRegistry（展示器注册表）
# ═══════════════════════════════════════════════════════════════════════════

class PresenterRegistry:
    """基于类型的视图工厂注册表

    将 Python 类型映射到 QWidget 工厂函数。当 ContentPresenter 接收到数据对象时，
    在此处查找其类型并创建匹配的视图。

    用法：
        registry = PresenterRegistry()
        registry.register(VisionNodeData, lambda parent: PropertyPanel(parent, readonly=True))
        registry.register(ROIBase, lambda parent: RoiEditWidget(parent))
    """

    def __init__(self):
        """初始化展示器注册表"""
        # 类型到工厂函数的映射字典
        self._factories: dict[Type, Callable[[QWidget], QWidget]] = {}
        # 后备工厂函数（用于未匹配的类型）
        self._fallback: Callable[[Any, QWidget], QWidget] | None = None

    def register(self, data_type: Type, factory: Callable[[QWidget], QWidget]):
        """为特定数据类型注册展示器工厂

        参数：
            data_type: 要匹配的 Python 类（通过 isinstance 检查）
            factory: 可调用对象 factory(parent: QWidget) → QWidget 展示器
        """
        # 将类型和工厂函数存入字典
        self._factories[data_type] = factory

    def set_fallback(self, factory: Callable[[Any, QWidget], QWidget]):
        """为未匹配的类型设置后备工厂

        参数：
            factory: 后备工厂函数，签名为 (data, parent) → QWidget
        """
        self._fallback = factory

    def resolve(self, data: Any) -> Callable[[QWidget], QWidget] | None:
        """为数据对象查找最佳匹配的工厂

        使用 isinstance() 按注册顺序检查类型。
        如果没有匹配且没有后备工厂，返回 None。

        参数：
            data: 数据对象

        返回：
            工厂函数或 None
        """
        # 遍历所有已注册的类型
        for data_type, factory in self._factories.items():
            # 如果数据对象是该类型的实例
            if isinstance(data, data_type):
                # 返回对应的工厂函数
                return factory
        # 没有找到匹配，返回后备工厂
        return self._fallback

    def create(self, data: Any, parent: QWidget = None) -> QWidget | None:
        """解析并创建数据对象的展示器

        参数：
            data: 数据对象
            parent: 父对象

        返回：
            展示器控件或 None
        """
        # 解析工厂函数
        factory = self.resolve(data)
        # 如果工厂函数存在
        if factory:
            try:
                # 尝试用 parent 参数调用
                return factory(parent)
            except TypeError:
                # 如果失败，用 (data, parent) 签名调用（后备工厂）
                return factory(data, parent)
        # 没有工厂返回 None
        return None


# 全局单例
presenter_registry = PresenterRegistry()


# ═══════════════════════════════════════════════════════════════════════════
# ContentPresenter 控件
# ═══════════════════════════════════════════════════════════════════════════

class ContentPresenter(QWidget):
    """ContentPresenter 等价实现 — 自动将内容类型解析为视图。

    用法：
        presenter = ContentPresenter(parent)
        presenter.set_content(some_node)  # 自动创建匹配的 PropertyPanel
        presenter.set_content(None)       # 清空视图
    """

    def __init__(self, parent=None, registry: PresenterRegistry = None):
        """初始化内容展示器

        参数：
            parent: 父对象
            registry: 展示器注册表
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 保存注册表引用
        self._registry = registry or presenter_registry
        # 当前内容对象
        self._content: Any = None
        # 当前展示器控件
        self._presenter: QWidget | None = None

        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

    def set_content(self, data: Any):
        """设置内容对象并自动解析/创建匹配的展示器

        参数：
            data: 内容数据对象
        """
        # 移除之前的展示器
        if self._presenter:
            # 从布局中移除
            self.layout().removeWidget(self._presenter)
            # 删除控件
            self._presenter.deleteLater()
            # 清空引用
            self._presenter = None

        # 保存内容对象
        self._content = data
        # 如果数据为空，返回
        if data is None:
            return

        # 从注册表创建展示器
        widget = self._registry.create(data, parent=self)
        # 如果创建成功
        if widget:
            # 保存展示器引用
            self._presenter = widget
            # 添加到布局
            self.layout().addWidget(widget)

    @property
    def content(self) -> Any:
        """获取当前内容对象"""
        return self._content

    @property
    def presenter(self) -> QWidget | None:
        """获取当前展示器控件"""
        return self._presenter


# ═══════════════════════════════════════════════════════════════════════════
# 内置后备展示器
# ═══════════════════════════════════════════════════════════════════════════

class DefaultTextPresenter(QWidget):
    """简单的文本展示器，将 obj.__repr__() 显示为标签"""

    def __init__(self, data: Any, parent=None):
        """初始化默认文本展示器

        参数：
            data: 数据对象
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距
        layout.setContentsMargins(8, 8, 8, 8)
        # 创建标签
        label = QLabel(str(data) if data else "(无数据)")
        # 允许换行
        label.setWordWrap(True)
        # 设置样式
        label.setStyleSheet("color: #dcdcdc; font-size: 12px; background: transparent;")
        # 添加到布局
        layout.addWidget(label)
        # 添加弹性空间
        layout.addStretch()


# 注册后备展示器
presenter_registry.set_fallback(lambda data, parent: DefaultTextPresenter(data, parent))


# ═══════════════════════════════════════════════════════════════════════════
# 常见 VisionMaster 类型的内置展示器
# ═══════════════════════════════════════════════════════════════════════════

def _create_property_presenter(parent):
    """为模块结果标签页创建只读的 PropertyPanel

    参数：
        parent: 父对象

    返回：
        PropertyPanel 控件
    """
    from gui.property_panel import PropertyPanel
    from core.node_base import PropertyGroupNames
    # 创建只读的属性面板，只显示结果参数分组
    return PropertyPanel(parent, group_filter=[PropertyGroupNames.RESULT_PARAMETERS], readonly=True)


def _create_help_presenter(parent):
    """创建帮助文本浏览器

    参数：
        parent: 父对象

    返回：
        QTextBrowser 控件
    """
    from PyQt5.QtWidgets import QTextBrowser
    # 创建文本浏览器
    browser = QTextBrowser(parent)
    # 允许打开外部链接
    browser.setOpenExternalLinks(True)
    # 设置样式
    browser.setStyleSheet("""
        QTextBrowser {
            background: #252526; color: #dcdcdc; border: none;
            font-size: 12px; padding: 8px;
        }
    """)
    # 返回浏览器控件
    return browser


def _create_roi_presenter(parent):
    """创建简单的 ROI 信息标签

    参数：
        parent: 父对象

    返回：
        QLabel 控件
    """
    from PyQt5.QtWidgets import QLabel
    from PyQt5.QtCore import Qt as QtCore
    # 创建标签
    label = QLabel("ROI 编辑器", parent)
    # 设置样式
    label.setStyleSheet("color: #dcdcdc; padding: 8px; background: transparent;")
    # 设置居中对齐
    label.setAlignment(QtCore.AlignCenter)
    # 返回标签控件
    return label


def _register_builtins():
    """注册内置类型"""
    # 导入需要注册的类
    from core.node_base import VisionNodeData, ROINodeData, ROIBase, ConditionNodeData
    # 注册视觉节点数据 → 属性面板展示器
    presenter_registry.register(VisionNodeData, _create_property_presenter)
    # 注册ROI基类 → ROI展示器
    presenter_registry.register(ROIBase, _create_roi_presenter)
    # ConditionNodeData 也使用 PropertyPanel（通过 VisionNodeData 匹配）


# 导入时自动注册
_register_builtins()
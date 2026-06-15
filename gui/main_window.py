"""Main window
  - 左：流程资源 / 日志
  - 中：流程图多标签画布
  - 右：图像 / 模块结果 + 底部历史/当前/帮助
"""

import ctypes
import os
import json
import time
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QAction,
    QLabel, QTabWidget, QMessageBox, QFileDialog, QApplication, QFormLayout,
    QPushButton, QFrame, QMenuBar, QMenu, QLineEdit, QStackedWidget, QTabBar,
    QDialog, QScrollArea, QGroupBox, QGridLayout, QCheckBox, QListWidgetItem,
    QListWidget, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QTimer, QSettings, pyqtSignal, QEvent
from PyQt5.QtGui import QIcon, QPixmap, QCursor, QFont

from core.node_base import NodeBase, VisionNodeData, SrcFilesVisionNodeData, ROINodeData
from core.workflow import WorkflowEngine, WorkflowState
from core.project import project_service, DiagramData, ProjectItem
from core.events import EventType, event_system
from core.registry import node_registry
from gui.font_icons import FontIcons, FontIconButton, FontIconTextBlock, FontIconToggleButton

from gui.theme import theme_manager, ThemePickerDialog, connect_theme
from gui.theme_data import resolve_colors
from gui.node_editor.node_item import NodeState
from gui.toolbox_panel import ToolboxPanel
from gui.property_panel import PropertyPanel
from gui.result_panel import ResultPanel
from gui.image_viewer import ImageViewerPanel
from gui.log_panel import LogPanel
from gui.widgets.grid_splitter_box import GridSplitterBox
from gui.flow_resource_panel import FlowResourcePanel
from gui.node_editor.editor_widget import DiagramEditorWidget
from gui.start_page import StartPage
from gui.help_panel import HelpPanel
from services.workflow_runner import WorkflowRunner

# ── Windows 无边框窗口边框调整大小 ──────────────────────────

# WM_NCHITTEST 消息：Windows 发送此消息以确定鼠标位置的命中测试结果
WM_NCHITTEST = 0x0084
# WM_NCCALCSIZE 消息：用于计算窗口的非客户区大小
WM_NCCALCSIZE = 0x0083
# 命中测试结果常量：左侧边框
HTLEFT = 10
# 命中测试结果常量：右侧边框
HTRIGHT = 11
# 命中测试结果常量：顶部边框
HTTOP = 12
# 命中测试结果常量：左上角
HTTOPLEFT = 13
# 命中测试结果常量：右上角
HTTOPRIGHT = 14
# 命中测试结果常量：底部边框
HTBOTTOM = 15
# 命中测试结果常量：左下角
HTBOTTOMLEFT = 16
# 命中测试结果常量：右下角
HTBOTTOMRIGHT = 17
# 命中测试结果常量：标题栏区域（用于拖动窗口）
HTCAPTION = 2

# 边框调整大小边距（像素）
_BORDER = 8


class _MSG(ctypes.Structure):
    """Windows 消息结构体，用于接收消息参数"""
    _fields_ = [
        ("hwnd", ctypes.c_void_p),  # 窗口句柄
        ("message", ctypes.c_uint),  # 消息ID
        ("_pad", ctypes.c_uint),  # 填充字段
        ("wParam", ctypes.c_ulonglong),  # 消息的 wParam 参数
        ("lParam", ctypes.c_longlong),  # 消息的 lParam 参数
    ]


class PanelState:
    """面板状态管理类，用于保存和恢复各种面板的状态（宽度、高度、可见性等）"""

    GRP = "PanelState"  # QSettings 中的分组名称

    def __init__(self):
        """初始化面板状态管理器"""
        # 创建 QSettings 对象
        self.s = QSettings()

    def _k(self, key):
        """生成完整的键名

        参数：
            key: 键名

        返回：
            带分组前缀的完整键名
        """
        return f"{self.GRP}/{key}"

    def get_i(self, key, default=0):
        """获取整数值

        参数：
            key: 键名
            default: 默认值

        返回：
            整数值
        """
        # 从 QSettings 获取值，如果不存在则返回默认值
        return int(self.s.value(self._k(key), default) or default)

    def set_i(self, key, value):
        """设置整数值

        参数：
            key: 键名
            value: 整数值
        """
        # 保存整数值到 QSettings
        self.s.setValue(self._k(key), value)

    def get_b(self, key, default=True):
        """获取布尔值

        参数：
            key: 键名
            default: 默认值

        返回：
            布尔值
        """
        # 从 QSettings 获取值
        value = self.s.value(self._k(key), default)
        # 如果是字符串，转换为布尔值；否则直接返回
        return str(value).lower() == "true" if isinstance(value, str) else bool(value) if value is not None else default

    def set_b(self, key, value):
        """设置布尔值

        参数：
            key: 键名
            value: 布尔值
        """
        # 保存布尔值到 QSettings（转换为字符串 'true' 或 'false'）
        self.s.setValue(self._k(key), "true" if value else "false")


# 创建全局面板状态实例
_ps = PanelState()

# UI 配置文件版本号
_UI_PROFILE_VERSION = 1
# 默认窗口宽度（像素）
_DEFAULT_WINDOW_WIDTH = 1460
# 默认窗口高度（像素）
_DEFAULT_WINDOW_HEIGHT = 900
# 默认左侧面板宽度（像素）
_DEFAULT_LEFT_WIDTH = 280
# 默认右侧面板宽度（像素）
_DEFAULT_RIGHT_WIDTH = 850
# 默认中央区域高度（像素）
_DEFAULT_CENTER_HEIGHT = 800
# 默认底部面板高度（像素）
_DEFAULT_BOTTOM_HEIGHT = 180
# 默认资源面板高度（像素）
_DEFAULT_RESOURCE_HEIGHT = 118
# 默认标题栏高度（像素）
_DEFAULT_CAPTION_HEIGHT = 85


def _app_config_path():
    """获取应用配置文件的路径

    返回：
        配置文件路径
    """
    # 配置文件位于当前文件所在目录的父目录下
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "app_config.json")


def _load_app_config():
    """加载应用配置文件

    返回：
        配置字典
    """
    try:
        # 打开配置文件
        with open(_app_config_path(), "r", encoding="utf-8") as f:
            # 解析 JSON 数据
            data = json.load(f)
            # 确保返回字典类型
            return data if isinstance(data, dict) else {}
    except Exception:
        # 出错时返回空字典
        return {}


def _save_app_config(data: dict):
    """保存应用配置文件

    参数：
        data: 配置字典
    """
    # 打开配置文件写入
    with open(_app_config_path(), "w", encoding="utf-8") as f:
        # 将数据序列化为 JSON 格式写入文件
        json.dump(data, f, indent=2, ensure_ascii=False)


class _Sep(QFrame):
    """分隔线控件"""

    def __init__(self, vertical=True):
        """初始化分隔线

        参数：
            vertical: 是否为垂直分隔线（True=垂直，False=水平）
        """
        # 调用父类 QFrame 的构造函数
        super().__init__()
        # 设置帧形状：垂直分隔线或水平分隔线
        self.setFrameShape(QFrame.VLine if vertical else QFrame.HLine)
        # 设置样式表：颜色为深灰色
        self.setStyleSheet("color: #505050;")
        # 如果是垂直分隔线
        if vertical:
            # 设置固定宽度为1像素
            self.setFixedWidth(1)
        else:
            # 设置固定高度为1像素
            self.setFixedHeight(1)


def _hsep():
    """创建垂直分隔线（实际上是水平分隔符，函数名是历史遗留）

    返回：
        垂直分隔线控件
    """
    return _Sep(True)


def _cmd_btn_qss():
    """工具栏命令按钮样式表 — 从主题动态生成

    通过 explicit setEnabled() 调用 + :disabled QSS 提供视觉反馈

    返回：
        样式表字符串
    """
    return f"""
    QPushButton {{
        background: transparent;
        border: none;
        border-radius: 2px;
        padding: 5px 0;
        color: {theme_manager.color('text_primary').name()};
    }}
    QPushButton:hover {{ background: {theme_manager.color('bg_surface_hover').name()}; }}
    QPushButton:pressed {{ background: {theme_manager.color('accent').name()}; color: white; }}
    QPushButton:disabled {{
        color: {theme_manager.color('text_secondary').name()};
        background: transparent;
    }}
"""


def _tab_qss():
    """标签页控件样式表 — 从主题动态生成

    标签页文字使用 text_title 以提高清晰度

    返回：
        样式表字符串
    """
    # 获取主题管理器
    c = theme_manager
    # 返回样式表
    return f"""
    QTabWidget::pane {{ border: none; background: {c.color('bg_surface').name()}; }}
    QTabWidget:focus {{ outline: 0; }}
    QTabWidget::pane:focus {{ outline: 0; border: none; }}
    QTabBar:focus {{ outline: 0; }}
    QTabBar::tab {{
        background: {c.color('bg_surface_raised').name()};
        color: {c.color('text_title').name()};
        padding: 3px 8px;
        border: none;
        border-bottom: 2px solid transparent;
        font-size: 11px;
    }}
    QTabBar::tab:selected {{ background: {c.color('bg_surface').name()}; border-bottom: 2px solid {c.color('accent').name()}; }}
    QTabBar::tab:focus {{ outline: 0; }}
    QTabBar::tab:hover {{ background: {c.color('bg_surface_hover').name()}; }}
    QTabBar::close-button {{
        subcontrol-position: right;
        padding: 3px;
        margin-left: 4px;
    }}
    QTabBar::close-button:hover {{ background: #c42b1c; border-radius: 3px; }}
"""


# 全局命令按钮样式表
_CMD_BTN = _cmd_btn_qss()
# 全局标签页样式表
_TAB_STYLE = _tab_qss()


def find_child_by_tip(parent, tip):
    """通过工具提示递归查找可见的子控件

    参数：
        parent: 父控件
        tip: 工具提示文本

    返回：
        找到的控件，如果没有找到则返回 None
    """
    try:
        # 遍历父控件的所有子控件
        for w in parent.findChildren(QWidget):
            try:
                # 如果控件可见且有 toolTip 属性，且 toolTip 匹配
                if w.isVisible() and hasattr(w, 'toolTip') and w.toolTip() == tip:
                    # 返回找到的控件
                    return w
            except Exception:
                continue
    except Exception:
        pass
    # 没有找到返回 None
    return None


class _InlineStatusStrip(QWidget):
    """内联状态栏控件，显示在窗口底部"""

    def __init__(self, accent: str = "#4caf50", parent=None):
        """初始化内联状态栏

        参数：
            accent: 强调色（用于图标颜色）
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 设置焦点策略为无焦点（阻止Windows原生蓝色焦点框）
        self.setFocusPolicy(Qt.NoFocus)
        # 保存强调色
        self._accent = accent
        # 当前图标颜色，初始为强调色
        self._current_icon_color = accent
        # 创建水平布局
        layout = QHBoxLayout(self)
        # 设置布局边距
        layout.setContentsMargins(10, 4, 10, 4)
        # 设置布局间距为8
        layout.setSpacing(8)

        # 图标标签（圆点）
        self._icon = QLabel("●")
        # 添加到布局
        layout.addWidget(self._icon)

        # 文本标签
        self._label = QLabel("就绪")
        # 设置字体为微软雅黑，大小11
        self._label.setFont(QFont("Microsoft YaHei", 11))
        # 添加到布局，拉伸因子为1
        layout.addWidget(self._label, 1)

        # 连接主题变化信号，刷新样式
        connect_theme(self._refresh_qss)

    def _refresh_qss(self):
        """刷新样式表（主题变化时调用）"""
        # 获取主题管理器
        tm = theme_manager
        # 获取各种颜色
        bg = tm.color("bg_surface_deep").name()  # 深层背景色
        border = tm.color("border").name()  # 边框色
        text = tm.color("text_primary").name()  # 主文本色
        # 设置控件样式
        self.setStyleSheet(
            f"background: {bg}; border-top: 1px solid {border}; outline: none;"
        )
        # 设置文本标签样式
        self._label.setStyleSheet(
            f"color: {text}; font-size: 11px; background: transparent;"
        )
        # 设置图标样式
        self._icon.setStyleSheet(
            f"color: {self._current_icon_color}; font-weight: bold; background: transparent;"
        )

    def set_status(self, text: str, color: str | None = None):
        """设置状态文本和颜色

        参数：
            text: 状态文本
            color: 图标颜色
        """
        # 设置文本标签内容
        self._label.setText(text)
        # 更新当前图标颜色（使用传入颜色或默认强调色）
        self._current_icon_color = color or self._accent
        # 更新图标样式
        self._icon.setStyleSheet(
            f"color: {self._current_icon_color}; font-weight: bold; background: transparent;"
        )


class _DiagramTabHeader(QWidget):
    """图表标签页头部控件，包含名称编辑框和操作按钮"""

    # 重命名请求信号
    rename_requested = pyqtSignal(str)
    # 运行请求信号
    run_requested = pyqtSignal()
    # 停止请求信号
    stop_requested = pyqtSignal()
    # 重置请求信号
    reset_requested = pyqtSignal()

    def __init__(self, name: str, parent=None):
        """初始化图表标签页头部

        参数：
            name: 图表名称
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 创建水平布局
        layout = QHBoxLayout(self)
        # 设置布局边距
        layout.setContentsMargins(6, 0, 6, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

        # 名称编辑框
        self._name_edit = QLineEdit(name)
        # 设置无边框
        self._name_edit.setFrame(False)
        # 设置固定高度22像素
        self._name_edit.setFixedHeight(22)
        # 设置最小宽度60像素
        self._name_edit.setMinimumWidth(60)
        # 连接编辑完成信号
        self._name_edit.editingFinished.connect(self._emit_rename)
        # 刷新样式
        self._refresh_qss()
        # 添加到布局，拉伸因子为1
        layout.addWidget(self._name_edit, 1)

    def _refresh_qss(self):
        """刷新样式表（主题变化时调用）"""
        # 获取主题管理器
        tm = theme_manager
        # 设置编辑框样式
        self._name_edit.setStyleSheet(
            f"QLineEdit {{ background: transparent; color: {tm.color('text_title').name()};"
            f" border: none; padding: 0 2px; font-family: 'Microsoft YaHei'; font-size: 12px; }}"
            f"QLineEdit:focus {{ border-bottom: 1px solid {tm.color('accent').name()}; }}"
        )

    def _emit_rename(self):
        """发出重命名信号"""
        # 获取编辑框文本（去除首尾空格）
        name = self._name_edit.text().strip()
        # 发出重命名信号
        self.rename_requested.emit(name)

    def set_name(self, name: str):
        """设置图表名称

        参数：
            name: 图表名称
        """
        # 如果名称不同，更新编辑框文本
        if self._name_edit.text() != name:
            self._name_edit.setText(name)

    def set_active(self, active: bool):
        """设置激活状态

        参数：
            active: 是否激活
        """
        # 当前不需要额外处理，保留为空
        pass


class _SettingsDialog(QDialog):
    """设置对话框

    布局：QTabWidget 分组标签页 + 每个标签页内的导航框 + 底部按钮
    """

    def __init__(self, parent=None):
        """初始化设置对话框

        参数：
            parent: 父对象
        """
        # 调用父类QDialog的构造函数
        super().__init__(parent)
        # 设置窗口标题
        self.setWindowTitle("系统设置")
        # 设置最小尺寸720x500
        self.setMinimumSize(720, 500)
        # 保存原始主题ID
        self._original_theme = theme_manager.current_theme_id
        # 设置UI
        self._setup_ui()
        # 加载设置
        self._load_settings()

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局间距为0
        layout.setSpacing(0)
        # 创建标签页控件
        self._group_tabs = QTabWidget()
        # 添加到布局，拉伸因子为1
        layout.addWidget(self._group_tabs, 1)
        # 构建主题标签页
        self._build_theme_tab()
        # 构建基本设置标签页
        self._build_basic_tab()
        # 构建设置标签页
        self._build_display_tab()
        # 创建按钮行
        btn_row = QHBoxLayout()
        # 设置按钮行边距
        btn_row.setContentsMargins(10, 8, 10, 8)
        # 添加弹性空间
        btn_row.addStretch()
        # 恢复默认按钮
        restore_btn = QPushButton("恢复默认")
        # 连接点击信号
        restore_btn.clicked.connect(self._on_restore_default)
        # 添加到按钮行
        btn_row.addWidget(restore_btn)
        # 取消按钮
        cancel_btn = QPushButton("取消")
        # 连接点击信号
        cancel_btn.clicked.connect(self._on_cancel)
        # 添加到按钮行
        btn_row.addWidget(cancel_btn)
        # 确定按钮
        ok_btn = QPushButton("确定")
        # 设置为默认按钮
        ok_btn.setDefault(True)
        # 连接点击信号
        ok_btn.clicked.connect(self.accept)
        # 添加到按钮行
        btn_row.addWidget(ok_btn)
        # 添加按钮行到布局
        layout.addLayout(btn_row)

    # -- 导航框辅助方法 --
    def _make_nav_box(self):
        """创建导航框（分割器 + 导航列表 + 堆叠窗口）

        返回：
            (分割器, 导航列表, 堆叠窗口) 元组
        """
        # 创建水平分割器
        box = QSplitter(Qt.Horizontal)
        # 创建导航列表
        nav = QListWidget()
        # 设置固定宽度130像素
        nav.setFixedWidth(130)
        # 设置间距为0
        nav.setSpacing(0)
        # 创建堆叠窗口
        stack = QStackedWidget()
        # 添加导航列表到分割器
        box.addWidget(nav)
        # 添加堆叠窗口到分割器
        box.addWidget(stack)
        # 连接导航列表当前行变化信号
        nav.currentRowChanged.connect(stack.setCurrentIndex)
        # 返回分割器、导航列表、堆叠窗口
        return box, nav, stack

    @staticmethod
    def _add_nav_item(nav, stack, name, page):
        """添加导航项

        参数：
            nav: 导航列表
            stack: 堆叠窗口
            name: 项名称
            page: 页面控件
        """
        # 添加列表项
        nav.addItem(QListWidgetItem(name))
        # 添加页面到堆叠窗口
        stack.addWidget(page)

    # -- Tab 1: 主题  --
    def _build_theme_tab(self):
        """构建主题标签页"""
        # 创建导航框
        box, nav, stack = self._make_nav_box()
        # 创建页面（滚动区域）
        page = QScrollArea()
        # 设置控件可调整大小
        page.setWidgetResizable(True)
        # 设置无边框
        page.setFrameShape(QScrollArea.NoFrame)
        # 创建页面控件
        pw = QWidget()
        # 创建垂直布局
        vl = QVBoxLayout(pw)
        # 设置布局间距为10
        vl.setSpacing(10)
        # 添加说明标签
        vl.addWidget(QLabel("选择颜色主题，即时预览："))
        # 按分组收集主题
        groups = {}
        # 遍历所有可用主题
        for t in theme_manager.available_themes:
            groups.setdefault(t.group, []).append(t)
        # 按顺序处理分组
        for group_name in ["强力推荐", "纯色", "外部主题"]:
            # 如果分组不存在，跳过
            if group_name not in groups:
                continue
            # 创建分组框
            gb = QGroupBox(group_name)
            # 创建网格布局
            grid = QGridLayout()
            # 设置网格间距为8
            grid.setSpacing(8)
            # 遍历分组中的主题
            for i, tdef in enumerate(groups[group_name]):
                # 创建主题卡片
                card = self._make_theme_card(tdef)
                # 添加到网格布局（每行2列）
                grid.addWidget(card, i // 2, i % 2)
            # 设置分组框布局
            gb.setLayout(grid)
            # 添加到垂直布局
            vl.addWidget(gb)
        # 添加弹性空间
        vl.addStretch()
        # 设置滚动区域控件
        page.setWidget(pw)
        # 添加导航项
        self._add_nav_item(nav, stack, "颜色主题", page)
        # 设置选中第一项
        nav.setCurrentRow(0)
        # 添加标签页
        self._group_tabs.addTab(box, "主题")

    def _make_theme_card(self, tdef):
        """创建主题卡片

        参数：
            tdef: 主题定义

        返回：
            卡片控件
        """
        # 解析主题颜色
        c = resolve_colors(tdef)
        # 创建卡片框架
        card = QFrame()
        # 设置固定大小200x100
        card.setFixedSize(200, 100)
        # 设置光标为手指形状
        card.setCursor(Qt.PointingHandCursor)
        # 设置工具提示
        card.setToolTip(f"{tdef.name} - {tdef.description}")
        # 检查是否为当前主题
        is_current = tdef.id == theme_manager.current_theme_id
        # 边框颜色：当前主题使用强调色，否则使用边框色
        border = c.get("accent", "#3399FF") if is_current else c.get("border", "#555")
        # 边框宽度：当前主题为2，否则为1
        bw = 2 if is_current else 1
        # 设置卡片样式
        card.setStyleSheet(
            f"QFrame {{ background: {c.get('bg_surface', '#333')}; "
            f"border: {bw}px solid {border}; border-radius: 6px; }}")
        # 设置鼠标按下事件
        card.mousePressEvent = lambda e, tid=tdef.id: self._on_theme_select(tid)
        # 创建内部垂直布局
        inner = QVBoxLayout(card)
        # 设置布局边距
        inner.setContentsMargins(8, 6, 8, 6)
        # 设置布局间距为3
        inner.setSpacing(3)
        # 提示标签
        p = QLabel(f"[{tdef.prompt or tdef.name}]")
        p.setAlignment(Qt.AlignCenter)
        p.setStyleSheet(f"color: {c.get('text_title', '#ccc')}; font-weight: bold; "
                        f"border: none; background: transparent;")
        inner.addWidget(p)
        # 名称标签
        n = QLabel(tdef.name)
        n.setAlignment(Qt.AlignCenter)
        n.setStyleSheet(f"color: {c.get('text_primary', '#ccc')}; border: none; background: transparent;")
        inner.addWidget(n)
        # 描述标签
        d = QLabel(tdef.description or "")
        d.setAlignment(Qt.AlignCenter)
        d.setWordWrap(True)
        d.setStyleSheet(f"color: {c.get('text_secondary', '#999')}; font-size: 9px; "
                        f"border: none; background: transparent;")
        inner.addWidget(d)
        return card

    def _on_theme_select(self, theme_id):
        """主题选择回调

        参数：
            theme_id: 主题ID
        """
        # 切换主题
        theme_manager.set_theme(theme_id)

    # -- Tab 2: 基本设置 --
    def _build_basic_tab(self):
        """构建基本设置标签页"""
        # 创建导航框
        box, nav, stack = self._make_nav_box()
        # 创建页面（滚动区域）
        page = QScrollArea()
        # 设置控件可调整大小
        page.setWidgetResizable(True)
        # 设置无边框
        page.setFrameShape(QScrollArea.NoFrame)
        # 创建页面控件
        pw = QWidget()
        # 创建垂直布局
        vl = QVBoxLayout(pw)
        # 创建分组框
        gb = QGroupBox("通用设置")
        # 创建表单布局
        form = QFormLayout(gb)
        # 开机自动启动复选框
        self._chk_auto_start = QCheckBox()
        form.addRow("开机自动启动：", self._chk_auto_start)
        # 任务栏显示图标复选框
        self._chk_tray = QCheckBox()
        form.addRow("任务栏显示图标：", self._chk_tray)
        # 显示主题按钮复选框
        self._chk_theme_btn = QCheckBox()
        form.addRow("显示主题按钮：", self._chk_theme_btn)
        # 添加分组框到布局
        vl.addWidget(gb)
        # 添加弹性空间
        vl.addStretch()
        # 设置滚动区域控件
        page.setWidget(pw)
        # 添加导航项
        self._add_nav_item(nav, stack, "通用设置", page)
        # 设置选中第一项
        nav.setCurrentRow(0)
        # 添加标签页
        self._group_tabs.addTab(box, "基本设置")

    # -- Tab 3: 显示设置 --
    def _build_display_tab(self):
        """构建设置标签页"""
        # 创建导航框
        box, nav, stack = self._make_nav_box()
        # 创建页面（滚动区域）
        page = QScrollArea()
        # 设置控件可调整大小
        page.setWidgetResizable(True)
        # 设置无边框
        page.setFrameShape(QScrollArea.NoFrame)
        # 创建页面控件
        pw = QWidget()
        # 创建垂直布局
        vl = QVBoxLayout(pw)
        # 创建分组框
        gb = QGroupBox("画布设置")
        # 创建表单布局
        form = QFormLayout(gb)
        # 显示画布网格复选框
        self._chk_show_grid = QCheckBox()
        form.addRow("显示画布网格：", self._chk_show_grid)
        # 添加分组框到布局
        vl.addWidget(gb)
        # 添加弹性空间
        vl.addStretch()
        # 设置滚动区域控件
        page.setWidget(pw)
        # 添加导航项
        self._add_nav_item(nav, stack, "画布设置", page)
        # 设置选中第一项
        nav.setCurrentRow(0)
        # 添加标签页
        self._group_tabs.addTab(box, "显示设置")

    # -- 持久化 --
    def _config_path(self):
        """获取配置文件路径

        返回：
            配置文件路径
        """
        # 配置文件位于当前文件所在目录的父目录下
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "app_config.json")

    def _load_settings(self):
        """加载设置"""
        try:
            # 打开配置文件
            with open(self._config_path(), "r", encoding="utf-8") as f:
                # 解析JSON数据
                data = json.load(f)
        except Exception:
            # 出错时使用空字典
            data = {}
        # 设置复选框状态
        self._chk_auto_start.setChecked(data.get("auto_start", False))
        self._chk_tray.setChecked(data.get("show_tray", True))
        self._chk_theme_btn.setChecked(data.get("show_theme_btn", True))
        self._chk_show_grid.setChecked(data.get("show_grid", True))

    def _save_settings(self):
        """保存设置"""
        # 构建数据字典
        data = {
            "auto_start": self._chk_auto_start.isChecked(),
            "show_tray": self._chk_tray.isChecked(),
            "show_theme_btn": self._chk_theme_btn.isChecked(),
            "show_grid": self._chk_show_grid.isChecked(),
        }
        # 写入配置文件
        with open(self._config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _on_restore_default(self):
        """恢复默认设置"""
        # 恢复复选框默认值
        self._chk_auto_start.setChecked(False)
        self._chk_tray.setChecked(True)
        self._chk_theme_btn.setChecked(False)
        self._chk_show_grid.setChecked(True)
        # 如果当前主题与原始主题不同
        if self._original_theme != theme_manager.current_theme_id:
            # 恢复原始主题
            theme_manager.set_theme(self._original_theme)

    def _on_cancel(self):
        """取消按钮处理"""
        # 如果当前主题与原始主题不同
        if self._original_theme != theme_manager.current_theme_id:
            # 恢复原始主题
            theme_manager.set_theme(self._original_theme)
        # 重新加载设置
        self._load_settings()
        # 拒绝对话框
        self.reject()

    def accept(self):
        """确定按钮处理"""
        # 保存设置
        self._save_settings()
        # 调用父类的accept方法
        super().accept()


class MainWindow(QMainWindow):
    """
    主窗口类

    参数：
        ctx: AppContext DI容器。如果为None，则使用 get_app_context() 作为后备。
    """

    # 用于跨线程工作流状态UI更新的内部信号
    # Qt 自动将工作线程的信号队列到主线程
    _wf_ui_update = pyqtSignal(str, dict)

    def __init__(self, ctx=None):
        """初始化主窗口

        参数：
            ctx: 应用上下文（依赖注入容器）
        """
        # 调用父类QMainWindow的构造函数
        super().__init__()
        # 如果未提供上下文，获取默认上下文
        if ctx is None:
            from services.app_context import get_app_context
            ctx = get_app_context()
        # 保存应用上下文（包含总线事务，节点组，节点注册，节点服务，项目服务和主题服务）
        self._ctx = ctx
        # 当前工作流引擎，初始为None
        self._workflow: WorkflowEngine | None = None
        # 当前选中的节点
        self._selected_node: NodeBase | None = None
        # 流程图编辑器控件
        self._diagram_editor: DiagramEditorWidget | None = None
        # 流程图页面缓存字典
        self._diagram_pages: dict[str, QWidget] = {}
        # 流程图标签页头部组件缓存字典
        self._diagram_headers: dict[str, _DiagramTabHeader] = {}
        # 项目是否已加载标志
        self._project_loaded = False
        # 是否处于连续运行模式
        self._continuous_mode = False
        # 是否请求停止运行
        self._stop_requested = False
        # 工作流运行器
        self._wf_runner = WorkflowRunner()
        # 实时预览定时器
        self._live_preview_timer = QTimer(self)
        # 设置定时器间隔为50毫秒（约20 FPS）
        self._live_preview_timer.setInterval(50)
        # 连接定时器超时信号到实时预览更新方法
        self._live_preview_timer.timeout.connect(self._tick_live_preview)
        # 左侧面板是否可见，初始为True
        self._left_panel_visible = True
        # 右侧面板是否可见，初始为True
        self._right_panel_visible = True
        # 保存的右侧面板宽度（从QSettings加载，默认420）
        self._saved_right_width = _ps.get_i("right_width", 420)
        # 加载共享的UI布局配置文件
        self._ui_layout_profile = self._load_shared_ui_layout_profile()
        # 计算UI布局度量（为了适应不同屏幕显示一样的画面）
        self._ui_layout_metrics = self._compute_ui_layout_metrics()
        # 是否等待捕获UI布局配置（第一次运行没有配置会捕获一次）
        self._ui_profile_capture_pending = self._ui_layout_profile is None
        # 是否已经安排了UI布局配置捕获（避免重复捕获）
        self._ui_profile_capture_scheduled = False

        # 连接工作流UI更新信号到处理函数
        self._wf_ui_update.connect(self._on_wf_ui_update)

        # 设置窗口
        self._setup_window()
        # 设置标题栏
        self._setup_caption_bar()
        # 设置主界面
        self._setup_main_surface()
        # 设置状态栏
        self._setup_status_bar()
        # 连接信号
        self._wire_signals()
        # 连接事件
        self._connect_events()

        # 创建时钟定时器
        self._clock = QTimer(self)
        # 连接定时器超时信号到更新时钟方法
        self._clock.timeout.connect(self._update_clock)
        # 启动时钟定时器，间隔1000毫秒（1秒）
        self._clock.start(1000)

        # 显示起始页
        self._show_start_page()
        # 应用设置
        self._apply_settings()
        # 启动时加载模板
        self._load_templates_on_startup()

    def _setup_window(self):
        """设置窗口的基本属性"""
        # 设置窗口标题
        self.setWindowTitle("VisionFlow — VisionFlow")
        # 设置窗口标志为普通窗口 + 无边框
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        # 获取布局度量中的窗口宽度
        width = self._ui_layout_metrics["window_width"]
        # 获取布局度量中的窗口高度
        height = self._ui_layout_metrics["window_height"]
        # 调整窗口大小
        self.resize(width, height)
        # 设置最小窗口大小为1180x720
        self.setMinimumSize(1180, 720)
        # 设置窗口调色板（从主题管理器获取）
        self.setPalette(theme_manager.colors.to_palette())
        # 设置窗口样式表（从主题管理器获取）
        self.setStyleSheet(theme_manager.get_stylesheet())
        # 连接主题变化信号，主题改变时应用新主题
        theme_manager.theme_changed.connect(lambda _: self._apply_theme())
        # 创建字体：微软雅黑，9号
        font = QFont("Microsoft YaHei", 9)
        # 设置字体
        self.setFont(font)
        # 获取图标路径
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "logo.ico")
        # 如果图标文件存在
        if os.path.exists(icon_path):
            # 设置窗口图标
            self.setWindowIcon(QIcon(icon_path))
        # 获取主屏幕
        screen = QApplication.primaryScreen()
        # 如果屏幕存在
        if screen is not None:
            # 获取屏幕几何信息
            geometry = screen.geometry()
            # 计算窗口居中位置
            x = (geometry.width() - width) // 2
            y = (geometry.height() - height) // 2
            # 移动窗口到屏幕中心
            self.move(x, y)

        # 初始化DWM阴影
        self._init_dwm_shadow()

    def _init_dwm_shadow(self):
        """将 DWM 框架扩展到客户端区域，以实现原生阴影效果"""
        try:
            # 获取窗口句柄
            hwnd = int(self.winId())
            # 设置边距为 -1 以扩展到整个窗口
            margins = (ctypes.c_int * 4)(-1, -1, -1, -1)
            # 调用 DWM API 扩展框架到客户端区域
            ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, margins)
        except Exception:
            # 如果失败，忽略异常
            pass

    def showEvent(self, event):
        """窗口显示事件

        参数：
            event: 显示事件对象
        """
        # 调用父类的showEvent
        super().showEvent(event)
        # 初始化DWM阴影
        self._init_dwm_shadow()
        # 安排UI布局配置捕获
        self._schedule_ui_profile_capture()

    def _load_shared_ui_layout_profile(self):
        """加载共享的UI布局配置

        返回：
            UI布局配置字典，如果不存在则返回None
        """
        # 从根目录的 app_config.json 中加载 ui_layout_profile
        profile = _load_app_config().get("ui_layout_profile")
        # 确保返回的是字典类型
        return profile if isinstance(profile, dict) else None

    def _screen_available_size(self):
        """获取屏幕可用尺寸

        返回：
            (宽度, 高度) 元组
        """
        # 获取主屏幕
        screen = QApplication.primaryScreen()
        # 如果屏幕不存在，返回默认尺寸
        if screen is None:
            return _DEFAULT_WINDOW_WIDTH, _DEFAULT_WINDOW_HEIGHT
        # 获取屏幕可用几何区域
        geometry = screen.availableGeometry()
        # 获取宽度，至少为1
        width = max(1, geometry.width())
        # 获取高度，至少为1
        height = max(1, geometry.height())
        return width, height

    @staticmethod
    def _scaled_int(value: int | float, scale: float, minimum: int) -> int:
        """缩放整数值

        参数：
            value: 原始值
            scale: 缩放比例
            minimum: 最小值

        返回：
            缩放后的整数值
        """
        # 计算缩放后的值，四舍五入，并确保不小于最小值
        return max(minimum, int(round(float(value) * scale)))

    def _compute_ui_layout_metrics(self):
        """计算UI布局度量

        返回：
            布局度量字典
        """
        # 从QSettings加载左侧面板宽度
        left_width = _ps.get_i("left_width", _DEFAULT_LEFT_WIDTH)
        # 从QSettings加载底部面板高度
        bottom_height = _ps.get_i("bottom_height", _DEFAULT_BOTTOM_HEIGHT)
        # 默认度量值
        metrics = {
            "window_width": _ps.get_i("window_width", _DEFAULT_WINDOW_WIDTH),  # 窗口宽度
            "window_height": _ps.get_i("window_height", _DEFAULT_WINDOW_HEIGHT),  # 窗口高度
            "left_width": left_width,  # 左侧面板宽度
            "right_width": _DEFAULT_RIGHT_WIDTH,  # 右侧面板宽度
            "center_height": _DEFAULT_CENTER_HEIGHT,  # 中央区域高度
            "bottom_height": bottom_height,  # 底部面板高度
            "resource_height": _DEFAULT_RESOURCE_HEIGHT,  # 资源面板高度
            "caption_height": _DEFAULT_CAPTION_HEIGHT,  # 标题栏高度
        }

        # 获取UI布局配置
        profile = self._ui_layout_profile
        # 如果没有配置，返回默认值
        if not profile:
            return metrics

        # 获取屏幕配置
        base_screen = profile.get("screen") or {}
        # 获取基础屏幕宽度
        base_width = max(1, int(base_screen.get("width", metrics["window_width"])))
        # 获取基础屏幕高度
        base_height = max(1, int(base_screen.get("height", metrics["window_height"])))
        # 获取当前屏幕尺寸
        current_width, current_height = self._screen_available_size()
        # 计算缩放比例
        scale_x = current_width / base_width
        scale_y = current_height / base_height

        # 获取窗口配置
        window = profile.get("window") or {}
        # 获取布局配置
        layout = profile.get("layout") or {}

        # 计算缩放后的窗口宽度（不超过当前屏幕宽度，不小于1180）
        metrics["window_width"] = min(
            current_width,
            self._scaled_int(window.get("width", metrics["window_width"]), scale_x, 1180),
        )
        # 计算缩放后的窗口高度（不超过当前屏幕高度，不小于720）
        metrics["window_height"] = min(
            current_height,
            self._scaled_int(window.get("height", metrics["window_height"]), scale_y, 720),
        )
        # 计算缩放后的左侧面板宽度（不小于50）
        metrics["left_width"] = self._scaled_int(layout.get("left_width", metrics["left_width"]), scale_x, 50)
        # 计算缩放后的右侧面板宽度（不小于420）
        metrics["right_width"] = self._scaled_int(layout.get("right_width", metrics["right_width"]), scale_x, 420)
        # 计算缩放后的中央区域高度（不小于420）
        metrics["center_height"] = self._scaled_int(layout.get("center_height", metrics["center_height"]), scale_y, 420)
        # 计算缩放后的底部面板高度（不小于120）
        metrics["bottom_height"] = self._scaled_int(layout.get("bottom_height", metrics["bottom_height"]), scale_y, 120)
        # 计算缩放后的资源面板高度（不小于84）
        metrics["resource_height"] = self._scaled_int(layout.get("resource_height", metrics["resource_height"]),
                                                      scale_y, 84)
        # 计算缩放后的标题栏高度（不小于72）
        metrics["caption_height"] = self._scaled_int(layout.get("caption_height", metrics["caption_height"]), scale_y,
                                                     72)

        # 左侧面板最大宽度限制（窗口宽度 - 980）
        max_left = max(50, metrics["window_width"] - 980)
        # 限制左侧面板宽度不超过最大值
        metrics["left_width"] = min(metrics["left_width"], max_left)
        # 右侧面板最大宽度限制
        max_right = max(420, metrics["window_width"] - metrics["left_width"] - 320)
        # 限制右侧面板宽度不超过最大值
        metrics["right_width"] = min(metrics["right_width"], max_right)
        # 中央区域最大高度限制
        max_center_height = max(420, metrics["window_height"] - 120)
        # 限制中央区域高度不超过最大值
        metrics["center_height"] = min(metrics["center_height"], max_center_height)
        # 底部面板最大高度限制
        max_bottom_height = max(120, metrics["window_height"] - 360)
        # 限制底部面板高度不超过最大值
        metrics["bottom_height"] = min(metrics["bottom_height"], max_bottom_height)
        # 资源面板最大高度限制为180
        metrics["resource_height"] = min(metrics["resource_height"], 180)
        return metrics

    def _schedule_ui_profile_capture(self):
        """安排UI布局配置捕获"""
        # 如果不需要捕获或已经安排了捕获，返回
        if not self._ui_profile_capture_pending or self._ui_profile_capture_scheduled:
            return
        # 设置已安排捕获标志
        self._ui_profile_capture_scheduled = True
        # 在下一个事件循环中执行捕获（延迟到UI完全初始化后）
        QTimer.singleShot(0, self._capture_ui_layout_profile)

    def _capture_ui_layout_profile(self):
        """捕获当前UI布局配置"""
        # 重置已安排捕获标志
        self._ui_profile_capture_scheduled = False
        # 如果不再需要捕获，返回
        if not self._ui_profile_capture_pending:
            return

        # 获取屏幕可用尺寸
        screen_width, screen_height = self._screen_available_size()
        # 获取左侧面板宽度
        left_width = self._left_box.menu_width() if hasattr(self, "_left_box") else _DEFAULT_LEFT_WIDTH
        # 获取右侧面板宽度
        right_width = self._right_panel.width() if hasattr(self, "_right_panel") and self._right_panel.width() > 0 else _DEFAULT_RIGHT_WIDTH
        # 获取中央区域高度
        center_height = self._center_splitter.widget(0).height() if hasattr(self, "_center_splitter") else _DEFAULT_CENTER_HEIGHT
        # 如果中央区域高度无效，使用默认值
        if center_height <= 0:
            center_height = _DEFAULT_CENTER_HEIGHT
        # 获取底部面板高度
        bottom_height = _ps.get_i("bottom_height", _DEFAULT_BOTTOM_HEIGHT)
        # 如果有中央分割器，获取其大小
        if hasattr(self, "_center_splitter"):
            sizes = self._center_splitter.sizes()
            if len(sizes) >= 2 and sizes[1] > 0:
                bottom_height = sizes[1]

        # 加载应用配置
        data = _load_app_config()
        # 保存UI布局配置
        data["ui_layout_profile"] = {
            "version": _UI_PROFILE_VERSION,                                    # 配置文件版本
            "screen": {                                                        # 屏幕信息
                "width": screen_width,                                         # 屏幕宽度
                "height": screen_height,                                       # 屏幕高度
            },
            "window": {                                                        # 窗口信息
                "width": self.width(),                                         # 窗口宽度
                "height": self.height(),                                       # 窗口高度
            },
            "layout": {                                                        # 布局信息
                "left_width": left_width,                                      # 左侧面板宽度
                "right_width": right_width,                                    # 右侧面板宽度
                "center_height": center_height,                                # 中央区域高度
                "bottom_height": bottom_height,                                # 底部面板高度
                "resource_height": self._resource_panel.height() if hasattr(self, "_resource_panel") and self._resource_panel.height() > 0 else _DEFAULT_RESOURCE_HEIGHT,  # 资源面板高度
                "caption_height": self._caption_bar.height() if hasattr(self, "_caption_bar") and self._caption_bar.height() > 0 else _DEFAULT_CAPTION_HEIGHT,  # 标题栏高度
            },
        }
        # 保存应用配置
        _save_app_config(data)
        # 更新UI布局配置
        self._ui_layout_profile = data["ui_layout_profile"]
        # 清除待捕获标志
        self._ui_profile_capture_pending = False

    def changeEvent(self, event):
        """窗口状态变化时切换最大化/还原按钮的可见性"""
        # 如果是窗口状态变化事件
        if event.type() == QEvent.WindowStateChange:
            # 检查是否最大化
            maximized = self.isMaximized()
            # 如果有最大化按钮，设置其可见性（最大化时隐藏）
            if hasattr(self, '_max_btn'):
                self._max_btn.setVisible(not maximized)
            # 如果有还原按钮，设置其可见性（最大化时显示）
            if hasattr(self, '_restore_btn'):
                self._restore_btn.setVisible(maximized)
        # 调用父类的changeEvent
        super().changeEvent(event)

    def _setup_caption_bar(self):
        """
        外部停靠面板（数据上下文=项目）：
        分隔符（高度=20，右侧）| 操作停靠面板（右侧）| 统一网格（行数=2）
        第0行：停靠面板：菜单（左侧）|“项目名称：XXX”（中心）
        第1行：边框（顶部）| 停靠面板（最后子元素填充=False）：4个按钮组
        """
        # 创建标题栏控件
        bar = QWidget()
        # 设置固定高度（从布局度量获取）
        bar.setFixedHeight(self._ui_layout_metrics["caption_height"])
        # 设置背景颜色
        bar.setStyleSheet("background: #1e1e1e;")
        # 保存标题栏引用
        self._caption_bar = bar

        # ── 外层停靠面板 ──
        # 创建水平布局
        outer = QHBoxLayout(bar)
        # 设置布局边距为0
        outer.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        outer.setSpacing(0)

        # ══════════ 第0列：图标 + 标题 ══════════
        # 创建第0列容器
        col0 = QWidget()
        # 创建水平布局
        col0_layout = QHBoxLayout(col0)
        # 设置布局边距（左=10，上=20，右=0，下=20）
        col0_layout.setContentsMargins(10, 20, 0, 20)
        # 设置布局间距为0
        col0_layout.setSpacing(0)
        # 获取Logo图片路径
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "logo.png")
        # 如果Logo文件存在
        if os.path.exists(logo_path):
            # 创建Logo标签
            logo = QLabel()
            # 加载并缩放Logo图片（32x32）
            logo.setPixmap(QPixmap(logo_path).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            # 设置右边距5px
            logo.setStyleSheet("padding: 0 5px 0 0;")
            # 添加到布局
            col0_layout.addWidget(logo)

        # 创建标题标签
        title_lbl = QLabel("VisionFlow")
        # 设置标题样式
        title_lbl.setStyleSheet("color: #dcdcdc; font-size: 30px; font-weight: bold; padding: 0 0 0 5px;")
        # 添加到布局
        col0_layout.addWidget(title_lbl)

        # 添加第0列到外层布局
        outer.addWidget(col0)

        # ══════════ 统一网格（行数=2）—— 填满剩余空间 ══════════
        # 创建网格容器
        grid = QWidget()
        # 创建垂直布局
        grid_layout = QVBoxLayout(grid)
        # 设置布局边距（上=2，下=2）
        grid_layout.setContentsMargins(0, 2, 0, 2)
        # 设置布局间距为0
        grid_layout.setSpacing(0)

        # ---- 第0行：包含菜单和项目名称 ----
        # 创建第0行容器
        row0 = QWidget()
        # 创建水平布局
        r0 = QHBoxLayout(row0)
        # 设置布局边距（左=8）
        r0.setContentsMargins(8, 0, 0, 0)
        # 设置布局间距为0
        r0.setSpacing(0)

        # 菜单栏
        menu_bar = QMenuBar()
        # 设置菜单栏样式
        menu_bar.setStyleSheet(
            "QMenuBar { background: transparent; color: #dcdcdc; padding: 0; margin: 1px 0; }"
            "QMenuBar::item { padding: 6px 12px; background: transparent; }"
            "QMenuBar::item:selected { background: #3e3e42; }"
            "QMenu { background: #2d2d30; color: #dcdcdc; border: 1px solid #505050; }"
            "QMenu::item { padding: 6px 30px 6px 16px; }"
            "QMenu::item:selected { background: #0078d4; }"
            "QMenu::separator { height: 1px; background: #505050; margin: 4px 10px; }"
        )
        # 构建菜单项
        self._build_menus(menu_bar)
        # 添加到布局
        r0.addWidget(menu_bar)

        # 添加弹性空间
        r0.addStretch(1)
        # 添加"项目名称："标签
        r0.addWidget(self._lbl("项目名称：", "#c8c8c8", 12, pad="0 4px"))
        # 创建项目名称标签
        self._cap_proj_lbl = self._lbl("无项目", "#0078d4", 12, bold=True, pad="0 12px")
        # 添加到布局
        r0.addWidget(self._cap_proj_lbl)
        # 添加弹性空间
        r0.addStretch(1)

        # 将第0行添加到网格布局
        grid_layout.addWidget(row0)

        # ---- 第1行：顶部边框 + 工具栏 ----
        # 创建第1行容器
        row1 = QWidget()
        # 设置样式：背景色，顶部边框
        row1.setStyleSheet("background:#2d2d30; border-top:1px solid #3f3f46;")
        # 创建水平布局
        r1 = QHBoxLayout(row1)
        # 设置布局边距（上=1）
        r1.setContentsMargins(0, 1, 0, 0)
        # 设置布局间距为0
        r1.setSpacing(0)

        # 内部停靠面板（LastChildFill="False" → 4个按钮组）
        toolbar = QWidget()
        # 创建水平布局
        tb = QHBoxLayout(toolbar)
        # 设置布局边距
        tb.setContentsMargins(6, 3, 6, 3)
        # 设置布局间距为2
        tb.setSpacing(2)

        # 按钮组1 — 新建 | 打开 | 编辑 | 保存
        # 遍历按钮配置
        for icon, tip, slot in [
            (FontIcons.Page,                "新建项目", self._on_new_project),          # 新建项目按钮
            (FontIcons.OpenFolderHorizontal, "打开项目", self._on_open_project),        # 打开项目按钮
            (FontIcons.Edit,                 "编辑项目", self._on_edit_project),        # 编辑项目按钮
            (FontIcons.Save,                 "保存项目", self._on_save_project),        # 保存项目按钮
        ]:
            # 创建字体图标按钮
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            # 设置样式
            btn.setStyleSheet(_CMD_BTN)
            # 连接点击信号
            btn.clicked.connect(slot)
            # 添加到布局
            tb.addWidget(btn)
        # 添加分隔线
        tb.addWidget(_hsep())

        # 按钮组2 — 项目级命令
        # 创建项目命令工具栏容器
        self._tool_project_cmds = QWidget()
        # 设置水平布局
        self._tool_project_cmds.setLayout(QHBoxLayout())
        # 设置布局边距为0
        self._tool_project_cmds.layout().setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为2
        self._tool_project_cmds.layout().setSpacing(2)
        # 遍历按钮配置
        for icon, tip, slot in [
            (FontIcons.Add,           "新建流程图",           self._on_add_diagram),        # 新建流程图按钮
            (FontIcons.Ethernet,      "运行模式",             self._on_cycle_run_mode),     # 运行模式按钮
            (FontIcons.Copy,          "重复流程图",           self._on_duplicate_diagram),  # 重复流程图按钮
            (FontIcons.DictionaryAdd, "从模板添加流程图",     self._on_add_from_template),  # 从模板添加流程图按钮
            (FontIcons.Manage,        "模板管理",             self._on_manage_templates),   # 模板管理按钮
            (FontIcons.SaveAs,        "流程图另存为模板",     self._on_save_as_template),   # 流程图另存为模板按钮
            (FontIcons.Cancel,        "删除流程图",           self._on_delete_diagram),     # 删除流程图按钮
        ]:
            # 创建字体图标按钮
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            # 设置样式
            btn.setStyleSheet(_CMD_BTN)
            # 如果有槽函数，连接点击信号
            if slot:
                btn.clicked.connect(slot)
            # 保存删除流程图按钮的引用（用于状态管理）
            if tip == "删除流程图":
                self._delete_diagram_btn = btn
            # 添加到布局
            self._tool_project_cmds.layout().addWidget(btn)
        # 添加到工具栏
        tb.addWidget(self._tool_project_cmds)
        # 添加分隔线
        tb.addWidget(_hsep())

        # 按钮组3 — 图表命令
        # 创建图表命令工具栏容器
        self._tool_diagram_cmds = QWidget()
        # 设置水平布局
        self._tool_diagram_cmds.setLayout(QHBoxLayout())
        # 设置布局边距为0
        self._tool_diagram_cmds.layout().setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为2
        self._tool_diagram_cmds.layout().setSpacing(2)

        # 遍历按钮配置
        for icon, tip, slot in [
            (FontIcons.Replay,         "单次执行",         self._on_run_workflow),       # 单次执行按钮
            (FontIcons.Sync,           "连续执行",     self._on_continuous_run),        # 连续执行按钮
            (FontIcons.Location,       "停止",         self._on_stop_workflow),         # 停止按钮
            (FontIcons.Refresh,        "重置",         self._on_reset_workflow_view),   # 重置按钮
            # (FontIcons.EditMirrored,   "编辑面板",     None),                            # 编辑面板按钮
            # (FontIcons.View,           "查看面板",     None),                            # 查看面板按钮
            # (FontIcons.DisconnectDrive,"删除选中节点", None),                            # 删除选中节点按钮
            # (FontIcons.Delete,         "清空节点",     None),                            # 清空节点按钮
            # (FontIcons.Zoom,           "缩放定位",     None),                            # 缩放定位按钮
            # (FontIcons.AlignCenter,    "对齐节点",     None),                            # 对齐节点按钮
        ]:
            # 创建字体图标按钮
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            # 设置样式
            btn.setStyleSheet(_CMD_BTN)
            # 如果有槽函数，连接点击信号
            if slot:
                btn.clicked.connect(slot)
            # 添加到布局
            self._tool_diagram_cmds.layout().addWidget(btn)
        # 保存按钮引用（用于状态管理）
        self._run_btn = self._tool_diagram_cmds.layout().itemAt(0).widget()   # 单次执行按钮
        self._continuous_btn = self._tool_diagram_cmds.layout().itemAt(1).widget()  # 连续执行按钮
        self._stop_btn = self._tool_diagram_cmds.layout().itemAt(2).widget()  # 停止按钮
        self._reset_btn = self._tool_diagram_cmds.layout().itemAt(3).widget()  # 重置按钮
        # 初始状态下停止按钮和重置按钮不可用（没有正在运行的工作流）
        self._stop_btn.setEnabled(False)
        self._reset_btn.setEnabled(False)

        # 添加到工具栏
        tb.addWidget(self._tool_diagram_cmds)
        # 添加分隔线
        tb.addWidget(_hsep())

        # 按钮组4 — 查看 | 标签页编辑
        # 创建查看按钮
        # self._tool_view_btn = FontIconButton(FontIcons.View, tooltip="查看", font_size=16)
        # 设置样式
        # self._tool_view_btn.setStyleSheet(_CMD_BTN)
        # 添加到布局
        # tb.addWidget(self._tool_view_btn)

        # 添加弹性空间（将后续按钮推到右侧）
        tb.addStretch(1)
        # 将工具栏添加到第1行布局
        r1.addWidget(toolbar)
        # 将第1行添加到网格布局
        grid_layout.addWidget(row1)

        # 将网格容器添加到外层布局，拉伸因子为1
        outer.addWidget(grid, 1)

        # ══════════ 右侧停靠的动作按钮 ══════════
        # 样式与第1行工具栏相同
        # 遍历按钮配置：颜色主题、设置
        for icon, tip, slot in [
            (FontIcons.Color,   "颜色主题", self._on_show_theme_dialog),   # 颜色主题按钮
            (FontIcons.Setting, "设置",     self._on_open_settings),       # 设置按钮
        ]:
            # 创建字体图标按钮
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            # 设置样式
            btn.setStyleSheet(_CMD_BTN)
            # 如果有槽函数，连接点击信号
            if slot:
                btn.clicked.connect(slot)
            # 添加到外层布局
            outer.addWidget(btn)

        # 创建主题切换按钮（亮色/暗色）
        self._theme_toggle = FontIconToggleButton(FontIcons.Brightness, FontIcons.QuietHours, font_size=16)
        # 设置工具提示
        self._theme_toggle.setToolTip("切换明/暗主题")
        # 设置样式
        self._theme_toggle.setStyleSheet(_CMD_BTN + """
            FontIconToggleButton:checked { color: #dcdcdc; }
            FontIconToggleButton:checked:hover { background: #3e3e42; }
        """)
        # 根据当前主题设置初始状态
        self._theme_toggle.setChecked(theme_manager.is_dark)
        # 连接切换信号
        self._theme_toggle.toggled.connect(lambda _: self._on_toggle_theme())
        # 添加到外层布局
        outer.addWidget(self._theme_toggle)

        # 遍历按钮配置：关于、新手向导
        for icon, tip, slot in [
            (FontIcons.Info,  "关于",     self._on_about),           # 关于按钮
            (FontIcons.Smartcard, "新手向导", self._on_open_guide),  # 新手向导按钮
        ]:
            # 创建字体图标按钮
            btn = FontIconButton(icon, tooltip=tip, font_size=16)
            # 设置样式
            btn.setStyleSheet(_CMD_BTN)
            # 如果有槽函数，连接点击信号
            if slot:
                btn.clicked.connect(slot)
            # 添加到外层布局
            outer.addWidget(btn)

        # ══════════ 最右侧20px分隔线 ══════════
        # 创建分隔符控件
        sep20 = QFrame()
        # 设置为垂直线
        sep20.setFrameShape(QFrame.VLine)
        # 设置颜色
        sep20.setStyleSheet("color: #505050;")
        # 设置固定大小（宽1px，高20px）
        sep20.setFixedSize(1, 20)
        # 添加到外层布局
        outer.addWidget(sep20)

        # ══════════ 窗口标题栏按钮 ══════════
        # 定义窗口按钮样式表
        _WIN = (
            "QPushButton { background:transparent; border:none; color:#999;"
            " font-family:'Segoe Fluent Icons','Segoe MDL2 Assets','Segoe UI Symbol';"
            " font-size:14px; min-width:46px; min-height:32px; }"
            "QPushButton:hover { background:#3e3e42; color:#dcdcdc; }"
            "QPushButton#close_btn:hover { background:#e81123; color:white; }"
        )
        # 遍历窗口按钮配置
        for icon, tip, slot, btn_attr in [
            (FontIcons.ChromeMinimize, "最小化", self.showMinimized, None),         # 最小化按钮
            (FontIcons.ChromeMaximize, "最大化", self._toggle_max, "_max_btn"),    # 最大化按钮
            (FontIcons.ChromeRestore,  "还原",   self._toggle_max, "_restore_btn"), # 还原按钮
            (FontIcons.ChromeClose,    "关闭",   self._on_close_window, None),      # 关闭按钮
        ]:
            # 创建按钮
            btn = QPushButton(icon)
            # 设置工具提示
            btn.setToolTip(tip)
            # 设置样式
            btn.setStyleSheet(_WIN)
            # 如果是关闭按钮，设置对象名以应用特定样式
            if icon == FontIcons.ChromeClose:
                btn.setObjectName("close_btn")
            # 连接点击信号
            btn.clicked.connect(slot)
            # 如果需要保存按钮引用（最大化/还原按钮）
            if btn_attr:
                setattr(self, btn_attr, btn)
            # 添加到外层布局
            outer.addWidget(btn)
        # 初始状态下隐藏还原按钮（窗口未最大化）
        self._restore_btn.hide()

        # ── 拖动支持 ──
        # 保存标题栏引用
        self._caption_bar = bar
        # 为标题栏安装事件过滤器以捕获鼠标事件实现窗口拖动
        bar.installEventFilter(self)
        # 为标题栏的所有子组件也安装事件过滤器
        for child in bar.findChildren(QWidget):
            child.installEventFilter(self)

        # 标题栏将在 _setup_main_surface() 中作为普通 widget 添加到主布局
        # 不使用 setMenuWidget()，以避免 QMenu 在 frameless 窗口下无法接收鼠标事件的问题

    def eventFilter(self, obj, event):
        """拦截标题栏控件上的鼠标事件，用于窗口拖动和双击"""
        # 获取事件类型
        etype = event.type()
        # 如果是鼠标按下事件且按下的是左键
        if etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            # 如果点击的是交互控件（按钮、菜单项、输入框等），不处理拖动
            if self._is_interactive_widget(obj):
                return False
            # 如果有活跃的弹出窗口（QMenu等），不吞事件，让其模态循环处理外部点击关闭
            if QApplication.activePopupWidget() is not None:
                return False
            # 记录拖拽起始全局坐标
            self._drag_pos = event.globalPos()
            # 标题栏捕获鼠标
            self._caption_bar.grabMouse()
            return True

        # 如果是鼠标移动事件且有拖拽起始坐标记录
        if etype == QEvent.MouseMove and hasattr(self, '_drag_pos'):
            # 计算鼠标移动偏移量
            delta = event.globalPos() - self._drag_pos
            # 移动窗口
            self.move(self.x() + delta.x(), self.y() + delta.y())
            # 更新拖拽起始坐标
            self._drag_pos = event.globalPos()
            return True

        # 如果是鼠标释放事件且有拖拽起始坐标记录
        if etype == QEvent.MouseButtonRelease and hasattr(self, '_drag_pos'):
            # 删除拖拽起始坐标记录
            del self._drag_pos
            # 释放鼠标捕获
            self._caption_bar.releaseMouse()
            return True

        # 如果是鼠标双击事件且双击的是左键
        if etype == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
            # 如果双击的不是交互控件
            if not self._is_interactive_widget(obj):
                # 切换最大化/还原状态
                self._toggle_max()
                return True

        return False

    def _is_caption_descendant(self, widget) -> bool:
        """判断控件是否是标题栏或其子控件

        参数：
            widget: 要检查的控件

        返回：
            如果是标题栏或其子控件返回True，否则返回False
        """
        # 向上遍历父控件链
        while widget is not None:
            # 如果找到了标题栏
            if widget is self._caption_bar:
                return True
            # 获取父控件
            widget = widget.parentWidget()
        return False

    def _is_interactive_widget(self, widget) -> bool:
        """判断控件是否是按钮/菜单项等需要鼠标事件的交互控件

        参数：
            widget: 要检查的控件

        返回：
            如果是交互控件返回True，否则返回False
        """
        # 从当前控件向上遍历
        w = widget
        while w is not None and w is not self._caption_bar:
            # 如果是弹出菜单，检查点击位置是否在有效的菜单项上
            if isinstance(w, QMenu):
                cp = w.mapFromGlobal(QCursor.pos())
                return w.actionAt(cp) is not None
            # 如果是按钮类型
            if isinstance(w, QPushButton):
                return True
            # 如果是菜单栏，检查点击位置是否在有效的菜单项上
            if isinstance(w, QMenuBar):
                cp = w.mapFromGlobal(QCursor.pos())
                return w.actionAt(cp) is not None
            # 如果是输入框
            if isinstance(w, QLineEdit):
                return True
            # 获取父控件
            w = w.parentWidget()
        return False

    def nativeEvent(self, eventType, message):
        """处理 WM_NCHITTEST（调整大小手柄）+ WM_NCCALCSIZE（移除白边）"""
        # 如果不是 Windows 消息，返回 False
        if eventType != b"windows_generic_MSG":
            return False, 0

        # 将消息指针转换为 _MSG 结构体
        msg_ptr = ctypes.cast(int(message), ctypes.POINTER(_MSG))
        msg = msg_ptr.contents

        # 移除非客户区以消除无边框窗口的白边
        if msg.message == WM_NCCALCSIZE:
            return True, 0

        # 如果不是命中测试消息，返回 False
        if msg.message != WM_NCHITTEST:
            return False, 0

        # 从 lParam 解析屏幕坐标（处理多显示器时的符号扩展）
        x_raw = msg.lParam & 0xFFFF
        y_raw = (msg.lParam >> 16) & 0xFFFF
        x = x_raw - 65536 if x_raw > 32767 else x_raw
        y = y_raw - 65536 if y_raw > 32767 else y_raw

        # 获取窗口几何信息
        g = self.geometry()
        # 判断鼠标位置是否在边框区域内
        on_left = x < g.x() + _BORDER          # 左侧边框
        on_right = x > g.x() + g.width() - _BORDER  # 右侧边框
        on_top = y < g.y() + _BORDER           # 顶部边框
        on_bottom = y > g.y() + g.height() - _BORDER  # 底部边框

        # 根据鼠标位置返回对应的命中测试结果
        if on_top and on_left:
            return True, HTTOPLEFT          # 左上角
        if on_top and on_right:
            return True, HTTOPRIGHT         # 右上角
        if on_bottom and on_left:
            return True, HTBOTTOMLEFT       # 左下角
        if on_bottom and on_right:
            return True, HTBOTTOMRIGHT      # 右下角
        if on_left:
            return True, HTLEFT              # 左侧边框
        if on_right:
            return True, HTRIGHT             # 右侧边框
        if on_top:
            return True, HTTOP               # 顶部边框
        if on_bottom:
            return True, HTBOTTOM            # 底部边框

        return False, 0

    def _setup_main_surface(self):
        """设置主界面"""
        # 创建根页面
        root = QWidget()
        # 创建垂直布局
        root_layout = QVBoxLayout(root)
        # 设置根页面的内容边距为0
        root_layout.setContentsMargins(0, 0, 0, 0)
        # 设置根页面的间距为0
        root_layout.setSpacing(0)

        # 将标题栏添加到根布局顶部（替代 setMenuWidget，避免 QMenu 点击失效）
        root_layout.addWidget(self._caption_bar)

        # 创建页面堆叠组件，用于切换不同的页面
        self._root_stack = QStackedWidget()
        # 创建开始页面
        self._start_page = StartPage()
        # 连接新项目信号
        self._start_page.new_project_requested.connect(self._on_new_project)
        # 连接打开项目信号
        self._start_page.open_project_requested.connect(self._on_open_project)
        # 连接打开指定项目信号
        self._start_page.project_open_requested.connect(self._open_project)
        # 将开始页面添加到页面堆叠组件
        self._root_stack.addWidget(self._start_page)

        # 创建编辑器页面
        self._editor_surface = QWidget()
        # 创建垂直布局
        editor_layout = QVBoxLayout(self._editor_surface)
        # 设置编辑器页面的内容边距为0
        editor_layout.setContentsMargins(0, 0, 0, 0)
        # 设置编辑器页面的间距为0
        editor_layout.setSpacing(0)

        # 构建左侧面板
        self._left_box = self._build_left_panel()

        # 创建中央和右侧的水平分割器
        self._center_right_splitter = QSplitter(Qt.Horizontal)
        # 设置手柄宽度为2像素
        self._center_right_splitter.setHandleWidth(2)
        # 设置手柄样式
        self._center_right_splitter.setStyleSheet("QSplitter::handle { background: #505050; }")

        # 构建图表面板
        self._diagram_panel = self._build_diagram_panel()
        # 添加到分割器
        self._center_right_splitter.addWidget(self._diagram_panel)

        # 构建右侧面板
        self._right_panel = self._build_side_panel()
        # 设置右侧面板固定宽度（从布局度量获取）
        self._right_panel.setFixedWidth(self._ui_layout_metrics["right_width"])
        # 添加到分割器
        self._center_right_splitter.addWidget(self._right_panel)

        # 工作区布局：左侧面板 | 中央+右侧分割器
        workspace = QWidget()
        # 创建水平布局
        ws_layout = QHBoxLayout(workspace)
        # 设置布局边距为0
        ws_layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        ws_layout.setSpacing(0)
        # 添加左侧面板
        ws_layout.addWidget(self._left_box)
        # 添加中央+右侧分割器，拉伸因子为1
        ws_layout.addWidget(self._center_right_splitter, 1)
        # 将工作区添加到编辑器布局，拉伸因子为1
        editor_layout.addWidget(workspace, 1)

        # 将编辑器页面添加到页面堆叠组件
        self._root_stack.addWidget(self._editor_surface)
        # 将页面堆叠组件添加到根布局，拉伸因子为1
        root_layout.addWidget(self._root_stack, 1)
        # 设置根页面为中央控件
        self.setCentralWidget(root)

        # 应用分割器状态
        self._apply_splitter_state()

    def _build_side_panel(self):
        """构建右侧面板"""
        # 创建垂直分割器
        self._center_splitter = QSplitter(Qt.Vertical)
        # 设置手柄宽度为2像素
        self._center_splitter.setHandleWidth(2)
        # 设置手柄样式
        self._center_splitter.setStyleSheet("QSplitter::handle { background: #505050; }")
        # 构建中央面板
        center_panel = self._build_center_panel()
        # 设置中央面板固定高度（从布局度量获取）
        center_panel.setFixedHeight(self._ui_layout_metrics["center_height"])
        # 添加到分割器
        self._center_splitter.addWidget(center_panel)
        # 添加底部面板
        self._center_splitter.addWidget(self._build_bottom_panel())

        # 创建容器面板
        panel = QWidget()
        # 创建垂直布局
        layout = QVBoxLayout(panel)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)
        # 添加分割器，拉伸因子为1
        layout.addWidget(self._center_splitter, 1)
        return panel

    def _build_left_panel(self):
        """构建左侧面板"""
        # 创建工具箱面板
        self._toolbox = ToolboxPanel()
        # 创建日志面板（为 API 兼容性而保留）
        self._log_panel = LogPanel()

        # 创建网格分割框，用于左侧面板的布局
        box = GridSplitterBox()
        # 将工具箱面板设置为网格分割框的内容
        box.set_content(self._toolbox)
        return box

    def _build_center_panel(self):
        """构建中央面板"""
        # 创建面板容器
        panel = QWidget()
        # 创建垂直布局
        layout = QVBoxLayout(panel)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

        # 创建中央标签页控件
        self._center_tabs = QTabWidget()
        # 设置标签页样式
        self._center_tabs.setStyleSheet(_TAB_STYLE)

        # 创建图像查看器面板
        self._img_panel = ImageViewerPanel()
        # 添加图像标签页
        self._center_tabs.addTab(self._img_panel, "图像")

        # 创建模块结果页面
        module_page = QWidget()
        # 创建垂直布局
        module_layout = QVBoxLayout(module_page)
        # 设置布局边距为0
        module_layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        module_layout.setSpacing(0)

        # 创建模块结果标题
        self._module_result_title = QLabel("模块名称 <未选择>")
        # 设置标题样式
        self._module_result_title.setStyleSheet(
            "background: #2d2d30; color: #dcdcdc; padding: 8px 10px;"
            "font-size: 12px; font-weight: bold; border-bottom: 1px solid #3f3f46;"
        )
        # 添加到布局
        module_layout.addWidget(self._module_result_title)

        # 创建属性面板
        self._property_panel = PropertyPanel()
        # 添加到布局，拉伸因子为1
        module_layout.addWidget(self._property_panel, 1)
        # 添加模块结果标签页
        self._center_tabs.addTab(module_page, "模块结果")

        # 添加到布局，拉伸因子为1
        layout.addWidget(self._center_tabs, 1)

        # 创建资源面板
        self._resource_panel = FlowResourcePanel()
        # 设置固定高度（从布局度量获取）
        self._resource_panel.setFixedHeight(self._ui_layout_metrics["resource_height"])
        # 初始隐藏
        self._resource_panel.setVisible(False)
        # 添加到布局
        layout.addWidget(self._resource_panel)

        # 创建侧边状态栏
        self._side_status_strip = _InlineStatusStrip("#4caf50")
        # 设置初始状态文本
        self._side_status_strip.set_status("等待选择节点")
        # 添加到布局
        layout.addWidget(self._side_status_strip)
        return panel

    def _build_bottom_panel(self):
        """构建底部面板"""
        # 创建结果面板
        self._result_panel = ResultPanel()
        # 设置图像查看器
        self._result_panel.set_image_viewer(self._img_panel.viewer)
        # 连接节点跳转请求信号
        self._result_panel.node_jump_requested.connect(self._jump_to_node)
        # 连接图像更新请求信号
        self._result_panel.image_update_requested.connect(self._on_result_image_update)
        # 包装在容器中，以便切换/角按钮正常工作
        self._bottom_tabs = self._result_panel._tabs
        # 设置标签页样式
        self._bottom_tabs.setStyleSheet(_TAB_STYLE)
        # 设置最小高度为120像素
        self._bottom_tabs.setMinimumHeight(120)

        # 创建帮助面板（保持向后兼容）
        self._help_panel = HelpPanel()

        # 底部面板可见性标志
        self._bottom_visible = True
        # 创建底部切换按钮
        self._bottom_toggle = QPushButton("▼")
        # 设置固定大小24x18
        self._bottom_toggle.setFixedSize(24, 18)
        # 设置按钮样式
        self._bottom_toggle.setStyleSheet(
            "QPushButton { background: #2d2d30; border: 1px solid #3f3f46; color: #999; font-size: 9px; }"
            "QPushButton:hover { color: #dcdcdc; }"
        )
        # 连接点击信号
        self._bottom_toggle.clicked.connect(self._toggle_bottom)
        # 将切换按钮设置为标签页的角控件（左上角）
        self._bottom_tabs.setCornerWidget(self._bottom_toggle, Qt.TopLeftCorner)
        return self._bottom_tabs

    def _build_diagram_panel(self):
        """构建图表面板"""
        # 创建面板容器
        panel = QWidget()
        # 创建垂直布局
        layout = QVBoxLayout(panel)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

        # 创建图表标签页控件
        self._diagram_tab_widget = QTabWidget()
        # 设置标签页样式
        self._diagram_tab_widget.setStyleSheet(_TAB_STYLE)
        # 设置标签页不可关闭
        self._diagram_tab_widget.setTabsClosable(False)
        # 连接标签页关闭请求信号
        self._diagram_tab_widget.tabCloseRequested.connect(self._on_close_diagram_tab)
        # 连接当前标签页变化信号
        self._diagram_tab_widget.currentChanged.connect(self._on_diagram_tab_changed)
        # 设置文档模式
        self._diagram_tab_widget.setDocumentMode(True)
        # 添加到布局，拉伸因子为1
        layout.addWidget(self._diagram_tab_widget, 1)

        # 创建图表状态栏
        self._diagram_status_strip = _InlineStatusStrip("#4caf50")
        # 设置初始状态文本
        self._diagram_status_strip.set_status("流程图就绪")
        # 添加到布局
        layout.addWidget(self._diagram_status_strip)
        return panel

    def _setup_status_bar(self):
        """设置状态栏"""
        # 获取状态栏
        status = self.statusBar()
        # 禁用大小调整手柄
        status.setSizeGripEnabled(False)

        # 创建状态标签
        self._state_lbl = QLabel(f"{FontIcons.Completed} 空闲")
        # 设置样式
        self._state_lbl.setStyleSheet("color: #4caf50; font-weight: bold; background: transparent;")
        # 添加到状态栏
        status.addWidget(self._state_lbl)
        # 添加分隔线
        status.addWidget(_hsep())

        # 创建消息标签
        self._msg_lbl = QLabel("就绪")
        # 添加到状态栏，拉伸因子为1
        status.addWidget(self._msg_lbl, 1)
        # 添加分隔线
        status.addWidget(_hsep())

        # 创建节点计数标签
        self._node_cnt_lbl = QLabel("节点: 0")
        # 添加到永久控件（右侧）
        status.addPermanentWidget(self._node_cnt_lbl)
        # 创建时间标签
        self._time_lbl = QLabel("")
        # 添加到永久控件（右侧）
        status.addPermanentWidget(self._time_lbl)

        # 跟随主题强调色
        self._refresh_status_bar_qss()
        # 连接主题变化信号
        connect_theme(lambda: self._refresh_status_bar_qss())

    def _refresh_status_bar_qss(self):
        """更新状态栏样式以匹配当前主题"""
        # 获取主题管理器
        tm = theme_manager
        # 获取各种颜色
        bg = tm.color("bg_surface_raised").name()  # 背景色
        text = tm.color("text_primary").name()      # 文本色
        border = tm.color("border").name()          # 边框色
        # 设置状态栏样式
        self.statusBar().setStyleSheet(
            f"QStatusBar {{ background: {bg}; color: {text}; border-top: 1px solid {border};"
            f" padding: 2px 8px; font-size: 11px; outline: 0; }}"
            f"QStatusBar::item {{ border: none; }}"
        )

    def _wire_signals(self):
        """连接各种信号"""
        # 工具箱节点类型选择信号
        self._toolbox.node_type_selected.connect(self._on_node_type_selected)
        # 属性面板属性变化信号
        self._property_panel.property_changed.connect(self._on_property_changed)
        # 设置属性面板的图像查看器
        self._property_panel.set_image_viewer(self._img_panel.viewer)
        # 资源面板文件选择信号
        self._resource_panel.file_selected.connect(self._on_resource_file_selected)
        # 资源面板文件双击信号
        self._resource_panel.file_double_clicked.connect(self._on_resource_file_double_clicked)

    def _connect_events(self):
        """连接事件系统"""
        # 订阅节点选中事件
        event_system.subscribe(EventType.NODE_SELECTED, self._on_ev_node_sel)
        # 订阅图表变更事件
        event_system.subscribe(EventType.DIAGRAM_CHANGED, self._on_ev_diag_chg)
        # 订阅工作流启动事件
        event_system.subscribe(EventType.WORKFLOW_STARTED, self._on_wf_start)
        # 订阅工作流完成事件
        event_system.subscribe(EventType.WORKFLOW_COMPLETED, self._on_wf_done)
        # 订阅工作流错误事件
        event_system.subscribe(EventType.WORKFLOW_ERROR, self._on_wf_err)
        # 订阅工作流停止事件
        event_system.subscribe(EventType.WORKFLOW_STOPPED, self._on_wf_stopped)
        # 订阅项目加载事件
        event_system.subscribe(EventType.PROJECT_LOADED, self._on_proj_load)
        # 订阅项目保存事件
        event_system.subscribe(EventType.PROJECT_SAVED, self._on_proj_save)
        # 文件迭代事件（"运行全部" / "显示全部"）
        event_system.subscribe(EventType.FILE_ITERATION_NEXT, self._on_file_iteration_next)
        event_system.subscribe(EventType.FILE_ITERATION_COMPLETED, self._on_file_iteration_completed)

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 同步工作流到项目
        self._sync_workflow_to_project()
        # 保存窗口宽度到QSettings
        _ps.set_i("window_width", self.width())
        # 保存窗口高度到QSettings
        _ps.set_i("window_height", self.height())
        # 如果有左侧面板
        if hasattr(self, "_left_box"):
            # 保存左侧面板宽度
            _ps.set_i("left_width", self._left_box.menu_width())
            # 获取中央+右侧分割器的大小
            inner_sizes = self._center_right_splitter.sizes()
            # 如果有右侧面板且可见，保存右侧面板宽度
            if len(inner_sizes) >= 2 and self._right_panel_visible:
                _ps.set_i("right_width", inner_sizes[1])
            # 获取中央分割器的大小
            center_sizes = self._center_splitter.sizes()
            if len(center_sizes) >= 2:
                # 保存底部面板高度
                _ps.set_i("bottom_height", center_sizes[1])
        # 保存左侧面板可见性
        _ps.set_b("left_visible", self._left_panel_visible)
        # 保存右侧面板可见性
        _ps.set_b("right_visible", self._right_panel_visible)
        # 停止时钟定时器
        self._clock.stop()
        # 调用父类的closeEvent
        super().closeEvent(event)

    def _apply_splitter_state(self):
        """应用分割器状态"""
        # 获取左侧面板宽度
        if self._ui_layout_profile:
            left_width = self._ui_layout_metrics["left_width"]
        else:
            left_width = _ps.get_i("left_width", 280)
        # 获取右侧面板宽度
        if self._ui_layout_profile:
            right_width = self._ui_layout_metrics["right_width"]
        else:
            right_width = _ps.get_i("right_width", 420)
        # 获取底部面板高度
        if self._ui_layout_profile:
            bottom_height = self._ui_layout_metrics["bottom_height"]
        else:
            bottom_height = _ps.get_i("bottom_height", 180)

        # 设置左侧面板宽度
        self._left_box.set_menu_width(left_width)
        # 设置中央+右侧分割器大小
        self._center_right_splitter.setSizes([max(640, self.width() - left_width - right_width), right_width])
        # 设置中央分割器大小
        self._center_splitter.setSizes([max(380, self.height() - bottom_height - 140), bottom_height])

        # 获取左侧面板可见性
        self._left_panel_visible = _ps.get_b("left_visible", True)
        # 获取右侧面板可见性
        self._right_panel_visible = _ps.get_b("right_visible", True)
        # 如果左侧面板不可见
        if not self._left_panel_visible:
            # 切换左侧面板
            self.toggle_left_panel()
        # 如果右侧面板不可见
        if not self._right_panel_visible:
            # 切换右侧面板
            self.toggle_right_panel()

    def _lbl(self, text, color, size, bold=False, pad=""):
        """创建标签控件"""
        # 创建标签
        label = QLabel(text)
        # 设置样式表
        label.setStyleSheet(
            f"color: {color}; font-size: {size}px; {'font-weight: bold;' if bold else ''} padding: {pad};"
        )
        return label

    def _toggle_max(self):
        """切换最大化/还原"""
        # 如果当前是最大化，则还原；否则最大化
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def _build_menus(self, menu_bar: QMenuBar):
        """构建菜单栏"""
        # ── 文件菜单 ──
        file_menu = menu_bar.addMenu("文件(&F)")
        file_menu.addAction("新建项目(&N)", self._on_new_project, "Ctrl+N")
        file_menu.addAction("打开项目(&O)...", self._on_open_project, "Ctrl+O")
        file_menu.addAction("保存项目(&S)", self._on_save_project, "Ctrl+S")
        file_menu.addAction("另存为(&A)...", self._on_save_as_project, "Ctrl+Shift+S")
        file_menu.addSeparator()
        # 最近项目子菜单
        self._recent_menu = file_menu.addMenu("最近的项目(&R)")
        self._recent_menu.aboutToShow.connect(self._refresh_recent)
        file_menu.addSeparator()
        file_menu.addAction("退出(&X)", self._on_close_window, "Alt+F4")

        # ── 编辑菜单 ──
        edit_menu = menu_bar.addMenu("编辑(&E)")
        edit_menu.addAction("撤销(&U)", self._on_undo_diagram, "Ctrl+Z")
        edit_menu.addAction("重做(&R)", self._on_redo_diagram, "Ctrl+Y")

        # ── 运行菜单 ──
        run_menu = menu_bar.addMenu("运行(&R)")
        run_menu.addAction("运行流程(&F)", self._on_run_workflow, "F5")
        run_menu.addAction("停止(&S)", self._on_stop_workflow, "Shift+F5")

        # ── 系统菜单 ──
        system_menu = menu_bar.addMenu("系统(&S)")
        system_menu.addAction("项目属性...", self._on_edit_project)
        system_menu.addSeparator()
        system_menu.addAction("切换左侧流程资源", self.toggle_left_panel)
        system_menu.addAction("切换右侧图像结果区", self.toggle_right_panel)

        # ── 帮助菜单 ──
        help_menu = menu_bar.addMenu("帮助(&H)")
        help_menu.addAction("使用指南(&G)", self._on_open_guide)
        help_menu.addSeparator()
        help_menu.addAction("关于 VisionFlow(&A)", self._on_about)

    def _refresh_recent(self):
        """刷新最近项目菜单"""
        # 清空最近项目菜单
        self._recent_menu.clear()
        # 清理不存在的最近项目
        project_service.cleanup_recent_projects()
        # 如果没有最近项目
        if not project_service.recent_projects:
            # 创建空动作
            empty_action = QAction("(无最近项目)", self)
            # 禁用动作
            empty_action.setEnabled(False)
            # 添加到菜单
            self._recent_menu.addAction(empty_action)
            return
        # 遍历最近项目路径
        for path in project_service.recent_projects:
            # 创建动作
            action = QAction(os.path.basename(path), self)
            # 设置工具提示为完整路径
            action.setToolTip(path)
            # 连接触发信号
            action.triggered.connect(lambda checked=False, current_path=path: self._open_project(current_path))
            # 添加到菜单
            self._recent_menu.addAction(action)
        # 添加分隔线
        self._recent_menu.addSeparator()
        # 清空最近项目动作
        clear_action = QAction("清空最近项目", self)
        # 连接触发信号
        clear_action.triggered.connect(project_service.clear_recent_projects)
        # 添加到菜单
        self._recent_menu.addAction(clear_action)

    def _wire_diagram_editor(self, editor: DiagramEditorWidget):
        """连接图表编辑器信号"""
        # 连接节点选中信号
        editor.node_selected.connect(self._on_editor_node_selected)
        # 连接节点取消选中信号
        editor.node_deselected.connect(lambda: self._select_node(None))
        # 连接节点双击信号
        editor.node_double_clicked.connect(self._on_editor_node_double_clicked)
        # 连接节点属性请求信号
        editor.node_properties_requested.connect(self._on_editor_node_double_clicked)
        # 连接节点帮助请求信号
        editor.node_help_requested.connect(self._on_editor_node_help_requested)
        # 连接节点执行信号
        editor.node_executed.connect(self._on_node_executed)
        # 连接场景状态消息信号
        editor.scene.status_message.connect(self._on_editor_status)

    def _create_diagram_page(self, diagram: DiagramData) -> QWidget:
        """创建图表页面

        参数：
            diagram: 图表数据

        返回：
            页面控件
        """
        # 创建页面容器
        page = QWidget()
        # 创建垂直布局
        layout = QVBoxLayout(page)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)
        # 创建图表编辑器
        editor = DiagramEditorWidget()
        # 连接编辑器信号
        self._wire_diagram_editor(editor)
        # 如果图表没有工作流
        if diagram.workflow is None:
            # 创建新的工作流
            diagram.workflow = WorkflowEngine(name=diagram.name)
        # 绑定工作流
        editor.bind_workflow(diagram.workflow)
        # 添加到布局，拉伸因子为1
        layout.addWidget(editor, 1)
        # 保存图表ID
        page.diagram_id = diagram.id
        # 保存工作流引用
        page.workflow = diagram.workflow
        # 保存编辑器引用
        page.editor = editor
        return page

    def _show_start_page(self):
        """显示开始页面"""
        # 切换到开始页面
        self._root_stack.setCurrentWidget(self._start_page)
        # 刷新最近项目列表
        self._start_page.refresh_recent(project_service)
        # 项目未加载标志
        self._project_loaded = False
        # 清空工作流引用
        self._workflow = None
        # 清空编辑器引用
        self._diagram_editor = None
        # 取消选中节点
        self._select_node(None)
        # 同步项目标签
        self._sync_proj_labels(None)
        # 设置图表状态栏
        self._diagram_status_strip.set_status("流程图就绪", "#4caf50")
        # 设置侧边状态栏
        self._side_status_strip.set_status("等待选择节点", "#4caf50")

    def _show_editor(self):
        """显示编辑器页面"""
        # 切换到编辑器页面
        self._root_stack.setCurrentWidget(self._editor_surface)
        # 项目已加载标志
        self._project_loaded = True

    def _bind_project_diagram(self, project: ProjectItem):
        """绑定项目图表

        参数：
            project: 项目对象
        """
        # 如果项目没有图表，添加一个默认图表
        if not project.diagrams:
            project.add_diagram(project.name)
        # 始终同步全局模板（在节点发现后加载）
        if project_service._templates:
            project._templates = list(project_service._templates)
        # 刷新图表标签页
        self._refresh_diagram_tabs(project)
        # 显示编辑器页面
        self._show_editor()
        # 同步项目标签
        self._sync_proj_labels(project)
        # 取消选中节点
        self._select_node(None)
        # 延迟刷新：Qt 可能在 _refresh_diagram_tabs 解除信号阻塞后触发 currentChanged(-1)
        # 在事件循环稳定后重新应用正确的状态，以覆盖任何延迟触发的无效索引信号
        QTimer.singleShot(0, lambda: self._refresh_command_states(
            project_service.current_project))

    def _refresh_diagram_tabs(self, project: ProjectItem):
        """刷新图表标签页

        参数：
            project: 项目对象
        """
        # 设置正在重建标签页标志
        self._rebuilding_tabs = True
        # 清空图表页面缓存
        self._diagram_pages.clear()
        # 清空图表头部缓存
        self._diagram_headers.clear()
        # 阻塞标签页控件信号
        self._diagram_tab_widget.blockSignals(True)
        # 清空标签页
        self._diagram_tab_widget.clear()
        # 遍历项目的所有图表
        for diagram in project.diagrams:
            # 创建图表页面
            page = self._create_diagram_page(diagram)
            # 保存到缓存
            self._diagram_pages[diagram.id] = page
            # 添加标签页
            index = self._diagram_tab_widget.addTab(page, "")
            # 安装标签页头部
            self._install_diagram_tab_header(index, diagram)
        # 计算目标索引
        target_index = max(0, min(project.selected_diagram_index, self._diagram_tab_widget.count() - 1))
        # 如果有标签页，设置当前索引
        if self._diagram_tab_widget.count() > 0:
            self._diagram_tab_widget.setCurrentIndex(target_index)
        # 解除信号阻塞
        self._diagram_tab_widget.blockSignals(False)
        # 触发当前标签页变化
        self._on_diagram_tab_changed(target_index)
        # 重置重建标志
        self._rebuilding_tabs = False

    def _install_diagram_tab_header(self, index: int, diagram: DiagramData):
        """安装图表标签页头部控件

        参数：
            index: 标签页索引
            diagram: 图表数据
        """
        # 创建图表标签页头部
        header = _DiagramTabHeader(diagram.name, self._diagram_tab_widget.tabBar())
        # 连接重命名请求信号
        header.rename_requested.connect(lambda text, current=diagram: self._rename_diagram(current, text))
        # 连接运行请求信号
        header.run_requested.connect(lambda current=diagram: self._run_diagram(current.id))
        # 连接停止请求信号
        header.stop_requested.connect(lambda current=diagram: self._stop_diagram(current.id))
        # 连接重置请求信号
        header.reset_requested.connect(lambda current=diagram: self._reset_diagram_view(current.id))
        # 设置标签页工具提示
        self._diagram_tab_widget.setTabToolTip(index, diagram.name)
        # 设置标签页左侧按钮为自定义头部
        self._diagram_tab_widget.tabBar().setTabButton(index, QTabBar.LeftSide, header)

        # 自定义关闭按钮 — 为暗色主题可见性定制样式
        close_btn = QPushButton("×")
        # 设置固定大小18x18
        close_btn.setFixedSize(18, 18)
        # 设置关闭按钮样式
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {theme_manager.color('text_secondary').name()};"
            f" font-size: 14px; padding: 0; }}"
            f"QPushButton:hover {{ background: #c42b1c; color: white; border-radius: 2px; }}"
        )
        # 连接关闭按钮点击信号
        close_btn.clicked.connect(lambda checked, idx=index: self._on_close_diagram_tab(idx))
        # 设置标签页右侧按钮为关闭按钮
        self._diagram_tab_widget.tabBar().setTabButton(index, QTabBar.RightSide, close_btn)

        # 保存头部引用
        self._diagram_headers[diagram.id] = header

    def _rename_diagram(self, diagram: DiagramData, text: str):
        """重命名图表

        参数：
            diagram: 图表数据
            text: 新名称
        """
        # 获取名称（去除首尾空格，如果为空则使用原名称）
        name = (text or "").strip() or diagram.name
        # 更新图表名称
        diagram.name = name
        # 如果工作流存在，更新工作流名称
        if diagram.workflow is not None:
            diagram.workflow.name = name
        # 获取当前项目
        project = project_service.current_project
        # 如果项目存在
        if project is not None:
            # 遍历项目的图表，找到对应的索引
            for index, item in enumerate(project.diagrams):
                if item.id == diagram.id:
                    # 更新标签页工具提示
                    self._diagram_tab_widget.setTabToolTip(index, name)
                    break
        # 获取头部控件
        header = self._diagram_headers.get(diagram.id)
        # 如果头部存在，更新名称
        if header is not None:
            header.set_name(name)
        # 同步项目标签
        self._sync_proj_labels(project_service.current_project)

    def _refresh_diagram_tab_headers(self):
        """刷新图表标签页头部激活状态"""
        # 获取当前图表的ID
        current_id = getattr(self._current_diagram_page(), "diagram_id", None)
        # 遍历所有头部
        for diagram_id, header in self._diagram_headers.items():
            # 设置激活状态（当前图表为激活）
            header.set_active(diagram_id == current_id)

    def _run_diagram(self, diagram_id: str):
        """运行指定图表

        参数：
            diagram_id: 图表ID
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 遍历项目的图表
        for index, diagram in enumerate(project.diagrams):
            if diagram.id == diagram_id:
                # 切换到该图表
                self._diagram_tab_widget.setCurrentIndex(index)
                # 运行工作流
                self._on_run_workflow()
                return

    def _stop_diagram(self, diagram_id: str):
        """停止指定图表

        参数：
            diagram_id: 图表ID
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 遍历项目的图表
        for index, diagram in enumerate(project.diagrams):
            if diagram.id == diagram_id:
                # 切换到该图表
                self._diagram_tab_widget.setCurrentIndex(index)
                # 停止工作流
                self._on_stop_workflow()
                return

    def _reset_diagram_view(self, diagram_id: str):
        """重置指定图表的视图

        参数：
            diagram_id: 图表ID
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 遍历项目的图表
        for index, diagram in enumerate(project.diagrams):
            if diagram.id == diagram_id:
                # 切换到该图表
                self._diagram_tab_widget.setCurrentIndex(index)
                # 重置工作流视图
                self._on_reset_workflow_view()
                return

    def _current_diagram_page(self):
        """获取当前图表页面

        返回：
            当前图表页面控件
        """
        # 获取当前标签页控件
        page = self._diagram_tab_widget.currentWidget()
        return page if page is not None else None

    def _current_diagram_editor(self) -> DiagramEditorWidget | None:
        """获取当前图表编辑器

        返回：
            当前图表编辑器控件
        """
        # 获取当前图表页面
        page = self._current_diagram_page()
        # 返回页面的editor属性
        return getattr(page, "editor", None) if page is not None else None

    def _current_diagram_data(self) -> DiagramData | None:
        """获取当前图表数据

        返回：
            当前图表数据对象
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return None
        # 返回项目选中的图表
        return project.selected_diagram

    def _on_add_diagram(self):
        """添加新图表"""
        # 获取当前项目
        project = project_service.current_project
        # 如果项目为空，新建项目
        if project is None:
            project = project_service.new_project()
        # 同步工作流到项目
        self._sync_workflow_to_project()
        # 添加新图表
        diagram = project.add_diagram()
        # 刷新图表标签页
        self._refresh_diagram_tabs(project)
        # 记录日志
        self._log_panel.info(f"新建流程图: {diagram.name}")
        # 同步项目标签
        self._sync_proj_labels(project)

    def _on_duplicate_diagram(self):
        """复制当前图表"""
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 同步工作流到项目
        self._sync_workflow_to_project()
        # 复制当前图表
        clone = project.duplicate_diagram()
        if clone:
            # 刷新图表标签页
            self._refresh_diagram_tabs(project)
            # 记录日志
            self._log_panel.success(f"已复制流程图: {clone.name}")

    def _on_add_from_template(self):
        """从模板添加图表

        流程：
          1. 检查：没有模板时显示"不存在模板，请先添加模板"
          2. 显示DiagramTemplates选择对话框（ListBox DataTemplate）
          3. 提交时：将SelectedDiagramTemplate.Diagram添加到DiagramDatas
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 如果没有模板
        if not project.templates:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "不存在模板，请先将流程图另存为模板")
            return
        # 导入模板管理器对话框
        from gui.template_dialog import TemplateManagerDialog
        # 创建对话框
        dlg = TemplateManagerDialog(project, self)
        # 执行对话框
        dlg.exec_()
        # 如果有添加的图表
        if dlg.added_diagram:
            # 刷新图表标签页
            self._refresh_diagram_tabs(project)
            # 记录日志
            self._log_panel.success(f"从模板创建: {dlg.added_diagram.name}")

    def _on_manage_templates(self):
        """打开模板管理对话框"""
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 导入模板管理器对话框
        from gui.template_dialog import TemplateManagerDialog
        # 创建对话框
        dlg = TemplateManagerDialog(project, self)
        # 执行对话框
        dlg.exec_()
        # 持久化任何删除操作
        self._persist_templates()
        # 如果有添加的图表
        if dlg.added_diagram:
            # 刷新图表标签页
            self._refresh_diagram_tabs(project)
            # 记录日志
            self._log_panel.success(f"从模板创建: {dlg.added_diagram.name}")

    def _load_templates_on_startup(self):
        """应用启动时加载全局模板

        必须在 _discover_nodes() 填充 node_registry 之后运行，
        否则 node_registry.create() 对所有类型返回 None，节点会丢失。
        """
        # 加载模板
        project_service._templates = project_service.load_templates()
        # 获取当前项目
        project = project_service.current_project
        # 如果项目存在
        if project is not None:
            # 同步模板列表
            project._templates = list(project_service._templates)

    def _persist_templates(self):
        """持久化模板到磁盘"""
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 同步到全局存储
        project_service._templates = list(project._templates)
        # 保存模板
        project_service.save_templates(project._templates)

    def _on_save_as_template(self):
        """将当前图表另存为模板

        Python: 使用 QInputDialog 实现相同行为。

        检查：如果图表没有节点，警告用户以防止保存空模板。
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 获取当前选中的图表
        diagram = project.selected_diagram
        if diagram is None:
            return

        # 获取节点数量
        node_count = len(diagram.workflow.get_all_nodes()) if diagram.workflow else 0
        # 如果没有节点
        if node_count == 0:
            # 询问用户是否保存空模板
            reply = QMessageBox.question(
                self, "空流程图",
                "当前流程图没有任何节点，保存为模板后添加时将显示空白画布。\n\n确定要保存空模板吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        # 导入输入对话框
        from PyQt5.QtWidgets import QInputDialog
        # 获取模板名称
        name, ok = QInputDialog.getText(
            self, "保存模板名称",
            "请输入模板名称：",
            text=diagram.name)
        # 如果确认且名称不为空
        if ok and name.strip():
            # 同步工作流到项目
            self._sync_workflow_to_project()
            # 保存为模板
            project.save_diagram_as_template(diagram=diagram, name=name.strip())
            # 持久化模板
            self._persist_templates()
            # 记录日志
            self._log_panel.success(f"模板已保存: {name.strip()} ({node_count} 个节点)")

    def _on_delete_diagram(self):
        """删除当前图表

        模式：
          - Model (VisionProjectItemBase) 持有 DeleteDiagramCommand
          - CanExecute: SelectedDiagramData != null && Count > 1
          - Execute: DiagramDatas.Remove(SelectedDiagramData)
          - TabControl 通过绑定自动选择下一个图表

        Python: 同步 → model.delete_selected_diagram() → 刷新标签页 → 记录日志。
        视图只处理UI关注点；业务逻辑留在 ProjectItem 中。
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 同步工作流到项目
        self._sync_workflow_to_project()
        # 删除选中的图表
        deleted = project.delete_selected_diagram()
        # 如果删除成功
        if deleted is not None:
            # 刷新图表标签页
            self._refresh_diagram_tabs(project)
            # 记录日志
            self._log_panel.info(f"已删除流程图: {deleted.name}")
            # 同步项目标签
            self._sync_proj_labels(project)
        else:
            # 记录警告（至少需要保留一个流程图）
            self._log_panel.warning("至少需要保留一个流程图")

    def _on_close_diagram_tab(self, index: int):
        """通过标签页索引关闭图表

        流程与 _on_delete_diagram 相同，但使用显式索引，
        用于用户点击标签页关闭按钮而非工具栏删除按钮的情况。

        参数：
            index: 标签页索引
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 检查索引有效性
        if not (0 <= index < len(project.diagrams)):
            return
        # 同步工作流到项目
        self._sync_workflow_to_project()
        # 获取要删除的图表
        diagram = project.diagrams[index]
        # 删除图表
        if not project.delete_diagram(diagram):
            # 记录警告
            self._log_panel.warning("至少需要保留一个流程图")
            return
        # 刷新图表标签页
        self._refresh_diagram_tabs(project)
        # 记录日志
        self._log_panel.info(f"已删除流程图: {diagram.name}")
        # 同步项目标签
        self._sync_proj_labels(project)

    def _on_diagram_tab_changed(self, index: int):
        """图表标签页切换事件

        参数：
            index: 新的标签页索引
        """
        # 获取当前项目
        project = project_service.current_project
        # 如果项目为空或索引无效
        if project is None or not (0 <= index < len(project.diagrams)):
            # 在标签页重建期间，忽略无效索引信号，避免在 clear() 和 setCurrentIndex() 之间禁用按钮
            if getattr(self, '_rebuilding_tabs', False):
                return
            # 清空工作流引用
            self._workflow = None
            # 清空编辑器引用
            self._diagram_editor = None
            # 绑定空工作流到运行器
            self._wf_runner.bind(None)
            # 设置图表状态栏
            self._diagram_status_strip.set_status("流程图就绪", "#4caf50")
            # 刷新命令状态
            self._refresh_command_states(None)
            return
        # 更新项目的选中图表索引
        project.selected_diagram_index = index
        # 获取选中的图表
        diagram = project.selected_diagram
        # 获取当前图表页面
        page = self._current_diagram_page()
        # 清空结果面板的历史记录
        self._result_panel.clear_history()
        # 设置工作流
        self._workflow = diagram.workflow if diagram else None
        # 绑定工作流到结果面板
        self._result_panel.bind_workflow(self._workflow)
        # 同步历史记录
        self._result_panel.sync_history_from_workflow()
        # 绑定工作流到运行器
        self._wf_runner.bind(self._workflow)
        # 获取编辑器
        self._diagram_editor = getattr(page, "editor", None)
        # 更新节点计数标签
        self._node_cnt_lbl.setText(f"节点: {len(self._workflow.get_all_nodes()) if self._workflow else 0}")
        # 同步项目标签
        self._sync_proj_labels(project)
        # 刷新图表标签页头部激活状态
        self._refresh_diagram_tab_headers()
        # 设置图表状态栏
        self._diagram_status_strip.set_status(f"当前流程图：{diagram.display_name}", "#4caf50")

    def _sync_proj_labels(self, project: ProjectItem | None):
        """同步项目标签

        参数：
            project: 项目对象
        """
        # 如果项目为空
        if project is None:
            project_name = "无项目"
            diagram_name = "无流程图"
            self.setWindowTitle("VisionFlow — VisionFlow")
        else:
            project_name = project.name or project.display_name
            diagram_name = project.selected_diagram.display_name if project.selected_diagram else "无流程图"
            self.setWindowTitle(f"{project_name} — VisionFlow")
        # 如果有标题栏项目名称标签，更新
        if hasattr(self, "_cap_proj_lbl"):
            self._cap_proj_lbl.setText(project_name)
        # 如果有命令栏项目名称标签，更新
        if hasattr(self, "_cmd_proj_lbl"):
            self._cmd_proj_lbl.setText(diagram_name)
        # 刷新命令状态
        self._refresh_command_states(project)

    def _refresh_command_states(self, project: ProjectItem | None):
        """更新工具栏按钮启用状态

        管理的按钮：
          - 开始：当 CanStart 为 True 时启用（状态 != Running && != Canceling && 有节点）
          - 停止：当 CanStop 为 True 时启用（状态 == Running）
          - 重置：当 CanReset 为 True 时启用（总是）
          - 删除流程图：当 SelectedDiagramData != null && Count > 1 时启用

        参数：
            project: 项目对象
        """
        # 获取当前工作流
        workflow = self._workflow
        # 设置运行按钮状态
        if hasattr(self, '_run_btn'):
            self._run_btn.setEnabled(workflow.can_start() if workflow else False)
        # 设置连续运行按钮状态
        if hasattr(self, '_continuous_btn'):
            self._continuous_btn.setEnabled(workflow.can_start() if workflow else False)
        # 设置停止按钮状态
        if hasattr(self, '_stop_btn'):
            self._stop_btn.setEnabled(
                (workflow.can_stop() if workflow else False) or self._continuous_mode)
        # 设置重置按钮状态
        if hasattr(self, '_reset_btn'):
            self._reset_btn.setEnabled(workflow.can_reset() if workflow else False)
        # 设置删除流程图按钮状态
        if hasattr(self, '_delete_diagram_btn'):
            self._delete_diagram_btn.setEnabled(
                project.can_delete_diagram if project is not None else False)

    def _sync_workflow_to_project(self):
        """同步工作流到项目"""
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 遍历项目的所有图表
        for index, diagram in enumerate(project.diagrams):
            # 如果索引在标签页范围内
            if index < self._diagram_tab_widget.count():
                # 获取页面
                page = self._diagram_tab_widget.widget(index)
                # 获取编辑器
                editor = getattr(page, "editor", None)
                # 如果编辑器存在，保存到工作流
                if editor is not None:
                    editor.save_to_workflow()
                    diagram.workflow = editor._workflow

    def _select_node(self, node: NodeBase | None):
        """选择节点

        参数：
            node: 节点数据对象
        """
        # 切换节点或取消选择时停止实时预览
        self._live_preview_timer.stop()
        # 保存选中的节点
        self._selected_node = node
        # 更新属性面板显示选中节点的属性
        self._property_panel.set_node(node)
        # 更新帮助面板显示选中节点的帮助信息
        self._help_panel.set_node(node)
        # 更新模块结果标题显示选中节点的名称
        self._module_result_title.setText(f"模块名称 <{node.name}>" if node else "模块名称 <未选择>")
        # 仅当选中节点是 VisionNodeData 时才显示结果和帮助
        if isinstance(node, VisionNodeData):
            # 在结果面板显示选中节点的结果
            self._result_panel.show_node_results(node)
            # 在结果面板显示选中节点的帮助信息
            self._result_panel.show_help(node)
        else:
            # 非 VisionNodeData 时不显示结果
            self._result_panel.show_node_results(None)
            # 非 VisionNodeData 时不显示帮助
            self._result_panel.show_help(None)
        # 更新图像上下文显示选中节点的相关图像
        self._update_image_context(node)

        # 如果选中节点是 SrcFilesVisionNodeData，则启用资源面板
        if isinstance(node, SrcFilesVisionNodeData):
            self._resource_panel.set_node(node)
            self._resource_panel.setVisible(True)
        else:
            self._resource_panel.setVisible(False)
            self._resource_panel.set_node(None)

        # 更新图像面板
        if isinstance(node, VisionNodeData) and node.mat is not None:
            self._img_panel.set_image(node.mat)
        elif isinstance(node, VisionNodeData) and node._result_image_source is not None:
            self._img_panel.set_image(node._result_image_source)
        else:
            self._img_panel.set_image(None)


        # 更新状态栏
        if node is not None:
            self._side_status_strip.set_status(f"已选择模块：{node.name}", "#0078d4")
            # 在连续执行期间启动实时预览
            if self._continuous_mode and isinstance(node, VisionNodeData):
                self._live_preview_timer.start()
        else:
            self._side_status_strip.set_status("等待选择节点", "#4caf50")
            self._live_preview_timer.stop()

    def _on_node_type_selected(self, type_name: str):
        """节点类型选中事件

        参数：
            type_name: 节点类型名称
        """
        # 如果没有工作流，返回
        if not self._workflow:
            return
        # 从节点注册表创建节点
        node = self._ctx.node_registry.create(type_name) if self._ctx.node_registry else None
        # 获取当前图表编辑器
        editor = self._current_diagram_editor()
        # 如果节点存在且编辑器存在
        if node is not None and editor is not None:
            # 添加节点
            editor.add_node(node, group_name=self._get_group(type_name))
            # 记录使用
            self._toolbox.record_use(type_name)
            # 记录日志
            self._log_panel.info(f"添加节点: {node.name}")
            # 更新节点计数标签
            self._node_cnt_lbl.setText(f"节点: {len(self._workflow.get_all_nodes())}")

    def _on_editor_node_selected(self, node_data: NodeBase):
        """编辑器节点选中事件

        参数：
            node_data: 节点数据
        """
        self._select_node(node_data)

    def _on_editor_node_double_clicked(self, node_data: NodeBase):
        """处理节点双击 — 打开标签页属性对话框

        解耦：调用 open_node_dialog，它使用 get_property_presenter()
        来解析设置对象。不同的节点类型可以重写 get_property_presenter()
        来提供自定义的设置面板。

        参数：
            node_data: 节点数据
        """
        from gui.property_panel import open_node_dialog
        # 选中节点
        self._select_node(node_data)
        # 打开节点对话框
        open_node_dialog(node_data, parent=self)

    def _on_node_executed(self, node_data, state: str, time_span: str):
        """处理节点执行完成

        历史记录同步由 ResultPanel 直接订阅 NODE_COMPLETED / NODE_ERROR 事件处理
        （通过 core.events.event_system），绕过编辑器的 node_executed 信号链，
        该信号链可能因双 WorkflowEngine 实例而失败。

        在连续模式下，当执行的节点是当前选中的节点时刷新图像面板。

        参数：
            node_data: 节点数据
            state: 执行状态
            time_span: 执行时间
        """
        # 连续模式：为选中的节点实时更新图像
        if (getattr(self, '_continuous_mode', False)
                and self._selected_node is node_data
                and isinstance(node_data, VisionNodeData)):
            # 如果有图像数据，更新图像面板
            if node_data.mat is not None:
                self._img_panel.set_image(node_data.mat)
            elif getattr(node_data, '_result_image_source', None) is not None:
                self._img_panel.set_image(node_data._result_image_source)

    def _on_editor_node_help_requested(self, node_data: NodeBase):
        """处理右键 → 帮助 — 切换到帮助标签页并显示节点帮助

        参数：
            node_data: 节点数据
        """
        # 选中节点
        self._select_node(node_data)
        # 切换到帮助标签页
        if hasattr(self, '_bottom_tabs'):
            self._bottom_tabs.setCurrentIndex(2)  # 索引2 = 帮助标签页
        # 显示帮助内容
        if hasattr(self, '_help_panel'):
            self._help_panel.set_node(node_data)

    def _on_editor_status(self, message: str):
        """编辑器状态消息

        参数：
            message: 状态消息
        """
        # 更新消息标签
        self._msg_lbl.setText(message)
        if message:
            # 更新图表状态栏
            self._diagram_status_strip.set_status(message, "#0078d4")

    def _get_group(self, type_name: str) -> str:
        """获取节点类型所属的分组名称

        参数：
            type_name: 节点类型名称

        返回：
            分组名称
        """
        from core.node_group import node_data_group_manager
        # 遍历所有分组
        for group in node_data_group_manager.get_all_groups():
            # 遍历分组中的节点类型
            for node_type in group.node_types:
                # 如果匹配，返回分组名称
                if node_type.__name__ == type_name:
                    return group.name
        return ""

    def _on_property_changed(self, name, old, new):
        """属性变化事件

        参数：
            name: 属性名
            old: 旧值
            new: 新值
        """
        # 如果有选中的节点
        if self._selected_node:
            # 发布节点属性变化事件
            event_system.publish(EventType.NODE_PROPERTY_CHANGED, sender=self._selected_node, name=name, old=old,
                                 new=new)

    def _on_ev_node_sel(self, sender, **kwargs):
        """节点选中事件处理

        参数：
            sender: 发送者
            **kwargs: 关键字参数
        """
        self._select_node(kwargs.get("node", sender))

    def _on_ev_diag_chg(self, sender, **kwargs):
        """图表变更事件处理

        参数：
            sender: 发送者
            **kwargs: 关键字参数
        """
        # 如果有工作流，更新节点计数
        if self._workflow:
            self._node_cnt_lbl.setText(f"节点: {len(self._workflow.get_all_nodes())}")
        # 节点添加/删除 → CanStart 条件可能已改变
        self._refresh_command_states(project_service.current_project)

    def _on_wf_start(self, sender, **kwargs):
        """工作流启动事件（在工作线程上运行）— 发出信号以在主线程上更新UI"""
        self._wf_ui_update.emit("start", {})

    def _on_wf_done(self, sender, **kwargs):
        """工作流完成事件（在工作线程上运行）— 发出信号以在主线程上更新UI"""
        self._wf_ui_update.emit("done", {"result": kwargs.get("result")})

    def _on_wf_err(self, sender, **kwargs):
        """工作流错误事件（在工作线程上运行）— 发出信号以在主线程上更新UI"""
        self._wf_ui_update.emit("error", {"result": kwargs.get("result")})

    def _on_wf_stopped(self, sender, **kwargs):
        """工作流停止事件（在工作线程上运行）— 发出信号以在主线程上更新UI"""
        self._wf_ui_update.emit("stopped", {})

    def _on_file_iteration_next(self, sender, **kwargs):
        """处理 FILE_ITERATION_NEXT — 在"运行全部"循环期间更新图像显示以显示当前文件

        VisionDiagramDataBase.Start():
          1. ResultImageSource = item.ToImageSource()    // 总是 — 更新图像查看器
          2. if (UseAutoSwitch) SrcFilePath = item       // 仅在开启时 — 更新缩略图

        解耦：UI 订阅事件，更新图像查看器 + 当 auto_switch 开启时可选地刷新 FlowResourcePanel。

        参数：
            sender: 发送者
            **kwargs: 关键字参数（file_path, index, total, auto_switch）
        """
        # 获取参数
        file_path = kwargs.get("file_path", "")
        index = kwargs.get("index", 0)
        total = kwargs.get("total", 0)
        auto_switch = kwargs.get("auto_switch", True)
        # 如果没有文件路径，返回
        if not file_path:
            return

        # ResultImageSource = item.ToImageSource() — 总是更新显示
        import cv2
        try:
            # 读取图像
            img = cv2.imread(file_path, cv2.IMREAD_COLOR)
            if img is not None:
                # 获取图像尺寸
                h, w = img.shape[:2]
                # 更新图像面板
                self._img_panel.set_image(img)
                # 设置图像信息
                self._img_panel.set_image_info(file_path, w, h)
                # 切换到图像标签页
                self._center_tabs.setCurrentIndex(0)
                # 设置状态标签
                label = "自动切换" if auto_switch else "显示全部"
                self._side_status_strip.set_status(
                    f"{label}: {os.path.basename(file_path)} [{index + 1}/{total}]", "#2196f3"
                )
        except Exception:
            pass

        # if (UseAutoSwitch) SrcFilePath = item — 刷新缩略图面板
        # SrcFilePath 本身总是在事件前由 WorkflowRunner 更新。
        # 这里仅在 auto_switch 开启时刷新 UI 缩略图条。
        if auto_switch and self._resource_panel.isVisible():
            self._resource_panel.refresh_selection()

    def _on_file_iteration_completed(self, sender, **kwargs):
        """处理 FILE_ITERATION_COMPLETED — 在"运行全部"循环后重置显示状态

        RunModeResult = result (bool?), LogCurrentMessage()

        参数：
            sender: 发送者
            **kwargs: 关键字参数（total）
        """
        # 获取总文件数
        total = kwargs.get("total", 0)
        # 设置状态栏
        self._side_status_strip.set_status(f"显示全部完成: {total} 个文件", "#4caf50")
        # 完成执行状态（与单次运行的 _finalize_execution_state 相同）
        self._finalize_execution_state()

    def _on_wf_ui_update(self, event: str, data: dict):
        """槽函数通过队列信号在主线程上被调用。可以安全地操作控件

        参数：
            event: 事件类型（start/done/error/stopped）
            data: 事件数据
        """
        # 如果工作流开始
        if event == "start":
            # 记录工作流开始时间
            self._wf_start_time = __import__('time').time()
            # 更新状态标签为运行中
            self._state_lbl.setText(f"{FontIcons.Sync} 运行中")
            self._state_lbl.setStyleSheet("color: #2196f3; font-weight: bold;")
            # 更新消息标签
            self._msg_lbl.setText("流程运行中...")
            # 更新图表状态栏
            self._diagram_status_strip.set_status("流程图运行中...", "#2196f3")
            # 更新结果区状态栏
            self._side_status_strip.set_status("结果区正在等待输出...", "#2196f3")
            # 刷新命令状态
            self._refresh_command_states(project_service.current_project)
        # 如果工作流完成（整条流程的每个节点都执行完，且没有出错、没有被停止）
        elif event == "done":
            self._finalize_execution_state()
            # 计算工作流运行时间
            elapsed = self._format_elapsed()
            # 根据是否连续执行设置标签
            label = "连续执行中" if getattr(self, '_continuous_mode', False) else "流程执行完成"
            # 更新状态标签
            self._state_lbl.setText(f"{FontIcons.Completed} {label}")
            self._state_lbl.setStyleSheet("color: #4caf50; font-weight: bold;")
            # 更新消息标签
            self._msg_lbl.setText(f"{label} (用时: {elapsed})")
            # 更新图表状态栏
            self._diagram_status_strip.set_status(f"{label} · 用时: {elapsed}", "#4caf50")
            # 更新结果区状态栏
            self._side_status_strip.set_status("结果区已更新", "#4caf50")
            # 在连续执行期间保持停止按钮启用
            if getattr(self, '_continuous_mode', False):
                self._refresh_command_states(project_service.current_project)
            # 在连续模式下，刷新用户选择的节点的图像
            if getattr(self, '_continuous_mode', False) and self._selected_node:
                self._update_image_context(self._selected_node)
                # 如果选中的节点是视觉节点
                if isinstance(self._selected_node, VisionNodeData):
                    # 获取节点的图像数据
                    mat = self._selected_node.mat
                    if mat is not None:
                        self._img_panel.set_image(mat)
                    elif getattr(self._selected_node, '_result_image_source', None) is not None:
                        self._img_panel.set_image(self._selected_node._result_image_source)
        # 如果发生错误（某个节点发生错误）
        elif event == "error":
            self._finalize_execution_state()
            # 关闭连续模式
            self._continuous_mode = False
            # 停止实时预览定时器
            self._live_preview_timer.stop()
            # 刷新命令状态
            self._refresh_command_states(project_service.current_project)
            # 计算工作流运行时间
            elapsed = self._format_elapsed()
            # 更新状态标签
            self._state_lbl.setText(f"{FontIcons.Error} 错误")
            self._state_lbl.setStyleSheet("color: #f44336; font-weight: bold;")
            # 获取错误消息
            msg = getattr(data.get("result"), 'message', '流程错误')
            # 更新消息标签
            self._msg_lbl.setText(f"{msg} (用时: {elapsed})")
            # 更新图表状态栏
            self._diagram_status_strip.set_status(f"流程图错误：{msg}", "#f44336")
            # 更新结果区状态栏
            self._side_status_strip.set_status("结果区收到错误消息", "#f44336")
        # 如果事务停止
        elif event == "stopped":
            self._finalize_execution_state()
            # 关闭连续模式
            self._continuous_mode = False
            # 更新状态标签
            self._state_lbl.setText(f"{FontIcons.Stop} 已停止")
            self._state_lbl.setStyleSheet("color: #ff9800; font-weight: bold;")
            # 更新消息标签
            self._msg_lbl.setText("流程已被用户停止")
            # 更新图表状态栏
            self._diagram_status_strip.set_status("流程图已停止", "#ff9800")
            # 更新结果区状态栏
            self._side_status_strip.set_status("结果区已停止等待", "#ff9800")
        # 刷新命令状态
        self._refresh_command_states(project_service.current_project)

    def _format_elapsed(self) -> str:
        """格式化工作流运行时间

        返回：
            格式化的时间字符串
        """
        # 获取工作流开始时间
        start = getattr(self, '_wf_start_time', None)
        # 如果没有开始时间，返回"00:00:00"
        if start is None:
            return "00:00:00"
        # 计算运行秒数
        seconds = time.time() - start
        # 计算小时
        h = int(seconds // 3600)
        # 计算分钟
        m = int((seconds % 3600) // 60)
        # 计算秒
        s = int(seconds % 60)
        # 如果有小时，返回"HH:MM:SS"格式
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        # 否则返回"MM:SS"格式
        return f"{m:02d}:{s:02d}"

    def _on_proj_load(self, sender, **kwargs):
        """项目加载事件处理

        参数：
            sender: 发送者
            **kwargs: 关键字参数
        """
        # 获取项目对象
        project = kwargs.get("project")
        if project:
            # 绑定项目图表
            self._bind_project_diagram(project)

    def _on_proj_save(self, sender, **kwargs):
        """项目保存事件处理

        参数：
            sender: 发送者
            **kwargs: 关键字参数
        """
        # 获取项目对象
        project = kwargs.get("project")
        if project:
            # 同步项目标签
            self._sync_proj_labels(project)

    def _update_clock(self):
        """更新时钟显示"""
        # 设置时间标签为当前时间
        self._time_lbl.setText(datetime.now().strftime("%H:%M:%S"))

    def _on_new_project(self):
        """新建项目"""
        # 创建新项目
        project = project_service.new_project()
        # 绑定项目图表
        self._bind_project_diagram(project)
        # 记录日志
        self._log_panel.info("新建项目")

    def _on_open_project(self):
        """打开项目"""
        # 打开文件选择对话框
        path, _ = QFileDialog.getOpenFileName(self, "打开项目", "", project_service.FILE_FILTER)
        if path:
            self._open_project(path)

    def _open_project(self, path: str):
        """打开指定路径的项目

        参数：
            path: 项目文件路径
        """
        # 如果路径无效或文件不存在
        if not path or not os.path.exists(path):
            # 从最近列表中移除
            project_service.remove_recent(path)
            # 显示警告
            QMessageBox.warning(self, "打开失败", f"文件不存在: {path}")
            return
        # 加载项目
        project = project_service.load(path)
        if project:
            # 绑定项目图表
            self._bind_project_diagram(project)
            # 记录日志
            self._log_panel.success(f"已打开: {path}")

    def open_project(self, file_path: str):
        """公开的打开项目方法

        参数：
            file_path: 项目文件路径
        """
        self._open_project(file_path)

    def _on_save_project(self):
        """保存项目"""
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 同步工作流到项目
        self._sync_workflow_to_project()
        # 如果项目有文件路径
        if project.file_path:
            if project_service.save(project):
                self._log_panel.success(f"项目已保存: {os.path.basename(project.file_path)}")
            else:
                self._log_panel.error("项目保存失败")
        else:
            # 否则另存为
            self._on_save_as_project()

    def _on_save_as_project(self):
        """另存为项目"""
        # 获取当前项目，如果为空则新建项目
        project = project_service.current_project or project_service.new_project()
        # 打开保存文件对话框，默认文件名格式为"项目名.json"
        path, _ = QFileDialog.getSaveFileName(self, "另存为...", f"{project.name}.json", project_service.FILE_FILTER)
        # 如果用户选择了路径
        if path:
            # 设置项目的文件路径
            project.file_path = path
            # 同步工作流到项目（将当前编辑器的状态保存到项目）
            self._sync_workflow_to_project()
            # 调用项目服务的另存为方法
            if project_service.save_as(project, path):
                # 记录成功日志
                self._log_panel.success(f"已保存至: {path}")
                # 同步项目标签（更新标题栏显示的项目名称）
                self._sync_proj_labels(project)

    def _on_run_workflow(self):
        """单次运行：执行工作流一次

        在工作线程上按拓扑顺序执行所有节点。
        - 每个节点条通过事件变为绿色（完成）或红色（错误）。
        - 图像区域保持空白，直到用户点击节点。
        """
        # 开始执行，连续模式为False
        self._start_execution(continuous=False)

    def _on_continuous_run(self):
        """连续运行：循环执行工作流

        每次迭代时摄像头捕获新帧。节点条实时更新。
        当用户点击节点时，其处理后的图像会连续更新。
        """
        # 开始执行，连续模式为True
        self._start_execution(continuous=True)

    def _start_execution(self, continuous: bool = False):
        """公共执行入口 — 同步、检查、委托给 WorkflowRunner。

          - 单次运行 → VisionDiagramDataBase.Start()（单张图像）
          - "运行全部" → VisionDiagramDataBase.Start() + UseAllImage 循环
          - 连续运行 → 带间隔的循环

        节点状态直接在主线程上设置 — 不通过跨线程事件，因为跨线程事件与 threading.Thread 不可靠。

        参数：
            continuous: 是否为连续运行模式
        """
        # 如果没有工作流，返回
        if not self._workflow:
            return
        # 同步工作流到项目（保存当前编辑器的状态）运行前强制刷新，获得流程图当前最新状态和数据
        self._sync_workflow_to_project()
        # 获取工作流中的节点数量
        node_count = len(self._workflow.get_all_nodes())
        # 如果没有节点，弹出警告并返回
        if node_count == 0:
            self._log_panel.warning("流程图无节点，无法开始")
            return

        # 设置连续模式标志
        self._continuous_mode = continuous
        # 重置停止请求标志
        self._stop_requested = False

        # 刷新按钮状态，以便在连续模式下启用停止按钮
        self._refresh_command_states(project_service.current_project)

        # 在主线程上将所有节点状态设置为运行中（可靠，不会产生跨线程问题）
        editor = self._current_diagram_editor()
        if editor:
            from core.node_base import VisionNodeData
            # 遍历场景中的所有节点项
            for item in editor.scene.get_all_node_items():
                # 清除上次执行的残留状态，避免旧状态污染本轮判断
                nd = item.node_data
                if isinstance(nd, VisionNodeData):
                    nd._execution_state = None
                # 设置节点状态为运行中
                item.set_state(NodeState.RUNNING)

        # 检测"运行全部"模式
        if not continuous:
            # 获取起始节点
            start_node = self._workflow.get_start_node_data()
            # 如果是源文件节点且启用了"使用所有图像"标志
            if isinstance(start_node, SrcFilesVisionNodeData) and start_node.use_all_image:
                # 获取文件路径列表
                file_paths = start_node.src_file_paths
                if file_paths:
                    # 获取自动切换标志
                    auto_switch = getattr(start_node, 'use_auto_switch', True)
                    # 记录日志
                    self._log_panel.info(f"运行全部: {len(file_paths)} 个文件 ({node_count} 个节点)")
                    # 启动运行全部模式
                    self._wf_runner.start_run_all(
                        file_paths=file_paths,
                        auto_switch=auto_switch,
                        interval=1.0,  # Task.Delay(1000)，间隔1秒
                    )
                    # 状态完成由 _on_file_iteration_completed + 轮询兜底处理
                    self._poll_execution_finished()
                    return

        # 根据连续模式设置日志标签
        label = "连续执行" if continuous else "开始执行流程"
        self._log_panel.info(f"{label}... ({node_count} 个节点)")

        # 启动工作流运行器
        if continuous:
            # 连续运行模式
            self._wf_runner.start_continuous()
        else:
            # 单次运行模式
            self._wf_runner.start_once()

        # 用主线程定时器轮询 _run_finished 标记（避免跨线程 pyqtSignal 不可靠）
        self._poll_execution_finished()


    def _poll_execution_finished(self):
        """用主线程定时器轮询后台线程的执行完成标记，完成后调用 _finalize_execution_state"""
        def _check():
            if self._wf_runner._run_finished.is_set():
                self._finalize_execution_state()
            else:
                # 继续轮询，每100ms检查一次，最多检查50次（5秒超时）
                _check.count += 1
                if _check.count < 50:
                    QTimer.singleShot(100, _check)
                else:
                    # 超时兜底：强制最终化
                    self._finalize_execution_state()
        _check.count = 0
        QTimer.singleShot(50, _check)

    def _finalize_execution_state(self):
        """执行完成后，将节点状态设置为最终值"""
        # 如果不是连续模式，停止实时预览定时器
        if not self._continuous_mode:
            self._live_preview_timer.stop()
        # 获取当前图表编辑器
        editor = self._current_diagram_editor()
        # 如果编辑器或工作流不存在，返回
        if editor is None or not self._workflow:
            return
        from core.node_base import VisionNodeData
        # 遍历场景中的所有节点项
        for item in editor.scene.get_all_node_items():
            # 获取节点数据
            nd = item.node_data
            # 如果是视觉节点，根据执行状态设置 UI 状态
            if isinstance(nd, VisionNodeData):
                state = nd._execution_state
                if state == "error":
                    item.set_state(NodeState.ERROR)
                elif state == "completed":
                    item.set_state(NodeState.COMPLETED)
                elif state == "break":
                    item.set_state(NodeState.IDLE)
                else:
                    # 未执行到的节点（上游中断导致跳过）设为已完成
                    item.set_state(NodeState.COMPLETED)
            else:
                # 非视觉节点直接设为完成
                item.set_state(NodeState.COMPLETED)

    def _tick_live_preview(self):
        """在连续执行期间，从选定节点刷新图像查看器"""
        # 获取当前选中的节点
        node = self._selected_node
        # 如果未选中节点或者不是连续模式
        if node is None or not self._continuous_mode:
            # 停止计时器
            self._live_preview_timer.stop()
            return
        # 如果节点是视觉节点
        if isinstance(node, VisionNodeData):
            # 如果节点有图像矩阵数据
            if node.mat is not None:
                # 将节点图片刷新到图片显示区域
                self._img_panel.set_image(node.mat)
            # 如果节点有结果图像源
            elif node._result_image_source is not None:
                # 更新图像
                self._img_panel.set_image(node._result_image_source)

    def _on_stop_workflow(self):
        """停止工作流执行

        Stop() → Canceling → GotoState on all parts → Canceled.
        Python：委托给 WorkflowRunner + 直接状态重置。
        """
        # 设置停止请求标志
        self._stop_requested = True
        # 关闭连续模式
        self._continuous_mode = False
        # 停止实时预览定时器
        self._live_preview_timer.stop()
        # 停止工作流运行器
        self._wf_runner.stop()
        # 直接重置所有节点状态（可靠，无跨线程事件）
        editor = self._current_diagram_editor()
        if editor:
            # 遍历场景中的所有节点项
            for item in editor.scene.get_all_node_items():
                # 设置节点状态为空闲
                item.set_state(NodeState.IDLE)
        # 记录警告日志
        self._log_panel.warning("流程已停止")
        # 更新图表状态栏为橙色
        self._diagram_status_strip.set_status("流程图已停止", "#ff9800")
        # 更新侧边状态栏为橙色
        self._side_status_strip.set_status("结果区已停止等待", "#ff9800")
        # 刷新命令状态
        self._refresh_command_states(project_service.current_project)

    def _on_reset_workflow_view(self):
        """重置工作流到就绪状态

        Reset() → GotoState(x => FlowableState.Ready) on all parts.
        Python：model.reset() 重置状态；同时从工作流重新加载场景。
        """
        # 如果工作流存在，重置工作流状态
        if self._workflow:
            self._workflow.reset()
        # 获取当前图表编辑器
        editor = self._current_diagram_editor()
        # 如果编辑器和工流都存在，重新绑定工作流
        if editor is not None and self._workflow is not None:
            editor.bind_workflow(self._workflow)
        # 记录信息日志
        self._log_panel.info("已重置当前流程图")
        # 刷新命令状态
        self._refresh_command_states(project_service.current_project)

    def _on_cycle_run_mode(self):
        """循环切换运行模式：节点 → 连线 → 端口 → 节点"""
        # 如果没有工作流，返回
        if not self._workflow:
            return
        from core.workflow import DiagramFlowableMode
        # 模式显示标签字典
        _MODE_LABELS = {
            DiagramFlowableMode.NODE: "运行模式: 按节点",
            DiagramFlowableMode.LINK: "运行模式: 节点+连线",
            DiagramFlowableMode.PORT: "运行模式: 节点+连线+端口",
        }
        # 下一个模式的映射
        _NEXT = {
            DiagramFlowableMode.NODE: DiagramFlowableMode.LINK,
            DiagramFlowableMode.LINK: DiagramFlowableMode.PORT,
            DiagramFlowableMode.PORT: DiagramFlowableMode.NODE,
        }
        # 获取当前运行模式
        current = self._workflow.flowable_mode
        # 切换到下一个模式
        self._workflow.flowable_mode = _NEXT[current]
        # 获取新模式的显示标签
        new_label = _MODE_LABELS[self._workflow.flowable_mode]
        # 记录信息日志
        self._log_panel.info(new_label)
        # 更新图表状态栏，显示当前运行模式
        self._diagram_status_strip.set_status(new_label, "#0078d4")

    def _jump_to_node(self, node_id: str):
        """跳转到指定节点

        参数：
            node_id: 节点ID
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 遍历项目的所有图表
        for index, diagram in enumerate(project.diagrams):
            # 获取图表的工作流
            workflow = diagram.workflow
            # 如果工作流存在且包含该节点
            if workflow and workflow.get_node_by_id(node_id):
                # 切换到对应的图表标签页
                self._diagram_tab_widget.setCurrentIndex(index)
                # 获取当前图表编辑器
                editor = self._current_diagram_editor()
                if editor is None:
                    return
                # 获取节点项
                item = editor.scene.get_node_item(node_id)
                if item is not None:
                    # 清除当前选中状态
                    editor.scene.clearSelection()
                    # 选中该节点
                    item.setSelected(True)
                    # 将视图中心移动到该节点
                    editor.view.centerOn(item)
                    # 选中节点数据（更新属性面板等）
                    self._select_node(item.node_data)
                return

    def _on_resource_file_selected(self, path: str):
        """资源文件选中事件

        参数：
            path: 文件路径
        """
        if not path:
            return
        try:
            import cv2
            # 使用OpenCV读取图像
            image = cv2.imread(path, cv2.IMREAD_COLOR)
            if image is not None:
                # 获取图像高度和宽度
                h, w = image.shape[:2]
                # 在图像面板显示图像
                self._img_panel.set_image(image)
                # 设置图像信息（路径、尺寸）
                self._img_panel.set_image_info(path, w, h)
                # 切换到图像标签页
                self._center_tabs.setCurrentIndex(0)
        except Exception:
            pass

    def _on_result_image_update(self, image):
        """处理历史行点击 — 更新主图像显示

        参数：
            image: 图像数据
        """
        import numpy as np
        if image is not None:
            # 在图像面板显示图像
            self._img_panel.set_image(image)
            # 切换到图像标签页
            self._center_tabs.setCurrentIndex(0)

    def _on_resource_file_double_clicked(self, path: str):
        """打开图像文件的全尺寸缩放查看器

        参数：
            path: 文件路径
        """
        if not path or not os.path.exists(path):
            return
        # 切换到图像标签页并加载全分辨率
        self._on_resource_file_selected(path)
        # 切换到图像标签页
        self._center_tabs.setCurrentIndex(0)
        # 适应窗口大小
        if hasattr(self._img_panel, 'viewer'):
            self._img_panel.viewer.fit_to_window()

    def toggle_left_panel(self):
        """通过 GridSplitterBox 切换左侧面板"""
        # 切换左侧盒子的展开状态
        self._left_box.toggle_expand()
        # 更新左侧面板可见性标志
        self._left_panel_visible = self._left_box.is_expanded

    def toggle_right_panel(self):
        """切换右侧面板"""
        # 如果右侧面板可见
        if self._right_panel_visible:
            # 隐藏右侧面板
            self._right_panel.setVisible(False)
            # 设置可见性标志为False
            self._right_panel_visible = False
        else:
            # 显示右侧面板
            self._right_panel.setVisible(True)
            # 设置可见性标志为True
            self._right_panel_visible = True

    @property
    def active_workflow(self) -> WorkflowEngine | None:
        """获取当前活动的工作流

        返回：
            工作流对象或None
        """
        return self._workflow

    def add_diagram_tab(self, name: str, workflow: WorkflowEngine):
        """添加图表标签页

        参数：
            name: 图表名称
            workflow: 工作流引擎

        返回：
            图表名称
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            # 如果没有项目，新建项目
            project = project_service.new_project()
        # 创建图表数据对象
        diagram = DiagramData(name=name)
        # 设置图表的工作流
        diagram.workflow = workflow
        # 将图表添加到项目中
        project.diagrams.append(diagram)
        # 设置当前选中的图表索引为最后一个
        project.selected_diagram_index = len(project.diagrams) - 1
        # 刷新图表标签页
        self._refresh_diagram_tabs(project)
        return name

    def remove_diagram_tab(self, name: str):
        """按名称删除图表（供外部调用者使用，如CLI）

        与交互式删除处理程序不同，此方法不会先同步工作流 —
        调用者需要先保存（如果需要）。

        参数：
            name: 图表名称
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 遍历项目的所有图表
        for diagram in list(project.diagrams):
            if diagram.name == name:
                # 删除图表
                project.delete_diagram(diagram)
                break
        # 刷新图表标签页
        self._refresh_diagram_tabs(project)

    def switch_to_diagram(self, name_or_index: str | int):
        """切换到指定的图表

        参数：
            name_or_index: 图表名称或索引
        """
        # 如果是整数，按索引切换
        if isinstance(name_or_index, int):
            if 0 <= name_or_index < self._diagram_tab_widget.count():
                self._diagram_tab_widget.setCurrentIndex(name_or_index)
            return
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 遍历项目的所有图表
        for index, diagram in enumerate(project.diagrams):
            if diagram.name == name_or_index:
                # 切换到该图表
                self._diagram_tab_widget.setCurrentIndex(index)
                return

    def _active_visual_target(self):
        """获取当前活动的视觉目标控件（用于键盘操作）"""
        # 获取当前焦点控件
        focus = QApplication.focusWidget()
        # 获取当前图表编辑器
        editor = self._current_diagram_editor()
        # 如果编辑器存在且焦点控件存在
        if editor is not None and focus is not None:
            # 从焦点控件向上遍历父控件链
            current = focus
            while current is not None:
                # 如果找到编辑器或其视图
                if current is editor or current is editor.view:
                    return editor.view
                current = current.parentWidget()
        # 如果中央标签页当前索引为0（图像标签页）
        if self._center_tabs.currentIndex() == 0:
            return self._img_panel.viewer
        # 默认返回编辑器的视图或图像查看器
        return editor.view if editor is not None else self._img_panel.viewer

    def _on_reset_workflow_view(self):
        """重置工作流视图"""
        # 获取当前图表编辑器
        editor = self._current_diagram_editor()
        # 如果编辑器和工流都存在
        if editor is not None and self._workflow is not None:
            # 重新绑定工作流
            editor.bind_workflow(self._workflow)
            # 记录信息日志
            self._log_panel.info("已重置当前流程图视图")

    def _on_undo_diagram(self):
        """撤销图表操作"""
        # 获取当前图表编辑器
        editor = self._current_diagram_editor()
        if editor is not None:
            # 调用编辑器的撤销方法
            editor._on_undo()

    def _on_redo_diagram(self):
        """重做图表操作"""
        # 获取当前图表编辑器
        editor = self._current_diagram_editor()
        if editor is not None:
            # 调用编辑器的重做方法
            editor._on_redo()

    def _toggle_bottom(self):
        """切换底部面板的显示/隐藏"""
        # 获取中央分割器的大小
        sizes = self._center_splitter.sizes()
        # 如果大小列表长度小于2，返回
        if len(sizes) < 2:
            return
        # 如果底部面板当前可见
        if self._bottom_visible:
            # 保存当前底部面板高度
            _ps.set_i("bottom_height_saved", sizes[1])
            # 将底部面板高度设为0（隐藏）
            self._center_splitter.setSizes([sizes[0] + sizes[1], 0])
            # 切换按钮文本为向上箭头
            self._bottom_toggle.setText("▲")
        else:
            # 获取保存的底部面板高度，默认180
            saved = _ps.get_i("bottom_height_saved", 180)
            # 计算总高度
            total = sum(sizes)
            # 计算新的底部面板高度（不超过总高度减去220）
            height = min(saved, total - 220)
            # 设置分割器大小
            self._center_splitter.setSizes([total - height, height])
            # 切换按钮文本为向下箭头
            self._bottom_toggle.setText("▼")
        # 取反底部面板可见性标志
        self._bottom_visible = not self._bottom_visible

    def _update_image_context(self, node: NodeBase | None):
        """根据节点的不同情况，更新图像面板显示的信息

        参数：
            node: 节点数据对象
        """
        # 如果节点为空
        if node is None:
            # 清空图像显示区域的上下文信息
            self._img_panel.clear_context_info()
            return

        # 徽章文本和颜色
        badge = "无结果"
        badge_color = "#3f3f46"  # 灰色
        # 如果是源文件节点
        if isinstance(node, SrcFilesVisionNodeData):
            badge = "原始图像"
            badge_color = "#0078d4"  # 蓝色
        # 如果是视觉节点且存在图像数据
        elif isinstance(node, VisionNodeData) and (node.mat is not None or node.result_image_source is not None):
            badge = "模块结果"
            badge_color = "#4caf50"  # 绿色

        # 查找图像来源路径和提示信息
        source_path, source_hint = self._find_source_context(node)
        # 设置结果徽章
        self._img_panel.set_result_badge(badge, badge_color)
        # 设置来源提示
        self._img_panel.set_source_hint(source_hint)
        # 设置消息横幅
        self._img_panel.set_message_banner(getattr(node, "message", ""))
        # 如果有图像路径
        if source_path:
            # 获取像素宽度和高度
            pixel_w = getattr(node, 'pixel_width', 0) or 0
            pixel_h = getattr(node, 'pixel_height', 0) or 0
            # 显示图像路径和像素尺寸（宽×高）
            self._img_panel.set_image_info(source_path, pixel_w, pixel_h)
        else:
            # 清空图像信息
            self._img_panel.set_image_info(None)

    def _find_source_context(self, node: NodeBase | None) -> tuple[str | None, str]:
        """查找节点的图像来源上下文

        参数：
            node: 节点数据对象

        返回：
            (源文件路径, 提示信息) 元组
        """
        # 如果节点为空，返回None和空字符串
        if node is None:
            return None, ""

        # 候选源节点列表
        candidates: list[SrcFilesVisionNodeData] = []
        # 如果节点本身就是源文件节点
        if isinstance(node, SrcFilesVisionNodeData):
            candidates.append(node)
        # 如果节点有获取所有上游节点的方法
        if hasattr(node, "get_all_from_node_datas"):
            # 遍历所有上游节点，添加源文件类型的节点
            candidates.extend(
                upstream for upstream in node.get_all_from_node_datas()
                if isinstance(upstream, SrcFilesVisionNodeData)
            )

        # 已处理的节点ID集合（避免重复）
        seen: set[str] = set()
        # 遍历候选源节点
        for source_node in candidates:
            # 如果已处理过，跳过
            if source_node.node_id in seen:
                continue
            # 标记为已处理
            seen.add(source_node.node_id)
            # 获取当前文件路径
            path = getattr(source_node, "src_file_path", "")
            # 获取文件路径列表
            paths = getattr(source_node, "src_file_paths", []) or []
            # 如果没有当前路径，跳过
            if not path:
                continue
            # 构建提示信息
            hint = ""
            if paths:
                try:
                    # 提示：图像源 索引/总数
                    hint = f"图像源 {paths.index(path) + 1}/{len(paths)}"
                except ValueError:
                    hint = f"图像源 1/{len(paths)}"
            return path, hint
        return None, ""

    def _format_file_info(self, path: str | None) -> str:
        """格式化文件信息

        参数：
            path: 文件路径

        返回：
            格式化后的文件信息字符串
        """
        # 如果路径为空或文件不存在，返回空字符串
        if not path or not os.path.exists(path):
            return ""
        try:
            # 获取文件大小
            size = os.path.getsize(path)
            # 获取修改时间
            modified = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
            # 获取文件名
            filename = os.path.basename(path)
            # 格式化文件大小
            if size < 1024 * 1024:
                size_text = f"{size / 1024:.1f} KB"
            else:
                size_text = f"{size / 1024 / 1024:.2f} MB"
            # 返回格式化字符串
            return f"{filename}    |    {size_text}    |    {modified}"
        except OSError:
            # 出错时只返回文件名
            return os.path.basename(path)

    def _on_close_window(self):
        """关闭窗口前保存项目"""
        try:
            # 如果有当前项目，保存项目
            if project_service.current_project:
                self._on_save_project()
        except Exception:
            pass
        # 关闭窗口
        self.close()

    def _on_open_guide(self):
        """打开交互式引导覆盖层"""
        from gui.guide_overlay import GuideOverlay
        # 创建引导覆盖层
        overlay = GuideOverlay(self)
        # 添加引导步骤
        # 步骤1：创建项目
        overlay.add_step("创建项目",
            "点击这里创建一个新的视觉检测项目。\n项目用于组织流程图、图像和设置。",
            widget=find_child_by_tip(self, "新建项目"))
        # 步骤2：节点工具箱
        overlay.add_step("节点工具箱",
            "左侧工具箱列出了所有可用的视觉处理节点。\n拖拽节点到画布上即可开始构建流程图。",
            widget=find_child_by_tip(self, "搜索节点..."))
        # 步骤3：切换主题
        overlay.add_step("切换主题",
            "点击调色板按钮选择颜色主题。\n支持深色、浅色、科技蓝等多种风格。",
            widget=find_child_by_tip(self, "颜色主题"))
        # 步骤4：开始运行
        overlay.add_step("开始运行",
            "构建好流程图后，点击「开始」运行整个流程。\n结果将显示在右侧面板中。",
            widget=find_child_by_tip(self, "开始"))
        # 启动引导
        overlay.start()

    def _on_open_settings(self):
        """打开设置对话框"""
        # 创建设置对话框
        dlg = _SettingsDialog(self)
        # 如果用户确认
        if dlg.exec_() == QDialog.Accepted:
            # 应用设置
            self._apply_settings()
        # 应用主题
        self._apply_theme()
        # 如果有主题切换按钮
        if hasattr(self, '_theme_toggle'):
            # 阻塞信号，避免循环
            self._theme_toggle.blockSignals(True)
            # 设置主题切换按钮状态
            self._theme_toggle.setChecked(theme_manager.is_dark)
            # 恢复信号
            self._theme_toggle.blockSignals(False)

    def _apply_settings(self):
        """将持久化设置应用到UI"""
        import json, os
        # 获取配置文件路径
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app_config.json")
        try:
            # 读取配置文件
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

        # 显示/隐藏主题切换按钮
        if hasattr(self, '_theme_toggle'):
            show = data.get("show_theme_btn", True)
            self._theme_toggle.setVisible(show)

        # 切换画布网格显示
        show_grid = data.get("show_grid", True)
        editors = []
        # 收集所有编辑器
        if self._diagram_editor is not None:
            editors.append(self._diagram_editor)
        for page in self._diagram_pages.values():
            ed = getattr(page, 'editor', None)
            if ed is not None:
                editors.append(ed)
        # 遍历所有编辑器，设置网格显示状态
        for editor in editors:
            s = editor.scene
            if s is not None and hasattr(s, '_show_grid'):
                if s._show_grid != show_grid:
                    s.toggle_grid()

        # 系统托盘
        tray_enabled = data.get("show_tray", True)
        if hasattr(self, '_tray_icon'):
            self._tray_icon.setVisible(tray_enabled)

    def _on_show_theme_dialog(self):
        """打开颜色主题选择器对话框"""
        # 创建主题选择器对话框
        dlg = ThemePickerDialog(self)
        # 如果用户确认
        if dlg.exec_():
            # 应用主题
            self._apply_theme()
        # 如果有主题切换按钮
        if hasattr(self, '_theme_toggle'):
            # 阻塞信号，避免循环
            self._theme_toggle.blockSignals(True)
            # 设置主题切换按钮状态
            self._theme_toggle.setChecked(theme_manager.is_dark)
            # 恢复信号
            self._theme_toggle.blockSignals(False)

    def _on_toggle_theme(self):
        """在暗色和亮色主题之间切换"""
        # 切换主题
        theme_manager.toggle()
        # 应用主题
        self._apply_theme()
        # 如果有主题切换按钮
        if hasattr(self, '_theme_toggle'):
            # 阻塞信号，避免循环
            self._theme_toggle.blockSignals(True)
            # 设置主题切换按钮状态
            self._theme_toggle.setChecked(theme_manager.is_dark)
            # 恢复信号
            self._theme_toggle.blockSignals(False)

    def _reapply_widget_styles(self):
        """重新应用动态QSS到有内联样式的控件"""
        global _CMD_BTN, _TAB_STYLE
        # 更新全局样式
        _CMD_BTN = _cmd_btn_qss()
        _TAB_STYLE = _tab_qss()
        # 获取主题管理器
        tm = theme_manager
        # 主题切换按钮样式
        if hasattr(self, '_theme_toggle'):
            self._theme_toggle.setStyleSheet(_CMD_BTN + f"""
                FontIconToggleButton:checked {{ color: {tm.color('text_primary').name()}; }}
                FontIconToggleButton:checked:hover {{ background: {tm.color('bg_surface_hover').name()}; }}
            """)
        # 图表标签页控件（包含"新项目"、流程图标签页）
        if hasattr(self, '_diagram_tab_widget'):
            self._diagram_tab_widget.setStyleSheet(_TAB_STYLE)
        # 中央标签页（图像 / 模块结果 / 帮助）
        if hasattr(self, '_center_tabs'):
            self._center_tabs.setStyleSheet(_TAB_STYLE)

    def _apply_theme(self):
        """重新应用主题到所有控件"""
        # 获取主题管理器
        tm = theme_manager
        # 获取颜色代理
        c = tm.colors
        # 获取样式表
        qss = tm.get_stylesheet()

        # 1. 全局QSS — 覆盖所有窗口、对话框和标准控件类型
        QApplication.instance().setStyleSheet(qss)

        # 2. 主窗口调色板 + 样式表
        self.setPalette(c.to_palette())
        self.setStyleSheet(qss)

        # 3. 重新应用工具栏按钮（每个按钮在创建时都有自己的QSS）
        self._reapply_widget_styles()
        cmd = _CMD_BTN  # 当前主题的QSS
        # 遍历所有按钮，重新应用样式
        for btn in self.findChildren(QPushButton):
            s = btn.styleSheet()
            if s and 'transparent' in s and 'border-radius' in s:
                btn.setStyleSheet(cmd)

        # 4. 强制重绘所有QWidget子控件
        for child in self.findChildren(QWidget):
            try:
                child.style().unpolish(child)
                child.style().polish(child)
                child.update()
            except Exception:
                pass

        # 5. 图表场景 — 重新应用棋盘格背景画刷
        from PyQt5.QtWidgets import QGraphicsView
        from gui.node_editor.scene import _make_checker_brush
        for view in self.findChildren(QGraphicsView):
            scene = view.scene()
            if scene:
                scene.setBackgroundBrush(_make_checker_brush())
                scene.update()
            view.viewport().update()

        # 6. 图像查看器 — 重新应用信息条背景
        from gui.image_viewer import ImageViewerPanel
        for iv in self.findChildren(ImageViewerPanel):
            if hasattr(iv, '_setup_ui') and hasattr(iv, 'viewer'):
                iv.viewer.viewport().update()

        # 7. 图表标签页头部（标签页栏中的自定义控件）
        for header in self._diagram_headers.values():
            if hasattr(header, '_refresh_qss'):
                header._refresh_qss()

        # 8. 标题栏
        if hasattr(self, '_title_bar'):
            self._title_bar.update()

    def _on_edit_project(self):
        """打开项目设置对话框"""
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            # 如果没有项目，新建项目
            project = project_service.new_project()
        # 创建对话框
        dlg = QDialog(self)
        # 设置窗口标题
        dlg.setWindowTitle("项目属性")
        # 设置最小宽度400
        dlg.setMinimumWidth(400)
        # 设置对话框样式
        dlg.setStyleSheet("QDialog { background: #2d2d30; color: #dcdcdc; }")
        # 创建表单布局
        form = QFormLayout(dlg)

        # 项目名称编辑框
        name_edit = QLineEdit(project.display_name)
        form.addRow("项目名称:", name_edit)

        # 项目描述编辑框
        desc_edit = QLineEdit(getattr(project, 'description', ''))
        form.addRow("描述:", desc_edit)

        # 作者编辑框
        author_edit = QLineEdit(getattr(project, 'author', ''))
        form.addRow("作者:", author_edit)

        # 统计信息标签
        info = QLabel(f"流程图: {len(project.diagrams)} 个\n节点总数: {sum(len(d.workflow.get_all_nodes()) if d.workflow else 0 for d in project.diagrams)}")
        info.setStyleSheet("color: #999; font-size: 11px;")
        form.addRow(info)

        # 按钮框
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        # 如果用户确认
        if dlg.exec_() == dlg.Accepted:
            # 保存旧名称
            old_name = project.name
            # 更新项目属性
            project.name = name_edit.text().strip() or project.name
            project.description = desc_edit.text()
            project.author = author_edit.text()
            # 如果项目有文件路径且名称已更改，更新文件路径
            if project.file_path and project.name != old_name:
                d = os.path.dirname(project.file_path)
                project.file_path = os.path.join(d, f"{project.name}.json")
            # 同步项目标签
            self._sync_proj_labels(project)
            # 记录日志
            self._log_panel.info(f"项目已重命名: {old_name} → {project.name}")

    def _show_notification(self, level: str, title: str, message: str):
        """显示桌面通知

        参数：
            level: 通知级别（Info/Warning/Error/Success）
            title: 通知标题
            message: 通知消息
        """
        from PyQt5.QtWidgets import QSystemTrayIcon
        # 如果系统托盘可用且支持消息
        if QSystemTrayIcon.isSystemTrayAvailable() and QSystemTrayIcon.supportsMessages():
            # 如果没有托盘图标，创建托盘图标
            if not hasattr(self, '_tray_icon'):
                self._tray_icon = QSystemTrayIcon(self)
                # 获取图标路径
                icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "logo.png")
                if os.path.exists(icon_path):
                    self._tray_icon.setIcon(QIcon(icon_path))
                self._tray_icon.show()
            # 消息图标映射
            icon_map = {"Info": 1, "Warning": 2, "Error": 3, "Success": 1}
            # 显示托盘消息
            self._tray_icon.showMessage(title, message, icon_map.get(level, 1), 3000)
        else:
            # 后备方案：在状态栏显示消息
            self._log_panel.info(f"[{level}] {title}: {message}")

    def _on_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 VisionFlow",
            "<h2>VisionFlow 2.0</h2><p>视觉流程编辑器</p>"
            "<p>使用 Python + PyQt5 + OpenCV</p><hr>"
        )
"""主题系统

数据驱动的主题引擎，包含：
  - 5个内置主题（暗色、亮色、默认、科技蓝、紫色）
  - color(key) → QColor 统一访问器（替代硬编码的 QColor）
  - 持久化：保存/加载主题选择到用户配置
  - 向后兼容：colors 属性、get_stylesheet()、to_palette()
  - 可扩展：通过向 theme_data.py 添加条目来增加主题

对齐说明：
  - ThemeOptions.Instance.ColorResource ↔ ThemeManager.current_theme_id
  - ThemeOptions.RefreshTheme()       ↔ ThemeManager._apply()
  - ColorKeys + BrushKeys             ↔ COLOR_KEYS + resolve_colors()
  - ResourceDictionary swap           ↔ _active_colors dict replace
  - Persistence                       ↔ JSON save/load
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import Qt, pyqtSignal, QObject

from gui.theme_data import (
    THEMES, COLOR_KEYS, ThemeDef, resolve_colors, get_theme_ids, get_theme_by_id,
)


# 配置路径 — 保存在应用旁边或用户主目录
def _config_path() -> str:
    """获取主题配置文件路径"""
    # 候选路径列表
    candidates = [
        Path(__file__).parent.parent / "theme_config.json",   # 项目根目录
        Path.home() / ".visionflow_theme.json",               # 用户主目录
    ]
    # 遍历候选路径
    for p in candidates:
        try:
            # 创建父目录（如果不存在）
            p.parent.mkdir(parents=True, exist_ok=True)
            # 返回路径字符串
            return str(p)
        except Exception:
            continue
    # 默认返回第一个候选路径
    return str(candidates[0])


# ═══════════════════════════════════════════════════════════════════════════
# 旧版样式颜色对象 — 与现有代码向后兼容
# ═══════════════════════════════════════════════════════════════════════════

class _ThemeColorsProxy:
    """向后兼容的属性访问包装器，包装活动颜色映射。

    现有代码如 `theme_manager.colors.node_bg` 继续工作。
    新代码应优先使用 `theme_manager.color("node_bg")`。
    """

    def __init__(self, manager: "ThemeManager"):
        """初始化颜色代理

        参数：
            manager: 主题管理器对象
        """
        # 保存主题管理器引用
        self._manager = manager

    def __getattr__(self, name: str):
        """获取属性

        参数：
            name: 属性名

        返回：
            QColor对象
        """
        # 将旧版属性名映射到颜色键ID
        key = _LEGACY_TO_KEY.get(name, name)
        # 获取颜色值
        val = self._manager._active_colors.get(key)
        # 如果没有找到，返回空QColor
        if val is None:
            return QColor()
        # 返回QColor对象
        return QColor(val)

    def __dir__(self):
        """返回属性列表"""
        return list(COLOR_KEYS.keys())

    # ── 调色板 + 样式表（从旧版ThemeColors委托）──────────

    def to_palette(self) -> QPalette:
        """转换为QPalette

        返回：
            QPalette对象
        """
        return _build_palette(self)

    @property
    def stylesheet(self) -> str:
        """获取样式表字符串

        返回：
            样式表字符串
        """
        return _build_stylesheet(self)


# 旧版属性名 → 新ColorKey ID映射
_LEGACY_TO_KEY = {
    "window_bg":         "bg_window",          # 窗口背景
    "title_bar_bg":      "bg_title_bar",       # 标题栏背景
    "title_bar_text":    "text_title",         # 标题栏文字
    "surface":           "bg_surface",         # 表面背景
    "surface_raised":    "bg_surface_raised",  # 凸起表面背景
    "surface_hover":     "bg_surface_hover",   # 悬停表面背景
    "surface_input":     "bg_surface_input",   # 输入框表面背景
    "surface_deep":      "bg_surface_deep",    # 深层表面背景
    "status_ok":         "status_ok",          # 状态正常颜色
    "status_error":      "status_error",       # 状态错误颜色
    "status_running":    "status_running",     # 状态运行中颜色
    "status_idle":       "status_idle",        # 状态空闲颜色
    "port_input":        "port_input",         # 输入端口颜色
    "port_output":       "port_output",        # 输出端口颜色
    "link":              "edge",               # 连线颜色
    "link_selected":     "edge_selected",      # 选中连线颜色
    "checker_base":      "canvas_checker_base", # 画布棋盘格基础色
    "checker_alt":       "canvas_checker_alt",  # 画布棋盘格交替色
    "canvas_bg":         "canvas_bg",          # 画布背景
    "node_bg":           "node_bg",            # 节点背景
    "node_bg_hover":     "node_bg_hover",      # 节点悬停背景
    "node_bg_selected":  "node_bg_selected",   # 节点选中背景
    "node_border":       "node_border",        # 节点边框
    "node_border_selected": "node_border_selected", # 节点选中边框
    "node_text":         "node_text",          # 节点文字
    "node_flag_default": "gray",               # 节点默认标志颜色
    "node_shadow":       "node_shadow",        # 节点阴影
    "scroll_bg":         "scroll_bg",          # 滚动条背景
    "scroll_handle":     "scroll_handle",      # 滚动条手柄
    "scroll_handle_hover": "scroll_handle_hover", # 滚动条手柄悬停
}


# ═══════════════════════════════════════════════════════════════════════════
# 调色板构建器 — 独立于代理类
# ═══════════════════════════════════════════════════════════════════════════

def _build_palette(colors) -> QPalette:
    """从解析的颜色构建 QPalette

    参数：
        colors: 颜色代理对象

    返回：
        QPalette对象
    """
    # 创建QPalette对象
    p = QPalette()
    # 设置窗口颜色
    p.setColor(QPalette.Window, QColor(colors.surface))
    # 设置窗口文字颜色
    p.setColor(QPalette.WindowText, QColor(colors.text_primary))
    # 设置基础颜色
    p.setColor(QPalette.Base, QColor(colors.surface_deep))
    # 设置交替基础颜色
    p.setColor(QPalette.AlternateBase, QColor(colors.surface))
    # 设置工具提示基础颜色（根据表面深度亮度选择）
    if colors.surface_deep.lightness() < 128:
        p.setColor(QPalette.ToolTipBase, QColor(60, 60, 60))
    else:
        p.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
    # 设置工具提示文字颜色
    p.setColor(QPalette.ToolTipText, QColor(colors.text_primary))
    # 设置文字颜色
    p.setColor(QPalette.Text, QColor(colors.text_primary))
    # 设置按钮颜色
    p.setColor(QPalette.Button, QColor(colors.surface))
    # 设置按钮文字颜色
    p.setColor(QPalette.ButtonText, QColor(colors.text_primary))
    # 设置链接颜色
    p.setColor(QPalette.Link, QColor(colors.accent))
    # 设置高亮颜色
    p.setColor(QPalette.Highlight, QColor(colors.accent))
    # 设置高亮文字颜色
    p.setColor(QPalette.HighlightedText, QColor(colors.accent_text))
    # 设置禁用状态的文字颜色
    p.setColor(QPalette.Disabled, QPalette.Text, QColor(128, 128, 128))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(128, 128, 128))
    # 返回调色板
    return p


def _build_stylesheet(colors) -> str:
    """覆盖所有控件类的全面QSS

    通过 QApplication.setStyleSheet() 应用以获得最大覆盖率。
    使用ID选择器（如 QFrame#panel_bg）进行面板覆盖。

    参数：
        colors: 颜色代理对象

    返回：
        样式表字符串
    """
    # 创建颜色快捷方式
    c = colors
    # 返回样式表字符串
    return f"""
        /* ── 全局默认值 ── */
        QWidget {{ background: {c.bg_surface.name()}; color: {c.text_primary.name()}; }}
        QMainWindow {{ background: {c.bg_surface_deep.name()}; }}
        QMainWindow::separator {{ background: {c.border.name()}; width: 1px; height: 1px; }}

        /* ── 工具提示 ── */
        QToolTip {{ color: {c.text_primary.name()}; background: {c.bg_surface_input.name()}; border: 1px solid {c.border.name()}; padding: 4px; }}

        /* ── 菜单 ── */
        QMenuBar {{ background: {c.bg_surface.name()}; color: {c.text_primary.name()}; }}
        QMenuBar::item:selected {{ background: {c.bg_surface_hover.name()}; }}
        QMenu {{ background: {c.bg_surface.name()}; color: {c.text_primary.name()}; border: 1px solid {c.border.name()}; }}
        QMenu::item:selected {{ background: {c.accent.name()}; color: {c.accent_text.name()}; }}
        QMenu::separator {{ height: 1px; background: {c.border.name()}; margin: 4px 10px; }}

        /* ── 状态栏 ── */
        QStatusBar {{ background: #007acc; color: white; }}

        /* ── 滚动条 ── */
        QScrollBar:vertical {{ background: {c.scroll_bg.name()}; width: 10px; }}
        QScrollBar::handle:vertical {{ background: {c.scroll_handle.name()}; min-height: 20px; border-radius: 5px; }}
        QScrollBar::handle:vertical:hover {{ background: {c.scroll_handle_hover.name()}; }}
        QScrollBar:horizontal {{ background: {c.scroll_bg.name()}; height: 10px; }}
        QScrollBar::handle:horizontal {{ background: {c.scroll_handle.name()}; min-width: 20px; border-radius: 5px; }}
        QScrollBar::handle:horizontal:hover {{ background: {c.scroll_handle_hover.name()}; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}

        /* ── 树/列表 ── */
        QTreeWidget, QTreeView, QListView, QListWidget {{ background: {c.bg_surface.name()}; color: {c.text_primary.name()}; border: none; outline: none; }}
        QTreeWidget::item:hover, QTreeView::item:hover, QListView::item:hover, QListWidget::item:hover {{ background: {c.bg_surface_hover.name()}; }}
        QTreeWidget::item:selected, QTreeView::item:selected, QListWidget::item:selected {{ background: #094771; color: white; }}

        /* ── 分割器 ── */
        QSplitter::handle {{ background: {c.border.name()}; }}

        /* ── 标签页 ── */
        QTabWidget::pane {{ border: 1px solid {c.border.name()}; background: {c.bg_surface.name()}; }}
        QTabBar::tab {{ background: {c.bg_surface_raised.name()}; color: {c.text_primary.name()}; padding: 6px 12px; border-bottom: 2px solid transparent; }}
        QTabBar::tab:selected {{ background: {c.bg_surface.name()}; border-bottom: 2px solid {c.accent.name()}; }}
        QTabBar::tab:hover {{ background: {c.bg_surface_hover.name()}; }}

        /* ── 表格 ── */
        QTableView, QTableWidget {{ background: {c.bg_surface.name()}; color: {c.text_primary.name()}; border: 1px solid {c.border.name()}; gridline-color: {c.border.name()}; selection-background-color: #094771; }}
        QHeaderView::section {{ background: {c.bg_surface_raised.name()}; color: {c.text_primary.name()}; padding: 4px 8px; border: none; border-right: 1px solid {c.border.name()}; border-bottom: 1px solid {c.border.name()}; }}

        /* ── 输入框 ── */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{ background: {c.bg_surface_input.name()}; color: {c.text_primary.name()}; border: 1px solid {c.border.name()}; padding: 4px 8px; border-radius: 3px; selection-background-color: {c.accent.name()}; }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border-color: {c.accent.name()}; }}
        QComboBox QAbstractItemView {{ background: {c.bg_surface.name()}; color: {c.text_primary.name()}; selection-background-color: {c.accent.name()}; }}
        QComboBox::drop-down {{ border: none; }}

        /* ── 按钮 ── */
        QPushButton {{ background: {c.accent.name()}; color: {c.accent_text.name()}; border: none; padding: 6px 16px; border-radius: 3px; }}
        QPushButton:hover {{ background: #1a8ad4; }}
        QPushButton:pressed {{ background: #005a9e; }}
        QPushButton:disabled {{ background: {c.border.name()}; color: {c.text_disabled.name()}; }}
        QToolButton {{ background: transparent; border: none; color: {c.text_primary.name()}; }}
        QToolButton:hover {{ background: {c.bg_surface_hover.name()}; }}

        /* ── 复选框/单选按钮 ── */
        QCheckBox, QRadioButton {{ color: {c.text_primary.name()}; }}

        /* ── 标签 ── */
        QLabel {{ color: {c.text_primary.name()}; }}

        /* ── 分组框 ── */
        QGroupBox {{ color: {c.text_primary.name()}; border: 1px solid {c.border.name()}; margin-top: 12px; padding-top: 16px; font-weight: bold; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 6px; }}

        /* ── 框架/分隔线 ── */
        QFrame[frameShape=\"4\"] {{ color: {c.border.name()}; }}  /* HLine 水平线 */
        QFrame[frameShape=\"5\"] {{ color: {c.border.name()}; }}  /* VLine 垂直线 */

        /* ── 对话框 ── */
        QDialog {{ background: {c.bg_surface.name()}; }}
    """


# ═══════════════════════════════════════════════════════════════════════════
# 主题管理器
# ═══════════════════════════════════════════════════════════════════════════

class ThemeManager(QObject):
    """中央主题服务 — ThemeOptions + ILoadThemeOptionsService

    管理活动主题，提供颜色访问，并持久化选择。

    用法：
        # 统一访问器（新代码推荐使用）
        accent = theme_manager.color("accent")

        # 向后兼容的属性访问
        accent = theme_manager.colors.accent

        # 切换主题
        theme_manager.set_theme("light")
        theme_manager.set_theme("technology_blue")
        theme_manager.toggle_dark()    # 在暗色/亮色之间切换

        # 列出可用主题供UI使用
        for t in theme_manager.available_themes:
            print(t.id, t.name, t.group)
    """

    # 主题变化信号，携带新的主题ID
    theme_changed = pyqtSignal(str)

    def __init__(self):
        """初始化主题管理器"""
        # 调用父类QObject的构造函数
        super().__init__()
        # 活动主题ID，默认为"dark"
        self._theme_id: str = "dark"
        # 解析后的颜色字典，键为颜色键，值为十六进制颜色值
        self._active_colors: dict[str, str] = {}
        # 活动主题定义对象
        self._theme_def: ThemeDef | None = None
        # 向后兼容的颜色代理对象
        self.colors = _ThemeColorsProxy(self)

        # 加载持久化的主题选择，如果失败则回退到暗色主题
        loaded = self._load()
        # 如果加载成功且主题存在
        if loaded and loaded in THEMES:
            # 设置主题ID
            self._theme_id = loaded
        # 应用主题
        self._apply()

    # ── 公共API ──────────────────────────────────────────────────────

    def color(self, key: str) -> QColor:
        """统一颜色访问器 — {DynamicResource BrushKeys.Xxx}

        所有GUI代码应使用此方法而不是硬编码 QColor("#...")。
        如果键未知，返回黑色（安全回退）。

        参数：
            key: 颜色键名

        返回：
            QColor对象
        """
        # 获取十六进制颜色值
        hex_val = self._active_colors.get(key)
        # 如果未找到，返回黑色
        if hex_val is None:
            return QColor(0, 0, 0)
        # 返回QColor对象
        return QColor(hex_val)

    def set_theme(self, theme_id: str):
        """切换到不同的主题 — ThemeOptions.ColorResource 设置器

        参数：
            theme_id: 主题ID
        """
        # 如果主题ID相同，返回
        if theme_id == self._theme_id:
            return
        # 如果主题ID不存在于主题字典中，返回
        if theme_id not in THEMES:
            return
        # 保存主题ID
        self._theme_id = theme_id
        # 应用主题
        self._apply()
        # 保存主题选择
        self._save()

    def toggle_dark(self):
        """在暗色/亮色之间切换 — ThemeOptions.SwitchDark()"""
        # 获取当前主题
        current = THEMES.get(self._theme_id)
        # 如果当前主题不存在
        if current is None:
            # 设置主题为暗色
            self.set_theme("dark")
            return
        # 目标是否为暗色（与当前相反）
        target_is_dark = not current.is_dark
        # 首先在"强力推荐"分组中查找目标亮暗模式的主题
        for tid, tdef in THEMES.items():
            if tdef.is_dark == target_is_dark and tdef.group == "强力推荐":
                self.set_theme(tid)
                return
        # 如果没找到，在所有主题中查找
        for tid, tdef in THEMES.items():
            if tdef.is_dark == target_is_dark:
                self.set_theme(tid)
                return

    def toggle(self):
        """向后兼容的别名，调用 toggle_dark()"""
        self.toggle_dark()

    @property
    def current_theme_id(self) -> str:
        """获取当前主题ID"""
        return self._theme_id

    @property
    def current_theme_name(self) -> str:
        """获取当前主题名称"""
        # 获取主题定义
        t = THEMES.get(self._theme_id)
        # 返回名称或ID
        return t.name if t else self._theme_id

    @property
    def is_dark(self) -> bool:
        """是否为暗色主题"""
        # 获取主题定义
        t = THEMES.get(self._theme_id)
        # 返回暗色标志，默认为True
        return t.is_dark if t else True

    @property
    def available_themes(self) -> list[ThemeDef]:
        """所有已注册的主题，按显示顺序排列 — ThemeOptions.ColorResources"""
        # 按order排序后返回
        return sorted(THEMES.values(), key=lambda t: t.order)

    def get_stylesheet(self) -> str:
        """当前主题的QSS样式表（向后兼容）

        返回：
            样式表字符串
        """
        # 返回颜色代理的样式表
        return self.colors.stylesheet

    # ── 内部方法 ────────────────────────────────────────────────────────

    def _apply(self):
        """解析当前主题的颜色并通知 — RefreshTheme()"""
        # 获取主题定义
        tdef = THEMES.get(self._theme_id)
        # 如果主题定义不存在
        if tdef is None:
            # 使用暗色主题
            tdef = THEMES["dark"]
            # 设置主题ID为暗色
            self._theme_id = "dark"
        # 保存主题定义
        self._theme_def = tdef
        # 解析颜色
        self._active_colors = resolve_colors(tdef)
        # 发出主题变化信号
        self.theme_changed.emit(self._theme_id)

    def _save(self):
        """将主题选择持久化到JSON — PF ThemeOptions.Save()"""
        try:
            # 创建数据字典
            data = {"theme": self._theme_id}
            # 写入配置文件
            with open(_config_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            # 非关键错误 — 如果无法写入配置，不崩溃
            pass

    def _load(self) -> str | None:
        """加载持久化的主题选择 — ThemeOptions.Load()

        返回：
            主题ID或None
        """
        # 遍历候选路径
        for path in [
            Path(__file__).parent.parent / "theme_config.json",   # 项目根目录
            Path.home() / ".visionflow_theme.json",               # 用户主目录
        ]:
            try:
                # 打开文件
                with open(path, "r", encoding="utf-8") as f:
                    # 解析JSON
                    data = json.load(f)
                    # 获取主题ID
                    theme_id = data.get("theme", "")
                    # 如果主题存在，返回主题ID
                    if theme_id in THEMES:
                        return theme_id
            except Exception:
                # 继续尝试下一个路径
                continue
        return None


# 全局单例 — ThemeOptions.Instance
theme_manager = ThemeManager()


# ═══════════════════════════════════════════════════════════════════════════
# 主题感知辅助函数 — QWidget面板的DynamicResource模式
# ═══════════════════════════════════════════════════════════════════════════

def connect_theme(refresh_fn):
    """注册每次主题变化时运行的回调，并立即运行一次

    在任何面板的 __init__ 中使用：
        connect_theme(self._refresh_qss)

    相当于 {DynamicResource BrushKeys.Xxx} 自动刷新。

    参数：
        refresh_fn: 刷新函数
    """
    # 立即执行一次刷新函数
    refresh_fn()
    # 连接主题变化信号，主题变化时再次执行刷新函数
    theme_manager.theme_changed.connect(lambda _: refresh_fn())


# ═══════════════════════════════════════════════════════════════════════════
# 主题选择对话框
# ═══════════════════════════════════════════════════════════════════════════

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QGroupBox, QScrollArea, QWidget,
                               QGridLayout, QFrame)
from PyQt5.QtCore import Qt as QtCore_Qt

class ThemePickerDialog(QDialog):
    """颜色主题选择器

    布局：分组框 + 卡片网格（类似WrapPanel）。
    每个卡片 = 250x150 QFrame，使用主题自身颜色渲染。
    点击卡片 → 立即预览（SelectionChanged → RefreshThemeCommand）。
    确定 = 保留，取消 = 恢复到原始。
    """

    # 卡片宽度（像素）
    CARD_W = 250
    # 卡片高度（像素）
    CARD_H = 150
    # 每行列数
    COLS = 2

    def __init__(self, parent=None):
        """初始化主题选择对话框

        参数：
            parent: 父对象
        """
        # 调用父类QDialog的构造函数
        super().__init__(parent)
        # 设置窗口标题
        self.setWindowTitle("颜色主题")
        # 设置最小尺寸580x480
        self.setMinimumSize(580, 480)
        # 保存原始主题ID
        self._original_theme = theme_manager.current_theme_id
        # 当前选中的主题ID
        self._selected_id: str | None = None
        # 卡片字典，键为主题ID，值为卡片控件
        self._cards: dict[str, QFrame] = {}
        # 设置UI
        self._setup_ui()

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局间距为10
        layout.setSpacing(10)

        # 创建滚动区域
        scroll = QScrollArea()
        # 设置控件可调整大小
        scroll.setWidgetResizable(True)
        # 设置无边框
        scroll.setFrameShape(QScrollArea.NoFrame)
        # 创建容器
        container = QWidget()
        # 创建垂直布局
        container_layout = QVBoxLayout(container)
        # 设置布局间距为14
        container_layout.setSpacing(14)

        # 按分组名称分组
        groups: dict[str, list] = {}
        # 遍历所有可用主题
        for t in theme_manager.available_themes:
            # 按分组添加到字典
            groups.setdefault(t.group, []).append(t)

        # 按顺序创建分组
        for group_name in ["强力推荐", "纯色", "外部主题", "自定义"]:
            # 如果分组不存在，跳过
            if group_name not in groups:
                continue
            # 创建分组框
            group_box = QGroupBox(group_name)
            # 设置分组框样式
            group_box.setStyleSheet(f"""
                QGroupBox {{ font-weight: bold; border: 1px solid {theme_manager.color('border').name()};
                             margin-top: 14px; padding-top: 18px; }}
                QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; }}
            """)
            # 创建网格布局
            grid = QGridLayout()
            # 设置网格间距为10
            grid.setSpacing(10)
            # 遍历分组中的主题
            for i, tdef in enumerate(groups[group_name]):
                # 创建卡片
                card = self._make_card(tdef)
                # 添加到网格布局（行 = i // COLS，列 = i % COLS）
                grid.addWidget(card, i // self.COLS, i % self.COLS)
            # 设置分组框布局
            group_box.setLayout(grid)
            # 添加到容器布局
            container_layout.addWidget(group_box)

        # 添加弹性空间
        container_layout.addStretch()
        # 设置滚动区域控件
        scroll.setWidget(container)
        # 添加到主布局，拉伸因子为1
        layout.addWidget(scroll, 1)

        # 底部按钮行
        btn_row = QHBoxLayout()
        # 添加弹性空间
        btn_row.addStretch()
        # 取消按钮
        cancel_btn = QPushButton("取消")
        # 连接点击信号
        cancel_btn.clicked.connect(self._on_cancel)
        # 添加到按钮行
        btn_row.addWidget(cancel_btn)
        # 确定按钮
        ok_btn = QPushButton("确定")
        # 设置为默认按钮（按回车时触发）
        ok_btn.setDefault(True)
        # 连接点击信号
        ok_btn.clicked.connect(self._on_accept)
        # 添加到按钮行
        btn_row.addWidget(ok_btn)
        # 添加按钮行到布局
        layout.addLayout(btn_row)

        # 高亮当前活动主题的卡片
        self._update_card_highlights()

    # ── 卡片工厂（ItemTemplate 250×150 边框）──────────────────

    def _make_card(self, tdef) -> QFrame:
        """构建250x150的预览卡片，使用主题自身的颜色渲染

        参数：
            tdef: 主题定义

        返回：
            卡片控件
        """
        from gui.theme_data import resolve_colors
        # 解析主题的颜色映射
        c = resolve_colors(tdef)

        # 创建卡片框架
        card = QFrame()
        # 设置固定大小
        card.setFixedSize(self.CARD_W, self.CARD_H)
        # 设置光标为手指形状
        card.setCursor(QtCore_Qt.PointingHandCursor)
        # 设置工具提示
        card.setToolTip(f"{tdef.name} — {tdef.description}")

        # 设置卡片样式
        card.setStyleSheet(f"""
            QFrame {{
                background: {c.get('bg_surface', '#333')};
                border: 1px solid {c.get('border', '#555')};
                border-radius: 6px;
            }}
        """)

        # 点击卡片 → 选择 + 立即应用
        # 重写mousePressEvent方法
        card.mousePressEvent = lambda e, tid=tdef.id: self._select(tid)
        # 保存到卡片字典
        self._cards[tdef.id] = card

        # 创建内部垂直布局
        inner = QVBoxLayout(card)
        # 设置布局边距
        inner.setContentsMargins(10, 10, 10, 10)
        # 设置布局间距为4
        inner.setSpacing(4)

        # 第1行：【提示文本】（前景标题）
        prompt = tdef.prompt or tdef.name
        p_lbl = QLabel(f"【{prompt}】")
        p_lbl.setAlignment(QtCore_Qt.AlignCenter)
        p_lbl.setStyleSheet(f"color: {c.get('text_title', c.get('text_primary','#ccc'))}; "
                            f"font-weight: bold; font-size: 12px; border: none; background: transparent;")
        inner.addWidget(p_lbl)

        # 第2行：名称（前景色）
        n_lbl = QLabel(tdef.name)
        n_lbl.setAlignment(QtCore_Qt.AlignCenter)
        n_lbl.setStyleSheet(f"color: {c.get('text_primary', '#ccc')}; font-size: 11px; "
                            f"border: none; background: transparent;")
        inner.addWidget(n_lbl)

        # 第3行：描述（前景辅助色，换行 + 省略号）
        desc = tdef.description or f"{'深色' if tdef.is_dark else '浅色'}主题"
        d_lbl = QLabel(desc)
        d_lbl.setAlignment(QtCore_Qt.AlignCenter)
        d_lbl.setWordWrap(True)
        d_lbl.setStyleSheet(f"color: {c.get('text_secondary', '#999')}; font-size: 9px; "
                            f"border: none; background: transparent;")
        inner.addWidget(d_lbl)

        # 添加弹性空间
        inner.addStretch()

        # 第4行："默认按钮"（标题背景 / 标题前景）
        btn = QPushButton("默认按钮")
        btn.setEnabled(False)   # 仅显示，不可交互
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {c.get('bg_caption', c.get('bg_surface_raised','#444'))};
                color: {c.get('text_caption', c.get('text_primary','#ccc'))};
                border: 1px solid {c.get('border', '#555')};
                border-radius: 3px; padding: 3px 12px; font-size: 10px;
            }}
        """)
        inner.addWidget(btn)

        # 返回卡片
        return card

    # ── 选择（SelectionChanged → RefreshThemeCommand）──────────

    def _select(self, theme_id: str):
        """点击时立即应用 — TwoWay SelectedItem 绑定

        参数：
            theme_id: 主题ID
        """
        # 设置主题
        theme_manager.set_theme(theme_id)
        # 保存选中的主题ID
        self._selected_id = theme_id
        # 更新卡片高亮
        self._update_card_highlights()

    def _update_card_highlights(self):
        """更新卡片边框：选中的卡片使用强调色边框，其他使用正常边框"""
        # 获取当前主题ID
        current = theme_manager.current_theme_id
        # 遍历所有卡片
        for tid, card in self._cards.items():
            # 查找主题定义
            tdef = next((t for t in theme_manager.available_themes if t.id == tid), None)
            # 如果主题定义不存在，跳过
            if tdef is None:
                continue
            from gui.theme_data import resolve_colors
            # 解析主题颜色
            c = resolve_colors(tdef)
            # 如果是当前主题，边框使用强调色，否则使用边框色
            border = c.get('accent', '#3399FF') if tid == current else c.get('border', '#555')
            # 如果是当前主题，线宽为3，否则为1
            width = 3 if tid == current else 1
            # 设置卡片样式
            card.setStyleSheet(f"""
                QFrame {{ background: {c.get('bg_surface', '#333')};
                         border: {width}px solid {border}; border-radius: 6px; }}
            """)

    # ── 确定 / 取消 ──────────────────────────────────────────────────

    def _on_accept(self):
        """确定按钮点击处理"""
        self.accept()

    def _on_cancel(self):
        """取消按钮点击处理"""
        # 如果当前主题与原始主题不同
        if self._original_theme != theme_manager.current_theme_id:
            # 恢复原始主题
            theme_manager.set_theme(self._original_theme)
        # 拒绝对话框
        self.reject()

    def exec_(self) -> int:
        """执行对话框

        返回：
            对话框结果
        """
        # 执行父类的exec_方法
        result = super().exec_()
        # 如果结果不是接受
        if result != QDialog.Accepted:
            # 调用取消处理
            self._on_cancel()
        # 返回是否有选中的主题或对话框接受
        return bool(self._selected_id) or (result == QDialog.Accepted)
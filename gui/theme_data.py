"""颜色主题数据

纯数据层：对 Qt 或其他 GUI 模块零依赖。
定义哪些颜色存在以及每个主题将它们设置为什么值。
ThemeManager 在 theme.py 中加载这些数据 — 数据与逻辑的清晰分离。

架构
  ColorKey    — 一个具有暗色/亮色默认值的命名颜色槽
  ThemeDef    — 包含键→十六进制值覆盖字典的命名主题
  COLOR_KEYS  — 所有45个颜色键的注册表
  THEMES      — 所有主题定义的注册表
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════════════
# ColorKey（颜色键）
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ColorKey:
    """一个具有暗色/亮色默认值的命名颜色令牌

    每个键包含：
      - id: 唯一标识符，例如 "accent"、"foreground"
      - name: 中文显示名称
      - group: 用于UI组织的分类（前景/背景/边框/强调/状态/画布/节点/端口/滚动条）
      - dark_default: 当没有主题覆盖时的回退十六进制值（暗色模式）
      - light_default: 当没有主题覆盖时的回退十六进制值（亮色模式）
    """
    id: str                        # 唯一标识符
    name: str = ""                 # 中文显示名称
    group: str = ""                # 分类
    dark_default: str = "#000000"  # 暗色模式默认值
    light_default: str = "#FFFFFF" # 亮色模式默认值

    def default_for(self, is_dark: bool) -> str:
        """根据是否为暗色模式返回默认值

        参数：
            is_dark: 是否为暗色模式

        返回：
            十六进制颜色字符串
        """
        # 如果是暗色模式返回dark_default，否则返回light_default
        return self.dark_default if is_dark else self.light_default


# ═══════════════════════════════════════════════════════════════════════════
# ThemeDef（主题定义）
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ThemeDef:
    """一个命名的颜色主题

    每个主题：
      - id: 唯一标识符
      - name: 显示名称
      - group: 分类
      - is_dark: True = 暗色背景
      - prompt: 在【】中显示的简短提示
      - description: 更长的描述
      - colors: 颜色键ID → 十六进制值的字典
      - order: 排序顺序
    """
    id: str                                      # 唯一标识符
    name: str                                    # 显示名称
    group: str = "纯色"                          # 分类
    is_dark: bool = True                         # 是否为暗色模式
    prompt: str = ""                             # 简短提示
    description: str = ""                        # 描述
    colors: dict[str, str] = field(default_factory=dict)  # 颜色覆盖字典
    order: int = 0                               # 排序顺序


# ═══════════════════════════════════════════════════════════════════════════
# COLOR_KEYS — 45个颜色令牌
# ═══════════════════════════════════════════════════════════════════════════

# 颜色键字典
COLOR_KEYS: dict[str, ColorKey] = {
    # ── 强调色 / 强调 ──
    "accent":              ColorKey("accent", "强调色", "强调",
                                    dark_default="#2D80FF", light_default="#FF3399FF"),
    "accent_text":         ColorKey("accent_text", "强调文字", "强调",
                                    dark_default="#FFFFFF", light_default="#FFFFFF"),

    # ── 前景文字 / 前景 ──
    "text_primary":        ColorKey("text_primary", "主文字", "前景",
                                    dark_default="#FF8F939C", light_default="#606266"),
    "text_secondary":      ColorKey("text_secondary", "次文字", "前景",
                                    dark_default="#909399", light_default="#909399"),
    "text_disabled":       ColorKey("text_disabled", "禁用文字", "前景",
                                    dark_default="#656565", light_default="#C0C0C0"),
    "text_title":          ColorKey("text_title", "标题文字", "前景",
                                    dark_default="#FFFFFF", light_default="#000000"),
    "text_link":           ColorKey("text_link", "链接文字", "前景",
                                    dark_default="#6296D8", light_default="#6296D8"),
    "text_caption":        ColorKey("text_caption", "标题栏文字", "前景",
                                    dark_default="#8F939C", light_default="#606266"),

    # ── 背景 / 背景 ──
    "bg_window":           ColorKey("bg_window", "窗口背景", "背景",
                                    dark_default="#2D2D30", light_default="#F5F5F5"),
    "bg_surface":          ColorKey("bg_surface", "表面", "背景",
                                    dark_default="#252526", light_default="#FFFFFF"),
    "bg_surface_raised":   ColorKey("bg_surface_raised", "凸起表面", "背景",
                                    dark_default="#343437", light_default="#F5F5F5"),
    "bg_surface_hover":    ColorKey("bg_surface_hover", "悬停表面", "背景",
                                    dark_default="#3E3E42", light_default="#E8E8E8"),
    "bg_surface_input":    ColorKey("bg_surface_input", "输入框背景", "背景",
                                    dark_default="#333337", light_default="#FFFFFF"),
    "bg_surface_deep":     ColorKey("bg_surface_deep", "深层背景", "背景",
                                    dark_default="#1E1E1E", light_default="#F0F0F0"),
    "bg_title_bar":        ColorKey("bg_title_bar", "标题栏背景", "背景",
                                    dark_default="#1E1E1E", light_default="#FFFFFF"),
    "bg_caption":          ColorKey("bg_caption", "标题栏底", "背景",
                                    dark_default="#191A20", light_default="#F5F5F5"),
    "bg_alternating":      ColorKey("bg_alternating", "交替行背景", "背景",
                                    dark_default="#191A20", light_default="#FAFAFA"),
    "bg_menu":             ColorKey("bg_menu", "菜单背景", "背景",
                                    dark_default="#191A20", light_default="#FFFFFF"),

    # ── 边框 / 边框 ──
    "border":              ColorKey("border", "边框", "边框",
                                    dark_default="#3F3F46", light_default="#E0E0E0"),
    "border_focus":        ColorKey("border_focus", "焦点边框", "边框",
                                    dark_default="#0078D4", light_default="#0078D4"),
    "border_title":        ColorKey("border_title", "标题边框", "边框",
                                    dark_default="#363844", light_default="#E2E2E2"),
    "border_assist":       ColorKey("border_assist", "辅助边框", "边框",
                                    dark_default="#272932", light_default="#F0F0F0"),

    # ── 状态色 / 状态 ──
    "status_ok":           ColorKey("status_ok", "成功", "状态",
                                    dark_default="#67C23A", light_default="#67C23A"),
    "status_error":        ColorKey("status_error", "错误", "状态",
                                    dark_default="#DC000C", light_default="#DC000C"),
    "status_warning":      ColorKey("status_warning", "警告", "状态",
                                    dark_default="#FFC107", light_default="#E6A23C"),
    "status_running":      ColorKey("status_running", "运行中", "状态",
                                    dark_default="#3399FF", light_default="#3399FF"),
    "status_idle":         ColorKey("status_idle", "空闲", "状态",
                                    dark_default="#909399", light_default="#909399"),
    "status_disabled":     ColorKey("status_disabled", "禁用", "状态",
                                    dark_default="#555555", light_default="#C0C0C0"),

    # ── 具名颜色 / 具名色 ──
    "green":               ColorKey("green", "绿色", "具名色",
                                    dark_default="#67C23A", light_default="#67C23A"),
    "red":                 ColorKey("red", "红色", "具名色",
                                    dark_default="#DC000C", light_default="#DC000C"),
    "orange":              ColorKey("orange", "橙色", "具名色",
                                    dark_default="#FFC107", light_default="#E6A23C"),
    "yellow":              ColorKey("yellow", "黄色", "具名色",
                                    dark_default="#FFEE33", light_default="#FFEE33"),
    "blue":                ColorKey("blue", "蓝色", "具名色",
                                    dark_default="#2196F3", light_default="#2196F3"),
    "purple":              ColorKey("purple", "紫色", "具名色",
                                    dark_default="#9C27B0", light_default="#9C27B0"),
    "pink":                ColorKey("pink", "粉色", "具名色",
                                    dark_default="#E91E63", light_default="#E91E63"),
    "gray":                ColorKey("gray", "灰色", "具名色",
                                    dark_default="#909399", light_default="#909399"),

    # ── 画布 / 画布 ──
    "canvas_bg":           ColorKey("canvas_bg", "画布背景", "画布",
                                    dark_default="#121317", light_default="#FFFFFF"),
    "canvas_checker_base": ColorKey("canvas_checker_base", "棋盘格基底", "画布",
                                    dark_default="#121317", light_default="#FFFFFF"),
    "canvas_checker_alt":  ColorKey("canvas_checker_alt", "棋盘格交替", "画布",
                                    dark_default="#191A20", light_default="#C0C0C0"),
    "canvas_grid":         ColorKey("canvas_grid", "网格线", "画布",
                                    dark_default="#2E313B", light_default="#E8E8E8"),

    # ── 节点 / 节点 ──
    "node_bg":             ColorKey("node_bg", "节点背景", "节点",
                                    dark_default="#3C3C3C", light_default="#FFFFFF"),
    "node_bg_hover":       ColorKey("node_bg_hover", "节点悬停", "节点",
                                    dark_default="#4A4A4A", light_default="#F5F5F5"),
    "node_bg_selected":    ColorKey("node_bg_selected", "节点选中", "节点",
                                    dark_default="#4A4A4A", light_default="#EBEBEB"),
    "node_border":         ColorKey("node_border", "节点边框", "节点",
                                    dark_default="#555555", light_default="#EBEBEB"),
    "node_border_hover":   ColorKey("node_border_hover", "节点悬停边框", "节点",
                                    dark_default="#606266", light_default="#606266"),
    "node_border_selected": ColorKey("node_border_selected", "节点选中边框", "节点",
                                    dark_default="#E6A23C", light_default="#E6A23C"),
    "node_text":           ColorKey("node_text", "节点文字", "节点",
                                    dark_default="#DCDCDC", light_default="#1E1E1E"),
    "node_shadow":         ColorKey("node_shadow", "节点阴影", "节点",
                                    dark_default="#3C000000", light_default="#1E000000"),

    # ── 连线 / 连线 ──
    "edge":                ColorKey("edge", "连线", "连线",
                                    dark_default="#67C23A", light_default="#67C23A"),
    "edge_selected":       ColorKey("edge_selected", "连线选中", "连线",
                                    dark_default="#3399FF", light_default="#3399FF"),
    "edge_hover":          ColorKey("edge_hover", "连线悬停", "连线",
                                    dark_default="#0078D4", light_default="#0078D4"),
    "edge_running":        ColorKey("edge_running", "连线运行中", "连线",
                                    dark_default="#3399FF", light_default="#3399FF"),
    "edge_success":        ColorKey("edge_success", "连线完成", "连线",
                                    dark_default="#67C23A", light_default="#67C23A"),
    "edge_error":          ColorKey("edge_error", "连线错误", "连线",
                                    dark_default="#DC000C", light_default="#DC000C"),

    # ── 端口 / 端口 ──
    "port_input":          ColorKey("port_input", "输入端口", "端口",
                                    dark_default="#FFFFFF", light_default="#FFFFFF"),
    "port_output":         ColorKey("port_output", "输出端口", "端口",
                                    dark_default="#67C23A", light_default="#67C23A"),
    "port_connected":      ColorKey("port_connected", "已连接端口", "端口",
                                    dark_default="#67C23A", light_default="#67C23A"),

    # ── 滚动条 / 滚动条 ──
    "scroll_bg":           ColorKey("scroll_bg", "滚动条背景", "滚动条",
                                    dark_default="#1E1E1E", light_default="#F0F0F0"),
    "scroll_handle":       ColorKey("scroll_handle", "滚动条手柄", "滚动条",
                                    dark_default="#505050", light_default="#C0C0C0"),
    "scroll_handle_hover": ColorKey("scroll_handle_hover", "滚动条悬停", "滚动条",
                                    dark_default="#686868", light_default="#A0A0A0"),

    # ── 节点分组颜色 / 节点分组 ──
    "group_src":           ColorKey("group_src", "图像数据源", "节点分组",
                                    dark_default="#4A9EFF", light_default="#4A9EFF"),
    "group_preprocess":    ColorKey("group_preprocess", "预处理", "节点分组",
                                    dark_default="#FF8C00", light_default="#FF8C00"),
    "group_blur":          ColorKey("group_blur", "滤波", "节点分组",
                                    dark_default="#9C27B0", light_default="#9C27B0"),
    "group_morphology":    ColorKey("group_morphology", "形态学", "节点分组",
                                    dark_default="#00BCD4", light_default="#00BCD4"),
    "group_detector":      ColorKey("group_detector", "目标识别", "节点分组",
                                    dark_default="#F44336", light_default="#F44336"),
    "group_match":         ColorKey("group_match", "模板匹配", "节点分组",
                                    dark_default="#4CAF50", light_default="#4CAF50"),
    "group_output":        ColorKey("group_output", "结果输出", "节点分组",
                                    dark_default="#607D8B", light_default="#607D8B"),
    "group_network":       ColorKey("group_network", "网络通讯", "节点分组",
                                    dark_default="#795548", light_default="#795548"),
    "group_onnx":          ColorKey("group_onnx", "ONNX", "节点分组",
                                    dark_default="#E91E63", light_default="#E91E63"),
}

# 快速查找：颜色键ID → 暗色/亮色模式的默认值
# 当主题未覆盖时，由 ThemeDef.resolve() 使用
_DEFAULTS_DARK = {k: v.dark_default for k, v in COLOR_KEYS.items()}   # 暗色模式默认值字典
_DEFAULTS_LIGHT = {k: v.light_default for k, v in COLOR_KEYS.items()}  # 亮色模式默认值字典


# ═══════════════════════════════════════════════════════════════════════════
# 主题 — 所有内置主题定义
# ═══════════════════════════════════════════════════════════════════════════

def _make_dark() -> dict[str, str]:
    """暗色主题

    返回：
        暗色主题的颜色字典
    """
    return {
        "accent":              "#2D80FF",
        "text_primary":        "#FF8F939C",
        "text_title":          "#FFFFFF",
        "text_caption":        "#8F939C",
        "text_secondary":      "#909399",
        "text_disabled":       "#656565",
        "text_link":           "#6296D8",
        "bg_window":           "#2D2D30",
        "bg_surface":          "#252526",
        "bg_surface_raised":   "#343437",
        "bg_surface_hover":    "#3E3E42",
        "bg_surface_input":    "#333337",
        "bg_surface_deep":     "#1E1E1E",
        "bg_title_bar":        "#1E1E1E",
        "bg_caption":          "#191A20",
        "bg_alternating":      "#191A20",
        "bg_menu":             "#191A20",
        "border":              "#2E313B",
        "border_focus":        "#0078D4",
        "border_title":        "#363844",
        "border_assist":       "#272932",
        "status_ok":           "#67C23A",
        "status_error":        "#DC000C",
        "status_warning":      "#FFC107",
        "status_running":      "#3399FF",
        "status_idle":         "#909399",
        "status_disabled":     "#555555",
        "canvas_bg":           "#121317",
        "canvas_checker_base": "#121317",
        "canvas_checker_alt":  "#191A20",
        "canvas_grid":         "#2E313B",
        "node_bg":             "#3C3C3C",
        "node_bg_hover":       "#4A4A4A",
        "node_bg_selected":    "#4A4A4A",
        "node_border":         "#555555",
        "node_border_hover":   "#606266",
        "node_border_selected":"#E6A23C",
        "node_text":           "#DCDCDC",
        "node_shadow":         "#3C000000",
        "edge":                "#67C23A",
        "edge_selected":       "#3399FF",
        "edge_hover":          "#0078D4",
        "edge_running":        "#3399FF",
        "edge_success":        "#67C23A",
        "edge_error":          "#DC000C",
        "port_input":          "#FFFFFF",
        "port_output":         "#67C23A",
        "port_connected":      "#67C23A",
        "scroll_bg":           "#1E1E1E",
        "scroll_handle":       "#505050",
        "scroll_handle_hover": "#686868",
    }


def _make_light() -> dict[str, str]:
    """亮色主题

    返回：
        亮色主题的颜色字典
    """
    return {
        "accent":              "#FF3399FF",
        "text_primary":        "#606266",
        "text_title":          "#000000",
        "text_caption":        "#606266",
        "text_secondary":      "#909399",
        "text_disabled":       "#C0C0C0",
        "text_link":           "#6296D8",
        "bg_window":           "#F5F5F5",
        "bg_surface":          "#FFFFFF",
        "bg_surface_raised":   "#F5F5F5",
        "bg_surface_hover":    "#E8E8E8",
        "bg_surface_input":    "#FFFFFF",
        "bg_surface_deep":     "#F0F0F0",
        "bg_title_bar":        "#FFFFFF",
        "bg_caption":          "#F5F5F5",
        "bg_alternating":      "#FAFAFA",
        "bg_menu":             "#FFFFFF",
        "border":              "#EBEBEB",
        "border_focus":        "#0078D4",
        "border_title":        "#E2E2E2",
        "border_assist":       "#F0F0F0",
        "status_ok":           "#67C23A",
        "status_error":        "#DC000C",
        "status_warning":      "#E6A23C",
        "status_running":      "#3399FF",
        "status_idle":         "#909399",
        "status_disabled":     "#C0C0C0",
        "canvas_bg":           "#FFFFFF",
        "canvas_checker_base": "#FFFFFF",
        "canvas_checker_alt":  "#C0C0C0",
        "canvas_grid":         "#D8D8D8",
        "node_bg":             "#FFFFFF",
        "node_bg_hover":       "#F5F5F5",
        "node_bg_selected":    "#EBEBEB",
        "node_border":         "#EBEBEB",
        "node_border_hover":   "#606266",
        "node_border_selected":"#E6A23C",
        "node_text":           "#1E1E1E",
        "node_shadow":         "#1E000000",
        "edge":                "#67C23A",
        "edge_selected":       "#3399FF",
        "edge_hover":          "#0078D4",
        "edge_running":        "#3399FF",
        "edge_success":        "#67C23A",
        "edge_error":          "#DC000C",
        "port_input":          "#FFFFFF",
        "port_output":         "#67C23A",
        "port_connected":      "#67C23A",
        "scroll_bg":           "#F0F0F0",
        "scroll_handle":       "#C0C0C0",
        "scroll_handle_hover": "#A0A0A0",
    }


def _make_technology_blue_dark() -> dict[str, str]:
    """深空科技蓝主题

    用蓝青色技术调色板覆盖暗色主题：
      - accent → #00D1FF（青色）
      - bg → 深蓝灰色（#0A1628, #0D1F35）
      - node → 玻璃蓝（#1A3A5C）

    返回：
        科技蓝主题的颜色字典
    """
    return {
        **_make_dark(),          # 继承暗色主题的所有颜色
        # 覆盖以下颜色
        "accent":              "#00D1FF",
        "bg_surface":          "#0D1F35",
        "bg_surface_raised":   "#112240",
        "bg_surface_hover":    "#162D50",
        "bg_surface_input":    "#0A1628",
        "bg_surface_deep":     "#091320",
        "bg_window":           "#091320",
        "bg_title_bar":        "#091320",
        "bg_caption":          "#0A1628",
        "bg_alternating":      "#0D1F35",
        "bg_menu":             "#0A1628",
        "border":              "#1A3A5C",
        "border_focus":        "#00D1FF",
        "border_title":        "#1A3A5C",
        "border_assist":       "#0D1F35",
        "canvas_bg":           "#091320",
        "canvas_checker_base": "#091320",
        "canvas_checker_alt":  "#0D1F35",
        "canvas_grid":         "#1A3A5C",
        "node_bg":             "#1A3A5C",
        "node_bg_hover":       "#225080",
        "node_bg_selected":    "#225080",
        "node_border":         "#2A6090",
        "node_border_hover":   "#00D1FF",
        "node_text":           "#E0F0FF",
        "edge":                "#00D1FF",
        "edge_selected":       "#FFFFFF",
        "edge_running":        "#00D1FF",
        "scroll_bg":           "#091320",
        "scroll_handle":       "#1A3A5C",
        "scroll_handle_hover": "#225080",
        "status_running":      "#00D1FF",
    }


def _make_purple_dark() -> dict[str, str]:
    """暗夜紫主题

    用紫色调色板覆盖暗色主题。

    返回：
        紫色主题的颜色字典
    """
    return {
        **_make_dark(),          # 继承暗色主题的所有颜色
        # 覆盖以下颜色
        "accent":              "#BB86FC",
        "bg_surface":          "#1E1A2E",
        "bg_surface_raised":   "#262236",
        "bg_surface_hover":    "#2E2940",
        "bg_surface_input":    "#191528",
        "bg_surface_deep":     "#141024",
        "bg_window":           "#141024",
        "bg_title_bar":        "#141024",
        "bg_caption":          "#191528",
        "bg_alternating":      "#1E1A2E",
        "bg_menu":             "#191528",
        "border":              "#3A2E5C",
        "border_focus":        "#BB86FC",
        "border_title":        "#3A2E5C",
        "border_assist":       "#1E1A2E",
        "canvas_bg":           "#141024",
        "canvas_checker_base": "#141024",
        "canvas_checker_alt":  "#1E1A2E",
        "canvas_grid":         "#3A2E5C",
        "node_bg":             "#3A2E5C",
        "node_bg_hover":       "#4A3E70",
        "node_bg_selected":    "#4A3E70",
        "node_border":         "#5A4E80",
        "node_border_hover":   "#BB86FC",
        "node_text":           "#E8E0F0",
        "edge":                "#BB86FC",
        "edge_selected":       "#FFFFFF",
        "edge_running":        "#BB86FC",
        "scroll_bg":           "#141024",
        "scroll_handle":       "#3A2E5C",
        "scroll_handle_hover": "#4A3E70",
        "status_running":      "#BB86FC",
    }


# 主题字典
THEMES: dict[str, ThemeDef] = {
    # 暗色主题（推荐）
    "dark": ThemeDef(
        id="dark", name="深色（推荐）", group="强力推荐",
        is_dark=True, prompt="专业深色", description="护眼深色主题，适合长时间使用",
        colors=_make_dark(), order=0,
    ),
    # 亮色主题（推荐）
    "light": ThemeDef(
        id="light", name="浅色（推荐）", group="强力推荐",
        is_dark=False, prompt="清爽浅色", description="明亮清新，适合日间办公环境",
        colors=_make_light(), order=1,
    ),
    # 常规主题
    "default": ThemeDef(
        id="default", name="常规", group="纯色",
        is_dark=False, prompt="系统默认", description="跟随系统的基础配色方案",
        colors={}, order=10,
    ),
    # 深空科技蓝主题
    "technology_blue": ThemeDef(
        id="technology_blue", name="深空科技蓝", group="外部主题",
        is_dark=True, prompt="科技感", description="深蓝基调搭配青色强调，充满科技感",
        colors=_make_technology_blue_dark(), order=20,
    ),
    # 暗夜紫主题
    "purple": ThemeDef(
        id="purple", name="暗夜紫", group="外部主题",
        is_dark=True, prompt="优雅紫色", description="深紫底色配合淡紫强调，优雅神秘",
        colors=_make_purple_dark(), order=21,
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# 解析：合并主题覆盖与默认值
# ═══════════════════════════════════════════════════════════════════════════

def resolve_colors(theme: ThemeDef) -> dict[str, str]:
    """将主题解析为完整的颜色映射，用默认值填充缺失的键

    参数：
        theme: 主题定义

    返回：
        完整的颜色字典
    """
    # 根据是否为暗色模式选择默认值字典
    defaults = _DEFAULTS_DARK if theme.is_dark else _DEFAULTS_LIGHT
    # 从所有默认值开始
    resolved = dict(defaults)
    # 应用主题覆盖
    resolved.update(theme.colors)
    return resolved


def get_theme_ids() -> list[str]:
    """获取所有已注册的主题ID，按显示顺序排列

    返回：
        主题ID列表
    """
    # 按order排序后返回主题ID列表
    return sorted(THEMES.keys(), key=lambda k: THEMES[k].order)


def get_theme_by_id(theme_id: str) -> ThemeDef | None:
    """根据ID获取主题定义

    参数：
        theme_id: 主题ID

    返回：
        主题定义或None
    """
    return THEMES.get(theme_id)


def get_color_key(key_id: str) -> ColorKey | None:
    """根据ID获取颜色键

    参数：
        key_id: 颜色键ID

    返回：
        颜色键或None
    """
    return COLOR_KEYS.get(key_id)


def list_color_keys() -> list[str]:
    """列出所有颜色键ID

    返回：
        颜色键ID列表
    """
    return list(COLOR_KEYS.keys())
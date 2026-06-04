"""Shared constants — single source of truth for group metadata.

Previously duplicated across toolbox_panel.py, node_list_view.py, and node_item.py.
Now all modules import from here.
"""

from gui.font_icons import FontIcons

# ── Group colors and icons matching WPF ──────────────────────────────────

GROUP_META = {
    "图像数据源":   {"color": "#4a9eff", "icon": FontIcons.Photo2},
    "系统数据源":   {"color": "#5c6bc0", "icon": FontIcons.Folder},
    "图像预处理模块": {"color": "#ff8c00", "icon": FontIcons.Color},
    "滤波模块":     {"color": "#9c27b0", "icon": FontIcons.Filter},
    "图像分割提取模块": {"color": "#e91e63", "icon": FontIcons.Cut},
    "形态学模块":   {"color": "#00bcd4", "icon": "⬒"},
    "逻辑模块":     {"color": "#ff5722", "icon": "⇄"},
    "模板匹配模块": {"color": "#4caf50", "icon": "⌖"},
    "对象识别模块": {"color": "#f44336", "icon": "◉"},
    "特征提取模块": {"color": "#ff9800", "icon": "✣"},
    "网络通讯模块": {"color": "#795548", "icon": "⌁"},
    "结果输出模块": {"color": "#607d8b", "icon": "↗"},
    "Onnx通用模型": {"color": "#c2185b", "icon": "AI"},
    "其他模块":     {"color": "#607d8b", "icon": "◇"},
    "视频处理模块": {"color": "#8d6e63", "icon": FontIcons.Video},
    "★ 收藏":      {"color": "#d7ba7d", "icon": FontIcons.FavoriteStar},
    "🕐 最近使用":  {"color": "#d7ba7d", "icon": "🕐"},
    # English aliases
    "Source":       {"color": "#4a9eff", "icon": FontIcons.Photo2},
    "Preprocessing":{"color": "#ff8c00", "icon": FontIcons.Color},
    "Blur":         {"color": "#9c27b0", "icon": FontIcons.Filter},
    "Takeoff":      {"color": "#e91e63", "icon": FontIcons.Cut},
    "Morphology":   {"color": "#00bcd4", "icon": "⬒"},
    "Condition":    {"color": "#ff5722", "icon": "⇄"},
    "TemplateMatching": {"color": "#4caf50", "icon": "⌖"},
    "Detector":     {"color": "#f44336", "icon": "◉"},
    "Feature":      {"color": "#ff9800", "icon": "✣"},
    "Network":      {"color": "#795548", "icon": "⌁"},
    "Output":       {"color": "#607d8b", "icon": "↗"},
    "ONNX":         {"color": "#e91e63", "icon": "AI"},
    "Other":        {"color": "#607d8b", "icon": "◇"},
    "Video":        {"color": "#8d6e63", "icon": FontIcons.Video},
}

# ── Group colors (flattened, used by node_item.py) ─────────────────────

GROUP_COLORS = {k: v["color"] for k, v in GROUP_META.items()}


def get_group_meta(group_name: str) -> dict:
    """Get metadata for a group, with fallback."""
    return GROUP_META.get(group_name, {"color": "#607d8b", "icon": "◇"})


def get_group_color(group_name: str) -> str:
    """Get color for a group, with fallback."""
    meta = GROUP_META.get(group_name, {})
    return meta.get("color", "#607d8b")


def get_group_icon(group_name: str) -> str:
    """Get icon for a group, with fallback."""
    meta = GROUP_META.get(group_name, {})
    return meta.get("icon", "◇")

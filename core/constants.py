"""Shared constants — single source of truth for group metadata.

Previously duplicated across toolbox_panel.py, node_list_view.py, and node_item.py.
Now all modules import from here.
"""

from gui.font_icons import FontIcons

# ── Group colors and icons matching WPF ──────────────────────────────────

GROUP_META = {
    # WPF H.VisionMaster.NodeGroup — icons match FontIcons.cs exactly
    "图像数据源":   {"color": "#4a9eff", "icon": FontIcons.Camera},           # SrcImageDataGroup
    "系统数据源":   {"color": "#5c6bc0", "icon": FontIcons.Photo2},           # ZooNodeDataGroup
    "图像预处理模块": {"color": "#ff8c00", "icon": FontIcons.Color},           # PreprocessingDataGroup
    "滤波模块":     {"color": "#9c27b0", "icon": FontIcons.InPrivate},        # BlurDataGroup
    "图像分割提取模块": {"color": "#e91e63", "icon": FontIcons.Annotation},    # TakeoffDataGroup
    "形态学模块":   {"color": "#00bcd4", "icon": FontIcons.HomeGroup},        # MorphologyDataGroup
    "逻辑模块":     {"color": "#ff5722", "icon": FontIcons.Dial6},            # ConditionDataGroup
    "模板匹配模块": {"color": "#4caf50", "icon": FontIcons.GotoToday},        # TemplateMatchingDataGroup
    "对象识别模块": {"color": "#f44336", "icon": FontIcons.LargeErase},       # DetectorDataGroup
    "特征提取模块": {"color": "#ff9800", "icon": FontIcons.GenericScan},      # FeatureDetectorDataGroup
    "网络通讯模块": {"color": "#795548", "icon": FontIcons.NarratorForward},  # NetworkDataGroup
    "结果输出模块": {"color": "#607d8b", "icon": FontIcons.Ethernet},         # OutputDataGroup
    "Onnx通用模型": {"color": "#c2185b", "icon": FontIcons.CommandPrompt},    # OnnxDataGroup
    "其他模块":     {"color": "#607d8b", "icon": FontIcons.More},             # OtherDataGroup
    "视频处理模块": {"color": "#8d6e63", "icon": FontIcons.Video},
    "★ 收藏":      {"color": "#d7ba7d", "icon": FontIcons.FavoriteStar},
    "🕐 最近使用":  {"color": "#d7ba7d", "icon": "🕐"},
    # English aliases
    "Source":       {"color": "#4a9eff", "icon": FontIcons.Camera},
    "Preprocessing":{"color": "#ff8c00", "icon": FontIcons.Color},
    "Blur":         {"color": "#9c27b0", "icon": FontIcons.InPrivate},
    "Takeoff":      {"color": "#e91e63", "icon": FontIcons.Annotation},
    "Morphology":   {"color": "#00bcd4", "icon": FontIcons.HomeGroup},
    "Condition":    {"color": "#ff5722", "icon": FontIcons.Dial6},
    "TemplateMatching": {"color": "#4caf50", "icon": FontIcons.GotoToday},
    "Detector":     {"color": "#f44336", "icon": FontIcons.LargeErase},
    "Feature":      {"color": "#ff9800", "icon": FontIcons.GenericScan},
    "Network":      {"color": "#795548", "icon": FontIcons.NarratorForward},
    "Output":       {"color": "#607d8b", "icon": FontIcons.Ethernet},
    "ONNX":         {"color": "#e91e63", "icon": FontIcons.CommandPrompt},
    "Other":        {"color": "#607d8b", "icon": FontIcons.More},
    "Video":        {"color": "#8d6e63", "icon": FontIcons.Video},
}

# ── Group colors (flattened, used by node_item.py) ─────────────────────

GROUP_COLORS = {k: v["color"] for k, v in GROUP_META.items()}


def get_group_meta(group_name: str) -> dict:
    """Get metadata for a group, with fallback (WPF More icon)."""
    return GROUP_META.get(group_name,
                          {"color": "#607d8b", "icon": FontIcons.More})


def get_group_color(group_name: str) -> str:
    """Get color for a group, with fallback."""
    meta = GROUP_META.get(group_name, {})
    return meta.get("color", "#607d8b")


def get_group_icon(group_name: str) -> str:
    """Get icon for a group, with fallback (WPF More icon)."""
    meta = GROUP_META.get(group_name, {})
    return meta.get("icon", FontIcons.More)

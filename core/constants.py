"""共享常量 -- 群组元数据的单一数据源
    模块分组元数据配置

    用途: 为节点库/模块面板中的各个分组提供统一的视觉标识

    数据格式:
      - 键: 分组显示名称(中英文均可)
      - 值: 包含颜色(十六进制)和图标(字体图标或emoji)的字典

    分组说明:
      - 中文分组: 面向UI显示的实际分组名称
      - 英文别名: 便于代码中通过英文标识访问配置
      - 特殊分组: * 收藏, 最近使用(元分组, 用于动态内容)

    关联类注释(中文分组对应的后端数据类):
      - 图像数据源 -> SrcImageDataGroup
      - 系统数据源 -> ZooNodeDataGroup
      - 图像预处理模块 -> PreprocessingDataGroup
      - 滤波模块 -> BlurDataGroup
      - 图像分割提取模块 -> TakeoffDataGroup
      - 形态学模块 -> MorphologyDataGroup
      - 逻辑模块 -> ConditionDataGroup
      - 模板匹配模块 -> TemplateMatchingDataGroup
      - 对象识别模块 -> DetectorDataGroup
      - 特征提取模块 -> FeatureDetectorDataGroup
      - 网络通讯模块 -> NetworkDataGroup
      - 结果输出模块 -> OutputDataGroup
      - Onnx通用模型 -> OnnxDataGroup
      - 其他模块 -> OtherDataGroup
# TODO(arch): GUI layer maps these icon string keys to QIcon objects.
# See gui/font_icons.py for the FontIcons class that imports from here.
"""

# Icon string constants (Segoe Fluent Icons Unicode codepoints)
ICON_CAMERA = ""
ICON_PHOTO2 = ""
ICON_COLOR = ""
ICON_IN_PRIVATE = ""
ICON_ANNOTATION = ""
ICON_HOME_GROUP = ""
ICON_DIAL6 = ""
ICON_GOTO_TODAY = ""
ICON_LARGE_ERASE = ""
ICON_GENERIC_SCAN = ""
ICON_NARRATOR_FORWARD = ""
ICON_ETHERNET = ""
ICON_COMMAND_PROMPT = ""
ICON_MORE = ""
ICON_VIDEO = ""
ICON_FAVORITE_STAR = ""

# English alias -> Chinese key mapping (avoids duplicating color/icon data)
_ALIAS_TO_CHINESE: dict[str, str] = {
    "Source": "图像数据源",          # 图像数据源
    "Preprocessing": "图像预处理模块",  # 图像预处理模块
    "Blur": "滤波模块",                  # 滤波模块
    "Takeoff": "图像分割提取模块",  # 图像分割提取模块
    "Morphology": "形态学模块",       # 形态学模块
    "Condition": "逻辑模块",              # 逻辑模块
    "TemplateMatching": "模板匹配模块",  # 模板匹配模块
    "Detector": "对象识别模块",   # 对象识别模块
    "Feature": "特征提取模块",    # 特征提取模块
    "Network": "网络通讯模块",    # 网络通讯模块
    "Output": "结果输出模块",     # 结果输出模块
    "ONNX": "Onnx通用模型",               # Onnx通用模型
    "Other": "其他模块",                  # 其他模块
    "Video": "视频处理模块",      # 视频处理模块
}

# Group metadata config
GROUP_META = {
    # Chinese groups
    "图像数据源": {"color": "#4a9eff", "icon": ICON_CAMERA},
    "系统数据源": {"color": "#5c6bc0", "icon": ICON_PHOTO2},
    "图像预处理模块": {"color": "#ff8c00", "icon": ICON_COLOR},
    "滤波模块": {"color": "#9c27b0", "icon": ICON_IN_PRIVATE},
    "图像分割提取模块": {"color": "#e91e63", "icon": ICON_ANNOTATION},
    "形态学模块": {"color": "#00bcd4", "icon": ICON_HOME_GROUP},
    "逻辑模块": {"color": "#ff5722", "icon": ICON_DIAL6},
    "模板匹配模块": {"color": "#4caf50", "icon": ICON_GOTO_TODAY},
    "对象识别模块": {"color": "#f44336", "icon": ICON_LARGE_ERASE},
    "特征提取模块": {"color": "#ff9800", "icon": ICON_GENERIC_SCAN},
    "网络通讯模块": {"color": "#795548", "icon": ICON_NARRATOR_FORWARD},
    "结果输出模块": {"color": "#607d8b", "icon": ICON_ETHERNET},
    "Onnx通用模型": {"color": "#c2185b", "icon": ICON_COMMAND_PROMPT},
    "其他模块": {"color": "#607d8b", "icon": ICON_MORE},
    "视频处理模块": {"color": "#8d6e63", "icon": ICON_VIDEO},
    "★ 收藏": {"color": "#d7ba7d", "icon": ICON_FAVORITE_STAR},
    "🕐 最近使用": {"color": "#d7ba7d", "icon": "🕐"},
}

# Flattened color map (used by node_item.py)
GROUP_COLORS = {k: v["color"] for k, v in GROUP_META.items()}


def _resolve_group_name(group_name: str) -> str:
    """Resolve English alias to Chinese key, or return as-is if not an alias."""
    return _ALIAS_TO_CHINESE.get(group_name, group_name)


def get_group_meta(group_name: str) -> dict:
    """Get group metadata, or default if not found."""
    key = _resolve_group_name(group_name)
    return GROUP_META.get(key,
                          {"color": "#607d8b", "icon": ICON_MORE})


def get_group_color(group_name: str) -> str:
    """Get group color, or default gray if not found."""
    return get_group_meta(group_name).get("color", "#607d8b")


def get_group_icon(group_name: str) -> str:
    """Get group icon, or default More icon if not found."""
    return get_group_meta(group_name).get("icon", ICON_MORE)

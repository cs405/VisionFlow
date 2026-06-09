"""共享常量——群组元数据的单一数据源
    模块分组元数据配置

    用途：为节点库/模块面板中的各个分组提供统一的视觉标识

    数据格式：
      - 键：分组显示名称（中英文均可）
      - 值：包含颜色（十六进制）和图标（字体图标或emoji）的字典

    分组说明：
      - 中文分组：面向UI显示的实际分组名称
      - 英文别名：便于代码中通过英文标识访问配置
      - 特殊分组：★ 收藏、🕐 最近使用（元分组，用于动态内容）

    关联类注释（中文分组对应的后端数据类）：
      - 图像数据源 → SrcImageDataGroup
      - 系统数据源 → ZooNodeDataGroup
      - 图像预处理模块 → PreprocessingDataGroup
      - 滤波模块 → BlurDataGroup
      - 图像分割提取模块 → TakeoffDataGroup
      - 形态学模块 → MorphologyDataGroup
      - 逻辑模块 → ConditionDataGroup
      - 模板匹配模块 → TemplateMatchingDataGroup
      - 对象识别模块 → DetectorDataGroup
      - 特征提取模块 → FeatureDetectorDataGroup
      - 网络通讯模块 → NetworkDataGroup
      - 结果输出模块 → OutputDataGroup
      - Onnx通用模型 → OnnxDataGroup
      - 其他模块 → OtherDataGroup
"""
from gui.font_icons import FontIcons


# 定义模块分组元数据配置字典
# 用于为不同功能模块组分配视觉样式（颜色、图标）和关联的类名
GROUP_META = {
    # ==================== 中文分组 ====================
    "图像数据源": {"color": "#4a9eff", "icon": FontIcons.Camera},  # 关联类: SrcImageDataGroup
    "系统数据源": {"color": "#5c6bc0", "icon": FontIcons.Photo2},  # 关联类: ZooNodeDataGroup
    "图像预处理模块": {"color": "#ff8c00", "icon": FontIcons.Color},  # 关联类: PreprocessingDataGroup
    "滤波模块": {"color": "#9c27b0", "icon": FontIcons.InPrivate},  # 关联类: BlurDataGroup
    "图像分割提取模块": {"color": "#e91e63", "icon": FontIcons.Annotation},  # 关联类: TakeoffDataGroup
    "形态学模块": {"color": "#00bcd4", "icon": FontIcons.HomeGroup},  # 关联类: MorphologyDataGroup
    "逻辑模块": {"color": "#ff5722", "icon": FontIcons.Dial6},  # 关联类: ConditionDataGroup
    "模板匹配模块": {"color": "#4caf50", "icon": FontIcons.GotoToday},  # 关联类: TemplateMatchingDataGroup
    "对象识别模块": {"color": "#f44336", "icon": FontIcons.LargeErase},  # 关联类: DetectorDataGroup
    "特征提取模块": {"color": "#ff9800", "icon": FontIcons.GenericScan},  # 关联类: FeatureDetectorDataGroup
    "网络通讯模块": {"color": "#795548", "icon": FontIcons.NarratorForward},  # 关联类: NetworkDataGroup
    "结果输出模块": {"color": "#607d8b", "icon": FontIcons.Ethernet},  # 关联类: OutputDataGroup
    "Onnx通用模型": {"color": "#c2185b", "icon": FontIcons.CommandPrompt},  # 关联类: OnnxDataGroup
    "其他模块": {"color": "#607d8b", "icon": FontIcons.More},  # 关联类: OtherDataGroup
    "视频处理模块": {"color": "#8d6e63", "icon": FontIcons.Video},  # 视频处理相关
    "★ 收藏": {"color": "#d7ba7d", "icon": FontIcons.FavoriteStar},  # 收藏夹分组（特殊元分组）
    "🕐 最近使用": {"color": "#d7ba7d", "icon": "🕐"},  # 最近使用分组（特殊元分组，使用emoji图标）

    # ==================== 英文别名/映射 ====================
    # 提供英文键名映射，方便代码中统一访问（避免中文字符串硬编码）
    "Source": {"color": "#4a9eff", "icon": FontIcons.Camera},  # 对应"图像数据源"
    "Preprocessing": {"color": "#ff8c00", "icon": FontIcons.Color},  # 对应"图像预处理模块"
    "Blur": {"color": "#9c27b0", "icon": FontIcons.InPrivate},  # 对应"滤波模块"
    "Takeoff": {"color": "#e91e63", "icon": FontIcons.Annotation},  # 对应"图像分割提取模块"
    "Morphology": {"color": "#00bcd4", "icon": FontIcons.HomeGroup},  # 对应"形态学模块"
    "Condition": {"color": "#ff5722", "icon": FontIcons.Dial6},  # 对应"逻辑模块"
    "TemplateMatching": {"color": "#4caf50", "icon": FontIcons.GotoToday},  # 对应"模板匹配模块"
    "Detector": {"color": "#f44336", "icon": FontIcons.LargeErase},  # 对应"对象识别模块"
    "Feature": {"color": "#ff9800", "icon": FontIcons.GenericScan},  # 对应"特征提取模块"
    "Network": {"color": "#795548", "icon": FontIcons.NarratorForward},  # 对应"网络通讯模块"
    "Output": {"color": "#607d8b", "icon": FontIcons.Ethernet},  # 对应"结果输出模块"
    "ONNX": {"color": "#e91e63", "icon": FontIcons.CommandPrompt},  # 对应"Onnx通用模型"
    "Other": {"color": "#607d8b", "icon": FontIcons.More},  # 对应"其他模块"
    "Video": {"color": "#8d6e63", "icon": FontIcons.Video},  # 对应"视频处理模块"
}

# ── Group colors (flattened, used by node_item.py) ─────────────────────

GROUP_COLORS = {k: v["color"] for k, v in GROUP_META.items()}


# 从 GROUP_META 中提取颜色映射，生成扁平化的颜色字典
GROUP_COLORS = {k: v["color"] for k, v in GROUP_META.items()}


def get_group_meta(group_name: str) -> dict:
    """获取组的元数据，若不存在则返回默认元数据（灰色 + More图标）"""
    return GROUP_META.get(group_name,
                          {"color": "#607d8b", "icon": FontIcons.More})


def get_group_color(group_name: str) -> str:
    """获取组的颜色，若不存在则返回默认灰色"""
    meta = GROUP_META.get(group_name, {})
    return meta.get("color", "#607d8b")


def get_group_icon(group_name: str) -> str:
    """获取组的图标，若不存在则返回默认 More 图标"""
    meta = GROUP_META.get(group_name, {})
    return meta.get("icon", FontIcons.More)

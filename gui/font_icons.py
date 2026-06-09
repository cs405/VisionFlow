"""字体图标系统

该模块提供：
  - FontIcons: 常量类，将所有图标名称映射到Unicode码点
  - FontIconButton: 使用图标字体渲染的 QPushButton
  - FontIconToggleButton: 带选中/未选中图标的可选中按钮
  - FontIconTextBlock: 使用图标字体渲染的 QLabel
  - 带后备方案的图标字体加载

用法：
    btn = FontIconButton(FontIcons.Replay, "启动", parent)
    toggle = FontIconToggleButton(FontIcons.AlignLeft, FontIcons.CaretBottomRightSolidCenter8, parent)
    label = FontIconTextBlock(FontIcons.Photo2, parent)
"""

from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QHBoxLayout
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QFontDatabase, QPainter

from gui.theme import theme_manager, connect_theme


# ── 字体族解析 ──────────────────────────────────────────────────

def _detect_icon_font() -> str:
    """检测 Windows 上可用的 Segoe 图标字体族"""
    # 候选字体列表（按优先级排序）
    candidates = [
        "Segoe MDL2 Assets",        # Windows 10 图标字体
        "Segoe Fluent Icons",       # Windows 11 新图标字体（许多字形不同或缺失）
        "Segoe UI Symbol",          # 最后的后备方案
    ]
    # 遍历候选字体
    for name in candidates:
        # 创建字体对象
        font = QFont(name)
        # 如果精确匹配成功
        if font.exactMatch():
            # 返回字体名称
            return name
    # 后备方案：尝试查找任何包含"segoe"和图标相关关键词的字体
    db = QFontDatabase()
    # 遍历所有可用字体族
    for family in db.families():
        # 如果字体名包含"segoe"且包含图标相关关键词
        if "segoe" in family.lower() and ("icon" in family.lower() or "symbol" in family.lower() or "mdl2" in family.lower()):
            # 返回找到的字体族
            return family
    # 最终后备方案
    return "Segoe UI Symbol"


# 全局图标字体族常量
ICON_FONT_FAMILY = _detect_icon_font()


def icon_font(size: int = 12) -> QFont:
    """创建配置好的图标字体 QFont

    参数：
        size: 字体像素大小

    返回：
        配置好的 QFont 对象
    """
    # 创建字体对象
    font = QFont(ICON_FONT_FAMILY)
    # 设置像素大小
    font.setPixelSize(size)
    # 设置字体策略为优先抗锯齿
    font.setStyleStrategy(QFont.PreferAntialias)
    # 返回字体对象
    return font


# ── FontIcons 常量类 ─────────────────────────────────────

class FontIcons:
    """静态图标常量类

    每个常量将图标名称映射到 Segoe Fluent Icons / Segoe MDL2 Assets 字体中的 Unicode 码点。
    码点源自 Windows 11 Segoe Fluent Icons 字符映射表
    """

    # ── 导航图标 ──
    GlobalNavButton = ""      # 全局导航按钮
    ChevronLeft = ""          # 左箭头
    ChevronRight = ""         # 右箭头
    ChevronUp = ""            # 上箭头
    ChevronDown = ""          # 下箭头
    PageLeft = ""             # 左翻页
    PageRight = ""            # 右翻页

    # ── 动作图标 ──
    Replay = ""               # 重放/运行/启动
    Play = ""                 # 播放（同Replay）
    Stop = ""                # 停止
    Pause = ""               # 暂停
    Sync = ""                # 同步
    Refresh = ""             # 刷新/重置
    Undo = ""                # 撤销
    Redo = ""                # 重做
    Delete = ""              # 删除/清空
    Cancel = ""              # 取消
    Add = ""                # 添加
    Copy = ""                # 复制
    Paste = ""               # 粘贴
    Save = ""                # 保存
    OpenFile = ""            # 打开文件
    OpenFolderHorizontal = "" # 打开文件夹（水平）
    Edit = ""                # 编辑
    EditMirrored = ""        # 编辑（镜像）
    Setting = ""             # 设置/齿轮
    Zoom = ""                # 缩放/适应
    ZoomIn = ""              # 放大
    ZoomOut = ""             # 缩小
    FullScreen = ""          # 全屏
    View = ""                # 视图/眼睛
    Page = ""                # 页面/新建项目

    # ── 状态图标 ──
    Completed = ""           # 完成
    Error = ""               # 错误
    Info = ""                # 信息/关于
    Warning = ""             # 警告
    Help = ""                # 帮助
    Location = ""            # 位置/停止位置

    # ── 文件/对象图标 ──
    Photo2 = ""              # 照片
    Calendar = ""            # 日历
    Folder = ""              # 文件夹
    Document = ""            # 文档
    Video = ""               # 视频
    Camera = ""              # 相机
    OpenAs = ""              # 打开为

    # ── 节点分组图标 ──
    InPrivate = ""           # 滤波模块 BlurDataGroup
    Annotation = ""          # 图像分割提取 TakeoffDataGroup
    HomeGroup = ""           # 形态学模块 MorphologyDataGroup
    Dial6 = ""               # 逻辑模块 ConditionDataGroup
    GotoToday = ""           # 模板匹配 TemplateMatchingDataGroup
    LargeErase = ""          # 对象识别 DetectorDataGroup
    GenericScan = ""         # 特征识别 FeatureDetectorDataGroup
    NarratorForward = ""     # 网络通讯 NetworkDataGroup
    CommandPrompt = ""       # Onnx通用模型 OnnxDataGroup
    More = ""                # 其他模块 OtherDataGroup

    # ── 布局/视图图标 ──
    AlignLeft = ""           # 左对齐
    AlignCenter = ""         # 居中对齐
    CaretBottomRightSolidCenter8 = ""  # 右下角实心箭头
    DisconnectDrive = ""     # 断开连接/删除节点

    # ── 工具图标 ──
    Color = ""               # 调色板/主题
    Brightness = ""          # 太阳/亮度
    QuietHours = ""          # 月亮/夜间模式
    Crop = ""                # 裁剪
    Cut = ""                 # 剪切
    Filter = ""              # 过滤
    DictionaryAdd = ""       # 从模板添加
    Manage = ""              # 管理/模板管理器
    SaveAs = ""              # 另存为模板
    Ethernet = ""            # 运行模式

    # ── 窗口控制图标 ──
    ChromeMinimize = ""      # 最小化
    ChromeMaximize = ""      # 最大化
    ChromeRestore = ""       # 还原
    ChromeClose = ""         # 关闭

    # ── 鼠标/引导图标 ──
    Mouse = ""               # 鼠标/向导
    Smartcard = ""           # ShowGuideCommand 图标别名

    # ── 电源/系统图标 ──
    PowerButton = ""         # 电源按钮

    # ── 通信图标 ──
    Mail = ""                # 邮件
    Chat = ""                # 聊天
    Phone = ""               # 电话
    WiFi = ""                # WiFi

    # ── 地图图标 ──
    MapPin = ""              # 地图图钉
    POI = ""                 # 兴趣点

    # ── 联系人/人员图标 ──
    Contact = ""             # 联系人
    People = ""              # 人员
    Emoji = ""               # 表情符号

    # ── 交通图标 ──
    Bus = ""                 # 公交
    Car = ""                 # 汽车

    # ── 后备/额外图标 ──
    FavoriteStar = ""        # 实心星形（收藏）
    FavoriteStarOutline = "" # 空心星形（收藏轮廓）
    Pin = ""                 # 图钉（固定）
    Unpin = ""               # 取消固定
    Like = ""                # 点赞
    Dislike = ""             # 点踩
    Flag = ""               # 标记

    # ── 从 HeBianGu 框架扩展的图标 ──
    Home = ""                # 主页
    Download = ""            # 下载
    Upload = ""              # 上传
    Print = ""               # 打印
    Shop = ""                # 商店
    World = ""               # 世界
    Feedback = ""            # 反馈/缺陷
    Heart = ""               # 心形
    Share = ""               # 分享
    Link = ""                # 链接


# ── FontIcon 展示控件 ─────────────────────────────────────────────

class FontIconTextBlock(QLabel):
    """使用图标字体渲染的 QLabel"""

    def __init__(self, text: str = "", font_size: int = 12,
                 color: str = "", parent=None):
        """初始化字体图标文本块

        参数：
            text: 图标字符
            font_size: 字体大小
            color: 颜色
            parent: 父对象
        """
        # 调用父类QLabel的构造函数
        super().__init__(text, parent)
        # 保存图标文本
        self._icon_text = text
        # 保存图标大小
        self._icon_size = font_size
        # 保存图标颜色
        self._icon_color = color
        # 应用样式
        self._apply_style()
        # 设置文本
        self.setText(text)

    def setText(self, text: str):
        """设置文本

        参数：
            text: 文本内容
        """
        # 调用父类的setText
        super().setText(text)
        # 更新保存的图标文本
        self._icon_text = text
        # 应用样式
        self._apply_style()

    def set_icon(self, icon: str):
        """设置图标字符

        参数：
            icon: 图标字符
        """
        # 调用setText设置文本
        self.setText(icon)

    def set_color(self, color: str):
        """通过样式表设置图标颜色

        参数：
            color: 颜色值
        """
        # 保存颜色
        self._icon_color = color
        # 应用样式
        self._apply_style()

    def _apply_style(self):
        """应用图标字体样式"""
        # 如果有颜色，生成颜色样式字符串
        extra = f"color: {self._icon_color};" if self._icon_color else ""
        # 设置字体
        self.setFont(icon_font(self._icon_size))
        # 设置样式表
        self.setStyleSheet(
            f"FontIconTextBlock {{ background: transparent; border: none; {extra} }}"
        )


class FontIconButton(QPushButton):
    """带有图标字形的按钮

    支持：仅图标模式、图标+文本模式、工具提示和 Command 样式
    """

    def __init__(self, icon: str = "", text: str = "", tooltip: str = "",
                 font_size: int = 16, parent=None):
        """初始化字体图标按钮

        参数：
            icon: 图标字符
            text: 按钮文本
            tooltip: 工具提示
            font_size: 字体大小
            parent: 父对象
        """
        # 调用父类QPushButton的构造函数
        super().__init__(parent)
        # 保存图标
        self._icon = icon
        # 保存图标大小
        self._icon_size = font_size
        # 保存文本标签
        self._label_text = text
        # 是否为仅图标模式
        self._icon_only = not bool(text)

        # 如果有文本
        if text:
            # 设置文本为"图标  文本"
            self.setText(f"{icon}  {text}" if icon else text)
        else:
            # 只设置图标
            self.setText(icon)

        # 设置字体
        self.setFont(icon_font(font_size))
        # 如果有工具提示
        if tooltip:
            # 设置工具提示
            self.setToolTip(tooltip)

        # 如果是仅图标模式
        if self._icon_only:
            # 设置固定大小为35x35
            self.setFixedSize(35, 35)

        # 设置光标为手指形状
        self.setCursor(Qt.PointingHandCursor)
        # 应用样式
        self._apply_style()
        # 连接主题变化信号
        connect_theme(self._refresh_qss)

    def set_icon(self, icon: str):
        """设置图标

        参数：
            icon: 图标字符
        """
        # 保存图标
        self._icon = icon
        # 如果有文本标签
        if self._label_text:
            # 更新文本为"图标  文本"
            self.setText(f"{icon}  {self._label_text}")
        else:
            # 只设置图标
            self.setText(icon)

    def _refresh_qss(self):
        """主题变化时重新应用 QSS"""
        # 应用样式
        self._apply_style()

    def _apply_style(self):
        """应用样式"""
        # 从主题获取各种颜色
        text_primary = theme_manager.color('text_primary').name()     # 主文本色
        hover_bg = theme_manager.color('bg_surface_hover').name()     # 悬停背景色
        accent = theme_manager.color('accent').name()                 # 强调色
        text_secondary = theme_manager.color('text_secondary').name() # 次要文本色
        # 设置样式表
        self.setStyleSheet(f"""
            FontIconButton {{
                background: transparent;
                border: none;
                border-radius: 2px;
                color: {text_primary};
                padding: 5px 0;
            }}
            FontIconButton:hover {{
                background: {hover_bg};
            }}
            FontIconButton:pressed {{
                background: {accent};
                color: white;
            }}
            FontIconButton:disabled {{
                color: {text_secondary};
                background: transparent;
            }}
        """)

    # 按钮类型常量
    Command = "Command"   # FontIconButtonKeys.Command
    Default = "Default"   # FontIconButtonKeys.Default


class FontIconToggleButton(QPushButton):
    """可切换的字体图标按钮

    参数：
        checked_icon: 选中状态显示的图标
        unchecked_icon: 未选中状态显示的图标
        text: 图标旁的可选标签
        font_size: 图标字体像素大小
    """

    def __init__(self, checked_icon: str = "", unchecked_icon: str = "",
                 text: str = "", font_size: int = 16, parent=None):
        """初始化可切换字体图标按钮

        参数：
            checked_icon: 选中时显示的图标
            unchecked_icon: 未选中时显示的图标
            text: 按钮文本
            font_size: 字体大小
            parent: 父对象
        """
        # 调用父类QPushButton的构造函数
        super().__init__(parent)
        # 保存选中图标
        self._checked_icon = checked_icon
        # 保存未选中图标
        self._unchecked_icon = unchecked_icon
        # 保存文本标签
        self._label_text = text
        # 保存图标大小
        self._icon_size = font_size

        # 设置按钮可选中
        self.setCheckable(True)
        # 默认设为选中状态
        self.setChecked(True)
        # 设置字体
        self.setFont(icon_font(font_size))
        # 设置光标为手指形状
        self.setCursor(Qt.PointingHandCursor)
        # 更新按钮文本
        self._update_text()
        # 连接切换信号
        self.toggled.connect(lambda _: self._update_text())
        # 应用样式
        self._apply_style()
        # 连接主题变化信号
        connect_theme(self._refresh_qss)

    def _update_text(self):
        """更新按钮文本"""
        # 根据选中状态选择图标
        icon = self._checked_icon if self.isChecked() else self._unchecked_icon
        # 如果有文本标签
        if self._label_text:
            # 设置文本为"图标  文本"
            self.setText(f"{icon}  {self._label_text}")
        else:
            # 只设置图标
            self.setText(icon)

    def set_checked_icon(self, icon: str):
        """设置选中时的图标

        参数：
            icon: 图标字符
        """
        # 保存选中图标
        self._checked_icon = icon
        # 更新文本
        self._update_text()

    def set_unchecked_icon(self, icon: str):
        """设置未选中时的图标

        参数：
            icon: 图标字符
        """
        # 保存未选中图标
        self._unchecked_icon = icon
        # 更新文本
        self._update_text()

    def _refresh_qss(self):
        """主题变化时重新应用 QSS"""
        # 应用样式
        self._apply_style()

    def _apply_style(self):
        """应用样式"""
        # 从主题获取各种颜色
        text_secondary = theme_manager.color('text_secondary').name()  # 次要文本色
        hover_bg = theme_manager.color('bg_surface_hover').name()      # 悬停背景色
        text_primary = theme_manager.color('text_primary').name()      # 主文本色
        # 设置样式表
        self.setStyleSheet(f"""
            FontIconToggleButton {{
                background: transparent;
                border: none;
                border-radius: 2px;
                color: {text_secondary};
                padding: 5px 0;
            }}
            FontIconToggleButton:hover {{
                background: {hover_bg};
                color: {text_primary};
            }}
            FontIconToggleButton:checked {{
                color: {text_primary};
            }}
            FontIconToggleButton:checked:hover {{
                background: {hover_bg};
            }}
        """)

    # 按钮类型常量
    Switch = "Switch"  # FontIconToggleButtonKeys.Switch
    Command = "Command"


# ── 复合控件：水平布局中的图标+文本 ──────────────────────────────────────

class FontIconTextBlockWithText(QWidget):
    """组合的 FontIcon + 文本标签

    用法：
        item = FontIconTextBlockWithText(FontIcons.Completed, "执行成功", color="#4caf50")
    """

    def __init__(self, icon: str, text: str, color: str = "#dcdcdc",
                 icon_size: int = 12, text_size: int = 11, parent=None):
        """初始化字体图标文本块（带文本）

        参数：
            icon: 图标字符
            text: 文本内容
            color: 颜色
            icon_size: 图标大小
            text_size: 文本大小
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 创建水平布局
        layout = QHBoxLayout(self)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为4像素
        layout.setSpacing(4)

        # 创建图标标签
        self.icon_label = FontIconTextBlock(icon, font_size=icon_size, color=color)
        # 添加到布局
        layout.addWidget(self.icon_label)

        # 创建文本标签
        self.text_label = QLabel(text)
        # 设置文本标签样式
        self.text_label.setStyleSheet(
            f"color: {color}; font-size: {text_size}px; background: transparent; border: none;"
        )
        # 添加到布局
        layout.addWidget(self.text_label)

    def set_text(self, text: str):
        """设置文本

        参数：
            text: 文本内容
        """
        # 更新文本标签
        self.text_label.setText(text)

    def set_color(self, color: str):
        """设置颜色

        参数：
            color: 颜色值
        """
        # 更新图标标签颜色
        self.icon_label.set_color(color)
        # 更新文本标签颜色
        self.text_label.setStyleSheet(
            f"color: {color}; font-size: {self.text_label.fontInfo().pixelSize()}px; "
            "background: transparent; border: none;"
        )
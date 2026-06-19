from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QPushButton

from core.constants import (
    ICON_CAMERA, ICON_PHOTO2, ICON_COLOR, ICON_IN_PRIVATE,
    ICON_ANNOTATION, ICON_HOME_GROUP, ICON_DIAL6, ICON_GOTO_TODAY,
    ICON_LARGE_ERASE, ICON_GENERIC_SCAN, ICON_NARRATOR_FORWARD,
    ICON_ETHERNET, ICON_COMMAND_PROMPT, ICON_MORE, ICON_VIDEO,
    ICON_FAVORITE_STAR,
)

from gui.theme import theme_manager, connect_theme


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
    Stop = ""                 # 停止
    Pause = ""                # 暂停
    Sync = ""                 # 同步
    Refresh = ""              # 刷新/重置
    Undo = ""                 # 撤销
    Redo = ""                 # 重做
    Delete = ""               # 删除/清空
    Cancel = ""               # 取消
    Add = ""                  # 添加
    Copy = ""                 # 复制
    Paste = ""                # 粘贴
    Save = ""                 # 保存
    OpenFile = ""             # 打开文件
    OpenFolderHorizontal = "" # 打开文件夹（水平）
    Edit = ""                 # 编辑
    EditMirrored = ""         # 编辑（镜像）
    Setting = ""              # 设置/齿轮
    Zoom = ""                 # 缩放/适应
    ZoomIn = ""               # 放大
    ZoomOut = ""              # 缩小
    FullScreen = ""           # 全屏
    View = ""                 # 视图/眼睛
    Page = ""                 # 页面/新建项目

    # ── 状态图标 ──
    Completed = ""           # 完成
    Error = ""               # 错误
    Info = ""                # 信息/关于
    Warning = ""             # 警告
    Help = ""                # 帮助
    Location = ""            # 位置/停止位置

    # ── 文件/对象图标 ──
    Photo2 = ICON_PHOTO2       # 照片
    Calendar = ""            # 日历
    Folder = ""              # 文件夹
    Document = ""            # 文档
    Video = ICON_VIDEO         # 视频
    Camera = ICON_CAMERA       # 相机
    OpenAs = ""              # 打开为

    # ── 节点分组图标 ──
    InPrivate = ICON_IN_PRIVATE              # 滤波模块 BlurDataGroup
    Annotation = ICON_ANNOTATION             # 图像分割提取 TakeoffDataGroup
    HomeGroup = ICON_HOME_GROUP              # 形态学模块 MorphologyDataGroup
    Dial6 = ICON_DIAL6                       # 逻辑模块 ConditionDataGroup
    GotoToday = ICON_GOTO_TODAY              # 模板匹配 TemplateMatchingDataGroup
    LargeErase = ICON_LARGE_ERASE            # 对象识别 DetectorDataGroup
    GenericScan = ICON_GENERIC_SCAN          # 特征识别 FeatureDetectorDataGroup
    NarratorForward = ICON_NARRATOR_FORWARD  # 网络通讯 NetworkDataGroup
    CommandPrompt = ICON_COMMAND_PROMPT      # Onnx通用模型 OnnxDataGroup
    More = ICON_MORE                         # 其他模块 OtherDataGroup

    # ── 布局/视图图标 ──
    AlignLeft = ""                     # 左对齐
    AlignCenter = ""                   # 居中对齐
    CaretBottomRightSolidCenter8 = ""  # 右下角实心箭头
    DisconnectDrive = ""               # 断开连接/删除节点

    # ── 工具图标 ──
    Color = ICON_COLOR         # 调色板/主题
    Brightness = ""          # 太阳/亮度
    QuietHours = ""          # 月亮/夜间模式
    Crop = ""                # 裁剪
    Cut = ""                 # 剪切
    Filter = ""              # 过滤
    DictionaryAdd = ""       # 从模板添加
    Manage = ""              # 管理/模板管理器
    SaveAs = ""              # 另存为模板
    Ethernet = ICON_ETHERNET   # 运行模式

    # ── 窗口控制图标 ──
    ChromeMinimize = ""      # 最小化
    ChromeMaximize = ""      # 最大化
    ChromeRestore = ""       # 还原
    ChromeClose = ""         # 关闭

    # ── 鼠标/引导图标 ──
    Mouse = ""               # 鼠标/向导
    Smartcard = ""           # Reminder / 新手向导

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
    FavoriteStar = ICON_FAVORITE_STAR        # 实心星形（收藏）
    FavoriteStarOutline = ""               # 空心星形（收藏轮廓）
    Pin = ""                               # 图钉（固定）
    Unpin = ""                             # 取消固定
    Like = ""                              # 点赞
    Dislike = ""                           # 点踩
    Flag = ""                              # 标记

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


class FontIconButton(QPushButton):
    def __init__(self, icon: str = "", text: str = "", tooltip: str = "",
                 font_size: int = 16, parent=None):
        """
        初始化字体图标按钮
        参数：
            icon: 图标字符
            text: 按钮文本
            tooltip: 工具提示
            font_size: 字体大小
            parent: 父对象
        """
        super().__init__(parent)
        self._icon = icon
        self._label_text = text
        self._icon_size = font_size
        self._icon_only = not bool(text)  # 是否为仅图标模式

        if text:
            self.setText(f"{icon}  {text}" if icon else text)  # 设置文本为"图标  文本"
        else:
            self.setText(icon)                                 # 只设置图标

        # 设置字体（使用系统字体，不需要特殊图标字体）
        font = QFont("Segoe MDL2 Assets", font_size)
        font.setPixelSize(font_size)
        self.setFont(font)

        if tooltip:                   # 如果有工具提示
            self.setToolTip(tooltip)  # 设置工具提示

        if self._icon_only:            # 如果是仅图标模式
            self.setFixedSize(35, 35)  # 设置固定大小为35x35

        self.setCursor(Qt.PointingHandCursor)  # 设置光标为手指形状
        self._apply_style()                    # 应用样式
        connect_theme(self._refresh_qss)       # 连接主题变化信号

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


    def _refresh_qss(self):
        """主题变化时重新应用 QSS"""
        self._apply_style()


class FontIconToggleButton(QPushButton):
    """
    可切换的字体图标按钮
    参数：
        checked_icon: 选中状态显示的图标
        unchecked_icon: 未选中状态显示的图标
        text: 图标旁的可选标签
        font_size: 图标字体像素大小
    """

    def __init__(self, checked_icon: str = "", unchecked_icon: str = "",
                 text: str = "", font_size: int = 16, parent=None):
        """
        初始化可切换字体图标按钮
        参数：
            checked_icon: 选中时显示的图标
            unchecked_icon: 未选中时显示的图标
            text: 按钮文本
            font_size: 字体大小
            parent: 父对象
        """
        super().__init__(parent)
        self._checked_icon = checked_icon                    # 保存选中图标
        self._unchecked_icon = unchecked_icon                # 保存未选中图标
        self._label_text = text                              # 保存文本标签
        self._icon_size = font_size                          # 保存图标大小
        self.setCheckable(True)                              # 设置按钮可选中
        self.setChecked(True)                                # 默认设为选中状态
        self.setFont(icon_font(font_size))                   # 设置字体
        self.setCursor(Qt.PointingHandCursor)                # 设置光标为手指形状
        self.setFixedSize(35, 35)                            # 固定尺寸，与 FontIconButton 保持一致
        self._update_text()                                  # 更新按钮文本
        self.toggled.connect(lambda _: self._update_text())  # 连接切换信号
        self._apply_style()                                  # 应用样式
        connect_theme(self._refresh_qss)                     # 连接主题变化信号

    def _update_text(self):
        """更新按钮文本"""
        icon = self._checked_icon if self.isChecked() else self._unchecked_icon # 根据选中状态选择图标
        if self._label_text: # 如果有文本标签
            self.setText(f"{icon}  {self._label_text}") # 设置文本为"图标  文本"
        else:
            self.setText(icon) # 只设置图标

    def set_checked_icon(self, icon: str):
        """
        设置选中时的图标
        参数：
            icon: 图标字符
        """
        self._checked_icon = icon  # 保存选中图标
        self._update_text()        # 更新文本

    def set_unchecked_icon(self, icon: str):
        """
        设置未选中时的图标
        参数：
            icon: 图标字符
        """
        self._unchecked_icon = icon  # 保存未选中图标
        self._update_text()          # 更新文本

    def _refresh_qss(self):
        """主题变化时重新应用 QSS"""
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


def icon_font(size: int = 12) -> QFont:
    """
    创建配置好的图标字体 QFont
    参数：
        size: 字体像素大小

    返回：
        配置好的 QFont 对象
    """
    font = QFont("Segoe MDL2 Assets")  # 直接使用固定字体
    font.setPixelSize(size)
    font.setStyleStrategy(QFont.PreferAntialias)
    return font
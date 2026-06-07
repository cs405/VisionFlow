"""FontIcon system

This module provides:
  - FontIcons: constant class mapping all icon names to Unicode codepoints
  - FontIconButton: QPushButton rendered with icon font
  - FontIconToggleButton: checkable button with checked/unchecked glyphs
  - FontIconTextBlock: QLabel rendered with icon font
  - icon font loading with fallback

Usage:
    btn = FontIconButton(FontIcons.Replay, "启动", parent)
    toggle = FontIconToggleButton(FontIcons.AlignLeft, FontIcons.CaretBottomRightSolidCenter8, parent)
    label = FontIconTextBlock(FontIcons.Photo2, parent)
"""

from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QHBoxLayout
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QFontDatabase, QPainter

from gui.theme import theme_manager, connect_theme


# ── Font family resolution ──────────────────────────────────────────────────

def _detect_icon_font() -> str:
    """Detect available Segoe icon font family on Windows."""
    candidates = [
        "Segoe MDL2 Assets",
        "Segoe Fluent Icons",     # Win11 new — many glyphs differ or missing
        "Segoe UI Symbol",        # last resort fallback
    ]
    for name in candidates:
        font = QFont(name)
        if font.exactMatch():
            return name
    # Fallback: try to find any Segoe icon font
    db = QFontDatabase()
    for family in db.families():
        if "segoe" in family.lower() and ("icon" in family.lower() or "symbol" in family.lower() or "mdl2" in family.lower()):
            return family
    return "Segoe UI Symbol"  # last-resort fallback


ICON_FONT_FAMILY = _detect_icon_font()


def icon_font(size: int = 12) -> QFont:
    """Create a QFont configured for icon rendering."""
    font = QFont(ICON_FONT_FAMILY)
    font.setPixelSize(size)
    font.setStyleStrategy(QFont.PreferAntialias)
    return font


# ── FontIcons ─────────────────────────────────────

class FontIcons:
    """Static icon constants

    Each constant maps a icon name to its Unicode codepoint in Segoe Fluent Icons /
    Segoe MDL2 Assets font.  Codepoints are derived from Windows 11 Segoe Fluent Icons
    character map

    """

    # ── Navigation ──
    GlobalNavButton = ""
    ChevronLeft = ""
    ChevronRight = ""
    ChevronUp = ""
    ChevronDown = ""
    PageLeft = ""
    PageRight = ""

    # ── Actions ──
    Replay = ""                #  — run / start
    Play = ""
    Stop = ""
    Pause = ""
    Sync = ""
    Refresh = ""              #  — reset
    Undo = ""
    Redo = ""
    Delete = ""               #  — trash / clear
    Cancel = ""
    Add = ""
    Copy = ""
    Paste = ""
    Save = ""                 # 
    OpenFile = ""             # 
    OpenFolderHorizontal = "" # 
    Edit = ""                 # 
    EditMirrored = ""         # 
    Setting = ""              #  — gear / settings
    Zoom = ""                 #  — zoom/fit
    ZoomIn = ""
    ZoomOut = ""
    FullScreen = ""
    View = ""                 #  — eye/show view
    Page = ""                 #  — new page/project

    # ── Status ──
    Completed = ""
    Error = ""
    Info = ""                 #  — info/about
    Warning = ""
    Help = ""
    Location = ""             #  — stop location

    # ── Files / Objects ──
    Photo2 = ""
    Calendar = ""
    Folder = ""
    Document = ""
    Video = ""
    Camera = ""
    OpenAs = ""

    # ── node group icons  ──
    InPrivate = ""          # 滤波模块 BlurDataGroup
    Annotation = ""         # 图像分割提取 TakeoffDataGroup
    HomeGroup = ""          # 形态学模块 MorphologyDataGroup
    Dial6 = ""              # 逻辑模块 ConditionDataGroup
    GotoToday = ""          # 模板匹配 TemplateMatchingDataGroup
    LargeErase = ""         # 对象识别 DetectorDataGroup
    GenericScan = ""        # 特征识别 FeatureDetectorDataGroup
    NarratorForward = ""    # 网络通讯 NetworkDataGroup
    CommandPrompt = ""      # Onnx通用模型 OnnxDataGroup
    More = ""               # 其他模块 OtherDataGroup

    # ── Layout / Views ──
    AlignLeft = ""
    AlignCenter = ""           # 
    CaretBottomRightSolidCenter8 = ""
    DisconnectDrive = ""      #  — delete/remove node

    # ── Tools ──
    Color = ""                 #  — color palette / theme
    Brightness = ""           #  — sun / brightness
    QuietHours = ""           #  — moon / night
    Crop = ""
    Cut = ""
    Filter = ""
    DictionaryAdd = ""       #  — add from template
    Manage = ""              #  — manage/template manager
    SaveAs = ""              #  — save as template
    Ethernet = ""            #  — run mode

    # ── Window Chrome ──
    ChromeMinimize = ""       # 
    ChromeMaximize = ""       # 
    ChromeRestore = ""        # 
    ChromeClose = ""          # 

    # ── Mouse / Guide ──
    Mouse = ""                #  — guide/wizard
    Smartcard = ""            #  — ShowGuideCommand icon (alias)

    # ── Power / System ──
    PowerButton = ""

    # ── Communication ──
    Mail = ""
    Chat = ""
    Phone = ""
    WiFi = ""

    # ── Map ──
    MapPin = ""
    POI = ""

    # ── Contact / People ──
    Contact = ""
    People = ""
    Emoji = ""

    # ── Transport ──
    Bus = ""
    Car = ""

    # ── Fallbacks / Extra ──
    FavoriteStar = ""           # ★ solid star for favorites
    FavoriteStarOutline = ""    # ☆ outline star
    Pin = ""
    Unpin = ""
    Like = ""
    Dislike = ""
    Flag = ""

    # ── Expanded set from HeBianGu framework ──
    Home = ""
    Download = ""
    Upload = ""
    Print = ""
    Shop = ""
    World = ""
    Feedback = ""              # feedback/bug
    Heart = ""
    Share = ""
    Link = ""


# ── FontIcon presenter controls ─────────────────────────────────────────────

class FontIconTextBlock(QLabel):
    """QLabel rendered in icon font."""

    def __init__(self, text: str = "", font_size: int = 12,
                 color: str = "", parent=None):
        super().__init__(text, parent)
        self._icon_text = text
        self._icon_size = font_size
        self._icon_color = color
        self._apply_style()
        self.setText(text)

    def setText(self, text: str):
        super().setText(text)
        self._icon_text = text
        self._apply_style()

    def set_icon(self, icon: str):
        """Set the icon glyph."""
        self.setText(icon)

    def set_color(self, color: str):
        """Set icon color via stylesheet."""
        self._icon_color = color
        self._apply_style()

    def _apply_style(self):
        """Apply icon font styling."""
        extra = f"color: {self._icon_color};" if self._icon_color else ""
        self.setFont(icon_font(self._icon_size))
        self.setStyleSheet(
            f"FontIconTextBlock {{ background: transparent; border: none; {extra} }}"
        )


class FontIconButton(QPushButton):
    """button with icon font glyph.

    Supports: icon-only mode, icon+text mode, tooltip, and Command style.
    """

    def __init__(self, icon: str = "", text: str = "", tooltip: str = "",
                 font_size: int = 16, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._icon_size = font_size
        self._label_text = text
        self._icon_only = not bool(text)

        if text:
            self.setText(f"{icon}  {text}" if icon else text)
        else:
            self.setText(icon)

        self.setFont(icon_font(font_size))
        if tooltip:
            self.setToolTip(tooltip)

        if self._icon_only:
            self.setFixedSize(35, 35)

        self.setCursor(Qt.PointingHandCursor)
        self._apply_style()
        connect_theme(self._refresh_qss)

    def set_icon(self, icon: str):
        self._icon = icon
        if self._label_text:
            self.setText(f"{icon}  {self._label_text}")
        else:
            self.setText(icon)

    def _refresh_qss(self):
        """Re-apply QSS on theme change."""
        self._apply_style()

    def _apply_style(self):
        text_primary = theme_manager.color('text_primary').name()
        hover_bg = theme_manager.color('bg_surface_hover').name()
        accent = theme_manager.color('accent').name()
        text_secondary = theme_manager.color('text_secondary').name()
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

    Command = "Command"   # FontIconButtonKeys.Command
    Default = "Default"   # FontIconButtonKeys.Default


class FontIconToggleButton(QPushButton):
    """
    Args:
        checked_icon: icon shown when checked
        unchecked_icon: icon shown when unchecked
        text: optional label beside the icon
        font_size: icon font pixel size
    """

    def __init__(self, checked_icon: str = "", unchecked_icon: str = "",
                 text: str = "", font_size: int = 16, parent=None):
        super().__init__(parent)
        self._checked_icon = checked_icon
        self._unchecked_icon = unchecked_icon
        self._label_text = text
        self._icon_size = font_size

        self.setCheckable(True)
        self.setChecked(True)
        self.setFont(icon_font(font_size))
        self.setCursor(Qt.PointingHandCursor)
        self._update_text()
        self.toggled.connect(lambda _: self._update_text())
        self._apply_style()
        connect_theme(self._refresh_qss)

    def _update_text(self):
        icon = self._checked_icon if self.isChecked() else self._unchecked_icon
        if self._label_text:
            self.setText(f"{icon}  {self._label_text}")
        else:
            self.setText(icon)

    def set_checked_icon(self, icon: str):
        self._checked_icon = icon
        self._update_text()

    def set_unchecked_icon(self, icon: str):
        self._unchecked_icon = icon
        self._update_text()

    def _refresh_qss(self):
        """Re-apply QSS on theme change."""
        self._apply_style()

    def _apply_style(self):
        text_secondary = theme_manager.color('text_secondary').name()
        hover_bg = theme_manager.color('bg_surface_hover').name()
        text_primary = theme_manager.color('text_primary').name()
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

    Switch = "Switch"  # FontIconToggleButtonKeys.Switch
    Command = "Command"


# ── Compound widget: icon + text in horizontal layout ──────────────────────

class FontIconTextBlockWithText(QWidget):
    """Combined FontIcon + text label

    Usage:
        item = FontIconTextBlockWithText(FontIcons.Completed, "执行成功", color="#4caf50")
    """

    def __init__(self, icon: str, text: str, color: str = "#dcdcdc",
                 icon_size: int = 12, text_size: int = 11, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.icon_label = FontIconTextBlock(icon, font_size=icon_size, color=color)
        layout.addWidget(self.icon_label)

        self.text_label = QLabel(text)
        self.text_label.setStyleSheet(
            f"color: {color}; font-size: {text_size}px; background: transparent; border: none;"
        )
        layout.addWidget(self.text_label)

    def set_text(self, text: str):
        self.text_label.setText(text)

    def set_color(self, color: str):
        self.icon_label.set_color(color)
        self.text_label.setStyleSheet(
            f"color: {color}; font-size: {self.text_label.fontInfo().pixelSize()}px; "
            "background: transparent; border: none;"
        )

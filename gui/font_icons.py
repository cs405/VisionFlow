"""FontIcon system — 1:1 port of WPF FontIcons static class + FontIcon presenter controls.

WPF uses Segoe Fluent Icons / MDL2 Assets font with Unicode codepoints for all UI icons.
This module provides:
  - FontIcons: constant class mapping all WPF icon names to Unicode codepoints
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


# ── Font family resolution ──────────────────────────────────────────────────

def _detect_icon_font() -> str:
    """Detect available Segoe icon font family on Windows."""
    candidates = [
        "Segoe Fluent Icons",
        "Segoe MDL2 Assets",
        "Segoe UI Symbol",
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


# ── WPF FontIcons 1:1 constant mapping ─────────────────────────────────────

class FontIcons:
    """Static icon constants matching WPF H.Controls.FontIcons class.

    Each constant maps a WPF icon name to its Unicode codepoint in Segoe Fluent Icons /
    Segoe MDL2 Assets font.  Codepoints are derived from Windows 11 Segoe Fluent Icons
    character map (verified against typical WPF HeBianGu framework constants).

    Naming convention matches WPF exactly: PascalCase icon names.
    """

    # ── Navigation ──
    GlobalNavButton = ""
    ChevronLeft = ""
    ChevronRight = ""
    ChevronUp = ""
    ChevronDown = ""
    PageLeft = ""
    PageRight = ""

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

    # ── Layout / Views ──
    AlignLeft = ""
    AlignCenter = ""           # 
    CaretBottomRightSolidCenter8 = ""
    DisconnectDrive = ""      #  — delete/remove node

    # ── Tools ──
    Color = ""                 #  — color palette / theme
    Crop = ""
    Cut = ""
    Filter = ""

    # ── Window Chrome ──
    ChromeMinimize = ""       # 
    ChromeMaximize = ""       # 
    ChromeRestore = ""        # 
    ChromeClose = ""          # 

    # ── Mouse / Guide ──
    Mouse = ""                #  — guide/wizard

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
    """WPF FontIconTextBlock equivalent — QLabel rendered in icon font."""

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
    """WPF FontIconButton equivalent — button with icon font glyph.

    Supports: icon-only mode, icon+text mode, tooltip, and WPF Command style.
    Corresponds to WPF `<FontIconButton Content="{x:Static FontIcons.xxx}" />`.
    """

    def __init__(self, icon: str = "", text: str = "", tooltip: str = "",
                 font_size: int = 14, parent=None):
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
            self.setFixedSize(34, 30)

        self.setCursor(Qt.PointingHandCursor)
        self._apply_style()

    def set_icon(self, icon: str):
        self._icon = icon
        if self._label_text:
            self.setText(f"{icon}  {self._label_text}")
        else:
            self.setText(icon)

    def _apply_style(self):
        self.setStyleSheet("""
            FontIconButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                color: #dcdcdc;
                padding: 3px 8px;
            }
            FontIconButton:hover {
                background: #3e3e42;
                border-color: #505050;
            }
            FontIconButton:pressed {
                background: #0078d4;
                border-color: #0078d4;
                color: white;
            }
            FontIconButton:disabled {
                color: #666;
                background: transparent;
            }
        """)

    # Support WPF-like style key pattern
    Command = "Command"   # FontIconButtonKeys.Command
    Default = "Default"   # FontIconButtonKeys.Default


class FontIconToggleButton(QPushButton):
    """WPF FontIconToggleButton equivalent — checkable button with dual glyphs.

    Matches WPF `<FontIconToggleButton CheckedGlyph="..." UncheckedGlyph="..." />`.

    Args:
        checked_icon: icon shown when checked
        unchecked_icon: icon shown when unchecked
        text: optional label beside the icon
        font_size: icon font pixel size
    """

    def __init__(self, checked_icon: str = "", unchecked_icon: str = "",
                 text: str = "", font_size: int = 14, parent=None):
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

    def _apply_style(self):
        self.setStyleSheet("""
            FontIconToggleButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                color: #999;
                padding: 3px 8px;
            }
            FontIconToggleButton:hover {
                background: #3e3e42;
                color: #dcdcdc;
            }
            FontIconToggleButton:checked {
                color: #dcdcdc;
            }
            FontIconToggleButton:checked:hover {
                background: #3e3e42;
            }
        """)

    # WPF style key constants
    Switch = "Switch"  # FontIconToggleButtonKeys.Switch
    Command = "Command"


# ── Compound widget: icon + text in horizontal layout ──────────────────────

class FontIconTextBlockWithText(QWidget):
    """Combined FontIcon + text label, matching WPF patterns like status bar items.

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

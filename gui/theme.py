"""
VisionFlow 暗色主题 — WPF VisionMaster风格
统一管理所有颜色、字体和样式常量
"""

from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt

# ========== 颜色常量 ==========

class Colors:
    # 主背景色
    Background = "#1E1E1E"
    BackgroundDark = "#252526"
    BackgroundLight = "#2D2D2D"

    # 边框
    Border = "#3D3D3D"
    BorderLight = "#4A4A4A"
    BorderTitle = "#3D3D3D"

    # 前景/文字
    Foreground = "#E0E0E0"
    ForegroundDim = "#A0A0A0"
    ForegroundDark = "#808080"

    # 强调色
    Accent = "#4A6A9A"
    AccentLight = "#5A7AAA"
    AccentDark = "#3A5A8A"

    # 状态色
    Green = "#4CAF50"
    Orange = "#FF9800"
    Red = "#F44336"
    Blue = "#2196F3"

    # 节点颜色 (分类)
    NodeIO = QColor(40, 60, 50)
    NodeIO_Header = QColor(60, 100, 70)
    NodePreprocessing = QColor(50, 50, 60)
    NodePreprocessing_Header = QColor(70, 70, 100)
    NodeFeature = QColor(60, 50, 50)
    NodeFeature_Header = QColor(100, 70, 70)
    NodeMatch = QColor(50, 50, 50)
    NodeMatch_Header = QColor(80, 80, 100)
    NodeMeasurement = QColor(50, 60, 60)
    NodeMeasurement_Header = QColor(70, 100, 100)
    NodeEnhance = QColor(60, 50, 40)
    NodeEnhance_Header = QColor(100, 80, 60)
    NodeGeometry = QColor(50, 50, 55)
    NodeGeometry_Header = QColor(80, 80, 90)
    NodeColor = QColor(55, 45, 55)
    NodeColor_Header = QColor(90, 70, 90)
    NodeDefault = QColor(50, 50, 60)
    NodeDefault_Header = QColor(70, 70, 100)

    # 棋盘格背景 (Tile25)
    Tile25_Dark = QColor(30, 30, 30)
    Tile25_Light = QColor(40, 40, 40)

    # 场景背景
    SceneBackground = QColor(35, 35, 35)
    GridMinor = QColor(50, 50, 50)
    GridMajor = QColor(65, 65, 65)


# ========== 字体常量 ==========

class Fonts:
    Family = "Microsoft YaHei"
    FamilyMono = "Consolas"

    @staticmethod
    def make(size=11, bold=False):
        font = QFont(Fonts.Family, size)
        font.setBold(bold)
        return font

    @staticmethod
    def make_mono(size=10):
        return QFont(Fonts.FamilyMono, size)


# ========== 全局样式表 (QSS) ==========

GLOBAL_STYLESHEET = """
/* 主窗口 */
QMainWindow {
    background-color: #1E1E1E;
}

/* 菜单栏 */
QMenuBar {
    background-color: #2D2D2D;
    color: #E0E0E0;
    border-bottom: 1px solid #3D3D3D;
    font: 12px "Microsoft YaHei";
    padding: 2px;
}
QMenuBar::item {
    padding: 4px 10px;
    background: transparent;
    border-radius: 3px;
}
QMenuBar::item:selected {
    background-color: #4A6A9A;
}

/* 菜单 */
QMenu {
    background-color: #2D2D2D;
    color: #E0E0E0;
    border: 1px solid #3D3D3D;
    font: 12px "Microsoft YaHei";
    padding: 4px;
}
QMenu::item {
    padding: 6px 30px 6px 20px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #4A6A9A;
}
QMenu::separator {
    height: 1px;
    background-color: #3D3D3D;
    margin: 5px 10px;
}

/* 工具栏 */
QToolBar {
    background-color: #2D2D2D;
    border: none;
    border-bottom: 1px solid #3D3D3D;
    spacing: 4px;
    padding: 2px;
}
QToolBar QToolButton {
    background-color: transparent;
    color: #E0E0E0;
    border: none;
    border-radius: 4px;
    padding: 5px 10px;
    font: 11px "Microsoft YaHei";
}
QToolBar QToolButton:hover {
    background-color: #4A4A4A;
}
QToolBar QToolButton:pressed {
    background-color: #4A6A9A;
}

/* 状态栏 */
QStatusBar {
    background-color: #2D2D2D;
    color: #A0A0A0;
    border-top: 1px solid #3D3D3D;
    font: 11px "Microsoft YaHei";
}

/* 停靠窗口 */
QDockWidget {
    titlebar-close-icon: url(none);
    titlebar-normal-icon: url(none);
    color: #E0E0E0;
}
QDockWidget::title {
    background-color: #2D2D2D;
    color: #E0E0E0;
    padding: 6px;
    font: bold 12px "Microsoft YaHei";
    border-bottom: 1px solid #3D3D3D;
}

/* 树形控件 */
QTreeWidget {
    background-color: #252526;
    color: #E0E0E0;
    border: none;
    font: 11px "Microsoft YaHei";
    outline: 0;
}
QTreeWidget::item {
    padding: 4px 2px;
    border-radius: 2px;
}
QTreeWidget::item:hover {
    background-color: #2A2D2E;
}
QTreeWidget::item:selected {
    background-color: #4A6A9A;
}

/* 标签页 */
QTabWidget::pane {
    background-color: #1E1E1E;
    border: none;
}
QTabBar::tab {
    background-color: #2D2D2D;
    color: #A0A0A0;
    padding: 8px 16px;
    font: 11px "Microsoft YaHei";
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    color: #FFFFFF;
    border-bottom: 2px solid #4A6A9A;
}
QTabBar::tab:hover:!selected {
    background-color: #3D3D3D;
    color: #E0E0E0;
}

/* 分割器 */
QSplitter::handle {
    background-color: #3D3D3D;
    width: 2px;
    height: 2px;
}
QSplitter::handle:hover {
    background-color: #4A6A9A;
}

/* 滚动条 */
QScrollBar:vertical {
    background-color: #1E1E1E;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background-color: #4A4A4A;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #5A5A5A;
}
QScrollBar:horizontal {
    background-color: #1E1E1E;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background-color: #4A4A4A;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #5A5A5A;
}

/* 分组框 */
QGroupBox {
    color: #E0E0E0;
    font: bold 11px "Microsoft YaHei";
    border: 1px solid #3D3D3D;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 16px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #E0E0E0;
}

/* 标签 */
QLabel {
    color: #E0E0E0;
    font: 11px "Microsoft YaHei";
}

/* 输入框 */
QLineEdit {
    background-color: #3D3D3D;
    color: #E0E0E0;
    border: 1px solid #4A4A4A;
    border-radius: 3px;
    padding: 4px 8px;
    font: 11px "Microsoft YaHei";
}
QLineEdit:focus {
    border-color: #4A6A9A;
}

/* 下拉框 */
QComboBox {
    background-color: #3D3D3D;
    color: #E0E0E0;
    border: 1px solid #4A4A4A;
    border-radius: 3px;
    padding: 4px 8px;
    font: 11px "Microsoft YaHei";
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #2D2D2D;
    color: #E0E0E0;
    border: 1px solid #3D3D3D;
    selection-background-color: #4A6A9A;
}

/* 数字输入框 */
QSpinBox, QDoubleSpinBox {
    background-color: #3D3D3D;
    color: #E0E0E0;
    border: 1px solid #4A4A4A;
    border-radius: 3px;
    padding: 4px;
    font: 11px "Microsoft YaHei";
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #4A6A9A;
}

/* 按钮 */
QPushButton {
    background-color: #4A6A9A;
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    font: 11px "Microsoft YaHei";
}
QPushButton:hover {
    background-color: #5A7AAA;
}
QPushButton:pressed {
    background-color: #3A5A8A;
}

/* 复选框 */
QCheckBox {
    color: #E0E0E0;
    font: 11px "Microsoft YaHei";
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #4A4A4A;
    border-radius: 2px;
    background-color: #3D3D3D;
}
QCheckBox::indicator:checked {
    background-color: #4A6A9A;
    border-color: #4A6A9A;
}

/* 表格 */
QTableWidget {
    background-color: #252526;
    color: #E0E0E0;
    border: none;
    gridline-color: #3D3D3D;
    font: 11px "Microsoft YaHei";
}
QTableWidget::item:selected {
    background-color: #4A6A9A;
}
QHeaderView::section {
    background-color: #2D2D2D;
    color: #E0E0E0;
    border: none;
    border-right: 1px solid #3D3D3D;
    border-bottom: 1px solid #3D3D3D;
    padding: 6px;
    font: bold 11px "Microsoft YaHei";
}

/* 进度条 */
QProgressBar {
    background-color: #3D3D3D;
    border: none;
    border-radius: 2px;
    height: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #4A6A9A;
    border-radius: 2px;
}

/* 滑块 */
QSlider::groove:horizontal {
    background-color: #3D3D3D;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background-color: #4A6A9A;
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}
QSlider::handle:horizontal:hover {
    background-color: #5A7AAA;
}

/* 文本编辑器 */
QTextEdit {
    background-color: #1E1E1E;
    color: #E0E0E0;
    border: none;
    font: 10px "Consolas";
}
"""

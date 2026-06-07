"""Guide overlay

Semi-transparent overlay covering the main window, with a "hole" highlighting
the current step's target widget, and a floating popup with instructions.

Usage:
    overlay = GuideOverlay(main_window, steps=[
        {"title": "新建项目", "desc": "点击这里创建新项目", "widget": some_btn},
        {"title": "工具箱",   "desc": "从这里拖拽节点到画布", "widget": toolbox},
    ])
    overlay.start()
"""

from PyQt5.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout,
                               QHBoxLayout)
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import (QPainter, QPen, QColor, QBrush, QPainterPath)


class GuideOverlay(QWidget):
    """Modal overlay guiding users through UI features.
    """

    finished = pyqtSignal()

    def __init__(self, parent, steps: list[dict] = None):
        super().__init__(parent)
        self._parent = parent
        self._steps = steps or []
        self._current = 0
        self._popup = None
        self._target_widget = None

        self.setWindowFlags(Qt.Widget | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setGeometry(parent.rect())

        self._setup_popup()

    # ── Popup ───────────────────────────────────────────────────────────

    def _setup_popup(self):
        self._popup = QWidget(self)
        self._popup.setObjectName("guide_popup")
        self._popup.setFixedWidth(320)
        self._popup.setStyleSheet(
            "QWidget#guide_popup { background: #2d2d30; border: 2px solid #FF8C00;"
            " border-radius: 8px; }")

        layout = QVBoxLayout(self._popup)
        layout.setSpacing(8)

        # Step counter
        self._step_lbl = QLabel()
        self._step_lbl.setStyleSheet(
            "color: #FF8C00; font-size: 20px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(self._step_lbl)

        # Title
        self._title_lbl = QLabel()
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setStyleSheet(
            "color: #dcdcdc; font-size: 15px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(self._title_lbl)

        # Description
        self._desc_lbl = QLabel()
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet(
            "color: #aaa; font-size: 12px; border: none; background: transparent; line-height: 1.5;")
        layout.addWidget(self._desc_lbl)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        self._skip_btn = QPushButton("跳过")
        self._skip_btn.setStyleSheet(
            "QPushButton { color: #999; background: transparent; border: none; "
            "font-size: 12px; padding: 6px 12px; }"
            "QPushButton:hover { color: #dcdcdc; }")
        self._skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(self._skip_btn)

        btn_row.addStretch()

        self._next_btn = QPushButton("下一步 →")
        self._next_btn.setStyleSheet(
            "QPushButton { color: white; background: #FF8C00; border: none; "
            "border-radius: 4px; padding: 8px 20px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #FFA726; }")
        self._next_btn.clicked.connect(self._on_next)
        self._next_btn.setDefault(True)
        btn_row.addWidget(self._next_btn)

        layout.addLayout(btn_row)

    # ── Step management ─────────────────────────────────────────────────

    def add_step(self, title: str, desc: str, widget: QWidget = None,
                 finder: callable = None):
        """Add a step. Either pass widget directly, or a finder callable."""
        self._steps.append({"title": title, "desc": desc,
                            "widget": widget, "finder": finder})

    def _show_step(self, index: int):
        if index >= len(self._steps):
            self._on_finish()
            return
        self._current = index
        step = self._steps[index]
        self._target_widget = step.get("widget")
        if self._target_widget is None and step.get("finder"):
            self._target_widget = step["finder"]()

        self._step_lbl.setText(f"●  {index + 1} / {len(self._steps)}")
        self._title_lbl.setText(step["title"])
        self._desc_lbl.setText(step["desc"])

        if index == len(self._steps) - 1:
            self._next_btn.setText("完成 ✓")
            self._skip_btn.hide()

        self._position_popup()
        self.update()

    def _position_popup(self):
        try:
            if self._target_widget is None:
                return
            pos = self._target_widget.mapTo(self._parent, QPoint(0, 0))
            size = self._target_widget.size()
            x = pos.x() + size.width() + 20
            y = pos.y()
            popup_w = self._popup.width()
            popup_h = max(self._popup.sizeHint().height(), 120)
            pw = self._parent.width()
            ph = self._parent.height()
            if x + popup_w > pw - 20:
                x = pos.x() - popup_w - 20
            if y + popup_h > ph - 20:
                y = ph - popup_h - 20
            if y < 10:
                y = 10
            if x < 10:
                x = 10
            self._popup.move(x, y)
            self._popup.adjustSize()
            self._popup.show()
            self._popup.raise_()
        except Exception:
            pass

    # ── Navigation ──────────────────────────────────────────────────────

    def _on_next(self):
        self._show_step(self._current + 1)

    def _on_skip(self):
        self._on_finish()

    def _on_finish(self):
        self._popup.hide()
        self.hide()
        self.finished.emit()

    # ── Overlay ─────────────────────────────────────────────────────────

    def start(self):
        if not self._steps:
            return
        self._parent.installEventFilter(self)
        self.show()
        self.raise_()
        self._show_step(0)

    def eventFilter(self, obj, event):
        # Keep overlay on top when parent resizes
        if obj is self._parent and event.type() == event.Resize:
            self.setGeometry(self._parent.rect())
            self._position_popup()
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setBrush(QColor(0, 0, 0, 180))
            painter.setPen(Qt.NoPen)
            if self._target_widget is not None:
                try:
                    pos = self._target_widget.mapTo(self._parent, QPoint(0, 0))
                    size = self._target_widget.size()
                    hole = QRect(pos, size).adjusted(-4, -4, 4, 4)
                    path = QPainterPath()
                    path.addRect(self.rect())
                    path.addRoundedRect(QRect(hole), 6, 6)
                    painter.drawPath(path)
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(QColor("#FF8C00"), 3))
                    painter.drawRoundedRect(QRect(hole), 6, 6)
                except Exception:
                    painter.drawRect(self.rect())
            else:
                painter.drawRect(self.rect())
        except Exception:
            pass

    # ── Static factory for common guides ────────────────────────────────

    @staticmethod
    def create_app_guide(main_window) -> "GuideOverlay":
        """Create a standard application guide for VisionFlow."""
        from gui.font_icons import FontIconButton
        overlay = GuideOverlay(main_window)

        # Helper: find any button by tooltip text
        def _find_btn(tip):
            for w in main_window.findChildren(QWidget):
                try:
                    if w.toolTip() == tip and w.isVisible():
                        return w
                except Exception:
                    pass
            return None

        overlay.add_step(
            "创建项目",
            "点击「新建项目」按钮创建一个新的视觉检测项目。\n项目用于组织流程图、图像和设置。",
            finder=lambda: _find_btn("新建项目"))

        overlay.add_step(
            "节点工具箱",
            "左侧工具箱列出了所有可用的视觉处理节点。\n拖拽节点到画布上即可开始构建流程图。",
            finder=lambda: _find_btn("工具箱") or _find_btn("搜索节点..."))

        overlay.add_step(
            "切换主题",
            "点击调色板按钮可以选择不同的颜色主题。\n支持深色、浅色、科技蓝等多种风格。",
            finder=lambda: _find_btn("颜色主题"))

        overlay.add_step(
            "运行流程图",
            "构建好流程图后，点击「开始」按钮运行整个流程。\n结果将显示在右侧面板中。",
            finder=lambda: _find_btn("开始"))

        return overlay

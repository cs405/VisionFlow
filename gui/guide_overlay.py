"""引导覆盖层

半透明覆盖层 + 目标控件聚光灯高亮 + 浮动弹窗。

高亮策略：用 QGraphicsColorizeEffect 直接在目标控件上叠加白色，
完全避免 Windows 子控件 alpha 合成不可靠的问题。

用法：
    overlay = GuideOverlay(main_window)
    overlay.add_step("标题", "描述", widget=target)
    overlay.start()
"""

from PyQt5.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout,
                               QHBoxLayout, QGraphicsColorizeEffect)
from PyQt5.QtCore import Qt, QEvent, QRect, QPoint, QRectF, pyqtSignal
from PyQt5.QtGui import (QPainter, QPen, QColor)


class GuideOverlay(QWidget):
    """引导覆盖层"""

    finished = pyqtSignal()

    def __init__(self, parent, steps: list[dict] = None):
        super().__init__(parent)
        self._parent = parent
        self._steps = steps or []
        self._current = 0
        self._popup = None
        self._target_widget = None
        self._prev_target = None       # 上一步的目标控件
        self._brighten_effect = None   # 提亮特效

        self.setWindowFlags(Qt.Widget | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setGeometry(parent.rect())

        self._setup_popup()

    def _setup_popup(self):
        self._popup = QWidget(self)
        self._popup.setObjectName("guide_popup")
        self._popup.setFixedWidth(320)
        self._popup.setStyleSheet(
            "QWidget#guide_popup { background: #2d2d30; border: 2px solid #FF8C00;"
            " border-radius: 8px; }")

        layout = QVBoxLayout(self._popup)
        layout.setSpacing(8)

        self._step_lbl = QLabel()
        self._step_lbl.setStyleSheet(
            "color: #FF8C00; font-size: 20px; font-weight: bold;"
            " border: none; background: transparent;")
        layout.addWidget(self._step_lbl)

        self._title_lbl = QLabel()
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setStyleSheet(
            "color: #dcdcdc; font-size: 15px; font-weight: bold;"
            " border: none; background: transparent;")
        layout.addWidget(self._title_lbl)

        self._desc_lbl = QLabel()
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet(
            "color: #aaa; font-size: 12px; border: none;"
            " background: transparent; line-height: 1.5;")
        layout.addWidget(self._desc_lbl)

        layout.addStretch()

        btn_row = QHBoxLayout()
        self._skip_btn = QPushButton("跳过")
        self._skip_btn.setStyleSheet(
            "QPushButton { color: #999; background: transparent; border: none;"
            " font-size: 12px; padding: 6px 12px; }"
            "QPushButton:hover { color: #dcdcdc; }")
        self._skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(self._skip_btn)

        btn_row.addStretch()

        self._next_btn = QPushButton("下一步 →")
        self._next_btn.setStyleSheet(
            "QPushButton { color: white; background: #FF8C00; border: none;"
            " border-radius: 4px; padding: 8px 20px; font-size: 13px;"
            " font-weight: bold; }"
            "QPushButton:hover { background: #FFA726; }")
        self._next_btn.clicked.connect(self._on_next)
        self._next_btn.setDefault(True)
        btn_row.addWidget(self._next_btn)

        layout.addLayout(btn_row)

    # ── 步骤管理 ─────────────────────────────────────────────────

    def add_step(self, title: str, desc: str, widget: QWidget = None,
                 finder = None):
        self._steps.append({"title": title, "desc": desc,
                            "widget": widget, "finder": finder})

    def _show_step(self, index: int):
        if index >= len(self._steps):
            self._on_finish()
            return
        self._current = index
        step = self._steps[index]

        # 清除上一步的提亮特效
        self._clear_brighten()

        self._target_widget = step.get("widget")
        if self._target_widget is None and step.get("finder"):
            self._target_widget = step["finder"]()

        # 在新目标上应用提亮特效
        self._apply_brighten()

        self._step_lbl.setText(f"●  {index + 1} / {len(self._steps)}")
        self._title_lbl.setText(step["title"])
        self._desc_lbl.setText(step["desc"])

        if index == len(self._steps) - 1:
            self._next_btn.setText("完成 ✓")
            self._skip_btn.hide()

        self._position_popup()
        self.update()

    def _apply_brighten(self):
        """在目标控件上叠加白色提亮"""
        if self._target_widget is None:
            return
        self._brighten_effect = QGraphicsColorizeEffect()
        self._brighten_effect.setColor(QColor(255, 255, 255))
        self._brighten_effect.setStrength(0.55)
        self._target_widget.setGraphicsEffect(self._brighten_effect)
        self._prev_target = self._target_widget

    def _clear_brighten(self):
        """清除上一次的提亮特效"""
        if self._prev_target is not None:
            self._prev_target.setGraphicsEffect(None)
            self._prev_target = None
        self._brighten_effect = None

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
            pw, ph = self._parent.width(), self._parent.height()
            if x + popup_w > pw - 20:
                x = pos.x() - popup_w - 20
            if y + popup_h > ph - 20:
                y = ph - popup_h - 20
            y = max(y, 10)
            x = max(x, 10)
            self._popup.move(x, y)
            self._popup.adjustSize()
            self._popup.show()
            self._popup.raise_()
        except Exception:
            pass

    # ── 导航 ──────────────────────────────────────────────────────

    def _on_next(self):
        self._show_step(self._current + 1)

    def _on_skip(self):
        self._on_finish()

    def _on_finish(self):
        self._clear_brighten()
        self._popup.hide()
        self.hide()
        self._parent.removeEventFilter(self)
        self.finished.emit()

    # ── 覆盖层 ─────────────────────────────────────────────────────────

    def start(self):
        if not self._steps:
            return
        self._parent.installEventFilter(self)
        self.show()
        self.raise_()
        self._show_step(0)

    def eventFilter(self, obj, event):
        if obj is self._parent and event.type() == QEvent.Resize:
            self.setGeometry(self._parent.rect())
            self._position_popup()
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._target_widget is not None:
            try:
                pos = self._target_widget.mapTo(self._parent, QPoint(0, 0))
                size = self._target_widget.size()
                pw, ph = self.width(), self.height()

                # 孔洞矩形（向外扩展 6px，裁剪到窗口范围内）
                x = max(0, pos.x() - 6)
                y = max(0, pos.y() - 6)
                r = min(pw, pos.x() + size.width() + 6)
                b = min(ph, pos.y() + size.height() + 6)
                hole = QRect(x, y, r - x, b - y)

                # 暗色遮罩（四块矩形围出孔洞）
                painter.setBrush(QColor(0, 0, 0, 180))
                painter.setPen(Qt.NoPen)
                if hole.top() > 0:
                    painter.drawRect(0, 0, pw, hole.top())
                if hole.bottom() < ph:
                    painter.drawRect(0, hole.bottom(), pw, ph - hole.bottom())
                if hole.left() > 0:
                    painter.drawRect(0, hole.top(), hole.left(), hole.height())
                if hole.right() < pw:
                    painter.drawRect(hole.right(), hole.top(),
                                     pw - hole.right(), hole.height())

                # 外发光
                glow = QColor("#FFA726")
                glow.setAlpha(80)
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(glow, 8))
                painter.drawRoundedRect(QRectF(hole), 8, 8)

                # 内边框
                painter.setPen(QPen(QColor("#FFB74D"), 3))
                painter.drawRoundedRect(QRectF(hole), 8, 8)
            except Exception:
                painter.setBrush(QColor(0, 0, 0, 180))
                painter.setPen(Qt.NoPen)
                painter.drawRect(self.rect())
        else:
            painter.setBrush(QColor(0, 0, 0, 180))
            painter.setPen(Qt.NoPen)
            painter.drawRect(self.rect())

    # ── 引导工厂方法 ────────────────────────────────────────────────

    @staticmethod
    def create_app_guide(main_window) -> "GuideOverlay":
        overlay = GuideOverlay(main_window)

        def _find_btn(tip):
            for w in main_window.findChildren(QWidget):
                try:
                    if w.toolTip() == tip and w.isVisible():
                        return w
                except Exception:
                    pass
            return None

        # ── 项目操作 ──
        overlay.add_step(
            "新建项目",
            "点击「新建项目」创建一个新的视觉检测项目，\n所有流程图、图像和设置都将组织在项目内。",
            finder=lambda: _find_btn("新建项目"))

        overlay.add_step(
            "保存项目",
            "完成编辑后点击「保存项目」将项目持久化到磁盘，\n支持 .json 格式，方便版本管理和协作。",
            finder=lambda: _find_btn("保存项目"))

        # ── 流程图构建 ──
        overlay.add_step(
            "节点工具箱",
            "左侧工具箱列出了所有可用的视觉处理节点，\n拖拽节点到画布上即可开始构建流程图。",
            finder=lambda: _find_btn("节点工具箱"))

        overlay.add_step(
            "新建流程图",
            "点击「新建流程图」可以在项目中创建多个流程，\n点击标签页即可在不同流程之间切换。",
            finder=lambda: _find_btn("新建流程图"))

        overlay.add_step(
            "流程图编辑区",
            "中央画布是流程图编辑区，在这里拖拽、连接节点，\n构建完整的视觉检测流水线。",
            finder=lambda: _find_btn("流程图标签页"))

        # ── 运行控制 ──
        overlay.add_step(
            "运行模式",
            "点击「运行模式」可以循环切换执行粒度：\n按节点 → 节点+连线 → 节点+连线+端口。",
            finder=lambda: _find_btn("运行模式"))

        overlay.add_step(
            "单次执行",
            "构建好流程图后，点击「单次执行」运行整个流程，\n每个节点依次执行，结果实时显示在右侧面板。",
            finder=lambda: _find_btn("单次执行"))

        overlay.add_step(
            "连续执行",
            "点击「连续执行」进入连续运行模式，\n流程将反复执行，适合实时监控场景。",
            finder=lambda: _find_btn("连续执行"))

        # ── 结果查看 ──
        overlay.add_step(
            "检查结果",
            "右侧上半部分是检查结果面板，\n包含图像预览和模块属性两个标签页。",
            finder=lambda: _find_btn("检查结果面板"))

        overlay.add_step(
            "运行结果",
            "右侧下半部分是运行结果面板，\n按时间线展示每次执行的输出和历史记录。",
            finder=lambda: _find_btn("运行结果面板"))

        # ── 个性化 ──
        overlay.add_step(
            "切换主题",
            "点击调色板按钮可以选择颜色主题，\n支持深色、浅色、科技蓝等多种风格。",
            finder=lambda: _find_btn("颜色主题"))

        overlay.add_step(
            "应用设置",
            "点击齿轮按钮打开设置对话框，\n可以配置画布网格、系统托盘等选项。",
            finder=lambda: _find_btn("设置"))

        return overlay

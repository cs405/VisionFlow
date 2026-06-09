"""引导覆盖层

覆盖主窗口的半透明覆盖层，有一个"孔"高亮当前步骤的目标控件，
以及一个带说明文字的浮动弹窗。

用法：
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
    """引导覆盖层，引导用户浏览UI功能。"""

    # 引导结束时发出的信号
    finished = pyqtSignal()

    def __init__(self, parent, steps: list[dict] = None):
        """初始化引导覆盖层

        参数：
            parent: 父窗口
            steps: 引导步骤列表
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 保存父窗口引用
        self._parent = parent
        # 保存引导步骤列表
        self._steps = steps or []
        # 当前步骤索引
        self._current = 0
        # 弹窗控件
        self._popup = None
        # 当前高亮的目标控件
        self._target_widget = None

        # 设置窗口标志为Widget + 无边框
        self.setWindowFlags(Qt.Widget | Qt.FramelessWindowHint)
        # 设置属性：不允许鼠标穿透
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        # 设置属性：无系统背景
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        # 设置属性：透明背景
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # 设置几何尺寸为父窗口的矩形
        self.setGeometry(parent.rect())

        # 设置弹窗
        self._setup_popup()

    # ── 弹窗 ───────────────────────────────────────────────────────────

    def _setup_popup(self):
        """设置弹窗控件"""
        # 创建弹窗控件，父对象为自身
        self._popup = QWidget(self)
        # 设置弹窗对象名（用于样式表选择器）
        self._popup.setObjectName("guide_popup")
        # 设置固定宽度320像素
        self._popup.setFixedWidth(320)
        # 设置弹窗样式表
        self._popup.setStyleSheet(
            "QWidget#guide_popup { background: #2d2d30; border: 2px solid #FF8C00;"
            " border-radius: 8px; }")

        # 创建垂直布局
        layout = QVBoxLayout(self._popup)
        # 设置布局间距
        layout.setSpacing(8)

        # 步骤计数器标签
        self._step_lbl = QLabel()
        # 设置样式
        self._step_lbl.setStyleSheet(
            "color: #FF8C00; font-size: 20px; font-weight: bold; border: none; background: transparent;")
        # 添加到布局
        layout.addWidget(self._step_lbl)

        # 标题标签
        self._title_lbl = QLabel()
        # 允许换行
        self._title_lbl.setWordWrap(True)
        # 设置样式
        self._title_lbl.setStyleSheet(
            "color: #dcdcdc; font-size: 15px; font-weight: bold; border: none; background: transparent;")
        # 添加到布局
        layout.addWidget(self._title_lbl)

        # 描述标签
        self._desc_lbl = QLabel()
        # 允许换行
        self._desc_lbl.setWordWrap(True)
        # 设置样式
        self._desc_lbl.setStyleSheet(
            "color: #aaa; font-size: 12px; border: none; background: transparent; line-height: 1.5;")
        # 添加到布局
        layout.addWidget(self._desc_lbl)

        # 添加弹性空间
        layout.addStretch()

        # 按钮行
        btn_row = QHBoxLayout()
        # 跳过按钮
        self._skip_btn = QPushButton("跳过")
        # 设置跳过按钮样式
        self._skip_btn.setStyleSheet(
            "QPushButton { color: #999; background: transparent; border: none; "
            "font-size: 12px; padding: 6px 12px; }"
            "QPushButton:hover { color: #dcdcdc; }")
        # 连接点击信号
        self._skip_btn.clicked.connect(self._on_skip)
        # 添加到按钮行
        btn_row.addWidget(self._skip_btn)

        # 添加弹性空间
        btn_row.addStretch()

        # 下一步按钮
        self._next_btn = QPushButton("下一步 →")
        # 设置下一步按钮样式
        self._next_btn.setStyleSheet(
            "QPushButton { color: white; background: #FF8C00; border: none; "
            "border-radius: 4px; padding: 8px 20px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #FFA726; }")
        # 连接点击信号
        self._next_btn.clicked.connect(self._on_next)
        # 设置为默认按钮（按回车时触发）
        self._next_btn.setDefault(True)
        # 添加到按钮行
        btn_row.addWidget(self._next_btn)

        # 添加按钮行到布局
        layout.addLayout(btn_row)

    # ── 步骤管理 ─────────────────────────────────────────────────

    def add_step(self, title: str, desc: str, widget: QWidget = None,
                 finder: callable = None):
        """添加一个引导步骤

        参数：
            title: 步骤标题
            desc: 步骤描述
            widget: 目标控件（直接传入）
            finder: 目标控件查找函数（返回QWidget）
        """
        # 将步骤添加到列表
        self._steps.append({"title": title, "desc": desc,
                            "widget": widget, "finder": finder})

    def _show_step(self, index: int):
        """显示指定索引的步骤

        参数：
            index: 步骤索引
        """
        # 如果索引超出范围，结束引导
        if index >= len(self._steps):
            self._on_finish()
            return
        # 保存当前索引
        self._current = index
        # 获取当前步骤
        step = self._steps[index]
        # 获取目标控件
        self._target_widget = step.get("widget")
        # 如果没有直接传入控件但有查找函数
        if self._target_widget is None and step.get("finder"):
            # 调用查找函数获取控件
            self._target_widget = step["finder"]()

        # 更新步骤计数器标签
        self._step_lbl.setText(f"●  {index + 1} / {len(self._steps)}")
        # 更新标题标签
        self._title_lbl.setText(step["title"])
        # 更新描述标签
        self._desc_lbl.setText(step["desc"])

        # 如果是最后一步
        if index == len(self._steps) - 1:
            # 按钮文本改为"完成 ✓"
            self._next_btn.setText("完成 ✓")
            # 隐藏跳过按钮
            self._skip_btn.hide()

        # 定位弹窗位置
        self._position_popup()
        # 触发重绘
        self.update()

    def _position_popup(self):
        """定位弹窗位置"""
        try:
            # 如果没有目标控件，返回
            if self._target_widget is None:
                return
            # 将目标控件的左上角映射到父窗口的坐标
            pos = self._target_widget.mapTo(self._parent, QPoint(0, 0))
            # 获取目标控件的大小
            size = self._target_widget.size()
            # 弹窗默认放在目标控件右侧
            x = pos.x() + size.width() + 20
            y = pos.y()
            # 获取弹窗宽度
            popup_w = self._popup.width()
            # 计算弹窗高度（至少120）
            popup_h = max(self._popup.sizeHint().height(), 120)
            # 获取父窗口宽度和高度
            pw = self._parent.width()
            ph = self._parent.height()
            # 如果右侧放不下，放到左侧
            if x + popup_w > pw - 20:
                x = pos.x() - popup_w - 20
            # 如果底部放不下，向上调整
            if y + popup_h > ph - 20:
                y = ph - popup_h - 20
            # 确保不超出顶部
            if y < 10:
                y = 10
            # 确保不超出左侧
            if x < 10:
                x = 10
            # 移动弹窗到计算的位置
            self._popup.move(x, y)
            # 调整弹窗大小
            self._popup.adjustSize()
            # 显示弹窗
            self._popup.show()
            # 将弹窗提升到最前
            self._popup.raise_()
        except Exception:
            # 忽略异常
            pass

    # ── 导航 ──────────────────────────────────────────────────────

    def _on_next(self):
        """下一步按钮点击处理"""
        # 显示下一个步骤
        self._show_step(self._current + 1)

    def _on_skip(self):
        """跳过按钮点击处理"""
        # 结束引导
        self._on_finish()

    def _on_finish(self):
        """结束引导"""
        # 隐藏弹窗
        self._popup.hide()
        # 隐藏覆盖层自身
        self.hide()
        # 发出结束信号
        self.finished.emit()

    # ── 覆盖层 ─────────────────────────────────────────────────────────

    def start(self):
        """开始引导"""
        # 如果没有步骤，直接返回
        if not self._steps:
            return
        # 在父窗口上安装事件过滤器
        self._parent.installEventFilter(self)
        # 显示覆盖层
        self.show()
        # 将覆盖层提升到最前
        self.raise_()
        # 显示第一个步骤
        self._show_step(0)

    def eventFilter(self, obj, event):
        """事件过滤器"""
        # 如果事件来自父窗口且类型为Resize（窗口大小改变）
        if obj is self._parent and event.type() == event.Resize:
            # 更新覆盖层几何尺寸为父窗口大小
            self.setGeometry(self._parent.rect())
            # 重新定位弹窗
            self._position_popup()
        # 调用父类的事件过滤器
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        """绘制事件"""
        try:
            # 创建QPainter对象
            painter = QPainter(self)
            # 设置画刷为半透明黑色（透明度180/255）
            painter.setBrush(QColor(0, 0, 0, 180))
            # 设置画笔为无笔（不绘制边框）
            painter.setPen(Qt.NoPen)
            # 如果有目标控件
            if self._target_widget is not None:
                try:
                    # 将目标控件的左上角映射到父窗口坐标
                    pos = self._target_widget.mapTo(self._parent, QPoint(0, 0))
                    # 获取目标控件的大小
                    size = self._target_widget.size()
                    # 创建高亮孔洞矩形（向外扩展4像素）
                    hole = QRect(pos, size).adjusted(-4, -4, 4, 4)
                    # 创建组合路径
                    path = QPainterPath()
                    # 添加整个窗口矩形
                    path.addRect(self.rect())
                    # 添加圆角矩形孔洞（反向填充）
                    path.addRoundedRect(QRect(hole), 6, 6)
                    # 绘制路径（半透明区域 + 孔洞）
                    painter.drawPath(path)
                    # 设置画刷为无填充
                    painter.setBrush(Qt.NoBrush)
                    # 设置高亮边框画笔
                    painter.setPen(QPen(QColor("#FF8C00"), 3))
                    # 绘制高亮孔洞边框
                    painter.drawRoundedRect(QRect(hole), 6, 6)
                except Exception:
                    # 如果没有目标控件，绘制整个半透明窗口
                    painter.drawRect(self.rect())
            else:
                # 没有目标控件，绘制整个半透明窗口
                painter.drawRect(self.rect())
        except Exception:
            # 忽略绘制异常
            pass

    # ── 引导工厂方法 ────────────────────────────────────────────────

    @staticmethod
    def create_app_guide(main_window) -> "GuideOverlay":
        """为 VisionFlow 创建标准应用引导

        参数：
            main_window: 主窗口对象

        返回：
            配置好的引导覆盖层对象
        """
        # 导入字体图标按钮
        from gui.font_icons import FontIconButton
        # 创建引导覆盖层对象
        overlay = GuideOverlay(main_window)

        # 辅助函数：通过工具提示文本查找按钮
        def _find_btn(tip):
            # 遍历主窗口的所有子控件
            for w in main_window.findChildren(QWidget):
                try:
                    # 如果控件的工具提示匹配且可见
                    if w.toolTip() == tip and w.isVisible():
                        return w
                except Exception:
                    pass
            return None

        # 添加第一个步骤：创建项目
        overlay.add_step(
            "创建项目",
            "点击「新建项目」按钮创建一个新的视觉检测项目。\n项目用于组织流程图、图像和设置。",
            finder=lambda: _find_btn("新建项目"))

        # 添加第二个步骤：节点工具箱
        overlay.add_step(
            "节点工具箱",
            "左侧工具箱列出了所有可用的视觉处理节点。\n拖拽节点到画布上即可开始构建流程图。",
            finder=lambda: _find_btn("工具箱") or _find_btn("搜索节点..."))

        # 添加第三个步骤：切换主题
        overlay.add_step(
            "切换主题",
            "点击调色板按钮可以选择不同的颜色主题。\n支持深色、浅色、科技蓝等多种风格。",
            finder=lambda: _find_btn("颜色主题"))

        # 添加第四个步骤：运行流程图
        overlay.add_step(
            "运行流程图",
            "构建好流程图后，点击「开始」按钮运行整个流程。\n结果将显示在右侧面板中。",
            finder=lambda: _find_btn("开始"))

        # 返回引导覆盖层
        return overlay
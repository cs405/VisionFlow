"""结果面板

布局：
  - 历史结果标签页：表格，列 [执行序号|执行时间|模块|结果数据]
    - 结果数据列包含字体图标状态图标 + 消息文本
    - 状态图标：信息（默认）、错误（红色）、完成（绿色）
    - 点击历史行 → 更新主图像 + 切换到图像标签页
  - 当前模块结果标签页：详细结果项表格
    - 点击几何项 → 在主图像上显示叠加层 + 缩放
  - 帮助标签页：带可点击链接的节点文档
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
                              QTabWidget, QLabel, QTextEdit,
                              QStyledItemDelegate, QStyle)
from PyQt5.QtCore import Qt, pyqtSignal, QRect
from gui.theme import theme_manager, connect_theme
from PyQt5.QtGui import QColor, QFont, QPainter

from core.node_vision import VisionNodeData
from gui.image_viewer import OverlayType
from core.result_presenter import (ResultItem, RectangleResultItem, LineResultItem,
                                    ScoreRectangleResultItem, VisionMessage,
                                    ResultItemType)
from gui.font_icons import FontIcons


# ── 项类型的颜色映射 ───────────────────────────────────────────

GEOM_COLORS = {
    # 矩形类型：蓝色
    ResultItemType.RECTANGLE: QColor("#0078d4"),
    # 带分数矩形类型：绿色
    ResultItemType.SCORE_RECTANGLE: QColor("#4caf50"),
    # 线段类型：橙色
    ResultItemType.LINE: QColor("#ff9800"),
}

# 状态 → 字体图标映射
STATE_ICONS = {
    "Success": FontIcons.Completed,   # 成功：完成图标
    "Error": FontIcons.Error,         # 错误：错误图标
    "Warning": FontIcons.Warning,     # 警告：警告图标
    "Info": FontIcons.Info,           # 信息：信息图标
    "Running": FontIcons.Sync,        # 运行中：同步图标
}
# 状态 → 颜色映射
STATE_COLORS = {
    "Success": "#4caf50",   # 成功：绿色
    "Error": "#f44336",     # 错误：红色
    "Warning": "#ff9800",   # 警告：橙色
    "Info": "#dcdcdc",      # 信息：白色
    "Running": "#2196f3",   # 运行中：蓝色
}


# ── 历史表格中图标+文本单元格的自定义委托 ───────────────────────────────────

class IconTextDelegate(QStyledItemDelegate):
    """在单个表格单元格中绘制字体图标 + 文本的委托"""

    def __init__(self, parent=None):
        """初始化图标文本委托

        参数：
            parent: 父对象
        """
        # 调用父类QStyledItemDelegate的构造函数
        super().__init__(parent)
        # 行号 → 图标字符字典
        self._icons: dict[int, str] = {}
        # 行号 → 图标颜色字典
        self._colors: dict[int, str] = {}

    def set_row_icon(self, row: int, icon: str, color: str = "#dcdcdc"):
        """设置行的图标和颜色

        参数：
            row: 行号
            icon: 图标字符
            color: 图标颜色
        """
        # 保存图标
        self._icons[row] = icon
        # 保存颜色
        self._colors[row] = color

    def paint(self, painter: QPainter, option, index):
        """绘制单元格

        参数：
            painter: 绘图对象
            option: 样式选项
            index: 索引
        """
        # 保存绘图器状态
        painter.save()
        # 启用抗锯齿
        painter.setRenderHint(QPainter.Antialiasing)

        # 背景 — 从主题获取
        # 获取主题管理器
        tm = theme_manager
        # 如果单元格被选中
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, tm.color('accent'))
        else:
            # 奇数行使用交替背景色，偶数行使用表面背景色
            bg = tm.color('bg_surface') if index.row() % 2 == 0 else tm.color('bg_alternating')
            painter.fillRect(option.rect, bg)

        # 获取当前行号
        row = index.row()
        # 获取图标
        icon = self._icons.get(row, "")
        # 获取颜色
        color = self._colors.get(row, tm.color('text_primary').name())

        # 起始X坐标
        x = option.rect.left() + 6

        # 绘制字体图标
        if icon:
            # 创建图标字体
            font = QFont("Segoe MDL2 Assets", 11)
            font.setStyleStrategy(QFont.PreferAntialias)
            # 设置字体
            painter.setFont(font)
            # 设置画笔颜色
            painter.setPen(QColor(color))
            # 图标矩形区域
            icon_rect = QRect(x, option.rect.top(), 20, option.rect.height())
            # 绘制图标（垂直居中，左对齐）
            painter.drawText(icon_rect, Qt.AlignVCenter | Qt.AlignLeft, icon)
            # X坐标偏移
            x += 22

        # 绘制文本
        # 获取显示文本
        text = index.data(Qt.DisplayRole) or ""
        # 创建文本字体
        font = QFont("Segoe UI", 10)
        # 设置字体
        painter.setFont(font)
        # 设置画笔颜色
        painter.setPen(theme_manager.color('text_primary'))
        # 文本矩形区域
        text_rect = QRect(x, option.rect.top(),
                          option.rect.right() - x - 4, option.rect.height())
        # 绘制文本（垂直居中，左对齐，超出部分省略号）
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft,
                         painter.fontMetrics().elidedText(text, Qt.ElideRight, text_rect.width()))

        # 恢复绘图器状态
        painter.restore()


# ═══════════════════════════════════════════════════════════════════════════
# 主结果面板
# ═══════════════════════════════════════════════════════════════════════════

class ResultPanel(QWidget):
    """
    信号：
        item_selected(uid) — 用于图像查看器联动的叠加层UID
        node_jump_requested(node_id) — 从历史记录跳转到节点
        image_update_requested(image) — 请求主图像面板显示该图像
    """

    # 叠加项选中信号，携带UID
    item_selected = pyqtSignal(str)
    # 节点跳转请求信号，携带节点ID
    node_jump_requested = pyqtSignal(str)
    # 图像更新请求信号，携带图像（numpy数组或QPixmap）
    image_update_requested = pyqtSignal(object)
    # 跨线程历史同步信号（用于从工作线程编组到主线程）
    _history_sync_requested = pyqtSignal()

    def __init__(self, parent=None):
        """初始化结果面板

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 图像查看器引用
        self._image_viewer = None
        # 行号 → 叠加项UID映射
        self._overlay_map: dict[int, str] = {}
        # 当前节点
        self._current_node: VisionNodeData | None = None
        # 图标文本委托
        self._icon_delegate: IconTextDelegate | None = None
        # 工作流引用（用于历史消息）
        self._workflow = None
        # 注册到工作流的回调引用（用于解绑）
        self._history_callback = None
        # 设置UI
        self._setup_ui()

        # 跨线程编组：WorkflowEngine.on_history_changed() 回调在工作线程中触发
        # _history_sync_requested 使用 Qt::QueuedConnection 将 sync_history_from_workflow()
        # 安全地调度到主线程，在主线程中可以安全地访问 QTableWidget
        self._history_sync_requested.connect(self.sync_history_from_workflow)

    def set_image_viewer(self, viewer):
        """设置图像查看器

        参数：
            viewer: 图像查看器对象
        """
        # self._image_viewer = viewer
        pass

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

        # 标题栏
        title = QLabel("  结果面板")
        # 设置标题样式
        title.setStyleSheet("""
            QLabel {
                background: #2d2d30; color: #dcdcdc; padding: 8px;
                font-size: 13px; font-weight: bold; border-bottom: 1px solid #3f3f46;
            }
        """)
        # 添加到布局
        layout.addWidget(title)

        # 标签页控件
        self._tabs = QTabWidget()
        # 设置标签页样式
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #252526; }
            QTabBar::tab { padding: 6px 12px; font-size: 11px; }
        """)

        # ── 历史结果标签页 ──
        # 创建历史表格（4列）
        self._history_table = QTableWidget(0, 4)
        # 设置表头标签
        self._history_table.setHorizontalHeaderLabels(["执行序号", "执行时间", "模块", "结果数据"])
        # 设置列宽
        self._history_table.setColumnWidth(0, 60)
        self._history_table.setColumnWidth(1, 75)
        self._history_table.setColumnWidth(2, 100)
        # 最后一列拉伸填充
        self._history_table.horizontalHeader().setStretchLastSection(True)

        # 为第3列（结果数据）安装自定义委托，显示图标+文本
        self._icon_delegate = IconTextDelegate(self._history_table)
        self._history_table.setItemDelegateForColumn(3, self._icon_delegate)

        # 隐藏垂直表头
        self._history_table.verticalHeader().setVisible(False)
        # 选择行为为选择行
        self._history_table.setSelectionBehavior(QTableWidget.SelectRows)
        # 选择模式为单选
        self._history_table.setSelectionMode(QTableWidget.SingleSelection)
        # 禁止编辑
        self._history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        # 启用交替行颜色
        self._history_table.setAlternatingRowColors(True)
        # 设置历史表格样式
        self._history_table.setStyleSheet("""
            QTableWidget {
                background: #252526; color: #dcdcdc; border: none;
                gridline-color: #3f3f46; alternate-background-color: #2a2a2c;
            }
            QHeaderView::section {
                background: #2d2d30; color: #999; padding: 4px 8px;
                border: none; border-bottom: 1px solid #3f3f46; font-size: 11px;
            }
            QTableWidget::item { padding: 3px 6px; font-size: 11px; }
            QTableWidget::item:selected { background: #094771; color: #dcdcdc; }
        """)
        # 连接单元格点击信号
        self._history_table.cellClicked.connect(self._on_history_cell_clicked)
        # 添加历史表格到标签页
        self._tabs.addTab(self._history_table, "历史结果")

        # ── 当前结果标签页 ──
        # 创建当前结果表格（3列）
        self._current_table = QTableWidget(0, 3)
        # 设置表头标签
        self._current_table.setHorizontalHeaderLabels(["参数", "值", "类型"])
        # 设置列宽
        self._current_table.setColumnWidth(0, 100)
        self._current_table.setColumnWidth(2, 70)
        # 最后一列拉伸填充
        self._current_table.horizontalHeader().setStretchLastSection(True)
        # 隐藏垂直表头
        self._current_table.verticalHeader().setVisible(False)
        # 选择行为为选择行
        self._current_table.setSelectionBehavior(QTableWidget.SelectRows)
        # 禁止编辑
        self._current_table.setEditTriggers(QTableWidget.NoEditTriggers)
        # 启用交替行颜色
        self._current_table.setAlternatingRowColors(True)
        # 设置当前结果表格样式
        self._current_table.setStyleSheet("""
            QTableWidget {
                background: #252526; color: #dcdcdc; border: none;
                gridline-color: #3f3f46; alternate-background-color: #2a2a2c;
            }
            QHeaderView::section {
                background: #2d2d30; color: #999; padding: 4px 8px;
                border: none; border-bottom: 1px solid #3f3f46; font-size: 11px;
            }
            QTableWidget::item { padding: 3px 6px; font-size: 11px; }
            QTableWidget::item:selected { background: #094771; }
        """)
        # 连接单元格点击信号
        self._current_table.cellClicked.connect(self._on_current_result_clicked)
        # 添加当前结果表格到标签页
        self._tabs.addTab(self._current_table, "当前模块结果")

        # ── 帮助标签页 ──
        # 创建帮助文本编辑框
        self._help_text = QTextEdit()
        # 设置为只读
        self._help_text.setReadOnly(True)
        # 设置样式
        self._help_text.setStyleSheet("""
            QTextEdit {
                background: #252526; color: #dcdcdc; border: none;
                padding: 12px; font-size: 12px;
            }
        """)
        # 设置占位符文本
        self._help_text.setPlaceholderText("选择节点后在此查看帮助信息")
        # 添加帮助标签页
        self._tabs.addTab(self._help_text, "帮助")

        # 添加标签页到布局
        layout.addWidget(self._tabs)
        # 保存标题标签引用
        self._title_label = title
        # 连接主题变化信号
        connect_theme(self._refresh_qss)

    def _refresh_qss(self):
        """刷新主题样式"""
        # 获取主题管理器
        tm = theme_manager
        # 刷新标题标签样式
        self._title_label.setStyleSheet(f"""
            QLabel {{ background: {tm.color('bg_surface_raised').name()}; color: {tm.color('text_primary').name()};
                      padding: 8px; font-size: 13px; font-weight: bold;
                      border-bottom: 1px solid {tm.color('border').name()}; }}
        """)
        # 刷新标签页样式
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {tm.color('bg_surface').name()}; }}
            QTabWidget:focus {{ outline: 0; }}
            QTabWidget::pane:focus {{ outline: 0; border: none; }}
            QTabBar:focus {{ outline: 0; }}
            QTabBar::tab {{ padding: 6px 12px; font-size: 11px; }}
            QTabBar::tab:focus {{ outline: 0; }}
        """)
        accent = tm.color("accent").name()
        table_qss = f"""
            QTableWidget {{ background: {tm.color('bg_surface').name()}; color: {tm.color('text_primary').name()};
                           border: none; gridline-color: {tm.color('border').name()};
                           alternate-background-color: {tm.color('bg_alternating').name()}; }}
            QHeaderView::section {{ background: {tm.color('bg_surface_raised').name()};
                                   color: {tm.color('text_secondary').name()}; padding: 4px 8px;
                                   border: none; border-bottom: 1px solid {tm.color('border').name()}; font-size: 11px; }}
            QTableWidget::item {{ padding: 3px 6px; font-size: 11px; }}
            QTableWidget::item:selected {{ background: {accent}; color: {tm.color('text_primary').name()}; }}
        """
        if hasattr(self, '_history_table'):
            self._history_table.setStyleSheet(table_qss)
        if hasattr(self, '_current_table'):
            self._current_table.setStyleSheet(table_qss)
        if hasattr(self, '_help_text'):
            self._help_text.setStyleSheet(f"""
                QTextEdit, QPlainTextEdit {{ background: {tm.color('bg_surface').name()};
                    color: {tm.color('text_secondary').name()}; border: none; padding: 12px; font-size: 12px; }}
            """)

    # ── 当前节点结果 ──────────────────────────────────────

    def show_node_results(self, node: VisionNodeData | None):
        """在当前标签页中显示所选节点的结果

        参数：
            node: 视觉节点数据对象
        """
        # 清空当前表格
        self._current_table.setRowCount(0)
        # 清空叠加映射
        self._overlay_map.clear()
        # 保存当前节点
        self._current_node = node

        # 如果节点为空，返回
        if node is None:
            return

        # 结果项列表
        items: list[ResultItem] = [ResultItem("名称", node.name, ResultItemType.VALUE),
                                   ResultItem("类型", type(node).__name__, ResultItemType.VALUE),
                                   ResultItem("消息", node.message or "-", ResultItemType.VALUE),
                                   ResultItem("节点ID", node.node_id, ResultItemType.VALUE)]
        # 添加基本信息

        # 添加结果图像信息
        for img in node.result_images:
            # 获取图像形状
            shape = img.image.shape if img.image is not None else ()
            items.append(ResultItem(f"输出图像: {img.name}",
                                    f"{shape}" if shape else "None",
                                    ResultItemType.IMAGE))

        # 如果有检测结果
        if hasattr(node, 'detections') and node.detections:
            # 遍历检测结果
            for i, det in enumerate(node.detections):
                # 如果有矩形属性
                if hasattr(det, 'rect'):
                    # 获取矩形
                    rect = det.rect
                    # 获取置信度
                    score = getattr(det, 'confidence', 0.0)
                    # 获取标签
                    label = getattr(det, 'label', f"检测{i}")
                    # 添加到项列表
                    items.append(ScoreRectangleResultItem(
                        name=label, x=rect[0], y=rect[1],
                        width=rect[2], height=rect[3], score=score))

        # 遍历所有项
        for item in items:
            # 获取当前行号
            row = self._current_table.rowCount()
            # 插入新行
            self._current_table.insertRow(row)

            # 创建名称项
            name_item = QTableWidgetItem(item.name)
            name_item.setForeground(QColor("#999"))
            self._current_table.setItem(row, 0, name_item)

            # 创建值项
            val_item = QTableWidgetItem(str(item.value) if item.value is not None else "-")
            val_item.setForeground(QColor("#dcdcdc"))
            self._current_table.setItem(row, 1, val_item)

            # 创建类型项
            type_item = QTableWidgetItem(item.item_type.value)
            # 获取类型颜色
            type_color = GEOM_COLORS.get(item.item_type, QColor("#666"))
            type_item.setForeground(type_color)
            self._current_table.setItem(row, 2, type_item)

            # 如果是几何项（矩形、带分数矩形、线段），添加到叠加映射
            if isinstance(item, (RectangleResultItem, ScoreRectangleResultItem, LineResultItem)):
                self._overlay_map[row] = item

    # ── 历史记录 ─────────────────────────────────────────────────────────

    def bind_workflow(self, workflow):
        """绑定到工作流的历史消息集合

        通过 on_history_changed() 在工作流上注册回调。
        当工作流添加/更新消息时，回调触发 _history_sync_requested，
        使用 Qt::QueuedConnection 将 sync_history_from_workflow() 调度到主线程。

        参数：
            workflow: 工作流引擎
        """
        # 解绑旧工作流（避免旧工作流继续触发已失效的回调）
        if (self._workflow is not None
                and hasattr(self._workflow, 'off_history_changed')
                and self._history_callback is not None):
            self._workflow.off_history_changed(self._history_callback)
        # 保存工作流引用
        self._workflow = workflow
        self._history_callback = None
        # 如果工作流存在且有on_history_changed方法
        if workflow and hasattr(workflow, 'on_history_changed'):
            # 注册回调函数
            self._history_callback = lambda: self._history_sync_requested.emit()
            workflow.on_history_changed(self._history_callback)

    def sync_history_from_workflow(self):
        """从工作流的messages重建历史表格

        在节点执行完成或切换工作流时调用。
        对于视频/摄像头节点，通过result_node_data查找现有行并原地更新，而不是添加新行。

        使用 get_messages_snapshot() 实现线程安全访问
        （工作流在 ThreadPoolExecutor 线程中执行节点，UI 从主线程读取）
        """
        # 如果没有工作流，返回
        if self._workflow is None:
            return
        # 如果工作流有get_messages_snapshot方法，使用线程安全快照
        if hasattr(self._workflow, 'get_messages_snapshot'):
            messages = self._workflow.get_messages_snapshot()
        else:
            # 否则直接获取messages
            messages = getattr(self._workflow, 'messages', []) or []

        # 检查最后一条消息是否已有匹配的行（更新情况）
        if messages:
            # 获取最后一条消息
            last_msg = messages[-1]
            # 获取消息关联的节点
            last_node = last_msg.result_node_data
            # 如果节点存在
            if last_node is not None:
                # 遍历历史表格查找匹配的行
                for row in range(self._history_table.rowCount()):
                    # 获取第一列的用户数据
                    item = self._history_table.item(row, 0)
                    # 如果节点ID匹配
                    if item and item.data(Qt.UserRole) == last_node.node_id:
                        # 更新现有行
                        self._update_history_row(row, last_msg)
                        # 滚动到底部
                        self._history_table.scrollToBottom()
                        return

        # 完全重建：从工作流消息重建历史表格
        self._history_table.setRowCount(0)
        # 遍历所有消息
        for msg in messages:
            # 添加历史行
            self._add_history_row(msg)
        # 滚动到底部
        self._history_table.scrollToBottom()

    def _add_history_row(self, msg: VisionMessage):
        """向历史表格添加一行（单条VisionMessage）

        参数：
            msg: 视觉消息对象
        """
        # 获取当前行号
        row = self._history_table.rowCount()
        # 插入新行
        self._history_table.insertRow(row)
        # 节点ID
        node_id = ""
        # 如果有结果节点数据且节点ID属性
        if msg.result_node_data and hasattr(msg.result_node_data, 'node_id'):
            node_id = msg.result_node_data.node_id

        # 执行序号
        idx_item = QTableWidgetItem(str(msg.index))
        idx_item.setForeground(QColor("#666"))
        idx_item.setData(Qt.UserRole, node_id)
        idx_item.setTextAlignment(Qt.AlignCenter)
        self._history_table.setItem(row, 0, idx_item)

        # 执行时间
        time_item = QTableWidgetItem(msg.time_span)
        time_item.setForeground(QColor("#999"))
        time_item.setData(Qt.UserRole, node_id)
        self._history_table.setItem(row, 1, time_item)

        # 模块
        name_item = QTableWidgetItem(msg.type_name)
        name_item.setForeground(QColor("#dcdcdc"))
        name_item.setData(Qt.UserRole, node_id)
        self._history_table.setItem(row, 2, name_item)

        # 结果数据 — 图标 + 文本
        # 消息文本
        msg_text = msg.message or ("完成" if msg.state == "Success" else "失败")
        msg_item = QTableWidgetItem(msg_text)
        msg_item.setData(Qt.UserRole, node_id)
        # 获取图标
        icon = STATE_ICONS.get(msg.state, FontIcons.Info)
        # 获取颜色
        color = STATE_COLORS.get(msg.state, theme_manager.color('text_primary').name())
        # 如果有图标委托，设置行图标
        if self._icon_delegate:
            self._icon_delegate.set_row_icon(row, icon, color)
        self._history_table.setItem(row, 3, msg_item)

    def _update_history_row(self, row: int, msg: VisionMessage):
        """原地更新现有历史行（用于视频/摄像头持续节点）

        参数：
            row: 行号
            msg: 视觉消息对象
        """
        # 更新时间列
        time_item = self._history_table.item(row, 1)
        if time_item:
            time_item.setText(msg.time_span)
        # 更新消息文本列
        msg_item = self._history_table.item(row, 3)
        msg_text = msg.message or ("完成" if msg.state == "Success" else "失败")
        if msg_item:
            msg_item.setText(msg_text)
        # 更新图标
        icon = STATE_ICONS.get(msg.state, FontIcons.Info)
        color = STATE_COLORS.get(msg.state, theme_manager.color('text_primary').name())
        if self._icon_delegate:
            self._icon_delegate.set_row_icon(row, icon, color)

    def _on_history_cell_clicked(self, row: int):
        """处理历史行点击 — 更新主图像 + 跳转到节点

        SelectedMessageChangedCommand → SetResultNodeData(message)
          → ResultImageSource = message.ResultImageSource  // 更新主图像
          → ResultNodeData = message.ResultNodeData         // 更新属性面板

        参数：
            row: 行号
            col: 列号
        """
        # 如果没有工作流，返回
        if self._workflow is None:
            return
        # 获取消息列表
        if hasattr(self._workflow, 'get_messages_snapshot'):
            messages = self._workflow.get_messages_snapshot()
        else:
            messages = getattr(self._workflow, 'messages', []) or []
        # 检查行号有效性
        if not (0 <= row < len(messages)):
            return
        # 获取消息
        msg = messages[row]

        # 更新主图像
        if msg.result_image_source is not None:
            self.image_update_requested.emit(msg.result_image_source)

        # 跳转到节点 + 更新属性面板
        if msg.result_node_data and hasattr(msg.result_node_data, 'node_id'):
            self.node_jump_requested.emit(msg.result_node_data.node_id)

    # ── 交互 ───────────────────────────────────────────────────

    def _on_current_result_clicked(self, row: int):
        """处理结果点击 — 在图像查看器上显示叠加层 + 缩放到矩形

        参数：
            row: 行号
            col: 列号
        """
        # 如果行不在叠加映射中或没有图像查看器，返回
        if row not in self._overlay_map or self._image_viewer is None:
            return
        # 获取几何项
        geo_item = self._overlay_map[row]

        # 如果是矩形或带分数矩形项
        if isinstance(geo_item, (RectangleResultItem, ScoreRectangleResultItem)):
            # 构建矩形
            rect = (int(geo_item.x), int(geo_item.y),
                    int(geo_item.width), int(geo_item.height))
            # 判断类型：有分数则为检测框，否则为普通矩形
            ov_type = OverlayType.DETECTION if getattr(geo_item, 'score', 0.0) > 0 else OverlayType.RECT
            # 添加矩形叠加层
            uid = self._image_viewer.add_rect_overlay(
                rect, label=geo_item.name,
                color=GEOM_COLORS.get(geo_item.item_type, QColor("#0078d4")),
                score=getattr(geo_item, 'score', 0.0),
                overlay_type=ov_type)
            # 缩放到矩形
            self._image_viewer.zoom_to_rect(rect, padding=0.15, animate=True)
            # 发出项选中信号
            self.item_selected.emit(uid)
        # 如果是线段项
        elif isinstance(geo_item, LineResultItem):
            # 添加线段叠加层
            uid = self._image_viewer.add_line_overlay(
                geo_item.x1, geo_item.y1, geo_item.x2, geo_item.y2,
                label=geo_item.name,
                color=GEOM_COLORS.get(geo_item.item_type, QColor("#ff9800")))
            # 发出项选中信号
            self.item_selected.emit(uid)

    # ── 帮助显示 ──────────────────────────────────────────────

    def show_help(self, node: VisionNodeData | None):
        """显示节点的帮助信息，带有可点击的文档链接

        参数：
            node: 视觉节点数据对象
        """
        # 如果节点为空
        if node is None:
            # 显示提示信息
            self._help_text.setHtml(
                '<p style="color: #666; font-size: 13px;">'
                f'{FontIcons.Info}  选择一个节点以查看帮助信息</p>'
            )
            return

        # 获取帮助信息
        help_info = {}
        # 如果节点有create_help_presenter方法
        if hasattr(node, 'create_help_presenter'):
            try:
                # 调用方法获取帮助信息
                help_info = node.create_help_presenter() or {}
            except Exception:
                pass

        # 获取节点信息
        name = help_info.get("name", getattr(node, 'name', type(node).__name__))
        description = help_info.get("description", "")
        url = help_info.get("url", "")
        source = help_info.get("source", "")
        # 获取节点类
        cls = type(node)
        # 获取基类列表
        bases = [b.__name__ for b in cls.__mro__[1:6] if b.__name__ != 'object']

        # 构建HTML
        html = f"""
            <html>
            <body style="color:#dcdcdc; font-family:'Segoe UI'; font-size:12px;">
            <h2 style="color:#0078d4; margin-bottom:4px;">{FontIcons.Help}  {name}</h2>
            <p style="color:#999; margin-top:0;"><b>类型:</b> {cls.__name__}</p>
            <p style="color:#aaa;">{description}</p>
            <hr style="border-color:#3f3f46;">
            <h4>继承链</h4>
            <p style="color:#999;">{' → '.join(bases)}</p>
            <h4>参数列表</h4>
            <table style="width:100%; border-collapse:collapse;">
            """

        # 从Property描述符获取参数表
        for attr_name, attr in node.get_property_descriptors():
            try:
                val = getattr(node, attr_name, "")
                val_str = str(val) if val else "—"
                if isinstance(val, str) and len(val_str) > 50:
                    val_str = val_str[:50] + "..."
                html += (
                    f'<tr style="border-bottom:1px solid #3f3f46;">'
                    f'<td style="padding:3px 8px; color:#ccc;">{attr.display_name or attr_name}</td>'
                    f'<td style="padding:3px 8px; color:#999;">{val_str}</td>'
                    f'<td style="padding:3px 8px; color:#666; font-size:10px;">{attr.group or ""}</td>'
                    f'</tr>'
                )
            except Exception:
                pass

        html += "</table>"

        # 如果有URL，添加在线文档链接
        if url:
            html += (
                f'<p style="margin-top:12px;">'
                f'{FontIcons.Link}  <a href="{url}" style="color:#0078d4;">在线文档</a>'
                f'</p>'
            )
        # 如果有源文件路径，添加源文件信息
        if source:
            html += f'<p style="color:#666; font-size:10px;">源文件: {source}</p>'

        html += "</body></html>"
        # 设置帮助文本
        self._help_text.setHtml(html)

    # ── 清空 ──────────────────────────────────────────────────────────

    def clear(self):
        """清空所有表格和状态"""
        # 解绑旧工作流
        if (self._workflow is not None
                and hasattr(self._workflow, 'off_history_changed')
                and self._history_callback is not None):
            self._workflow.off_history_changed(self._history_callback)
        # 清空当前结果表格
        self._current_table.setRowCount(0)
        # 清空历史表格
        self._history_table.setRowCount(0)
        # 清空叠加映射
        self._overlay_map.clear()
        # 清空工作流引用
        self._workflow = None
        self._history_callback = None
        # 清空当前节点
        self._current_node = None

    def clear_history(self):
        """仅清空历史表格（新运行或切换图表时清除消息）"""
        # 清空历史表格
        self._history_table.setRowCount(0)
        # 如果工作流存在且有clear_messages方法
        if self._workflow and hasattr(self._workflow, 'clear_messages'):
            # 清空工作流的消息
            self._workflow.clear_messages()

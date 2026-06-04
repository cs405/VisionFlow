"""
WPF StyleNodeDataBase 节点图形精确还原
- 白色背景 + 圆角边框
- 左侧状态条(30px, 运行中=蓝/成功=绿/错误=红/空闲=隐藏)
- DockPanel: 图标(居中) + 文本(居中, 超长截断)
- 悬停: 浅灰底+深色边框 | 选中: 浅灰底+橙色边框
"""

from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QBrush, QColor, QPen, QFont, QPainter, QPainterPath
)

from core.events import EventBus, Event, EventType
from .socket_item import GraphicsSocket


class GraphicsNode(QGraphicsItem):
    """WPF StyleNodeDataBase 节点"""

    # WPF节点分类颜色 (用于左侧色条和标题栏)
    CATEGORY_COLORS = {
        "IO": QColor("#3C8D40"),
        "预处理": QColor("#5A5A8A"),
        "特征检测": QColor("#8A5A5A"),
        "匹配": QColor("#6A6A8A"),
        "测量": QColor("#5A8A8A"),
        "增强": QColor("#8A7A5A"),
        "几何变换": QColor("#6A6A6A"),
        "颜色处理": QColor("#7A5A7A"),
        "通用": QColor("#6A6A7A"),
    }

    STATE_COLORS = {
        "Running": QColor("#2196F3"),
        "Success": QColor("#4CAF50"),
        "Error": QColor("#F44336"),
    }

    def __init__(self, node_data: dict, event_bus: EventBus, parent=None):
        super().__init__(parent)
        self.node_id = node_data.get("id", "")
        self.node_name = node_data.get("name", "Node")
        self.category = node_data.get("category", "通用")
        self.inputs = node_data.get("inputs", [])
        self.outputs = node_data.get("outputs", [])
        self.parameters = node_data.get("parameters", [])
        self.event_bus = event_bus

        # WPF节点尺寸
        self.width = 160
        self.header_h = 28
        self.status_w = 8       # 左侧状态条宽度
        self.socket_area_top = self.header_h
        self.socket_spacing = 22
        self.padding_v = 8

        self.input_sockets = []
        self.output_sockets = []
        self._selected = False
        self._hovered = False
        self._exec_state = None  # Running|Success|Error|None

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(1)

        self._create_sockets()

    def _create_sockets(self):
        for i, s in enumerate(self.inputs):
            sock = GraphicsSocket(s, self, self.event_bus, is_input=True)
            sock.setPos(-6, self.socket_area_top + self.padding_v + i * self.socket_spacing)
            sock.setParentItem(self)
            self.input_sockets.append(sock)

        for i, s in enumerate(self.outputs):
            sock = GraphicsSocket(s, self, self.event_bus, is_input=False)
            sock.setPos(self.width + 6, self.socket_area_top + self.padding_v + i * self.socket_spacing)
            sock.setParentItem(self)
            self.output_sockets.append(sock)

        max_s = max(len(self.input_sockets), len(self.output_sockets), 1)
        self.body_h = self.socket_area_top + self.padding_v * 2 + max_s * self.socket_spacing
        self.height = self.body_h

    def boundingRect(self) -> QRectF:
        return QRectF(-8, -2, self.width + 16, self.height + 4)

    def shape(self):
        p = QPainterPath()
        p.addRoundedRect(2, 0, self.width, self.height, 4, 4)
        return p

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        # === WPF Border样式 ===
        if self._selected:
            border_c = QColor("#FF9800")  # 橙色
            bg_c = QColor("#F0F0F0")       # 浅灰
        elif self._hovered:
            border_c = QColor("#808080")
            bg_c = QColor("#F5F5F5")
        else:
            border_c = QColor("#D0D0D0")
            bg_c = QColor("#FFFFFF")

        # 主体背景
        body = QPainterPath()
        body.addRoundedRect(2, 0, self.width, self.height, 4, 4)
        painter.fillPath(body, QBrush(bg_c))
        painter.setPen(QPen(border_c, 1.2))
        painter.drawPath(body)

        # === 左侧状态条 (30px宽, 圆角左侧) ===
        if self._exec_state and self._exec_state in self.STATE_COLORS:
            state_c = self.STATE_COLORS[self._exec_state]
            bar = QPainterPath()
            bar.addRoundedRect(2, 1, self.status_w, self.height - 2, 3, 3)
            # 覆盖右侧圆角使左侧条右边缘为直角
            bar.addRect(self.status_w, 1, 2, self.height - 2)
            bar.setFillRule(Qt.WindingFill)
            painter.fillPath(bar, QBrush(state_c))

        # === 标题栏 ===
        cat_c = self.CATEGORY_COLORS.get(self.category, self.CATEGORY_COLORS["通用"])
        header = QPainterPath()
        header.addRoundedRect(2, 0, self.width, self.header_h, 4, 4)
        header.addRect(2, self.header_h - 4, self.width, 4)  # 底部直角
        painter.fillPath(header, QBrush(cat_c))

        # 标题文字(白色)
        font = QFont("Microsoft YaHei", 8, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        name = self.node_name[:14] + ".." if len(self.node_name) > 14 else self.node_name
        painter.drawText(QRectF(6, 0, self.width - 12, self.header_h),
                        Qt.AlignVCenter | Qt.AlignCenter, name)

        # === 图标区域(标题栏下方) ===
        # WPF: FontIconTextBlock + TextBlock 居中
        icon_font = QFont("Microsoft YaHei", 9)
        painter.setFont(icon_font)
        painter.setPen(QColor("#808080"))

        # 分类图标映射
        icons = {"IO": "📂", "预处理": "🔧", "特征检测": "🔍", "匹配": "🎯", "测量": "📏",
                 "增强": "✨", "几何变换": "🔄", "颜色处理": "🎨"}
        icon = icons.get(self.category, "⚙")
        painter.drawText(QRectF(6, self.header_h + 1, self.width - 12, 16),
                        Qt.AlignCenter, icon)

    # ===== 交互事件 =====

    def hoverEnterEvent(self, e):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, e):
        self._hovered = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.setSelected(True)
            self.event_bus.emit(Event(type=EventType.NODE_SELECTED, data={
                "node_id": self.node_id,
                "node_metadata": {"id": self.node_id, "name": self.node_name,
                                  "category": self.category, "inputs": self.inputs,
                                  "outputs": self.outputs, "parameters": self.parameters}
            }))
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.event_bus.emit(Event(type=EventType.NODE_DOUBLE_CLICKED,
                                   data={"node_id": self.node_id}))
        super().mouseDoubleClickEvent(e)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            self.event_bus.emit(Event(type=EventType.NODE_MOVED,
                data={"node_id": self.node_id, "pos_x": value.x(), "pos_y": value.y()}))
        elif change == QGraphicsItem.ItemSelectedChange:
            self._selected = value
            self.update()
        return super().itemChange(change, value)

    # ===== 公开API =====

    def set_execution_state(self, state):
        self._exec_state = state
        self.update()

    def get_input_socket(self, name: str):
        for s in self.input_sockets:
            if s.socket_name == name:
                return s
        return None

    def get_output_socket(self, name: str):
        for s in self.output_sockets:
            if s.socket_name == name:
                return s
        return None

    def update_node_data(self, data: dict):
        self.node_name = data.get("name", self.node_name)
        self.update()

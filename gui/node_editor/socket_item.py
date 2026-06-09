"""Socket (port) graphics item — typed connection points on nodes.
（Socket（端口）图形项 — 节点上的类型化连接点）
"""

from enum import Enum

from PyQt5.QtWidgets import (QGraphicsObject, QGraphicsSceneMouseEvent,
                              QStyleOptionGraphicsItem, QWidget)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainter, QPainterPath,
                          QLinearGradient, QPolygonF)

from core.node_base import Port, PortType, PortDock
from gui.theme import theme_manager

# 端口半径（像素）
PORT_RADIUS = 4.0
# 端口直径（像素）
PORT_DIAMETER = PORT_RADIUS * 2
# 端口悬停时的半径（像素）
PORT_HOVER_RADIUS = 6.0
# 端口的命中检测半径（像素），用于鼠标点击检测
PORT_HIT_RADIUS = PORT_RADIUS * 2.5


class PortDataType(Enum):
    """端口携带的数据类型 — 决定视觉样式"""
    # 图像数据类型：标签"image"，白色，蓝色光晕，非虚线
    IMAGE = ("image", QColor("#FFFFFF"), QColor("#4a9eff"), False)
    # 控制数据类型：标签"control"，金色，金色光晕，虚线
    CONTROL = ("control", QColor("#FFD700"), QColor("#FFD700"), True)
    # 文本数据类型：标签"text"，青色，青色光晕，非虚线
    TEXT = ("text", QColor("#00BCD4"), QColor("#00BCD4"), False)
    # 任意数据类型：标签"any"，灰色，灰色光晕，虚线
    ANY = ("any", QColor("#AAAAAA"), QColor("#AAAAAA"), True)

    # 构造函数的初始化方法
    def __init__(self, label: str, color: QColor, glow: QColor, dashed: bool):
        # 数据类型的显示标签
        self.label = label
        # 颜色
        self.color = color
        # 光晕颜色（悬停时使用）
        self.glow_color = glow
        # 是否使用虚线边框
        self.dashed = dashed


class SocketItem(QGraphicsObject):
    """节点上的可视化端口。按下时发出信号；场景处理其余操作。

    Qt注意：只处理mousePressEvent。移动和释放事件由DiagramScene.event()拦截。
    """

    # 鼠标按下时发出的信号 — 场景连接此信号以开始拖拽连线
    drag_started = pyqtSignal(object)   # socket对象

    # 保留用于向后兼容editor_widget.py的信号
    connection_started = pyqtSignal(object)      # 连线开始信号
    connection_moved = pyqtSignal(object, QPointF)  # 连线移动信号
    connection_ended = pyqtSignal(object, object)    # 连线结束信号

    def __init__(self, port: Port, parent=None):
        """初始化SocketItem

        参数：
            port: 端口数据对象
            parent: 父对象
        """
        # 调用父类QGraphicsObject的构造函数
        super().__init__(parent)
        # 保存端口数据
        self.port = port
        # 鼠标悬停标志，初始为False
        self._hovered = False
        # 与该插座相连的连线列表
        self._connected_edges: list = []
        # 画笔对象
        self._pen = QPen()
        # 画刷对象
        self._brush = QBrush()
        # 端口矩形区域（中心在原点）
        self._rect = QRectF(-PORT_RADIUS, -PORT_RADIUS, PORT_DIAMETER, PORT_DIAMETER)

        # 获取端口的数据类型字符串
        dt_str = getattr(port, 'data_type', 'image') or 'image'
        try:
            # 尝试从PortDataType枚举中获取对应的数据类型
            self._data_type = PortDataType[dt_str.upper()]
        except KeyError:
            # 如果找不到，默认使用图像类型
            self._data_type = PortDataType.IMAGE

        # 启用鼠标悬停事件
        self.setAcceptHoverEvents(True)
        # 设置图形项在位置变化时发送几何变化通知
        self.setFlag(QGraphicsObject.ItemSendsGeometryChanges, True)
        # 设置Z序为20（高于节点和连线）
        self.setZValue(20)
        # 设置光标样式为十字光标
        self.setCursor(Qt.CrossCursor)

        # 更新样式
        self._update_style()

    # ── 样式 ─────────────────────────────────────────────────────────────

    def _update_style(self):
        """更新端口的样式（颜色、画笔、画刷）"""
        # 获取数据类型
        dt = self._data_type
        # 如果鼠标悬停
        if self._hovered:
            # 画笔：光晕颜色，线宽2.5
            self._pen = QPen(dt.glow_color, 2.5)
            # 画刷：光晕颜色填充
            self._brush = QBrush(dt.glow_color)
        # 如果是输出端口（非悬停时）
        elif self.port.is_output:
            # 画笔：数据类型颜色，线宽2.0
            self._pen = QPen(dt.color, 2.0)
            # 画刷：数据类型颜色变亮120%
            self._brush = QBrush(dt.color.lighter(120))
        # 如果是输入端口（非悬停时）
        else:
            # 画笔：数据类型颜色，线宽1.5
            self._pen = QPen(dt.color, 1.5)
            # 如果数据类型需要虚线
            if dt.dashed:
                # 设置虚线样式
                self._pen.setStyle(Qt.DashLine)
            # 画刷：表面输入背景色（从主题获取）
            self._brush = QBrush(theme_manager.color("bg_surface_input"))
        # 设置工具提示文本
        self.setToolTip(f"{self.port.dock.name} — {dt.label}")
        # 触发重绘
        self.update()

    def set_highlight(self, on: bool):
        """在端口模式执行期间高亮显示端口"""
        # 设置悬停标志
        self._hovered = on
        # 更新样式
        self._update_style()

    def boundingRect(self) -> QRectF:
        """返回边界矩形（用于场景布局）"""
        # 内边距：悬停半径+2
        pad = PORT_HOVER_RADIUS + 2
        # 返回向外扩展后的矩形
        return self._rect.adjusted(-pad, -pad, pad, pad)

    def shape(self) -> QPainterPath:
        """返回形状（用于鼠标命中检测）"""
        # 创建路径对象
        path = QPainterPath()
        # 添加一个半径为命中检测半径的圆
        path.addEllipse(QPointF(0, 0), PORT_HIT_RADIUS, PORT_HIT_RADIUS)
        # 返回路径
        return path

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        """绘制端口"""
        # 启用抗锯齿
        painter.setRenderHint(QPainter.Antialiasing)
        # 设置画笔
        painter.setPen(self._pen)
        # 设置画刷
        painter.setBrush(self._brush)
        # 获取端口半径
        r = PORT_RADIUS
        # 如果是控制数据类型（菱形）
        if self._data_type == PortDataType.CONTROL:
            # 创建菱形多边形
            diamond = QPolygonF([
                QPointF(0, -r),   # 顶部点
                QPointF(r, 0),    # 右侧点
                QPointF(0, r),    # 底部点
                QPointF(-r, 0),   # 左侧点
            ])
            # 绘制菱形
            painter.drawPolygon(diamond)
        else:
            # 其他类型绘制圆形
            painter.drawEllipse(QPointF(0, 0), r, r)
        # 如果该端口已连接
        if self._connected_edges:
            # 设置无画笔
            painter.setPen(Qt.NoPen)
            # 设置画刷为连接中颜色（从主题获取）
            painter.setBrush(QBrush(theme_manager.color("port_connected")))
            # 在端口中心绘制一个小圆点（表示已连接）
            painter.drawEllipse(QPointF(0, 0), 2, 2)

    # ── 连线追踪 ─────────────────────────────────────────────────────

    def add_edge(self, edge):
        """添加连线到该端口"""
        # 如果连线不在列表中
        if edge not in self._connected_edges:
            # 添加到列表
            self._connected_edges.append(edge)
        # 触发重绘
        self.update()

    def remove_edge(self, edge):
        """从该端口移除连线"""
        # 如果连线在列表中
        if edge in self._connected_edges:
            # 从列表中移除
            self._connected_edges.remove(edge)
        # 触发重绘
        self.update()

    def get_center_scene_pos(self) -> QPointF:
        """获取端口在场景中的中心坐标"""
        # 将局部坐标(0,0)映射到场景坐标
        return self.mapToScene(0, 0)

    @property
    def is_connected(self) -> bool:
        """判断端口是否已连接"""
        return len(self._connected_edges) > 0

    # ── 悬停事件 ─────────────────────────────────────────────────────────────

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        """鼠标进入端口区域"""
        # 设置悬停标志为True
        self._hovered = True
        # 更新样式
        self._update_style()
        # 调用父类的hoverEnterEvent
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        """鼠标离开端口区域"""
        # 设置悬停标志为False
        self._hovered = False
        # 更新样式
        self._update_style()
        # 调用父类的hoverLeaveEvent
        super().hoverLeaveEvent(event)

    # ── 鼠标按下 → 发送信号给场景 ─────────────

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """只有输出端口才能开始连接。场景处理移动和释放。"""
        # 如果按下的是左键且端口是输出端口
        if event.button() == Qt.LeftButton and self.port.is_output:
            # 发出拖拽开始信号
            self.drag_started.emit(self)
            # 发出连线开始信号（向后兼容）
            self.connection_started.emit(self)
            # 获取场景对象
            s = self.scene()
            # 如果场景有start_edge_drag方法
            if hasattr(s, 'start_edge_drag'):
                # 调用场景的开始拖拽连线方法
                s.start_edge_drag(self)
            # 接受事件
            event.accept()
            return
        # 其他情况调用父类的mousePressEvent
        super().mousePressEvent(event)

    # ── 位置变化 → 更新相关连线 ─────────────────────────────────────────

    def itemChange(self, change, value):
        """图形项属性变化事件"""
        # 如果变化类型是位置已改变
        if change == QGraphicsObject.ItemPositionHasChanged:
            # 遍历所有与该端口相连的连线
            for edge in self._connected_edges:
                # 更新连线路径
                edge.update_path()
        # 调用父类的itemChange方法并返回结果
        return super().itemChange(change, value)
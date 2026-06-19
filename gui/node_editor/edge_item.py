"""连线（边）图形项。

颜色在绘制时从 theme_manager 解析 —— 没有硬编码值。
"""

import math

from PyQt5.QtWidgets import (QGraphicsObject, QGraphicsSceneMouseEvent,
                              QStyleOptionGraphicsItem, QWidget, QGraphicsTextItem,
                              QGraphicsView)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainterPath, QPainter,
                          QPolygonF, QFont, QPainterPathStroker)

from core.node_base import PortDock
from gui.node_editor.link_drawer import ILinkDrawer, BrokenLinkDrawer
from gui.theme import theme_manager

# ── 虚线样式（StrokeDashArray —— 结构定义，非颜色）──
# 动态虚线样式（绘制中预览）
DASH_DYNAMIC = [5, 2]
# 运行中虚线样式
DASH_RUNNING = [4, 4]
# 非流式虚线样式
DASH_NONFLOW = [5, 5]

# 箭头大小（像素）
ARROW_SIZE = 8.0
# 最小路径长度阈值（小于此值视为退化路径）
MIN_PATH_LENGTH = 1.0

# ── 辅助函数：从主题解析边颜色 ──
def _edge_color(key: str) -> QColor:
    """根据主题键名获取边颜色"""
    # 调用主题管理器的color方法获取颜色
    return theme_manager.color(key)


class EdgeState:
    """边状态常量"""
    # 正常状态
    NORMAL = "normal"
    # 选中状态
    SELECTED = "selected"
    # 鼠标悬停状态
    HOVER = "hover"
    # 运行中状态
    RUNNING = "running"
    # 成功状态
    SUCCESS = "success"
    # 错误状态
    ERROR = "error"


class EdgeItem(QGraphicsObject):
    """两个 SocketItem 之间的连线

    Qt: _active_pen() → 绘制时从 theme_manager.color("edge_xxx") 获取颜色
    """

    # 边被选中时发出的信号
    edge_selected = pyqtSignal(object)

    def __init__(self, from_socket=None, to_socket=None, link_data=None,
                 drawer: ILinkDrawer = None, parent=None):
        """初始化连线项

        参数：
            from_socket: 源插座
            to_socket: 目标插座
            link_data: 连线数据
            drawer: 连线绘制器
            parent: 父对象
        """
        # 调用父类QGraphicsObject的构造函数
        super().__init__(parent)
        # 保存源插座
        self.from_socket = from_socket
        # 保存目标插座
        self.to_socket = to_socket
        # 保存连线数据
        self.link_data = link_data
        # 保存连线绘制器（默认使用折线绘制器BrokenLinkDrawer）
        self._drawer = drawer or BrokenLinkDrawer()
        # 初始化鼠标悬停标志为False
        self._hovered = False
        # 初始化连线状态为正常
        self._state = EdgeState.NORMAL
        # 初始化临时终点为None（用于预览连线）
        self._temp_end = None
        # 初始化文本标签项为None
        self._label_item = None
        # 初始化路径对象
        self._path = QPainterPath()
        # 初始化箭头多边形
        self._arrow_poly = QPolygonF()
        # 初始化路径起点
        self._path_start: QPointF = QPointF()
        # 初始化路径终点
        self._path_end: QPointF = QPointF()
        # 初始化虚线样式列表为空
        self._dash_pattern: list = []

        # 设置Z序为5（使连线位于节点之上但在选中高亮之下）
        self.setZValue(5)
        # 启用鼠标悬停事件
        self.setAcceptHoverEvents(True)
        # 设置可选中的标志
        self.setFlag(QGraphicsObject.ItemIsSelectable, True)

        # 如果存在源插座
        if from_socket is not None:
            # 重建路径（根据起点和终点计算连线路径）
            self._rebuild()

        # 如果存在连线数据且包含文本
        if link_data and link_data.text:
            # 设置文本标签
            self.set_label(link_data.text)

    # ── 状态管理 ────────────────────────────────────────────────────────────────

    def set_state(self, state: str):
        """设置连线状态并触发重绘"""
        # 保存状态值
        self._state = state
        # 触发重绘
        self.update()

    # ── 可见性管理 ───────────────────────────────────────────────────────────

    def show_preview(self, from_socket):
        """显示预览连线（拖拽创建连线时）"""
        # 设置源插座
        self.from_socket = from_socket
        # 清空目标插座
        self.to_socket = None
        # 清空连线数据
        self.link_data = None
        # 设置状态为正常
        self._state = EdgeState.NORMAL
        # 使用动态虚线样式
        self._dash_pattern = list(DASH_DYNAMIC)
        # 临时终点设为源插座的中心场景坐标（如果源插座存在，否则为原点）
        self._temp_end = from_socket.get_center_scene_pos() if from_socket else QPointF()
        # 重建路径
        self._rebuild()
        # 设置为可见
        self.setVisible(True)
        # 预览连线不可选中
        self.setFlag(QGraphicsObject.ItemIsSelectable, False)

    def hide_preview(self):
        """隐藏预览连线"""
        # 清空源插座
        self.from_socket = None
        # 清空目标插座
        self.to_socket = None
        # 清空临时终点
        self._temp_end = None
        # 清空连线数据
        self.link_data = None
        # 清空虚线样式
        self._dash_pattern = []
        # 重置状态为正常
        self._state = EdgeState.NORMAL
        # 设置空路径
        self.setPath(QPainterPath())
        # 清空箭头多边形
        self._arrow_poly = QPolygonF()
        # 设置为不可见
        self.setVisible(False)

    # ── 路径管理 ─────────────────────────────────────────────────────────────────

    def _get_start(self) -> QPointF:
        """获取连线起点坐标"""
        # 如果存在缓存的起点且不是空点
        if self._path_start and not self._path_start.isNull():
            # 返回缓存的起点
            return self._path_start
        # 如果源插座存在
        if self.from_socket is not None:
            try:
                # 返回源插座的场景中心坐标
                return self.from_socket.get_center_scene_pos()
            except Exception:
                # 异常时返回原点
                return QPointF()
        # 默认返回原点
        return QPointF()

    def _get_end(self) -> QPointF:
        """获取连线终点坐标"""
        # 如果存在缓存的终点且不是空点
        if self._path_end and not self._path_end.isNull():
            # 返回缓存的终点
            return self._path_end
        # 如果目标插座存在
        if self.to_socket is not None:
            try:
                # 返回目标插座的场景中心坐标
                return self.to_socket.get_center_scene_pos()
            except Exception:
                # 异常时返回原点
                return QPointF()
        # 如果存在临时终点（预览模式）
        if self._temp_end is not None:
            # 返回临时终点
            return self._temp_end
        # 默认返回起点
        return self._get_start()

    def _rebuild(self):
        """重建连线的路径和箭头"""
        # 没有源插座时无法构建路径，直接返回
        if self.from_socket is None:
            return

        # 获取起点坐标
        start = self._get_start()
        # 获取终点坐标
        end = self._get_end()
        # 获取源插座的停靠位置（上/下/左/右）
        from_dock = self.from_socket.port.dock
        # 获取目标插座的停靠位置（如果目标插座存在，否则默认为顶部）
        to_dock = self.to_socket.port.dock if self.to_socket else PortDock.TOP

        # 计算起点到终点的欧几里得距离
        length = math.sqrt((end.x() - start.x()) ** 2 + (end.y() - start.y()) ** 2)

        try:
            # 如果距离小于0.5像素（几乎重合）
            if length < 0.5:
                # 创建新路径
                self._path = QPainterPath()
                # 在起点位置绘制一个半径为1的小圆点
                self._path.addEllipse(start, 1.0, 1.0)
                # 清空箭头多边形
                self._arrow_poly = QPolygonF()
            else:
                # 使用绘制器的draw_path方法绘制路径
                self._path = self._drawer.draw_path(start, end, from_dock, to_dock)
                # 基于路径末端切线计算箭头方向，避免折线/曲线出现箭头朝向偏斜
                self._arrow_poly = self._arrow_from_path(self._path, start, end)
        except Exception:
            # 发生异常时退化为直线
            self._path = QPainterPath()
            # 移动到起点
            self._path.moveTo(start)
            # 画直线到终点
            self._path.lineTo(end)
            # 清空箭头多边形
            self._arrow_poly = QPolygonF()

        # 如果存在文本标签项
        if self._label_item:
            # 计算连线中点坐标
            mid = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
            # 将标签移动到中点右偏5像素、上偏12像素的位置
            self._label_item.setPos(mid + QPointF(5, -12))

        # 通知图形项几何形状即将改变
        self.prepareGeometryChange()

    def _arrow_from_path(self, path: QPainterPath, start: QPointF, end: QPointF) -> QPolygonF:
        """按路径末端切线方向生成箭头。"""
        arrow_size = self._adaptive_arrow_size()
        tip = self._target_tip(end)

        # 退化路径回退到原逻辑
        if path.isEmpty():
            return self._build_arrow(start, tip, arrow_size)

        path_tip = path.pointAtPercent(1.0)
        # 从路径末端向前采样，找到第一个与末端有足够距离的点作为方向参考
        for t in (0.99, 0.97, 0.95, 0.90, 0.80):
            ref = path.pointAtPercent(t)
            dx = path_tip.x() - ref.x()
            dy = path_tip.y() - ref.y()
            if dx * dx + dy * dy > 0.25:
                return self._build_arrow(ref, tip, arrow_size)

        # 路径过短时使用端点向量兜底
        return self._build_arrow(start, tip, arrow_size)

    def _target_tip(self, fallback_end: QPointF) -> QPointF:
        """返回箭头尖端坐标：优先吸附到目标 Socket 中心。"""
        if self.to_socket is not None:
            try:
                return self.to_socket.get_center_scene_pos()
            except Exception:
                pass
        return fallback_end

    def _adaptive_arrow_size(self) -> float:
        """根据视图缩放做轻微箭头尺寸自适应。"""
        scale = self._view_scale()
        if scale <= 0:
            return ARROW_SIZE

        # 轻微自适应：缩放大时略小，缩放小时略大，避免视觉抖动
        factor = (1.0 / scale) ** 0.18
        factor = max(0.86, min(1.18, factor))
        return ARROW_SIZE * factor

    def _view_scale(self) -> float:
        """读取当前视图主缩放（scene 无视图时返回 1.0）。"""
        s = self.scene()
        if s is None:
            return 1.0
        views = s.views()
        if not views:
            return 1.0

        v = views[0]
        if not isinstance(v, QGraphicsView):
            return 1.0

        tr = v.transform()
        sx = math.hypot(tr.m11(), tr.m21())
        sy = math.hypot(tr.m22(), tr.m12())
        scale = (sx + sy) * 0.5
        return scale if scale > 1e-6 else 1.0

    def _build_arrow(self, start: QPointF, tip: QPointF, size: float) -> QPolygonF:
        """按起止方向和给定尺寸生成箭头三角形。"""
        dx = tip.x() - start.x()
        dy = tip.y() - start.y()
        length = math.hypot(dx, dy)
        if length < 0.5:
            return QPolygonF()

        ux, uy = dx / length, dy / length
        half_base = size * 0.5
        return QPolygonF([
            QPointF(tip.x(), tip.y()),
            QPointF(tip.x() - ux * size + uy * half_base,
                    tip.y() - uy * size - ux * half_base),
            QPointF(tip.x() - ux * size - uy * half_base,
                    tip.y() - uy * size + ux * half_base),
        ])

    def update_path(self):
        """更新路径并触发重绘"""
        # 重建路径
        self._rebuild()
        # 触发重绘
        self.update()

    def setPath(self, path: QPainterPath):
        """设置路径"""
        # 通知几何形状即将改变
        self.prepareGeometryChange()
        # 保存路径
        self._path = QPainterPath(path)

    def set_temp_end(self, pos: QPointF):
        """设置临时终点（用于预览）"""
        # 保存临时终点坐标
        self._temp_end = pos
        # 重建路径
        self._rebuild()
        # 触发重绘
        self.update()

    # ── 边界计算 ───────────────────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        """返回边界矩形"""
        # 获取路径的边界矩形
        r = self._path.boundingRect()
        # 如果存在箭头多边形且不为空
        if self._arrow_poly and not self._arrow_poly.isEmpty():
            # 将箭头多边形的边界与路径边界合并
            r = r.united(self._arrow_poly.boundingRect())
        # 如果边界有效，向外扩展8像素作为点击热区
        return r.adjusted(-8, -8, 8, 8) if r.isValid() else QRectF(-10, -10, 20, 20)

    def shape(self) -> QPainterPath:
        """返回形状（用于鼠标点击检测）"""
        # 如果路径为空，返回空路径
        if self._path.isEmpty():
            return QPainterPath()

        # 获取路径的边界矩形
        br = self._path.boundingRect()
        # 如果路径太短（宽度和高度都小于最小路径长度）
        if br.width() < MIN_PATH_LENGTH and br.height() < MIN_PATH_LENGTH:
            # 直接返回路径本身作为形状
            return self._path

        try:
            # 创建路径描边器
            stroker = QPainterPathStroker()
            # 设置描边宽度为10像素（扩大点击区域）
            stroker.setWidth(10.0)
            # 返回描边后的路径作为形状
            return stroker.createStroke(self._path)
        except Exception:
            # 异常时返回原始路径
            return self._path

    # ── 画笔 —— 绘制时从主题解析颜色 ────

    def _active_pen(self) -> QPen:
        """构建 QPen —— 颜色在调用时从 theme_manager 解析。

        每次调用重新解析颜色，使主题变更在下次绘制时生效。
        """
        # 获取基础颜色（从主题中获取"edge"颜色）
        base_color = _edge_color("edge")
        # 如果连线数据存在且有自定义的stroke_color属性
        if self.link_data is not None and hasattr(self.link_data, 'stroke_color'):
            # 获取连线的自定义颜色
            sc = self.link_data.stroke_color
            # 如果自定义颜色存在
            if sc:
                # 用自定义颜色覆盖基础颜色
                base_color = QColor(sc)

        # 根据状态覆盖颜色和样式
        # 如果是运行中状态
        if self._state == EdgeState.RUNNING:
            return QPen(_edge_color("edge_running"), 2.0, cap=Qt.RoundCap, join=Qt.RoundJoin)

        # 如果是成功状态
        if self._state == EdgeState.SUCCESS:
            # 创建成功状态画笔：颜色从主题获取，线宽2.0，圆头端点，圆角连接
            return QPen(_edge_color("edge_success"), 2.0, cap=Qt.RoundCap, join=Qt.RoundJoin)

        # 如果是错误状态
        if self._state == EdgeState.ERROR:
            # 创建错误状态画笔：颜色从主题获取，线宽2.0，圆头端点，圆角连接
            return QPen(_edge_color("edge_error"), 2.0, cap=Qt.RoundCap, join=Qt.RoundJoin)

        # 如果设置了虚线样式（动态或非流式）
        if self._dash_pattern:
            # 创建虚线画笔：使用基础颜色，线宽1.0，圆头端点，圆角连接
            pen = QPen(base_color, 1.0, cap=Qt.RoundCap, join=Qt.RoundJoin)
            # 设置虚线样式
            pen.setDashPattern(self._dash_pattern)
            return pen

        # 如果连线被选中
        if self.isSelected():
            # 创建选中状态画笔：颜色从主题获取，线宽2.5，圆头端点，圆角连接
            return QPen(_edge_color("edge_selected"), 2.5, cap=Qt.RoundCap, join=Qt.RoundJoin)

        # 如果鼠标悬停
        if self._hovered:
            # 创建悬停状态画笔：颜色从主题获取，线宽3.0，圆头端点，圆角连接
            return QPen(_edge_color("edge_hover"), 3.0, cap=Qt.RoundCap, join=Qt.RoundJoin)

        # 默认样式画笔：基础颜色，线宽2.0，圆头端点，圆角连接
        return QPen(base_color, 2.0, cap=Qt.RoundCap, join=Qt.RoundJoin)

    # ── 绘制 ───────────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        """绘制连线"""
        # 启用抗锯齿渲染
        painter.setRenderHint(QPainter.Antialiasing)
        # 获取当前有效的画笔
        pen = self._active_pen()
        # 设置画笔
        painter.setPen(pen)
        # 设置画刷为无填充
        painter.setBrush(Qt.NoBrush)

        # 如果路径不为空
        if not self._path.isEmpty():
            # 绘制路径
            painter.drawPath(self._path)

        # 如果箭头多边形存在且不为空
        if self._arrow_poly and not self._arrow_poly.isEmpty():
            # 设置画刷为画笔颜色
            painter.setBrush(QBrush(pen.color()))
            # 设置画笔为无笔（只填充不描边）
            painter.setPen(Qt.NoPen)
            # 绘制箭头多边形
            painter.drawPolygon(self._arrow_poly)

    # ── 标签管理 ────────────────────────────────────────────────────────────────

    def set_label(self, text: str):
        """设置连线上的文本标签"""
        # 如果文本为空
        if not text:
            # 移除标签
            self.remove_label()
            return

        # 如果标签项不存在
        if not self._label_item:
            # 创建文本标签项，父对象为当前连线
            self._label_item = QGraphicsTextItem(self)
            # 设置字体为 Segoe UI，大小8
            self._label_item.setFont(QFont("Segoe UI", 8))
            # 设置默认文字颜色（从主题获取次要文字颜色）
            self._label_item.setDefaultTextColor(_edge_color("text_secondary"))
            # 设置Z序为6（略高于连线）
            self._label_item.setZValue(6)

        # 设置标签的纯文本内容
        self._label_item.setPlainText(text)
        # 重建路径（更新标签位置）
        self._rebuild()

    def remove_label(self):
        """移除文本标签"""
        # 如果标签项存在
        if self._label_item:
            # 从父对象分离
            self._label_item.setParentItem(None)
            # 如果场景存在
            if self.scene():
                # 从场景中移除标签项
                self.scene().removeItem(self._label_item)
            # 清空标签项引用
            self._label_item = None

    # ── 清理 ──────────────────────────────────────────────────────────────

    def disconnect(self):
        """断开连线，清理所有引用"""
        # 移除文本标签
        self.remove_label()
        # 尝试从源插座中移除本连线
        try:
            if self.from_socket:
                self.from_socket.remove_edge(self)
        except Exception:
            # 忽略异常
            pass
        # 尝试从目标插座中移除本连线
        try:
            if self.to_socket:
                self.to_socket.remove_edge(self)
        except Exception:
            # 忽略异常
            pass
        # 清空源插座引用
        self.from_socket = None
        # 清空目标插座引用
        self.to_socket = None
        # 清空连线数据引用
        self.link_data = None
        # 清空临时终点
        self._temp_end = None

    # ── 鼠标事件 ────────────────────────────────────────────────────────────────

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        """鼠标进入事件"""
        # 设置悬停标志为True
        self._hovered = True
        # 触发重绘
        self.update()
        # 调用父类的悬停进入事件处理
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        """鼠标离开事件"""
        # 设置悬停标志为False
        self._hovered = False
        # 触发重绘
        self.update()
        # 调用父类的悬停离开事件处理
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """鼠标按下事件"""
        # 如果按下的是左键
        if event.button() == Qt.LeftButton:
            # 发出选中信号，传递当前连线对象
            self.edge_selected.emit(self)
        # 触发重绘
        self.update()
        # 调用父类的鼠标按下事件处理
        super().mousePressEvent(event)
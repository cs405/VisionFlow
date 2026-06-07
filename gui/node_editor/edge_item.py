"""Edge (link) graphics item.

Colors are resolved from theme_manager at paint time — no hardcoded values.
"""

import math
from PyQt5.QtWidgets import (QGraphicsObject, QGraphicsSceneMouseEvent,
                              QStyleOptionGraphicsItem, QWidget, QGraphicsTextItem)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainterPath, QPainter,
                          QPolygonF, QFont, QPainterPathStroker)

from core.node_base import LinkData, PortDock
from gui.node_editor.link_drawer import ILinkDrawer, BrokenLinkDrawer
from gui.theme import theme_manager

# ── Dash patterns (StrokeDashArray — structural, not color) ──
DASH_DYNAMIC = [5, 2]
DASH_RUNNING = [4, 4]
DASH_NONFLOW = [5, 5]

ARROW_SIZE = 8.0
MIN_PATH_LENGTH = 1.0

# ── Helper: resolve edge color from theme ──
def _edge_color(key: str) -> QColor:
    return theme_manager.color(key)


class EdgeState:
    NORMAL = "normal"
    SELECTED = "selected"
    HOVER = "hover"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class EdgeItem(QGraphicsObject):
    """Link between two SocketItems

    Qt:  _active_pen() → theme_manager.color("edge_xxx") at paint time.
    """

    edge_selected = pyqtSignal(object)

    def __init__(self, from_socket=None, to_socket=None, link_data=None,
                 drawer: ILinkDrawer = None, parent=None):
        super().__init__(parent)
        self.from_socket = from_socket
        self.to_socket = to_socket
        self.link_data = link_data
        self._drawer = drawer or BrokenLinkDrawer()
        self._hovered = False
        self._state = EdgeState.NORMAL
        self._temp_end = None
        self._label_item = None
        self._path = QPainterPath()
        self._arrow_poly = QPolygonF()
        self._path_start: QPointF = QPointF()
        self._path_end: QPointF = QPointF()
        self._dash_pattern: list = []

        self.setZValue(5)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsObject.ItemIsSelectable, True)

        if from_socket is not None:
            self._rebuild()

        if link_data and link_data.text:
            self.set_label(link_data.text)

    # ── State ────────────────────────────────────────────────────────────────

    def set_state(self, state: str):
        self._state = state
        self.update()

    # ── Visibility ───────────────────────────────────────────────────────────

    def show_preview(self, from_socket):
        self.from_socket = from_socket
        self.to_socket = None
        self.link_data = None
        self._state = EdgeState.NORMAL
        self._dash_pattern = list(DASH_DYNAMIC)
        self._temp_end = from_socket.get_center_scene_pos() if from_socket else QPointF()
        self._rebuild()
        self.setVisible(True)
        self.setFlag(QGraphicsObject.ItemIsSelectable, False)

    def hide_preview(self):
        self.from_socket = None
        self.to_socket = None
        self._temp_end = None
        self.link_data = None
        self._dash_pattern = []
        self._state = EdgeState.NORMAL
        self.setPath(QPainterPath())
        self._arrow_poly = QPolygonF()
        self.setVisible(False)

    # ── Path ─────────────────────────────────────────────────────────────────

    def _get_start(self) -> QPointF:
        if self._path_start and not self._path_start.isNull():
            return self._path_start
        if self.from_socket is not None:
            try: return self.from_socket.get_center_scene_pos()
            except Exception: return QPointF()
        return QPointF()

    def _get_end(self) -> QPointF:
        if self._path_end and not self._path_end.isNull():
            return self._path_end
        if self.to_socket is not None:
            try: return self.to_socket.get_center_scene_pos()
            except Exception: return QPointF()
        if self._temp_end is not None:
            return self._temp_end
        return self._get_start()

    def _rebuild(self):
        if self.from_socket is None:
            return
        start = self._get_start()
        end = self._get_end()
        from_dock = self.from_socket.port.dock
        to_dock = self.to_socket.port.dock if self.to_socket else PortDock.TOP

        length = math.sqrt((end.x() - start.x()) ** 2 + (end.y() - start.y()) ** 2)
        try:
            if length < 0.5:
                self._path = QPainterPath()
                self._path.addEllipse(start, 1.0, 1.0)
                self._arrow_poly = QPolygonF()
            else:
                self._path = self._drawer.draw_path(start, end, from_dock, to_dock)
                self._arrow_poly = self._drawer.arrow(start, end)
        except Exception:
            self._path = QPainterPath()
            self._path.moveTo(start); self._path.lineTo(end)
            self._arrow_poly = QPolygonF()

        if self._label_item:
            mid = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
            self._label_item.setPos(mid + QPointF(5, -12))

        self.prepareGeometryChange()

    def update_path(self):
        self._rebuild(); self.update()

    def setPath(self, path: QPainterPath):
        self.prepareGeometryChange()
        self._path = QPainterPath(path)

    def set_temp_end(self, pos: QPointF):
        self._temp_end = pos; self._rebuild(); self.update()

    # ── Bounds ───────────────────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        r = self._path.boundingRect()
        if self._arrow_poly and not self._arrow_poly.isEmpty():
            r = r.united(self._arrow_poly.boundingRect())
        return r.adjusted(-8, -8, 8, 8) if r.isValid() else QRectF(-10, -10, 20, 20)

    def shape(self) -> QPainterPath:
        if self._path.isEmpty():
            return QPainterPath()
        br = self._path.boundingRect()
        if br.width() < MIN_PATH_LENGTH and br.height() < MIN_PATH_LENGTH:
            return self._path
        try:
            stroker = QPainterPathStroker()
            stroker.setWidth(10.0)
            return stroker.createStroke(self._path)
        except Exception:
            return self._path

    # ── Pen — resolved from theme at paint time ────

    def _active_pen(self) -> QPen:
        """Build QPen — colors resolved from theme_manager at call time.

        Each call re-resolves colors so theme changes take effect on next paint.
        """

        base_color = _edge_color("edge")
        if self.link_data is not None and hasattr(self.link_data, 'stroke_color'):
            sc = self.link_data.stroke_color
            if sc:
                base_color = QColor(sc)

        # State overrides
        if self._state == EdgeState.RUNNING:
            pen = QPen(_edge_color("edge_running"), 2.0, cap=Qt.RoundCap, join=Qt.RoundJoin)
            pen.setDashPattern(DASH_RUNNING)
            return pen
        if self._state == EdgeState.SUCCESS:
            return QPen(_edge_color("edge_success"), 2.0, cap=Qt.RoundCap, join=Qt.RoundJoin)
        if self._state == EdgeState.ERROR:
            return QPen(_edge_color("edge_error"), 2.0, cap=Qt.RoundCap, join=Qt.RoundJoin)

        # Dynamic / non-flowable dash
        if self._dash_pattern:
            pen = QPen(base_color, 1.0, cap=Qt.RoundCap, join=Qt.RoundJoin)
            pen.setDashPattern(self._dash_pattern)
            return pen

        # Selection / hover
        if self.isSelected():
            return QPen(_edge_color("edge_selected"), 2.5, cap=Qt.RoundCap, join=Qt.RoundJoin)
        if self._hovered:
            return QPen(_edge_color("edge_hover"), 3.0, cap=Qt.RoundCap, join=Qt.RoundJoin)

        return QPen(base_color, 2.0, cap=Qt.RoundCap, join=Qt.RoundJoin)

    # ── Paint ───────────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        painter.setRenderHint(QPainter.Antialiasing)
        pen = self._active_pen()
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        if not self._path.isEmpty():
            painter.drawPath(self._path)
        if self._arrow_poly and not self._arrow_poly.isEmpty():
            painter.setBrush(QBrush(pen.color()))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(self._arrow_poly)

    # ── Label ────────────────────────────────────────────────────────────────

    def set_label(self, text: str):
        if not text:
            self.remove_label(); return
        if not self._label_item:
            self._label_item = QGraphicsTextItem(self)
            self._label_item.setFont(QFont("Segoe UI", 8))
            self._label_item.setDefaultTextColor(_edge_color("text_secondary"))
            self._label_item.setZValue(6)
        self._label_item.setPlainText(text)
        self._rebuild()

    def remove_label(self):
        if self._label_item:
            self._label_item.setParentItem(None)
            if self.scene(): self.scene().removeItem(self._label_item)
            self._label_item = None

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def disconnect(self):
        self.remove_label()
        try:
            if self.from_socket: self.from_socket.remove_edge(self)
        except Exception: pass
        try:
            if self.to_socket: self.to_socket.remove_edge(self)
        except Exception: pass
        self.from_socket = None
        self.to_socket = None
        self.link_data = None
        self._temp_end = None

    # ── Mouse ────────────────────────────────────────────────────────────────

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        self._hovered = True; self.update(); super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        self._hovered = False; self.update(); super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton:
            self.edge_selected.emit(self)
        self.update()
        super().mousePressEvent(event)

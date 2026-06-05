"""Edge (link) graphics item — WPF Link + ILinkDrawer 1:1 port.

Single QGraphicsObject per link. Path computed by ILinkDrawer strategy.
Supports reuse as a dynamic preview edge (WPF _dynamicLink in DynamicLayer).

Colors — exact WPF BrushKeys from Link.xaml triggers:
  Default:     #606266  (Foreground)
  Selected:    #3399FF  (Accent)
  Hover:       #0078d4  (MouseOver with shadow effect)
  Running:     #3399FF  animated dash "4 4"
  Success:     #67C23A  (Green)
  Error:       #dc000c  (Red)

Dash patterns — exact WPF StrokeDashArray:
  Default:     solid
  Dynamic:     "5 2"    (S.Link.Dash)
  Running:     "4 4"    animated
  Non-flow:    "5 5"    (not IFlowable)
"""

import math
from PyQt5.QtWidgets import (QGraphicsObject, QGraphicsSceneMouseEvent,
                              QStyleOptionGraphicsItem, QWidget, QGraphicsTextItem)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainterPath, QPainter,
                          QPolygonF, QFont, QPainterPathStroker)

from core.node_base import LinkData, PortDock
from gui.node_editor.link_drawer import ILinkDrawer, BrokenLinkDrawer

# ── WPF Link.xaml BrushKeys colors (WPF-VisionMaster flowable link defaults) ──

EDGE_COLOR = QColor("#67C23A")           # WPF BrushKeys.Green — default flowable link (VisionMaster)
EDGE_COLOR_SELECTED = QColor("#3399FF")  # WPF BrushKeys.Accent — IsSelected trigger
EDGE_COLOR_HOVER = QColor("#0078d4")     # MouseOver blue
EDGE_COLOR_RUNNING = QColor("#3399FF")   # WPF BrushKeys.Accent — State=Running + marching ants
EDGE_COLOR_SUCCESS = QColor("#67C23A")   # WPF BrushKeys.Green — State=Success
EDGE_COLOR_ERROR = QColor("#dc000c")     # WPF BrushKeys.Red — State=Error
EDGE_COLOR_ORANGE = QColor("#E6A23C")    # WPF BrushKeys.Orange — IsDragEnter

EDGE_WIDTH = 2.0                         # WPF default StrokeThickness
EDGE_WIDTH_SELECTED = 2.5
EDGE_WIDTH_HOVER = 3.0
EDGE_WIDTH_DYNAMIC = 1.0                 # WPF S.Link.Dash StrokeThickness=1

# ── WPF dash patterns ──
DASH_DYNAMIC = [5, 2]     # WPF S.Link.Dash: StrokeDashArray="5 2"
DASH_RUNNING = [4, 4]     # WPF State=Running: StrokeDashArray="4 4"
DASH_NONFLOW = [5, 5]     # WPF not IFlowable: StrokeDashArray="5 5"

ARROW_SIZE = 8.0
MIN_PATH_LENGTH = 1.0


class EdgeState:
    """Edge visual states — matching WPF Link state triggers."""
    NORMAL = "normal"
    SELECTED = "selected"
    HOVER = "hover"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class EdgeItem(QGraphicsObject):
    """Link between two SocketItems — WPF Link equivalent.

    WPF architecture:
      - Link is ContentPresenter + Path (visual child via AddVisualChild)
      - Path.Data = Geometry from ILinkDrawer.DrawPath()
      - Content = ILinkData (DefaultLinkData with Message)
      - Colors via DataTrigger on State, IsSelected, IsMouseOver
      - Dash patterns via DataTrigger (Running, non-IFlowable)

    Qt equivalent:
      - QGraphicsObject with QPainterPath + QGraphicsTextItem for label
      - _rebuild() → drawer.draw_path() → self._path
      - Color selection in _active_pen() by state
    """

    edge_selected = pyqtSignal(object)

    def __init__(self, from_socket=None, to_socket=None, link_data=None,
                 drawer: ILinkDrawer = None, parent=None):
        super().__init__(parent)
        self.from_socket = from_socket
        self.to_socket = to_socket
        self.link_data = link_data
        self._drawer = drawer or BrokenLinkDrawer()   # WPF default: BrokenLinkDrawer (折线)
        self._hovered = False
        self._state = EdgeState.NORMAL
        self._temp_end = None
        self._label_item = None
        self._path = QPainterPath()
        self._arrow_poly = QPolygonF()
        self._path_start: QPointF = QPointF()
        self._path_end: QPointF = QPointF()
        self._dash_pattern: list = []   # WPF StrokeDashArray — empty = solid

        self.setZValue(5)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsObject.ItemIsSelectable, True)

        if from_socket is not None:
            self._rebuild()

        if link_data and link_data.text:
            self.set_label(link_data.text)

    # ── State management (WPF DataTriggers) ──────────────────────────────────

    def set_state(self, state: str):
        """Set visual state — WPF Link DataTriggers on State property."""
        self._state = state
        self.update()

    # ── Visibility (WPF _dynamicLink singleton) ──────────────────────────────

    def show_preview(self, from_socket):
        """Reset for drag preview — WPF InitDynamic: show _dynamicLink."""
        self.from_socket = from_socket
        self.to_socket = None
        self.link_data = None
        self._state = EdgeState.NORMAL
        self._dash_pattern = list(DASH_DYNAMIC)   # WPF S.Link.Dash
        self._temp_end = from_socket.get_center_scene_pos() if from_socket else QPointF()
        self._rebuild()
        self.setVisible(True)
        self.setFlag(QGraphicsObject.ItemIsSelectable, False)

    def hide_preview(self):
        """Hide — WPF _dynamicLink.Visibility = Collapsed."""
        self.from_socket = None
        self.to_socket = None
        self._temp_end = None
        self.link_data = None
        self._dash_pattern = []
        self._state = EdgeState.NORMAL
        self.setPath(QPainterPath())
        self._arrow_poly = QPolygonF()
        self.setVisible(False)

    # ── Path computation (WPF link.Update → Draw) ──────────────────────────

    def _get_start(self) -> QPointF:
        if self._path_start and not self._path_start.isNull():
            return self._path_start
        if self.from_socket is not None:
            try:
                return self.from_socket.get_center_scene_pos()
            except Exception:
                return QPointF()
        return QPointF()

    def _get_end(self) -> QPointF:
        if self._path_end and not self._path_end.isNull():
            return self._path_end
        if self.to_socket is not None:
            try:
                return self.to_socket.get_center_scene_pos()
            except Exception:
                return QPointF()
        if self._temp_end is not None:
            return self._temp_end
        return self._get_start()

    def _rebuild(self):
        """Rebuild path — WPF link.Draw(start, end)."""
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
            self._path.moveTo(start)
            self._path.lineTo(end)
            self._arrow_poly = QPolygonF()

        if self._label_item:
            mid = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
            self._label_item.setPos(mid + QPointF(5, -12))

        self.prepareGeometryChange()

    def update_path(self):
        self._rebuild()
        self.update()

    def setPath(self, path: QPainterPath):
        self.prepareGeometryChange()
        self._path = QPainterPath(path)

    def set_temp_end(self, pos: QPointF):
        self._temp_end = pos
        self._rebuild()
        self.update()

    # ── Bounds ───────────────────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        r = self._path.boundingRect()
        if self._arrow_poly and not self._arrow_poly.isEmpty():
            r = r.united(self._arrow_poly.boundingRect())
        return r.adjusted(-8, -8, 8, 8) if r.isValid() else QRectF(-10, -10, 20, 20)

    def shape(self) -> QPainterPath:
        """Hit-test shape. Safe for degenerate paths."""
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

    # ── Color & Pen — WPF Style triggers 1:1 ────────────────────────────────

    def _active_pen(self) -> QPen:
        """Build QPen matching WPF Link.xaml DataTriggers.

        WPF: Stroke="{Binding Stroke}" from link data, with DataTrigger fallbacks.
        """
        # WPF: {Binding Stroke} from link data — use link_data.stroke_color if set
        base_color = EDGE_COLOR
        if self.link_data is not None and hasattr(self.link_data, 'stroke_color'):
            sc = self.link_data.stroke_color
            if sc:
                base_color = QColor(sc)

        # State-based colors take priority (WPF DataTrigger order)
        if self._state == EdgeState.RUNNING:
            pen = QPen(EDGE_COLOR_RUNNING, 2.0, cap=Qt.RoundCap, join=Qt.RoundJoin)
            pen.setDashPattern(DASH_RUNNING)
            return pen
        if self._state == EdgeState.SUCCESS:
            return QPen(EDGE_COLOR_SUCCESS, EDGE_WIDTH, cap=Qt.RoundCap, join=Qt.RoundJoin)
        if self._state == EdgeState.ERROR:
            return QPen(EDGE_COLOR_ERROR, EDGE_WIDTH, cap=Qt.RoundCap, join=Qt.RoundJoin)

        # Non-flowable / dynamic — dashed (WPF: S.Link.Dash / not IFlowable)
        if self._dash_pattern:
            pen = QPen(base_color, EDGE_WIDTH_DYNAMIC, cap=Qt.RoundCap, join=Qt.RoundJoin)
            pen.setDashPattern(self._dash_pattern)
            return pen

        # Selection / hover
        if self.isSelected():
            return QPen(EDGE_COLOR_SELECTED, EDGE_WIDTH_SELECTED, cap=Qt.RoundCap, join=Qt.RoundJoin)
        if self._hovered:
            return QPen(EDGE_COLOR_HOVER, EDGE_WIDTH_HOVER, cap=Qt.RoundCap, join=Qt.RoundJoin)

        # Default — WPF {Binding Stroke} or BrushKeys.Green
        return QPen(base_color, EDGE_WIDTH, cap=Qt.RoundCap, join=Qt.RoundJoin)

    # ── Paint ───────────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        painter.setRenderHint(QPainter.Antialiasing)
        pen = self._active_pen()
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        if not self._path.isEmpty():
            painter.drawPath(self._path)
        # Arrow — filled with pen color (WPF arrow by GetArrowGeometry)
        if self._arrow_poly and not self._arrow_poly.isEmpty():
            painter.setBrush(QBrush(pen.color()))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(self._arrow_poly)

    # ── Label (WPF ContentPresenter for link text) ──────────────────────────

    def set_label(self, text: str):
        if not text:
            self.remove_label()
            return
        if not self._label_item:
            self._label_item = QGraphicsTextItem(self)
            self._label_item.setFont(QFont("Segoe UI", 8))
            self._label_item.setDefaultTextColor(QColor("#606266"))  # WPF Foreground
            self._label_item.setZValue(6)
        self._label_item.setPlainText(text)
        self._rebuild()

    def remove_label(self):
        if self._label_item:
            self._label_item.setParentItem(None)
            if self.scene():
                self.scene().removeItem(self._label_item)
            self._label_item = None

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def disconnect(self):
        self.remove_label()
        try:
            if self.from_socket:
                self.from_socket.remove_edge(self)
        except Exception:
            pass
        try:
            if self.to_socket:
                self.to_socket.remove_edge(self)
        except Exception:
            pass
        self.from_socket = None
        self.to_socket = None
        self.link_data = None
        self._temp_end = None

    # ── Mouse ────────────────────────────────────────────────────────────────

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton:
            self.edge_selected.emit(self)
        self.update()
        super().mousePressEvent(event)

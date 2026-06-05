"""ILinkDrawer — WPF ILinkDrawer / BrokenLinkDrawer / BezierLinkDrawer / LineLinkDrawer 1:1 port.

Strategy pattern for computing link geometry from start/end points and port docks.
Decoupled from EdgeItem — replaceable per Diagram (like WPF Diagram.LinkDrawer).

WPF default: BrokenLinkDrawer (orthogonal折线) — see Diagram.RefreshLinkDrawer().
"""

import math
from PyQt5.QtCore import QPointF, QLineF
from PyQt5.QtGui import QPainterPath, QPolygonF
from core.node_base import PortDock

ARROW_SIZE = 8.0


# ═══════════════════════════════════════════════════════════════════════════
# ILinkDrawer — WPF ILinkDrawer interface
# ═══════════════════════════════════════════════════════════════════════════

class ILinkDrawer:
    """Abstract link geometry strategy (WPF ILinkDrawer)."""

    def draw_path(self, start: QPointF, end: QPointF,
                  from_dock: PortDock = PortDock.BOTTOM,
                  to_dock: PortDock = PortDock.TOP) -> QPainterPath:
        raise NotImplementedError

    def arrow(self, start: QPointF, end: QPointF) -> QPolygonF:
        """Arrowhead at end point — WPF GetArrowPoints using rotation matrix.

        Returns an empty polygon for degenerate (near-zero-length) inputs.
        """
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length < 0.5:
            return QPolygonF()
        dx, dy = dx / length, dy / length
        s = ARROW_SIZE
        return QPolygonF([
            QPointF(end.x(), end.y()),
            QPointF(end.x() - dx * s + dy * s * 0.5,
                     end.y() - dy * s - dx * s * 0.5),
            QPointF(end.x() - dx * s - dy * s * 0.5,
                     end.y() - dy * s + dx * s * 0.5),
        ])


# ═══════════════════════════════════════════════════════════════════════════
# Port.ChangedPoint — WPF Port.ChangedPoint(Point, double)
# ═══════════════════════════════════════════════════════════════════════════

def changed_point(pos: QPointF, dock: PortDock, span: float) -> QPointF:
    """Offset a point along its dock direction by span — WPF Port.ChangedPoint().

    This is how WPF computes the "inner point" that the broken line starts
    from before bending. The direction depends on which side of the node
    the port is on.
    """
    if dock == PortDock.BOTTOM:
        return QPointF(pos.x(), pos.y() + span)
    if dock == PortDock.TOP:
        return QPointF(pos.x(), pos.y() - span)
    if dock == PortDock.RIGHT:
        return QPointF(pos.x() + span, pos.y())
    if dock == PortDock.LEFT:
        return QPointF(pos.x() - span, pos.y())
    return pos


# ═══════════════════════════════════════════════════════════════════════════
# LineLinkDrawer — WPF LineLinkDrawer (straight line)
# ═══════════════════════════════════════════════════════════════════════════

class LineLinkDrawer(ILinkDrawer):
    """Straight line (WPF LineLinkDrawer)."""

    def draw_path(self, start, end, from_dock=PortDock.BOTTOM, to_dock=PortDock.TOP):
        path = QPainterPath()
        path.moveTo(start)
        path.lineTo(end)
        return path


# ═══════════════════════════════════════════════════════════════════════════
# BezierLinkDrawer — WPF BezierLinkDrawer (cubic bezier curve)
# ═══════════════════════════════════════════════════════════════════════════

class BezierLinkDrawer(ILinkDrawer):
    """Cubic Bezier with port-dock-aware control points (WPF BezierLinkDrawer)."""

    def __init__(self, span: float = 50.0):
        self.span = span

    def draw_path(self, start, end, from_dock=PortDock.BOTTOM, to_dock=PortDock.TOP):
        ctrl1 = changed_point(start, from_dock, self.span)
        ctrl2 = changed_point(end, to_dock, self.span)
        mx = start.x() + (end.x() - start.x()) / 2.0
        my = start.y() + (end.y() - start.y()) / 2.0
        mid = QPointF(mx, my)
        path = QPainterPath()
        path.moveTo(start)
        path.cubicTo(ctrl1, mid, ctrl2, end)
        return path


# ═══════════════════════════════════════════════════════════════════════════
# BrokenLinkDrawer (DEFAULT) — WPF BrokenLinkDrawer 1:1 port
# ═══════════════════════════════════════════════════════════════════════════

class BrokenLinkDrawer(ILinkDrawer):
    """Orthogonal link routing — 1:1 port of WPF BrokenLinkDrawer.

    Algorithm (matching WPF exactly):
      1. Compute inner1/2 via Port.ChangedPoint(start/end, InnerSpan)
      2. Test two crossing candidates: cross1(inner1.x, inner2.y) and cross2(inner2.x, inner1.y)
      3. Check if each crossing lies on the segment from start->inner1 or end->inner2
         (if so, skip that inner point for a cleaner route)
      4. If both crossings work, choose the one with fewer bends
      5. If neither works, fall back to midline routing
    """

    def __init__(self, inner_span: float = 30.0):
        self.inner_span = inner_span

    def _on_segment(self, p1: QPointF, p2: QPointF, q: QPointF) -> bool:
        """WPF OnSegment — is point Q on line segment P1-P2?"""
        # Cross-product check: (Q-P1) × (P2-P1) == 0 means collinear
        cross = (q.x() - p1.x()) * (p2.y() - p1.y()) - \
                (p2.x() - p1.x()) * (q.y() - p1.y())
        if abs(cross) > 0.001:
            return False
        # Bounding-box check
        return (min(p1.x(), p2.x()) - 0.001 <= q.x() <= max(p1.x(), p2.x()) + 0.001 and
                min(p1.y(), p2.y()) - 0.001 <= q.y() <= max(p1.y(), p2.y()) + 0.001)

    def _bend_count(self, points: list) -> int:
        """WPF GetBrokenCount — count direction changes in polyline."""
        bends = 0
        for i in range(2, len(points)):
            p1, p2, c = points[i - 2], points[i - 1], points[i]
            # If c is NOT on the line from p1 to p2, this is a bend
            if not self._on_segment(p1, c, p2):
                bends += 1
        return bends

    def _center(self, points: list) -> QPointF:
        """WPF GetCenter — find the center of the polyline for label placement."""
        if not points:
            return QPointF()
        # All vertical
        if all(abs(p.x() - points[0].x()) < 0.01 for p in points):
            ys = [p.y() for p in points]
            return QPointF(points[0].x(), (min(ys) + max(ys)) / 2)
        # All horizontal
        if all(abs(p.y() - points[0].y()) < 0.01 for p in points):
            xs = [p.x() for p in points]
            return QPointF((min(xs) + max(xs)) / 2, points[0].y())
        if len(points) > 2:
            return QPointF(points[2].x() / 2 + points[1].x() / 2,
                           points[2].y() / 2 + points[1].y() / 2)
        return points[-1] if points else QPointF()

    def _build_polyline(self, pts: list) -> QPainterPath:
        """Build a QPainterPath from point list."""
        path = QPainterPath()
        if not pts:
            return path
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        return path

    def draw_path(self, start, end, from_dock=PortDock.BOTTOM, to_dock=PortDock.TOP):
        """WPF BrokenLinkDrawer.DrawPath — full orthogonal routing algorithm."""
        inner1 = changed_point(start, from_dock, self.inner_span)
        inner2 = changed_point(end, to_dock, self.inner_span)

        # Two possible crossing configurations
        cross1 = QPointF(inner1.x(), inner2.y())   # vertical first, then horizontal
        cross2 = QPointF(inner2.x(), inner1.y())   # horizontal first, then vertical

        is_cross1 = (not self._on_segment(inner1, cross1, start) and
                     not self._on_segment(inner2, cross1, end))
        is_cross2 = (not self._on_segment(inner1, cross2, start) and
                     not self._on_segment(inner2, cross2, end))

        points: list[QPointF] = []

        if is_cross1 and not is_cross2:
            points.append(start)
            if not self._on_segment(start, inner1, cross1):
                points.append(inner1)
            points.append(cross1)
            if not self._on_segment(end, inner2, cross1):
                points.append(inner2)
            points.append(end)

        elif not is_cross1 and is_cross2:
            points.append(start)
            if not self._on_segment(start, inner1, cross2):
                points.append(inner1)
            points.append(cross2)
            if not self._on_segment(end, inner2, cross2):
                points.append(inner2)
            points.append(end)

        elif is_cross1 and is_cross2:
            # Both work — choose the one with fewer bends
            pts1 = [start]
            if not self._on_segment(start, inner1, cross1):
                pts1.append(inner1)
            pts1.append(cross1)
            if not self._on_segment(end, inner2, cross1):
                pts1.append(inner2)
            pts1.append(end)

            pts2 = [start]
            if not self._on_segment(start, inner1, cross2):
                pts2.append(inner1)
            pts2.append(cross2)
            if not self._on_segment(end, inner2, cross2):
                pts2.append(inner2)
            pts2.append(end)

            if self._bend_count(pts1) > self._bend_count(pts2):
                points = pts2
            else:
                points = pts1
        else:
            # Neither cross works — fallback to midline routing
            line_y = (inner1.y() + inner2.y()) / 2
            ly_start = QPointF(inner1.x(), line_y)
            ly_end = QPointF(inner2.x(), line_y)
            line_x = (inner1.x() + inner2.x()) / 2
            lx_start = QPointF(line_x, inner1.y())
            lx_end = QPointF(line_x, inner2.y())

            is_linex = (not self._on_segment(inner1, ly_start, start) and
                        not self._on_segment(inner2, ly_end, end))

            if is_linex:
                points.append(start)
                if not self._on_segment(start, inner1, ly_start):
                    points.append(inner1)
                points.append(ly_start)
                points.append(ly_end)
                if not self._on_segment(end, inner2, ly_end):
                    points.append(inner2)
                points.append(end)
            else:
                points.append(start)
                if not self._on_segment(start, inner1, lx_start):
                    points.append(inner1)
                points.append(lx_start)
                points.append(lx_end)
                if not self._on_segment(end, inner2, lx_end):
                    points.append(inner2)
                points.append(end)

        return self._build_polyline(points)

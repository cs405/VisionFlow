"""ILinkDrawer — ILinkDrawer / BrokenLinkDrawer / BezierLinkDrawer / LineLinkDrawer 1:1 移植。

从起点/终点和端口停靠位置计算连线几何的策略模式。
与 EdgeItem 解耦 — 每个 Diagram 可替换
"""

import math

from PyQt5.QtCore import QPointF, QLineF
from PyQt5.QtGui import QPainterPath, QPolygonF

from core.node_base import PortDock

# 箭头大小常量（像素）
ARROW_SIZE = 8.0


# ═══════════════════════════════════════════════════════════════════════════
# ILinkDrawer（连线绘制器接口）
# ═══════════════════════════════════════════════════════════════════════════

class ILinkDrawer:
    """抽象的连线几何策略接口。"""

    def draw_path(self, start: QPointF, end: QPointF,
                  from_dock: PortDock = PortDock.BOTTOM,
                  to_dock: PortDock = PortDock.TOP) -> QPainterPath:
        """绘制从起点到终点的路径

        参数：
            start: 起点坐标
            end: 终点坐标
            from_dock: 源端口的停靠位置（上/下/左/右）
            to_dock: 目标端口的停靠位置（上/下/左/右）

        返回：
            绘制好的 QPainterPath 对象
        """
        # 抽象方法，子类必须实现
        raise NotImplementedError

    def arrow(self, start: QPointF, end: QPointF) -> QPolygonF:
        """在终点处绘制箭头

        对于退化的（长度接近零）输入返回空多边形。
        """
        # 计算从起点到终点的方向向量
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        # 计算起点到终点的欧几里得距离
        length = math.sqrt(dx * dx + dy * dy)
        # 如果距离小于0.5像素（几乎重合），不绘制箭头
        if length < 0.5:
            # 返回空多边形
            return QPolygonF()
        # 归一化方向向量（长度为1）
        dx, dy = dx / length, dy / length
        # 箭头大小
        s = ARROW_SIZE
        # 返回箭头多边形（三角形形状）
        return QPolygonF([
            # 箭头尖端（终点位置）
            QPointF(end.x(), end.y()),
            # 左侧翼：从终点倒退 s 距离，再侧向偏移 dy*s*0.5
            QPointF(end.x() - dx * s + dy * s * 0.5, end.y() - dy * s - dx * s * 0.5),
            # 右侧翼：从终点倒退 s 距离，再反向侧向偏移
            QPointF(end.x() - dx * s - dy * s * 0.5, end.y() - dy * s + dx * s * 0.5),
        ])


# ═══════════════════════════════════════════════════════════════════════════
# Port.ChangedPoint（端口偏移点计算）
# ═══════════════════════════════════════════════════════════════════════════

def changed_point(pos: QPointF, dock: PortDock, span: float) -> QPointF:
    """沿端口的停靠方向偏移指定距离

    这是计算折线在弯曲之前开始的"内点"的方法。
    偏移方向取决于端口所在节点的一侧。

    参数：
        pos: 原始位置
        dock: 端口停靠方向
        span: 偏移距离

    返回：
        偏移后的坐标
    """
    # 如果端口停靠在底部
    if dock == PortDock.BOTTOM:
        # Y坐标向下偏移（增加）
        return QPointF(pos.x(), pos.y() + span)
    # 如果端口停靠在顶部
    if dock == PortDock.TOP:
        # Y坐标向上偏移（减少）
        return QPointF(pos.x(), pos.y() - span)
    # 如果端口停靠在右侧
    if dock == PortDock.RIGHT:
        # X坐标向右偏移（增加）
        return QPointF(pos.x() + span, pos.y())
    # 如果端口停靠在左侧
    if dock == PortDock.LEFT:
        # X坐标向左偏移（减少）
        return QPointF(pos.x() - span, pos.y())
    # 未知的停靠位置，返回原位置
    return pos


# ═══════════════════════════════════════════════════════════════════════════
# LineLinkDrawer（直线连线绘制器）
# ═══════════════════════════════════════════════════════════════════════════

class LineLinkDrawer(ILinkDrawer):
    """直线连线绘制器。"""

    def draw_path(self, start, end, from_dock=PortDock.BOTTOM, to_dock=PortDock.TOP):
        """绘制从起点到终点的直线"""
        # 创建一个新的路径对象
        path = QPainterPath()
        # 将画笔移动到起点
        path.moveTo(start)
        # 从起点画直线到终点
        path.lineTo(end)
        # 返回路径
        return path


# ═══════════════════════════════════════════════════════════════════════════
# BezierLinkDrawer（贝塞尔曲线连线绘制器）
# ═══════════════════════════════════════════════════════════════════════════

class BezierLinkDrawer(ILinkDrawer):
    """带端口停靠感知控制点的三次贝塞尔曲线连线绘制器"""

    def __init__(self, span: float = 50.0):
        """初始化贝塞尔曲线绘制器

        参数：
            span: 控制点偏移距离（控制曲线的弯曲程度）
        """
        # 保存控制点偏移距离
        self.span = span

    def draw_path(self, start, end, from_dock=PortDock.BOTTOM, to_dock=PortDock.TOP):
        """绘制贝塞尔曲线路径"""
        # 计算起点侧的控制点（从起点沿端口方向偏移span距离）
        ctrl1 = changed_point(start, from_dock, self.span)
        # 计算终点侧的控制点（从终点沿端口反方向偏移span距离）
        ctrl2 = changed_point(end, to_dock, self.span)
        # 计算起点和终点的中点X坐标
        mx = start.x() + (end.x() - start.x()) / 2.0
        # 计算起点和终点的中点Y坐标
        my = start.y() + (end.y() - start.y()) / 2.0
        # 创建中点坐标
        mid = QPointF(mx, my)
        # 创建新的路径对象
        path = QPainterPath()
        # 将画笔移动到起点
        path.moveTo(start)
        # 绘制三次贝塞尔曲线：起点 → 控制点1 → 中点 → 控制点2 → 终点
        path.cubicTo(ctrl1, mid, ctrl2, end)
        # 返回路径
        return path


# ═══════════════════════════════════════════════════════════════════════════
# BrokenLinkDrawer（折线连线绘制器，默认）
# ═══════════════════════════════════════════════════════════════════════════

class BrokenLinkDrawer(ILinkDrawer):
    """正交连线路由（折线/直角线）。

    算法：
      1. 通过 Port.ChangedPoint(start/end, InnerSpan) 计算 inner1/inner2
      2. 测试两种交叉候选路径：cross1(inner1.x, inner2.y) 和 cross2(inner2.x, inner1.y)
      3. 检查每个交叉点是否位于 start→inner1 或 end→inner2 线段上
         （如果是，跳过该内点以获得更干净的路线）
      4. 如果两种交叉都有效，选择折弯数较少的
      5. 如果都不有效，回退到中线路由
    """

    def __init__(self, inner_span: float = 30.0):
        """初始化折线绘制器

        参数：
            inner_span: 内点偏移距离
        """
        # 保存内点偏移距离
        self.inner_span = inner_span

    def _on_segment(self, p1: QPointF, p2: QPointF, q: QPointF) -> bool:
        """ OnSegment — 判断点 Q 是否在线段 P1-P2 上"""
        # 计算叉积：(Q-P1) × (P2-P1)
        # 叉积为0表示向量共线
        cross = (q.x() - p1.x()) * (p2.y() - p1.y()) - \
                (p2.x() - p1.x()) * (q.y() - p1.y())
        # 如果叉积的绝对值大于0.001，说明不共线，Q不在线段上
        if abs(cross) > 0.001:
            return False
        # 边界框检查：Q的X坐标必须在P1和P2的X坐标之间
        return (min(p1.x(), p2.x()) - 0.001 <= q.x() <= max(p1.x(), p2.x()) + 0.001 and
                # Q的Y坐标必须在P1和P2的Y坐标之间
                min(p1.y(), p2.y()) - 0.001 <= q.y() <= max(p1.y(), p2.y()) + 0.001)

    def _bend_count(self, points: list) -> int:
        """ GetBrokenCount — 计算折线中的方向变化次数（弯折数）"""
        # 初始化弯折数为0
        bends = 0
        # 从第三个点开始遍历（需要前两个点才能判断方向变化）
        for i in range(2, len(points)):
            # 获取前两个点和当前点
            p1, p2, c = points[i - 2], points[i - 1], points[i]
            # 如果当前点 C 不在从 P1 到 P2 的直线上
            if not self._on_segment(p1, c, p2):
                # 这是一个弯折，计数加1
                bends += 1
        # 返回弯折总数
        return bends

    def _center(self, points: list) -> QPointF:
        """ GetCenter — 找到折线的中心点（用于标签放置）"""
        # 如果点列表为空，返回原点
        if not points:
            return QPointF()
        # 检查是否所有点的X坐标相同（垂直线）
        if all(abs(p.x() - points[0].x()) < 0.01 for p in points):
            # 收集所有Y坐标
            ys = [p.y() for p in points]
            # 返回垂直线中心点
            return QPointF(points[0].x(), (min(ys) + max(ys)) / 2)
        # 检查是否所有点的Y坐标相同（水平线）
        if all(abs(p.y() - points[0].y()) < 0.01 for p in points):
            # 收集所有X坐标
            xs = [p.x() for p in points]
            # 返回水平线中心点
            return QPointF((min(xs) + max(xs)) / 2, points[0].y())
        # 如果点数大于2
        if len(points) > 2:
            # 返回第二个点和第三个点的中点（折线拐点附近）
            return QPointF(points[2].x() / 2 + points[1].x() / 2,
                           points[2].y() / 2 + points[1].y() / 2)
        # 默认返回最后一个点
        return points[-1] if points else QPointF()

    def _build_polyline(self, pts: list) -> QPainterPath:
        """从点列表构建带圆角拐弯的 QPainterPath"""
        path = QPainterPath()
        if not pts:
            return path
        if len(pts) < 3:
            path.moveTo(pts[0])
            for p in pts[1:]:
                path.lineTo(p)
            return path

        corner_r = 10.0  # 拐角圆角半径
        path.moveTo(pts[0])

        for i in range(1, len(pts) - 1):
            p0 = pts[i - 1]
            p1 = pts[i]
            p2 = pts[i + 1]

            # 入 / 出向量
            v1 = QPointF(p1.x() - p0.x(), p1.y() - p0.y())
            len1 = (v1.x() ** 2 + v1.y() ** 2) ** 0.5
            v2 = QPointF(p2.x() - p1.x(), p2.y() - p1.y())
            len2 = (v2.x() ** 2 + v2.y() ** 2) ** 0.5

            r = min(corner_r, len1 / 2, len2 / 2)
            if r < 1.0:
                path.lineTo(p1)
                continue

            u1 = QPointF(v1.x() / len1, v1.y() / len1)
            u2 = QPointF(v2.x() / len2, v2.y() / len2)

            start_arc = QPointF(p1.x() - u1.x() * r, p1.y() - u1.y() * r)
            end_arc = QPointF(p1.x() + u2.x() * r, p1.y() + u2.y() * r)

            path.lineTo(start_arc)
            path.quadTo(p1, end_arc)

        path.lineTo(pts[-1])
        return path

    def draw_path(self, start, end, from_dock=PortDock.BOTTOM, to_dock=PortDock.TOP):
        """ BrokenLinkDrawer.DrawPath — 完整的正交路由算法"""
        # 起点终点 X/Y 接近时直接画直线，不走折线路由
        if abs(start.x() - end.x()) < 2.0 or abs(start.y() - end.y()) < 2.0:
            path = QPainterPath()
            path.moveTo(start)
            path.lineTo(end)
            return path

        inner1 = changed_point(start, from_dock, self.inner_span)
        inner2 = changed_point(end, to_dock, self.inner_span)

        # 第一种交叉配置：先垂直后水平（连接 inner1.x 和 inner2.y）
        cross1 = QPointF(inner1.x(), inner2.y())
        # 第二种交叉配置：先水平后垂直（连接 inner2.x 和 inner1.y）
        cross2 = QPointF(inner2.x(), inner1.y())

        # 检查第一种配置是否有效（交叉点不在起点/内点1的延长线上，且不在终点/内点2的延长线上）
        is_cross1 = (not self._on_segment(inner1, cross1, start) and
                     not self._on_segment(inner2, cross1, end))
        # 检查第二种配置是否有效
        is_cross2 = (not self._on_segment(inner1, cross2, start) and
                     not self._on_segment(inner2, cross2, end))

        # 初始化点列表
        points: list[QPointF] = []

        # 情况1：只有第一种配置有效
        if is_cross1 and not is_cross2:
            # 添加起点
            points.append(start)
            # 如果交叉点不在起点到内点1的线段上，添加内点1
            if not self._on_segment(start, inner1, cross1):
                points.append(inner1)
            # 添加交叉点
            points.append(cross1)
            # 如果交叉点不在终点到内点2的线段上，添加内点2
            if not self._on_segment(end, inner2, cross1):
                points.append(inner2)
            # 添加终点
            points.append(end)

        # 情况2：只有第二种配置有效
        elif not is_cross1 and is_cross2:
            # 添加起点
            points.append(start)
            # 如果交叉点不在起点到内点1的线段上，添加内点1
            if not self._on_segment(start, inner1, cross2):
                points.append(inner1)
            # 添加交叉点
            points.append(cross2)
            # 如果交叉点不在终点到内点2的线段上，添加内点2
            if not self._on_segment(end, inner2, cross2):
                points.append(inner2)
            # 添加终点
            points.append(end)

        # 情况3：两种配置都有效
        elif is_cross1 and is_cross2:
            # 构建第一条路径（使用cross1）
            pts1 = [start]
            if not self._on_segment(start, inner1, cross1):
                pts1.append(inner1)
            pts1.append(cross1)
            if not self._on_segment(end, inner2, cross1):
                pts1.append(inner2)
            pts1.append(end)

            # 构建第二条路径（使用cross2）
            pts2 = [start]
            if not self._on_segment(start, inner1, cross2):
                pts2.append(inner1)
            pts2.append(cross2)
            if not self._on_segment(end, inner2, cross2):
                pts2.append(inner2)
            pts2.append(end)

            # 选择弯折数较少的路径
            if self._bend_count(pts1) > self._bend_count(pts2):
                points = pts2
            else:
                points = pts1

        else:
            # 情况4：两种交叉都无效 —— 回退到中线路由
            # 计算水平中线的Y坐标（内点1和内点2的Y坐标平均值）
            line_y = (inner1.y() + inner2.y()) / 2
            # 水平中线起点（内点1的X坐标，中线Y坐标）
            ly_start = QPointF(inner1.x(), line_y)
            # 水平中线终点（内点2的X坐标，中线Y坐标）
            ly_end = QPointF(inner2.x(), line_y)
            # 计算垂直中线的X坐标（内点1和内点2的X坐标平均值）
            line_x = (inner1.x() + inner2.x()) / 2
            # 垂直中线起点（中线X坐标，内点1的Y坐标）
            lx_start = QPointF(line_x, inner1.y())
            # 垂直中线终点（中线X坐标，内点2的Y坐标）
            lx_end = QPointF(line_x, inner2.y())

            # 检查水平中线路由是否有效
            is_linex = (not self._on_segment(inner1, ly_start, start) and
                        not self._on_segment(inner2, ly_end, end))

            if is_linex:
                # 使用水平中线路由
                # 将起点添加到点列表中
                points.append(start)
                # 判断起点到内点1的线段上是否包含水平中线起点（ly_start）
                if not self._on_segment(start, inner1, ly_start):
                    # 如果不包含，将内点1添加到点列表中（需要先走到内点1）
                    points.append(inner1)
                # 将水平中线起点添加到点列表中
                points.append(ly_start)
                # 将水平中线终点添加到点列表中
                points.append(ly_end)
                # 判断终点到内点2的线段上是否包含水平中线终点（ly_end）
                if not self._on_segment(end, inner2, ly_end):
                    # 如果不包含，将内点2添加到点列表中（需要从内点2走到终点）
                    points.append(inner2)
                # 将终点添加到点列表中
                points.append(end)
            else:
                # 使用垂直中线路由
                # 将起点添加到点列表中
                points.append(start)
                # 判断起点到内点1的线段上是否包含垂直中线起点（lx_start）
                if not self._on_segment(start, inner1, lx_start):
                    # 如果不包含，将内点1添加到点列表中（需要先走到内点1）
                    points.append(inner1)
                # 将垂直中线起点添加到点列表中
                points.append(lx_start)
                # 将垂直中线终点添加到点列表中
                points.append(lx_end)
                # 判断终点到内点2的线段上是否包含垂直中线终点（lx_end）
                if not self._on_segment(end, inner2, lx_end):
                    # 如果不包含，将内点2添加到点列表中（需要从内点2走到终点）
                    points.append(inner2)
                # 将终点添加到点列表中
                points.append(end)

        # 从点列表构建并返回路径
        return self._build_polyline(points)
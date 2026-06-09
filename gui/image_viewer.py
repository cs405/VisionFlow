"""可缩放图像查看器

提供：鼠标滚轮缩放、中键/右键拖拽平移、适应窗口、像素信息、
叠加层（ROI框、检测框、文本标签）、结构化叠加模型、选择高亮、缩放到矩形导航。
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                              QWidget,
                              QVBoxLayout, QLabel, QHBoxLayout, QStackedLayout)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QPropertyAnimation, QEasingCurve, QVariantAnimation
from PyQt5.QtGui import (QPixmap, QImage, QPen, QColor, QBrush, QPainter,
                           QWheelEvent, QMouseEvent, QFont)
from gui.theme import theme_manager, connect_theme


def numpy_to_qimage(array: np.ndarray) -> QImage:
    """将numpy数组（BGR/灰度）转换为QImage

    参数：
        array: numpy数组图像

    返回：
        QImage对象
    """
    # 如果数组为空，返回空QImage
    if array is None:
        return QImage()
    # 获取图像高度和宽度
    h, w = array.shape[:2]
    # 如果是灰度图（2维）
    if len(array.shape) == 2:
        return QImage(array.data, w, h, w, QImage.Format_Grayscale8)
    # 如果是3通道彩色图（BGR格式）
    elif array.shape[2] == 3:
        # BGR转RGB（浅拷贝）
        rgb = array[..., ::-1].copy()
        return QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
    # 如果是4通道图像（BGRA格式）
    elif array.shape[2] == 4:
        # BGRA转RGBA
        rgba = array[..., [2, 1, 0, 3]].copy()
        return QImage(rgba.data, w, h, w * 4, QImage.Format_RGBA8888)
    # 其他格式返回空QImage
    return QImage()


def numpy_to_pixmap(array: np.ndarray) -> QPixmap:
    """将numpy数组转换为QPixmap

    参数：
        array: numpy数组图像

    返回：
        QPixmap对象
    """
    # 先转换为QImage，再转换为QPixmap
    qimg = numpy_to_qimage(array)
    return QPixmap.fromImage(qimg)


# ── 叠加模型 ──────────────────────────────────────────────────────────

class OverlayType(Enum):
    """叠加项类型枚举"""
    RECT = "rect"          # 矩形
    CIRCLE = "circle"      # 圆形
    LINE = "line"          # 线段
    TEXT = "text"          # 文本
    ROI = "roi"            # 感兴趣区域
    DETECTION = "detection" # 检测框


@dataclass
class OverlayItem:
    """结构化叠加元数据，用于管理和命中测试"""
    uid: str                                    # 唯一标识符
    type: OverlayType                           # 叠加类型
    geometry: dict                              # 几何参数（根据类型不同：{x,y,w,h} 或 {cx,cy,r} 或 {x1,y1,x2,y2}）
    label: str = ""                             # 标签文本
    color: QColor = field(default_factory=lambda: QColor("#0078d4"))  # 颜色
    line_width: int = 2                         # 线宽
    score: float = 0.0                          # 置信度分数
    z_value: int = 10                           # Z序
    selected: bool = False                      # 是否选中
    highlighted: bool = False                   # 是否高亮
    graphics_items: list = field(default_factory=list)  # 对应的QGraphicsItem引用列表

    def to_rect(self) -> tuple[int, int, int, int] | None:
        """获取边界矩形 (x, y, w, h)

        返回：
            矩形元组，如果不是矩形类型则返回None
        """
        # 获取几何字典
        geo = self.geometry
        # 如果是矩形、ROI或检测框类型
        if self.type in (OverlayType.RECT, OverlayType.ROI, OverlayType.DETECTION):
            return (geo.get("x", 0), geo.get("y", 0),
                    geo.get("w", 0), geo.get("h", 0))
        return None


# ── 图像查看器 ───────────────────────────────────────────────────────────

class ImageViewer(QGraphicsView):
    """可缩放、可平移的图像查看器，具有结构化叠加层管理。

    功能：
      - 鼠标滚轮缩放（以光标为中心）
      - 中键/右键拖拽平移
      - 左键点击报告像素坐标
      - 适应窗口 / 1:1缩放
      - 带选择/高亮的结构化叠加模型
      - zoom_to_rect() 带动画导航
      - 取色模式和ROI拾取模式
    """

    # 信号定义
    pixel_clicked = pyqtSignal(int, int, object)  # x, y, 像素值
    mouse_moved = pyqtSignal(int, int)             # x, y（图像坐标）
    zoom_changed = pyqtSignal(float)                # 缩放因子
    color_picked = pyqtSignal(object)               # 字典：rgb/bgr/hsv/hex/x/y
    roi_picked = pyqtSignal(tuple)                  # (x, y, w, h)
    overlay_selected = pyqtSignal(str)              # 叠加项uid
    overlay_deselected = pyqtSignal()

    # 缩放范围常量
    MIN_ZOOM = 0.01      # 最小缩放比例
    MAX_ZOOM = 50.0      # 最大缩放比例
    ZOOM_FACTOR = 1.15   # 缩放因子

    def __init__(self, parent=None):
        """初始化图像查看器

        参数：
            parent: 父对象
        """
        # 调用父类QGraphicsView的构造函数
        super().__init__(parent)

        # 创建图形场景
        self._scene = QGraphicsScene(self)
        # 设置场景
        self.setScene(self._scene)

        # 主图像项
        self._pixmap_item = QGraphicsPixmapItem()
        # 添加到场景
        self._scene.addItem(self._pixmap_item)

        # 状态变量
        self._zoom = 1.0                         # 当前缩放比例
        self._pan_start: QPointF | None = None   # 平移起始点
        self._image: np.ndarray | None = None    # 当前图像数组
        self._fit_to_window = True               # 是否适应窗口
        self._color_pick_mode = False            # 取色模式标志
        self._roi_pick_mode = False              # ROI拾取模式标志
        self._roi_drag_start: QPointF | None = None  # ROI拖拽起始点
        self._roi_pick_item = None               # ROI拾取矩形项

        # 叠加模型
        self._overlays: dict[str, OverlayItem] = {}  # 叠加项字典
        self._selected_uid: str | None = None        # 选中的叠加项ID
        self._overlay_counter = 0                    # 叠加项计数器

        # 视图设置
        # 启用抗锯齿和平滑像素图变换
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        # 设置拖拽模式为无拖拽（手动控制）
        self.setDragMode(QGraphicsView.NoDrag)
        # 设置变换锚点为鼠标下方
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        # 设置调整大小锚点为鼠标下方
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        # 设置视口更新模式为全视口更新
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        # 禁用水平滚动条
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 禁用垂直滚动条
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 设置无边框
        self.setFrameShape(QGraphicsView.NoFrame)

        # 背景
        self._refresh_tile_brush()

    def _create_tile_brush(self, color1: QColor, color2: QColor, size: int) -> QBrush:
        """创建棋盘格画刷

        参数：
            color1: 第一种颜色
            color2: 第二种颜色
            size: 单元格大小

        返回：
            棋盘格画刷
        """
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import QSize
        # 创建2x2大小的像素图
        pixmap = QPixmap(size * 2, size * 2)
        # 用第一种颜色填充
        pixmap.fill(color1)
        # 创建绘图对象
        painter = QPainter(pixmap)
        # 绘制左上角单元格
        painter.fillRect(0, 0, size, size, color2)
        # 绘制右下角单元格
        painter.fillRect(size, size, size, size, color2)
        # 结束绘制
        painter.end()
        # 返回画刷
        return QBrush(pixmap)

    def _refresh_tile_brush(self):
        """从当前主题颜色重新应用棋盘格背景画刷"""
        # 设置背景画刷为棋盘格
        self.setBackgroundBrush(self._create_tile_brush(
            theme_manager.color('canvas_checker_base'),
            theme_manager.color('canvas_checker_alt'), 16))

        # 启用鼠标追踪
        self.setMouseTracking(True)

    # ── 图像加载 ─────────────────────────────────────────────────

    def set_image(self, image: np.ndarray | QPixmap | None):
        """设置显示的图像

        参数：
            image: numpy数组或QPixmap对象
        """
        # 清除所有叠加层
        self.clear_overlays()
        # 清除ROI矩形
        self.clear_roi_rect()

        # 如果图像为空
        if image is None:
            # 清空像素图
            self._pixmap_item.setPixmap(QPixmap())
            # 清空图像数组
            self._image = None
            # 设置场景矩形为空
            self._scene.setSceneRect(QRectF())
            return

        # 根据图像类型处理
        if isinstance(image, np.ndarray):
            # 保存图像数组
            self._image = image
            # 转换为QPixmap
            pixmap = numpy_to_pixmap(image)
        elif isinstance(image, QPixmap):
            # 保存像素图
            pixmap = image
            # 清空图像数组
            self._image = None
        else:
            return

        # 设置像素图
        self._pixmap_item.setPixmap(pixmap)
        # 设置场景矩形为像素图矩形
        self._scene.setSceneRect(QRectF(pixmap.rect()))

        # 如果需要适应窗口
        if self._fit_to_window:
            # 适应窗口
            self.fit_to_window()

    @property
    def image(self) -> np.ndarray | None:
        """获取当前图像数组"""
        return self._image

    # ── 缩放 ──────────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent):
        """滚轮事件处理

        参数：
            event: 滚轮事件对象
        """
        # 获取滚轮滚动量（正值向上，负值向下）
        delta = event.angleDelta().y()
        # 根据方向计算缩放因子
        factor = self.ZOOM_FACTOR if delta > 0 else 1.0 / self.ZOOM_FACTOR
        # 计算新的缩放比例
        new_zoom = self._zoom * factor
        # 检查是否在允许范围内
        if self.MIN_ZOOM <= new_zoom <= self.MAX_ZOOM:
            # 更新缩放比例
            self._zoom = new_zoom
            # 执行缩放
            self.scale(factor, factor)
            # 发出缩放变化信号
            self.zoom_changed.emit(self._zoom)
            # 标记不再适应窗口
            self._fit_to_window = False

    def fit_to_window(self):
        """适应窗口大小"""
        # 如果像素图为空，返回
        if self._pixmap_item.pixmap().isNull():
            return
        # 适应场景矩形，保持宽高比
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        # 获取当前缩放比例
        self._zoom = self.transform().m11()
        # 发出缩放变化信号
        self.zoom_changed.emit(self._zoom)
        # 标记为适应窗口状态
        self._fit_to_window = True

    def zoom_in(self):
        """放大"""
        # 计算新的缩放比例（不超过最大值）
        self._zoom = min(self._zoom * self.ZOOM_FACTOR, self.MAX_ZOOM)
        # 重置变换
        self.resetTransform()
        # 应用缩放
        self.scale(self._zoom, self._zoom)
        # 标记不再适应窗口
        self._fit_to_window = False

    def zoom_out(self):
        """缩小"""
        # 计算新的缩放比例（不小于最小值）
        self._zoom = max(self._zoom / self.ZOOM_FACTOR, self.MIN_ZOOM)
        # 重置变换
        self.resetTransform()
        # 应用缩放
        self.scale(self._zoom, self._zoom)
        # 标记不再适应窗口
        self._fit_to_window = False

    def zoom_to_100(self):
        """100%缩放"""
        # 设置缩放比例为1.0
        self._zoom = 1.0
        # 重置变换
        self.resetTransform()
        # 标记不再适应窗口
        self._fit_to_window = False

    def set_zoom(self, factor: float):
        """设置缩放比例

        参数：
            factor: 缩放因子
        """
        # 限制在允许范围内
        self._zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, factor))
        # 重置变换
        self.resetTransform()
        # 应用缩放
        self.scale(self._zoom, self._zoom)
        # 标记不再适应窗口
        self._fit_to_window = False

    @property
    def zoom_level(self) -> float:
        """获取当前缩放级别"""
        return self._zoom

    # ── zoom_to_rect ──────────────────────────────────────────────────

    def zoom_to_rect(self, rect: tuple[int, int, int, int],
                     padding: float = 0.1, animate: bool = True):
        """缩放并居中到指定区域

        参数：
            rect: (x, y, w, h) 图像坐标
            padding: 视口内边距比例
            animate: 是否使用动画
        """
        # 解包矩形参数
        x, y, w, h = rect
        # 如果尺寸无效，返回
        if w <= 0 or h <= 0:
            return

        # 计算内边距
        pw = w * padding
        ph = h * padding
        # 计算目标矩形
        target_rect = QRectF(x - pw, y - ph, w + 2 * pw, h + 2 * ph)

        # 停止现有动画
        if animate and hasattr(self, '_zoom_anim') and self._zoom_anim is not None:
            self._zoom_anim.stop()

        # 如果需要动画且目标矩形有效
        if animate and not target_rect.isEmpty():
            # 执行动画
            self._animate_to_rect(target_rect)
        else:
            # 直接适应目标矩形
            self.fitInView(target_rect, Qt.KeepAspectRatio)
            # 获取当前缩放比例
            self._zoom = self.transform().m11()
            # 标记不再适应窗口
            self._fit_to_window = False
            # 发出缩放变化信号
            self.zoom_changed.emit(self._zoom)

    def _animate_to_rect(self, target_rect: QRectF):
        """平滑动画导航到目标矩形

        参数：
            target_rect: 目标矩形
        """
        # 获取当前视口矩形
        start_rect = self.viewport_rect_in_scene()
        # 如果当前矩形无效
        if start_rect.isEmpty():
            # 直接适应
            self.fitInView(target_rect, Qt.KeepAspectRatio)
            # 获取缩放比例
            self._zoom = self.transform().m11()
            # 标记不再适应窗口
            self._fit_to_window = False
            # 发出缩放变化信号
            self.zoom_changed.emit(self._zoom)
            return

        # 创建动画对象
        self._zoom_anim = QVariantAnimation(self)
        # 设置动画时长250毫秒
        self._zoom_anim.setDuration(250)
        # 设置缓动曲线为三次缓出
        self._zoom_anim.setEasingCurve(QEasingCurve.OutCubic)
        # 设置起始值
        self._zoom_anim.setStartValue(start_rect)
        # 设置结束值
        self._zoom_anim.setEndValue(target_rect)

        # 定义步进函数
        def _step(rect):
            # 适应当前矩形
            self.fitInView(rect, Qt.KeepAspectRatio)
            # 获取缩放比例
            self._zoom = self.transform().m11()
            # 标记不再适应窗口
            self._fit_to_window = False

        # 连接值变化信号
        self._zoom_anim.valueChanged.connect(_step)
        # 连接完成信号
        self._zoom_anim.finished.connect(lambda: (
            self.zoom_changed.emit(self._zoom),   # 发出缩放变化信号
            setattr(self, '_zoom_anim', None)      # 清空动画引用
        ))
        # 启动动画
        self._zoom_anim.start()

    def viewport_rect_in_scene(self) -> QRectF:
        """获取当前视口在场景中的矩形"""
        # 将视口矩形映射到场景坐标，返回边界矩形
        return self.mapToScene(self.viewport().rect()).boundingRect()

    # ── 平移 ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件

        参数：
            event: 鼠标事件对象
        """
        # 如果是左键且处于ROI拾取模式且像素图不为空
        if event.button() == Qt.LeftButton and self._roi_pick_mode and not self._pixmap_item.pixmap().isNull():
            # 记录拖拽起点
            self._roi_drag_start = self.mapToScene(event.pos())
            # 如果ROI拾取项不存在
            if self._roi_pick_item is None:
                # 创建虚线画笔
                pen = QPen(QColor(0, 120, 212), 2)
                pen.setStyle(Qt.DashLine)
                # 添加矩形项
                self._roi_pick_item = self._scene.addRect(QRectF(), pen)
                # 设置Z序
                self._roi_pick_item.setZValue(50)
            # 设置矩形为起点到起点的点矩形
            self._roi_pick_item.setRect(QRectF(self._roi_drag_start, self._roi_drag_start))
            # 接受事件
            event.accept()
            return
        # 如果是左键且处于取色模式
        if event.button() == Qt.LeftButton and self._color_pick_mode:
            # 获取像素位置
            self._emit_pixel_pos(event.pos())
            # 获取颜色信息
            self._emit_color_info(event.pos())
            # 接受事件
            event.accept()
            return
        # 如果是中键或右键
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            # 记录平移起始点
            self._pan_start = event.pos()
            # 设置光标为握紧手形状
            self.setCursor(Qt.ClosedHandCursor)
        # 如果是左键
        elif event.button() == Qt.LeftButton:
            # 获取像素位置
            self._emit_pixel_pos(event.pos())
            # 检查叠加层命中测试
            self._hit_test_overlays(event.pos())
        # 调用父类的mousePressEvent
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件

        参数：
            event: 鼠标事件对象
        """
        # 如果正在拖拽ROI且处于ROI拾取模式
        if self._roi_drag_start is not None and self._roi_pick_mode:
            # 获取当前鼠标位置
            current_pos = self.mapToScene(event.pos())
            # 计算归一化矩形
            rect = QRectF(self._roi_drag_start, current_pos).normalized()
            # 如果ROI拾取项存在
            if self._roi_pick_item is not None:
                # 设置矩形
                self._roi_pick_item.setRect(rect)
            # 接受事件
            event.accept()
            return
        # 如果正在平移
        if self._pan_start is not None:
            # 计算偏移量
            delta = event.pos() - self._pan_start
            # 更新起始点
            self._pan_start = event.pos()
            # 移动水平滚动条
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            # 移动垂直滚动条
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        else:
            # 获取鼠标在场景中的位置
            scene_pos = self.mapToScene(event.pos())
            # 获取整数坐标
            x, y = int(scene_pos.x()), int(scene_pos.y())
            # 检查是否在图像范围内
            if 0 <= x < self._scene.width() and 0 <= y < self._scene.height():
                # 发出鼠标移动信号
                self.mouse_moved.emit(x, y)
        # 调用父类的mouseMoveEvent
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件

        参数：
            event: 鼠标事件对象
        """
        # 如果是左键且正在拖拽ROI且处于ROI拾取模式
        if event.button() == Qt.LeftButton and self._roi_drag_start is not None and self._roi_pick_mode:
            # 获取当前鼠标位置
            current_pos = self.mapToScene(event.pos())
            # 计算归一化矩形
            rect = QRectF(self._roi_drag_start, current_pos).normalized()
            # 清空拖拽起点
            self._roi_drag_start = None
            # 将矩形转换为元组
            roi_rect = self._scene_rect_to_tuple(rect)
            # 如果ROI拾取项存在
            if self._roi_pick_item is not None:
                # 从场景移除
                self._scene.removeItem(self._roi_pick_item)
                # 清空引用
                self._roi_pick_item = None
            # 如果矩形有效
            if roi_rect[2] > 0 and roi_rect[3] > 0:
                # 发出ROI拾取信号
                self.roi_picked.emit(roi_rect)
            # 接受事件
            event.accept()
            return
        # 如果是中键或右键
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            # 清空平移起始点
            self._pan_start = None
            # 恢复光标为箭头
            self.setCursor(Qt.ArrowCursor)
        # 调用父类的mouseReleaseEvent
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """鼠标双击事件

        参数：
            event: 鼠标事件对象
        """
        # 如果是左键
        if event.button() == Qt.LeftButton:
            # 适应窗口
            self.fit_to_window()
        # 调用父类的mouseDoubleClickEvent
        super().mouseDoubleClickEvent(event)

    def _emit_pixel_pos(self, pos: QPointF):
        """发出像素位置信号

        参数：
            pos: 视口坐标
        """
        # 将视口坐标转换为场景坐标
        scene_pos = self.mapToScene(pos)
        # 获取整数坐标
        x, y = int(scene_pos.x()), int(scene_pos.y())
        # 检查是否在图像范围内
        if self._image is not None and 0 <= y < self._image.shape[0] and 0 <= x < self._image.shape[1]:
            # 获取像素值
            pixel_val = self._image[y, x].tolist()
            # 发出像素点击信号
            self.pixel_clicked.emit(x, y, pixel_val)

    def _emit_color_info(self, pos: QPointF):
        """发出颜色信息信号

        参数：
            pos: 视口坐标
        """
        # 转换为场景坐标
        scene_pos = self.mapToScene(pos)
        # 获取整数坐标
        x, y = int(scene_pos.x()), int(scene_pos.y())
        # 调用取色方法
        self.pick_color_at(x, y)

    def pick_color_at(self, x: int, y: int) -> dict | None:
        """直接从图像坐标取色

        参数：
            x: X坐标
            y: Y坐标

        返回：
            颜色信息字典
        """
        # 检查图像是否存在且坐标有效
        if self._image is None or not (0 <= y < self._image.shape[0] and 0 <= x < self._image.shape[1]):
            return
        # 获取像素值
        pixel = self._image[y, x]
        # 如果是灰度图
        if np.isscalar(pixel):
            gray = int(pixel)
            bgr = (gray, gray, gray)
        else:
            # 转换为列表
            values = [int(v) for v in pixel.tolist()]
            if len(values) >= 3:
                bgr = tuple(values[:3])
            elif len(values) == 1:
                bgr = (values[0], values[0], values[0])
            else:
                return
        # 转换为HSV
        hsv = cv2.cvtColor(np.array([[bgr]], dtype=np.uint8), cv2.COLOR_BGR2HSV)[0, 0].tolist()
        # 转换为RGB
        rgb = (bgr[2], bgr[1], bgr[0])
        # 构建返回数据
        payload = {
            "x": x, "y": y,                                   # 坐标
            "bgr": bgr,                                       # BGR值
            "rgb": rgb,                                       # RGB值
            "hsv": tuple(int(v) for v in hsv),                # HSV值
            "hex": "#{:02X}{:02X}{:02X}".format(*rgb),        # HEX值
        }
        # 发出颜色拾取信号
        self.color_picked.emit(payload)
        return payload

    def _scene_rect_to_tuple(self, rect: QRectF) -> tuple[int, int, int, int]:
        """将场景矩形转换为整数元组

        参数：
            rect: 场景矩形

        返回：
            (x, y, w, h) 元组
        """
        # 如果没有图像
        if self._image is None:
            return (int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))
        # 获取图像尺寸
        max_w = self._image.shape[1]
        max_h = self._image.shape[0]
        # 限制范围
        x1 = max(0, min(int(round(rect.left())), max_w))
        y1 = max(0, min(int(round(rect.top())), max_h))
        x2 = max(0, min(int(round(rect.right())), max_w))
        y2 = max(0, min(int(round(rect.bottom())), max_h))
        return (x1, y1, max(0, x2 - x1), max(0, y2 - y1))

    # ── 取色/ROI拾取模式 ───────────────────────────────────────────

    def set_color_pick_mode(self, enabled: bool):
        """设置取色模式

        参数：
            enabled: 是否启用
        """
        self._color_pick_mode = enabled
        # 设置光标样式
        self.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)

    def set_roi_pick_mode(self, enabled: bool):
        """设置ROI拾取模式

        参数：
            enabled: 是否启用
        """
        self._roi_pick_mode = enabled
        if not enabled:
            # 清空拖拽起点
            self._roi_drag_start = None
            # 移除ROI拾取项
            if self._roi_pick_item is not None:
                self._scene.removeItem(self._roi_pick_item)
                self._roi_pick_item = None
        # 设置光标样式
        self.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)

    # ── ROI叠加层 ───────────────────────────────────────────────────

    def clear_roi_rect(self):
        """移除固定位置的ROI叠加层"""
        # 遍历ROI叠加项列表
        for item in getattr(self, '_roi_overlay_items', []):
            # 从场景移除
            self._scene.removeItem(item)
        # 清空列表
        self._roi_overlay_items = []

    def set_roi_rect(self, rect: tuple[int, int, int, int] | None,
                     label: str = "ROI",
                     color: QColor = QColor(0, 120, 212)):
        """设置ROI矩形

        参数：
            rect: 矩形 (x, y, w, h)
            label: 标签文本
            color: 颜色
        """
        # 清除现有ROI
        self.clear_roi_rect()
        # 如果不存在属性，初始化
        if not hasattr(self, '_roi_overlay_items'):
            self._roi_overlay_items = []
        # 如果矩形为空，返回
        if rect is None:
            return
        # 解包矩形
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return

        # 创建画笔
        pen = QPen(color, 2)
        pen.setStyle(Qt.DashLine)
        # 添加矩形项
        item = self._scene.addRect(x, y, w, h, pen)
        item.setZValue(40)
        # 添加到列表
        self._roi_overlay_items.append(item)

        # 如果有标签
        if label:
            # 添加文本项
            text = self._scene.addText(label, QFont("Segoe UI", 10))
            text.setPos(x, max(0, y - 20))
            text.setDefaultTextColor(color)
            text.setZValue(41)
            self._roi_overlay_items.append(text)

    # ── 结构化叠加模型 ──────────────────────────────────────

    def add_rect_overlay(self, rect: tuple, label: str = "",
                         color: QColor = QColor(0, 120, 212),
                         score: float = 0.0,
                         overlay_type: OverlayType = OverlayType.RECT) -> str:
        """添加矩形叠加层，带结构化追踪

        参数：
            rect: 矩形 (x, y, w, h)
            label: 标签
            color: 颜色
            score: 置信度分数
            overlay_type: 叠加类型

        返回：
            唯一叠加项ID
        """
        # 计数器加1
        self._overlay_counter += 1
        # 生成唯一ID
        uid = f"overlay_{self._overlay_counter}"
        # 解包矩形
        x, y, w, h = rect

        # 创建画笔
        pen = QPen(color, 2)
        # 根据类型设置画笔样式
        pen.setStyle(Qt.DashLine if overlay_type == OverlayType.ROI else Qt.SolidLine)
        # 添加矩形项
        rect_item = self._scene.addRect(x, y, w, h, pen)
        rect_item.setZValue(10)
        # 图形项列表
        gfx_items = [rect_item]

        # 如果有标签或分数
        if label or score > 0:
            # 构建文本
            text_str = f"{label} {score:.2f}" if score > 0 else label
            # 添加文本项
            text_item = self._scene.addText(text_str, QFont("Segoe UI", 9))
            text_item.setPos(x, y - 18)
            text_item.setDefaultTextColor(color)
            text_item.setZValue(11)
            gfx_items.append(text_item)

        # 创建叠加项
        overlay = OverlayItem(
            uid=uid,                              # 唯一ID
            type=overlay_type,                   # 类型
            geometry={"x": x, "y": y, "w": w, "h": h},  # 几何参数
            label=label,                         # 标签
            color=color,                         # 颜色
            score=score,                         # 分数
            graphics_items=gfx_items,            # 图形项列表
        )
        # 保存到字典
        self._overlays[uid] = overlay
        # 返回ID
        return uid

    def add_circle_overlay(self, center: tuple, radius: float,
                            label: str = "",
                            color: QColor = QColor(76, 175, 80)) -> str:
        """添加圆形叠加层，带结构化追踪

        参数：
            center: 圆心 (cx, cy)
            radius: 半径
            label: 标签
            color: 颜色

        返回：
            唯一叠加项ID
        """
        # 计数器加1
        self._overlay_counter += 1
        # 生成唯一ID
        uid = f"overlay_{self._overlay_counter}"
        # 解包圆心
        cx, cy = center

        # 创建画笔
        pen = QPen(color, 2)
        # 添加椭圆项（圆形）
        item = self._scene.addEllipse(cx - radius, cy - radius,
                                       radius * 2, radius * 2, pen)
        item.setZValue(10)
        # 图形项列表
        gfx_items = [item]

        # 如果有标签
        if label:
            # 添加文本项
            text_item = self._scene.addText(label, QFont("Segoe UI", 9))
            text_item.setPos(cx - radius, cy - radius - 18)
            text_item.setDefaultTextColor(color)
            text_item.setZValue(11)
            gfx_items.append(text_item)

        # 创建叠加项
        overlay = OverlayItem(
            uid=uid,                                    # 唯一ID
            type=OverlayType.CIRCLE,                   # 类型
            geometry={"cx": cx, "cy": cy, "r": radius},  # 几何参数
            label=label,                               # 标签
            color=color,                               # 颜色
            graphics_items=gfx_items,                  # 图形项列表
        )
        # 保存到字典
        self._overlays[uid] = overlay
        # 返回ID
        return uid

    def add_line_overlay(self, x1: float, y1: float, x2: float, y2: float,
                          label: str = "",
                          color: QColor = QColor(255, 152, 0)) -> str:
        """添加线段叠加层，带结构化追踪

        参数：
            x1, y1: 起点坐标
            x2, y2: 终点坐标
            label: 标签
            color: 颜色

        返回：
            唯一叠加项ID
        """
        # 计数器加1
        self._overlay_counter += 1
        # 生成唯一ID
        uid = f"overlay_{self._overlay_counter}"
        # 创建画笔
        pen = QPen(color, 1)
        # 添加线段项
        item = self._scene.addLine(x1, y1, x2, y2, pen)
        item.setZValue(10)
        # 图形项列表
        gfx_items = [item]

        # 如果有标签
        if label:
            # 添加文本项
            text_item = self._scene.addText(label, QFont("Segoe UI", 9))
            text_item.setPos(x1, y1 - 18)
            text_item.setDefaultTextColor(color)
            text_item.setZValue(11)
            gfx_items.append(text_item)

        # 创建叠加项
        overlay = OverlayItem(
            uid=uid,                                          # 唯一ID
            type=OverlayType.LINE,                           # 类型
            geometry={"x1": x1, "y1": y1, "x2": x2, "y2": y2},  # 几何参数
            label=label,                                     # 标签
            color=color,                                     # 颜色
            graphics_items=gfx_items,                        # 图形项列表
        )
        # 保存到字典
        self._overlays[uid] = overlay
        # 返回ID
        return uid

    def remove_overlay(self, uid: str):
        """根据ID移除单个叠加层

        参数：
            uid: 叠加项ID
        """
        # 弹出叠加项
        overlay = self._overlays.pop(uid, None)
        # 如果存在
        if overlay:
            # 移除所有图形项
            for item in overlay.graphics_items:
                self._scene.removeItem(item)
            # 如果选中的是当前项，清除选中状态
            if self._selected_uid == uid:
                self._clear_selection()

    def clear_overlays(self):
        """移除所有结构化叠加层"""
        # 遍历所有叠加项
        for overlay in list(self._overlays.values()):
            # 移除图形项
            for item in overlay.graphics_items:
                self._scene.removeItem(item)
        # 清空字典
        self._overlays.clear()
        # 清除选中状态
        self._clear_selection()

    # ── 选择与高亮 ─────────────────────────────────────────

    def select_overlay(self, uid: str):
        """选择叠加层并应用视觉高亮

        参数：
            uid: 叠加项ID
        """
        # 如果已经是选中的，返回
        if uid == self._selected_uid:
            return
        # 清除当前选中
        self._clear_selection()
        # 获取叠加项
        overlay = self._overlays.get(uid)
        if overlay is None:
            return
        # 标记为选中
        overlay.selected = True
        # 保存选中ID
        self._selected_uid = uid

        # 视觉：用高亮颜色重绘
        highlight_color = QColor("#FFD700")  # 金色
        # 只处理主要图形项（第一个）
        for item in overlay.graphics_items[:1]:
            # 获取画笔
            pen = item.pen()
            # 设置高亮颜色
            pen.setColor(highlight_color)
            # 设置线宽
            pen.setWidth(3)
            # 应用画笔
            item.setPen(pen)

        # 发出选中信号
        self.overlay_selected.emit(uid)

    def deselect_overlay(self):
        """取消当前选中"""
        self._clear_selection()
        self.overlay_deselected.emit()

    def _clear_selection(self):
        """清除选中状态"""
        # 如果有选中的ID且存在
        if self._selected_uid and self._selected_uid in self._overlays:
            # 获取叠加项
            overlay = self._overlays[self._selected_uid]
            # 标记未选中
            overlay.selected = False
            # 恢复原始颜色
            for item in overlay.graphics_items[:1]:
                pen = item.pen()
                pen.setColor(overlay.color)
                pen.setWidth(overlay.line_width)
                item.setPen(pen)
        # 清空选中ID
        self._selected_uid = None

    def highlight_overlay(self, uid: str, highlight_color: QColor = QColor("#FFD700"),
                          duration_ms: int = 2000):
        """临时高亮叠加层（用于结果面板联动）

        参数：
            uid: 叠加项ID
            highlight_color: 高亮颜色
            duration_ms: 高亮持续时间（毫秒）
        """
        # 获取叠加项
        overlay = self._overlays.get(uid)
        if overlay is None:
            return

        # 缩放到该区域
        rect = overlay.to_rect()
        if rect:
            self.zoom_to_rect(rect, padding=0.2, animate=True)

        # 高亮处理
        for item in overlay.graphics_items[:1]:
            pen = item.pen()
            pen.setColor(highlight_color)
            pen.setWidth(4)
            item.setPen(pen)

        # 延迟恢复
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(duration_ms, lambda: self._restore_highlight(uid))

    def _restore_highlight(self, uid: str):
        """恢复高亮

        参数：
            uid: 叠加项ID
        """
        # 获取叠加项
        overlay = self._overlays.get(uid)
        # 如果存在且未选中
        if overlay and not overlay.selected:
            for item in overlay.graphics_items[:1]:
                pen = item.pen()
                pen.setColor(overlay.color)
                pen.setWidth(overlay.line_width)
                item.setPen(pen)

    def _hit_test_overlays(self, view_pos: QPointF):
        """检查点击是否命中任何叠加层并选中

        参数：
            view_pos: 视口坐标
        """
        # 转换为场景坐标
        scene_pos = self.mapToScene(view_pos)
        x, y = scene_pos.x(), scene_pos.y()

        # 按添加顺序逆序遍历（后添加的先命中）
        for uid, overlay in reversed(list(self._overlays.items())):
            # 获取几何参数
            geo = overlay.geometry
            # 如果是矩形、ROI或检测框类型
            if overlay.type in (OverlayType.RECT, OverlayType.ROI, OverlayType.DETECTION):
                gx, gy, gw, gh = geo.get("x", 0), geo.get("y", 0), geo.get("w", 0), geo.get("h", 0)
                # 检查点是否在矩形内
                if gx <= x <= gx + gw and gy <= y <= gy + gh:
                    self.select_overlay(uid)
                    return
            # 如果是圆形类型
            elif overlay.type == OverlayType.CIRCLE:
                cx, cy, r = geo.get("cx", 0), geo.get("cy", 0), geo.get("r", 0)
                # 检查点是否在圆形内
                if (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2:
                    self.select_overlay(uid)
                    return

        # 没有命中任何叠加层
        self.deselect_overlay()

    # ── 兼容性便捷方法 ────────────────────────────────────

    def add_roi_overlay(self, rect: tuple, label: str = "",
                         color: QColor = QColor(0, 120, 212)):
        """兼容性方法 - 添加ROI矩形叠加层

        参数：
            rect: 矩形 (x, y, w, h)
            label: 标签
            color: 颜色

        返回：
            叠加项ID
        """
        return self.add_rect_overlay(rect, label, color, overlay_type=OverlayType.ROI)

    def add_detection_overlay(self, rect: tuple, label: str = "",
                               color: QColor = QColor(76, 175, 80),
                               score: float = 0.0):
        """兼容性方法 - 添加检测框叠加层

        参数：
            rect: 矩形 (x, y, w, h)
            label: 标签
            color: 颜色
            score: 置信度分数

        返回：
            叠加项ID
        """
        return self.add_rect_overlay(rect, label, color, score=score,
                                     overlay_type=OverlayType.DETECTION)

    def get_overlay(self, uid: str) -> OverlayItem | None:
        """根据ID获取叠加项元数据

        参数：
            uid: 叠加项ID

        返回：
            叠加项对象或None
        """
        return self._overlays.get(uid)

    def get_all_overlays(self) -> dict[str, OverlayItem]:
        """获取所有叠加项

        返回：
            叠加项字典
        """
        return dict(self._overlays)

    # ── 视频帧支持 ──────────────────────────────────────────

    def show_video_frame(self, frame: np.ndarray, frame_index: int = 0,
                          total_frames: int = 0, fps: float = 0.0):
        """显示视频帧，带叠加指示器

        参数：
            frame: numpy数组（BGR格式）
            frame_index: 当前帧号（0-based）
            total_frames: 视频总帧数
            fps: 帧率
        """
        # 设置图像
        self.set_image(frame)
        # 如果有总帧数信息
        if total_frames > 0:
            # 构建信息文本
            info = f"视频帧 {frame_index + 1}/{total_frames}"
            if fps > 0:
                info += f" @ {fps:.1f} FPS"
            # 显示帧叠加信息
            self._show_frame_overlay(info)

    def _show_frame_overlay(self, text: str):
        """在左上角显示半透明帧信息叠加层

        参数：
            text: 显示文本
        """
        # 清除现有帧叠加层
        self._clear_frame_overlay()
        # 添加背景矩形
        overlay = self._scene.addRect(0, 0, 300, 28, QPen(Qt.NoPen),
                                       QBrush(QColor(0, 0, 0, 140)))
        overlay.setZValue(100)
        self._frame_overlay_items = [overlay]
        # 添加文本
        txt = self._scene.addText(text, QFont("Segoe UI", 10))
        txt.setDefaultTextColor(QColor("#00ff00"))
        txt.setPos(6, 4)
        txt.setZValue(101)
        self._frame_overlay_items.append(txt)

    def _clear_frame_overlay(self):
        """清除帧叠加层"""
        # 遍历帧叠加层项列表
        for item in getattr(self, '_frame_overlay_items', []):
            self._scene.removeItem(item)
        # 清空列表
        self._frame_overlay_items = []

    def clear_video_frame(self):
        """清除视频帧叠加层"""
        self._clear_frame_overlay()

    # ── 调整大小 ────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        """调整大小事件

        参数：
            event: 大小改变事件对象
        """
        # 调用父类的resizeEvent
        super().resizeEvent(event)
        # 如果需要适应窗口且像素图不为空
        if self._fit_to_window and not self._pixmap_item.pixmap().isNull():
            # 适应窗口
            self.fit_to_window()


# ── 图像查看器面板 ─────────────────────────────────────────────────────

class ImageViewerPanel(QWidget):
    """带信息栏的ImageViewer面板封装"""

    def __init__(self, parent=None):
        """初始化图像查看器面板

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 设置UI
        self._setup_ui()

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

        # 创建图像查看器
        self.viewer = ImageViewer()

        # 创建查看器宿主
        viewer_host = QWidget()
        # 创建堆叠布局
        viewer_stack = QStackedLayout(viewer_host)
        # 设置边距为0
        viewer_stack.setContentsMargins(0, 0, 0, 0)
        # 设置堆叠模式为全部叠加
        viewer_stack.setStackingMode(QStackedLayout.StackAll)
        # 添加查看器
        viewer_stack.addWidget(self.viewer)

        # 创建叠加层
        overlay_layer = QWidget()
        # 设置鼠标穿透
        overlay_layer.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # 设置透明背景
        overlay_layer.setStyleSheet("background: transparent;")
        # 创建垂直布局
        overlay_layout = QVBoxLayout(overlay_layer)
        # 设置边距
        overlay_layout.setContentsMargins(8, 8, 8, 8)
        # 设置间距
        overlay_layout.setSpacing(6)

        # 顶部行
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        # 结果徽章
        self._result_badge = QLabel("无结果")
        self._result_badge.setStyleSheet(
            "QLabel {"
            "background: rgba(37, 37, 38, 0.92); color: #dcdcdc;"
            "border: 1px solid #3f3f46; border-radius: 4px;"
            "padding: 6px 12px; font-size: 12px; font-weight: 600;"
            "}"
        )
        # 添加到顶部行，左对齐顶部
        top_row.addWidget(self._result_badge, 0, Qt.AlignLeft | Qt.AlignTop)

        # 添加弹性空间
        top_row.addStretch(1)

        # 来源提示
        self._source_hint = QLabel("")
        self._source_hint.setStyleSheet(
            "QLabel {"
            "background: rgba(0, 0, 0, 0.45); color: #dcdcdc;"
            "border-radius: 4px; padding: 4px 8px; font-size: 11px;"
            "}"
        )
        self._source_hint.hide()
        # 添加到顶部行，右对齐顶部
        top_row.addWidget(self._source_hint, 0, Qt.AlignRight | Qt.AlignTop)
        # 添加顶部行到布局
        overlay_layout.addLayout(top_row)

        # 添加弹性空间
        overlay_layout.addStretch(1)

        # 消息横幅
        self._message_banner = QLabel("")
        self._message_banner.setWordWrap(True)
        self._message_banner.setStyleSheet(
            "QLabel {"
            "background: rgba(0, 0, 0, 0.42); color: #dcdcdc;"
            "border-radius: 4px; padding: 6px 10px; font-size: 11px;"
            "}"
        )
        self._message_banner.hide()
        # 添加到布局，左下对齐
        overlay_layout.addWidget(self._message_banner, 0, Qt.AlignLeft | Qt.AlignBottom)

        # 文件信息条
        self._file_info_strip = QLabel("")
        self._file_info_strip.setWordWrap(False)
        self._file_info_strip.setStyleSheet(
            "QLabel {"
            "background: rgba(0, 0, 0, 0.58); color: #d0d0d0;"
            "padding: 7px 10px; font-size: 11px;"
            "border-radius: 2px;"
            "}"
        )
        self._file_info_strip.hide()
        # 添加到布局，底部对齐
        overlay_layout.addWidget(self._file_info_strip, 0, Qt.AlignBottom)

        # 添加叠加层
        viewer_stack.addWidget(overlay_layer)
        # 添加查看器宿主到主布局，拉伸因子为1
        layout.addWidget(viewer_host, 1)

        # 信息栏
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(8, 2, 8, 2)

        # 位置标签
        self._pos_label = QLabel("位置: -")
        self._pos_label.setStyleSheet("font-size: 11px; color: #999;")
        info_layout.addWidget(self._pos_label)

        # 弹性空间
        info_layout.addStretch()

        # 尺寸标签
        self._size_label = QLabel("尺寸: -")
        self._size_label.setStyleSheet(f"font-size: 11px; color: {theme_manager.color('text_secondary').name()};")
        info_layout.addWidget(self._size_label)

        # 缩放标签
        self._zoom_label = QLabel("缩放: 100%")
        self._zoom_label.setStyleSheet(f"font-size: 11px; color: {theme_manager.color('text_secondary').name()};")
        info_layout.addWidget(self._zoom_label)

        # 创建信息控件
        self._info_widget = QWidget()
        self._info_widget.setLayout(info_layout)
        # 添加到主布局
        layout.addWidget(self._info_widget)

        # 连接信号
        self.viewer.mouse_moved.connect(self._on_mouse_moved)
        self.viewer.zoom_changed.connect(self._on_zoom_changed)
        self.viewer.pixel_clicked.connect(self._on_pixel_clicked)

        # 连接主题变化
        connect_theme(self._refresh_qss)

    def _refresh_qss(self):
        """主题变化时重新应用图像查看器QSS和棋盘格画刷"""
        # 获取主题管理器
        tm = theme_manager
        # 设置信息控件样式
        self._info_widget.setStyleSheet(
            f"background: {tm.color('bg_surface').name()}; border-top: 1px solid {tm.color('border').name()};"
        )
        # 设置位置标签样式
        self._pos_label.setStyleSheet(f"font-size: 11px; color: {tm.color('text_secondary').name()};")
        # 设置尺寸标签样式
        self._size_label.setStyleSheet(f"font-size: 11px; color: {tm.color('text_secondary').name()};")
        # 设置缩放标签样式
        self._zoom_label.setStyleSheet(f"font-size: 11px; color: {tm.color('text_secondary').name()};")
        # 刷新查看器的棋盘格画刷
        self.viewer._refresh_tile_brush()
        # 更新视口
        self.viewer.viewport().update()

    def set_image(self, image: np.ndarray | None):
        """设置图像

        参数：
            image: numpy数组图像
        """
        self.viewer.set_image(image)
        # 如果有图像
        if image is not None:
            # 获取图像尺寸
            h, w = image.shape[:2]
            # 更新尺寸标签
            self._size_label.setText(f"尺寸: {w} x {h}")
        else:
            # 清空尺寸标签
            self._size_label.setText("尺寸: -")

    def set_result_badge(self, text: str, accent: str | None = None):
        """设置结果徽章

        参数：
            text: 徽章文本
            accent: 强调色
        """
        # 去除首尾空格
        text = (text or "无结果").strip()
        # 设置文本
        self._result_badge.setText(text)
        # 边框颜色
        border = accent or "#3f3f46"
        # 设置样式
        self._result_badge.setStyleSheet(
            "QLabel {"
            "background: rgba(37, 37, 38, 0.92); color: #dcdcdc;"
            f"border: 1px solid {border}; border-radius: 4px;"
            "padding: 6px 12px; font-size: 12px; font-weight: 600;"
            "}"
        )

    def set_source_hint(self, text: str | None):
        """设置来源提示

        参数：
            text: 提示文本
        """
        # 去除首尾空格
        text = (text or "").strip()
        # 根据是否有文本设置可见性
        self._source_hint.setVisible(bool(text))
        # 设置文本
        self._source_hint.setText(text)

    def set_message_banner(self, text: str | None):
        """设置消息横幅

        参数：
            text: 消息文本
        """
        # 去除首尾空格
        text = (text or "").strip()
        # 根据是否有文本设置可见性
        self._message_banner.setVisible(bool(text))
        # 设置文本
        self._message_banner.setText(text)

    def set_file_info(self, text: str | None):
        """设置文件信息

        参数：
            text: 文件信息文本
        """
        # 去除首尾空格
        text = (text or "").strip()
        # 根据是否有文本设置可见性
        self._file_info_strip.setVisible(bool(text))
        # 设置文本
        self._file_info_strip.setText(text)

    def set_image_info(self, file_path: str | None, pixel_w: int = 0, pixel_h: int = 0):
        """设置底部信息条，包含完整的文件元数据

        格式：文件名.ext | 1920×1080 | 1.2 MB | 2024-01-15 14:30:00

        参数：
            file_path: 文件路径
            pixel_w: 像素宽度
            pixel_h: 像素高度
        """
        # 如果没有文件路径
        if not file_path:
            # 隐藏文件信息条
            self._file_info_strip.setVisible(False)
            return
        import os
        from datetime import datetime
        # 信息部分列表
        parts = [os.path.basename(file_path)]  # 文件名
        # 添加尺寸信息
        if pixel_w > 0 and pixel_h > 0:
            parts.append(f"{pixel_w}×{pixel_h}")
        try:
            # 获取文件大小
            size = os.path.getsize(file_path)
            if size < 1024 * 1024:
                parts.append(f"{size / 1024:.1f} KB")
            else:
                parts.append(f"{size / 1024 / 1024:.2f} MB")
        except OSError:
            pass
        try:
            # 获取修改时间
            mtime = os.path.getmtime(file_path)
            parts.append(datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"))
        except OSError:
            pass
        # 设置文本
        self._file_info_strip.setText("  |  ".join(parts))
        # 设置工具提示
        self._file_info_strip.setToolTip(file_path)
        # 显示文件信息条
        self._file_info_strip.setVisible(True)

    def clear_context_info(self):
        """清除上下文信息"""
        self.set_result_badge("无结果")
        self.set_source_hint("")
        self.set_message_banner("")
        self._file_info_strip.setVisible(False)

    def set_roi_rect(self, rect: tuple[int, int, int, int] | None, label: str = "ROI"):
        """设置ROI矩形

        参数：
            rect: 矩形 (x, y, w, h)
            label: 标签
        """
        self.viewer.set_roi_rect(rect, label=label)

    def clear_roi_rect(self):
        """清除ROI矩形"""
        self.viewer.clear_roi_rect()

    def _on_mouse_moved(self, x: int, y: int):
        """鼠标移动回调

        参数：
            x: X坐标
            y: Y坐标
        """
        self._pos_label.setText(f"位置: ({x}, {y})")

    def _on_zoom_changed(self, zoom: float):
        """缩放变化回调

        参数：
            zoom: 缩放比例
        """
        self._zoom_label.setText(f"缩放: {zoom * 100:.0f}%")

    def _on_pixel_clicked(self, x: int, y: int, value: object):
        """像素点击回调

        参数：
            x: X坐标
            y: Y坐标
            value: 像素值
        """
        self._pos_label.setText(f"位置: ({x}, {y}) | 值: {value}")

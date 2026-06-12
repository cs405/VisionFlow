"""编辑器控件 — QGraphicsView + 工具栏 + 小地图 + 键盘快捷键。

功能：
  - 使用 Ctrl+滚轮 缩放，中键拖拽平移
  - 通过 CommandStack 支持撤销/重做（Ctrl+Z / Ctrl+Y）
  - 复制/粘贴（Ctrl+C / Ctrl+V）
  - 删除（Del / Backspace），全选（Ctrl+A）
  - 适应窗口（F），100%缩放（Ctrl+0）
  - 单步执行（Shift+F5）— 单个节点执行
  - 角落小地图概览
  - 包含所有命令按钮的工具栏
  - 从工具箱拖拽
  - 右键上下文菜单
"""

import time
import queue

from PyQt5.QtWidgets import (QGraphicsView, QWidget, QVBoxLayout)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer
from PyQt5.QtGui import (QPainter, QWheelEvent, QMouseEvent, QKeyEvent,
                          QColor, QPen, QBrush, QDragEnterEvent, QDropEvent)

from core.node_base import NodeBase, VisionNodeData
from core.workflow import WorkflowEngine
from core.events import EventType, event_system
from core.registry import node_registry

from gui.node_editor.scene import DiagramScene
from gui.node_editor.node_item import NodeItem, NodeState
# from gui.node_editor.edge_item import EdgeItem
from gui.node_editor.socket_item import SocketItem

# ── 小地图 ──────────────────────────────────────────────────────────────

class MiniMapView(QGraphicsView):
    """角落中整个场景的小概览视图。"""

    # 点击小地图时发出的信号，携带场景坐标
    scene_point_clicked = pyqtSignal(QPointF)

    def __init__(self, scene: DiagramScene, parent=None):
        """初始化小地图

        参数：
            scene: 图表场景
            parent: 父对象
        """
        # 调用父类QGraphicsView的构造函数
        super().__init__(scene, parent)
        # 固定大小为180x120像素
        self.setFixedSize(180, 120)
        # 禁用水平滚动条
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 禁用垂直滚动条
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 启用抗锯齿渲染，使图形边缘平滑
        self.setRenderHints(QPainter.Antialiasing)
        # 设置边框形状为Box（有边框）
        self.setFrameShape(QGraphicsView.Box)
        # 设置样式表：蓝色边框，圆角4px，深色背景
        self.setStyleSheet("QGraphicsView { border: 2px solid #0078d4; border-radius: 4px; background: #1e1e1e; }")
        # 禁用交互（不响应鼠标拖拽缩放操作）
        self.setInteractive(False)
        # 适应整个场景的大小，保持宽高比
        self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)
        # 设置视口更新模式为最小更新
        self.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)

        # 初始化视口矩形覆盖层（空矩形）
        self._vp_rect: QRectF = QRectF()

    def sync_viewport(self, main_view: "DiagramEditorView"):
        """更新小地图以反映主视图的视口位置"""
        # 将主视图的视口矩形映射到场景坐标，获取边界矩形
        vp_rect = main_view.mapToScene(main_view.viewport().rect()).boundingRect()
        # 保存视口矩形
        self._vp_rect = vp_rect
        # 触发视口重绘
        self.viewport().update()

    def drawForeground(self, painter: QPainter, rect: QRectF):
        """绘制前景（视口矩形）"""
        # 调用父类的drawForeground方法
        super().drawForeground(painter, rect)
        # 如果视口矩形有效
        if self._vp_rect.isValid():
            # 设置画笔：蓝色，线宽1.5
            painter.setPen(QPen(QColor("#0078d4"), 1.5))
            # 设置画刷：半透明蓝色（40/255透明度）
            painter.setBrush(QBrush(QColor(0, 120, 212, 40)))
            # 绘制矩形表示当前主视图在场景中的位置
            painter.drawRect(self._vp_rect)

    def mousePressEvent(self, event: QMouseEvent):
        """点击小地图时导航主视图到对应位置"""
        # 如果按下的是左键
        if event.button() == Qt.LeftButton:
            # 将点击位置转换为场景坐标，发出信号（携带场景坐标）
            self.scene_point_clicked.emit(self.mapToScene(event.pos()))
            # 事件已处理
            event.accept()
            return
        # 其他情况调用父类处理
        super().mousePressEvent(event)


# ── 图表编辑器视图 ───────────────────────────────────────────────────

class DiagramEditorView(QGraphicsView):
    """支持缩放/平移/适应窗口、键盘快捷键和拖拽放置的 QGraphicsView。"""

    MIN_ZOOM = 0.05      # 最小缩放比例（5%）
    MAX_ZOOM = 5.0       # 最大缩放比例（500%）
    ZOOM_FACTOR = 1.15   # 缩放因子（每次缩放乘以此值）

    zoom_changed = pyqtSignal(float)           # 缩放比例变更信号
    node_dropped = pyqtSignal(str, QPointF)    # 节点拖拽放置信号（节点类型名，场景坐标）

    def __init__(self, scene: DiagramScene, parent=None):
        """初始化编辑器视图

        参数：
            scene: 图表场景
            parent: 父对象
        """
        # 调用父类QGraphicsView的构造函数
        super().__init__(scene, parent)
        # 保存图表场景引用
        self._diagram_scene = scene
        # 当前缩放比例，初始为1.0（100%）
        self._zoom = 1.0
        # 平移起始点，初始为None
        self._pan_start: QPointF | None = None

        # 设置渲染提示：抗锯齿 + 平滑图像变换
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        # 设置视口更新模式为全视口更新
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        # 设置变换锚点为鼠标下方（缩放时以鼠标位置为中心）
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        # 设置调整大小锚点为鼠标下方
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        # 设置拖拽模式为橡皮筋框选
        self.setDragMode(QGraphicsView.RubberBandDrag)
        # 设置无边框
        self.setFrameShape(QGraphicsView.NoFrame)
        # 设置接受拖拽事件
        self.setAcceptDrops(True)
        # 设置光标样式为箭头
        self.setCursor(Qt.ArrowCursor)

    # ── 缩放功能 ──────────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent):
        """处理滚轮事件（Ctrl+滚轮缩放）"""
        # 如果按下了Ctrl键
        if event.modifiers() & Qt.ControlModifier:
            # 获取滚轮滚动角度（正值向上滚动/放大，负值向下滚动/缩小）
            delta = event.angleDelta().y()
            # 根据滚动方向计算缩放因子（向上放大，向下缩小）
            factor = self.ZOOM_FACTOR if delta > 0 else 1.0 / self.ZOOM_FACTOR
            # 计算新的缩放比例
            new_zoom = self._zoom * factor
            # 检查新的缩放比例是否在允许范围内
            if self.MIN_ZOOM <= new_zoom <= self.MAX_ZOOM:
                # 更新缩放比例
                self._zoom = new_zoom
                # 执行缩放变换
                self.scale(factor, factor)
                # 发出缩放比例变更信号
                self.zoom_changed.emit(self._zoom)
        else:
            # 未按下Ctrl键时，调用父类处理（默认滚动行为）
            super().wheelEvent(event)

    def zoom_in(self):
        """放大"""
        # 计算新的缩放比例（当前值乘以缩放因子，不超过最大值）
        self._zoom = min(self._zoom * self.ZOOM_FACTOR, self.MAX_ZOOM)
        # 执行缩放变换
        self.scale(self.ZOOM_FACTOR, self.ZOOM_FACTOR)
        # 发出缩放比例变更信号
        self.zoom_changed.emit(self._zoom)

    def zoom_out(self):
        """缩小"""
        # 计算新的缩放比例（当前值除以缩放因子，不小于最小值）
        self._zoom = max(self._zoom / self.ZOOM_FACTOR, self.MIN_ZOOM)
        # 执行缩放变换（缩小）
        self.scale(1.0 / self.ZOOM_FACTOR, 1.0 / self.ZOOM_FACTOR)
        # 发出缩放比例变更信号
        self.zoom_changed.emit(self._zoom)

    def fit_to_window(self):
        """适应窗口大小"""
        # 将整个场景适应到视图内，保持宽高比
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
        # 获取当前变换矩阵的X方向缩放值作为当前缩放比例
        self._zoom = self.transform().m11()
        # 发出缩放比例变更信号
        self.zoom_changed.emit(self._zoom)

    def zoom_to_100(self):
        """重置到100%缩放"""
        # 设置缩放比例为1.0
        self._zoom = 1.0
        # 重置所有变换
        self.resetTransform()
        # 发出缩放比例变更信号
        self.zoom_changed.emit(self._zoom)

    @property
    def zoom_level(self) -> float:
        """获取当前缩放级别"""
        return self._zoom

    # ── 平移功能 ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件（中键/右键开始平移）"""
        # 如果按下的是中键或右键
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            # 记录平移起始点（当前鼠标位置）
            self._pan_start = event.pos()
            # 设置光标为闭手形状
            self.setCursor(Qt.ClosedHandCursor)
            # 事件已处理
            event.accept()
            return
        # 其他情况调用父类处理
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件（平移拖拽）"""
        # 如果正在平移（有起始点记录）
        if self._pan_start is not None:
            # 计算当前鼠标位置相对于起始点的偏移量
            delta = event.pos() - self._pan_start
            # 更新起始点为当前位置
            self._pan_start = event.pos()
            # 水平滚动条移动负的X偏移量（实现平移）
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            # 垂直滚动条移动负的Y偏移量
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            # 事件已处理
            event.accept()
            return
        # 非平移状态调用父类处理
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件（结束平移）"""
        # 获取释放的按钮
        btn = event.button()
        # 如果是中键或右键，且正在平移状态
        if btn in (Qt.MiddleButton, Qt.RightButton) and self._pan_start is not None:
            # 清空平移起始点
            self._pan_start = None
            # 恢复光标为箭头
            self.setCursor(Qt.ArrowCursor)
            # 事件已处理
            event.accept()
            return
        # 其他情况调用父类处理
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """鼠标双击事件：双击节点打开属性面板，双击空白处适应窗口"""
        # 如果双击的是左键
        if event.button() == Qt.LeftButton:
            # 获取鼠标位置下的图形项
            item = self.itemAt(event.pos())
            # 如果有点击到图形项
            if item is not None:
                # 让图形项处理（NodeItem 会发出 node_double_clicked 信号）
                super().mouseDoubleClickEvent(event)
                # 事件已处理
                event.accept()
                return
            else:
                # 双击空白处：适应窗口
                self.fit_to_window()
                # 事件已处理
                event.accept()
                return
        # 其他情况调用父类处理
        super().mouseDoubleClickEvent(event)

    # ── 键盘快捷键 ──────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        """处理键盘快捷键"""
        # 获取按下的键
        k = event.key()
        # 获取修饰键状态
        mod = event.modifiers()

        # 删除键或退格键：删除选中的项
        if k == Qt.Key_Delete or k == Qt.Key_Backspace:
            self._diagram_scene.delete_selected()
        # Ctrl+A：全选
        elif k == Qt.Key_A and mod & Qt.ControlModifier:
            # 遍历所有节点项，全部设为选中
            for item in self._diagram_scene.get_all_node_items():
                item.setSelected(True)
        # Ctrl+C：复制
        elif k == Qt.Key_C and mod & Qt.ControlModifier:
            self._diagram_scene.copy_selected()
        # Ctrl+V：粘贴
        elif k == Qt.Key_V and mod & Qt.ControlModifier:
            self._diagram_scene.paste()
        # Ctrl+Shift+Z：重做
        elif k == Qt.Key_Z and mod & Qt.ControlModifier and mod & Qt.ShiftModifier:
            self._diagram_scene.redo()
        # Ctrl+Z：撤销
        elif k == Qt.Key_Z and mod & Qt.ControlModifier:
            self._diagram_scene.undo()
        # Ctrl+Y：重做
        elif k == Qt.Key_Y and mod & Qt.ControlModifier:
            self._diagram_scene.redo()
        # F（无修饰键）：适应窗口
        elif k == Qt.Key_F and not mod:
            self.fit_to_window()
        # Ctrl+0：100%缩放
        elif k == Qt.Key_0 and mod & Qt.ControlModifier:
            self.zoom_to_100()
        else:
            # 其他按键调用父类处理
            super().keyPressEvent(event)

    # ── 右键上下文菜单（非拖拽时）─────────────────────────────────────────

    def contextMenuEvent(self, event):
        """显示右键上下文菜单"""
        # 如果正在平移拖拽中，不显示菜单
        if self._pan_start is not None:
            return
        # 将鼠标位置转换为场景坐标
        pos = self.mapToScene(event.pos())
        # 获取场景的上下文菜单
        menu = self._diagram_scene.context_menu(pos)
        # 如果有菜单，在全局位置弹出
        if menu:
            menu.exec_(event.globalPos())

    # ── 从工具箱拖拽放置 ────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件"""
        # 如果拖拽数据包含文本
        if event.mimeData().hasText():
            # 接受拖拽动作
            event.acceptProposedAction()
        else:
            # 否则调用父类处理
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """拖拽移动事件"""
        # 如果拖拽数据包含文本
        if event.mimeData().hasText():
            # 接受拖拽动作
            event.acceptProposedAction()
        else:
            # 否则调用父类处理
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        """拖拽放置事件"""
        # 如果拖拽数据包含文本
        if event.mimeData().hasText():
            # 获取节点类型名称（拖拽文本内容）
            type_name = event.mimeData().text()
            # 将鼠标位置转换为场景坐标
            scene_pos = self.mapToScene(event.pos())
            # 发出节点拖拽放置信号
            self.node_dropped.emit(type_name, scene_pos)
            # 接受拖拽动作
            event.acceptProposedAction()
        else:
            # 否则调用父类处理
            super().dropEvent(event)


# ── 图表编辑器控件 ─────────────────────────────────────────────────

class DiagramEditorWidget(QWidget):
    """完整的编辑器：工具栏 + 场景/视图 + 小地图。

    工具栏按钮：
      ▶ 运行  ■ 停止  ⚡单步执行 | ↩撤销 ↪重做 | 📋复制 📌粘贴 | 适应窗口 1:1 | 缩放
    """

    # 信号定义
    node_selected = pyqtSignal(object)           # 节点选中信号
    node_deselected = pyqtSignal()               # 节点取消选中信号
    node_double_clicked = pyqtSignal(object)     # 节点双击信号
    node_properties_requested = pyqtSignal(object)  # 请求属性面板信号
    node_help_requested = pyqtSignal(object)     # 请求帮助信号
    node_executed = pyqtSignal(object, str, str)  # 节点执行信号（节点，状态，时间）

    def __init__(self, parent=None):
        """初始化图表编辑器控件"""
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 当前工作流引擎，初始为None
        self._workflow: WorkflowEngine | None = None
        # 订阅的工作流引擎，初始为None
        self._subscribed_workflow: WorkflowEngine | None = None
        # 创建小地图更新定时器
        self._mini_timer = QTimer(self)
        # 设置定时器间隔为100毫秒
        self._mini_timer.setInterval(100)
        # 连接定时器timeout信号到_update_minimap方法
        self._mini_timer.timeout.connect(self._update_minimap)

        # 线程安全的状态队列：工作线程推送事件，主线程轮询应用
        self._state_queue: queue.Queue = queue.Queue()
        # 创建状态轮询定时器
        self._state_poll = QTimer(self)
        # 设置轮询间隔为30毫秒
        self._state_poll.setInterval(30)
        # 连接定时器timeout信号到_drain_state_queue方法
        self._state_poll.timeout.connect(self._drain_state_queue)
        # 启动状态轮询定时器
        self._state_poll.start()

        # 设置UI界面
        self._setup_ui()

    def _setup_ui(self):
        """设置用户界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

        # ── 场景和视图（先创建，工具栏按钮会引用它们）──
        # 创建主体容器
        body = QWidget()
        # 创建主体容器内的垂直布局
        body_lo = QVBoxLayout(body)
        # 设置布局边距为0
        body_lo.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        body_lo.setSpacing(0)

        # 创建图表场景
        self.scene = DiagramScene()
        # 创建编辑器视图，传入场景
        self.view = DiagramEditorView(self.scene)

        # 连接场景信号到编辑器控件的信号
        # 节点选中信号
        self.scene.node_selected.connect(self.node_selected.emit)
        # 节点取消选中信号
        self.scene.node_deselected.connect(self.node_deselected.emit)
        # 请求属性面板信号
        self.scene.node_properties_requested.connect(self.node_properties_requested.emit)
        # 请求帮助信号
        self.scene.node_help_requested.connect(self.node_help_requested.emit)
        # 场景选中项变化信号
        self.scene.selectionChanged.connect(self._update_toolbar_state)

        # 连接视图的节点拖拽放置信号到_on_node_dropped方法
        self.view.node_dropped.connect(self._on_node_dropped)

        # 连接插座拖拽信号
        self._connect_socket_signals()

        # 将视图添加到主体布局中
        body_lo.addWidget(self.view)
        # 将主体容器添加到主布局，拉伸因子为1
        layout.addWidget(body, 1)

        # ── 小地图 ──
        # 创建小地图视图，传入场景
        self._minimap = MiniMapView(self.scene, self)
        # 连接小地图的点击信号到_center_view_on_scene_point方法
        self._minimap.scene_point_clicked.connect(self._center_view_on_scene_point)
        # 设置初始位置（左上角偏移6,6）
        self._minimap.move(6, 6)
        # 显示小地图
        self._minimap.show()
        # 设置小地图的父对象为视图
        self._minimap.setParent(self.view)
        # 将小地图提升到最上层
        self._minimap.raise_()

        # 启动小地图更新定时器
        self._mini_timer.start()

    def _update_minimap(self):
        """更新小地图"""
        # 检查小地图和视图是否存在
        if hasattr(self, '_minimap') and hasattr(self, 'view'):
            # 同步小地图的视口位置
            self._minimap.sync_viewport(self.view)

    def resizeEvent(self, event):
        """窗口大小改变事件，调整小地图位置"""
        # 调用父类的resizeEvent
        super().resizeEvent(event)
        # 如果小地图存在
        if hasattr(self, '_minimap'):
            # 将小地图移动到右上角（右侧距离190px，顶部距离10px）
            self._minimap.move(self.width() - 190, 10)

    def _update_toolbar_state(self):
        """更新工具栏状态（空实现，子类可重写）"""
        pass

    def _center_view_on_scene_point(self, scene_pos: QPointF):
        """将视图居中到场景的指定点"""
        # 将视图中心移动到指定场景坐标
        self.view.centerOn(scene_pos)
        # 更新小地图
        self._update_minimap()

    # ── 插座拖拽信号 ───────────────────────────────────────────

    def _connect_socket_signals(self):
        """连接插座拖拽信号"""
        # 连接场景的节点项添加信号到_on_node_item_added方法
        self.scene.node_item_added.connect(self._on_node_item_added)

    def _on_node_item_added(self, node_item: NodeItem):
        """节点项添加时的处理"""
        # 连接节点的双击信号到编辑器的node_double_clicked信号
        node_item.node_double_clicked.connect(self.node_double_clicked.emit)
        # 遍历节点的所有插座
        for socket in node_item.sockets:
            # 连接插座的拖拽开始信号
            socket.connection_started.connect(self._on_socket_drag_start)
            # 连接插座的拖拽移动信号
            socket.connection_moved.connect(self._on_socket_drag_move)
            # 连接插座的拖拽结束信号
            socket.connection_ended.connect(self._on_socket_drag_end)

    def _on_socket_drag_start(self, socket: SocketItem):
        """插座拖拽开始"""
        # 主要路径：场景的 event() 在图表层面拦截移动/释放
        # 此信号仅作为拖拽开始的二次确认，目前不需要额外处理
        pass

    def _on_socket_drag_move(self, socket: SocketItem, scene_pos: QPointF):
        """插座拖拽移动"""
        # 场景通过 event() 重写处理移动，目前不需要额外处理
        pass

    def _on_socket_drag_end(self, socket: SocketItem, scene_pos: QPointF):
        """插座拖拽结束"""
        # 场景通过 event() 重写处理释放，目前不需要额外处理
        pass

    def _on_node_dropped(self, type_name: str, pos: QPointF):
        """节点拖拽放置处理"""
        # 从节点注册表创建节点实例
        node = node_registry.create(type_name)
        # 如果节点创建成功
        if node:
            from core.commands import AddNodeCommand
            # 通过命令栈执行添加节点命令
            self.scene.command_stack.execute(AddNodeCommand(self.scene, node, (pos.x(), pos.y())))

    # ── 工作流集成 ──────────────────────────────────────────

    def bind_workflow(self, workflow: WorkflowEngine):
        """绑定工作流引擎"""
        # 取消旧工作流的事件订阅
        self._unsubscribe_workflow_events()
        # 保存新的工作流引擎
        self._workflow = workflow
        # 保存订阅的工作流引用
        self._subscribed_workflow = workflow
        # 绑定场景的工作流
        self.scene.bind_workflow(workflow)
        # 从工作流加载场景数据
        self.scene.load_from_workflow(workflow)
        # 订阅新工作流的事件
        self._subscribe_workflow_events()

    def save_to_workflow(self):
        """将当前场景的位置和连线持久化回绑定的工作流"""
        # 如果存在工作流
        if self._workflow:
            # 将场景保存到工作流
            self.scene.save_to_workflow(self._workflow)

    def _on_run(self):
        """运行工作流"""
        if self._workflow:
            # 1) 重置所有节点为 IDLE，清除上次运行残留的 _last_error
            for item in self.scene.get_all_node_items():
                item.set_state(NodeState.IDLE)
                nd = item.node_data
                if nd is not None and hasattr(nd, '_last_error'):
                    del nd._last_error
            # 2) 清空状态队列中的残留事件
            while not self._state_queue.empty():
                try: self._state_queue.get_nowait()
                except: break
            # 3) 执行工作流（阻塞主线程）
            self._workflow.execute()
            # 4) 先处理事件队列（让 NODE_ERROR/NODE_COMPLETED 更新到 NodeItem）
            self._drain_state_queue()
            # 5) 再以 _last_error 为准做最终同步（事件可能丢失，_last_error 是权威来源）
            self._sync_states_from_data()

    def _on_stop(self):
        """停止工作流"""
        # 如果存在工作流
        if self._workflow:
            # 停止工作流引擎
            self._workflow.stop()
            # 重置所有节点的状态为空闲
            for item in self.scene.get_all_node_items():
                item.set_state(NodeState.IDLE)

    def _on_run_step(self):
        """单步执行当前选中的节点"""
        nd = self.scene.get_selected_node_data()
        if nd and isinstance(nd, VisionNodeData) and self._workflow:
            item = self.scene.get_node_item(nd.node_id)
            if item:
                item.set_state(NodeState.RUNNING)
            self._workflow.execute_step(nd.node_id)
            # 直接同步状态，不依赖事件队列
            self._sync_states_from_data()
            self.scene.status_message.emit(f"单步执行: {nd.name}")

    def _on_undo(self):
        """撤销"""
        # 调用场景的撤销方法
        self.scene.undo()
        # 更新工具栏状态
        self._update_toolbar_state()

    def _on_redo(self):
        """重做"""
        # 调用场景的重做方法
        self.scene.redo()
        # 更新工具栏状态
        self._update_toolbar_state()

    # ── 公共API ────────────────────────────────────────────────────

    def add_node(self, node_data: NodeBase, pos: QPointF = None, group_name: str = ""):
        """添加节点到场景"""
        from core.commands import AddNodeCommand
        # 如果有位置和分组名称
        if pos and group_name:
            # 直接添加节点项到场景
            item = self.scene.add_node_item(node_data, pos, group_name)
            return item
        # 否则通过命令栈执行添加（支持撤销）
        self.scene.command_stack.execute(AddNodeCommand(self.scene, node_data, pos, group_name))
        # 返回添加的节点项
        return self.scene.get_node_item(node_data.node_id)

    def clear(self):
        """清空场景"""
        # 调用场景的清空所有方法
        self.scene.clear_all()

    def _subscribe_workflow_events(self):
        """订阅工作流事件"""
        # 订阅节点开始事件
        event_system.subscribe(EventType.NODE_STARTED, self._on_node_started)
        # 订阅节点完成事件
        event_system.subscribe(EventType.NODE_COMPLETED, self._on_node_completed)
        # 订阅节点错误事件
        event_system.subscribe(EventType.NODE_ERROR, self._on_node_error)
        # 订阅工作流停止事件
        event_system.subscribe(EventType.WORKFLOW_STOPPED, self._on_workflow_stopped)
        # 订阅连线开始事件
        event_system.subscribe(EventType.LINK_STARTED, self._on_link_started)
        # 订阅连线完成事件
        event_system.subscribe(EventType.LINK_COMPLETED, self._on_link_completed)
        # 订阅端口开始事件
        event_system.subscribe(EventType.PORT_STARTED, self._on_port_started)
        # 订阅端口完成事件
        event_system.subscribe(EventType.PORT_COMPLETED, self._on_port_completed)

    def _unsubscribe_workflow_events(self):
        """取消订阅工作流事件"""
        # 取消订阅节点开始事件
        event_system.unsubscribe(EventType.NODE_STARTED, self._on_node_started)
        # 取消订阅节点完成事件
        event_system.unsubscribe(EventType.NODE_COMPLETED, self._on_node_completed)
        # 取消订阅节点错误事件
        event_system.unsubscribe(EventType.NODE_ERROR, self._on_node_error)
        # 取消订阅工作流停止事件
        event_system.unsubscribe(EventType.WORKFLOW_STOPPED, self._on_workflow_stopped)
        # 取消订阅连线开始事件
        event_system.unsubscribe(EventType.LINK_STARTED, self._on_link_started)
        # 取消订阅连线完成事件
        event_system.unsubscribe(EventType.LINK_COMPLETED, self._on_link_completed)
        # 取消订阅端口开始事件
        event_system.unsubscribe(EventType.PORT_STARTED, self._on_port_started)
        # 取消订阅端口完成事件
        event_system.unsubscribe(EventType.PORT_COMPLETED, self._on_port_completed)

    def _belongs_to_bound_workflow(self, sender) -> bool:
        """检查发送者是否属于绑定的工作流"""
        # 返回发送者存在且其diagram_data属性等于订阅的工作流
        return bool(sender) and getattr(sender, 'diagram_data', None) is self._subscribed_workflow

    def _link_belongs(self, sender) -> bool:
        """检查连线是否属于绑定的工作流"""
        # 返回订阅的工作流存在且发送者在工作流的连线列表中
        return (self._subscribed_workflow is not None
                and sender in self._subscribed_workflow._links)

    def _port_belongs(self, sender) -> bool:
        """检查端口是否属于绑定的工作流（通过其节点）"""
        # 如果没有订阅的工作流，返回False
        if self._subscribed_workflow is None:
            return False
        # 根据端口所属的节点ID获取节点
        node = self._subscribed_workflow.get_node_by_id(sender.node_id)
        # 返回节点是否存在
        return node is not None

    def _drain_state_queue(self):
        """在主线程上应用所有待处理的状态变更"""
        try:
            # 循环获取队列中的所有待处理状态
            while True:
                # 从队列中获取状态（非阻塞）
                node_id, state = self._state_queue.get_nowait()
                # 如果是全部节点的状态更新
                if node_id == "__all__":
                    # 将所有节点的状态设置为空闲
                    for item in self.scene.get_all_node_items():
                        item.set_state(NodeState.IDLE)
                else:
                    # 更新单个节点的状态
                    self.scene.on_workflow_state_changed(node_id, state)
        # 队列为空时退出循环
        except queue.Empty:
            pass

    def _on_node_started(self, sender, **kwargs):
        """节点开始执行事件处理"""
        # 如果发送者属于绑定的工作流
        if self._belongs_to_bound_workflow(sender):
            # 将节点状态设为"running"放入队列
            self._state_queue.put((sender.node_id, "running"))

    def _on_node_completed(self, sender, **kwargs):
        """节点执行完成事件处理"""
        # 如果发送者属于绑定的工作流
        if self._belongs_to_bound_workflow(sender):
            # 将节点状态设为"completed"放入队列
            self._state_queue.put((sender.node_id, "completed"))
            # 发出节点执行完成信号，状态为Success，时间为当前时间
            self.node_executed.emit(sender, "Success", time.strftime("%H:%M:%S"))

    def _on_node_error(self, sender, **kwargs):
        """节点执行错误事件处理"""
        # 如果发送者属于绑定的工作流
        if self._belongs_to_bound_workflow(sender):
            # 将节点状态设为"error"放入队列
            self._state_queue.put((sender.node_id, "error"))
            # 发出节点执行错误信号，状态为Error，时间为当前时间
            self.node_executed.emit(sender, "Error", time.strftime("%H:%M:%S"))

    def _on_workflow_stopped(self, sender, **kwargs):
        """工作流停止事件处理"""
        # 如果发送者是订阅的工作流
        if sender is self._subscribed_workflow:
            # 将所有节点状态设为"idle"放入队列
            self._state_queue.put(("__all__", "idle"))

    def _sync_states_from_data(self):
        """执行完毕后直接同步：从节点数据 _last_error 设置 NodeItem 状态。

        参照 WPF-VisionMaster：状态存储在数据对象上，执行完成后直接读取。
        不依赖事件队列（主线程阻塞期间事件无法被定时器处理）。
        """
        from core.node_base import VisionNodeData
        for item in self.scene.get_all_node_items():
            nd = item.node_data
            if not isinstance(nd, VisionNodeData):
                continue
            if not hasattr(nd, '_last_error'):
                # 未执行过的节点保持 IDLE
                continue
            if nd._last_error:
                item.set_state(NodeState.ERROR)
            else:
                item.set_state(NodeState.COMPLETED)

    def refresh_all_node_states(self):
        """同步所有节点项的视觉状态到模型状态

        在工作流完成后作为后备方案调用，以防个别节点的信号丢失
        """
        # 遍历所有节点项
        for item in self.scene.get_all_node_items():
            # 从节点数据更新节点显示状态
            item.update_from_node()

    # ── 连线/端口事件处理（连线模式/端口模式）──

    def _on_link_started(self, sender, **kwargs):
        """连线开始执行事件"""
        # 如果连线属于绑定的工作流
        if self._link_belongs(sender):
            # 更新连线的状态为运行中
            self.scene.on_link_state_changed(sender.link_id, "running")

    def _on_link_completed(self, sender, **kwargs):
        """连线执行完成事件"""
        # 如果连线属于绑定的工作流
        if self._link_belongs(sender):
            # 更新连线的状态为已完成
            self.scene.on_link_state_changed(sender.link_id, "completed")

    def _on_port_started(self, sender, **kwargs):
        """端口开始执行事件"""
        # 如果端口属于绑定的工作流
        if self._port_belongs(sender):
            # 更新端口的状态为运行中
            self.scene.on_port_state_changed(sender.node_id, sender.port_id, "running")

    def _on_port_completed(self, sender, **kwargs):
        """端口执行完成事件"""
        # 如果端口属于绑定的工作流
        if self._port_belongs(sender):
            # 更新端口的状态为已完成
            self.scene.on_port_state_changed(sender.node_id, sender.port_id, "completed")
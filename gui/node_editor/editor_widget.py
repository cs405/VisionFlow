"""
编辑器控件 — QGraphicsView + 小地图 + 键盘快捷键。
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
import threading

from PyQt5.QtWidgets import (QGraphicsView, QWidget, QVBoxLayout)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer
from PyQt5.QtGui import (QPainter, QWheelEvent, QMouseEvent, QKeyEvent,
                          QColor, QPen, QBrush, QDragEnterEvent, QDropEvent)

from core.node_base import NodeBase
from core.data_packet import FlowableResultState
from core.node_vision import VisionNodeData
from core.commands import AddNodeCommand
from core.workflow import WorkflowEngine
from core.events import EventType, event_system
from core.registry import node_registry

from gui.node_editor.scene import DiagramScene
from gui.node_editor.node_item import NodeItem, NodeState


# ── 小地图 ──────────────────────────────────────────────────────────────

class MiniMapView(QGraphicsView):
    """角落中整个场景的小概览视图。"""

    # 点击小地图时发出的信号，携带场景坐标
    scene_point_clicked = pyqtSignal(QPointF)

    def __init__(self, scene: DiagramScene, parent=None):
        """
        初始化小地图
        参数：
            scene: 图表场景
            parent: 父对象
        """
        super().__init__(scene, parent)
        self.setFixedSize(180, 120)                               # 固定大小为180x120像素
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 禁用水平滚动条
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)    # 禁用垂直滚动条
        self.setRenderHints(QPainter.Antialiasing)                # 启用抗锯齿渲染，使图形边缘平滑
        self.setFrameShape(QGraphicsView.Box)                     # 设置边框形状为Box（有边框）
        # 设置样式表：蓝色边框，圆角4px，深色背景
        self.setStyleSheet("QGraphicsView { border: 2px solid #0078d4; border-radius: 4px; background: #1e1e1e; }")
        self.setInteractive(False)                                # 禁用交互（不响应鼠标拖拽缩放操作）
        self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)     # 适应整个场景的大小，保持宽高比
        self.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)  # 设置视口更新模式为最小更新
        self._vp_rect: QRectF = QRectF()                          # 初始化视口矩形覆盖层（空矩形）

    def sync_viewport(self, main_view: "DiagramEditorView"):
        """
        更新小地图以反映主视图的视口位置
        """
        vp_rect = main_view.mapToScene(main_view.viewport().rect()).boundingRect()  # 将主视图的视口矩形映射到场景坐标，获取边界矩形
        self._vp_rect = vp_rect   # 保存视口矩形
        self.viewport().update()  # 触发视口重绘

    def drawForeground(self, painter: QPainter, rect: QRectF):
        """
        绘制前景（视口矩形）
        """
        super().drawForeground(painter, rect)
        if self._vp_rect.isValid():
            painter.setPen(QPen(QColor("#0078d4"), 1.5))
            painter.setBrush(QBrush(QColor(0, 120, 212, 40)))
            painter.drawRect(self._vp_rect)

    def mousePressEvent(self, event: QMouseEvent):
        """
        点击小地图时导航主视图到对应位置
        """
        # 如果按下的是左键
        if event.button() == Qt.LeftButton:
            self.scene_point_clicked.emit(self.mapToScene(event.pos()))  # 将点击位置转换为场景坐标，发出信号（携带场景坐标）
            event.accept()  # 标记事件已处理，事件到此为止，不再传给父控件
            return
        super().mousePressEvent(event)


# ── 图表编辑器视图 ───────────────────────────────────────────────────

class DiagramEditorView(QGraphicsView):
    """
    支持缩放/平移/适应窗口、键盘快捷键和拖拽放置的 QGraphicsView。
    """

    MIN_ZOOM = 0.05      # 最小缩放比例（5%）
    MAX_ZOOM = 5.0       # 最大缩放比例（500%）
    ZOOM_FACTOR = 1.15   # 缩放因子（每次缩放乘以此值）

    zoom_changed = pyqtSignal(float)               # 缩放比例变更信号
    node_dropped = pyqtSignal(str, QPointF)  # 节点拖拽放置信号（节点类型名，场景坐标）

    def __init__(self, scene: DiagramScene, parent=None):
        """
        初始化编辑器视图
        参数：
            scene: 图表场景
            parent: 父对象
        """
        super().__init__(scene, parent)
        self._diagram_scene = scene
        self._zoom = 1.0
        self._pan_start: QPointF | None = None

        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)  # 启用抗锯齿和高质量缩放
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)  # 设置视口更新模式为全视口更新
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)  # 设置变换锚点为鼠标下方（缩放时以鼠标位置为中心）
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)          # 设置调整大小锚点为鼠标下方
        self.setDragMode(QGraphicsView.RubberBandDrag)                # 设置拖拽模式为橡皮筋框选
        self.setFrameShape(QGraphicsView.NoFrame)                     # 设置无边框
        self.setAcceptDrops(True)                                     # 设置接受拖拽事件
        self.setCursor(Qt.ArrowCursor)                                # 设置光标样式为箭头

    # ── 缩放功能 ──────────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent):
        """
        处理滚轮事件（Ctrl+滚轮缩放）
                ⎧  zoom × 1.15        δ > 0（向上滚，放大）
        zoom' = ⎨
                ⎩  zoom ÷ 1.15        δ < 0（向下滚，缩小）
        0.05 ≤ zoom' ≤ 5.0
        δ = angleDelta().y()，向上滚 δ > 0 放大，向下滚 δ < 0 缩小。每次滚轮缩放 15%
        """
        if event.modifiers() & Qt.ControlModifier:  # 如果按下了Ctrl键
            delta = event.angleDelta().y()          # 获取滚轮滚动角度（正值向上滚动/放大，负值向下滚动/缩小）
            factor = self.ZOOM_FACTOR if delta > 0 else 1.0 / self.ZOOM_FACTOR  # 根据滚动方向计算缩放因子（向上放大，向下缩小）
            new_zoom = self._zoom * factor          # 计算新的缩放比例

            if self.MIN_ZOOM <= new_zoom <= self.MAX_ZOOM:  # 检查新的缩放比例是否在允许范围内
                self._zoom = new_zoom                       # 更新缩放比例
                self.scale(factor, factor)                  # 执行缩放变换
                self.zoom_changed.emit(self._zoom)          # 发出缩放比例变更信号
        else:
            super().wheelEvent(event)                       # 未按下Ctrl键时，调用父类处理（默认滚动行为）

    def fit_to_window(self):
        """适应窗口大小"""
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)  # 将整个场景适应到视图内，保持宽高比
        self._zoom = self.transform().m11()  # 获取当前变换矩阵的X方向缩放值作为当前缩放比例
        self.zoom_changed.emit(self._zoom)  # 发出缩放比例变更信号

    def zoom_to_100(self):
        """重置到100%缩放"""

        self._zoom = 1.0                    # 设置缩放比例为1.0
        self.resetTransform()               # 重置所有变换
        self.zoom_changed.emit(self._zoom)  # 发出缩放比例变更信号

    # ── 平移功能 ───────────────────────────────────────────────────────────
    def mousePressEvent(self, event: QMouseEvent):
        """
        鼠标按下事件（中键/右键开始平移）
        按右键可以平移画布
        """
        if event.button() in (Qt.MiddleButton, Qt.RightButton):  # 如果按下的是中键或右键
            self._pan_start = event.pos()                        # 记录平移起始点（当前鼠标位置）
            self.setCursor(Qt.ClosedHandCursor)                  # 设置光标为闭手形状
            event.accept()                                       # 事件已处理
            return
        super().mousePressEvent(event)  # 其他情况调用父类处理

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        鼠标移动事件（平移拖拽）
        当用户按住鼠标拖拽编辑器画布时，通过移动滚动条实现视图平移
        """
        if self._pan_start is not None:             # 如果正在平移（有起始点记录）
            delta = event.pos() - self._pan_start   # 计算当前鼠标位置相对于起始点的偏移量
            self._pan_start = event.pos()           # 更新起始点为当前位置
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())  # 水平滚动条移动负的X偏移量（实现平移）
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())      # 垂直滚动条移动负的Y偏移量
            event.accept()  # 事件已处理
            return

        super().mouseMoveEvent(event)  # 非平移状态调用父类处理

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件（结束平移）"""
        btn = event.button()  # 获取释放的按钮
        if btn in (Qt.MiddleButton, Qt.RightButton) and self._pan_start is not None:  # 如果是中键或右键，且正在平移状态
            self._pan_start = None          # 清空平移起始点
            self.setCursor(Qt.ArrowCursor)  # 恢复光标为箭头
            event.accept()                  # 事件已处理
            return

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """鼠标双击事件：双击节点打开属性面板，双击空白处适应窗口"""
        if event.button() == Qt.LeftButton:  # 如果双击的是左键
            item = self.itemAt(event.pos())  # 获取鼠标位置下的图形项
            if item is not None:             # 如果有点击到图形项
                super().mouseDoubleClickEvent(event)  # 让图形项处理（NodeItem 会发出 node_double_clicked 信号）
                event.accept()               # 事件已处理
                return
            else:
                self.fit_to_window()         # 双击空白处：适应窗口
                event.accept()               # 事件已处理
                return

        super().mouseDoubleClickEvent(event)

    # ── 键盘快捷键 ──────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        """处理键盘快捷键"""
        k = event.key()                                            # 获取按下的键
        mod = event.modifiers()                                    # 获取修饰键状态
        if k == Qt.Key_Delete or k == Qt.Key_Backspace:            # 删除键或退格键：删除选中的项
            self._diagram_scene.delete_selected()
        elif k == Qt.Key_A and mod & Qt.ControlModifier:           # Ctrl+A：全选
            for item in self._diagram_scene.get_all_node_items():  # 遍历所有节点项，全部设为选中
                item.setSelected(True)
        elif k == Qt.Key_C and mod & Qt.ControlModifier:           # Ctrl+C：复制
            self._diagram_scene.copy_selected()
        elif k == Qt.Key_V and mod & Qt.ControlModifier:           # Ctrl+V：粘贴
            self._diagram_scene.paste()
        elif k == Qt.Key_Z and mod & Qt.ControlModifier and mod & Qt.ShiftModifier:  # Ctrl+Shift+Z：重做
            self._diagram_scene.redo()
        elif k == Qt.Key_Z and mod & Qt.ControlModifier:           # Ctrl+Z：撤销
            self._diagram_scene.undo()
        elif k == Qt.Key_Y and mod & Qt.ControlModifier:           # Ctrl+Y：重做
            self._diagram_scene.redo()
        elif k == Qt.Key_F and not mod:                            # F（无修饰键）：适应窗口
            self.fit_to_window()
        elif k == Qt.Key_0 and mod & Qt.ControlModifier:           # Ctrl+0：100%缩放
            self.zoom_to_100()
        else:
            super().keyPressEvent(event)

    # ── 右键上下文菜单（非拖拽时）─────────────────────────────────────────
    def contextMenuEvent(self, event):
        """显示右键上下文菜单"""
        if self._pan_start is not None:               # 如果正在平移拖拽中，不显示菜单
            return

        pos = self.mapToScene(event.pos())            # 将鼠标位置转换为场景坐标
        menu = self._diagram_scene.context_menu(pos)  # 获取场景的上下文菜单
        if menu:
            menu.exec_(event.globalPos())             # 如果有菜单，在全局位置弹出

    # ── 从工具箱拖拽放置节点 ────────────────────────────────────────
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件"""

        if event.mimeData().hasText():    # 如果拖拽数据包含文本
            # print("从gui/toolbox_panel.py拖入节点，节点数据为{}".format(event.mimeData().text()))
            event.acceptProposedAction()  # 接受拖拽动作
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """拖拽移动事件"""
        if event.mimeData().hasText():    # 如果拖拽数据包含文本
            # print("节点{}在窗口内移动".format(event.mimeData().text()))
            event.acceptProposedAction()  # 接受拖拽动作
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        """拖拽节点放置事件"""
        if event.mimeData().hasText():                    # 如果拖拽数据包含文本
            # print("在窗口内释放节点，节点数据为{}".format(event.mimeData().text()))
            type_name = event.mimeData().text()           # 获取节点类型名称（拖拽文本内容）
            scene_pos = self.mapToScene(event.pos())      # 将鼠标位置转换为场景坐标
            self.node_dropped.emit(type_name, scene_pos)  # 发出节点拖拽放置信号
            event.acceptProposedAction()                  # 接受拖拽动作
        else:
            super().dropEvent(event)


# ── 图表编辑器控件 ─────────────────────────────────────────────────
class DiagramEditorWidget(QWidget):
    """
    完整的编辑器：场景/视图 + 小地图。
    """
    # 信号定义
    node_selected = pyqtSignal(object)              # 节点选中信号
    node_deselected = pyqtSignal()                  # 节点取消选中信号
    node_double_clicked = pyqtSignal(object)        # 节点双击信号
    node_properties_requested = pyqtSignal(object)  # 请求属性面板信号
    node_help_requested = pyqtSignal(object)        # 请求帮助信号
    execution_finished = pyqtSignal()               # 工作流执行完成信号

    def __init__(self, parent=None):
        """初始化图表编辑器控件"""
        super().__init__(parent)
        self._workflow: WorkflowEngine | None = None               # 当前工作流引擎，初始为None
        self._subscribed_workflow: WorkflowEngine | None = None    # 订阅的工作流引擎，初始为None
        self._state_queue: queue.Queue = queue.Queue()             # 线程安全的状态队列：工作线程推送事件，主线程轮询应用
        self._state_poll = QTimer(self)                            # 创建状态轮询定时器
        self._state_poll.setInterval(30)                           # 设置轮询间隔为30毫秒
        self._state_poll.timeout.connect(self._drain_state_queue)  # 连接定时器timeout信号到_drain_state_queue方法

        self._event_subscriptions = [
            (EventType.NODE_STARTED, self._on_node_started),
            (EventType.NODE_COMPLETED, self._on_node_completed),
            (EventType.NODE_ERROR, self._on_node_error),
            (EventType.LINK_STARTED, self._on_link_started),
            (EventType.LINK_COMPLETED, self._on_link_completed),
            (EventType.PORT_STARTED, self._on_port_started),
            (EventType.PORT_COMPLETED, self._on_port_completed),
            (EventType.WORKFLOW_STOPPED, self._on_workflow_stopped),
            (EventType.WORKFLOW_COMPLETED, self._on_workflow_completed),
        ]

        # 设置UI界面
        self._setup_ui()

    def _setup_ui(self):
        """设置用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 场景和视图（先创建，工具栏按钮会引用它们）──
        body = QWidget()
        body_lo = QVBoxLayout(body)
        body_lo.setContentsMargins(0, 0, 0, 0)
        body_lo.setSpacing(0)

        # 创建图表场景
        self.scene = DiagramScene()
        self.view = DiagramEditorView(self.scene)  # 创建编辑器视图，传入场景

        # 连接场景信号到编辑器控件的信号
        self.scene.node_selected.connect(self.node_selected.emit)              # 节点选中信号
        self.scene.node_deselected.connect(self.node_deselected.emit)          # 节点取消选中信号
        self.scene.node_properties_requested.connect(self.node_properties_requested.emit)  # 请求属性面板信号
        self.scene.node_help_requested.connect(self.node_help_requested.emit)  # 请求帮助信号
        self.view.node_dropped.connect(self._on_node_dropped)                  # 连接视图的节点拖拽放置信号到_on_node_dropped方法
        self._connect_socket_signals()                                         # 连接插座拖拽信号

        # 将视图添加到主体布局中
        body_lo.addWidget(self.view)
        layout.addWidget(body, 1)

        # ── 小地图 ──
        self._minimap = MiniMapView(self.scene, self)                                # 创建小地图视图，传入场景
        self._minimap.scene_point_clicked.connect(self._center_view_on_scene_point)  # 连接小地图的点击信号到_center_view_on_scene_point方法
        self._minimap.move(6, 6)                                                     # 设置初始位置（左上角偏移6,6）
        self._minimap.show()                                                         # 显示小地图
        self._minimap.setParent(self.view)                                           # 设置小地图的父对象为视图
        self._minimap.raise_()                                                       # 将小地图提升到最上层
        self.view.horizontalScrollBar().valueChanged.connect(self._update_minimap)   # 水平滚动时同步小地图
        self.view.verticalScrollBar().valueChanged.connect(self._update_minimap)     # 垂直滚动时同步小地图
        self.view.zoom_changed.connect(self._update_minimap)                         # 缩放时同步小地图

    def _update_minimap(self):
        """更新小地图"""
        if hasattr(self, '_minimap') and hasattr(self, 'view'):  # 检查小地图和视图是否存在
            self._minimap.sync_viewport(self.view)               # 同步小地图的视口位置

    def resizeEvent(self, event):
        """窗口大小改变事件，调整小地图位置"""
        super().resizeEvent(event)
        if hasattr(self, '_minimap'):                   # 如果小地图存在
            self._minimap.move(self.width() - 190, 10)  # 将小地图移动到右上角（右侧距离190px，顶部距离10px）

    def _center_view_on_scene_point(self, scene_pos: QPointF):
        """将视图居中到场景的指定点"""
        self.view.centerOn(scene_pos)  # 将视图中心移动到指定场景坐标
        self._update_minimap()         # 更新小地图

    # ── 插座拖拽信号 ───────────────────────────────────────────
    def _connect_socket_signals(self):
        """连接插座拖拽信号"""
        self.scene.node_item_added.connect(self._on_node_item_added)  # 连接场景的节点项添加信号到_on_node_item_added方法

    def _on_node_item_added(self, node_item: NodeItem):
        """节点项添加时的处理"""
        node_item.node_double_clicked.connect(self.node_double_clicked.emit)

    def _on_node_dropped(self, type_name: str, pos: QPointF):
        """节点拖拽放置处理"""
        node = node_registry.create(type_name)  # 从节点注册表创建节点实例
        if node:                                # 如果节点创建成功
            self.scene.command_stack.execute(AddNodeCommand(self.scene, node, (pos.x(), pos.y())))  # 通过命令栈执行添加节点命令

    # ── 工作流集成 ──────────────────────────────────────────
    def bind_workflow(self, workflow: WorkflowEngine):
        """绑定工作流引擎"""
        self._unsubscribe_workflow_events()      # 取消旧工作流的事件订阅
        self._workflow = workflow                # 保存新的工作流引擎
        self._subscribed_workflow = workflow     # 保存订阅的工作流引用
        self.scene.bind_workflow(workflow)       # 绑定场景的工作流
        self.scene.load_from_workflow(workflow)  # 从工作流加载场景数据
        self._subscribe_workflow_events()        # 订阅新工作流的事件

    def save_to_workflow(self):
        """将当前场景的位置和连线持久化回绑定的工作流"""
        if self._workflow:                               # 如果存在工作流
            self.scene.save_to_workflow(self._workflow)  # 将场景保存到工作流

    def start_state_polling(self):
        """开启消息队列"""
        self._state_poll.start()

    def _finalize_after_run(self):
        """工作流执行完成后的最终同步"""
        self._drain_state_queue()
        self._sync_states_from_data()

    def stop_state_polling(self):
        """停止状态轮询定时器（由外部生命周期管理调用）"""
        self._state_poll.stop()

    def _on_stop(self):
        """停止工作流"""
        if self._workflow:                                # 如果存在工作流
            self._workflow.stop()                         # 停止工作流引擎
            for item in self.scene.get_all_node_items():  # 重置所有节点的状态为空闲
                item.set_state(NodeState.IDLE)

    def _on_undo(self):
        """撤销"""
        self.scene.undo()

    def _on_redo(self):
        """重做"""
        self.scene.redo()

    # ── 公共API ────────────────────────────────────────────────────
    def _subscribe_workflow_events(self):
        """订阅工作流事件"""
        for event_type, handler in self._event_subscriptions:
            event_system.subscribe(event_type, handler)

    def _unsubscribe_workflow_events(self):
        """取消订阅工作流事件"""
        for event_type, handler in self._event_subscriptions:
            event_system.unsubscribe(event_type, handler)

    def closeEvent(self, event):
        """关闭时取消事件订阅，防止回调悬空"""
        self._unsubscribe_workflow_events()
        super().closeEvent(event)

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
        if self._subscribed_workflow is None:                            # 如果没有订阅的工作流，返回False
            return False

        node = self._subscribed_workflow.get_node_by_id(sender.node_id)  # 根据端口所属的节点ID获取节点
        return node is not None

    def _drain_state_queue(self):
        """在主线程上应用所有待处理的状态变更"""
        dispatch = {
            "__workflow_done__": lambda: (self._finalize_after_run(),
                                           self.execution_finished.emit()),
            "__all__": lambda: (self._set_all_idle(),
                                 self._finalize_after_run(),
                                 self.execution_finished.emit()),
        }
        try:
            while True:
                node_id, state = self._state_queue.get_nowait()
                handler = dispatch.get(node_id)
                if handler:
                    handler()
                else:
                    self.scene.on_workflow_state_changed(node_id, state)
        except queue.Empty:
            pass

    def _set_all_idle(self):
        """将所有节点状态设为空闲"""
        for item in self.scene.get_all_node_items():
            item.set_state(NodeState.IDLE)

    def _on_node_started(self, sender, **kwargs):
        """节点开始执行事件处理"""
        if self._belongs_to_bound_workflow(sender):             # 如果发送者属于绑定的工作流
            self._state_queue.put((sender.node_id, "running"))  # 将节点状态设为"running"放入队列

    def _on_node_completed(self, sender, **kwargs):
        """节点执行完成事件处理"""
        if self._belongs_to_bound_workflow(sender):              # 如果发送者属于绑定的工作流
            self._state_queue.put((sender.node_id, "completed"))  # 将节点状态设为"completed"放入队列

    def _on_node_error(self, sender, **kwargs):
        """节点执行错误事件处理"""
        if self._belongs_to_bound_workflow(sender):           # 如果发送者属于绑定的工作流
            self._state_queue.put((sender.node_id, "error"))  # 将节点状态设为"error"放入队列

    def _on_workflow_stopped(self, sender, **kwargs):
        """工作流停止事件处理"""
        if sender is self._subscribed_workflow:  # 如果发送者是订阅的工作流
            self._state_queue.put(("__all__", "idle"))  # 将所有节点状态设为"idle"放入队列

    def _on_workflow_completed(self, sender, **kwargs):
        """工作流完成事件处理"""
        if sender is self._subscribed_workflow:
            self._state_queue.put(("__workflow_done__", ""))

    def _sync_states_from_data(self):
        """
        执行完毕后直接同步：从节点数据 _execution_state 设置 NodeItem 状态。
        状态存储在数据对象上，执行完成后直接读取。
        不依赖事件队列（主线程阻塞期间事件无法被定时器处理）。
        """
        for item in self.scene.get_all_node_items():
            nd = item.node_data
            if not isinstance(nd, VisionNodeData):
                continue
            state = nd._execution_state
            if state == FlowableResultState.ERROR:
                item.set_state(NodeState.ERROR)
            elif state == FlowableResultState.OK:
                item.set_state(NodeState.COMPLETED)
            elif state == FlowableResultState.BREAK:
                item.set_state(NodeState.IDLE)
            # None = 未执行，保持当前状态不变

    def refresh_all_node_states(self):
        """
        同步所有节点项的视觉状态到模型状态
        在工作流完成后作为后备方案调用，以防个别节点的信号丢失
        """
        # 遍历所有节点项
        for item in self.scene.get_all_node_items():
            item.update_from_node()  # 从节点数据更新节点显示状态

    # ── 连线/端口事件处理（连线模式/端口模式）──
    def _on_link_started(self, sender, **kwargs):
        """连线开始执行事件"""
        if self._link_belongs(sender):                                        # 如果连线属于绑定的工作流
            self.scene.on_link_state_changed(sender.link_id, "running")  # 更新连线的状态为运行中

    def _on_link_completed(self, sender, **kwargs):
        """连线执行完成事件"""
        if self._link_belongs(sender):                                          # 如果连线属于绑定的工作流
            self.scene.on_link_state_changed(sender.link_id, "completed")  # 更新连线的状态为已完成

    def _on_port_started(self, sender, **kwargs):
        """端口开始执行事件"""
        if self._port_belongs(sender):                                                        # 如果端口属于绑定的工作流
            self.scene.on_port_state_changed(sender.node_id, sender.port_id, "running")  # 更新端口的状态为运行中

    def _on_port_completed(self, sender, **kwargs):
        """端口执行完成事件"""
        if self._port_belongs(sender):  # 如果端口属于绑定的工作流
            self.scene.on_port_state_changed(sender.node_id, sender.port_id, "completed")  # 更新端口的状态为已完成
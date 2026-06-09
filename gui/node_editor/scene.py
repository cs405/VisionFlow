"""Diagram scene（图表场景）"""

import re
import inspect

from PyQt5.QtWidgets import (QGraphicsScene, QGraphicsItem, QMenu, QAction,
                              QGraphicsSceneMouseEvent)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QLineF, QMimeData, QTimer, QEvent
from PyQt5.QtGui import (QPainter, QPen, QColor, QBrush, QFont, QPainterPath,
                          QTransform, QPixmap)

from core.node_base import (NodeBase, Port, PortType, PortDock, LinkData,
                             VisionNodeData)
from core.workflow import WorkflowEngine
from core.events import EventType, event_system
from core.registry import node_registry
from core.commands import (CommandStack, AddNodeCommand, RemoveNodeCommand,
                            AddLinkCommand, RemoveLinkCommand, MoveNodeCommand,
                            BatchCommand)

from gui.node_editor.node_item import NodeItem, NodeState
from gui.node_editor.socket_item import SocketItem, PORT_DIAMETER
from gui.node_editor.edge_item import EdgeItem, EdgeState
from gui.node_editor.link_drawer import ILinkDrawer, BrokenLinkDrawer
from core.node_group import node_data_group_manager


# 场景边界矩形：从(-5000,-5000)到(5000,5000)，宽高各10000
SCENE_RECT = QRectF(-5000, -5000, 10000, 10000)

# 棋盘格背景的瓦片大小（像素）
CHECKER_TILE = 40
# 棋盘格背景的单元格大小（像素）
CHECKER_CELL = 20

from gui.theme import theme_manager


def _make_checker_brush(tile=CHECKER_TILE, cell=CHECKER_CELL,
                         base=None, alt=None):
    """创建棋盘格背景画刷"""
    # 如果未指定基础颜色，从主题获取画布棋盘格基础色
    if base is None:
        base = theme_manager.color("canvas_checker_base")
    # 如果未指定交替颜色，从主题获取画布棋盘格交替色
    if alt is None:
        alt = theme_manager.color("canvas_checker_alt")
    # 创建指定大小的QPixmap作为画刷图案
    pixmap = QPixmap(tile, tile)
    # 用基础色填充整个pixmap
    pixmap.fill(base)
    # 创建QPainter用于在pixmap上绘制
    p = QPainter(pixmap)
    # 绘制左上角单元格（从(0,0)开始，宽高为cell）
    p.fillRect(0, 0, cell, cell, alt)
    # 绘制右下角单元格（从(cell,cell)开始，宽高为cell）
    p.fillRect(cell, cell, cell, cell, alt)
    # 结束绘制
    p.end()
    # 返回使用该pixmap创建的画刷
    return QBrush(pixmap)


# ── 图层Z值常量 ──

class LayerZ:
    """Z值常量类，用于控制图形项的渲染层级（数值越大越靠前）"""

    # 连线层Z值：5（连线在节点下方渲染）
    LINK = 5

    # 节点层Z值：10（节点在连线上方渲染）
    NODE = 10

    # 动态层Z值：100（拖拽预览等动态元素在最上层渲染）
    DYNAMIC = 100


class DiagramScene(QGraphicsScene):
    """主图表场景类"""

    # 信号定义
    node_item_added = pyqtSignal(NodeItem)      # 节点项添加信号
    node_item_removed = pyqtSignal(str)         # 节点项移除信号
    edge_item_added = pyqtSignal(EdgeItem)      # 连线项添加信号
    edge_item_removed = pyqtSignal(str)         # 连线项移除信号
    node_selected = pyqtSignal(object)          # 节点选中信号
    node_deselected = pyqtSignal()              # 节点取消选中信号
    node_properties_requested = pyqtSignal(object)  # 请求节点属性信号
    node_help_requested = pyqtSignal(object)    # 请求节点帮助信号
    status_message = pyqtSignal(str)            # 状态消息信号

    def __init__(self, parent=None):
        """初始化图表场景"""
        # 调用父类QGraphicsScene的构造函数
        super().__init__(parent)
        # 设置场景边界矩形
        self.setSceneRect(SCENE_RECT)
        # 设置场景背景画刷为棋盘格
        self.setBackgroundBrush(_make_checker_brush())

        # 工作流引擎引用，初始为None
        self._workflow: WorkflowEngine | None = None
        # 节点字典：键为节点ID，值为节点图形项
        self._node_items: dict[str, NodeItem] = {}
        # 连线字典：键为连线ID，值为连线图形项
        self._edge_items: dict[str, EdgeItem] = {}
        # 是否显示网格线
        self._show_grid = True
        # 连线绘制策略（默认使用折线绘制器）
        self._link_drawer: ILinkDrawer = BrokenLinkDrawer()

        # ── 单个可复用的预览连线 ──
        # 动态连线（拖拽预览用），初始为None
        self._dynamic_edge: EdgeItem | None = None

        # ── 场景级别的拖拽状态（替代SocketItem级别的处理）──
        # 是否正在连线拖拽中
        self._connecting = False
        # 拖拽起始插座
        self._drag_from_socket: SocketItem | None = None
        # 拖拽目标位置
        self._drag_to_pos: QPointF = QPointF()

        # ── 待提交的连线 ──
        # 待提交的起始插座
        self._pending_from: SocketItem | None = None
        # 待提交的目标插座
        self._pending_to: SocketItem | None = None
        # 提交延迟定时器
        self._commit_timer = QTimer()
        # 设置定时器为单次触发
        self._commit_timer.setSingleShot(True)
        # 设置定时器间隔为0毫秒（立即执行）
        self._commit_timer.setInterval(0)
        # 连接定时器的timeout信号到_do_pending_commit方法
        self._commit_timer.timeout.connect(self._do_pending_commit)

        # ── 命令栈 ──
        # 命令栈对象，传入当前场景作为参数
        self._cmd_stack = CommandStack(scene=self)

        # ── 剪贴板 ──
        # 剪贴板数据列表
        self._clipboard: list[dict] = []

        # ── 节点序号计数器 ──
        self._node_counter: int = 0

        # 连接场景的选中项变化信号到_on_selection_changed方法
        self.selectionChanged.connect(self._on_selection_changed)

    # ═══════════════════════════════════════════════════════════════════════════
    # 场景级别的事件处理（event()重写）
    # ═══════════════════════════════════════════════════════════════════════════

    def event(self, e: QEvent) -> bool:
        """在场景级别拦截鼠标事件

        Qt注意：QGraphicsScene.event()在分发给图形项之前触发。
        当_connecting为True时，在此处拦截移动和释放事件，
        这样SocketItem就不需要拖拽逻辑了。
        """
        # 如果正在连线拖拽中
        if self._connecting:
            # 如果是场景鼠标移动事件
            if e.type() == QEvent.GraphicsSceneMouseMove:
                # 调用鼠标移动处理
                self._on_scene_mouse_move(e)
                # 返回True表示事件已处理
                return True
            # 如果是场景鼠标释放事件
            if e.type() == QEvent.GraphicsSceneMouseRelease:
                # 调用鼠标释放处理
                self._on_scene_mouse_release(e)
                # 返回True表示事件已处理
                return True
            # 如果是场景鼠标按下事件（拖拽过程中阻止新的按下）
            if e.type() == QEvent.GraphicsSceneMousePress:
                # 返回True表示事件已处理，阻止进一步分发
                return True
        # 其他情况调用父类的event方法
        return super().event(e)

    def _on_scene_mouse_move(self, event: QGraphicsSceneMouseEvent):
        """场景鼠标移动处理（Diagram_MouseMove等价）"""
        # 更新拖拽目标位置为当前鼠标场景坐标
        self._drag_to_pos = event.scenePos()
        # 如果动态连线存在
        if self._dynamic_edge is not None:
            # 更新动态连线的临时终点
            self._dynamic_edge.set_temp_end(self._drag_to_pos)

    def _on_scene_mouse_release(self, event: QGraphicsSceneMouseEvent):
        """场景鼠标释放处理（Diagram_MouseLeftButtonUp等价）"""
        # 如果不在连线拖拽中，直接返回
        if not self._connecting:
            return
        # 设置连线拖拽标志为False
        self._connecting = False
        # 获取当前鼠标场景坐标
        scene_pos = event.scenePos()
        # 查找鼠标位置下的插座（排除起始插座）
        target = self._find_socket_at(scene_pos, exclude=self._drag_from_socket)
        # 保存起始插座引用
        from_sock = self._drag_from_socket
        # 清空起始插座引用
        self._drag_from_socket = None

        # 立即隐藏预览连线
        if self._dynamic_edge is not None:
            self._dynamic_edge.hide_preview()

        # 如果没有找到目标插座或起始插座无效
        if not target or not from_sock:
            # 发出取消连线状态消息
            self.status_message.emit("连线已取消")
            return

        # 延迟创建连线（通过Dispatcher）
        self._pending_from = from_sock
        self._pending_to = target
        # 启动延迟定时器
        self._commit_timer.start()

    # ═══════════════════════════════════════════════════════════════════════════
    # 命令栈访问
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def link_drawer(self) -> ILinkDrawer:
        """获取连线绘制策略"""
        return self._link_drawer

    @link_drawer.setter
    def link_drawer(self, value: ILinkDrawer):
        """设置连线绘制策略"""
        # 保存新的绘制策略
        self._link_drawer = value
        # 刷新所有连线（RefreshLinkDrawer）
        for edge in self._edge_items.values():
            # 更新每条连线的绘制器
            edge._drawer = value
            # 重建路径
            edge._rebuild()
            # 触发重绘
            edge.update()

    @property
    def command_stack(self) -> CommandStack:
        """获取命令栈"""
        return self._cmd_stack

    # ═══════════════════════════════════════════════════════════════════════════
    # 网格背景
    # ═══════════════════════════════════════════════════════════════════════════

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """绘制场景背景（网格线）"""
        # 调用父类的drawBackground方法
        super().drawBackground(painter, rect)
        # 如果不显示网格，直接返回
        if not self._show_grid:
            return
        # 从主题获取网格颜色
        grid_color = theme_manager.color("canvas_grid")
        # 创建网格画笔：颜色，线宽0.5
        grid_pen = QPen(grid_color, 0.5)
        # 设置画笔
        painter.setPen(grid_pen)
        # 网格间距20像素
        gs = 20.0
        # 计算起始X坐标（对齐到网格）
        left = int(rect.left() / gs) * gs
        # 计算起始Y坐标（对齐到网格）
        top = int(rect.top() / gs) * gs
        # 当前X坐标
        x = left
        # 循环绘制垂直网格线
        while x < rect.right():
            # 绘制从顶部到底部的垂直线
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            # X坐标增加网格间距
            x += gs
        # 当前Y坐标
        y = top
        # 循环绘制水平网格线
        while y < rect.bottom():
            # 绘制从左到右的水平线
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            # Y坐标增加网格间距
            y += gs

    def toggle_grid(self):
        """切换网格显示/隐藏"""
        # 取反网格显示标志
        self._show_grid = not self._show_grid
        # 如果显示网格
        if self._show_grid:
            # 设置背景画刷为棋盘格（带网格线）
            self.setBackgroundBrush(_make_checker_brush())
        else:
            # 否则设置背景为纯色（仅基础色）
            self.setBackgroundBrush(QBrush(theme_manager.color("canvas_checker_base")))
        # 触发场景重绘
        self.update()

    # ═══════════════════════════════════════════════════════════════════════════
    # 节点管理
    # ═══════════════════════════════════════════════════════════════════════════

    def bind_workflow(self, workflow: WorkflowEngine):
        """绑定工作流引擎"""
        self._workflow = workflow

    def add_node_item(self, node_data: NodeBase, pos: QPointF = None,
                      group_name: str = "", sync_workflow: bool = True,
                      auto_link: bool = True) -> NodeItem:
        """添加节点项到场景"""
        # 创建节点图形项
        item = NodeItem(node_data, group_name)
        # 设置节点的Z序为节点层
        item.setZValue(LayerZ.NODE)
        # 如果指定了位置
        if pos is not None:
            # 设置节点位置
            item.setPos(pos)
        else:
            # 获取当前节点数量
            count = len(self._node_items)
            # 计算X坐标：每5个节点一行，间距170，居中偏移
            x = (count % 5) * 170 - 340
            # 计算Y坐标：每5个节点换行，间距70，向上偏移200
            y = (count // 5) * 70 - 200
            # 设置节点位置
            item.setPos(x, y)

        # 布局端口：将插座均匀分布在节点边缘
        self._do_layout_port(item)

        # 分配顺序索引
        self._node_counter += 1
        item._index = self._node_counter

        # 将节点项添加到场景
        self.addItem(item)
        # 将节点项存入字典（键为节点ID）
        self._node_items[node_data.node_id] = item
        # 连接节点的选中信号
        item.node_selected.connect(self._on_node_item_selected)
        # 连接节点的移动信号
        item.node_moved.connect(self._on_node_item_moved)

        # 如果需要同步到工作流且工作流存在
        if sync_workflow and self._workflow:
            # 将节点数据添加到工作流
            self._workflow.add_node(node_data)

        # 自动连接到上一个节点（排除第一个节点，仅用于用户添加操作）
        if auto_link and item._index > 1:
            # 调用自动连接方法
            self._auto_connect_to_previous(item)

        # 发布节点添加事件
        event_system.publish(EventType.NODE_ADDED, sender=self, node=node_data)
        # 发布图表变更事件
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        # 发出节点项添加信号
        self.node_item_added.emit(item)
        # 返回创建的节点项
        return item

    def _auto_connect_to_previous(self, current_item: NodeItem):
        """自动将当前节点连接到索引 = 当前索引 - 1 的节点"""
        # 查找索引为当前索引-1的节点项
        prev_item = next(
            (it for it in self._node_items.values()
             if it._index == current_item._index - 1),
            None
        )
        # 如果没有找到前一个节点，返回
        if prev_item is None:
            return

        # 获取前一个节点的第一个输出插座
        out_socket = prev_item.get_output_sockets()[0] if prev_item.get_output_sockets() else None
        # 获取当前节点的第一个输入插座
        in_socket = current_item.get_input_sockets()[0] if current_item.get_input_sockets() else None
        # 如果两个插座都存在
        if out_socket and in_socket:
            # 创建连线
            self.create_edge(out_socket, in_socket, sync_workflow=True)

    def remove_node_item(self, node_id: str, sync_workflow: bool = True):
        """移除节点项"""
        # 从字典中弹出节点项
        item = self._node_items.pop(node_id, None)
        # 如果节点项不存在，返回
        if item is None:
            return

        # 收集与该节点相关的输入插座和输出插座
        incoming_sockets: list[SocketItem] = []
        outgoing_sockets: list[SocketItem] = []
        # 收集需要移除的连线ID列表
        edges_to_remove: list[str] = []
        # 遍历所有连线
        for eid, edge in list(self._edge_items.items()):
            # 如果该节点是源节点
            if edge.from_socket and edge.from_socket.port.node_id == node_id:
                # 将目标插座添加到输出列表
                if edge.to_socket:
                    outgoing_sockets.append(edge.to_socket)
                # 记录需要移除的连线ID
                edges_to_remove.append(eid)
            # 如果该节点是目标节点
            elif edge.to_socket and edge.to_socket.port.node_id == node_id:
                # 将源插座添加到输入列表
                if edge.from_socket:
                    incoming_sockets.append(edge.from_socket)
                # 记录需要移除的连线ID
                edges_to_remove.append(eid)

        # 移除所有相关的连线
        for eid in edges_to_remove:
            self.remove_edge_item(eid, sync_workflow=sync_workflow)

        # 桥接：将每个输入源连接到每个输出目标（保持数据流）
        for in_sock in incoming_sockets:
            for out_sock in outgoing_sockets:
                self.create_edge(in_sock, out_sock, sync_workflow=sync_workflow)

        # 从场景中移除节点项
        self.removeItem(item)
        # 如果需要同步到工作流且工作流存在
        if sync_workflow and self._workflow:
            # 从工作流中移除节点
            self._workflow.remove_node(node_id)
        # 重新索引所有节点
        self._reindex_nodes()
        # 发布节点移除事件
        event_system.publish(EventType.NODE_REMOVED, sender=self, node=item.node_data)
        # 发布图表变更事件
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        # 发出节点项移除信号
        self.node_item_removed.emit(node_id)

    def _reindex_nodes(self):
        """删除节点后重新分配所有节点的顺序索引"""
        # 按当前索引排序所有节点项
        items = sorted(self._node_items.values(), key=lambda it: it._index)
        # 重置节点计数器
        self._node_counter = 0
        # 遍历排序后的节点项
        for it in items:
            # 计数器加1
            self._node_counter += 1
            # 重新分配索引
            it._index = self._node_counter
            # 触发重绘（更新左侧条显示的序号）
            it.update()

    def get_node_item(self, node_id: str) -> NodeItem | None:
        """根据节点ID获取节点项"""
        return self._node_items.get(node_id)

    def get_all_node_items(self) -> list[NodeItem]:
        """获取所有节点项"""
        return list(self._node_items.values())

    # ═══════════════════════════════════════════════════════════════════════════
    # 连线管理
    # ═══════════════════════════════════════════════════════════════════════════

    def create_edge(self, from_socket: SocketItem, to_socket: SocketItem,
                    sync_workflow: bool = True,
                    existing_link: LinkData | None = None) -> EdgeItem | None:
        """创建已提交的连线"""
        # 标准化方向：确保源是输出，目标是输入
        # 如果源是输入且目标是输出，交换位置
        if from_socket.port.is_input and to_socket.port.is_output:
            from_socket, to_socket = to_socket, from_socket
        # 如果源不是输出或目标不是输入，返回None（无效连线）
        if not from_socket.port.is_output or not to_socket.port.is_input:
            return None
        # 如果源节点和目标节点是同一个节点，返回None（禁止自连）
        if from_socket.port.node_id == to_socket.port.node_id:
            return None

        # 检查是否已存在相同的连线
        for edge in self._edge_items.values():
            # 如果相同的插座对已存在连线
            if (edge.from_socket is from_socket and edge.to_socket is to_socket) or (
                edge.link_data and
                edge.link_data.from_port_id == from_socket.port.port_id and
                edge.link_data.to_port_id == to_socket.port.port_id
            ):
                # 返回None，禁止重复连线
                return None

        # 在工作流中创建LinkData
        if sync_workflow and self._workflow:
            # 调用工作流的add_link方法添加连线
            link = self._workflow.add_link(
                from_socket.port.node_id,
                to_socket.port.node_id,
                from_port_id=from_socket.port.port_id,
                to_port_id=to_socket.port.port_id,
                link_id=existing_link.link_id if existing_link else None,
                text=existing_link.text if existing_link else "",
            )
            # 如果连线创建失败，返回None
            if link is None:
                return None
        else:
            # 使用已有的连线数据或创建新的LinkData
            link = existing_link or LinkData(
                from_node_id=from_socket.port.node_id,
                from_port_id=from_socket.port.port_id,
                to_node_id=to_socket.port.node_id,
                to_port_id=to_socket.port.port_id,
            )

        # 创建连线图形项，使用场景的默认绘制器
        edge = EdgeItem(from_socket, to_socket, link, drawer=self._link_drawer)
        # 设置连线的Z序为连线层
        edge.setZValue(LayerZ.LINK)

        # 先将连线添加到场景（避免Qt双重添加问题）
        self.addItem(edge)
        # 将连线存入字典（键为连线ID）
        self._edge_items[link.link_id] = edge

        # 在场景添加后，将连线注册到插座
        from_socket.add_edge(edge)
        to_socket.add_edge(edge)

        # 布局连线：计算起点和终点，重建路径
        self._do_layout_link(edge)

        # 连接连线的选中信号
        edge.edge_selected.connect(self._on_edge_selected)
        # 发出连线项添加信号
        self.edge_item_added.emit(edge)
        # 返回创建的连线项
        return edge

    def remove_edge_item(self, link_id: str, sync_workflow: bool = True):
        """移除连线项"""
        # 从字典中弹出连线项
        edge = self._edge_items.pop(link_id, None)
        # 如果连线项不存在，返回
        if edge is None:
            return
        # 断开连线（清理插座中的引用）
        edge.disconnect()
        # 从场景中移除连线项
        self.removeItem(edge)
        # 如果需要同步到工作流且工作流存在
        if sync_workflow and self._workflow:
            # 从工作流中移除连线
            self._workflow.remove_link(link_id)
        # 发布连线移除事件
        event_system.publish(EventType.LINK_REMOVED, sender=self, link=link_id)
        # 发布图表变更事件
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        # 发出连线项移除信号
        self.edge_item_removed.emit(link_id)

    def get_edge_item(self, link_id: str) -> EdgeItem | None:
        """根据连线ID获取连线项"""
        return self._edge_items.get(link_id)

    def get_all_edge_items(self) -> list[EdgeItem]:
        """获取所有连线项"""
        return list(self._edge_items.values())

    # ═══════════════════════════════════════════════════════════════════════════
    # 布局端口 / 布局连线
    # ═══════════════════════════════════════════════════════════════════════════

    def _do_layout_port(self, node_item: NodeItem):
        """将插座均匀分布在节点各边缘上"""
        # 按端口停靠位置分组插座
        ports_by_dock: dict[PortDock, list[SocketItem]] = {}
        # 遍历节点的所有插座
        for sock in node_item.sockets:
            # 将插座按停靠位置分组
            ports_by_dock.setdefault(sock.port.dock, []).append(sock)

        # 获取节点宽度和高度
        w, h = node_item._node_w, node_item._node_h

        # 遍历每个停靠位置上的插座列表
        for dock, sockets in ports_by_dock.items():
            # 插座数量
            n = len(sockets)
            # 如果没有插座，跳过
            if n == 0:
                continue
            # 遍历插座并计算位置
            for i, sock in enumerate(sockets):
                # 如果停靠在顶部
                if dock == PortDock.TOP:
                    # X坐标：从左侧边缘开始，按比例均匀分布
                    x = -w / 2 + w * (i + 1) / (n + 1)
                    # Y坐标：顶部边缘
                    y = -h / 2
                # 如果停靠在底部
                elif dock == PortDock.BOTTOM:
                    # X坐标：从左侧边缘开始，按比例均匀分布
                    x = -w / 2 + w * (i + 1) / (n + 1)
                    # Y坐标：底部边缘
                    y = h / 2
                # 如果停靠在左侧
                elif dock == PortDock.LEFT:
                    # X坐标：左侧边缘
                    x = -w / 2
                    # Y坐标：从顶部边缘开始，按比例均匀分布
                    y = -h / 2 + h * (i + 1) / (n + 1)
                # 其他情况（右侧）
                else:  # RIGHT
                    # X坐标：右侧边缘
                    x = w / 2
                    # Y坐标：从顶部边缘开始，按比例均匀分布
                    y = -h / 2 + h * (i + 1) / (n + 1)
                # 设置插座位置
                sock.setPos(QPointF(x, y))

    def _do_layout_link(self, edge: EdgeItem):
        """从端口位置计算起点和终点并重建路径"""
        # 如果源插座或目标插座为空，返回
        if edge.from_socket is None or edge.to_socket is None:
            return
        # 获取源插座的中心场景坐标作为起点
        start = edge.from_socket.get_center_scene_pos()
        # 获取目标插座的中心场景坐标作为终点
        end = edge.to_socket.get_center_scene_pos()
        # 保存起点
        edge._path_start = start
        # 保存终点
        edge._path_end = end
        # 重建连线的路径
        edge._rebuild()

    def _relayout_links_for_node(self, node_item: NodeItem):
        """更新与节点相关的所有连线"""
        # 获取节点ID
        node_id = node_item.node_data.node_id
        # 遍历所有连线
        for edge in self._edge_items.values():
            # 如果连线以该节点为源或目标
            if (edge.from_socket and edge.from_socket.port.node_id == node_id) or \
               (edge.to_socket and edge.to_socket.port.node_id == node_id):
                # 重新布局该连线
                self._do_layout_link(edge)
                # 触发重绘
                edge.update()
        # 同时重新布局移动节点的端口
        self._do_layout_port(node_item)

    # ═══════════════════════════════════════════════════════════════════════════
    # 拖拽创建连线（使用可复用的单例预览连线）
    # ═══════════════════════════════════════════════════════════════════════════

    def _init_dynamic_edge(self):
        """延迟创建单个可复用的预览连线"""
        # 如果动态连线已经存在，直接返回
        if self._dynamic_edge is not None:
            return
        # 创建新的EdgeItem作为预览连线
        self._dynamic_edge = EdgeItem()
        # 设置Z序为动态层（最高）
        self._dynamic_edge.setZValue(LayerZ.DYNAMIC)
        # 设置为不可见
        self._dynamic_edge.setVisible(False)
        # 禁用可选中的标志
        self._dynamic_edge.setFlag(QGraphicsItem.ItemIsSelectable, False)
        # 禁用悬停事件
        self._dynamic_edge.setAcceptHoverEvents(False)
        # 添加到场景
        self.addItem(self._dynamic_edge)

    def start_edge_drag(self, from_socket: SocketItem):
        """开始连线拖拽（PortLinkBehavior.Init → InitDynamic）"""
        # 只有输出端口或双向端口才能开始连接
        if not from_socket.port.is_output:
            return

        # 初始化动态连线
        self._init_dynamic_edge()
        # 显示预览连线，传入源插座
        self._dynamic_edge.show_preview(from_socket)
        # 记录拖拽起始插座
        self._drag_from_socket = from_socket
        # 初始化拖拽目标位置为源插座位置
        self._drag_to_pos = from_socket.get_center_scene_pos()
        # 设置正在连线标志为True
        self._connecting = True

    def update_edge_drag(self, sock, scene_pos: QPointF):
        """更新连线拖拽位置（保留用于SocketItem信号兼容）"""
        # 如果不在连线拖拽中，返回
        if not self._connecting:
            return
        # 更新拖拽目标位置
        self._drag_to_pos = scene_pos
        # 如果动态连线存在，更新临时终点
        if self._dynamic_edge is not None:
            self._dynamic_edge.set_temp_end(scene_pos)

    def end_edge_drag(self, sock, scene_pos: QPointF):
        """结束连线拖拽（保留用于SocketItem信号兼容）"""
        # 如果不在连线拖拽中，返回
        if not self._connecting:
            return
        # 设置正在连线标志为False
        self._connecting = False
        # 查找鼠标位置下的插座（排除源插座）
        target = self._find_socket_at(scene_pos, exclude=sock)
        # 保存起始插座引用
        from_sock = self._drag_from_socket
        # 清空起始插座引用
        self._drag_from_socket = None
        # 隐藏预览连线
        if self._dynamic_edge is not None:
            self._dynamic_edge.hide_preview()
        # 如果没有找到目标插座或起始插座无效
        if not target or not from_sock:
            # 发出取消连线状态消息
            self.status_message.emit("连线已取消")
            return
        # 记录待提交的连线
        self._pending_from = from_sock
        self._pending_to = target
        # 启动延迟定时器
        self._commit_timer.start()

    def _do_pending_commit(self):
        """延迟创建连线的回调（Dispatcher.BeginInvoke）"""
        # 获取待提交的起始插座和目标插座
        fs = self._pending_from
        ts = self._pending_to
        # 清空待提交引用
        self._pending_from = None
        self._pending_to = None
        # 如果两个插座都有效
        if fs is not None and ts is not None:
            # 提交连线
            self._commit_edge(fs, ts)

    def _commit_edge(self, from_socket: SocketItem, to_socket: SocketItem):
        """延迟创建连线"""
        try:
            # 创建添加连线命令
            cmd = AddLinkCommand(self, from_socket, to_socket)
            # 执行命令
            result = self._cmd_stack.execute(cmd)
            # 如果执行成功
            if result:
                # 发出成功消息
                self.status_message.emit("连线已创建")
            else:
                # 发出失败消息
                self.status_message.emit("连线创建失败")
        except Exception as e:
            # 发生异常时发出错误消息
            self.status_message.emit(f"连线异常: {e}")

    def _find_socket_at(self, scene_pos: QPointF, exclude: SocketItem = None) -> SocketItem | None:
        """在场景坐标处进行插座命中测试"""
        # 获取排除插座的节点ID（如果存在）
        exclude_node_id = exclude.port.node_id if exclude else None
        # 遍历所有节点项
        for node_item in self._node_items.values():
            # 获取鼠标位置下的插座
            socket = node_item.get_socket_at(scene_pos)
            # 如果没有找到插座或插座就是排除的插座，跳过
            if socket is None or socket is exclude:
                continue
            # 如果插座所属节点是被排除的节点，跳过（禁止自连）
            if socket.port.node_id == exclude_node_id:
                continue
            # 返回找到的插座
            return socket
        # 没有找到返回None
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # 选中项管理
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_node_item_selected(self, node_data: NodeBase):
        """节点项被选中时的处理"""
        # 发出节点选中信号
        self.node_selected.emit(node_data)
        # 发布节点选中事件
        event_system.publish(EventType.NODE_SELECTED, sender=node_data, node=node_data)

    def _on_node_item_moved(self, node_data: NodeBase):
        """节点移动时的处理"""
        # 获取节点对应的图形项
        item = self._node_items.get(node_data.node_id)
        # 如果图形项存在
        if item:
            # 重新布局与该节点相关的所有连线
            self._relayout_links_for_node(item)
        # 发布节点属性变更事件
        event_system.publish(EventType.NODE_PROPERTY_CHANGED, sender=node_data)

    def _on_edge_selected(self, edge: EdgeItem):
        """连线项被选中时的处理"""
        # 目前不需要额外处理
        pass

    def _on_selection_changed(self):
        """场景选中项变化时的处理"""
        # 如果没有选中的项
        if not self.selectedItems():
            # 发出节点取消选中信号
            self.node_deselected.emit()
            # 发布节点取消选中事件
            event_system.publish(EventType.NODE_DESELECTED, sender=self)

    def get_selected_node_data(self) -> NodeBase | None:
        """获取当前选中的节点数据"""
        # 遍历选中的项
        for item in self.selectedItems():
            # 如果是节点项
            if isinstance(item, NodeItem):
                # 返回节点数据
                return item.node_data
        # 没有选中节点返回None
        return None

    def get_selected_node_items(self) -> list[NodeItem]:
        """获取所有选中的节点项"""
        # 返回选中的项中的节点项列表
        return [it for it in self.selectedItems() if isinstance(it, NodeItem)]

    def delete_selected(self):
        """删除所有选中的项"""
        # 获取所有选中的项
        items = self.selectedItems()
        # 如果没有选中项，返回
        if not items:
            return
        # 创建批量命令
        batch = BatchCommand(description="删除选中项")
        # 遍历选中的项
        for item in items:
            # 如果是节点项
            if isinstance(item, NodeItem):
                # 添加删除节点命令
                batch.add(RemoveNodeCommand(self, item.node_data.node_id))
            # 如果是连线项
            elif isinstance(item, EdgeItem):
                # 如果连线数据存在
                if item.link_data:
                    # 添加删除连线命令
                    batch.add(RemoveLinkCommand(self, item.link_data.link_id))
        # 执行批量命令
        self._cmd_stack.execute(batch)

    # ═══════════════════════════════════════════════════════════════════════════
    # 复制 / 粘贴
    # ═══════════════════════════════════════════════════════════════════════════

    def copy_selected(self):
        """复制选中的节点"""
        # 清空剪贴板
        self._clipboard.clear()
        # 遍历选中的项
        for item in self.selectedItems():
            # 如果是节点项
            if isinstance(item, NodeItem):
                # 获取节点数据
                nd = item.node_data
                # 获取节点位置
                pos = item.pos()
                # 获取端口的字典数据
                ports_data = [p.to_dict() for p in nd.ports]
                # 将节点信息添加到剪贴板
                self._clipboard.append({
                    "type": nd.__class__.__name__,  # 节点类型名称
                    "data": nd.to_dict() if hasattr(nd, 'to_dict') else {},  # 节点数据
                    "x": pos.x(),  # X坐标
                    "y": pos.y(),  # Y坐标
                    "ports": ports_data,  # 端口数据
                })
        # 发出复制完成消息
        self.status_message.emit(f"已复制 {len(self._clipboard)} 个节点")

    def paste(self):
        """粘贴节点"""
        # 如果剪贴板为空，返回
        if not self._clipboard:
            return
        # 创建批量命令
        batch = BatchCommand(description="粘贴节点")
        # 计算偏移量（避免覆盖原位置）
        offset = 30 + 15 * len(self._clipboard)
        # 遍历剪贴板中的节点信息
        for clip in self._clipboard:
            # 根据类型名称创建节点实例
            node = node_registry.create(clip["type"])
            # 如果节点创建成功
            if node:
                # 如果剪贴板中有节点数据，恢复节点状态
                if "data" in clip and clip["data"]:
                    if hasattr(node, 'from_dict'):
                        node.from_dict(clip["data"])
                # 计算新位置（原位置加偏移量）
                pos = QPointF(clip.get("x", 0) + offset, clip.get("y", 0) + offset)
                # 添加添加节点命令到批量命令
                batch.add(AddNodeCommand(self, node, (pos.x(), pos.y())))
        # 执行批量命令
        self._cmd_stack.execute(batch)
        # 发出粘贴完成消息
        self.status_message.emit(f"已粘贴 {len(self._clipboard)} 个节点")
        # 清空剪贴板
        self._clipboard.clear()

    # ═══════════════════════════════════════════════════════════════════════════
    # 对齐
    # ═══════════════════════════════════════════════════════════════════════════

    def align_selected(self, mode: str):
        """对齐选中的节点"""
        # 获取选中的节点项
        nodes = self.get_selected_node_items()
        # 如果选中节点少于2个，返回
        if len(nodes) < 2:
            return
        # 创建批量命令
        batch = BatchCommand(description=f"对齐 ({mode})")
        # 左对齐
        if mode == "left":
            # 计算最小的左边缘X坐标（节点X坐标减去宽度的一半）
            x_min = min(n.pos().x() - n._node_w / 2 for n in nodes)
            # 遍历所有选中节点
            for n in nodes:
                # 获取原位置
                old = n.pos()
                # 计算新位置：左边缘对齐到x_min，Y坐标不变
                new = QPointF(x_min + n._node_w / 2, old.y())
                # 添加移动节点命令
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        # 右对齐
        elif mode == "right":
            # 计算最大的右边缘X坐标（节点X坐标加上宽度的一半）
            x_max = max(n.pos().x() + n._node_w / 2 for n in nodes)
            # 遍历所有选中节点
            for n in nodes:
                # 获取原位置
                old = n.pos()
                # 计算新位置：右边缘对齐到x_max，Y坐标不变
                new = QPointF(x_max - n._node_w / 2, old.y())
                # 添加移动节点命令
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        # 顶部对齐
        elif mode == "top":
            # 计算最小的顶部边缘Y坐标（节点Y坐标减去高度的一半）
            y_min = min(n.pos().y() - n._node_h / 2 for n in nodes)
            # 遍历所有选中节点
            for n in nodes:
                # 获取原位置
                old = n.pos()
                # 计算新位置：顶部边缘对齐到y_min，X坐标不变
                new = QPointF(old.x(), y_min + n._node_h / 2)
                # 添加移动节点命令
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        # 底部对齐
        elif mode == "bottom":
            # 计算最大的底部边缘Y坐标（节点Y坐标加上高度的一半）
            y_max = max(n.pos().y() + n._node_h / 2 for n in nodes)
            # 遍历所有选中节点
            for n in nodes:
                # 获取原位置
                old = n.pos()
                # 计算新位置：底部边缘对齐到y_max，X坐标不变
                new = QPointF(old.x(), y_max - n._node_h / 2)
                # 添加移动节点命令
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        # 水平居中（Y坐标对齐到平均值）
        elif mode == "center_h":
            # 计算所有节点Y坐标的平均值
            avg_y = sum(n.pos().y() for n in nodes) / len(nodes)
            # 遍历所有选中节点
            for n in nodes:
                # 获取原位置
                old = n.pos()
                # 计算新位置：X坐标不变，Y坐标对齐到平均值
                new = QPointF(old.x(), avg_y)
                # 添加移动节点命令
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        # 垂直居中（X坐标对齐到平均值）
        elif mode == "center_v":
            # 计算所有节点X坐标的平均值
            avg_x = sum(n.pos().x() for n in nodes) / len(nodes)
            # 遍历所有选中节点
            for n in nodes:
                # 获取原位置
                old = n.pos()
                # 计算新位置：X坐标对齐到平均值，Y坐标不变
                new = QPointF(avg_x, old.y())
                # 添加移动节点命令
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        # 执行批量命令
        self._cmd_stack.execute(batch)

    def distribute_selected(self, mode: str):
        """均匀分布选中的节点"""
        # 获取选中的节点项
        nodes = self.get_selected_node_items()
        # 如果选中节点少于3个，返回（至少需要3个才能分布）
        if len(nodes) < 3:
            return
        # 创建批量命令
        batch = BatchCommand(description=f"分布 ({mode})")
        # 水平分布
        if mode == "horizontal":
            # 按X坐标排序
            nodes.sort(key=lambda n: n.pos().x())
            # 获取最小X坐标
            x_min = nodes[0].pos().x()
            # 获取最大X坐标
            x_max = nodes[-1].pos().x()
            # 计算均匀分布间距
            spacing = (x_max - x_min) / (len(nodes) - 1) if len(nodes) > 1 else 0
            # 遍历所有节点
            for i, n in enumerate(nodes):
                # 获取原位置
                old = n.pos()
                # 计算新位置：均匀分布的X坐标，Y坐标不变
                new = QPointF(x_min + i * spacing, old.y())
                # 添加移动节点命令
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        # 垂直分布
        elif mode == "vertical":
            # 按Y坐标排序
            nodes.sort(key=lambda n: n.pos().y())
            # 获取最小Y坐标
            y_min = nodes[0].pos().y()
            # 获取最大Y坐标
            y_max = nodes[-1].pos().y()
            # 计算均匀分布间距
            spacing = (y_max - y_min) / (len(nodes) - 1) if len(nodes) > 1 else 0
            # 遍历所有节点
            for i, n in enumerate(nodes):
                # 获取原位置
                old = n.pos()
                # 计算新位置：X坐标不变，均匀分布的Y坐标
                new = QPointF(old.x(), y_min + i * spacing)
                # 添加移动节点命令
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        # 执行批量命令
        self._cmd_stack.execute(batch)

    # ═══════════════════════════════════════════════════════════════════════════
    # 撤销 / 重做
    # ═══════════════════════════════════════════════════════════════════════════

    def undo(self):
        """撤销上一步操作"""
        # 如果命令栈撤销成功
        if self._cmd_stack.undo():
            # 发出撤销成功消息
            self.status_message.emit(f"撤销: {self._cmd_stack.undo_description}")

    def redo(self):
        """重做被撤销的操作"""
        # 如果命令栈重做成功
        if self._cmd_stack.redo():
            # 发出重做成功消息
            self.status_message.emit(f"重做: {self._cmd_stack.redo_description}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 工作流状态反馈
    # ═══════════════════════════════════════════════════════════════════════════

    def on_workflow_state_changed(self, node_id: str, state: str):
        """更新节点及其连接的连线以反映执行状态"""
        # 获取节点项
        item = self._node_items.get(node_id)
        # 如果节点项不存在，返回
        if item is None:
            return
        # 状态映射
        state_map = {
            "running": NodeState.RUNNING,      # 运行中
            "completed": NodeState.COMPLETED,  # 已完成
            "error": NodeState.ERROR,          # 错误
            "idle": NodeState.IDLE,            # 空闲
        }
        # 获取节点状态
        ns = state_map.get(state, NodeState.IDLE)
        # 设置节点状态
        item.set_state(ns)

        # 连线状态映射
        edge_state_map = {
            "running": EdgeState.RUNNING,   # 运行中
            "completed": EdgeState.SUCCESS, # 成功
            "error": EdgeState.ERROR,       # 错误
            "idle": EdgeState.NORMAL,       # 正常
        }
        # 获取连线状态
        es = edge_state_map.get(state, EdgeState.NORMAL)
        # 遍历所有连线
        for edge in self._edge_items.values():
            # 如果连线与该节点相关（作为源或目标）
            if (edge.from_socket and edge.from_socket.port.node_id == node_id) or \
               (edge.to_socket and edge.to_socket.port.node_id == node_id):
                # 设置连线状态
                edge.set_state(es)

    def on_link_state_changed(self, link_id: str, state: str):
        """更新单个连线的视觉状态"""
        # 获取连线项
        edge = self._edge_items.get(link_id)
        # 如果连线项不存在，返回
        if edge is None:
            return
        # 连线状态映射
        state_map = {
            "running": EdgeState.RUNNING,   # 运行中
            "completed": EdgeState.SUCCESS, # 成功
            "error": EdgeState.ERROR,       # 错误
        }
        # 获取连线状态
        es = state_map.get(state, EdgeState.NORMAL)
        # 设置连线状态
        edge.set_state(es)

    def on_port_state_changed(self, node_id: str, port_id: str, state: str):
        """更新插座的视觉状态"""
        # 获取节点项
        node_item = self._node_items.get(node_id)
        # 如果节点项不存在，返回
        if node_item is None:
            return
        # 遍历节点的所有插座
        for sock in node_item.sockets:
            # 如果找到匹配的端口ID
            if sock.port.port_id == port_id:
                # 如果状态为运行中
                if state == "running":
                    # 设置高亮
                    sock.set_highlight(True)
                else:
                    # 取消高亮
                    sock.set_highlight(False)
                # 找到后退出循环
                break

    # ═══════════════════════════════════════════════════════════════════════════
    # 上下文菜单
    # ═══════════════════════════════════════════════════════════════════════════

    def context_menu(self, pos: QPointF) -> QMenu | None:
        """获取右键上下文菜单"""
        # 获取鼠标位置下的图形项
        item = self.itemAt(pos, QTransform())
        # 创建菜单对象
        menu = QMenu()

        # 如果点击的是节点项
        if isinstance(item, NodeItem):
            # 暂时不处理，返回None
            return None

        # 如果点击的是连线项
        elif isinstance(item, EdgeItem):
            # 暂时不处理，返回None
            return None

        # 如果点击的是空白区域
        else:
            # 获取鼠标位置坐标
            px, py = pos.x(), pos.y()
            # 创建"添加节点"子菜单
            add_menu = menu.addMenu("添加节点")
            # 构建节点类型菜单
            self._build_node_type_menu(add_menu, menu, px, py)
            # 返回菜单
            return menu

    def _run_single_node(self, node_data: NodeBase):
        """运行单个节点"""
        # 如果工作流存在且节点是视觉节点
        if self._workflow and isinstance(node_data, VisionNodeData):
            # 更新当前调用（单步执行）
            node_data.update_invoke_current()
            # 获取节点对应的图形项
            item = self._node_items.get(node_data.node_id)
            # 如果图形项存在
            if item:
                # 从节点数据更新节点状态
                item.update_from_node()
            # 发出状态消息
            self.status_message.emit(f"已执行: {node_data.name}")

    def _build_node_type_menu(self, parent_menu: QMenu, root_menu: QMenu,
                               px: float, py: float):
        """从已注册的分组构建分层节点类型菜单"""
        # 收集所有可实例化的节点类型（非抽象类）
        all_instantiable = {
            t.__name__: t
            for t in node_registry._nodes.values()
            if not inspect.isabstract(t)
        }

        def _node_label(node_type: type) -> str:
            """获取节点显示名称"""
            try:
                # 尝试实例化获取name属性
                inst = node_type()
                name = inst.name or ''
                # 如果名称有效且不是类名本身且长度小于30
                if name and name != node_type.__name__ and len(name) < 30:
                    return name
            except Exception:
                pass
            # 获取类名
            cls_name = node_type.__name__
            # 将驼峰命名转换为带空格的名称
            spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', cls_name)
            spaced = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', spaced)
            return spaced

        # 已使用的节点类型集合（避免重复）
        used: set[str] = set()
        # 遍历所有分组
        for group in node_data_group_manager.get_all_groups():
            # 该分组下的节点类型列表
            group_types: list[type] = []
            # 遍历分组中的节点类型
            for nt in group.node_types:
                # 如果节点类型可实例化且未被使用
                if nt.__name__ in all_instantiable and nt.__name__ not in used:
                    group_types.append(nt)
                    used.add(nt.__name__)
            # 如果分组没有节点类型，跳过
            if not group_types:
                continue
            # 创建子菜单
            sub_menu = parent_menu.addMenu(group.name)
            # 遍历分组中的节点类型
            for node_type in group_types:
                # 获取节点显示名称
                label = _node_label(node_type)
                # 创建菜单动作
                action = QAction(label, root_menu)
                # 连接动作的triggered信号，lambda捕获节点类型和坐标
                action.triggered.connect(
                    lambda checked, nt=node_type, x=px, y=py:
                        self._cmd_stack.execute(AddNodeCommand(self, nt(), (x, y))))
                # 将动作添加到子菜单
                sub_menu.addAction(action)
        # 处理未分组的节点
        ungrouped = [t for n, t in all_instantiable.items() if n not in used]
        # 如果有未分组的节点
        if ungrouped:
            # 创建"其他"子菜单
            sub_menu = parent_menu.addMenu("其他")
            # 遍历未分组的节点类型
            for node_type in ungrouped:
                # 获取节点显示名称
                label = _node_label(node_type)
                # 创建菜单动作
                action = QAction(label, root_menu)
                # 连接动作的triggered信号
                action.triggered.connect(
                    lambda checked, nt=node_type, x=px, y=py:
                        self._cmd_stack.execute(AddNodeCommand(self, nt(), (x, y))))
                # 将动作添加到子菜单
                sub_menu.addAction(action)

    # ═══════════════════════════════════════════════════════════════════════════
    # 序列化
    # ═══════════════════════════════════════════════════════════════════════════

    def clear_all(self, sync_workflow: bool = True):
        """清空场景中的所有内容"""
        # 遍历所有节点ID的副本
        for node_id in list(self._node_items.keys()):
            # 移除节点项
            self.remove_node_item(node_id, sync_workflow=sync_workflow)
        # 清空节点字典
        self._node_items.clear()
        # 清空连线字典
        self._edge_items.clear()
        # 清空命令栈
        self._cmd_stack.clear()
        # 重置节点计数器
        self._node_counter = 0

    def load_from_workflow(self, workflow: WorkflowEngine):
        """从工作流加载场景"""
        # 清空场景（不同步工作流）
        self.clear_all(sync_workflow=False)
        # 保存工作流引用
        self._workflow = workflow

        # 遍历工作流中的所有节点
        for node in workflow.get_all_nodes():
            # 获取节点位置X坐标
            x = getattr(node, '_pos_x', 0.0) or 0.0
            # 获取节点位置Y坐标
            y = getattr(node, '_pos_y', 0.0) or 0.0
            # 如果有位置坐标则使用，否则None
            pos = QPointF(x, y) if (x or y) else None
            # 添加节点项（不同步工作流，不自动连线）
            item = self.add_node_item(node, pos, sync_workflow=False, auto_link=False)
            # 如果节点项创建成功
            if item:
                # 更新节点数据的位置坐标
                node._pos_x = item.pos().x()
                node._pos_y = item.pos().y()

        # 遍历工作流中的所有连线
        for link in workflow.get_all_links():
            # 获取源节点项
            from_item = self.get_node_item(link.from_node_id)
            # 获取目标节点项
            to_item = self.get_node_item(link.to_node_id)
            # 如果两个节点都存在
            if from_item and to_item:
                # 获取源插座
                fs = from_item.get_socket_by_port_id(link.from_port_id)
                # 获取目标插座
                ts = to_item.get_socket_by_port_id(link.to_port_id)
                # 如果两个插座都存在
                if fs and ts:
                    # 创建连线（不同步工作流，使用已有连线数据）
                    self.create_edge(fs, ts, sync_workflow=False, existing_link=link)

    def save_to_workflow(self, workflow: WorkflowEngine):
        """将场景保存到工作流"""
        # 遍历所有节点，保存位置
        for node_id, item in self._node_items.items():
            # 获取节点位置
            pos = item.pos()
            # 获取节点数据
            nd = item.node_data
            # 保存X坐标
            nd._pos_x = pos.x()
            # 保存Y坐标
            nd._pos_y = pos.y()
        # 清空工作流的连线列表
        workflow._links = []
        # 遍历所有连线
        for edge in self._edge_items.values():
            # 如果连线数据存在
            if edge.link_data:
                # 将连线数据添加到工作流
                workflow._links.append(edge.link_data)
"""节点图形项"""
from enum import Enum

from PyQt5.QtWidgets import QGraphicsItem, QGraphicsObject
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainter, QPainterPath,
                         QFont, QFontMetrics)

from core.data_packet import FlowableResultState
from core.node_base import NodeBase, PortDock
from core.node_vision import VisionNodeData
from core.node_selectable import SrcFilesVisionNodeData
from gui.node_editor.socket_item import SocketItem, PORT_DIAMETER
from gui.font_icons import FontIcons, icon_font
from core.constants import (NODE_MIN_HEIGHT, NODE_CORNER_RADIUS,
                            BAR_WIDTH, ICON_SIZE, TEXT_FONT_SIZE)
from core.constants import get_group_color

# ═══════════════════════════════════════════════════════════════════════════
# 枚举定义
# ═══════════════════════════════════════════════════════════════════════════
class NodeState(Enum):
    """节点状态枚举"""
    IDLE = "idle"           # 空闲状态
    RUNNING = "running"     # 运行中
    COMPLETED = "completed" # 已完成
    ERROR = "error"         # 错误状态
    DISABLED = "disabled"   # 禁用状态


class NodeTemplate(Enum):
    """节点模板类型枚举"""
    DEFAULT = "default"     # 默认样式
    SOURCE = "source"       # 源节点样式（数据源）
    CONDITION = "condition" # 条件节点样式（菱形）
    OUTPUT = "output"       # 输出节点样式


# 节点类型到图标的映射字典
_NODE_ICONS = {
    "SrcFilesVisionNodeData": FontIcons.Camera,  # 源文件视觉节点 -> 相机图标
    "ImageFileSource": FontIcons.Camera,         # 图像文件源节点 -> 相机图标
    "CameraCapture": FontIcons.Camera,           # 相机采集节点 -> 相机图标
    "VideoCapture": FontIcons.Video,             # 视频采集节点 -> 视频图标
    "CvtColor": FontIcons.Color,                 # 颜色转换节点 -> 颜色图标
    "GaussianBlur": FontIcons.InPrivate,         # 高斯模糊节点 -> 隐私图标（表示滤镜/模糊）
    "MedianBlur": FontIcons.InPrivate,           # 中值模糊节点 -> 隐私图标
    "BilateralFilter": FontIcons.InPrivate,      # 双边滤波节点 -> 隐私图标
    "DetailEnhance": FontIcons.InPrivate,        # 细节增强节点 -> 隐私图标
    "PencilSketch": FontIcons.InPrivate,         # 铅笔素描节点 -> 隐私图标
    "Threshold": FontIcons.InPrivate,            # 阈值处理节点 -> 隐私图标
    "ROINodeData": FontIcons.Annotation,         # ROI节点 -> 标注图标
    "Morphology": FontIcons.HomeGroup,           # 形态学处理节点 -> 主页组图标
    "ErodeNode": FontIcons.HomeGroup,            # 腐蚀节点 -> 主页组图标
    "DilateNode": FontIcons.HomeGroup,           # 膨胀节点 -> 主页组图标
    "ConditionNodeData": FontIcons.Dial6,        # 条件节点 -> 拨号6图标（表示逻辑分支）
    "WaitAllParallelNodeData": FontIcons.Dial6,  # 并行等待节点 -> 拨号6图标
    "TemplateMatching": FontIcons.GotoToday,     # 模板匹配节点 -> 今日跳转图标
    "Detector": FontIcons.LargeErase,            # 检测器节点 -> 大擦除图标
    "Feature": FontIcons.GenericScan,            # 特征提取节点 -> 通用扫描图标
    "Modbus": FontIcons.NarratorForward,         # Modbus通信节点 -> 讲述人前进图标（表示网络通信）
    "TcpClient": FontIcons.NarratorForward,      # TCP客户端节点 -> 讲述人前进图标
    "Output": FontIcons.Ethernet,                # 输出节点 -> 以太网图标
    "Onnx": FontIcons.CommandPrompt,             # ONNX模型节点 -> 命令提示符图标
    "Other": FontIcons.More,                     # 其他节点 -> 更多图标
}


# 初始插座偏移量（后续由 scene._do_layout_port() 精确调整）
_PORT_OFFSET_INIT = {
    PortDock.TOP: lambda w, h: QPointF(0, -h / 2),      # 顶部端口：X坐标为0（水平居中），Y坐标向上偏移半个高度
    PortDock.BOTTOM: lambda w, h: QPointF(0, h / 2),  # 底部端口：X坐标为0（水平居中），Y坐标向下偏移半个高度
    PortDock.LEFT: lambda w, h: QPointF(-w / 2, 0),     # 左侧端口：X坐标向左偏移半个宽度，Y坐标为0（垂直居中）
    PortDock.RIGHT: lambda w, h: QPointF(w / 2, 0),   # 右侧端口：X坐标向右偏移半个宽度，Y坐标为0（垂直居中）
}


# ═══════════════════════════════════════════════════════════════════════════
# NodeItem（节点图形项）
# ═══════════════════════════════════════════════════════════════════════════
class NodeItem(QGraphicsObject):
    """画布上的视觉节点"""
    # 信号定义
    node_selected = pyqtSignal(object)        # 节点被选中时发出的信号，携带节点数据对象
    node_moved = pyqtSignal(object)           # 节点被移动时发出的信号，携带节点数据对象
    node_move_finished = pyqtSignal(object)   # 节点移动完成时发出的信号，携带节点数据对象（供场景做吸附矫正）
    node_double_clicked = pyqtSignal(object)  # 节点被双击时发出的信号，携带节点数据对象

    def __init__(self, node_data: NodeBase, group_name: str = "", parent=None):
        """
        初始化节点图形项
        参数：
            node_data: 节点数据对象
            group_name: 分组名称（用于确定颜色）
            parent: 父对象
        """
        super().__init__(parent)
        self.node_data = node_data                              # 保存节点数据对象
        self._group_name = group_name                           # 保存分组名称
        self._hovered = False                                   # 初始化鼠标悬停标志为False
        self._state = NodeState.IDLE                            # 初始化节点状态为空闲状态
        self._template = self._detect_template()                # 检测并保存节点模板类型
        self._flag_color = QColor(get_group_color(group_name))  # 根据分组名称获取分组颜色，创建QColor对象
        self._icon_text = _resolve_node_icon(node_data)         # 解析节点对应的图标字符
        self._pulse_val = 0.0                                   # 初始化脉冲动画值为0.0
        self._pulse_timer: QTimer | None = None                 # 初始化脉冲动画定时器为None
        self._index = 0                                         # 初始化节点索引序号为0（由DiagramScene管理）
        self._node_w, self._node_h = self._compute_size()       # 计算节点自适应尺寸，返回宽度和高度
        self._rect = QRectF(                                    # 创建节点矩形区域，中心点位于(0,0)
            -self._node_w / 2,                                  # 矩形左上角X坐标：负的宽度的一半
            -self._node_h / 2,                                  # 矩形左上角Y坐标：负的高度的一半
            self._node_w,                                       # 矩形宽度
            self._node_h,                                       # 矩形高度
        )

        # 设置图形项标志
        self.setFlag(QGraphicsItem.ItemIsMovable, True)             # 设置节点可移动
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)          # 设置节点可选中
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)  # 设置节点在位置/几何变化时发送通知
        self.setAcceptHoverEvents(True)                                     # 设置接受鼠标悬停事件
        self.setZValue(10)                                                  # 设置Z序为10（值越大显示越靠前）
        # 创建插座列表
        self.sockets: list[SocketItem] = []
        self._create_sockets()                                              # 调用私有方法创建所有插座

    # ── 模板类型检测 ──────────────────────────────────────────────────
    def _detect_template(self) -> NodeTemplate:
        """检测节点模板类型"""
        nd = self.node_data                         # 获取节点数据的本地引用，方便使用
        if isinstance(nd, SrcFilesVisionNodeData):  # 判断是否为源文件视觉节点类型
            return NodeTemplate.SOURCE

        declared = getattr(nd, '__template__', None)  # 判断节点是否显式声明模板类型（支持字符串如 "condition" 或 NodeTemplate 枚举值）
        if declared is not None:
            if isinstance(declared, NodeTemplate):
                return declared
            try:
                return NodeTemplate(declared)
            except ValueError:
                pass

        cls_name = nd.__class__.__name__.lower()                 # 获取节点类名并转换为小写
        if cls_name.startswith("show") or "output" in cls_name:  # 判断类名是否以"show"开头或包含"output"
            return NodeTemplate.OUTPUT

        return NodeTemplate.DEFAULT

    # ── 自适应尺寸计算 ─────────────────────────────────────────────────────
    def _compute_size(self) -> tuple[float, float]:
        """计算节点尺寸（统一宽度，高度根据模板类型自适应）"""
        w = 160.0
        title = self.node_data.title or self.node_data.name
        font = self._title_font()
        fm = QFontMetrics(font)
        h = max(NODE_MIN_HEIGHT, fm.height() + 12)  # 高度取最小高度和字体高度+上下边距中的较大值
        # 根据不同模板类型调整高度
        if self._template == NodeTemplate.SOURCE:
            h = max(h, 38.0)
        elif self._template == NodeTemplate.CONDITION:
            h = max(h, 42.0)
        elif self._template == NodeTemplate.OUTPUT:
            h = max(h, 36.0)
        return w, h

    def _title_font(self) -> QFont:
        """获取标题字体"""
        font = QFont("Segoe UI", TEXT_FONT_SIZE)
        font.setStyleStrategy(QFont.PreferAntialias)  # 设置字体策略为优先抗锯齿
        return font

    # ── 插座管理 ─────────────────────────────────────────────────────────────
    def _create_sockets(self):
        """
        为每个端口创建 SocketItem
        初始位置由 _PORT_OFFSET_INIT 设置，场景的 _do_layout_port() 会进一步精确调整。
        """
        for port in self.node_data.ports:                 # 遍历节点数据中的所有端口
            socket = SocketItem(port, self)               # 为当前端口创建插座项，传入端口和当前节点作为父对象
            offset_fn = _PORT_OFFSET_INIT.get(port.dock)  # 根据端口的停靠位置获取对应的偏移量计算函数
            if offset_fn:                                 # 如果存在偏移量计算函数
                socket.setPos(offset_fn(self._node_w, self._node_h))  # 根据节点宽高计算偏移位置并设置插座的位置

            self.sockets.append(socket)

    def get_socket_at(self, pos: QPointF) -> SocketItem | None:
        """获取指定场景坐标下的插座"""
        threshold = PORT_DIAMETER * 2           # 设置检测阈值为端口直径的2倍
        for socket in self.sockets:             # 遍历所有插座
            sp = socket.get_center_scene_pos()  # 获取插座在场景中的中心坐标
            dx = pos.x() - sp.x()               # 计算目标点与插座中心的X方向差值
            dy = pos.y() - sp.y()               # 计算目标点与插座中心的Y方向差值
            if dx * dx + dy * dy < threshold * threshold:  # 如果距离小于阈值（使用平方比较避免开方）
                return socket                              # 返回找到的插座
        return None

    def get_socket_by_port_id(self, port_id: str) -> SocketItem | None:
        """根据端口ID获取插座"""
        for s in self.sockets:             # 遍历所有插座
            if s.port.port_id == port_id:  # 如果插座的端口ID与目标ID匹配
                return s                   # 返回该插座
        return None

    def get_input_sockets(self) -> list[SocketItem]:
        """获取所有输入插座"""
        return [s for s in self.sockets if s.port.is_input]

    def get_output_sockets(self) -> list[SocketItem]:
        """获取所有输出插座"""
        return [s for s in self.sockets if s.port.is_output]

    # ── 状态管理 ────────────────────────────────────────────────────

    def set_state(self, state: NodeState):
        """设置节点状态"""
        self._state = state             # 保存状态值
        self.prepareGeometryChange()    # 更新边界
        self.update()                   # 触发重绘
        if state == NodeState.RUNNING:  # 如果状态是运行中
            self._start_pulse()         # 启动脉冲动画
        else:
            self._stop_pulse()          # 否则停止脉冲动画

    def _start_pulse(self):
        """启动脉冲动画"""
        if self._pulse_timer is None:                            # 如果脉冲定时器还没有创建
            self._pulse_timer = QTimer()                         # 创建新的QTimer对象
            self._pulse_timer.timeout.connect(self._pulse_tick)  # 连接定时器的timeout信号到脉冲步进方法

        self._pulse_val = 0.0                                    # 重置脉冲动画值为0
        self._pulse_timer.start(50)                              # 启动定时器，间隔50毫秒

    def _stop_pulse(self):
        """停止脉冲动画"""
        if self._pulse_timer:         # 如果脉冲定时器存在
            self._pulse_timer.stop()  # 停止定时器

        self._pulse_val = 0.0         # 重置脉冲动画值为0

    def _pulse_tick(self):
        """脉冲动画步进"""
        self._pulse_val += 0.1  # 脉冲值增加0.1
        self.update()           # 触发重绘

    def update_from_node(self):
        """从节点数据更新节点状态（仅对本次运行已执行的节点生效）"""
        if isinstance(self.node_data, VisionNodeData):
            state = self.node_data._execution_state
            if state == FlowableResultState.ERROR:
                self.set_state(NodeState.ERROR)
            elif state == FlowableResultState.OK:
                self.set_state(NodeState.COMPLETED)
            elif state == FlowableResultState.BREAK:
                self.set_state(NodeState.IDLE)
        self.update()

    # ── 边界计算 ──────────────────────────────────────────────────────────────
    def boundingRect(self) -> QRectF:
        """返回边界矩形（包含插座区域）"""
        pad = PORT_DIAMETER + 4                           # 设置内边距为端口直径加4像素
        return self._rect.adjusted(-pad, -pad, pad, pad)  # 返回节点矩形向外扩展pad像素后的矩形

    def shape(self) -> QPainterPath:
        """返回形状（用于碰撞检测）"""
        return self._build_body_path(self._rect)  # 返回节点主体路径作为形状

    def _build_body_path(self, rect: QRectF) -> QPainterPath:
        """
        构建节点主体路径
        条件节点使用菱形（菱形），其他节点使用圆角矩形
        """
        path = QPainterPath()                              # 创建新的QPainterPath对象
        if self._template == NodeTemplate.CONDITION:       # 判断是否为条件节点模板
            path.moveTo(rect.center().x(), rect.top())     # 菱形路径：从顶部中点开始
            path.lineTo(rect.right(), rect.center().y())   # 画线到右侧中点
            path.lineTo(rect.center().x(), rect.bottom())  # 画线到底部中点
            path.lineTo(rect.left(), rect.center().y())    # 画线到左侧中点
            path.closeSubpath()                            # 闭合路径
        else:
            path.addRoundedRect(rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)  # 圆角矩形路径
        return path

    # ═════════════════════════════════════════════════════════════════════════
    # 绘制
    # ═════════════════════════════════════════════════════════════════════════
    def paint(self, painter, option, widget):
        """绘制节点"""
        painter.setRenderHint(QPainter.Antialiasing)   # 启用抗锯齿渲染
        state_color = self._resolve_state_color()      # 获取状态颜色（用于左侧状态条）
        body_path = self._build_body_path(self._rect)  # 获取主体路径（根据模板类型：菱形或圆角矩形）
        # ── 主体背景 —— 始终白色 ──
        bg_color = QColor("#FFFFFF")           # 设置背景颜色为白色
        painter.fillPath(body_path, bg_color)  # 用白色填充主体路径
        # ── 选中/悬停时绘制阴影 ──
        if self.isSelected() or self._hovered:                  # 判断节点是否被选中或鼠标悬停
            sr = self._rect.adjusted(2, 3, -2, 0)  # 创建阴影矩形：左+2，上+3，右-2，下不变
            shadow_path = self._build_body_path(sr)             # 构建阴影路径
            painter.fillPath(shadow_path, QColor(0, 0, 0, 30))  # 用半透明黑色(30/255透明度)填充阴影

        # ── 左侧条：带状态颜色的条，显示序号 ──
        self._draw_left_bar(painter, state_color)  # 调用私有方法绘制左侧状态条

        # ── 边框 ──
        border_color, border_width = self._resolve_border()  # 获取边框颜色和宽度
        painter.setPen(QPen(border_color, border_width))     # 设置画笔（边框颜色、边框宽度）
        painter.setBrush(Qt.NoBrush)                         # 设置画刷为无填充
        painter.drawPath(body_path)                          # 绘制主体路径的边框

        # ── 输出模板：双重边框 ──
        if self._template == NodeTemplate.OUTPUT and not self.isSelected():  # 判断是否为输出节点模板且未被选中
            inner = self._rect.adjusted(3, 3, -3, -3)               # 创建内层矩形：向内收缩3像素
            ipath = self._build_body_path(inner)                             # 构建内层路径
            painter.setPen(QPen(border_color.lighter(120), 0.5))             # 设置画笔：边框颜色变亮120%，线宽0.5像素
            painter.drawPath(ipath)                                          # 绘制内层边框

        # ── 右侧内容：白色背景上的图标和文字 ──
        self._draw_right_content(painter)  # 调用私有方法绘制右侧内容（图标和文字）

    # ── 颜色解析 ─────────────────────────────────────────────
    def _resolve_state_color(self) -> QColor:
        """左侧条的状态颜色——硬编码，与主题无关"""
        if self._state == NodeState.RUNNING:    # 运行中 — 蓝色
            return QColor("#409EFF")
        if self._state == NodeState.COMPLETED:  # 已完成 — 绿色
            return QColor("#67C23A")
        if self._state == NodeState.ERROR:      # 错误 - 红色
            return QColor("#DC000C")
        if self._state == NodeState.IDLE:       # 空闲 - 钢蓝色
            return QColor("#5C7A99")
        return QColor("#909399")                # 其他状态返回灰色

    def _resolve_border(self) -> tuple[QColor, float]:
        """状态感知的边框颜色——硬编码，与主题无关"""
        if self.isSelected():                   # 如果节点被选中
            return QColor("#E6A23C"), 2.0       # 返回橙色，线宽2.0
        if self._state == NodeState.ERROR:      # 如果状态为错误
            return QColor("#DC000C"), 2.0       # 返回红色，线宽2.0
        if self._state == NodeState.RUNNING:    # 运行中 — 蓝色边框
            return QColor("#409EFF"), 2.0       # 返回蓝色，线宽2.0
        if self._state == NodeState.COMPLETED:  # 如果状态为已完成
            return QColor("#67C23A"), 2.0       # 返回绿色，线宽2.0
        if self._state == NodeState.IDLE:       # 如果状态为空闲
            return QColor("#8899A6"), 1.5       # 返回蓝灰色，线宽1.5
        if self._hovered:                       # 如果鼠标悬停
            return QColor("#606266"), 1.5       # 返回深灰色，线宽1.5
        if self._template == NodeTemplate.SOURCE:  # 如果是源节点模板
            return self._flag_color, 2.0           # 返回分组颜色，线宽2.0
        return QColor("#EBEBEB"), 1.0              # 默认边框：浅灰色，线宽1.0

    def _resolve_content_color(self) -> QColor:
        """右侧内容（图标+文字）的颜色"""
        if self._state == NodeState.DISABLED:  # 如果节点被禁用
            return QColor("#C0C4CC")           # 返回浅灰色
        return QColor("#000000")               # 正常情况下返回黑色

    # ── 左侧条绘制 ────────────────────────────────────────────────────────────
    def _draw_left_bar(self, painter, state_color):
        """绘制左侧30px宽的状态条。条件节点用菱形主体裁剪bar贴合尖角，文字也跟随裁剪。"""
        bar_visible = self._state in (NodeState.RUNNING, NodeState.COMPLETED,
                                       NodeState.ERROR, NodeState.IDLE)
        if not bar_visible:
            return

        bar_rect = QRectF(-self._node_w / 2, -self._node_h / 2, BAR_WIDTH, self._node_h)
        if self._template == NodeTemplate.CONDITION:
            # 菱形：bar矩形与菱形主体取交集，得到贴合尖角的三角形可视区域
            body_path = self._build_body_path(self._rect)
            bar_path = QPainterPath()
            bar_path.addRect(bar_rect)
            visible_bar = body_path.intersected(bar_path)
            painter.fillPath(visible_bar, QBrush(state_color))
        else:
            # 矩形：圆角bar
            bar_path = QPainterPath()
            bar_path.addRoundedRect(bar_rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
            clip = QPainterPath()
            clip.addRect(-self._node_w / 2, -self._node_h / 2,
                         BAR_WIDTH + NODE_CORNER_RADIUS, self._node_h)
            visible_bar = clip.intersected(bar_path)
            painter.fillPath(visible_bar, QBrush(state_color))

        # 绘制序号（菱形时裁剪到可视区域，文字不会超出尖角范围）
        if self._index > 0:
            painter.save()
            if self._template == NodeTemplate.CONDITION:
                painter.setClipPath(visible_bar)
            index_font = QFont("Segoe UI", 11, QFont.Bold)
            painter.setFont(index_font)
            painter.setPen(QColor("#FFFFFF"))
            num_rect = QRectF(-self._node_w / 2 + 2, -self._node_h / 2 + 2,
                              BAR_WIDTH - 4, self._node_h - 4)
            painter.drawText(num_rect, Qt.AlignCenter, str(self._index))
            painter.restore()

    # ── 右侧内容绘制（白色背景上的图标和文字）─────────────────────────────────────
    def _draw_right_content(self, painter):
        """在右侧白色背景上绘制图标和文字"""
        right_x = -self._node_w / 2 + BAR_WIDTH        # 计算右侧区域的起始X坐标（左侧条结束的位置）
        right_w = self._node_w - BAR_WIDTH             # 计算右侧区域的宽度
        content_color = self._resolve_content_color()  # 获取内容颜色（正常为黑色，禁用为浅灰色）

        # ── 图标绘制 ──
        icon_f = icon_font(ICON_SIZE)  # 获取图标字体（字体图标）
        painter.setFont(icon_f)        # 设置字体为图标字体
        painter.setPen(content_color)  # 设置画笔颜色
        icon_w = 16.0                  # 图标宽度固定16像素
        icon_rect = QRectF(right_x + 6, -self._node_h / 2, icon_w, self._node_h)        # 图标显示区域：右侧区域向左偏移6像素，垂直居中
        painter.drawText(icon_rect, Qt.AlignVCenter | Qt.AlignCenter, self._icon_text)  # 绘制图标文字（垂直居中、水平居中）

        # ── 文字绘制（支持省略号）──
        font = self._title_font()      # 获取标题字体
        painter.setFont(font)          # 设置字体
        painter.setPen(content_color)  # 设置画笔颜色
        title = self.node_data.title or self.node_data.name  # 获取标题，如果标题为空则使用节点名称
        fm = QFontMetrics(font)                              # 创建字体度量器，用于测量文字宽度
        text_x = right_x + 6 + icon_w + 4                    # 文字起始X坐标：图标右侧偏移4像素
        text_w = max(1.0, right_w - icon_w - 14)             # 文字最大宽度：右侧区域宽度减去图标宽度和边距
        elided = fm.elidedText(title, Qt.ElideRight, int(text_w))            # 如果文字超出宽度，用省略号截断
        text_rect = QRectF(text_x, -self._node_h / 2, text_w, self._node_h)  # 文字显示区域
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)  # 绘制文字（垂直居中、左对齐）

    # ── 鼠标事件 ────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:          # 如果按下的是左键
            self.node_selected.emit(self.node_data)  # 发出节点选中信号
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件"""
        self.node_double_clicked.emit(self.node_data)  # 发出节点双击信号
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        super().mouseReleaseEvent(event)
        self.node_move_finished.emit(self.node_data)  # 松手后发出移动完成信号（供场景做吸附矫正）

    def hoverEnterEvent(self, event):
        """鼠标进入事件"""
        self._hovered = True  # 设置悬停标志为True
        self.update()         # 触发重绘
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """鼠标离开事件"""
        self._hovered = False  # 设置悬停标志为False
        self.update()          # 触发重绘
        super().hoverLeaveEvent(event)

    # ── 位置追踪 ───────────────────────────────────────────────────
    def itemChange(self, change, value):
        """图形项属性变化事件"""
        if change == self.ItemPositionHasChanged:  # 如果变化类型是位置发生变化
            self.node_moved.emit(self.node_data)   # 发出节点移动信号
        return super().itemChange(change, value)

    def set_node_position(self, x: float, y: float):
        """设置节点位置"""
        self.setPos(x, y)  # 调用setPos设置图形项位置

    def get_node_position(self) -> tuple[float, float]:
        """获取节点位置"""
        pos = self.pos()         # 获取当前图形项位置
        return pos.x(), pos.y()  # 返回X和Y坐标的元组

def _resolve_node_icon(node_data) -> str:
    """解析节点对应的图标"""
    cls = type(node_data)                             # 获取节点数据的类对象
    for base in cls.__mro__:                          # 遍历类的MRO（方法解析顺序），从子类到父类依次查找
        if base.__name__ in _NODE_ICONS:              # 检查当前基类的类名是否在图标映射字典中
            return _NODE_ICONS[base.__name__]         # 如果在字典中，返回对应的图标
    # 如果遍历完所有父类都没有找到匹配的图标
    # 获取节点的分组名称（从__group__属性获取，不存在则返回空字符串）
    group_name = getattr(node_data, '__group__', '')  # 根据分组名称获取对应的分组图标并返回
    return get_group_icon(group_name)
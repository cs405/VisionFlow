"""节点图形项"""

import math
from enum import Enum

from PyQt5.QtWidgets import (QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem,
                             QWidget)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer, QSizeF
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainter, QPainterPath,
                         QFont, QFontMetrics, QLinearGradient)

from core.node_base import NodeBase, Port, PortType, PortDock
from core.node_vision import VisionNodeData
from core.node_selectable import SrcFilesVisionNodeData
from core.node_condition import ConditionNodeData, WaitAllParallelNodeData
from gui.node_editor.socket_item import SocketItem, PORT_DIAMETER
from gui.font_icons import FontIcons, icon_font


# ═══════════════════════════════════════════════════════════════════════════
# 枚举定义
# ═══════════════════════════════════════════════════════════════════════════

class NodeState(Enum):
    """节点状态枚举"""
    IDLE = "idle"          # 空闲状态
    RUNNING = "running"    # 运行中
    COMPLETED = "completed" # 已完成
    ERROR = "error"        # 错误状态
    DISABLED = "disabled"  # 禁用状态


class NodeTemplate(Enum):
    """节点模板类型枚举"""
    DEFAULT = "default"    # 默认样式
    SOURCE = "source"      # 源节点样式（数据源）
    CONDITION = "condition" # 条件节点样式（菱形）
    OUTPUT = "output"      # 输出节点样式


# ═══════════════════════════════════════════════════════════════════════════
# 尺寸常量
# ═══════════════════════════════════════════════════════════════════════════

NODE_MIN_WIDTH = 120.0      # 节点最小宽度
NODE_MIN_HEIGHT = 35.0      # 节点最小高度
NODE_CORNER_RADIUS = 2.0    # 圆角半径
BAR_WIDTH = 30.0            # 左侧状态条宽度
ICON_SIZE = 14              # 图标大小
TEXT_FONT_SIZE = 9          # 文字字体大小
NODE_MARGIN = 2             # 节点边距

from core.constants import get_group_color, get_group_icon

# 节点类型到图标的映射字典
_NODE_ICONS = {
    # 源文件视觉节点 -> 相机图标
    "SrcFilesVisionNodeData": FontIcons.Camera,
    # 图像文件源节点 -> 相机图标
    "ImageFileSource": FontIcons.Camera,
    # 相机采集节点 -> 相机图标
    "CameraCapture": FontIcons.Camera,
    # 视频采集节点 -> 视频图标
    "VideoCapture": FontIcons.Video,
    # 颜色转换节点 -> 颜色图标
    "CvtColor": FontIcons.Color,
    # 高斯模糊节点 -> 隐私图标（表示滤镜/模糊）
    "GaussianBlur": FontIcons.InPrivate,
    # 中值模糊节点 -> 隐私图标
    "MedianBlur": FontIcons.InPrivate,
    # 双边滤波节点 -> 隐私图标
    "BilateralFilter": FontIcons.InPrivate,
    # 细节增强节点 -> 隐私图标
    "DetailEnhance": FontIcons.InPrivate,
    # 铅笔素描节点 -> 隐私图标
    "PencilSketch": FontIcons.InPrivate,
    # 阈值处理节点 -> 隐私图标
    "Threshold": FontIcons.InPrivate,
    # ROI节点 -> 标注图标
    "ROINodeData": FontIcons.Annotation,
    # 形态学处理节点 -> 主页组图标
    "Morphology": FontIcons.HomeGroup,
    # 腐蚀节点 -> 主页组图标
    "ErodeNode": FontIcons.HomeGroup,
    # 膨胀节点 -> 主页组图标
    "DilateNode": FontIcons.HomeGroup,
    # 条件节点 -> 拨号6图标（表示逻辑分支）
    "ConditionNodeData": FontIcons.Dial6,
    # 并行等待节点 -> 拨号6图标
    "WaitAllParallelNodeData": FontIcons.Dial6,
    # 模板匹配节点 -> 今日跳转图标
    "TemplateMatching": FontIcons.GotoToday,
    # 检测器节点 -> 大擦除图标
    "Detector": FontIcons.LargeErase,
    # 特征提取节点 -> 通用扫描图标
    "Feature": FontIcons.GenericScan,
    # Modbus通信节点 -> 讲述人前进图标（表示网络通信）
    "Modbus": FontIcons.NarratorForward,
    # TCP客户端节点 -> 讲述人前进图标
    "TcpClient": FontIcons.NarratorForward,
    # 输出节点 -> 以太网图标
    "Output": FontIcons.Ethernet,
    # ONNX模型节点 -> 命令提示符图标
    "Onnx": FontIcons.CommandPrompt,
    # 其他节点 -> 更多图标
    "Other": FontIcons.More,
}


def _resolve_node_icon(node_data) -> str:
    """解析节点对应的图标"""
    # 获取节点数据的类对象
    cls = type(node_data)
    # 遍历类的MRO（方法解析顺序），从子类到父类依次查找
    for base in cls.__mro__:
        # 检查当前基类的类名是否在图标映射字典中
        if base.__name__ in _NODE_ICONS:
            # 如果在字典中，返回对应的图标
            return _NODE_ICONS[base.__name__]
    # 如果遍历完所有父类都没有找到匹配的图标
    # 获取节点的分组名称（从__group__属性获取，不存在则返回空字符串）
    group_name = getattr(node_data, '__group__', '')
    # 根据分组名称获取对应的分组图标并返回
    return get_group_icon(group_name)


# 初始插座偏移量（后续由 scene._do_layout_port() 精确调整）
_PORT_OFFSET_INIT = {
    # 顶部端口：X坐标为0（水平居中），Y坐标向上偏移半个高度
    PortDock.TOP: lambda w, h: QPointF(0, -h / 2),
    # 底部端口：X坐标为0（水平居中），Y坐标向下偏移半个高度
    PortDock.BOTTOM: lambda w, h: QPointF(0, h / 2),
    # 左侧端口：X坐标向左偏移半个宽度，Y坐标为0（垂直居中）
    PortDock.LEFT: lambda w, h: QPointF(-w / 2, 0),
    # 右侧端口：X坐标向右偏移半个宽度，Y坐标为0（垂直居中）
    PortDock.RIGHT: lambda w, h: QPointF(w / 2, 0),
}


# ═══════════════════════════════════════════════════════════════════════════
# NodeItem（节点图形项）
# ═══════════════════════════════════════════════════════════════════════════

class NodeItem(QGraphicsObject):
    """画布上的视觉节点"""

    # 信号定义
    # 节点被选中时发出的信号，携带节点数据对象
    node_selected = pyqtSignal(object)
    # 节点被移动时发出的信号，携带节点数据对象
    node_moved = pyqtSignal(object)
    # 节点被双击时发出的信号，携带节点数据对象
    node_double_clicked = pyqtSignal(object)

    def __init__(self, node_data: NodeBase, group_name: str = "", parent=None):
        """初始化节点图形项

        参数：
            node_data: 节点数据对象
            group_name: 分组名称（用于确定颜色）
            parent: 父对象
        """
        # 调用父类QGraphicsObject的构造函数
        super().__init__(parent)
        # 保存节点数据对象
        self.node_data = node_data
        # 保存分组名称
        self._group_name = group_name
        # 初始化鼠标悬停标志为False
        self._hovered = False
        # 初始化节点状态为空闲状态
        self._state = NodeState.IDLE
        # 检测并保存节点模板类型
        self._template = self._detect_template()
        # 根据分组名称获取分组颜色，创建QColor对象
        self._flag_color = QColor(get_group_color(group_name))
        # 解析节点对应的图标字符
        self._icon_text = _resolve_node_icon(node_data)
        # 初始化脉冲动画值为0.0
        self._pulse_val = 0.0
        # 初始化脉冲动画定时器为None
        self._pulse_timer: QTimer | None = None
        # 初始化节点索引序号为0（由DiagramScene管理）
        self._index = 0

        # 计算节点自适应尺寸，返回宽度和高度
        self._node_w, self._node_h = self._compute_size()
        # 创建节点矩形区域，中心点位于(0,0)
        self._rect = QRectF(
            # 矩形左上角X坐标：负的宽度的一半
            -self._node_w / 2,
            # 矩形左上角Y坐标：负的高度的一半
            -self._node_h / 2,
            # 矩形宽度
            self._node_w,
            # 矩形高度
            self._node_h,
        )

        # 设置图形项标志
        # 设置节点可移动
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        # 设置节点可选中
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        # 设置节点在位置/几何变化时发送通知
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        # 设置接受鼠标悬停事件
        self.setAcceptHoverEvents(True)
        # 设置Z序为10（值越大显示越靠前）
        self.setZValue(10)

        # 创建插座列表
        self.sockets: list[SocketItem] = []
        # 调用私有方法创建所有插座
        self._create_sockets()

    # ── 模板类型检测 ──────────────────────────────────────────────────

    def _detect_template(self) -> NodeTemplate:
        """检测节点模板类型"""
        # 获取节点数据的本地引用，方便使用
        nd = self.node_data
        # 判断是否为源文件视觉节点类型
        if isinstance(nd, SrcFilesVisionNodeData):
            # 如果是源文件节点，返回源节点模板
            return NodeTemplate.SOURCE
        # 判断节点是否显式声明模板类型（支持字符串如 "condition" 或 NodeTemplate 枚举值）
        declared = getattr(nd, '__template__', None)
        if declared is not None:
            if isinstance(declared, NodeTemplate):
                return declared
            try:
                return NodeTemplate(declared)
            except ValueError:
                pass
        # 获取节点类名并转换为小写
        cls_name = nd.__class__.__name__.lower()
        # 判断类名是否以"show"开头或包含"output"
        if cls_name.startswith("show") or "output" in cls_name:
            # 如果是输出类节点，返回输出节点模板
            return NodeTemplate.OUTPUT
        # 其他情况返回默认模板
        return NodeTemplate.DEFAULT

    # ── 自适应尺寸计算 ─────────────────────────────────────────────────────

    def _compute_size(self) -> tuple[float, float]:
        """计算节点尺寸（根据标题文字长度自适应）"""
        # 获取节点标题，如果标题为空则使用节点名称
        title = self.node_data.title or self.node_data.name
        # 获取标题字体对象
        font = self._title_font()
        # 创建字体度量器，用于测量文字尺寸
        fm = QFontMetrics(font)
        # 计算标题文字的宽度（像素）
        text_width = fm.boundingRect(title).width()
        # 计算节点宽度：取最小宽度 和 (状态条宽度+文字宽度+边距+图标宽度+额外边距) 中的较大值
        w = max(NODE_MIN_WIDTH, BAR_WIDTH + text_width + 18 + ICON_SIZE + 10)
        # 计算节点高度：取最小高度 和 (字体高度+上下边距) 中的较大值
        h = max(NODE_MIN_HEIGHT, fm.height() + 12)
        # 根据不同模板类型调整高度
        # 如果是源节点模板
        if self._template == NodeTemplate.SOURCE:
            # 确保高度至少38像素
            h = max(h, 38.0)
        # 如果是条件节点模板（菱形）
        elif self._template == NodeTemplate.CONDITION:
            # 确保高度至少42像素
            h = max(h, 42.0)
        # 如果是输出节点模板
        elif self._template == NodeTemplate.OUTPUT:
            # 确保高度至少36像素
            h = max(h, 36.0)
        # 返回宽度和高度的元组
        return w, h

    def _title_font(self) -> QFont:
        """获取标题字体"""
        # 创建Segoe UI字体，大小为TEXT_FONT_SIZE(9)
        font = QFont("Segoe UI", TEXT_FONT_SIZE)
        # 设置字体策略为优先抗锯齿
        font.setStyleStrategy(QFont.PreferAntialias)
        # 返回字体对象
        return font

    # ── 插座管理 ─────────────────────────────────────────────────────────────

    def _create_sockets(self):
        """为每个端口创建 SocketItem

        初始位置由 _PORT_OFFSET_INIT 设置，场景的 _do_layout_port() 会进一步精确调整。
        """
        # 遍历节点数据中的所有端口
        for port in self.node_data.ports:
            # 为当前端口创建插座项，传入端口和当前节点作为父对象
            socket = SocketItem(port, self)
            # 根据端口的停靠位置获取对应的偏移量计算函数
            offset_fn = _PORT_OFFSET_INIT.get(port.dock)
            # 如果存在偏移量计算函数
            if offset_fn:
                # 根据节点宽高计算偏移位置并设置插座的位置
                socket.setPos(offset_fn(self._node_w, self._node_h))
            # 将创建的插座添加到sockets列表中
            self.sockets.append(socket)

    def get_socket_at(self, pos: QPointF) -> SocketItem | None:
        """获取指定场景坐标下的插座"""
        # 设置检测阈值为端口直径的2倍
        threshold = PORT_DIAMETER * 2
        # 遍历所有插座
        for socket in self.sockets:
            # 获取插座在场景中的中心坐标
            sp = socket.get_center_scene_pos()
            # 计算目标点与插座中心的X方向差值
            dx = pos.x() - sp.x()
            # 计算目标点与插座中心的Y方向差值
            dy = pos.y() - sp.y()
            # 如果距离小于阈值（使用平方比较避免开方）
            if dx * dx + dy * dy < threshold * threshold:
                # 返回找到的插座
                return socket
        # 没有找到则返回None
        return None

    def get_socket_by_port_id(self, port_id: str) -> SocketItem | None:
        """根据端口ID获取插座"""
        # 遍历所有插座
        for s in self.sockets:
            # 如果插座的端口ID与目标ID匹配
            if s.port.port_id == port_id:
                # 返回该插座
                return s
        # 没有找到则返回None
        return None

    def get_input_sockets(self) -> list[SocketItem]:
        """获取所有输入插座"""
        # 使用列表推导式，筛选出所有输入端口对应的插座
        return [s for s in self.sockets if s.port.is_input]

    def get_output_sockets(self) -> list[SocketItem]:
        """获取所有输出插座"""
        # 使用列表推导式，筛选出所有输出端口对应的插座
        return [s for s in self.sockets if s.port.is_output]

    # ── 状态管理 ────────────────────────────────────────────────────

    def set_state(self, state: NodeState):
        """设置节点状态"""
        # 保存状态值
        self._state = state
        # 通知几何形状即将变化（用于更新边界）
        self.prepareGeometryChange()
        # 触发重绘
        self.update()
        # 如果状态是运行中
        if state == NodeState.RUNNING:
            # 启动脉冲动画
            self._start_pulse()
        else:
            # 否则停止脉冲动画
            self._stop_pulse()

    def _start_pulse(self):
        """启动脉冲动画"""
        # 如果脉冲定时器还没有创建
        if self._pulse_timer is None:
            # 创建新的QTimer对象
            self._pulse_timer = QTimer()
            # 连接定时器的timeout信号到脉冲步进方法
            self._pulse_timer.timeout.connect(self._pulse_tick)
        # 重置脉冲动画值为0
        self._pulse_val = 0.0
        # 启动定时器，间隔50毫秒
        self._pulse_timer.start(50)

    def _stop_pulse(self):
        """停止脉冲动画"""
        # 如果脉冲定时器存在
        if self._pulse_timer:
            # 停止定时器
            self._pulse_timer.stop()
        # 重置脉冲动画值为0
        self._pulse_val = 0.0

    def _pulse_tick(self):
        """脉冲动画步进"""
        # 脉冲值增加0.1
        self._pulse_val += 0.1
        # 触发重绘
        self.update()

    def update_from_node(self):
        """从节点数据更新节点状态（仅对本次运行已执行的节点生效）"""
        if isinstance(self.node_data, VisionNodeData):
            state = self.node_data._execution_state
            if state == "error":
                self.set_state(NodeState.ERROR)
            elif state == "completed":
                self.set_state(NodeState.COMPLETED)
            elif state == "break":
                self.set_state(NodeState.IDLE)
            # None = 未执行，保持当前状态不变
        self.update()

    # ── 边界计算 ──────────────────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        """返回边界矩形（包含插座区域）"""
        # 设置内边距为端口直径加4像素
        pad = PORT_DIAMETER + 4
        # 返回节点矩形向外扩展pad像素后的矩形
        return self._rect.adjusted(-pad, -pad, pad, pad)

    def shape(self) -> QPainterPath:
        """返回形状（用于碰撞检测）"""
        # 返回节点主体路径作为形状
        return self._build_body_path(self._rect)

    def _build_body_path(self, rect: QRectF) -> QPainterPath:
        """构建节点主体路径

        条件节点使用菱形（菱形），其他节点使用圆角矩形
        """
        # 创建新的QPainterPath对象
        path = QPainterPath()
        # 判断是否为条件节点模板
        if self._template == NodeTemplate.CONDITION:
            # 菱形路径：从顶部中点开始
            path.moveTo(rect.center().x(), rect.top())
            # 画线到右侧中点
            path.lineTo(rect.right(), rect.center().y())
            # 画线到底部中点
            path.lineTo(rect.center().x(), rect.bottom())
            # 画线到左侧中点
            path.lineTo(rect.left(), rect.center().y())
            # 闭合路径
            path.closeSubpath()
        else:
            # 圆角矩形路径
            path.addRoundedRect(rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
        # 返回路径对象
        return path

    # ═════════════════════════════════════════════════════════════════════════
    # 绘制
    # ═════════════════════════════════════════════════════════════════════════

    def paint(self, painter, option, widget):
        """绘制节点"""
        # 启用抗锯齿渲染
        painter.setRenderHint(QPainter.Antialiasing)

        # 获取状态颜色（用于左侧状态条）
        state_color = self._resolve_state_color()
        # 获取主体路径（根据模板类型：菱形或圆角矩形）
        body_path = self._build_body_path(self._rect)

        # ── 主体背景 —— 始终白色，与主题无关 ──
        # 设置背景颜色为白色
        bg_color = QColor("#FFFFFF")
        # 用白色填充主体路径
        painter.fillPath(body_path, bg_color)

        # ── 选中/悬停时绘制阴影 ──
        # 判断节点是否被选中或鼠标悬停
        if self.isSelected() or self._hovered:
            # 创建阴影矩形：左+2，上+3，右-2，下不变
            sr = self._rect.adjusted(2, 3, -2, 0)
            # 构建阴影路径
            shadow_path = self._build_body_path(sr)
            # 用半透明黑色(30/255透明度)填充阴影
            painter.fillPath(shadow_path, QColor(0, 0, 0, 30))

        # ── 左侧条：带状态颜色的条，显示序号 ──
        # 调用私有方法绘制左侧状态条
        self._draw_left_bar(painter, state_color)

        # ── 边框 ──
        # 获取边框颜色和宽度
        border_color, border_width = self._resolve_border()
        # 设置画笔（边框颜色、边框宽度）
        painter.setPen(QPen(border_color, border_width))
        # 设置画刷为无填充
        painter.setBrush(Qt.NoBrush)
        # 绘制主体路径的边框
        painter.drawPath(body_path)

        # ── 输出模板：双重边框 ──
        # 判断是否为输出节点模板且未被选中
        if self._template == NodeTemplate.OUTPUT and not self.isSelected():
            # 创建内层矩形：向内收缩3像素
            inner = self._rect.adjusted(3, 3, -3, -3)
            # 构建内层路径
            ipath = self._build_body_path(inner)
            # 设置画笔：边框颜色变亮120%，线宽0.5像素
            painter.setPen(QPen(border_color.lighter(120), 0.5))
            # 绘制内层边框
            painter.drawPath(ipath)

        # ── 右侧内容：白色背景上的图标和文字 ──
        # 调用私有方法绘制右侧内容（图标和文字）
        self._draw_right_content(painter)

    # ── 颜色解析 ─────────────────────────────────────────────

    def _resolve_state_color(self) -> QColor:
        """左侧条的状态颜色——硬编码，与主题无关"""
        # 运行中 — 蓝色，与成功绿色区分
        if self._state == NodeState.RUNNING:
            return QColor("#409EFF")
        # 已完成 — 绿色，只有真正运行成功才是绿色
        if self._state == NodeState.COMPLETED:
            return QColor("#67C23A")
        # 如果状态为错误
        if self._state == NodeState.ERROR:
            # 返回红色
            return QColor("#DC000C")
        # 如果状态为空闲
        if self._state == NodeState.IDLE:
            # 返回钢蓝色
            return QColor("#5C7A99")
        # 其他状态返回灰色
        return QColor("#909399")

    def _resolve_border(self) -> tuple[QColor, float]:
        """状态感知的边框颜色——硬编码，与主题无关"""
        # 如果节点被选中
        if self.isSelected():
            # 返回橙色，线宽2.0
            return QColor("#E6A23C"), 2.0
        # 如果状态为错误
        if self._state == NodeState.ERROR:
            # 返回红色，线宽2.0
            return QColor("#DC000C"), 2.0
        # 运行中 — 蓝色边框
        if self._state == NodeState.RUNNING:
            return QColor("#409EFF"), 2.0
        # 如果状态为已完成
        if self._state == NodeState.COMPLETED:
            # 返回绿色，线宽2.0
            return QColor("#67C23A"), 2.0
        # 如果状态为空闲
        if self._state == NodeState.IDLE:
            # 返回蓝灰色，线宽1.5
            return QColor("#8899A6"), 1.5
        # 如果鼠标悬停
        if self._hovered:
            # 返回深灰色，线宽1.5
            return QColor("#606266"), 1.5
        # 如果是源节点模板
        if self._template == NodeTemplate.SOURCE:
            # 返回分组颜色，线宽2.0
            return self._flag_color, 2.0
        # 默认边框：浅灰色，线宽1.0
        return QColor("#EBEBEB"), 1.0

    def _resolve_content_color(self) -> QColor:
        """右侧内容（图标+文字）的颜色"""
        # 如果节点被禁用
        if self._state == NodeState.DISABLED:
            # 返回浅灰色
            return QColor("#C0C4CC")
        # 正常情况下返回黑色
        return QColor("#000000")

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
        # 计算右侧区域的起始X坐标（左侧条结束的位置）
        right_x = -self._node_w / 2 + BAR_WIDTH
        # 计算右侧区域的宽度
        right_w = self._node_w - BAR_WIDTH
        # 获取内容颜色（正常为黑色，禁用为浅灰色）
        content_color = self._resolve_content_color()

        # ── 图标绘制 ──
        # 获取图标字体（字体图标）
        icon_f = icon_font(ICON_SIZE)
        # 设置字体为图标字体
        painter.setFont(icon_f)
        # 设置画笔颜色
        painter.setPen(content_color)
        # 图标宽度固定16像素
        icon_w = 16.0
        # 图标显示区域：右侧区域向左偏移6像素，垂直居中
        icon_rect = QRectF(right_x + 6, -self._node_h / 2, icon_w, self._node_h)
        # 绘制图标文字（垂直居中、水平居中）
        painter.drawText(icon_rect, Qt.AlignVCenter | Qt.AlignCenter, self._icon_text)

        # ── 文字绘制（支持省略号）──
        # 获取标题字体
        font = self._title_font()
        # 设置字体
        painter.setFont(font)
        # 设置画笔颜色
        painter.setPen(content_color)
        # 获取标题，如果标题为空则使用节点名称
        title = self.node_data.title or self.node_data.name

        # 创建字体度量器，用于测量文字宽度
        fm = QFontMetrics(font)
        # 文字起始X坐标：图标右侧偏移4像素
        text_x = right_x + 6 + icon_w + 4
        # 文字最大宽度：右侧区域宽度减去图标宽度和边距
        text_w = max(1.0, right_w - icon_w - 14)
        # 如果文字超出宽度，用省略号截断
        elided = fm.elidedText(title, Qt.ElideRight, int(text_w))

        # 文字显示区域
        text_rect = QRectF(text_x, -self._node_h / 2, text_w, self._node_h)
        # 绘制文字（垂直居中、左对齐）
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

    # ── 鼠标事件 ────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        # 如果按下的是左键
        if event.button() == Qt.LeftButton:
            # 发出节点选中信号
            self.node_selected.emit(self.node_data)
        # 调用父类的鼠标按下事件处理
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件"""
        # 发出节点双击信号
        self.node_double_clicked.emit(self.node_data)
        # 调用父类的鼠标双击事件处理
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        # 发出节点移动信号
        self.node_moved.emit(self.node_data)
        # 调用父类的鼠标释放事件处理
        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        """鼠标进入事件"""
        # 设置悬停标志为True
        self._hovered = True
        # 触发重绘
        self.update()
        # 调用父类的悬停进入事件处理
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """鼠标离开事件"""
        # 设置悬停标志为False
        self._hovered = False
        # 触发重绘
        self.update()
        # 调用父类的悬停离开事件处理
        super().hoverLeaveEvent(event)

    # ── 位置追踪 ───────────────────────────────────────────────────

    def itemChange(self, change, value):
        """图形项属性变化事件"""
        # 如果变化类型是位置发生变化
        if change == self.ItemPositionHasChanged:
            # 发出节点移动信号
            self.node_moved.emit(self.node_data)
        # 调用父类的itemChange方法并返回结果
        return super().itemChange(change, value)

    def set_node_position(self, x: float, y: float):
        """设置节点位置"""
        # 调用setPos设置图形项位置
        self.setPos(x, y)

    def get_node_position(self) -> tuple[float, float]:
        """获取节点位置"""
        # 获取当前图形项位置
        pos = self.pos()
        # 返回X和Y坐标的元组
        return (pos.x(), pos.y())
"""结果展示器 - 节点执行输出的结构化结果项。

定义结果项层次结构：
  - ResultItem: 基础值结果（名称、值、类型）
  - RectangleResultItem: 带位置/大小的边界框
  - LineResultItem: 从 (x1,y1) 到 (x2,y2) 的线段
  - ScoreRectangleResultItem: 带置信度分数的边界框
  - ImageResultItem: 输出图像引用
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResultItemType(Enum):
    """结果项类型枚举"""
    VALUE = "value"              # 普通值类型
    RECTANGLE = "rectangle"      # 矩形/边界框
    LINE = "line"                # 线段
    SCORE_RECTANGLE = "score_rectangle"  # 带分数的边界框
    IMAGE = "image"              # 图像
    TABLE = "table"              # 表格
    TEXT = "text"                # 文本


@dataclass
class ResultItem:
    """带名称和值的基础结果项。"""
    name: str                                      # 结果名称
    value: Any = None                              # 结果值
    item_type: ResultItemType = ResultItemType.VALUE  # 结果类型
    description: str = ""                          # 描述
    unit: str = ""                                 # 单位

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "name": self.name,
            "value": str(self.value) if self.value is not None else "",
            "type": self.item_type.value,
            "description": self.description,
            "unit": self.unit,
        }


@dataclass
class RectangleResultItem(ResultItem):
    """矩形/边界框结果。

    几何信息：图像坐标系中的 (x, y, width, height)
    """
    x: float = 0.0        # 左上角 X 坐标
    y: float = 0.0        # 左上角 Y 坐标
    width: float = 0.0    # 宽度
    height: float = 0.0   # 高度

    def __post_init__(self):
        """初始化后设置类型为矩形"""
        self.item_type = ResultItemType.RECTANGLE

    @property
    def rect(self) -> tuple[float, float, float, float]:
        """获取矩形元组 (x, y, width, height)"""
        return (self.x, self.y, self.width, self.height)

    def to_dict(self) -> dict:
        """序列化为字典"""
        d = super().to_dict()
        d.update({"x": self.x, "y": self.y, "width": self.width, "height": self.height})
        return d


@dataclass
class LineResultItem(ResultItem):
    """线段结果。"""
    x1: float = 0.0   # 起点 X 坐标
    y1: float = 0.0   # 起点 Y 坐标
    x2: float = 0.0   # 终点 X 坐标
    y2: float = 0.0   # 终点 Y 坐标

    def __post_init__(self):
        """初始化后设置类型为线段"""
        self.item_type = ResultItemType.LINE

    @property
    def points(self) -> tuple[float, float, float, float]:
        """获取端点元组 (x1, y1, x2, y2)"""
        return (self.x1, self.y1, self.x2, self.y2)

    def to_dict(self) -> dict:
        """序列化为字典"""
        d = super().to_dict()
        d.update({"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2})
        return d


@dataclass
class ScoreRectangleResultItem(RectangleResultItem):
    """带置信度分数的边界框。"""
    score: float = 0.0    # 置信度分数（0-1）

    def __post_init__(self):
        """初始化后设置类型为带分数的矩形"""
        self.item_type = ResultItemType.SCORE_RECTANGLE

    def to_dict(self) -> dict:
        """序列化为字典"""
        d = super().to_dict()
        d.update({"score": self.score})
        return d


@dataclass
class ImageResultItem(ResultItem):
    """结果图像的引用。"""
    image_shape: tuple = field(default_factory=tuple)  # 图像形状 (H, W, C)
    image_path: str = ""                               # 图像文件路径

    def __post_init__(self):
        """初始化后设置类型为图像"""
        self.item_type = ResultItemType.IMAGE


@dataclass
class TableResultItem(ResultItem):
    """带行列的表格结果。"""
    columns: list[str] = field(default_factory=list)     # 列名列表
    rows: list[list[Any]] = field(default_factory=list)  # 行数据列表

    def __post_init__(self):
        """初始化后设置类型为表格"""
        self.item_type = ResultItemType.TABLE


# ── 结果集合 ──────────────────────────────────────────────────────

@dataclass
# ═══════════════════════════════════════════════════════════════════════════
# "历史结果" (History Results) 实现细节
#
# 核心架构（三层解耦）：
#
#   1. Data Model — IVisionMessage + VisionMessage (BindableBase, MVVM 数据层):
#      ┌──────────────────────┬─────────────────────────────────────────────────┐
#      │ Index (int)          │ 执行序号 = Messages.Count + 1                    │
#      │ TimeSpan             │ 执行耗时 (System.TimeSpan)                       │
#      │ Type (string)        │ 模块名称 (INameable.Name 或 ITextable.Text)       │
#      │ Message (string)     │ 结果数据文本，ToolTip 显示完整内容                   │
#      │ State (FlowableState)│ Success / Error                                 │
#      │ ResultImageSource    │ 结果图像 ImageSource → 点击行时更新主图像            │
#      │ SrcFilePath (string) │ 源文件路径（从 ISrcFilesNodeData 获取）             │
#      │ ResultNodeData       │ IResultPresenterNodeData 引用，用于更新属性面板     │
#      └──────────────────────┴─────────────────────────────────────────────────┘
#
#   2. Collection — ObservableCollection<IVisionMessage> Messages:
#      - 存储在 VisionDiagramDataBase 上（非 UI Panel）
#      - 每个 DiagramData 拥有独立的 Messages，切换 tab 时自动隔离
#      - "运行全部" 循环中每次迭代自动累积
#      - CurrentMessage: 聚合统计（totalTimeSpan + 最后一条消息）
#
#   3. OnInvokedPart(IPartData) — 节点执行后自动收归历史（关键解耦点）:
#      node 执行完成 → OnInvokedPart(partData)
#        → if !openCVNodeData.UseInvokedPart: return  ← 每个节点可控
#        → 对视频/摄像头节点: find existing by ResultNodeData match
#          → found: 原地更新 TimeSpan/Message/State/ResultImageSource（不新增行）
#          → not found: 新建 VisionMessage{Index, Type=Name, State, TimeSpan,
#              SrcFilePath, ResultImageSource, ResultNodeData}
#        → Messages.Add(message) → LogCurrentMessage()
#      注意: OnInvokedPart 在 Application.Current.Dispatcher.Invoke 中执行，
#      因为视频部分异步触发需要用主线程生成 ImageSource 对象。
#
#   4. SelectedMessageChangedCommand — 点击行联动:
#      SelectionChangedEventArgs → AddedItems → IVisionMessage
#        → SetResultNodeData(message):
#          ResultImageSource = message.ResultImageSource   // 更新主图像查看器
#          ResultNodeData = message.ResultNodeData         // 更新属性面板 + 图像上下文
#          ResultType = $"输出结果<{message.Type}>"        // 更新标题
#
#   5. LogCurrentMessage() — 聚合:
#      totalTimeSpan = Messages.Sum(x => x.TimeSpan.Ticks)
#      CurrentMessage = new VisionMessage{TimeSpan=total, Message=this.Message}
#
#   6. DataGrid 列定义: [执行序号|执行时间|模块|结果数据]
#      - 结果数据列 = DataGridTemplateColumn:
#        - FontIconTextBlock (FontIcons.Info 默认, Error=红色FontIcons.Error,
#          Success=绿色FontIcons.Completed)
#        - TextBlock (Text="{Binding Message}", ToolTip="{Binding Message}")
#      - DataTrigger: State=Error → Foreground=Red, Icon=Error
#      - DataTrigger: State=Success → Foreground=Green, Icon=Completed
#
#   7. UseInvokedPart 属性:
#      每个 VisionNodeData 上有 UseInvokedPart (bool, 默认 true)
#      位于 DisplayParameters 分组，控制是否输出到历史记录和预览图像
#      ModbusNodeDataBase 等网络节点将其默认设为 false
#
# VisionFlow 适配策略:
#   - VisionMessage dataclass (pure data, 无 Qt 依赖) → core/result_presenter.py
#   - Messages 集合存储在 WorkflowEngine 上  ← 关键解耦
#   - WorkflowEngine.on_node_completed() 替代 OnInvokedPart
#   - ResultPanel 从 active workflow 读取 messages，不拥有数据
#   - UseInvokedPart → VisionNodeData.use_invoked_part Property
#   - 点击行 → image_update_requested + node_jump_requested 信号
#   - 更新已有条目: 对相机/视频等持续采集节点，按 node_id 查找并原地更新
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class VisionMessage:
    """ IVisionMessage / VisionMessage 1:1 移植。

    存储在 ResultPanel（或 DiagramData）上，用于历史记录表显示。
    """
    index: int = 0                    # 执行序号
    time_span: str = ""               # 格式化的时间字符串
    type_name: str = ""               # 模块名称
    message: str = ""                 # 结果文本
    state: str = "Success"            # "Success" / "Error" / "Running"
    result_image_source: Any = None   # 用于图像显示的 numpy 数组
    src_file_path: str = ""           # 执行时的源文件路径
    result_node_data: Any = None      # VisionNodeData 的引用


@dataclass
class NodeResult:
    """单次节点执行的完整结果集。"""
    node_id: str = ""                                 # 节点ID
    node_name: str = ""                               # 节点名称
    node_type: str = ""                               # 节点类型
    success: bool = True                              # 是否成功
    message: str = ""                                 # 结果消息
    execution_time_ms: float = 0.0                    # 执行耗时（毫秒）
    timestamp: str = ""                               # 时间戳

    # 结果项分类存储
    value_items: list[ResultItem] = field(default_factory=list)                      # 值类型项
    rectangle_items: list[RectangleResultItem] = field(default_factory=list)        # 矩形项
    line_items: list[LineResultItem] = field(default_factory=list)                  # 线段项
    score_rectangle_items: list[ScoreRectangleResultItem] = field(default_factory=list)  # 带分矩形项
    image_items: list[ImageResultItem] = field(default_factory=list)                # 图像项
    table_items: list[TableResultItem] = field(default_factory=list)                # 表格项

    @property
    def total_items(self) -> int:
        """获取结果项总数"""
        return (len(self.value_items) + len(self.rectangle_items) +
                len(self.line_items) + len(self.score_rectangle_items) +
                len(self.image_items) + len(self.table_items))

    @property
    def all_geometry_items(self) -> list:
        """获取所有具有空间坐标的项（用于图像叠加显示）"""
        items = []
        items.extend(self.rectangle_items)
        items.extend(self.score_rectangle_items)
        items.extend(self.line_items)
        return items

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "node_type": self.node_type,
            "success": self.success,
            "message": self.message,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp,
            "value_items": [it.to_dict() for it in self.value_items],
            "rectangle_items": [it.to_dict() for it in self.rectangle_items],
            "line_items": [it.to_dict() for it in self.line_items],
            "score_rectangle_items": [it.to_dict() for it in self.score_rectangle_items],
            "image_items": [it.to_dict() for it in self.image_items],
            "table_items": [it.to_dict() for it in self.table_items],
        }


# ═══════════════════════════════════════════════════════════════════════════
# 结果展示器
# ═══════════════════════════════════════════════════════════════════════════

class ValueResultPresenter:
    """将单个值项呈现为键值对。

    生成适合 2 列表格（属性 | 值）的行。
    """

    def __init__(self, node_result: NodeResult = None):
        # 节点结果对象
        self._result = node_result

    def set_result(self, result: NodeResult):
        """设置要呈现的结果"""
        self._result = result

    def get_rows(self) -> list[tuple[str, str, ResultItemType]]:
        """返回表格显示的行数据 (名称, 值字符串, 类型)"""
        if self._result is None:
            return []
        rows: list[tuple[str, str, ResultItemType]] = []
        # 添加基本信息行
        rows.append(("节点名称", self._result.node_name, ResultItemType.VALUE))
        rows.append(("节点类型", self._result.node_type, ResultItemType.VALUE))
        rows.append(("执行状态", "成功" if self._result.success else "失败",
                     ResultItemType.VALUE))
        rows.append(("消息", self._result.message or "-", ResultItemType.VALUE))
        # 添加耗时信息（如果有）
        if self._result.execution_time_ms > 0:
            rows.append(("耗时", f"{self._result.execution_time_ms:.1f} ms",
                         ResultItemType.VALUE))
        # 添加所有值类型的项
        for item in self._result.value_items:
            rows.append((item.name, str(item.value) if item.value is not None else "-",
                         item.item_type))
        return rows


class DataGridResultPresenter:
    """将带几何数据的结构化结果项呈现为网格显示。

    生成包含以下列的行：名称 | 值 | X | Y | 宽度 | 高度 | 分数。
    通过几何坐标支持图像查看器联动。
    """

    # 表格列定义
    COLUMNS = ("名称", "值", "X", "Y", "宽度", "高度", "分数")

    def __init__(self, node_result: NodeResult = None):
        # 节点结果对象
        self._result = node_result
        # 选中的行索引集合
        self._selected_rows: set[int] = set()

    def set_result(self, result: NodeResult):
        """设置要呈现的结果"""
        self._result = result
        self._selected_rows.clear()

    def get_rows(self) -> list[dict]:
        """返回行数据列表，每行为字典格式"""
        if self._result is None:
            return []
        rows: list[dict] = []

        # 处理矩形项
        for item in self._result.rectangle_items:
            rows.append({"名称": item.name, "值": str(item.value or ""),
                         "X": str(item.x), "Y": str(item.y),
                         "宽度": str(item.width), "高度": str(item.height),
                         "分数": "", "type": ResultItemType.RECTANGLE,
                         "geometry": item.rect})

        # 处理带分数的矩形项
        for item in self._result.score_rectangle_items:
            rows.append({"名称": item.name, "值": str(item.value or ""),
                         "X": str(item.x), "Y": str(item.y),
                         "宽度": str(item.width), "高度": str(item.height),
                         "分数": f"{item.score:.3f}", "type": ResultItemType.SCORE_RECTANGLE,
                         "geometry": item.rect})

        # 处理线段项
        for item in self._result.line_items:
            rows.append({"名称": item.name, "值": str(item.value or ""),
                         "X": f"{item.x1:.1f}", "Y": f"{item.y1:.1f}",
                         "宽度": f"{item.x2:.1f}", "高度": f"{item.y2:.1f}",
                         "分数": "", "type": ResultItemType.LINE,
                         "geometry": item.points})

        return rows

    def select_row(self, index: int) -> dict | None:
        """选中一行并返回其几何数据（用于图像查看器联动）"""
        rows = self.get_rows()
        if 0 <= index < len(rows):
            self._selected_rows.add(index)
            return rows[index]
        return None

    def deselect_all(self):
        """取消所有选中"""
        self._selected_rows.clear()

    @property
    def selected_indices(self) -> set[int]:
        """获取选中的行索引集合"""
        return set(self._selected_rows)
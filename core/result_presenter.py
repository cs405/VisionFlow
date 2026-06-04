"""Result presenter - structured result items for node execution outputs.

Ported from H.VisionMaster.ResultPresenter/* (DataGridResultPresenter, ValueResultPresenter).

Defines the result item hierarchy:
  - ResultItem: base value result (name, value, type)
  - RectangleResultItem: bounding box with position/size
  - LineResultItem: line segment from (x1,y1) to (x2,y2)
  - ScoreRectangleResultItem: bounding box with confidence score
  - ImageResultItem: output image reference
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResultItemType(Enum):
    VALUE = "value"
    RECTANGLE = "rectangle"
    LINE = "line"
    SCORE_RECTANGLE = "score_rectangle"
    IMAGE = "image"
    TABLE = "table"
    TEXT = "text"


@dataclass
class ResultItem:
    """Base result item with name and value.

    Ported from C# ValueResultPresenter / IResultPresenter.
    """
    name: str
    value: Any = None
    item_type: ResultItemType = ResultItemType.VALUE
    description: str = ""
    unit: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": str(self.value) if self.value is not None else "",
            "type": self.item_type.value,
            "description": self.description,
            "unit": self.unit,
        }


@dataclass
class RectangleResultItem(ResultItem):
    """A rectangle/bounding box result.

    Ported from C# RectangleResultItem / DataGridResultPresenter.
    Geometry: (x, y, width, height) in image coordinates.
    """
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    def __post_init__(self):
        self.item_type = ResultItemType.RECTANGLE

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.width, self.height)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({"x": self.x, "y": self.y, "width": self.width, "height": self.height})
        return d


@dataclass
class LineResultItem(ResultItem):
    """A line segment result.

    Ported from C# LineResultItem.
    """
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0

    def __post_init__(self):
        self.item_type = ResultItemType.LINE

    @property
    def points(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2})
        return d


@dataclass
class ScoreRectangleResultItem(RectangleResultItem):
    """A bounding box with confidence score.

    Ported from C# ScoreRectangleResultItem.
    """
    score: float = 0.0

    def __post_init__(self):
        self.item_type = ResultItemType.SCORE_RECTANGLE

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({"score": self.score})
        return d


@dataclass
class ImageResultItem(ResultItem):
    """Reference to a result image."""
    image_shape: tuple = field(default_factory=tuple)
    image_path: str = ""

    def __post_init__(self):
        self.item_type = ResultItemType.IMAGE


@dataclass
class TableResultItem(ResultItem):
    """Tabular result with rows and columns."""
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)

    def __post_init__(self):
        self.item_type = ResultItemType.TABLE


# ── Result Collection ──────────────────────────────────────────────────────

@dataclass
class NodeResult:
    """Complete set of results from a single node execution.

    Ported from C# VisionDiagramData's result collection.
    """
    node_id: str = ""
    node_name: str = ""
    node_type: str = ""
    success: bool = True
    message: str = ""
    execution_time_ms: float = 0.0
    timestamp: str = ""

    # Result items
    value_items: list[ResultItem] = field(default_factory=list)
    rectangle_items: list[RectangleResultItem] = field(default_factory=list)
    line_items: list[LineResultItem] = field(default_factory=list)
    score_rectangle_items: list[ScoreRectangleResultItem] = field(default_factory=list)
    image_items: list[ImageResultItem] = field(default_factory=list)
    table_items: list[TableResultItem] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        return (len(self.value_items) + len(self.rectangle_items) +
                len(self.line_items) + len(self.score_rectangle_items) +
                len(self.image_items) + len(self.table_items))

    @property
    def all_geometry_items(self) -> list:
        """All items that have spatial coordinates for image overlay."""
        items = []
        items.extend(self.rectangle_items)
        items.extend(self.score_rectangle_items)
        items.extend(self.line_items)
        return items

    def to_dict(self) -> dict:
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
# Result Presenters — ported from WPF H.VisionMaster.ResultPresenter/*
# ═══════════════════════════════════════════════════════════════════════════

class ValueResultPresenter:
    """Presents individual value items as key-value pairs.

    Ported from C# ValueResultPresenter.
    Generates rows suitable for a 2-column table (Property | Value).
    """

    def __init__(self, node_result: NodeResult = None):
        self._result = node_result

    def set_result(self, result: NodeResult):
        self._result = result

    def get_rows(self) -> list[tuple[str, str, ResultItemType]]:
        """Return rows as (name, value_str, type) for table display."""
        if self._result is None:
            return []
        rows: list[tuple[str, str, ResultItemType]] = []
        rows.append(("节点名称", self._result.node_name, ResultItemType.VALUE))
        rows.append(("节点类型", self._result.node_type, ResultItemType.VALUE))
        rows.append(("执行状态", "成功" if self._result.success else "失败",
                     ResultItemType.VALUE))
        rows.append(("消息", self._result.message or "-", ResultItemType.VALUE))
        if self._result.execution_time_ms > 0:
            rows.append(("耗时", f"{self._result.execution_time_ms:.1f} ms",
                         ResultItemType.VALUE))
        for item in self._result.value_items:
            rows.append((item.name, str(item.value) if item.value is not None else "-",
                         item.item_type))
        return rows


class DataGridResultPresenter:
    """Presents structured result items with geometry data for grid display.

    Ported from C# DataGridResultPresenter.
    Generates rows with columns: Name | Value | X | Y | Width | Height | Score.
    Supports image viewer linkage via geometry coordinates.
    """

    COLUMNS = ("名称", "值", "X", "Y", "宽度", "高度", "分数")

    def __init__(self, node_result: NodeResult = None):
        self._result = node_result
        self._selected_rows: set[int] = set()

    def set_result(self, result: NodeResult):
        self._result = result
        self._selected_rows.clear()

    def get_rows(self) -> list[dict]:
        """Return rows as list of dicts with column values."""
        if self._result is None:
            return []
        rows: list[dict] = []
        for item in self._result.rectangle_items:
            rows.append({"名称": item.name, "值": str(item.value or ""),
                         "X": str(item.x), "Y": str(item.y),
                         "宽度": str(item.width), "高度": str(item.height),
                         "分数": "", "type": ResultItemType.RECTANGLE,
                         "geometry": item.rect})
        for item in self._result.score_rectangle_items:
            rows.append({"名称": item.name, "值": str(item.value or ""),
                         "X": str(item.x), "Y": str(item.y),
                         "宽度": str(item.width), "高度": str(item.height),
                         "分数": f"{item.score:.3f}", "type": ResultItemType.SCORE_RECTANGLE,
                         "geometry": item.rect})
        for item in self._result.line_items:
            rows.append({"名称": item.name, "值": str(item.value or ""),
                         "X": f"{item.x1:.1f}", "Y": f"{item.y1:.1f}",
                         "宽度": f"{item.x2:.1f}", "高度": f"{item.y2:.1f}",
                         "分数": "", "type": ResultItemType.LINE,
                         "geometry": item.points})
        return rows

    def select_row(self, index: int) -> dict | None:
        """Select a row and return its geometry for image viewer linkage."""
        rows = self.get_rows()
        if 0 <= index < len(rows):
            self._selected_rows.add(index)
            return rows[index]
        return None

    def deselect_all(self):
        self._selected_rows.clear()

    @property
    def selected_indices(self) -> set[int]:
        return set(self._selected_rows)

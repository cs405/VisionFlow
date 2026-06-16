"""
条件分支框架
架构:
  ConditionsPresenter → 管理多个 ConditionBranch
    每个 ConditionBranch → 关联 input_node + output_node + conditions[] + operate
      每个 PropertyCondition → property_name + filter_operate + value
"""

from __future__ import annotations

from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.node_base import NodeBase


# =============================================================================
# ConditionOperate — 条件组合模式
# =============================================================================

class ConditionOperate(Enum):
    """条件组合模式

    决定 ConditionBranch 内多个 PropertyCondition 如何组合判定。
    """
    ALL = "all"           # 满足所有条件 (AND)
    ANY = "any"           # 满足任一条件 (OR)
    ANY_NOT = "any_not"   # 任一条件不满足 (NOT ANY)
    NONE = "none"         # 全部不满足条件 (NOT ALL)


# =============================================================================
# FilterOperate — 属性过滤运算符
# =============================================================================

class FilterOperate(Enum):
    """属性过滤运算符

    通用: EQUALS, NOT_EQUALS
    数值: GREATER, LESS, GREATER_EQUAL, LESS_EQUAL
    文本: CONTAINS, NOT_CONTAINS, STARTS_WITH, ENDS_WITH, IS_SET, NOT_SET
    """
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER = ">"
    LESS = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_SET = "is_set"
    NOT_SET = "not_set"

    @classmethod
    def numeric_operators(cls):
        return {cls.EQUALS, cls.NOT_EQUALS, cls.GREATER, cls.LESS,
                cls.GREATER_EQUAL, cls.LESS_EQUAL}

    @classmethod
    def text_operators(cls):
        return {cls.EQUALS, cls.NOT_EQUALS, cls.CONTAINS, cls.NOT_CONTAINS,
                cls.STARTS_WITH, cls.ENDS_WITH, cls.IS_SET, cls.NOT_SET}


# =============================================================================
# PropertyCondition — 单条属性过滤规则
# =============================================================================

class PropertyCondition:
    """单条属性过滤规则

    对某个属性名执行一个过滤操作，判断是否匹配。
    """

    def __init__(self, property_name: str = "",
                 filter_operate: FilterOperate = FilterOperate.EQUALS,
                 value: Any = None):
        self.property_name = property_name
        self.filter_operate = filter_operate
        self.value = value

    def is_match(self, obj: Any) -> bool:
        """对目标对象评估此条件"""
        if obj is None:
            return False
        actual = self._get_property_value(obj)
        return self._evaluate(actual)

    def _get_property_value(self, obj: Any) -> Any:
        """从对象中获取属性值。支持 dict 和对象属性两种方式。"""
        if isinstance(obj, dict):
            return obj.get(self.property_name)
        return getattr(obj, self.property_name, None)

    def _evaluate(self, actual: Any) -> bool:
        op = self.filter_operate
        expected = self.value

        # IS_SET / NOT_SET
        if op == FilterOperate.IS_SET:
            return actual is not None and actual != ""
        if op == FilterOperate.NOT_SET:
            return actual is None or actual == ""

        if actual is None:
            return False

        # 数值比较
        if op in (FilterOperate.GREATER, FilterOperate.LESS,
                  FilterOperate.GREATER_EQUAL, FilterOperate.LESS_EQUAL):
            try:
                a, b = float(actual), float(expected)
            except (ValueError, TypeError):
                return False
            if op == FilterOperate.GREATER:
                return a > b
            if op == FilterOperate.LESS:
                return a < b
            if op == FilterOperate.GREATER_EQUAL:
                return a >= b
            return a <= b

        # EQUALS / NOT_EQUALS — 先尝试数值，再回退到文本
        if op in (FilterOperate.EQUALS, FilterOperate.NOT_EQUALS):
            eq = self._values_equal(actual, expected)
            return eq if op == FilterOperate.EQUALS else not eq

        # 文本操作
        a_str = str(actual)
        b_str = str(expected)
        if op == FilterOperate.CONTAINS:
            return b_str in a_str
        if op == FilterOperate.NOT_CONTAINS:
            return b_str not in a_str
        if op == FilterOperate.STARTS_WITH:
            return a_str.startswith(b_str)
        if op == FilterOperate.ENDS_WITH:
            return a_str.endswith(b_str)

        return False

    @staticmethod
    def _values_equal(a: Any, b: Any) -> bool:
        """比较两个值是否相等，支持布尔、数值、字符串的类型自适应比较。"""
        if a is b or a == b:
            return True
        if isinstance(a, bool) and not isinstance(b, bool):
            b = PropertyCondition._str_to_bool(b)
        elif isinstance(b, bool) and not isinstance(a, bool):
            a = PropertyCondition._str_to_bool(a)
        # 仅当双方都是数值类型时才进行浮点比较，避免 "001" == "1" 误判
        a_is_num = isinstance(a, (int, float)) and not isinstance(a, bool)
        b_is_num = isinstance(b, (int, float)) and not isinstance(b, bool)
        if a_is_num and b_is_num:
            try:
                return float(a) == float(b)
            except (ValueError, TypeError):
                pass
        return str(a) == str(b)

    @staticmethod
    def _str_to_bool(val: Any) -> Any:
        """将常见真假字符串转为 bool，无法识别时返回原值使得回退到字符串比较。"""
        s = str(val).strip().lower()
        if s in {"1", "true", "yes", "y", "on", "是"}:
            return True
        if s in {"0", "false", "no", "n", "off", "否"}:
            return False
        return val

    def display_text(self) -> str:
        return f"{self.property_name} {self.filter_operate.value} {self.value}"

    def to_dict(self) -> dict:
        return {
            "property_name": self.property_name,
            "filter_operate": self.filter_operate.name,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PropertyCondition":
        op_name = data.get("filter_operate", "EQUALS")
        # 兼容旧格式的 operator 字段
        if "operator" in data:
            op_name = cls._migrate_operator(data["operator"])
        try:
            op = FilterOperate[op_name]
        except KeyError:
            op = FilterOperate.EQUALS
        return cls(
            property_name=data.get("property_name", ""),
            filter_operate=op,
            value=data.get("value", data.get("threshold", "")),
        )

    @staticmethod
    def _migrate_operator(old_op: str) -> str:
        """将旧格式运算符映射为 FilterOperate 名称。"""
        mapping = {
            ">": "GREATER", "<": "LESS",
            ">=": "GREATER_EQUAL", "<=": "LESS_EQUAL",
            "==": "EQUALS", "!=": "NOT_EQUALS",
            "contains": "CONTAINS", "not contains": "NOT_CONTAINS",
        }
        return mapping.get(old_op, "EQUALS")


# =============================================================================
# ConditionBranch — 单条条件分支
# =============================================================================

class ConditionBranch:
    """单条条件分支

    一条分支 = 上游输入节点 + 一组属性条件 + 条件组合模式 + 下游输出节点。
    """

    def __init__(self, branch_id: str = ""):
        import uuid
        self.branch_id = branch_id or str(uuid.uuid4())[:8]

        # 输入节点引用
        self.selected_input_node_id: str = ""
        self._selected_input_node: "NodeBase | None" = None

        # 输出节点引用
        self.selected_output_node_id: str = ""
        self._selected_output_node: "NodeBase | None" = None

        # 条件组合模式
        self.condition_operate: ConditionOperate = ConditionOperate.ALL

        # 条件列表
        self.conditions: list[PropertyCondition] = []

    # -- 节点引用属性 --

    @property
    def selected_input_node(self) -> "NodeBase | None":
        return self._selected_input_node

    @selected_input_node.setter
    def selected_input_node(self, value: "NodeBase | None"):
        self._selected_input_node = value
        self.selected_input_node_id = value.node_id if value else ""

    @property
    def selected_output_node(self) -> "NodeBase | None":
        return self._selected_output_node

    @selected_output_node.setter
    def selected_output_node(self, value: "NodeBase | None"):
        self._selected_output_node = value
        self.selected_output_node_id = value.node_id if value else ""

    # -- 评估 --

    def is_match(self, input_obj: Any) -> bool:
        """评估此分支的所有条件是否匹配输入对象。

        根据 condition_operate 组合多个 PropertyCondition 的结果。
        """
        if not self.conditions:
            return False

        if self.condition_operate == ConditionOperate.ALL:
            return all(c.is_match(input_obj) for c in self.conditions)
        if self.condition_operate == ConditionOperate.ANY:
            return any(c.is_match(input_obj) for c in self.conditions)
        if self.condition_operate == ConditionOperate.ANY_NOT:
            return any(not c.is_match(input_obj) for c in self.conditions)
        if self.condition_operate == ConditionOperate.NONE:
            return not any(c.is_match(input_obj) for c in self.conditions)
        return False

    def add_condition(self, condition: PropertyCondition = None):
        """添加一条条件。"""
        if condition is None:
            condition = PropertyCondition()
        self.conditions.append(condition)

    def remove_condition(self, index: int):
        if 0 <= index < len(self.conditions):
            self.conditions.pop(index)

    # -- 序列化 --

    def to_dict(self) -> dict:
        return {
            "branch_id": self.branch_id,
            "selected_input_node_id": self.selected_input_node_id,
            "selected_output_node_id": self.selected_output_node_id,
            "condition_operate": self.condition_operate.name,
            "conditions": [c.to_dict() for c in self.conditions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConditionBranch":
        op_name = data.get("condition_operate", "ALL")
        try:
            op = ConditionOperate[op_name]
        except KeyError:
            op = ConditionOperate.ALL

        branch = cls(branch_id=data.get("branch_id", ""))
        branch.selected_input_node_id = data.get("selected_input_node_id", "")
        branch.selected_output_node_id = data.get("selected_output_node_id", "")
        branch.condition_operate = op
        branch.conditions = [PropertyCondition.from_dict(c)
                            for c in data.get("conditions", [])]
        return branch


# =============================================================================
# ConditionsPresenter — 条件分支集合管理器
# =============================================================================

class ConditionsPresenter:
    """条件分支集合管理器

    管理 ConditionNodeData 的多个 ConditionBranch，负责:
      - 添加/删除分支
      - 从节点加载数据（恢复节点引用）
      - 评估所有分支找出匹配项
    """

    def __init__(self):
        self.branches: list[ConditionBranch] = []
        self._selected_index: int = -1
        self._owner_node: "NodeBase | None" = None

    @property
    def selected_index(self) -> int:
        return self._selected_index

    @selected_index.setter
    def selected_index(self, value: int):
        self._selected_index = value

    @property
    def selected_branch(self) -> ConditionBranch | None:
        if 0 <= self._selected_index < len(self.branches):
            return self.branches[self._selected_index]
        return None

    # -- 分支管理 --

    def add_branch(self, branch: ConditionBranch = None) -> ConditionBranch:
        if branch is None:
            branch = ConditionBranch()
        self.branches.append(branch)
        if self._selected_index < 0:
            self._selected_index = 0
        return branch

    def remove_branch(self, index: int):
        if 0 <= index < len(self.branches):
            self.branches.pop(index)
            if self._selected_index >= len(self.branches):
                self._selected_index = len(self.branches) - 1

    def clear(self):
        self.branches.clear()
        self._selected_index = -1

    # -- 数据加载 --

    def load_data(self, owner_node: "NodeBase"):
        """从所属节点加载数据，恢复所有分支中的节点引用。
        """
        self._owner_node = owner_node
        all_nodes = owner_node.get_all_from_this_node_datas()
        to_nodes = owner_node.to_node_datas

        for branch in self.branches:
            for node in all_nodes:
                if node.node_id == branch.selected_input_node_id:
                    branch._selected_input_node = node
                    break
            for node in to_nodes:
                if node.node_id == branch.selected_output_node_id:
                    branch._selected_output_node = node
                    break

    # -- 评估 --

    def get_matching_branches(self, upstream_snapshots: dict[str, Any] = None) -> list[ConditionBranch]:
        """返回所有匹配的条件分支
        """
        matches: list[ConditionBranch] = []
        for branch in self.branches:
            if not branch.selected_input_node_id:
                continue
            input_obj = upstream_snapshots.get(branch.selected_input_node_id) if upstream_snapshots else None
            if branch.is_match(input_obj):
                matches.append(branch)
        return matches

    def get_matching_output_node_ids(self, upstream_snapshots: dict[str, Any] = None) -> set[str]:
        """返回所有匹配分支指向的输出节点ID集合。"""
        result: set[str] = set()
        for branch in self.get_matching_branches(upstream_snapshots):
            if branch.selected_output_node_id:
                result.add(branch.selected_output_node_id)
        return result

    # -- 上游快照 --

    def collect_upstream_snapshots(self) -> dict[str, dict[str, Any]]:
        """为每个上游节点收集属性快照，供条件评估使用。

        返回 {node_id: {property_name: value, ...}, ...}
        """
        snapshots: dict[str, dict[str, Any]] = {}
        if self._owner_node is None:
            return snapshots

        from core.node_base import VisionNodeData, PropertyGroupNames
        all_nodes = self._owner_node.get_all_from_this_node_datas()

        for node in all_nodes:
            if node is self._owner_node:
                continue
            props: dict[str, Any] = {}
            if isinstance(node, VisionNodeData):
                props["message"] = node.message
                props["mat"] = node.mat
                props["name"] = node.name
                for prop_name, prop_desc in node.get_property_descriptors():
                    val = getattr(node, prop_name, None)
                    props[prop_name] = val
                    # 同时以 "节点名.属性名" 的形式记录（兼容旧格式）
                    props[f"{node.name}.{prop_name}"] = val
            snapshots[node.node_id] = props
        return snapshots

    # -- 序列化 --

    def to_dict(self) -> dict:
        return {
            "selected_index": self._selected_index,
            "branches": [b.to_dict() for b in self.branches],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConditionsPresenter":
        presenter = cls()
        presenter._selected_index = data.get("selected_index", -1)
        presenter.branches = [ConditionBranch.from_dict(b)
                             for b in data.get("branches", [])]

        # 兼容旧格式：扁平 conditions 列表
        old_conditions = data.get("conditions")
        if old_conditions and not presenter.branches:
            presenter._migrate_from_old_format(old_conditions)

        return presenter

    def _migrate_from_old_format(self, old_conditions: list[dict]):
        """将旧版 VisionPropertyCondition 列表迁移为新的 branch 格式。

        旧格式: [{"property_name":..., "operator":..., "threshold":..., "output_node_id":...}, ...]
        迁移策略: 每条旧条件 → 一个独立的 ConditionBranch
        """
        for old in old_conditions:
            pc = PropertyCondition(
                property_name=old.get("property_name", ""),
                filter_operate=FilterOperate[PropertyCondition._migrate_operator(
                    old.get("operator", ">"))],
                value=old.get("threshold", ""),
            )
            branch = ConditionBranch()
            branch.selected_output_node_id = old.get("output_node_id", "")
            branch.condition_operate = ConditionOperate.ALL
            branch.conditions = [pc]
            self.branches.append(branch)


# 向后兼容别名（已弃用，请使用 ConditionsPresenter）
ConditionsPrensenter = ConditionsPresenter

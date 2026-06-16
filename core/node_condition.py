"""
条件分支与并行同步节点
包含逻辑模块标记接口、条件分支节点、旧版条件规则、并行同步屏障节点
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import threading

from core.data_packet import FlowableResult, FlowableInvokeMode
from core.events import EventType, event_system
from core.node_base import NodeBase, Property, PropertyGroupNames, Port, LinkData
from core.node_vision import VisionNodeData

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


# =============================================================================
# LogicModuleNode - 逻辑模块标记接口
# =============================================================================

class LogicModuleNode:
    """标记接口：实现此接口的节点自动归入"逻辑模块"分组。
    解耦了"属于逻辑模块"和"是 ConditionNodeData 子类"之间的强绑定。
    """
    pass


# ConditionNodeData - 条件分支节点
# =============================================================================

class ConditionNodeData(VisionNodeData):
    """基于上游节点结果评估条件并实现流程分支的节点。
    """

    def __init__(self):
        super().__init__()
        self.use_invoked_part = False

    # -- ConditionsPresenter (lazy init) --

    @property
    def conditions_presenter(self):
        """获取条件分支集合管理器。延迟导入避免循环依赖。"""
        if getattr(self, '_conditions_presenter', None) is None:
            from core.conditions import ConditionsPresenter
            self._conditions_presenter = ConditionsPresenter()
        return self._conditions_presenter

    @conditions_presenter.setter
    def conditions_presenter(self, value):
        self._conditions_presenter = value

    # -- 兼容旧 API (deprecated, 映射到 presenter.branches[0]) --

    @property
    def conditions(self) -> list:
        """[兼容] 获取旧版 VisionPropertyCondition 列表。新代码应使用 conditions_presenter.branches。"""
        return self._legacy_conditions()

    @conditions.setter
    def conditions(self, value: list):
        self._set_legacy_conditions(value)

    def _legacy_conditions(self) -> list:
        """将 presenter 的 branches 转回旧版 VisionPropertyCondition 格式（仅用于兼容）。"""
        result = []
        for branch in self.conditions_presenter.branches:
            for cond in branch.conditions:
                result.append(VisionPropertyCondition(
                    property_name=cond.property_name,
                    operator=cond.filter_operate.value,
                    threshold=cond.value,
                    output_node_id=branch.selected_output_node_id,
                ))
        return result

    def _set_legacy_conditions(self, value: list):
        from core.conditions import ConditionBranch, PropertyCondition, FilterOperate
        self.conditions_presenter.clear()
        for old in value:
            op_name = PropertyCondition._migrate_operator(getattr(old, 'operator', '>'))
            pc = PropertyCondition(
                property_name=getattr(old, 'property_name', ''),
                filter_operate=FilterOperate[op_name],
                value=getattr(old, 'threshold', ''),
            )
            branch = ConditionBranch()
            branch.selected_output_node_id = getattr(old, 'output_node_id', '')
            branch.conditions = [pc]
            self.conditions_presenter.branches.append(branch)

    def add_condition(self, condition: "VisionPropertyCondition"):
        from core.conditions import ConditionBranch, PropertyCondition, FilterOperate
        op_name = PropertyCondition._migrate_operator(condition.operator)
        pc = PropertyCondition(
            property_name=condition.property_name,
            filter_operate=FilterOperate[op_name],
            value=condition.threshold,
        )
        branch = ConditionBranch()
        branch.selected_output_node_id = condition.output_node_id
        branch.conditions = [pc]
        self.conditions_presenter.branches.append(branch)

    def remove_condition(self, index: int):
        self.conditions_presenter.remove_branch(index)

    def evaluate_conditions(self, upstream_results: dict[str, Any]) -> list["VisionPropertyCondition"]:
        upstream_snapshots = self.conditions_presenter.collect_upstream_snapshots()
        matches = []
        for branch in self.conditions_presenter.branches:
            snap = upstream_snapshots.get(branch.selected_input_node_id, {})
            if branch.is_match(snap):
                for cond in branch.conditions:
                    matches.append(VisionPropertyCondition(
                        property_name=cond.property_name,
                        operator=cond.filter_operate.value,
                        threshold=cond.value,
                        output_node_id=branch.selected_output_node_id,
                    ))
        return matches

    def get_condition_candidates(self) -> list[tuple[str, Any]]:
        """为条件编辑器收集可评估的上游节点属性。返回 [(node_name.prop_name, value), ...]"""
        candidates: list[tuple[str, Any]] = []
        seen: set[str] = set()
        for node in self.from_node_datas:
            if not isinstance(node, VisionNodeData):
                continue
            node_name = node.name or type(node).__name__
            for prop_name, prop_desc in node.get_property_descriptors():
                key = f"{node_name}.{prop_name}"
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((key, getattr(node, prop_name, None)))
            if node.message and f"{node_name}.message" not in seen:
                seen.add(f"{node_name}.message")
                candidates.append((f"{node_name}.message", node.message))
        return candidates

    def collect_upstream_results(self) -> dict[str, Any]:
        return dict(self.get_condition_candidates())

    # -- 核心调用 --

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        """执行条件分支逻辑。委托给 ConditionsPresenter 评估。
        实际路由由 get_flowable_output_links() 控制。
        """
        from_node = None
        for n in self.from_node_datas:
            if isinstance(n, VisionNodeData):
                from_node = n
                break
        if from_node is None:
            return self.break_(None, "没有找到上游 VisionNodeData 节点")

        # 传播上游 _original_mat（ROINodeData.invoke 的正常行为，条件分支也需要）
        if isinstance(from_node, VisionNodeData):
            upstream_original = getattr(from_node, '_original_mat', None)
            if upstream_original is not None:
                self._original_mat = upstream_original
            elif from_node.mat is not None:
                self._original_mat = from_node.mat.copy()
            # 传播上游累积裁剪偏移量（ROINodeData.invoke 的正常行为）
            self._crop_chain_offset = getattr(from_node, '_crop_chain_offset', (0, 0, 0, 0))

        src_data = self._find_source_node(diagram)

        # 加载节点数据到 presenter（恢复节点引用）
        self.conditions_presenter.load_data(self)

        # 调用 invoke_core 执行透传
        return self._invoke_action(lambda: self.invoke_core(src_data, from_node or src_data, diagram))

    def get_flowable_output_links(self, diagram: "WorkflowEngine") -> list["LinkData"]:
        """根据条件分支匹配结果，路由到对应的输出端口。
        """
        self.conditions_presenter.load_data(self)
        upstream_snapshots = self.conditions_presenter.collect_upstream_snapshots()
        matching_output_ids = self.conditions_presenter.get_matching_output_node_ids(upstream_snapshots)

        if not matching_output_ids:
            # 无匹配：检查是否有活动端口名（如 PixelThresholdConditionNode 设置的）
            active_port_name = getattr(self, '_active_output_port_name', None)
            if active_port_name:
                active_ids = {p.port_id for p in self.get_output_ports()
                             if p.name == active_port_name}
                return [l for l in (diagram.get_all_links() if diagram else [])
                        if l.from_node_id == self.node_id and l.from_port_id in active_ids]
            return []

        # 路由到匹配分支指向的输出节点
        result: list["LinkData"] = []
        for link in (diagram.get_all_links() if diagram else []):
            if link.from_node_id != self.node_id:
                continue
            if link.to_node_id in matching_output_ids:
                result.append(link)
        return result

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        return self.ok(from_node_data.mat if from_node_data else None)

    # -- 序列化 --

    def to_dict(self) -> dict:
        data = super().to_dict()
        presenter = getattr(self, '_conditions_presenter', None)
        if presenter is not None:
            data["conditions_presenter"] = presenter.to_dict()
        return data

    def restore_from_dict(self, data: dict) -> "ConditionNodeData":
        super().restore_from_dict(data)
        from core.conditions import ConditionsPresenter
        presenter_data = data.get("conditions_presenter")
        if presenter_data is not None:
            self._conditions_presenter = ConditionsPresenter.from_dict(presenter_data)
        elif "conditions" in data:
            # 兼容旧格式
            self._conditions_presenter = ConditionsPresenter.from_dict({"conditions": data["conditions"]})
        return self


# =============================================================================
# VisionPropertyCondition — 旧版条件规则（保留用于兼容）
# =============================================================================

class VisionPropertyCondition:
    """[兼容] 旧版单条条件规则。新代码应使用 core.conditions.PropertyCondition + ConditionBranch。

    该类的功能已迁移至:
      - PropertyCondition (单条过滤)
      - ConditionBranch (分支 = 输入节点 + 条件 + 输出节点)
      - ConditionsPresenter (分支集合管理)

    保留此类用于:
      1. GUI 兼容 (condition_editor.py)
      2. 旧项目文件反序列化
    """

    SUPPORTED_OPERATORS = (">", "<", ">=", "<=", "==", "!=", "contains", "not contains")

    def __init__(self, property_name: str = "", operator: str = ">",
                 threshold: Any = 0.0, output_node_id: str = ""):
        self.property_name = property_name
        self.operator = operator
        self.threshold = threshold
        self.output_node_id = output_node_id

    def display_text(self) -> str:
        target = f" → {self.output_node_id}" if self.output_node_id else ""
        return f"{self.property_name} {self.operator} {self.threshold}{target}"

    def evaluate(self, upstream_results: dict[str, Any]) -> bool:
        from core.conditions import PropertyCondition, FilterOperate
        op_name = PropertyCondition._migrate_operator(self.operator)
        try:
            filter_op = FilterOperate[op_name]
        except KeyError:
            filter_op = FilterOperate.EQUALS
        pc = PropertyCondition(
            property_name=self.property_name,
            filter_operate=filter_op,
            value=self.threshold,
        )
        return pc.is_match(upstream_results)

    def to_dict(self) -> dict:
        return {
            "property_name": self.property_name,
            "operator": self.operator,
            "threshold": self.threshold,
            "output_node_id": self.output_node_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VisionPropertyCondition":
        return cls(
            property_name=data.get("property_name", ""),
            operator=data.get("operator", ">"),
            threshold=data.get("threshold", 0.0),
            output_node_id=data.get("output_node_id", ""),
        )


# =============================================================================
# WaitAllParallelNodeData - 并行执行同步屏障
# =============================================================================

class WaitAllParallelNodeData(VisionNodeData, LogicModuleNode):
    """等待所有并行上游节点完成后才继续执行的同步屏障节点。

    作为同步屏障：统计来自并行分支的调用次数，
    只有当所有并行前驱节点都完成后才继续执行。
    """
    # 节点分组（用于UI分类）
    __group__ = "逻辑模块"

    def __init__(self):
        super().__init__()
        # 节点显示名称
        self.name = "并行等待"
        # 已完成的并行分支计数
        self._result_count = 0
        self._cached_parallel_count: int = 0
        self._parallel_count_cached: bool = False
        self._result_lock = threading.Lock()

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        """统计并行调用次数。只有当所有分支都完成时才继续执行。"""
        # 获取第一个上游节点
        from_node = None
        for n in self.from_node_datas:
            if isinstance(n, VisionNodeData):
                from_node = n
                break

        # 查找源节点
        src_data = self._find_source_node(diagram)

        # 调用每个并行分支完成时的处理
        self.on_parallel_from_invoked(src_data, from_node, diagram)

        # 增加完成计数并检查（锁内原子操作，消除 TOCTOU 竞态）
        with self._result_lock:
            self._result_count += 1
            if not self._parallel_count_cached:
                self._cached_parallel_count = sum(
                    1 for n in self.from_node_datas
                    if hasattr(n, 'invoke_mode') and n.invoke_mode == FlowableInvokeMode.PARALLEL
                    and getattr(n, '_execution_state', None) != 'error'
                )
                self._parallel_count_cached = True
            all_done = self._result_count >= self._cached_parallel_count
            if all_done:
                self._result_count = 0
                self._parallel_count_cached = False
        if all_done:
            # 调用所有并行分支完成时的处理
            return self._invoke_action(lambda: self.on_all_parallels_invoked(src_data, from_node, diagram))
        else:
            # 还有分支未完成，中断等待
            return self.break_(from_node.mat if from_node else None, "等待其他并行分支完成")

    def on_parallel_from_invoked(self, src_image_node_data, from_node, diagram):
        """每个并行分支完成时调用。子类可重写以累积结果。"""
        pass

    def on_all_parallels_invoked(self, src_image_node_data, from_node, diagram) -> FlowableResult:
        """所有并行分支都完成时调用。子类可重写以合并结果。"""
        return self.ok(from_node.mat if from_node else None)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        """核心调用方法（透传上游图像）"""
        return self.ok(from_node_data.mat if from_node_data else None)

    def to_dict(self) -> dict:
        """序列化节点为字典"""
        data = super().to_dict()
        data["result_count"] = self._result_count
        return data

    def restore_from_dict(self, data: dict) -> "WaitAllParallelNodeData":
        super().restore_from_dict(data)
        self._result_count = data.get("result_count", 0)
        return self

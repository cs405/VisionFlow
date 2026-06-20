"""数据收集节点 — 收集上游节点的 matched 结果并进行逻辑与运算。

从所有上游节点读取 `matched` 属性（bool），进行逻辑 AND：
- 全部为 True  → 绿色 bar，输出 matched=True
- 任意为 False → 红色 bar，输出 matched=False

可级联：多个数据收集节点可以接入另一个数据收集节点。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.node_condition import LogicModuleNode
from core.data_packet import FlowableResult

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class DataCollectorNode(OpenCVNodeDataBase, LogicModuleNode):
    """数据收集节点：对上游节点的 matched 结果做逻辑与运算。

    读取上游节点的 `matched` 属性（模板匹配节点或数据收集节点），
    全部为 True 时自身 matched=True（绿色 bar），否则 matched=False（红色 bar）。
    """

    __group__ = "逻辑模块"

    # 收集结果（与模板匹配节点的 matched 同名，方便级联）
    matched = Property(False, name="是否匹配", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 上游 true 计数
    true_count = Property(0, name="匹配数", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 上游总数
    total_count = Property(0, name="总输入数", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "数据收集"

    def _reset_for_new_execution(self):
        """每次工作流启动时重置结果属性，避免上次运行残留值。"""
        self.matched = False
        self.true_count = 0
        self.total_count = 0

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)

        # 收集上游节点的 matched 值
        upstream: list[tuple[str, bool]] = []
        for node in self.from_node_datas:
            if node is self:
                continue
            m = getattr(node, "matched", None)
            upstream.append((node.name, m is True))

        self.total_count = len(upstream)
        self.true_count = sum(1 for _, v in upstream if v)

        # 逻辑与：全部为 True 才为 True
        all_true = self.total_count > 0 and self.true_count == self.total_count
        self.matched = all_true

        # 构造消息
        parts = [f"{n}={v}" for n, v in upstream] if upstream else ["无上游输入"]
        status = "全部匹配" if all_true else ("存在未匹配" if upstream else "等待输入")
        msg = f"{status}: {' & '.join(parts)}"

        if all_true:
            return self.ok(mat, msg)
        else:
            return self.error(mat, msg)

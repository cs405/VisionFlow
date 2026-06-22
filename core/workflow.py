"""工作流引擎 - 编排节点图执行。

处理：
  - 节点图拓扑结构（节点 + 连线）
  - 执行顺序的拓扑排序
  - 顺序执行和并行执行
  - 执行上下文和数据流
  - 流程控制（OK/Error/Break 路由）
"""

import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum, auto
from typing import Any, Callable

from core.node_base import (
    NodeBase, LinkData, PortDock,
)
from core.node_vision import VisionNodeData
from core.data_packet import FlowableResult, FlowableResultState
from core.events import EventType, event_system
from core.result_presenter import VisionMessage


class WorkflowState(Enum):
    """工作流引擎的执行状态"""
    IDLE = auto()        # 空闲状态
    RUNNING = auto()     # 运行中
    PAUSED = auto()      # 已暂停
    STOPPED = auto()     # 已停止
    COMPLETED = auto()   # 已完成
    ERROR = auto()       # 错误状态

    def can_start(self) -> bool:
        """判断是否可以启动（未在运行中）"""
        return self != WorkflowState.RUNNING

    def can_stop(self) -> bool:
        """判断是否可以停止（正在运行中）"""
        return self == WorkflowState.RUNNING

    def can_reset(self) -> bool:
        """判断是否可以重置（始终可用）"""
        return True


class DiagramFlowableMode(Enum):
    """运行模式 — 控制执行粒度"""
    NODE = 0   # 按节点运行
    LINK = 1   # 按节点+连线运行
    PORT = 2   # 按节点+连线+端口运行


class WorkflowEngine:
    """管理节点图并执行它。
    每个 WorkflowEngine 实例代表一个图表/文档。
    """

    def __init__(self, name: str = "新建流程"):
        self.name = name                                                    # 工作流名称
        self.state: WorkflowState = WorkflowState.IDLE                      # 当前执行状态：默认空闲
        self._nodes: dict[str, NodeBase] = {}                               # 节点字典：键为节点ID，值为节点对象
        self._links: list[LinkData] = []                                    # 连线列表
        self._max_workers: int = 4                                          # 最大并行工作线程数
        self._executor: ThreadPoolExecutor | None = None                    # 可复用的线程池（惰性创建，实例级别共享，dispose() 时关闭）
        self._invoke_count: int = 0                                         # 调用计数
        self.result_image_source: Any = None                                # 结果图像源
        self.flowable_mode: DiagramFlowableMode = DiagramFlowableMode.NODE  # 流程执行模式
        self.message: str = ""                                              # 当前消息文本
        self.messages: list[VisionMessage] = []                             # 历史消息列表
        self._message_index: dict[str, VisionMessage] = {}                  # 消息索引：按节点 node_id 快速查找已有消息（O(1) 替代 O(n) 遍历）
        self.current_message = None                                         # 当前聚合消息
        self._messages_lock = threading.Lock()                              # 线程锁，保护消息列表的线程安全
        self._history_callbacks: list[Callable] = []                        # 历史变更回调列表（用于UI绑定）
        self._levels_cache: tuple[tuple[str, ...], list[list[str]]] | None = None  # 层级缓存（拓扑变更时失效）
        self._topo_cache: list[str] | None = None  # 拓扑排序缓存（拓扑变更时失效）
        self._rev_adj: dict[str, list[str]] | None = None  # 反向邻接映射（拓扑变更时失效），用于 _group_by_levels() O(1) 查前驱

    # -- 节点管理 --

    def add_node(self, node: NodeBase) -> str:
        """向图表中添加节点。返回节点的ID"""
        node.diagram_data = self                                            # 设置节点的工作流引擎的图表数据引用
        self._nodes[node.node_id] = node                                    # 将节点添加到字典
        event_system.publish(EventType.NODE_ADDED, sender=self, node=node)  # 发布节点添加事件
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)        # 发布图表变更事件
        self._invalidate_levels_cache()                                     # 拓扑结构变更，失效层级缓存
        return node.node_id

    def remove_node(self, node_id: str):
        """移除节点及其所有相关连线"""
        node = self._nodes.pop(node_id, None)  # 从字典中弹出节点
        if node is None:
            return
        # 移除与该节点相关的所有连线
        new_links = []
        for l in self._links:
            if l.from_node_id != node_id and l.to_node_id != node_id:
                new_links.append(l)
        self._links = new_links
        # 从其他节点的上下游列表中移除该节点
        for n in self._nodes.values():
            # 过滤上游
            new_from = []
            for x in n.from_node_datas:
                if x.node_id != node_id:
                    new_from.append(x)
            n.from_node_datas = new_from

            # 过滤下游
            new_to = []
            for x in n.to_node_datas:
                if x.node_id != node_id:
                    new_to.append(x)
            n.to_node_datas = new_to
        # 发布节点移除事件
        event_system.publish(EventType.NODE_REMOVED, sender=self, node=node)
        # 发布图表变更事件
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self._invalidate_levels_cache()

    def get_node_by_id(self, node_id: str) -> NodeBase | None:
        """根据ID获取节点"""
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> list[NodeBase]:
        """获取所有节点"""
        return list(self._nodes.values())

    # ── 历史消息管理 ──

    def on_history_changed(self, callback: Callable):
        """注册历史消息变更时的回调函数

        回调函数不接收参数 —— 调用者应根据需要调用 get_messages_snapshot()。
        回调可能在任何线程被调用；调用者应根据需要将调用调度到目标线程。
        """
        self._history_callbacks.append(callback)

    def off_history_changed(self, callback: Callable):
        """移除之前注册的历史消息变更回调"""
        try:
            self._history_callbacks.remove(callback)
        except ValueError:
            pass

    def _notify_history_callbacks(self):
        """调用所有已注册的历史变更回调"""
        for callback in self._history_callbacks:
            try:
                callback()
            except Exception:
                pass

    def on_node_completed(self, node: VisionNodeData, state: str, time_span: str):
        """ 添加/更新历史消息

        与 UI 解耦：WorkflowEngine 拥有 Messages 集合，
        ResultPanel 从中读取。每个工作流都有自己的 Messages，
        切换标签页时历史记录自动隔离。

        线程安全：从 ThreadPoolExecutor 的工作线程调用。
        """
        # 检查是否启用输出历史记录
        if not getattr(node, 'use_invoked_part', True):
            return

        # 获取源文件路径
        src_path = ""
        if hasattr(node, 'src_file_path'):  # 检查节点是否具有 src_file_path 属性
            src_path = node.src_file_path or ""  # 获取 src_file_path 的值，如果为 None 则使用空字符串

        # 获取结果图像（拷贝 numpy 数组以避免多线程数据竞争）
        result_image = node.result_image_source
        if result_image is not None and hasattr(result_image, 'copy'):
            result_image = result_image.copy()

        # 加锁保护消息列表；_notify_history_callbacks 在锁外调用避免死锁
        node_key = node.node_id
        should_notify = False
        with self._messages_lock:
            existing = self._message_index.get(node_key)             # 根据节点ID查找现有消息
            if existing is not None:
                existing.time_span = time_span                       # 更新时长
                existing.message = node.message or existing.message  # 更新消息文本（如果节点消息为空则保留原消息）
                existing.state = state                               # 更新状态
                if result_image is not None:                         # 更新结果图像（如果有）
                    existing.result_image_source = result_image      # 更新结果图像源
                existing.src_file_path = src_path                    # 更新源文件路径
                self._log_current_message_locked()                   # 更新当前聚合消息（锁内调用）
                should_notify = True                                 # 标记需要通知UI更新
            else:
                # 创建新消息条目
                msg = VisionMessage(
                    index=len(self.messages) + 1,
                    time_span=time_span,
                    type_name=node.name,
                    message=node.message or "",
                    state=state,
                    result_image_source=result_image,
                    src_file_path=src_path,
                    result_node_data=node,
                )
                self.messages.append(msg)            # 添加到消息列表末尾
                self._message_index[node_key] = msg  # 更新索引
                self._log_current_message_locked()   # 更新当前聚合消息（锁内调用）
                should_notify = True
                # 防止消息列表无界增长：将超出 1000 条的旧消息 result_image_source 置 None 释放 numpy 数组内存
                if len(self.messages) > 1000:
                    self.messages[len(self.messages) - 1001].result_image_source = None
        if should_notify:
            self._notify_history_callbacks()  # 在锁外调用回调通知UI更新

    def _log_current_message_locked(self):
        """ current_message（聚合消息）是一个"当前快照"，始终反映工作流最新一次执行的结果
            它和 messages（历史消息列表）的区别：
                        messages                current_message
            内容       完整执行历史，              仅最新一条的聚合快照
                      每个节点一条
            数量       持续增长	                  始终只有一个
            index	  按顺序编号 (1, 2, 3...)	      固定为 0
            type_name	各自节点的名称	             空字符串（不代表具体节点）
            message	    各自节点的 message	    工作流级别的 self.message，
                                                兜底用最后节点的 message
            ResultPanel 会读取它。简单说就是：ResultPanel 既需要看到完整历史（messages），
            也需要一个"当前正在发生什么"的实时摘要（current_message）。
            比如一个视频处理流程，节点 A → 节点 B → 节点 C 依次执行：
            messages 里会累积 3 条记录，用户可以回看每个节点的输出
            current_message 则随着执行推进不断被覆盖，始终只展示"此时此刻"的结果图像和消息，UI 用它来做实时预览/实时状态显示
        """
        if not self.messages:
            self.current_message = None
            return
        # 获取最后一条消息
        last = self.messages[-1]
        # 创建聚合消息
        self.current_message = VisionMessage(
            index=0,                                       # 固定为 0，表示当前快照
            time_span=last.time_span,                      # 使用最后一条消息的时长
            type_name="",                                  # 聚合消息不代表具体节点，类型名为空
            message=self.message or last.message,          # 使用工作流级别的 message，兜底用最后节点的 message
            state=last.state,                              # 使用最后一条消息的状态
            result_image_source=last.result_image_source,  # 使用最后一条消息的结果图像
            src_file_path=last.src_file_path,              # 使用最后一条消息的源文件路径
            result_node_data=last.result_node_data,        # 使用最后一条消息的节点
        )

    def get_messages_snapshot(self) -> list[VisionMessage]:
        """返回消息列表的线程安全副本，供 UI 显示"""
        with self._messages_lock:
            return list(self.messages)

    def clear_messages(self):
        """清空历史消息"""
        with self._messages_lock:
            self.messages.clear()
            self._message_index.clear()
            self.current_message = None

    def get_start_nodes(self) -> list[NodeBase]:
        """获取根节点（没有上游连接的节点）"""
        return [n for n in self._nodes.values() if len(n.from_node_datas) == 0]

    # -- 连线管理 --

    def _resolve_port(self, node: NodeBase, *, port_id: str | None = None,
                      dock: PortDock | None = None, is_output: bool | None = None):
        """根据端口ID优先解析具体端口，然后根据停靠位置/方向解析"""
        # 优先通过端口ID查找
        if port_id:
            for port in node.ports:
                if port.port_id == port_id:
                    return port

        # 否则根据停靠位置和方向查找
        for port in node.ports:
            if dock is not None and port.dock != dock:
                continue
            if is_output is True and not port.is_output:
                continue
            if is_output is False and not port.is_input:
                continue
            return port
        return None

    def _has_link_between(self, from_node_id: str, to_node_id: str,
                          *, exclude_link_id: str | None = None) -> bool:
        """
        检查两个节点之间是否已存在连线
        :param from_node_id: 来源节点
        :param to_node_id:   目标节点
        :param exclude_link_id: 排除连线ID
        """
        for link in self._links:
            # 如果存在exclude_link_id并且在self._links有线等于exclude_link_id，则跳过该线
            if exclude_link_id and link.link_id == exclude_link_id:
                continue
            if link.from_node_id == from_node_id and link.to_node_id == to_node_id:
                return True
        return False

    def add_link(self, from_node_id: str, to_node_id: str,
                 from_port_dock: PortDock = PortDock.BOTTOM,
                 to_port_dock: PortDock = PortDock.TOP,
                 from_port_id: str | None = None,
                 to_port_id: str | None = None,
                 link_id: str | None = None,
                 text: str = "") -> LinkData | None:
        """
        在两个节点之间创建连线，尽可能使用精确的端口
        :param from_node_id: 来源节点ID
        :param to_node_id: 目标节点ID
        :param from_port_dock: 来源端口停靠位置（默认底部）
        :param to_port_dock: 目标端口停靠位置（默认顶部）
        :param from_port_id: 来源端口ID（优先使用）
        :param to_port_id: 目标端口ID（优先使用）
        :param link_id: 连线ID（如果为None则自动生成）
        :param text: 连线文本（默认空）
        :return: 创建的LinkData对象，如果创建失败（如节点不存在或连线已存在）则返回None
        """
        # 获取源节点和目标节点
        from_node = self._nodes.get(from_node_id)
        to_node = self._nodes.get(to_node_id)
        if not from_node or not to_node:
            return None

        # 解析源端口
        from_port = self._resolve_port(
            from_node,
            port_id=from_port_id,
            dock=from_port_dock,
            is_output=True,
        )
        # 解析目标端口
        to_port = self._resolve_port(
            to_node,
            port_id=to_port_id,
            dock=to_port_dock,
            is_output=False,
        )

        if not from_port or not to_port:
            return None

        # 检查连线是否已存在
        for existing in self._links:
            if (existing.from_node_id == from_node_id and
                    existing.from_port_id == from_port.port_id and
                    existing.to_node_id == to_node_id and
                    existing.to_port_id == to_port.port_id):
                return existing

        # 创建新连线
        link = LinkData(
            from_node_id=from_node_id,
            from_port_id=from_port.port_id,
            to_node_id=to_node_id,
            to_port_id=to_port.port_id,
            text=text,
        )
        if link_id:
            link.link_id = link_id
        self._links.append(link)

        # 更新端口的连接列表
        if link not in from_port.connected_links:
            from_port.connected_links.append(link)
        if link not in to_port.connected_links:
            to_port.connected_links.append(link)
        # 更新节点的上下游关系
        if from_node not in to_node.from_node_datas:
            to_node.from_node_datas.append(from_node)
        if to_node not in from_node.to_node_datas:
            from_node.to_node_datas.append(to_node)

        # 发布事件
        event_system.publish(EventType.LINK_ADDED, sender=self, link=link)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self._invalidate_levels_cache()
        return link

    def remove_link(self, link_id: str):
        """根据ID移除连线"""
        # 查找要移除的连线
        link = None
        for l in self._links:
            if l.link_id == link_id:
                link = l
                break
        if link is None:
            return

        # 从列表中移除
        self._links.remove(link)

        # 更新端口的连接状态
        from_node = self._nodes.get(link.from_node_id)
        to_node = self._nodes.get(link.to_node_id)
        if from_node:
            from_port = self._resolve_port(from_node, port_id=link.from_port_id)
            if from_port and link in from_port.connected_links:
                from_port.connected_links.remove(link)
        if to_node:
            to_port = self._resolve_port(to_node, port_id=link.to_port_id)
            if to_port and link in to_port.connected_links:
                to_port.connected_links.remove(link)

        # 只有当两个节点之间没有其他连线时才移除上下游关系
        if to_node and from_node:
            if (from_node in to_node.from_node_datas and
                    not self._has_link_between(link.from_node_id, link.to_node_id, exclude_link_id=link.link_id)):
                to_node.from_node_datas.remove(from_node)
            if (to_node in from_node.to_node_datas and
                    not self._has_link_between(link.from_node_id, link.to_node_id, exclude_link_id=link.link_id)):
                from_node.to_node_datas.remove(to_node)

        # 发布事件
        event_system.publish(EventType.LINK_REMOVED, sender=self, link=link)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self._invalidate_levels_cache()

    def get_all_links(self) -> list[LinkData]:
        """获取所有连线"""
        return list(self._links)

    # -- 拓扑排序 --

    def topological_sort(self) -> list[str]:
        """对节点进行执行顺序排序（Kahn算法）

        没有输入的节点排在前面。能够检测并行分支。
        返回按执行顺序排列的节点ID列表。

        结果缓存在 _topo_cache 中，拓扑变更时自动失效。
        """
        if self._topo_cache is not None:
            return self._topo_cache

        # 初始化入度和邻接表
        in_degree: dict[str, int] = {}
        adj: dict[str, list[str]] = {}

        for node_id in self._nodes:
            in_degree[node_id] = 0
            adj[node_id] = []

        # 构建邻接表
        for link in self._links:
            if link.to_node_id in in_degree:
                in_degree[link.to_node_id] += 1
                adj.setdefault(link.from_node_id, []).append(link.to_node_id)

        # 找出所有入度为0的节点
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        result = []

        # Kahn算法
        while queue:
            current = queue.popleft()
            result.append(current)
            for neighbor in adj.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        self._topo_cache = result
        return result

    # -- 执行 --
    def can_start(self) -> bool:
        """
        判断是否可以启动：状态允许启动且有可执行节点
        只有当画布上有节点且状态为   can_start() 时才允许启动流程，避免无意义的启动操作
        """
        return self.state.can_start() and len(self._nodes) > 0

    def can_stop(self) -> bool:
        """判断是否可以停止：状态为运行中"""
        return self.state.can_stop()

    def can_reset(self) -> bool:
        """判断是否可以重置：始终可用"""
        return self.state.can_reset()

    def get_start_node_data(self) -> NodeBase | None:
        """
        查找起始节点（无上游连接且有输出端口的节点）
        """
        starts = [n for n in self._nodes.values()
                  if len(n.from_node_datas) == 0
                  and any(p.is_output for p in n.ports)]
        return starts[0] if starts else None

    def execute(self) -> FlowableResult:
        """执行整个工作流 — 按拓扑顺序运行所有节点"""
        if not self.can_start():
            return FlowableResult.error(message="流程已在运行中或没有节点")
        if self.get_start_node_data() is None:
            return FlowableResult.error(message="未找到起始节点")

        self.state = WorkflowState.RUNNING
        self._invoke_count = 0

        order = self.topological_sort()
        if not order:
            self.state = WorkflowState.COMPLETED
            return FlowableResult.ok(message="空流程")

        last_result = self._run_levels(self._group_by_levels(order))
        return self._finish_execution(last_result)

    def _run_levels(self, levels: list[list[str]]) -> FlowableResult:
        """逐层执行节点，同层内单节点顺序、多节点并行"""
        disabled: set[str] = set()
        last_result = FlowableResult.ok()
        try:
            for level in levels:
                if self.state == WorkflowState.STOPPED:
                    break
                executable = [nid for nid in level if nid not in disabled]
                if not executable:
                    continue
                if len(executable) == 1:
                    last_result = self._run_single(executable[0], disabled)
                    if last_result.is_break:
                        break
                else:
                    last_result = self._run_parallel(executable, disabled)
        except Exception as e:
            self.state = WorkflowState.ERROR
            return FlowableResult.error(message=str(e))
        return last_result

    def _run_single(self, node_id: str, disabled: set[str]) -> FlowableResult:
        """执行单个节点并处理端口路由"""
        node = self._nodes.get(node_id)
        if node is None:
            return FlowableResult.ok()
        result = self._execute_node(node)
        self._on_level_error(result)
        self._apply_port_routing(node, disabled)
        return result

    def _run_parallel(self, node_ids: list[str], disabled: set[str]) -> FlowableResult:
        """并行执行一组节点，取最后一个错误结果"""
        results = self._execute_parallel(node_ids)
        last = FlowableResult.ok()
        for r in results:
            if r.is_error:
                last = r
        self._on_level_error(last)
        for nid in node_ids:
            if nid not in disabled:
                node = self._nodes.get(nid)
                if node:
                    self._apply_port_routing(node, disabled)
        return last

    def _finish_execution(self, last_result: FlowableResult) -> FlowableResult:
        """根据执行后的状态发布对应完成事件"""
        if self.state == WorkflowState.STOPPED:
            return FlowableResult.ok(message="流程已停止")
        if self.state == WorkflowState.ERROR:
            event_system.publish(EventType.WORKFLOW_ERROR, sender=self, result=last_result)
            return last_result
        self.state = WorkflowState.COMPLETED
        event_system.publish(EventType.WORKFLOW_COMPLETED, sender=self, result=last_result)
        return last_result

    def reset(self):
        """将工作流状态重置为 IDLE 以便重新执行

        重置状态但不清除节点/连线。用于连续执行迭代之间以及重置命令。
        """
        self.state = WorkflowState.IDLE
        self._invoke_count = 0

    def execute_step(self, node_id: str) -> FlowableResult:
        """执行单个节点（用于单步调试）"""
        node = self._nodes.get(node_id)
        if node is None:
            return FlowableResult.error(message=f"节点不存在: {node_id}")

        if isinstance(node, VisionNodeData):
            node.update_invoke_current()
            return FlowableResult.ok(node.mat)

        return self._execute_node(node)

    def _apply_port_routing(self, node: NodeBase, disabled: set[str]):
        """根据节点的活动输出端口，禁用非活动端口下游的所有节点。

        只 yield 匹配条件的端口，
        不匹配的端口及其下游链路被跳过。

        参数：
            node: 当前已执行的节点
            disabled: 要追加禁用节点ID的集合
        """
        # 获取所有连接到该节点输出的连线
        all_outgoing = [l for l in self._links if l.from_node_id == node.node_id
                       and any(p.is_output and p.port_id == l.from_port_id for p in node.ports)]
        if not all_outgoing:
            return

        # 获取活动的输出连线
        if hasattr(node, 'get_flowable_output_links'):
            active = node.get_flowable_output_links(self)
        else:
            active = all_outgoing

        active_link_ids = {l.link_id for l in active}

        # 递归禁用非活动端口下游的所有节点，标记为错误状态
        new_disabled: set[str] = set()
        for link in all_outgoing:
            if link.link_id not in active_link_ids:
                self._disable_downstream(link.to_node_id, new_disabled)
        disabled.update(new_disabled)
        for nid in new_disabled:
            node = self._nodes.get(nid)
            if node is not None:
                node._execution_state = FlowableResultState.ERROR
                event_system.publish(EventType.NODE_ERROR, sender=node, result=None)

    def _disable_downstream(self, node_id: str, disabled: set[str]):
        """禁用节点及其所有下游节点（迭代，避免深图递归栈溢出）。"""
        adj: dict[str, list[str]] = {}
        for link in self._links:
            adj.setdefault(link.from_node_id, []).append(link.to_node_id)
        stack = [node_id]
        while stack:
            nid = stack.pop()
            if nid in disabled:
                continue
            disabled.add(nid)
            for to_id in adj.get(nid, ()):
                stack.append(to_id)

    def _on_level_error(self, result: FlowableResult):
        """当前层级执行出错时标记状态并发布事件"""
        if result.is_error:
            self.state = WorkflowState.ERROR
            event_system.publish(EventType.WORKFLOW_ERROR, sender=self, result=result)

    def stop(self):
        """停止执行（惰性停止）

        设置 STOPPED 状态，execute() 循环在每层级处理前检查并跳出。
        注意：已提交到 ThreadPoolExecutor 的节点任务不会立即中断，
        它们会运行至完成。这是设计权衡：强行中断线程可能留下不一致状态。
        """
        self.state = WorkflowState.STOPPED
        event_system.publish(EventType.WORKFLOW_STOPPED, sender=self)

    def _execute_node(self, node: NodeBase) -> FlowableResult:
        """执行单个节点及其周围的连线/端口（基于模式）

        递归链：Node → Port → Link → Port → Node
        Python（拓扑排序）：执行节点，然后根据模式调用连线和端口
        """
        self._invoke_count += 1

        # ── 连线/端口模式：执行传入的连线 ──
        previors = None
        if self.flowable_mode in (DiagramFlowableMode.LINK, DiagramFlowableMode.PORT):
            for link in self._links:
                if link.to_node_id == node.node_id:
                    link.invoke()
                    previors = previors or link

        # ── 端口模式：执行传入的端口 ──
        if self.flowable_mode == DiagramFlowableMode.PORT:
            for port in node.ports:
                if port.is_input and port.connected_links:
                    port.invoke(diagram=self)

        # ── 执行节点本身 ──
        if isinstance(node, VisionNodeData):
            try:
                result = node.invoke(previors, self)
            except Exception as e:
                import traceback
                result = FlowableResult.error(
                    message=f"节点执行异常: {e}\n{traceback.format_exc()}"
                )
        else:
            result = FlowableResult.ok()

        # ── 端口模式：执行传出的端口 ──
        if self.flowable_mode == DiagramFlowableMode.PORT:
            for port in node.ports:
                if port.is_output and port.connected_links:
                    port.invoke(diagram=self)

        return result

    def _execute_parallel(self, node_ids: list[str]) -> list[FlowableResult]:
        """并行执行一组节点（复用线程池减少创建/销毁开销）。"""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        results: dict[str, FlowableResult] = {}
        futures = {}
        for nid in node_ids:
            node = self._nodes.get(nid)
            if node:
                futures[self._executor.submit(self._execute_node, node)] = nid

        for future in as_completed(futures):
            nid = futures[future]
            try:
                results[nid] = future.result()
            except Exception as e:
                results[nid] = FlowableResult.error(message=str(e))
        return [results.get(nid, FlowableResult.error(message=f"节点 {nid} 未找到"))
                for nid in node_ids]

    def _invalidate_levels_cache(self):
        """拓扑变更时使层级缓存、拓扑排序缓存和反向邻接映射失效。"""
        self._levels_cache = None
        self._topo_cache = None
        self._rev_adj = None

    def _group_by_levels(self, topo_order: list[str]) -> list[list[str]]:
        """将拓扑排序后的节点按执行层级分组（结果缓存至拓扑变更）。"""
        if not topo_order:
            return []

        order_key = tuple(topo_order)
        if self._levels_cache is not None and self._levels_cache[0] == order_key:
            return self._levels_cache[1]

        # 惰性构建反向邻接映射（映射 node_id → 前驱节点列表），O(L) 建一次，查询 O(1)
        if self._rev_adj is None:
            self._rev_adj = {}
            for link in self._links:
                self._rev_adj.setdefault(link.to_node_id, []).append(link.from_node_id)

        # 按拓扑顺序计算每个节点的层级 = max(所有前驱节点层级) + 1
        node_level: dict[str, int] = {}
        for nid in topo_order:
            max_pred_level = -1
            for pred_id in self._rev_adj.get(nid, ()):
                pred_level = node_level.get(pred_id, -1)
                if pred_level > max_pred_level:
                    max_pred_level = pred_level
            node_level[nid] = max_pred_level + 1

        # 按层级分组（组内保持拓扑顺序）
        levels: list[list[str]] = []
        cur_level: list[str] = []
        cur_lev = 0
        for nid in topo_order:
            lev = node_level[nid]
            if lev != cur_lev:
                if cur_level:
                    levels.append(cur_level)
                cur_level = [nid]
                cur_lev = lev
            else:
                cur_level.append(nid)
        if cur_level:
            levels.append(cur_level)

        self._levels_cache = (order_key, levels)
        return levels

    # -- 序列化 --

    def to_dict(self) -> dict:
        """将整个工作流序列化为字典"""
        return {
            "name": self.name,
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "links": [l.to_dict() for l in self._links],
        }

    def from_dict(self, data: dict, node_factory: Callable[[str], NodeBase | None]):
        """从字典加载工作流

        参数：
            data: 序列化的工作流字典
            node_factory: 用于反序列化节点的函数 (type_name) -> NodeBase（必需）
        """
        self.name = data.get("name", "新建流程")
        self._nodes.clear()
        self._links.clear()

        # 反序列化节点
        node_map: dict[str, NodeBase] = {}
        for node_data in data.get("nodes", []):
            type_name = node_data.get("type", "")
            node = node_factory(type_name)
            if node is None:
                continue
            # 恢复节点状态
            if hasattr(node, "restore_from_dict"):
                node.restore_from_dict(node_data)
            else:
                node._id = node_data.get("id", node._id)
            node.diagram_data = self
            node_map[node._id] = node
            self._nodes[node._id] = node

        # 反序列化连线
        for link_data in data.get("links", []):
            link = LinkData.from_dict(link_data)
            self._links.append(link)

            # 重建邻接关系
            to_node = self._nodes.get(link.to_node_id)
            from_node = self._nodes.get(link.from_node_id)
            if to_node and from_node:
                from_port = next((p for p in from_node.ports if p.port_id == link.from_port_id), None)
                to_port = next((p for p in to_node.ports if p.port_id == link.to_port_id), None)
                if from_port is not None and link not in from_port.connected_links:
                    from_port.connected_links.append(link)
                if to_port is not None and link not in to_port.connected_links:
                    to_port.connected_links.append(link)
                if from_node not in to_node.from_node_datas:
                    to_node.from_node_datas.append(from_node)
                if to_node not in from_node.to_node_datas:
                    from_node.to_node_datas.append(to_node)

        self._invalidate_levels_cache()

    def clear(self):
        """移除所有节点和连线"""
        self._nodes.clear()
        self._links.clear()
        self.state = WorkflowState.IDLE
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self._invalidate_levels_cache()

    def dispose(self):
        """清理所有资源"""
        for node in list(self._nodes.values()):
            node.dispose()
        self.clear()
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()
        return False
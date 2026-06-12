"""工作流引擎 - 编排节点图执行。

处理：
  - 节点图拓扑结构（节点 + 连线）
  - 执行顺序的拓扑排序
  - 顺序执行和并行执行
  - 执行上下文和数据流
  - 流程控制（OK/Error/Break 路由）
"""

from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum, auto
from typing import Any, Callable

from core.node_base import (
    NodeBase, VisionNodeData, LinkData, PortDock,
)
from core.data_packet import FlowableResult
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
        import threading
        # 工作流名称
        self.name = name
        # 当前执行状态
        self.state: WorkflowState = WorkflowState.IDLE
        # 节点字典：键为节点ID，值为节点对象
        self._nodes: dict[str, NodeBase] = {}
        # 连线列表
        self._links: list[LinkData] = []
        # 执行顺序（节点ID列表）
        self._execution_order: list[str] = []
        # 最大并行工作线程数
        self._max_workers: int = 4
        # 调用计数
        self._invoke_count: int = 0
        # 结果图像源
        self.result_image_source: Any = None
        # 流程执行模式
        self.flowable_mode: DiagramFlowableMode = DiagramFlowableMode.NODE
        # 当前消息文本
        self.message: str = ""
        # 历史消息列表
        self.messages: list[VisionMessage] = []
        # 当前聚合消息
        self.current_message: VisionMessage | None = None
        # 线程锁，保护消息列表的线程安全
        self._messages_lock = threading.Lock()
        # 历史变更回调列表（用于UI绑定）
        self._history_callbacks: list[Callable] = []

    # -- 节点管理 --

    def add_node(self, node: NodeBase) -> str:
        """向图表中添加节点。返回节点的ID"""
        # 设置节点的图表数据引用
        node.diagram_data = self
        # 将节点添加到字典
        self._nodes[node.node_id] = node
        # 发布节点添加事件
        event_system.publish(EventType.NODE_ADDED, sender=self, node=node)
        # 发布图表变更事件
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        return node.node_id

    def remove_node(self, node_id: str):
        """移除节点及其所有相关连线"""
        # 从字典中弹出节点
        node = self._nodes.pop(node_id, None)
        if node is None:
            return
        # 移除与该节点相关的所有连线
        self._links = [l for l in self._links
                      if l.from_node_id != node_id and l.to_node_id != node_id]
        # 从其他节点的上下游列表中移除该节点
        for n in self._nodes.values():
            n.from_node_datas = [x for x in n.from_node_datas if x.node_id != node_id]
            n.to_node_datas = [x for x in n.to_node_datas if x.node_id != node_id]
        # 发布节点移除事件
        event_system.publish(EventType.NODE_REMOVED, sender=self, node=node)
        # 发布图表变更事件
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)

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

    def _notify_history_callbacks(self):
        """调用所有已注册的历史变更回调"""
        for cb in self._history_callbacks:
            try:
                cb()
            except Exception:
                pass

    def on_node_completed(self, node: VisionNodeData, state: str, time_span: str):
        """ OnInvokedPart(IPartData) 的等价实现 —— 添加/更新历史消息

        与 UI 解耦：WorkflowEngine 拥有 Messages 集合，
        ResultPanel 从中读取。每个工作流都有自己的 Messages，
        切换标签页时历史记录自动隔离。

        线程安全：从 ThreadPoolExecutor 的工作线程调用。
        """
        import time
        # 检查是否启用输出历史记录
        if not getattr(node, 'use_invoked_part', True):
            return

        # 获取源文件路径
        src_path = ""
        if hasattr(node, 'src_file_path'):
            src_path = node.src_file_path or ""

        # 获取结果图像
        result_image = getattr(node, '_result_image_source', None)

        # 加锁保护消息列表
        with self._messages_lock:
            # 查找已有的消息（用于视频/摄像头节点原地更新）
            for msg in self.messages:
                if msg.result_node_data is node:
                    # 更新已有消息
                    msg.time_span = time_span
                    msg.message = node.message or msg.message
                    msg.state = state
                    if result_image is not None:
                        msg.result_image_source = result_image
                    msg.src_file_path = src_path
                    self._log_current_message_locked()
                    self._notify_history_callbacks()
                    return

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
            self.messages.append(msg)
            self._log_current_message_locked()
            self._notify_history_callbacks()

    def _log_current_message_locked(self):
        """ LogCurrentMessage() — 调用者必须持有 _messages_lock 锁"""
        if not self.messages:
            self.current_message = None
            return
        # 获取最后一条消息
        last = self.messages[-1]
        # 创建聚合消息
        self.current_message = VisionMessage(
            index=0,
            time_span=last.time_span,
            type_name="",
            message=self.message or last.message,
            state=last.state,
            result_image_source=last.result_image_source,
            src_file_path=last.src_file_path,
            result_node_data=last.result_node_data,
        )

    def get_messages_snapshot(self) -> list[VisionMessage]:
        """返回消息列表的线程安全副本，供 UI 显示"""
        with self._messages_lock:
            return list(self.messages)

    def clear_messages(self):
        """清空历史消息"""
        with self._messages_lock:
            self.messages.clear()
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
        """检查两个节点之间是否已存在连线"""
        for link in self._links:
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
        """在两个节点之间创建连线，尽可能使用精确的端口"""
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

    def get_all_links(self) -> list[LinkData]:
        """获取所有连线"""
        return list(self._links)

    # -- 拓扑排序 --

    def topological_sort(self) -> list[str]:
        """对节点进行执行顺序排序（Kahn算法）

        没有输入的节点排在前面。能够检测并行分支。
        返回按执行顺序排列的节点ID列表。
        """
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

        self._execution_order = result
        return result

    # -- 执行 --

    def can_start(self) -> bool:
        """判断是否可以启动：状态允许启动且有可执行节点"""
        return self.state.can_start() and len(self._nodes) > 0

    def can_stop(self) -> bool:
        """判断是否可以停止：状态为运行中"""
        return self.state.can_stop()

    def can_reset(self) -> bool:
        """判断是否可以重置：始终可用"""
        return self.state.can_reset()

    def get_start_node_data(self) -> NodeBase | None:
        """查找起始节点（无上游连接且有输出端口的节点）

        对应 GetStartNodeDatas() → TryGetStartNodeData<T>()
        """
        starts = [n for n in self._nodes.values()
                  if len(n.from_node_datas) == 0
                  and any(p.is_output for p in n.ports)]
        return starts[0] if starts else None

    def start(self) -> FlowableResult:
        """执行工作流（StartCommand）

        "运行全部" (run_all_images) 由 WorkflowRunner.start_run_all() 处理，
        它会遍历 SrcFilePaths，在每次迭代前更新 src_file_path，
        并为 UI 发布 FILE_ITERATION_NEXT 事件。UseAutoSwitch 只影响
        缩略图面板刷新（FlowResourcePanel.refresh_selection()），
        不影响实际的文件切换 —— src_file_path 始终被更新。

        StartCommand → await this.Start() → InvokeState → Wait → node.Start()
        Python：守卫检查 → 获取起始节点 → 在当前线程上执行
        """
        if not self.can_start():
            return FlowableResult.error(message="流程已在运行中")
        if self.get_start_node_data() is None:
            return FlowableResult.error(message="未找到起始节点（需要无输入端口且有输出端口的节点）")
        return self.execute()

    def execute(self) -> FlowableResult:
        """执行整个工作流

        按拓扑顺序运行节点。使用 ThreadPoolExecutor 处理并行分支。
        支持节点级端口路由（get_flowable_output_links）实现条件分支。
        返回最后一个节点的执行结果。
        """
        if self.state == WorkflowState.RUNNING:
            return FlowableResult.error(message="流程已在运行中")

        # 设置运行状态
        self.state = WorkflowState.RUNNING
        self._invoke_count = 0
        event_system.publish(EventType.WORKFLOW_STARTED, sender=self)

        # 获取拓扑排序结果
        order = self.topological_sort()
        if not order:
            self.state = WorkflowState.COMPLETED
            return FlowableResult.ok(message="空流程")

        # 按层级分组并行节点
        levels = self._group_by_levels(order)

        # 被条件分支禁用端口排除的下游节点集合
        _disabled_node_ids: set[str] = set()

        last_result = FlowableResult.ok()
        try:
            for level in levels:
                # 检查是否已停止
                if self.state == WorkflowState.STOPPED:
                    break

                # 构建本层要执行的节点列表（排除被条件端口禁用的节点）
                executable = [nid for nid in level if nid not in _disabled_node_ids]

                if len(executable) == 0:
                    continue

                if len(executable) == 1:
                    # 单节点顺序执行
                    node = self._nodes.get(executable[0])
                    if node is None:
                        continue
                    last_result = self._execute_node(node)
                    if last_result.is_break:
                        break
                    if last_result.is_error:
                        self.state = WorkflowState.ERROR
                        event_system.publish(EventType.WORKFLOW_ERROR, sender=self, result=last_result)
                        return last_result
                    self._apply_port_routing(node, _disabled_node_ids)
                else:
                    # 并行执行一组节点
                    results = self._execute_parallel(executable)
                    has_error = False
                    for r in results:
                        if r.is_error:
                            last_result = r
                            has_error = True
                    if has_error:
                        self.state = WorkflowState.ERROR
                        event_system.publish(EventType.WORKFLOW_ERROR, sender=self, result=last_result)
                        return last_result
                    # 条件端口路由：并行执行后，对每个节点应用端口路由
                    for nid in executable:
                        if nid not in _disabled_node_ids:
                            node = self._nodes.get(nid)
                            if node:
                                self._apply_port_routing(node, _disabled_node_ids)

            # 处理停止状态
            if self.state == WorkflowState.STOPPED:
                event_system.publish(EventType.WORKFLOW_STOPPED, sender=self)
                return FlowableResult.ok(message="流程已停止")

            # 执行完成
            self.state = WorkflowState.COMPLETED
            event_system.publish(EventType.WORKFLOW_COMPLETED, sender=self, result=last_result)
            return last_result

        except Exception as e:
            self.state = WorkflowState.ERROR
            result = FlowableResult.error(message=str(e))
            event_system.publish(EventType.WORKFLOW_ERROR, sender=self, result=result)
            return result

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

        # 递归禁用非活动端口下游的所有节点，并发布 ERROR 状态
        new_disabled: set[str] = set()
        for link in all_outgoing:
            if link.link_id not in active_link_ids:
                self._disable_downstream(link.to_node_id, new_disabled)
        disabled.update(new_disabled)
        for nid in new_disabled:
            node = self._nodes.get(nid)
            if node is not None:
                event_system.publish(EventType.NODE_ERROR, sender=node, result=None)

    def _disable_downstream(self, node_id: str, disabled: set[str]):
        """递归禁用节点及其所有下游节点"""
        if node_id in disabled:
            return
        disabled.add(node_id)
        for link in self._links:
            if link.from_node_id == node_id:
                self._disable_downstream(link.to_node_id, disabled)

    def stop(self):
        """停止执行

        将工作流设置为 STOPPED 状态。execute() 循环会在处理每个层级前检查此标志并跳出。
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
                    link.invoke(diagram=self)
                    previors = previors or link
        else:
            for link in self._links:
                if link.to_node_id == node.node_id:
                    previors = link
                    break

        # ── 端口模式：执行传入的端口 ──
        if self.flowable_mode == DiagramFlowableMode.PORT:
            for port in node.ports:
                if port.is_input and port.connected_links:
                    port.invoke(previors=previors, diagram=self)

        # ── 执行节点本身 ──
        if isinstance(node, VisionNodeData):
            result = node.invoke(previors, self)
            # invoke_milliseconds_delay 不再在此处 sleep，帧率由
            # WorkflowRunner._run_continuous 根据起始节点的设置统一控制
        else:
            result = FlowableResult.ok()

        # ── 端口模式：执行传出的端口 ──
        if self.flowable_mode == DiagramFlowableMode.PORT:
            for port in node.ports:
                if port.is_output and port.connected_links:
                    port.invoke(previors=None, diagram=self)

        return result

    def _execute_parallel(self, node_ids: list[str]) -> list[FlowableResult]:
        """并行执行一组节点"""
        results: list[FlowableResult] = []
        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(node_ids))) as executor:
            futures = {}
            # 提交所有任务
            for nid in node_ids:
                node = self._nodes.get(nid)
                if node:
                    futures[executor.submit(self._execute_node, node)] = nid

            # 收集结果
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(FlowableResult.error(message=str(e)))
        return results

    def _group_by_levels(self, topo_order: list[str]) -> list[list[str]]:
        """将拓扑排序后的节点按执行层级分组。

        使用 BFS 距离确保下游节点始终在后续层级，
        条件分支等依赖端口路由的节点才能正常工作。
        """
        if not topo_order:
            return []

        # 按拓扑顺序计算每个节点的层级 = max(所有前驱节点层级) + 1
        node_level: dict[str, int] = {}
        for nid in topo_order:
            max_pred_level = -1
            for link in self._links:
                if link.to_node_id == nid:
                    pred_level = node_level.get(link.from_node_id, -1)
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

        return levels

    # -- 序列化 --

    def to_dict(self) -> dict:
        """将整个工作流序列化为字典"""
        return {
            "name": self.name,
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "links": [l.to_dict() for l in self._links],
        }

    def from_dict(self, data: dict, node_factory: Callable[[str], NodeBase | None] | None = None):
        """从字典加载工作流

        参数：
            data: 序列化的工作流字典
            node_factory: 用于反序列化节点的函数 (type_name) -> NodeBase
        """
        self.name = data.get("name", "新建流程")
        self._nodes.clear()
        self._links.clear()

        # 反序列化节点
        node_map: dict[str, NodeBase] = {}
        for node_data in data.get("nodes", []):
            type_name = node_data.get("type", "")
            if node_factory:
                node = node_factory(type_name)
            else:
                node = None
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

    def clear(self):
        """移除所有节点和连线"""
        self._nodes.clear()
        self._links.clear()
        self._execution_order.clear()
        self.state = WorkflowState.IDLE
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)

    def dispose(self):
        """清理所有资源"""
        self.clear()
        for node in list(self._nodes.values()):
            node.dispose()
        self._nodes.clear()
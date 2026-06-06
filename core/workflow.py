"""Workflow engine - orchestrates node graph execution.

Ported from H.Controls.Diagram.Presenter + H.Controls.Diagram.Presenters.Workflow.

Handles:
  - Node graph topology (nodes + links)
  - Topological sort for execution order
  - Sequential and parallel execution
  - Execution context and data flow
  - Flow control (OK/Error/Break routing)
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
    """Execution state of the workflow engine."""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    COMPLETED = auto()
    ERROR = auto()

    def can_start(self) -> bool:
        """WPF CanStart: not already running."""
        return self != WorkflowState.RUNNING

    def can_stop(self) -> bool:
        """WPF CanStop: currently running."""
        return self == WorkflowState.RUNNING

    def can_reset(self) -> bool:
        """WPF CanReset: always available."""
        return True


class DiagramFlowableMode(Enum):
    """Run mode — controls execution granularity (WPF DiagramFlowableMode)."""
    NODE = 0   # 按节点运行
    LINK = 1   # 按节点+连线运行
    PORT = 2   # 按节点+连线+端口运行


class WorkflowEngine:
    """Manages a node graph and executes it.

    Ported from C# IFlowableDiagramData + DiagramDataBase + FlowableDiagramData.
    Each WorkflowEngine instance represents one diagram/document.
    """

    def __init__(self, name: str = "新建流程"):
        import threading
        self.name = name
        self.state: WorkflowState = WorkflowState.IDLE
        self._nodes: dict[str, NodeBase] = {}
        self._links: list[LinkData] = []
        self._execution_order: list[str] = []
        self._max_workers: int = 4
        self._invoke_count: int = 0
        self.result_image_source: Any = None
        self.flowable_mode: DiagramFlowableMode = DiagramFlowableMode.NODE
        self.message: str = ""
        # WPF: ObservableCollection<IVisionMessage> Messages on DiagramData
        self.messages: list[VisionMessage] = []
        self.current_message: VisionMessage | None = None
        self._messages_lock = threading.Lock()  # protect messages from ThreadPoolExecutor
        self._history_callbacks: list[Callable] = []  # WPF: PropertyChanged → UI binding

    # -- Node management --

    def add_node(self, node: NodeBase) -> str:
        """Add a node to the diagram. Returns the node's ID."""
        node.diagram_data = self
        self._nodes[node.node_id] = node
        event_system.publish(EventType.NODE_ADDED, sender=self, node=node)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        return node.node_id

    def remove_node(self, node_id: str):
        """Remove a node and all its connected links."""
        node = self._nodes.pop(node_id, None)
        if node is None:
            return
        # Remove connected links
        self._links = [l for l in self._links
                      if l.from_node_id != node_id and l.to_node_id != node_id]
        # Remove from other nodes' from/to lists
        for n in self._nodes.values():
            n.from_node_datas = [x for x in n.from_node_datas if x.node_id != node_id]
            n.to_node_datas = [x for x in n.to_node_datas if x.node_id != node_id]
        event_system.publish(EventType.NODE_REMOVED, sender=self, node=node)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)

    def get_node_by_id(self, node_id: str) -> NodeBase | None:
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> list[NodeBase]:
        return list(self._nodes.values())

    # ── History Messages (WPF: VisionDiagramDataBase.OnInvokedPart + Messages) ─

    def on_history_changed(self, callback: Callable):
        """Register a callback invoked when Messages changes (WPF: binding equivalent).

        The callback receives no arguments — callers should read get_messages_snapshot().
        Called from any thread; callers should marshal to their target thread as needed.
        """
        self._history_callbacks.append(callback)

    def _notify_history_callbacks(self):
        """Call all registered history change callbacks."""
        for cb in self._history_callbacks:
            try:
                cb()
            except Exception:
                pass

    def on_node_completed(self, node: VisionNodeData, state: str, time_span: str):
        """WPF OnInvokedPart(IPartData) equivalent — add/update history message.

        Decoupled from UI: WorkflowEngine owns the Messages collection,
        ResultPanel reads from it. Each workflow has its own Messages,
        so switching tabs isolates history.

        Thread-safe: called from ThreadPoolExecutor worker threads.
        """
        import time
        if not getattr(node, 'use_invoked_part', True):
            return

        src_path = ""
        if hasattr(node, 'src_file_path'):
            src_path = node.src_file_path or ""

        result_image = getattr(node, '_result_image_source', None)

        with self._messages_lock:
            # WPF: find existing by ResultNodeData match → update (for video/camera nodes)
            for msg in self.messages:
                if msg.result_node_data is node:
                    msg.time_span = time_span
                    msg.message = node.message or msg.message
                    msg.state = state
                    if result_image is not None:
                        msg.result_image_source = result_image
                    msg.src_file_path = src_path
                    self._log_current_message_locked()
                    self._notify_history_callbacks()
                    return

            # New entry
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
        """WPF LogCurrentMessage() — caller must hold _messages_lock."""
        if not self.messages:
            self.current_message = None
            return
        last = self.messages[-1]
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
        """Return a thread-safe copy of messages for UI display."""
        with self._messages_lock:
            return list(self.messages)

    def clear_messages(self):
        """Clear history messages (WPF: Messages.Clear() on new run)."""
        with self._messages_lock:
            self.messages.clear()
            self.current_message = None

    def get_start_nodes(self) -> list[NodeBase]:
        """Get root nodes (no upstream connections)."""
        return [n for n in self._nodes.values() if len(n.from_node_datas) == 0]

    # -- Link management --

    def _resolve_port(self, node: NodeBase, *, port_id: str | None = None,
                      dock: PortDock | None = None, is_output: bool | None = None):
        """Resolve a concrete port by id first, then by dock/direction."""
        if port_id:
            for port in node.ports:
                if port.port_id == port_id:
                    return port

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
        """Create a link between two nodes using exact ports when available."""
        from_node = self._nodes.get(from_node_id)
        to_node = self._nodes.get(to_node_id)
        if not from_node or not to_node:
            return None

        from_port = self._resolve_port(
            from_node,
            port_id=from_port_id,
            dock=from_port_dock,
            is_output=True,
        )
        to_port = self._resolve_port(
            to_node,
            port_id=to_port_id,
            dock=to_port_dock,
            is_output=False,
        )

        if not from_port or not to_port:
            return None

        for existing in self._links:
            if (existing.from_node_id == from_node_id and
                    existing.from_port_id == from_port.port_id and
                    existing.to_node_id == to_node_id and
                    existing.to_port_id == to_port.port_id):
                return existing

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

        # Update adjacency
        if link not in from_port.connected_links:
            from_port.connected_links.append(link)
        if link not in to_port.connected_links:
            to_port.connected_links.append(link)
        if from_node not in to_node.from_node_datas:
            to_node.from_node_datas.append(from_node)
        if to_node not in from_node.to_node_datas:
            from_node.to_node_datas.append(to_node)

        event_system.publish(EventType.LINK_ADDED, sender=self, link=link)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        return link

    def remove_link(self, link_id: str):
        """Remove a link by ID."""
        link = None
        for l in self._links:
            if l.link_id == link_id:
                link = l
                break
        if link is None:
            return

        self._links.remove(link)

        # Update port connection state
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

        # Update adjacency only when there is no remaining link between the nodes
        if to_node and from_node:
            if (from_node in to_node.from_node_datas and
                    not self._has_link_between(link.from_node_id, link.to_node_id, exclude_link_id=link.link_id)):
                to_node.from_node_datas.remove(from_node)
            if (to_node in from_node.to_node_datas and
                    not self._has_link_between(link.from_node_id, link.to_node_id, exclude_link_id=link.link_id)):
                from_node.to_node_datas.remove(to_node)

        event_system.publish(EventType.LINK_REMOVED, sender=self, link=link)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)

    def get_all_links(self) -> list[LinkData]:
        return list(self._links)

    # -- Topological sort --

    def topological_sort(self) -> list[str]:
        """Sort nodes in execution order (Kahn's algorithm).

        Nodes with no inputs go first. Parallel branches are detected.
        Returns list of node IDs in execution order.
        """
        in_degree: dict[str, int] = {}
        adj: dict[str, list[str]] = {}

        for node_id in self._nodes:
            in_degree[node_id] = 0
            adj[node_id] = []

        for link in self._links:
            if link.to_node_id in in_degree:
                in_degree[link.to_node_id] += 1
                adj.setdefault(link.from_node_id, []).append(link.to_node_id)

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        result = []

        while queue:
            current = queue.popleft()
            result.append(current)
            for neighbor in adj.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        self._execution_order = result
        return result

    # -- Execution (mirrors WPF FlowableDiagramDataBase) --

    def can_start(self) -> bool:
        """WPF CanStart: state can start AND there are flowable nodes."""
        return self.state.can_start() and len(self._nodes) > 0

    def can_stop(self) -> bool:
        """WPF CanStop: state == Running."""
        return self.state.can_stop()

    def can_reset(self) -> bool:
        """WPF CanReset: always available."""
        return self.state.can_reset()

    def get_start_node_data(self) -> NodeBase | None:
        """Find the start node (no upstream connections, has output ports).

        WPF: GetStartNodeDatas() → TryGetStartNodeData<T>().
        """
        starts = [n for n in self._nodes.values()
                  if len(n.from_node_datas) == 0
                  and any(p.is_output for p in n.ports)]
        return starts[0] if starts else None

    def start(self) -> FlowableResult:
        """Execute workflow (WPF StartCommand).

        WPF: StartCommand → await this.Start() → InvokeState → Wait → node.Start()
        Python: guards → get_start_node → execute() on caller's thread.
        """
        if not self.can_start():
            return FlowableResult.error(message="流程已在运行中")
        if self.get_start_node_data() is None:
            return FlowableResult.error(message="未找到起始节点（需要无输入端口且有输出端口的节点）")
        return self.execute()

    # ═══════════════════════════════════════════════════════════════════════
    # TODO: run_all_images — WPF VisionDiagramDataBase.Start() "运行全部" port
    #
    # WPF 实现要点（VisionDiagramDataBase.Start(), RunDiagramDataPresenter）：
    #
    # 1. 找到起始节点，判断是否为 ISrcFilesNodeData
    # 2. 如果 UseAllImage == true：
    #    a. 遍历所有 SrcFilePaths
    #    b. 每次循环：
    #       - 检查状态（CANCELLING → break）
    #       - 检查 UseAllImage 是否仍为 true（可中途取消）
    #       - 更新 ResultImageSource = item.ToImageSource()  # 显示当前图（始终）
    #       - 如果 UseAutoSwitch → 更新 SrcFilePath = item    # 缩略图跟随
    #       - 调用源节点 Start() 触发整个流程
    #       - 收集结果到 Messages 集合
    #       - Task.Delay(1000) — 1秒间隔
    # 3. 如果 UseAllImage == false：单次运行
    # 4. 外部 RunDiagramDataPresenter.StartAllCommand 手动遍历文件列表
    #    → StartOne() 临时设置 UseAllImage=false, 运行, 恢复原值
    #
    # ═══════════════════════════════════════════════════════════════════════
    # TODO: "自动切换" (UseAutoSwitch) 实现要点
    #
    # WPF 实现（VisionDiagramDataBase.Start() line 167）：
    #
    #   this.ResultImageSource = item.ToImageSource();   // ALWAYS 更新显示
    #   if (visionImageSource.UseAutoSwitch)              // 仅 auto_switch=ON 时
    #       this.SrcImageNodeData.SrcFilePath = item;     // 才更新当前文件指针
    #
    # 解耦策略：
    #   - ResultImageSource 更新 → FILE_ITERATION_NEXT 事件 → UI 始终更新图像
    #   - SrcFilePath 更新    → WorkflowRunner._run_all() 检查 auto_switch
    #   - 缩略图面板刷新      → MainWindow 收到事件后检查 auto_switch 状态
    #                         调用 FlowResourcePanel.refresh_selection()（轻量刷新）
    #   - WPF 绑定自动生效     → VisionFlow 需显式调用 refresh_selection()
    # ═══════════════════════════════════════════════════════════════════════

    def execute(self) -> FlowableResult:
        """Execute the entire workflow.

        Runs nodes in topological order. Handles parallel branches using ThreadPoolExecutor.
        Returns the result from the last node.
        """
        if self.state == WorkflowState.RUNNING:
            return FlowableResult.error(message="流程已在运行中")

        self.state = WorkflowState.RUNNING
        self._invoke_count = 0
        event_system.publish(EventType.WORKFLOW_STARTED, sender=self)

        order = self.topological_sort()
        if not order:
            self.state = WorkflowState.COMPLETED
            return FlowableResult.ok(message="空流程")

        # Group parallel nodes by level
        levels = self._group_by_levels(order)

        last_result = FlowableResult.ok()
        try:
            for level in levels:
                if self.state == WorkflowState.STOPPED:
                    break

                if len(level) == 1:
                    # Sequential single node
                    node = self._nodes.get(level[0])
                    if node is None:
                        continue
                    last_result = self._execute_node(node)
                    if last_result.is_break:
                        break
                    if last_result.is_error:
                        self.state = WorkflowState.ERROR
                        event_system.publish(EventType.WORKFLOW_ERROR, sender=self, result=last_result)
                        return last_result
                else:
                    # Parallel group
                    results = self._execute_parallel(level)
                    for r in results:
                        if r.is_error:
                            last_result = r
                            self.state = WorkflowState.ERROR
                            event_system.publish(EventType.WORKFLOW_ERROR, sender=self, result=r)
                            return r

            if self.state == WorkflowState.STOPPED:
                event_system.publish(EventType.WORKFLOW_STOPPED, sender=self)
                return FlowableResult.ok(message="流程已停止")

            self.state = WorkflowState.COMPLETED
            event_system.publish(EventType.WORKFLOW_COMPLETED, sender=self, result=last_result)
            return last_result

        except Exception as e:
            self.state = WorkflowState.ERROR
            result = FlowableResult.error(message=str(e))
            event_system.publish(EventType.WORKFLOW_ERROR, sender=self, result=result)
            return result

    def reset(self):
        """Reset workflow state to IDLE for re-execution.

        Resets state without clearing nodes/links. Used between continuous
        execution iterations and by the reset command.
        """
        self.state = WorkflowState.IDLE
        self._invoke_count = 0

    def execute_step(self, node_id: str) -> FlowableResult:
        """Execute a single node (for single-step debugging)."""
        node = self._nodes.get(node_id)
        if node is None:
            return FlowableResult.error(message=f"节点不存在: {node_id}")

        if isinstance(node, VisionNodeData):
            node.update_invoke_current()
            return FlowableResult.ok(node.mat)

        return self._execute_node(node)

    def stop(self):
        """Stop execution (WPF: Diagram.State = Canceling → GotoState).

        Sets workflow to STOPPED state. The execute() loop checks
        this flag before processing each level and breaks out.
        """
        self.state = WorkflowState.STOPPED
        event_system.publish(EventType.WORKFLOW_STOPPED, sender=self)

    def _execute_node(self, node: NodeBase) -> FlowableResult:
        """Execute a single node + surrounding links/ports based on mode.

        WPF recursive chain:  Node → Port → Link → Port → Node
        Python (topo-sort):  execute node, then invoke links/ports per mode.
        """
        self._invoke_count += 1

        # ── Link/Port mode: execute incoming links ──
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

        # ── Port mode: execute incoming ports ──
        if self.flowable_mode == DiagramFlowableMode.PORT:
            for port in node.ports:
                if port.is_input and port.connected_links:
                    port.invoke(previors=previors, diagram=self)

        # ── Execute the node itself ──
        if isinstance(node, VisionNodeData):
            result = node.invoke(previors, self)
            import time
            time.sleep(node.invoke_milliseconds_delay / 1000.0)
        else:
            result = FlowableResult.ok()

        # ── Port mode: execute outgoing ports ──
        if self.flowable_mode == DiagramFlowableMode.PORT:
            for port in node.ports:
                if port.is_output and port.connected_links:
                    port.invoke(previors=None, diagram=self)

        return result

    def _execute_parallel(self, node_ids: list[str]) -> list[FlowableResult]:
        """Execute a group of nodes in parallel."""
        results: list[FlowableResult] = []
        with ThreadPoolExecutor(max_workers=min(self._max_workers, len(node_ids))) as executor:
            futures = {}
            for nid in node_ids:
                node = self._nodes.get(nid)
                if node:
                    futures[executor.submit(self._execute_node, node)] = nid

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(FlowableResult.error(message=str(e)))
        return results

    def _group_by_levels(self, topo_order: list[str]) -> list[list[str]]:
        """Group topologically sorted nodes into execution levels.

        Parallel nodes (those with no dependencies between them at the same level)
        are grouped together for parallel execution.
        """
        if not topo_order:
            return []

        # Simple approach: nodes with invoke_mode=PARALLEL and same in-degree go together
        in_degree: dict[str, int] = {}
        for node_id in topo_order:
            deg = 0
            for link in self._links:
                if link.to_node_id == node_id:
                    deg += 1
            in_degree[node_id] = deg

        levels: list[list[str]] = []
        current_level: list[str] = []
        current_degree = -1

        for node_id in topo_order:
            deg = in_degree.get(node_id, 0)
            if deg != current_degree:
                if current_level:
                    levels.append(current_level)
                current_level = [node_id]
                current_degree = deg
            else:
                current_level.append(node_id)

        if current_level:
            levels.append(current_level)

        return levels

    # -- Serialization --

    def to_dict(self) -> dict:
        """Serialize the entire workflow to a dict."""
        return {
            "name": self.name,
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "links": [l.to_dict() for l in self._links],
        }

    def from_dict(self, data: dict, node_factory: Callable[[str], NodeBase | None] | None = None):
        """Load a workflow from a dict.

        Args:
            data: Serialized workflow dict.
            node_factory: Function(type_name) -> NodeBase for deserializing nodes.
        """
        self.name = data.get("name", "新建流程")
        self._nodes.clear()
        self._links.clear()

        # Deserialize nodes
        node_map: dict[str, NodeBase] = {}
        for node_data in data.get("nodes", []):
            type_name = node_data.get("type", "")
            if node_factory:
                node = node_factory(type_name)
            else:
                node = None
            if node is None:
                continue
            if hasattr(node, "restore_from_dict"):
                node.restore_from_dict(node_data)
            else:
                node._id = node_data.get("id", node._id)
            node.diagram_data = self
            node_map[node._id] = node
            self._nodes[node._id] = node

        # Deserialize links
        for link_data in data.get("links", []):
            link = LinkData.from_dict(link_data)
            self._links.append(link)

            # Rebuild adjacency
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
        """Remove all nodes and links."""
        self._nodes.clear()
        self._links.clear()
        self._execution_order.clear()
        self.state = WorkflowState.IDLE
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)

    def dispose(self):
        """Clean up all resources."""
        self.clear()
        for node in list(self._nodes.values()):
            node.dispose()
        self._nodes.clear()

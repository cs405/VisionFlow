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


class WorkflowState(Enum):
    """Execution state of the workflow engine."""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    COMPLETED = auto()
    ERROR = auto()


class WorkflowEngine:
    """Manages a node graph and executes it.

    Ported from C# IFlowableDiagramData + DiagramDataBase + FlowableDiagramData.
    Each WorkflowEngine instance represents one diagram/document.
    """

    def __init__(self, name: str = "新建流程"):
        self.name = name
        self.state: WorkflowState = WorkflowState.IDLE
        self._nodes: dict[str, NodeBase] = {}
        self._links: list[LinkData] = []
        self._execution_order: list[str] = []
        self._max_workers: int = 4
        self._invoke_count: int = 0
        self.result_image_source: Any = None

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

    def get_start_nodes(self) -> list[NodeBase]:
        """Get root nodes (no upstream connections)."""
        return [n for n in self._nodes.values() if len(n.from_node_datas) == 0]

    # -- Link management --

    def add_link(self, from_node_id: str, to_node_id: str,
                 from_port_dock: PortDock = PortDock.BOTTOM,
                 to_port_dock: PortDock = PortDock.TOP) -> LinkData | None:
        """Create a link between two nodes."""
        from_node = self._nodes.get(from_node_id)
        to_node = self._nodes.get(to_node_id)
        if not from_node or not to_node:
            return None

        # Find matching ports
        from_port = None
        to_port = None
        for p in from_node.ports:
            if p.dock == from_port_dock and p.is_output:
                from_port = p
                break
        for p in to_node.ports:
            if p.dock == to_port_dock and p.is_input:
                to_port = p
                break

        if not from_port or not to_port:
            return None

        link = LinkData(
            from_node_id=from_node_id,
            from_port_id=from_port.port_id,
            to_node_id=to_node_id,
            to_port_id=to_port.port_id,
        )
        self._links.append(link)

        # Update adjacency
        from_port.connected_links.append(link)
        to_port.connected_links.append(link)
        to_node.from_node_datas.append(from_node)
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

        # Update adjacency
        to_node = self._nodes.get(link.to_node_id)
        from_node = self._nodes.get(link.from_node_id)
        if to_node and from_node:
            if from_node in to_node.from_node_datas:
                to_node.from_node_datas.remove(from_node)
            if to_node in from_node.to_node_datas:
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

    # -- Execution --

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

            self.state = WorkflowState.COMPLETED
            event_system.publish(EventType.WORKFLOW_COMPLETED, sender=self, result=last_result)
            return last_result

        except Exception as e:
            self.state = WorkflowState.ERROR
            result = FlowableResult.error(message=str(e))
            event_system.publish(EventType.WORKFLOW_ERROR, sender=self, result=result)
            return result

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
        """Stop execution."""
        self.state = WorkflowState.STOPPED
        event_system.publish(EventType.WORKFLOW_STOPPED, sender=self)

    def _execute_node(self, node: NodeBase) -> FlowableResult:
        """Execute a single node."""
        self._invoke_count += 1

        # Find the incoming link data
        previors = None
        for link in self._links:
            if link.to_node_id == node.node_id:
                previors = link
                break

        if isinstance(node, VisionNodeData):
            result = node.invoke(previors, self)
            # Sleep for invoke delay
            import time
            time.sleep(node.invoke_milliseconds_delay / 1000.0)
            return result

        # Non-vision node: just pass through
        return FlowableResult.ok()

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

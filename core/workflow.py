"""
流程管理器 - 管理节点和连接，执行拓扑排序
"""

from typing import Dict, List, Set, Optional, Any, Tuple
from collections import deque
import json
import os

from .node_base import NodeBase
from .registry import NodeRegistry
from .events import EventBus, Event, EventType
from .data_packet import DataType


class Workflow:
    """工作流管理器"""

    def __init__(self):
        self.nodes: Dict[str, NodeBase] = {}
        self.connections: List[Dict] = []

        # 图结构（用于拓扑排序）
        self._adj: Dict[str, List[str]] = {}
        self._in_degree: Dict[str, int] = {}

        # 事件总线
        self._event_bus = EventBus()

        # 项目相关
        self.project_path: Optional[str] = None
        self.project_name: str = "未命名项目"

    # ========== 节点管理 ==========

    def add_node(self, node: NodeBase) -> bool:
        """添加节点"""
        if node.node_id in self.nodes:
            return False

        self.nodes[node.node_id] = node
        self._rebuild_graph()

        # 发送事件
        self._event_bus.emit(Event(
            type=EventType.WORKFLOW_NODE_ADDED,
            data={"node": node}
        ))
        self._event_bus.emit_log("INFO", f"添加节点: {node.name} ({node.node_id[:8]})")
        return True

    def remove_node(self, node_id: str) -> bool:
        """删除节点"""
        if node_id not in self.nodes:
            return False

        node = self.nodes[node_id]

        # 删除相关连接
        self.connections = [c for c in self.connections
                            if c["from_node"] != node_id and c["to_node"] != node_id]

        del self.nodes[node_id]
        self._rebuild_graph()

        # 发送事件
        self._event_bus.emit(Event(
            type=EventType.WORKFLOW_NODE_REMOVED,
            data={"node_id": node_id, "node_name": node.name}
        ))
        self._event_bus.emit_log("INFO", f"删除节点: {node.name}")
        return True

    def get_node(self, node_id: str) -> Optional[NodeBase]:
        """获取节点"""
        return self.nodes.get(node_id)

    # ========== 连接管理 ==========

    def add_connection(self, from_node: str, from_socket: str,
                       to_node: str, to_socket: str) -> bool:
        """添加连接"""
        # 检查节点是否存在
        if from_node not in self.nodes or to_node not in self.nodes:
            return False

        # 检查类型兼容性
        from_node_obj = self.nodes[from_node]
        to_node_obj = self.nodes[to_node]

        from_socket_def = self._find_socket(from_node_obj, from_socket, is_input=False)
        to_socket_def = self._find_socket(to_node_obj, to_socket, is_input=True)

        if not from_socket_def or not to_socket_def:
            return False

        # 检查类型匹配
        if not self._is_type_compatible(from_socket_def.data_type, to_socket_def.data_type):
            self._event_bus.emit_log("ERROR",
                                     f"类型不匹配: {from_socket_def.data_type.value} -> {to_socket_def.data_type.value}")
            return False

        # 检查目标输入端口是否已被连接（非多连接端口）
        if not to_socket_def.multi_connection:
            existing = self.get_connections_to(to_node, to_socket)
            if existing:
                return False

        # 检查循环依赖
        if self._would_create_cycle(from_node, to_node):
            self._event_bus.emit_log("ERROR", "连接会创建循环依赖")
            return False

        # 添加连接
        connection = {
            "from_node": from_node,
            "from_socket": from_socket,
            "to_node": to_node,
            "to_socket": to_socket
        }
        self.connections.append(connection)
        self._rebuild_graph()

        # 发送事件
        self._event_bus.emit(Event(
            type=EventType.WORKFLOW_EDGE_ADDED,
            data=connection
        ))
        self._event_bus.emit_log("INFO", f"添加连接: {from_node[:8]}.{from_socket} -> {to_node[:8]}.{to_socket}")
        return True

    def remove_connection(self, from_node: str, from_socket: str,
                          to_node: str, to_socket: str) -> bool:
        """删除连接"""
        original_len = len(self.connections)
        self.connections = [c for c in self.connections
                            if not (c["from_node"] == from_node and
                                    c["from_socket"] == from_socket and
                                    c["to_node"] == to_node and
                                    c["to_socket"] == to_socket)]

        if len(self.connections) < original_len:
            self._rebuild_graph()
            self._event_bus.emit(Event(
                type=EventType.WORKFLOW_EDGE_REMOVED,
                data={"from_node": from_node, "from_socket": from_socket,
                      "to_node": to_node, "to_socket": to_socket}
            ))
            return True
        return False

    def get_connections_to(self, node_id: str, socket_name: str) -> List[Dict]:
        """获取连接到指定端口的所有连接"""
        return [c for c in self.connections
                if c["to_node"] == node_id and c["to_socket"] == socket_name]

    def get_connections_from(self, node_id: str, socket_name: str) -> List[Dict]:
        """获取从指定端口出发的所有连接"""
        return [c for c in self.connections
                if c["from_node"] == node_id and c["from_socket"] == socket_name]

    # ========== 辅助方法 ==========

    def _find_socket(self, node: NodeBase, socket_name: str, is_input: bool) -> Optional:
        """查找端口定义"""
        sockets = node.input_sockets if is_input else node.output_sockets
        for s in sockets:
            if s.name == socket_name:
                return s
        return None

    def _is_type_compatible(self, from_type: DataType, to_type: DataType) -> bool:
        """检查数据类型是否兼容"""
        if from_type == to_type:
            return True
        if to_type == DataType.ANY or from_type == DataType.ANY:
            return True
        # 灰度图可以作为图像输入
        if to_type == DataType.IMAGE and from_type == DataType.GRAY_IMAGE:
            return True
        return False

    def _would_create_cycle(self, from_node: str, to_node: str) -> bool:
        """检查添加连接是否会创建循环依赖"""
        # 临时添加连接
        temp_adj = {nid: list(neighbors) for nid, neighbors in self._adj.items()}
        temp_adj.setdefault(from_node, []).append(to_node)

        # DFS检测环
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in temp_adj.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for node in temp_adj:
            if node not in visited:
                if has_cycle(node):
                    return True
        return False

    def _rebuild_graph(self):
        """重建依赖图"""
        self._adj = {nid: [] for nid in self.nodes}
        self._in_degree = {nid: 0 for nid in self.nodes}

        for conn in self.connections:
            from_id = conn["from_node"]
            to_id = conn["to_node"]
            if from_id in self._adj and to_id in self._adj:
                self._adj[from_id].append(to_id)
                self._in_degree[to_id] += 1

    # ========== 执行引擎 ==========

    def get_execution_order(self) -> List[str]:
        """获取拓扑排序后的执行顺序"""
        in_degree = self._in_degree.copy()
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            nid = queue.popleft()
            order.append(nid)

            for neighbor in self._adj.get(nid, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.nodes):
            # 有循环依赖，返回所有节点（按原顺序）
            self._event_bus.emit_log("ERROR", "检测到循环依赖，无法自动排序")
            return list(self.nodes.keys())

        return order

    def get_inputs_for_node(self, node_id: str) -> Dict[str, Any]:
        """收集节点的输入数据"""
        inputs = {}
        for conn in self.connections:
            if conn["to_node"] == node_id:
                from_node = self.nodes.get(conn["from_node"])
                if from_node and hasattr(from_node, '_last_outputs'):
                    value = from_node._last_outputs.get(conn["from_socket"])
                    if value is not None:
                        inputs[conn["to_socket"]] = value
        return inputs

    def execute(self) -> Dict[str, Dict]:
        """执行整个工作流"""
        order = self.get_execution_order()
        results = {}

        self._event_bus.emit_log("INFO", f"开始执行工作流，共 {len(order)} 个节点")

        for node_id in order:
            node = self.nodes[node_id]
            inputs = self.get_inputs_for_node(node_id)
            outputs = node.execute(inputs)
            results[node_id] = outputs

        # 发送执行完成事件
        self._event_bus.emit(Event(
            type=EventType.WORKFLOW_EXECUTED,
            data={"results": results}
        ))
        self._event_bus.emit_log("INFO", "工作流执行完成")

        return results

    def execute_single(self, node_id: str) -> Dict:
        """单独执行一个节点（用于调试）"""
        node = self.nodes.get(node_id)
        if not node:
            return {}

        inputs = self.get_inputs_for_node(node_id)
        return node.execute(inputs)

    # ========== 序列化 ==========

    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "project_name": self.project_name,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "connections": self.connections.copy()
        }

    def from_dict(self, data: Dict):
        """从字典反序列化"""
        # 清空当前状态
        self.nodes.clear()
        self.connections.clear()

        self.project_name = data.get("project_name", "未命名项目")

        # 重建节点
        for node_data in data.get("nodes", []):
            node_type = node_data.get("type")
            node = NodeRegistry.create_instance(node_type, node_data.get("id"))
            if node:
                node.from_dict(node_data)
                self.nodes[node.node_id] = node

        # 重建连接
        for conn in data.get("connections", []):
            self.connections.append(conn)

        self._rebuild_graph()

        self._event_bus.emit_log("INFO", f"加载项目: {self.project_name}")

    def save(self, filepath: str):
        """保存到文件"""
        data = self.to_dict()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.project_path = filepath

        self._event_bus.emit(Event(
            type=EventType.PROJECT_SAVED,
            data={"path": filepath}
        ))

    def load(self, filepath: str):
        """从文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.from_dict(data)
        self.project_path = filepath

        self._event_bus.emit(Event(
            type=EventType.PROJECT_LOADED,
            data={"path": filepath}
        ))

    def clear(self):
        """清空工作流"""
        self.nodes.clear()
        self.connections.clear()
        self._rebuild_graph()

        self._event_bus.emit(Event(
            type=EventType.WORKFLOW_CLEARED,
            data={}
        ))
        self._event_bus.emit_log("INFO", "工作流已清空")
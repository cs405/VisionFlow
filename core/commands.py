"""
撤销/重做命令系统
将图表修改封装为可逆命令。
支持：添加/删除/移动节点、添加/删除链接、批量命令。
与 GUI 框架无关：使用简单的 (x, y) 元组表示位置。
GUI 层通过 `_to_point()` 函数转换 Qt 点
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from PyQt5.QtCore import QPointF


class Command(ABC):
    """
    命令模式基类（抽象类）

    功能：定义可撤销/重做的操作接口，场景对象在执行/撤销时传入
    用途：实现撤销/重做功能（Undo/Redo）的核心抽象
    """

    def __init__(self):
        # 初始化命令描述信息，默认为类名
        # 可在子类中覆盖此属性以提供更友好的操作描述
        self._description = self.__class__.__name__

    @abstractmethod
    def execute(self, scene: Any) -> Any:
        """
        在指定场景上执行命令

        参数：
            scene: 场景对象（如流程图、画布、文档等）

        返回：
            执行结果（类型取决于具体命令实现）

        说明：
            子类必须实现此方法，定义命令的具体执行逻辑
        """
        ...

    @abstractmethod
    def undo(self, scene: Any) -> Any:
        """
        在指定场景上撤销命令（恢复到执行前的状态）

        参数：
            scene: 场景对象（与 execute 接收的同一个场景）

        返回：
            撤销结果（类型取决于具体命令实现）

        说明：
            子类必须实现此方法，定义命令的回滚逻辑
            execute() 和 undo() 应该互为逆操作
        """
        ...

    @property
    def description(self) -> str:
        """
        获取命令的描述信息

        返回：
            命令描述字符串，用于UI显示（如撤销/重做菜单项文本）

        说明：
            默认返回类名，子类可覆盖 _description 属性以自定义描述
        """
        return self._description


class BatchCommand(Command):
    """
    批量命令类（组合命令/宏命令）

    功能：将多个命令组合为一个原子操作，统一执行和撤销
    用途：实现复杂操作的撤销/重做支持（如一次拖拽添加多个节点）
    """

    def __init__(self, description: str = "批量操作"):
        """
        初始化批量命令

        参数：
            description: 命令描述文本（默认为"批量操作"）
                        用于UI显示（如撤销菜单项显示"撤销 批量操作"）
        """
        super().__init__()  # 调用父类构造函数
        self._description = description  # 覆盖命令描述（自定义文本）
        self._commands: list[Command] = []  # 子命令列表（存储待批量执行的命令）
        self._executed: list[Command] = []  # 本轮已执行的子命令（用于失败回滚）

    def add(self, cmd: Command):
        """
        向批量命令中添加子命令

        参数：
            cmd: 要添加的命令对象（继承自Command的实例）

        说明：
            - 可以按顺序添加多个命令
            - 执行时会按照添加顺序执行
            - 撤销时会按照相反顺序撤销
        """
        self._commands.append(cmd)

    def execute(self, scene: Any) -> Any:
        """
        批量执行所有子命令

        参数：
            scene: 场景对象（如流程图、画布等）

        说明：
            - 按照添加的顺序依次执行每个命令
            - 任何一个命令失败时，先撤销失败命令的副作用，再逆序撤销已执行命令，
              然后清空 _executed 列表（后续 CommandStack 的 undo 调用成为安全空操作）
        """
        self._executed.clear()
        for cmd in self._commands:
            try:
                cmd.execute(scene)
            except Exception:
                # 撤销失败命令可能已产生的副作用
                try:
                    cmd.undo(scene)
                except Exception:
                    pass
                # 逆序撤销之前已执行的命令
                for c in reversed(self._executed):
                    try:
                        c.undo(scene)
                    except Exception:
                        pass
                self._executed.clear()
                raise
            self._executed.append(cmd)

    def undo(self, scene: Any) -> Any:
        """
        批量撤销所有子命令（逆序撤销）

        参数：
            scene: 场景对象

        说明：
            - 按执行顺序的逆序撤销（后执行的先撤销）
            - 仅撤销实际已执行的子命令（失败时未执行的不处理）
        """
        for cmd in reversed(self._executed):
            cmd.undo(scene)
        self._executed.clear()


class AddNodeCommand(Command):
    """
    添加节点命令类（继承自Command）

    功能：在场景中的指定位置添加一个节点
    支持撤销/重做：添加操作可以被撤销（删除节点）和重做（重新添加）
    """

    def __init__(self, scene, node_data: Any, pos=None, group_name: str = ""):
        """
        初始化添加节点命令

        参数：
            scene: 场景对象（流程图/画布实例），用于执行操作
            node_data: 节点数据对象（包含节点属性、名称、类型等）
            pos: 节点位置坐标（可选，None表示使用默认位置）
            group_name: 节点所属分组名称（用于组织节点，如"图像数据源"等）
        """
        super().__init__()  # 调用父类构造函数
        self._node_data = node_data  # 保存节点数据（用于执行时创建节点）
        self._pos = pos  # 保存节点位置（坐标）
        self._group_name = group_name  # 保存分组名称（用于UI分类）
        self._node_id = node_data.node_id  # 保存节点唯一标识符（用于撤销时定位）
        self._description = f"添加节点: {node_data.name}"  # 命令描述（显示为"添加节点: 节点名称"）
        self._scene = scene  # 保存场景引用（供undo使用）

    def execute(self, scene: Any) -> Any:
        """
        执行命令：在场景中添加节点

        参数：
            scene: 场景对象（通常与构造时传入的相同）

        返回：
            添加节点操作的结果（可能是创建的节点对象或ID）

        说明：
            - 如果提供了位置信息，则在指定位置创建节点
            - 否则使用默认位置
            - 使用辅助函数 _to_point() 转换坐标格式
        """
        # 转换位置坐标（如果提供了位置信息）
        pos = _to_point(self._pos) if self._pos else None
        # 调用场景方法添加节点
        return scene.add_node_item(self._node_data, pos, self._group_name)

    def undo(self, scene: Any) -> Any:
        """
        撤销命令：从场景中删除节点

        参数：
            scene: 场景对象

        说明：
            - 使用保存的 _node_id 定位要删除的节点
            - 不关心参数 scene 的值（内部使用构造时保存的 _scene）
            - 注意：scene 参数和 self._scene 可能是同一个对象
        """
        # 调用场景方法删除节点
        scene.remove_node_item(self._node_id)


class RemoveNodeCommand(Command):
    """
    删除节点命令类（继承自Command）

    功能：从场景中删除一个节点，并保存节点的完整信息以便撤销时恢复
    支持撤销/重做：删除操作可以被撤销（恢复节点及其所有属性）

    与 AddNodeCommand 互为逆操作：
        AddNodeCommand.execute() = 添加节点
        RemoveNodeCommand.execute() = 删除节点
        AddNodeCommand.undo() = 删除节点
        RemoveNodeCommand.undo() = 添加节点
    """

    def __init__(self, scene, node_id: str):
        """
        初始化删除节点命令

        参数：
            scene: 场景对象（流程图/画布实例）
            node_id: 要删除的节点唯一标识符

        说明：
            - 不立即删除节点，等待 execute() 调用
            - 初始化时不保存节点数据（执行时才获取）
            - 这种设计允许命令创建后延迟执行
        """
        super().__init__()
        self._node_id = node_id  # 节点ID（用于定位要删除的节点）
        self._saved_node: Any = None  # 保存的节点数据（用于撤销时恢复）
        self._saved_pos = (0.0, 0.0)  # 保存的节点位置（用于撤销时恢复）
        self._group_name: str = ""  # 保存的分组名称（用于撤销时分类）
        self._description = f"删除节点: {node_id}"  # 命令描述（UI显示文本）

    def execute(self, scene: Any) -> Any:
        """
        执行命令：从场景中删除节点并保存其信息

        参数：
            scene: 场景对象

        执行流程：
            1. 通过节点ID获取节点对象
            2. 保存节点数据（用于撤销恢复）
            3. 保存节点位置坐标
            4. 从场景中删除节点

        说明：
            - 删除前必须保存所有需要恢复的信息
            - 如果节点不存在则直接返回（容错处理）
        """
        # 步骤1：获取要删除的节点对象
        item = scene.get_node_item(self._node_id)

        # 容错处理：节点可能已被其他操作删除
        if item is None:
            return

        # 步骤2：保存节点数据（用于撤销时重建节点）
        self._saved_node = item.node_data

        # 步骤3：保存节点位置（用于撤销时恢复到原位置）
        p = item.pos()
        self._saved_pos = (p.x(), p.y())

        # 步骤4：从场景中删除节点
        # 注意：此处假设 remove_node_item 也会删除该节点相关的所有连线
        scene.remove_node_item(self._node_id)

    def undo(self, scene: Any) -> Any:
        """
        撤销命令：恢复被删除的节点

        参数：
            scene: 场景对象

        说明：
            - 使用保存的节点数据和位置重建节点
            - 注意：sync_workflow=False 表示暂不同步工作流（批量操作优化）
            - 恢复的节点会自动包含其端口信息（因为 node_data 中保存了完整数据）
        """
        # 确保已保存节点数据（execute 必须已执行）
        if self._saved_node is None:
            return

        # 转换位置坐标为 Qt 支持的格式
        pos = _to_point(self._saved_pos)

        # 重新添加节点到场景
        # sync_workflow=False：不立即同步工作流（可能用于批量操作性能优化）
        scene.add_node_item(self._saved_node, pos, self._group_name, sync_workflow=False)


class AddLinkCommand(Command):
    """
    添加连线命令类（继承自Command）

    功能：在两个插座（Socket）之间创建连线
    支持撤销/重做：连线可以被删除（撤销）和恢复（重做）

    注意：这是添加连线的命令，与之对应的删除连线命令是 RemoveLinkCommand
    """

    def __init__(self, scene, from_socket: Any, to_socket: Any):
        """
        初始化添加连线命令

        参数：
            scene: 场景对象（流程图/画布实例），用于执行操作
            from_socket: 源插座对象（连线起点，通常是输出端口）
            to_socket: 目标插座对象（连线终点，通常是输入端口）

        说明：
            - 不直接保存插座引用，而是保存节点ID和端口ID
            - 这样做可以避免悬空引用（节点/插座可能被删除）
            - 在execute时通过ID重新获取实际对象
            - 这种设计使命令可以序列化保存（保存/加载场景）
        """
        super().__init__()

        # 保存源节点的标识信息
        self._from_node_id = from_socket.port.node_id  # 源节点唯一标识
        self._from_port_id = from_socket.port.port_id  # 源端口ID

        # 保存目标节点的标识信息
        self._to_node_id = to_socket.port.node_id  # 目标节点唯一标识
        self._to_port_id = to_socket.port.port_id  # 目标端口ID

        self._link_id: str = ""  # 连线ID（执行后填充，用于撤销）
        self._description = "添加连线"  # 命令描述（UI显示文本）

    def execute(self, scene: Any) -> Any:
        """
        执行命令：在两个插座之间创建连线

        参数：
            scene: 场景对象

        返回：
            创建的连线对象（Edge），失败时返回None

        执行流程：
            1. 根据保存的节点ID获取源节点和目标节点
            2. 验证两个节点都存在
            3. 从节点中获取对应的插座对象
            4. 验证两个插座都存在且类型兼容（输出→输入）
            5. 调用场景方法创建连线
            6. 保存连线ID供撤销使用
        """
        # 步骤1：通过节点ID获取节点对象
        from_item = scene.get_node_item(self._from_node_id)
        to_item = scene.get_node_item(self._to_node_id)

        # 步骤2：验证节点存在性（节点可能已被删除）
        if not from_item or not to_item:
            return None

        # 步骤3：通过端口ID获取插座对象
        fs = from_item.get_socket_by_port_id(self._from_port_id)
        ts = to_item.get_socket_by_port_id(self._to_port_id)

        # 步骤4：验证插座存在并创建连线
        if fs and ts:
            # 调用场景方法创建连线（会检查连接是否合法）
            edge = scene.create_edge(fs, ts)

            # 步骤5：保存连线ID（如果创建成功）
            if edge and edge.link_data:
                self._link_id = edge.link_data.link_id  # 保存ID供撤销使用
            return edge

        return None  # 插座不存在，无法创建连线

    def undo(self, scene: Any) -> Any:
        """
        撤销命令：删除已创建的连线

        参数：
            scene: 场景对象

        说明：
            - 只有当连线ID存在时才执行删除
            - 使用保存的 _link_id 精确定位要删除的连线
            - 场景参数与execute时的scene应该是同一个对象
            - 删除操作通常是幂等的（重复删除不会出错）
        """
        if self._link_id:  # 确保连线ID有效（execute已成功执行）
            scene.remove_edge_item(self._link_id)  # 从场景中移除连线


class RemoveLinkCommand(Command):
    """
    删除连线命令类（继承自Command）

    功能：从场景中删除一条连线，并保存连线的端点信息以便撤销时恢复
    支持撤销/重做：删除操作可以被撤销（恢复连线及其端点连接）

    与 AddLinkCommand 互为逆操作：
        AddLinkCommand.execute() = 添加连线
        RemoveLinkCommand.execute() = 删除连线
        AddLinkCommand.undo() = 删除连线
        RemoveLinkCommand.undo() = 添加连线
    """

    def __init__(self, scene, link_id: str):
        """
        初始化删除连线命令

        参数：
            scene: 场景对象（流程图/画布实例）
            link_id: 要删除的连线唯一标识符

        说明：
            - 不立即删除连线，等待 execute() 调用
            - 初始化时不保存连线信息（执行时才获取）
            - 这种设计允许命令创建后延迟执行
        """
        super().__init__()
        self._link_id = link_id  # 连线ID（用于定位要删除的连线）
        self._saved_from_node = ""  # 保存的源节点ID（用于撤销时恢复）
        self._saved_to_node = ""  # 保存的目标节点ID（用于撤销时恢复）
        self._saved_from_port = ""  # 保存的源端口ID（用于撤销时恢复）
        self._saved_to_port = ""  # 保存的目标端口ID（用于撤销时恢复）
        self._description = f"删除连线: {link_id}"  # 命令描述（UI显示文本）

    def execute(self, scene: Any) -> Any:
        """
        执行命令：从场景中删除连线并保存其端点信息

        参数：
            scene: 场景对象

        执行流程：
            1. 通过连线ID获取连线对象
            2. 从连线数据中提取端点信息（源节点、源端口、目标节点、目标端口）
            3. 保存这些信息供撤销时使用
            4. 从场景中删除连线

        说明：
            - 删除前必须保存所有需要恢复的信息
            - 如果连线不存在则直接返回（容错处理）
        """
        # 步骤1：获取要删除的连线对象
        edge = scene.get_edge_item(self._link_id)

        # 步骤2：提取并保存连线端点信息（用于撤销时重建）
        if edge and edge.link_data:
            ld = edge.link_data
            # 保存源节点和源端口信息
            self._saved_from_node = ld.from_node_id
            self._saved_from_port = ld.from_port_id
            # 保存目标节点和目标端口信息
            self._saved_to_node = ld.to_node_id
            self._saved_to_port = ld.to_port_id

        # 步骤3：从场景中删除连线
        scene.remove_edge_item(self._link_id)

    def undo(self, scene: Any) -> Any:
        """
        撤销命令：恢复被删除的连线

        参数：
            scene: 场景对象

        执行流程：
            1. 根据保存的节点ID获取源节点和目标节点
            2. 验证两个节点都存在
            3. 根据保存的端口ID获取源插座和目标插座
            4. 重新创建连线

        说明：
            - 使用保存的端点信息重建连线
            - sync_workflow=True 表示立即同步工作流
            - 确保节点和端口在撤销时仍然存在
        """
        # 步骤1：根据节点ID获取节点对象
        from_item = scene.get_node_item(self._saved_from_node)
        to_item = scene.get_node_item(self._saved_to_node)

        # 步骤2：验证节点存在性（节点可能已被删除）
        if not from_item or not to_item:
            return

        # 步骤3：根据端口ID获取插座对象
        fs = from_item.get_socket_by_port_id(self._saved_from_port)
        ts = to_item.get_socket_by_port_id(self._saved_to_port)

        # 步骤4：验证插座存在并重建连线
        if fs and ts:
            # sync_workflow=True：立即同步工作流状态
            scene.create_edge(fs, ts, sync_workflow=True)


class MoveNodeCommand(Command):
    """
    移动节点命令类（继承自Command）

    功能：将节点从旧位置移动到新位置
    支持撤销/重做：可以在新旧位置之间来回切换

    应用场景：
        - 用户拖拽节点移动
        - 键盘方向键微调位置
        - 节点对齐/排列操作
        - 撤销/重做移动操作
    """

    def __init__(self, scene, node_id: str, old_pos, new_pos):
        """
        初始化移动节点命令

        参数：
            scene: 场景对象（流程图/画布实例），用于获取节点
            node_id: 要移动的节点唯一标识符
            old_pos: 移动前的位置（用于撤销时恢复）
            new_pos: 移动后的位置（用于执行/重做）

        说明：
            - 记录移动前后的位置信息
            - 不立即执行移动，等待 execute() 调用
            - 位置格式可以是 tuple、QPointF、QPoint 等
        """
        super().__init__()
        self._node_id = node_id  # 节点ID（用于定位要移动的节点）
        self._old_pos = old_pos  # 原始位置（撤销时使用）
        self._new_pos = new_pos  # 目标位置（执行时使用）
        self._description = f"移动节点: {node_id}"  # 命令描述（UI显示文本）

    def execute(self, scene: Any) -> Any:
        """
        执行命令：将节点移动到新位置

        参数：
            scene: 场景对象

        说明：
            - 通过节点ID获取节点对象
            - 如果节点不存在则直接返回（容错处理）
            - 使用 _to_point() 转换坐标格式为 QPointF
            - 设置节点位置到新坐标

        注意：
            - 此方法会在命令执行和重做时被调用
            - 移动是瞬时的，无动画效果
        """
        # 通过ID获取节点对象
        item = scene.get_node_item(self._node_id)

        # 容错处理：节点可能已被其他操作删除
        if item is None:
            return

        # 将节点移动到新位置（_to_point 确保坐标格式正确）
        item.setPos(_to_point(self._new_pos))

    def undo(self, scene: Any) -> Any:
        """
        撤销命令：将节点移回旧位置

        参数：
            scene: 场景对象

        说明：
            - 撤销时恢复节点到移动前的位置
            - 与 execute 互为逆操作
            - 同样使用 _to_point() 转换坐标格式

        注意：
            - 多次撤销/重做会在新旧位置之间来回切换
            - 位置精度应保持一致（避免浮点数误差累积）
        """
        # 通过ID获取节点对象
        item = scene.get_node_item(self._node_id)

        # 容错处理：节点可能已被删除
        if item is None:
            return

        # 将节点移回原始位置
        item.setPos(_to_point(self._old_pos))


class CommandStack:
    """
    命令栈类（撤销/重做管理器）

    功能：管理命令的执行、撤销和重做操作
    设计模式：命令模式（Command Pattern）的调用者（Invoker）

    核心特性：
        - 执行命令时立即执行并压入撤销栈
        - 支持撤销（Undo）和重做（Redo）操作
        - 维护撤销栈和重做栈两个独立栈
        - 提供UI状态查询属性（是否可撤销、可重做等）

    使用流程：
        1. 创建命令对象（如 AddNodeCommand）
        2. 调用 command_stack.execute(cmd) 执行命令
        3. 用户按 Ctrl+Z 时调用 undo()
        4. 用户按 Ctrl+Y 或 Ctrl+Shift+Z 时调用 redo()

    注意：场景对象必须在执行命令前设置
    """

    def __init__(self, scene=None):
        """
        初始化命令栈

        参数：
            scene: 场景对象（流程图/画布实例），可以为 None
                   如果为 None，需要在执行命令前通过 set_scene() 设置

        说明：
            - 场景对象会被传递给每个命令的 execute/undo 方法
            - 所有命令共享同一个场景对象
        """
        self._scene = scene  # 场景对象（命令执行的目标）
        self._undo_stack: list[Command] = []  # 撤销栈（已执行的命令）
        self._redo_stack: list[Command] = []  # 重做栈（已撤销的命令）

    def set_scene(self, scene):
        """
        设置场景对象

        参数：
            scene: 场景对象

        使用场景：
            - 命令栈创建时没有场景对象
            - 需要在运行时动态切换场景
            - 延迟初始化场景引用
        """
        self._scene = scene

    def execute(self, cmd: Command) -> Any:
        """
        执行命令并压入撤销栈

        参数：
            cmd: 要执行的命令对象

        返回：
            命令执行的结果（取决于具体命令）

        执行流程：
            1. 调用命令的 execute() 方法
            2. 将命令压入撤销栈
            3. 清空重做栈（新操作后不能再重做之前的操作）
            4. 返回执行结果

        说明：
            - 命令立即执行，不延迟
            - 执行新命令后会清空重做栈（符合标准撤销/重做行为）
            - 场景对象在命令执行时传入
        """
        # 步骤1：执行命令（传入场景对象）
        # 若执行失败则尝试回滚，避免部分修改残留在场景中
        try:
            result = cmd.execute(self._scene)
        except Exception:
            try:
                cmd.undo(self._scene)
            except Exception:
                pass
            raise

        # 步骤2：将命令压入撤销栈（仅在执行成功后）
        self._undo_stack.append(cmd)

        # 步骤3：清空重做栈（新操作使之前重做路径失效）
        self._redo_stack.clear()

        return result

    def undo(self) -> bool:
        """
        撤销上一个命令

        返回：
            bool: 是否成功执行撤销操作

        执行流程：
            1. 检查撤销栈是否为空
            2. 弹出栈顶命令（最近执行的命令）
            3. 调用命令的 undo() 方法
            4. 将命令压入重做栈（以便后续重做）
            5. 返回 True 表示撤销成功

        说明：
            - 只有存在可撤销命令时才执行
            - 撤销后命令移动到重做栈
        """
        # 检查是否有命令可撤销
        if not self._undo_stack:
            return False

        # 弹出最近执行的命令
        cmd = self._undo_stack.pop()

        # 调用命令的撤销方法（传入场景对象）
        cmd.undo(self._scene)

        # 将撤销的命令压入重做栈（支持重做）
        self._redo_stack.append(cmd)

        return True

    def redo(self) -> bool:
        """
        重做被撤销的命令

        返回：
            bool: 是否成功执行重做操作

        执行流程：
            1. 检查重做栈是否为空
            2. 弹出栈顶命令（最近撤销的命令）
            3. 调用命令的 execute() 方法
            4. 将命令压回撤销栈
            5. 返回 True 表示重做成功

        说明：
            - 只有存在可重做命令时才执行
            - 重做后命令移回撤销栈
        """
        # 检查是否有命令可重做
        if not self._redo_stack:
            return False

        # 弹出最近撤销的命令
        cmd = self._redo_stack.pop()

        # 重新执行命令（传入场景对象）
        cmd.execute(self._scene)

        # 将重做的命令压回撤销栈
        self._undo_stack.append(cmd)

        return True

    def clear(self):
        """
        清空所有命令栈

        说明：
            - 清空撤销栈和重做栈
            - 不执行任何命令
            - 用于重置场景时释放命令历史
            - 不会影响场景中已有的内容
        """
        self._undo_stack.clear()
        self._redo_stack.clear()

    @property
    def can_undo(self) -> bool:
        """
        检查是否可以撤销

        返回：
            bool: True 表示有命令可撤销，False 表示无

        用途：
            - 控制UI中"撤销"按钮的启用/禁用状态
            - 更新菜单项的敏感度
        """
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        """
        检查是否可以重做

        返回：
            bool: True 表示有命令可重做，False 表示无

        用途：
            - 控制UI中"重做"按钮的启用/禁用状态
            - 更新菜单项的敏感度
        """
        return len(self._redo_stack) > 0

    @property
    def undo_description(self) -> str:
        """
        获取下一个可撤销命令的描述文本

        返回：
            str: 命令描述文本，如果无命令则返回空字符串

        用途：
            - 在UI中显示"撤销 {操作描述}"（如"撤销 添加节点: 图像源"）
            - 提供更好的用户体验

        示例：
            - 返回 "添加节点: 图像源"
            - UI显示："撤销 添加节点: 图像源"
        """
        return self._undo_stack[-1].description if self._undo_stack else ""

    @property
    def redo_description(self) -> str:
        """
        获取下一个可重做命令的描述文本

        返回：
            str: 命令描述文本，如果无命令则返回空字符串

        用途：
            - 在UI中显示"重做 {操作描述}"（如"重做 移动节点: 节点1"）
            - 提供更好的用户体验

        示例：
            - 返回 "移动节点: 节点1"
            - UI显示："重做 移动节点: 节点1"
        """
        return self._redo_stack[-1].description if self._redo_stack else ""


# ── Point conversion (thread-safe lazy-initialized) ──────────────────────

import threading

_point_converter = None
_point_lock = threading.Lock()


def _to_point(pos):
    """Convert (x, y) tuple to framework-specific point type."""
    global _point_converter
    if _point_converter is None:
        with _point_lock:
            if _point_converter is None:
                try:
                    _point_converter = lambda p: QPointF(p[0], p[1])
                except ImportError:
                    _point_converter = lambda p: p
    return _point_converter(pos)

"""
VisionNodeData hierarchy - visual processing node classes.
Extracted from node_base.py.

Inheritance chain:
    NodeBase (node_base.py)
      -> VisionNodeDataBase (flow delay)
        -> ShowPropertyNodeDataBase (property presenter)
          -> HelpNodeDataBase (help URL)
            -> DemoNodeDataBase (demo parameters)
              -> VisionNodeData (Mat, ResultImages, invoke lifecycle)
"""

from __future__ import annotations

import time
import inspect
import numpy as np
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from core.data_packet import FlowableResult, FlowableInvokeMode, VisionResultImage
from core.events import EventType, event_system
from core.node_base import NodeBase, Property, PropertyGroupNames, Port, LinkData

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


# =============================================================================
# VisionNodeDataBase - 流延迟参数
# =============================================================================

class VisionNodeDataBase(NodeBase):
    """
    添加流程控制延迟参数的节点基类。
    """


# =============================================================================
# ShowPropertyNodeDataBase - 属性展示器
# =============================================================================

class ShowPropertyNodeDataBase(VisionNodeDataBase):
    """为属性面板提供属性展示器的基类。"""

    def get_property_presenter(self) -> Any:
        """返回在属性面板中显示的对象。默认返回自身。"""
        return self

# =============================================================================
# HelpNodeDataBase - 帮助/文档URL
# =============================================================================

class HelpNodeDataBase(ShowPropertyNodeDataBase):
    """提供带文档URL的帮助展示器的基类。"""

    def create_help_presenter(self) -> dict:
        """返回帮助面板所需的帮助信息。子类可重写以自定义。"""
        # 获取当前节点的类
        cls = type(self)
        # 获取类的文档字符串，取第一行作为简短描述
        doc = (cls.__doc__ or "").strip().split("\n")[0] if cls.__doc__ else ""
        return {
            # 帮助文档URL（使用类名作为路径）
            "url": f"https://github.com/cs405/visionflow/{cls.__name__}",
            # 节点名称
            "name": self.name,
            # 节点描述
            "description": doc or f"{self.name} - {cls.__name__}",
            # 源代码文件路径
            "source": inspect.getfile(cls),
        }

# =============================================================================
# DemoNodeDataBase - 示例/演示参数
# =============================================================================

class DemoNodeDataBase(HelpNodeDataBase):
    """添加演示/示例参数以展示参数系统模式的基类。"""

    # 示例：基本参数（用于演示如何在基本参数分组中添加参数）
    demo_base_parameter1 = Property("", name="示例：基本参数", group=PropertyGroupNames.BASE_PARAMETERS,
                                    description="用来演示如何增加基本参数", order=9999)
    # 示例：运行参数（用于演示如何在运行参数分组中添加参数）
    demo_run_parameter1 = Property("", name="示例：运行参数", group=PropertyGroupNames.RUN_PARAMETERS,
                                   description="用来演示如何增加结果参数", order=9999)
    # 示例：结果参数（只读，用于演示结果参数分组）
    demo_result1 = Property("", name="示例：结果参数", group=PropertyGroupNames.RESULT_PARAMETERS,
                            description="用来演示如何增加结果参数", readonly=True, order=9999)

    def create_result_presenter(self) -> Any:
        """为结果面板创建结果展示器。子类可重写。"""
        return None


# =============================================================================
# VisionNodeData - 核心视觉处理节点
# =============================================================================

class VisionNodeData(DemoNodeDataBase):
    """
    核心通用视觉处理节点。
    这是核心类——大多数视觉节点都继承自它。
    主要职责：
        - 维护 Mat 对象（当前图像的 NumPy 数组）
        - 提供 ResultImages 列表
        - 实现 Invoke 生命周期（查找源/来源、执行、返回结果）
        - 流程控制辅助函数：OK()、Error()、Break()
        - 图像处理管理
    """

    # UseInvokedPart - 控制输出是否进入历史记录/预览
    use_invoked_part = Property(True, name="启用输出历史记录", group=PropertyGroupNames.DISPLAY_PARAMETERS,
                                description="用于控制是否输出到历史记录和预览图像")

    def __init__(self):
        super().__init__()
        # 当前图像数据（NumPy数组）
        self._mat: np.ndarray | None = None
        # 原始图像数据（未经处理的源图像）
        self._original_mat: np.ndarray | None = None
        # 预处理后的输入图像（用于invoke_core处理）
        self._prepared_input: np.ndarray | None = None
        # 结果展示器
        self._result_presenter: Any = None
        # 累积裁剪偏移量 (x, y, w, h)，相对于原始图像
        # 由 ROINodeData / 匹配节点自动维护，ROIMapBackNode 只读不写
        self._crop_chain_offset: tuple = (0, 0, 0, 0)
        # 本轮执行状态: None(未执行) / "completed"(成功) / "error"(失败) / "break"(中断)
        self._execution_state: str | None = None

    # -- Mat（当前图像/数据） --

    @property
    def mat(self) -> np.ndarray | None:
        """获取当前图像数据"""
        return self._mat

    @mat.setter
    def mat(self, value: np.ndarray | None):
        """设置当前图像数据"""
        self._mat = value

    def get_input_mat(self, fallback: np.ndarray | None = None) -> np.ndarray | None:
        """获取用于 invoke_core 处理的有效输入图像。

        如果 _prepared_input 已设置（例如由 image_source_mode 或 ROI 逻辑设置），
        则返回 _prepared_input，否则返回 fallback（通常来自 from_node.mat）。
        这避免了修改 UI 线程可见的上游节点的 _mat。
        """
        return self._prepared_input if self._prepared_input is not None else fallback

    # -- 结果图像 --

    @property
    def result_images(self) -> list[VisionResultImage]:
        """获取结果图像列表"""
        return list(self._get_result_images())

    def _get_result_images(self):
        """生成结果图像。子类可重写以提供自定义结果。"""
        if self._mat is not None:
            yield VisionResultImage(name=f"{self.name} - 图像", image=self._mat)

    # -- 结果展示器 --

    @property
    def result_presenter(self) -> Any:
        """获取结果展示器"""
        return self._result_presenter

    @result_presenter.setter
    def result_presenter(self, value: Any):
        """设置结果展示器"""
        self._result_presenter = value

    # -- 主要的 invoke 方法 --

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        """工作流引擎调用的入口点。

        1. 查找源节点（ISrcVisionNodeData）
        2. 查找上游节点（IVisionNodeData）
        3. 传递上游的原始图像
        4. 调用 InvokeAction 执行实际处理
        """
        # 查找源节点（数据来源）
        src_data = self._find_source_node(diagram)
        # 查找上游节点
        from_data = self._find_from_node(diagram, previors)

        # 传递上游的原始图像，使每个节点都能访问未处理的源图像
        if isinstance(from_data, VisionNodeData):
            upstream_original = getattr(from_data, '_original_mat', None)
            if upstream_original is not None:
                self._original_mat = upstream_original
            elif from_data.mat is not None:
                self._original_mat = from_data.mat.copy()

        # 执行核心处理
        return self._invoke_action(lambda: self.invoke_core(src_data, from_data or src_data, diagram))

    def update_invoke_current(self):
        """从第一个上游节点单步执行。"""
        # 检查图表数据是否存在
        if self.diagram_data is None:
            return None
        # 如果工作流正在运行，则不执行
        if hasattr(self.diagram_data, 'state') and self.diagram_data.state.name == "RUNNING":
            return None

        # 查找源节点
        src_data = self._find_source_node(self.diagram_data)
        # 获取上游节点列表
        from_nodes = self.from_node_datas

        # 根据上游节点数量确定 from_data
        if len(from_nodes) == 0:
            from_data = self
        elif len(from_nodes) > 1:
            return None
        else:
            from_data = from_nodes[0]

        # 验证输入有效并执行
        if isinstance(from_data, VisionNodeData) and from_data.mat is not None:
            if not self.is_valid(from_data.mat):
                return None
            result = self._invoke_action(lambda: self.invoke_core(src_data, from_data, self.diagram_data))
            # 更新图表的结果图像源
            if hasattr(self.diagram_data, 'result_image_source'):
                self.diagram_data.result_image_source = self._result_image_source

            return result
        return None

    def _invoke_action(self, action: Callable[[], FlowableResult]) -> FlowableResult:
        """包装实际的 invoke 调用，管理 Mat 生命周期。

        1. 清除之前的结果展示器
        2. 执行动作
        3. 释放旧的 Mat，设置新的 Mat
        4. 更新结果图像源
        5. 必要时创建结果展示器
        """
        # 清除之前的结果展示器
        self._result_presenter = None
        # 发布节点开始执行事件
        event_system.publish(EventType.NODE_STARTED, sender=self)

        # 执行核心处理
        result = action()

        # 如果新 mat 不是旧 mat，则释放旧 mat
        if self._mat is not None and result.value is not self._mat:
            self._mat = None

        # 更新当前图像和消息（error 时不传递数据给下游）
        self._mat = result.value if result.is_ok else None
        self.message = result.message

        # 更新结果图像源
        if self.use_result_image_source:
            self._update_result_image_source()

        # 创建结果展示器（如果尚未创建）
        if self._result_presenter is None:
            self._result_presenter = self.create_result_presenter()

        # 先写入历史记录，再发布事件
        # 通过 workflow.on_history_changed() 注册的回调（如 ResultPanel）
        # 在这里同步触发，并使用 Qt::QueuedConnection 调度到主线程，
        # 以保证 QTableWidget 的线程安全访问
        state = "Success" if result.is_ok else "Error"
        ts = time.strftime("%H:%M:%S")
        if self.diagram_data and hasattr(self.diagram_data, 'on_node_completed'):
            self.diagram_data.on_node_completed(self, state, ts)

        # 记录执行状态（供 _finalize_execution_state / update_from_node 读取）
        if result.is_error:
            self._execution_state = "error"
        elif result.is_break:
            self._execution_state = "break"
        else:
            self._execution_state = "completed"

        # 发布事件
        if result.is_ok:
            event_system.publish(EventType.NODE_COMPLETED, sender=self, result=result)
        elif result.is_error:
            event_system.publish(EventType.NODE_ERROR, sender=self, result=result)

        # 调用后置钩子（子类可重写以在 invoke_core 完成后做额外处理）
        self._on_post_invoke(result)

        return result

    def _on_post_invoke(self, result: FlowableResult):
        """invoke_core 完成后的后置钩子。子类可重写。"""
        pass

    # -- 子类必须实现的抽象方法 --

    def is_valid(self, mat: np.ndarray) -> bool:
        """检查输入图像是否有效。子类可重写。"""
        return mat is not None

    @abstractmethod
    def invoke_core(self, src_image_node_data: "VisionNodeData | None",
                    from_node_data: "VisionNodeData | None",
                    diagram: "WorkflowEngine") -> FlowableResult:
        """核心处理逻辑。子类实现此方法。

        参数：
            src_image_node_data: 源图像节点（数据来源）
            from_node_data: 直接上游节点
            diagram: 工作流引擎上下文

        返回：
            包含处理后的图像和元数据的 FlowableResult
        """
        ...

    def _update_result_image_source(self):
        """更新图像结果图像源"""
        self._result_image_source = self._mat if self._mat is not None else None

    # -- 流程控制辅助函数 --

    def ok(self, mat: np.ndarray | None, message: str = "运行成功",
           result_presenter: Any = None) -> FlowableResult:
        """返回成功结果"""
        self.message = message
        if result_presenter is not None:
            self._result_presenter = result_presenter
        return FlowableResult.ok(mat, message)

    def error(self, mat: np.ndarray | None = None, message: str = "运行错误") -> FlowableResult:
        """返回错误结果"""
        self.message = message
        return FlowableResult.error(mat, message)

    def break_(self, mat: np.ndarray | None = None, message: str = "不满足条件返回") -> FlowableResult:
        """返回中断结果（流程在此分支停止）"""
        self.message = message
        return FlowableResult.break_(mat, message)

    # -- 内部辅助方法 --

    def _find_source_node(self, diagram: "WorkflowEngine") -> "VisionNodeData | None":
        """查找图表中的源节点（数据来源）"""
        if diagram is None:
            return None
        # 获取所有起始节点
        starts = diagram.get_start_nodes()
        for node in starts:
            if isinstance(node, VisionNodeData):
                return node
        return None

    def _find_from_node(self, diagram: "WorkflowEngine",
                        previors: LinkData | None) -> "VisionNodeData | None":
        """从连线数据中查找直接上游节点"""
        if previors is not None and diagram is not None:
            node = diagram.get_node_by_id(previors.from_node_id)
            if isinstance(node, VisionNodeData):
                return node
        # 后备方案：使用第一个 from_node_data
        for n in self.from_node_datas:
            if isinstance(n, VisionNodeData):
                return n
        return None

    # -- 序列化 --

    def to_dict(self) -> dict:
        """序列化节点为字典"""
        data = super().to_dict()
        data["use_invoked_part"] = self.use_invoked_part
        return data

    def dispose(self):
        """释放 Mat 内存和结果图像"""
        super().dispose()
        self._mat = None
        self._result_presenter = None

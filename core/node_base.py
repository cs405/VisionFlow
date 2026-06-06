"""Node base class hierarchy - ported from H.VisionMaster.NodeData/Base/ (25+ C# files).

Defines the complete inheritance chain for all vision processing nodes.

Inheritance (top to bottom):
    NodeBase  (ports, styles, diagram data)
      -> VisionNodeDataBase  (flow delays)
        -> ShowPropertyNodeDataBase  (property presenter)
          -> HelpNodeDataBase  (help URL)
            -> DemoNodeDataBase  (example parameters)
              -> VisionNodeData  (Mat, ResultImages, Invoke lifecycle)
                -> ROINodeData  (DrawROI / FromROI / InputROI)
                -> SelectableResultImageNodeData  (select upstream result)
                  -> OpenCVNodeDataBase  (OpenCV-specific Mat handling)
                -> SrcFilesVisionNodeData  (file-based image sources)
                -> Base64MatchingNodeData  (template matching)
                -> ConditionNodeData  (conditional branching)
                -> WaitAllParallelNodeData  (parallel sync barrier)

Python replaces C# generics <T> with duck typing - image type is numpy.ndarray.
"""

from __future__ import annotations

import importlib
import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable

import numpy as np

from core.data_packet import FlowableResult, FlowableInvokeMode, VisionResultImage
from core.events import EventType, event_system

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


# =============================================================================
# Parameter group names - ported from VisionPropertyGroupNames.cs
# =============================================================================

class PropertyGroupNames:
    RUN_PARAMETERS = "运行参数"
    BASE_PARAMETERS = "基本参数"
    RESULT_PARAMETERS = "结果参数"
    FLOW_PARAMETERS = "流程控制"
    DISPLAY_PARAMETERS = "显示参数"
    OTHER_PARAMETERS = "其他参数"


# =============================================================================
# Property descriptor - replaces C# [Display], [DefaultValue], [ReadOnly] attributes
# =============================================================================

class Property:
    """Observable property descriptor with metadata.

    Replaces the C# pattern:
        [Display(Name="...", GroupName="...")]
        [DefaultValue(...)]
        public T PropertyName { get => _field; set { _field=value; RaisePropertyChanged(); } }

    Extended metadata for the property panel:
      - editor: str | None  -> hint for custom editor ("color", "roi", "file", "slider", "choices")
      - choices: list | None -> dropdown choices
      - min_val / max_val: range constraints
      - validator: callable | None -> validation function (value) -> (bool, str)
      - step: float -> step for spin boxes
      - decimals: int -> decimal places for float display
    """

    def __init__(self, default: Any = None, *, name: str = "", group: str = "",
                 description: str = "", readonly: bool = False, order: int = 0,
                 editor: str = "", choices: list = None,
                 min_val: Any = None, max_val: Any = None,
                 validator: callable = None,
                 step: float = 0.1, decimals: int = 3):
        self.default = default
        self.display_name = name
        self.group = group
        self.description = description
        self.readonly = readonly
        self.order = order
        # Extended metadata
        self.editor = editor
        self.choices = choices or []
        self.min_val = min_val
        self.max_val = max_val
        self.validator = validator
        self.step = step
        self.decimals = decimals

    def __set_name__(self, owner, name):
        self.attr_name = f"_{name}"
        self.public_name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.attr_name, self.default)

    def __set__(self, obj, value):
        old = getattr(obj, self.attr_name, self.default)
        setattr(obj, self.attr_name, value)
        if old != value:
            obj._notify_property_changed(self.public_name, old, value)


# =============================================================================
# Port types - ported from H.Controls.Diagram (PortData, FlowablePortData)
# =============================================================================

class PortType(Enum):
    INPUT = auto()
    OUTPUT = auto()
    BOTH = auto()


class PortDock(Enum):
    TOP = auto()
    BOTTOM = auto()
    LEFT = auto()
    RIGHT = auto()


class Port:
    """A connection port on a node.

    Ported from C# FlowablePortData / OpenCVFlowablePortData.
    Nodes have 4 ports: Top(input), Bottom(output), Left(input), Right(output).
    """

    def __init__(self, node_id: str, port_type: PortType, dock: PortDock,
                 port_id: str = None, name: str = ""):
        self.port_id = port_id or str(uuid.uuid4())[:8]
        self.node_id = node_id
        self.port_type = port_type
        self.dock = dock
        self.name = name
        self.width = 6
        self.height = 6
        self.fill_color = "#FFFFFF"
        self.link_color = "#FF8C00"  # Orange - matches OpenCVFlowablePortData
        self.connected_links: list["LinkData"] = []

    @property
    def is_input(self) -> bool:
        return self.port_type in (PortType.INPUT, PortType.BOTH)

    @property
    def is_output(self) -> bool:
        return self.port_type in (PortType.OUTPUT, PortType.BOTH)

    def to_dict(self) -> dict:
        return {
            "port_id": self.port_id,
            "node_id": self.node_id,
            "port_type": self.port_type.name,
            "dock": self.dock.name,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Port":
        return cls(
            node_id=data["node_id"],
            port_type=PortType[data["port_type"]],
            dock=PortDock[data["dock"]],
            port_id=data.get("port_id"),
            name=data.get("name", ""),
        )

    def invoke(self, previors: "LinkData | None" = None,
               diagram: "WorkflowEngine | None" = None) -> "FlowableResult":
        """Execute port-level logic (WPF FlowablePortData.TryInvokeAsync).

        Default: publishes PORT_STARTED → returns OK → publishes PORT_COMPLETED.
        Override in subclasses for custom port processing (validation, transform).
        """
        from core.data_packet import FlowableResult
        from core.events import EventType, event_system
        event_system.publish(EventType.PORT_STARTED, sender=self, diagram=diagram)
        result = FlowableResult.ok(message="port ok")
        event_system.publish(EventType.PORT_COMPLETED, sender=self, result=result,
                             diagram=diagram)
        return result


class LinkData:
    """A connection between two ports.

    Ported from C# FlowableLinkData.
    """

    def __init__(self, from_node_id: str = "", from_port_id: str = "",
                 to_node_id: str = "", to_port_id: str = "",
                 text: str = ""):
        self.link_id = str(uuid.uuid4())[:8]
        self.from_node_id = from_node_id
        self.from_port_id = from_port_id
        self.to_node_id = to_node_id
        self.to_port_id = to_port_id
        self.text = text
        self.stroke_color = "#FF8C00"  # Orange

    def to_dict(self) -> dict:
        return {
            "link_id": self.link_id,
            "from_node_id": self.from_node_id,
            "from_port_id": self.from_port_id,
            "to_node_id": self.to_node_id,
            "to_port_id": self.to_port_id,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LinkData":
        link = cls(
            from_node_id=data.get("from_node_id", ""),
            from_port_id=data.get("from_port_id", ""),
            to_node_id=data.get("to_node_id", ""),
            to_port_id=data.get("to_port_id", ""),
            text=data.get("text", ""),
        )
        link.link_id = data.get("link_id", link.link_id)
        return link

    def invoke(self, diagram: "WorkflowEngine | None" = None) -> "FlowableResult":
        """Execute link-level logic (WPF FlowableLinkData.TryInvokeAsync).

        Default: publishes LINK_STARTED → returns OK → publishes LINK_COMPLETED.
        Override in subclasses for custom link processing (filter, transform).
        """
        from core.events import EventType, event_system
        event_system.publish(EventType.LINK_STARTED, sender=self)
        result = FlowableResult.ok(message="link ok")
        event_system.publish(EventType.LINK_COMPLETED, sender=self, result=result)
        return result


# =============================================================================
# Node base classes
# =============================================================================

class NodeBase(ABC):
    """Root base class for all diagram nodes.

    Ported from: StyleNodeDataBase -> ResultImageSourceNodeDataBase -> ...
    The C# inheritance chain is flattened here for Python.

    Provides: ports, styling, diagram data management, serialization.
    """

    def __init__(self):
        self._id = str(uuid.uuid4())[:8]
        self._name = self.__class__.__name__
        self._text = ""
        self._title = ""

        # Property change callbacks
        self._property_callbacks: dict[str, list[Callable]] = {}

        # Styling (from StyleNodeDataBase)
        self.width: float = 120.0
        self.height: float = 35.0
        self.corner_radius: float = 2.0
        self.fill_color: str = "#FFFFFF"
        self.flag_length: float = 10.0

        # Ports
        self.ports: list[Port] = []
        self._init_ports()

        # Diagram data
        self._diagram_data: WorkflowEngine | None = None
        self.from_node_datas: list[NodeBase] = []
        self.to_node_datas: list[NodeBase] = []

        # Result image (from IResultImageSourceNodeData)
        self.use_result_image_source: bool = True
        self._result_image_source: Any = None   # QImage/QPixmap for GUI, numpy array internally

        # Flowable
        self.message: str = ""

        # Execution mode
        self.invoke_mode: FlowableInvokeMode = FlowableInvokeMode.SEQUENTIAL

        # Order for toolbox sorting
        self.order: int = 0

        self.load_default()

    # -- Property change notification --

    def _notify_property_changed(self, name: str, old_value: Any, new_value: Any):
        """Called by Property descriptor when a value changes."""
        for cb in self._property_callbacks.get(name, []):
            cb(name, old_value, new_value)
        event_system.publish(EventType.NODE_PROPERTY_CHANGED,
                            sender=self, name=name, old=old_value, new=new_value)

    def on_property_changed(self, name: str, callback: Callable):
        """Register a callback for property changes."""
        self._property_callbacks.setdefault(name, []).append(callback)

    # -- Identification --

    @property
    def node_id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def title(self) -> str:
        return self._title or self._name

    @title.setter
    def title(self, value: str):
        self._title = value
        self._text = value

    @property
    def text(self) -> str:
        return self._text or self._name

    @text.setter
    def text(self, value: str):
        self._text = value

    @property
    def display_name(self) -> str:
        """Name shown in the toolbox and UI."""
        return self._name

    # -- Diagram data binding --

    @property
    def diagram_data(self) -> WorkflowEngine | None:
        return self._diagram_data

    @diagram_data.setter
    def diagram_data(self, value: WorkflowEngine | None):
        self._diagram_data = value

    def get_all_from_node_datas(self) -> list["NodeBase"]:
        """Get all upstream nodes recursively (traverse the graph backwards)."""
        visited: set[str] = set()
        result: list[NodeBase] = []

        def traverse(node: NodeBase):
            if node.node_id in visited:
                return
            visited.add(node.node_id)
            for from_node in node.from_node_datas:
                result.append(from_node)
                traverse(from_node)

        traverse(self)
        return result

    def get_all_from_this_node_datas(self) -> list["NodeBase"]:
        """Get self + all upstream nodes."""
        return [self] + self.get_all_from_node_datas()

    def get_start_node_datas(self) -> list["NodeBase"]:
        """Find root nodes (nodes with no inputs from other nodes)."""
        all_nodes = self.get_all_from_this_node_datas()
        return [n for n in all_nodes if len(n.from_node_datas) == 0]

    def get_from_node_data(self, node_type: type) -> "NodeBase | None":
        """Find the nearest upstream node of a specific type."""
        for from_node in self.from_node_datas:
            if isinstance(from_node, node_type):
                return from_node
            result = from_node.get_from_node_data(node_type)
            if result is not None:
                return result
        return None

    # -- Ports --

    def _init_ports(self):
        """Initialize the 4 default ports (Top/Bottom/Left/Right)."""
        self.ports = []
        # Top - Input
        p = self.create_port_data()
        p.dock = PortDock.TOP
        p.port_type = PortType.INPUT
        self.ports.append(p)
        # Bottom - Output
        p = self.create_port_data()
        p.dock = PortDock.BOTTOM
        p.port_type = PortType.OUTPUT
        self.ports.append(p)
        # Left - Input
        p = self.create_port_data()
        p.dock = PortDock.LEFT
        p.port_type = PortType.INPUT
        self.ports.append(p)
        # Right - Output
        p = self.create_port_data()
        p.dock = PortDock.RIGHT
        p.port_type = PortType.OUTPUT
        self.ports.append(p)

    def create_port_data(self) -> Port:
        """Create a single port. Override for custom port styling."""
        return Port(node_id=self.node_id, port_type=PortType.BOTH,
                   dock=PortDock.TOP)

    def get_input_ports(self) -> list[Port]:
        return [p for p in self.ports if p.is_input]

    def get_output_ports(self) -> list[Port]:
        return [p for p in self.ports if p.is_output]

    # -- Result image --

    @property
    def result_image_source(self) -> Any:
        return self._result_image_source

    @result_image_source.setter
    def result_image_source(self, value: Any):
        self._result_image_source = value

    # -- Lifecycle --

    def load_default(self):
        """Set default values. Override in subclasses."""
        pass

    @classmethod
    def get_property_descriptors(cls) -> list[tuple[str, Property]]:
        """Get Property descriptors declared on the class hierarchy."""
        result: list[tuple[str, Property]] = []
        seen: set[str] = set()
        for owner in cls.__mro__:
            if owner is object:
                break
            for name, desc in owner.__dict__.items():
                if isinstance(desc, Property) and name not in seen:
                    result.append((name, desc))
                    seen.add(name)
        return result

    def _serialize_property_value(self, value: Any) -> Any:
        # Normalize numpy/array-like types to native Python — ensures JSON-safe output
        import numpy as np
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, Enum):
            return {
                "__enum__": f"{value.__class__.__module__}.{value.__class__.__name__}",
                "name": value.name,
            }
        if isinstance(value, tuple):
            return {"__tuple__": [self._serialize_property_value(v) for v in value]}
        if isinstance(value, list):
            return [self._serialize_property_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._serialize_property_value(v) for k, v in value.items()}
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if hasattr(value, "to_dict") and callable(value.to_dict):
            return {
                "__type__": value.__class__.__name__,
                "data": value.to_dict(),
            }
        return str(value)

    def _deserialize_property_value(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._deserialize_property_value(v) for v in value]
        if not isinstance(value, dict):
            # Convert numeric strings back to numbers (numpy serialization fallback)
            if isinstance(value, str):
                try:
                    if '.' in value or 'e' in value.lower():
                        return float(value)
                    return int(value)
                except (ValueError, OverflowError):
                    pass
            return value

        if "__tuple__" in value:
            return tuple(self._deserialize_property_value(v) for v in value.get("__tuple__", []))

        if "__enum__" in value:
            enum_path = value.get("__enum__", "")
            enum_name = value.get("name", "")
            try:
                module_name, class_name = enum_path.rsplit(".", 1)
                enum_type = getattr(importlib.import_module(module_name), class_name)
                return enum_type[enum_name]
            except Exception:
                return value

        if "__type__" in value:
            type_name = value.get("__type__", "")
            data = value.get("data", {})
            if type_name in {"ROIBase", "FromROI", "DrawROI", "InputROI", "NoROI"}:
                return ROIBase.from_dict(data)

        return {k: self._deserialize_property_value(v) for k, v in value.items()}

    def _serialize_properties(self) -> dict[str, Any]:
        """Serialize ALL Property values — readable and writable alike.

        Every Property visible in the control panel is saved so reloading
        the project restores the exact panel state without per-node code.
        """
        properties: dict[str, Any] = {}
        for name, desc in self.get_property_descriptors():
            properties[name] = self._serialize_property_value(getattr(self, name, desc.default))
        return properties

    def restore_from_dict(self, data: dict) -> "NodeBase":
        """Restore node state from serialized project data."""
        self._id = data.get("id", self._id)
        self.name = data.get("name", self.name)
        self._title = data.get("title", "")
        self._text = data.get("text", "")
        self.width = data.get("width", 120.0)
        self.height = data.get("height", 35.0)
        self._pos_x = data.get("pos_x", 0.0)
        self._pos_y = data.get("pos_y", 0.0)

        invoke_mode_name = data.get("invoke_mode", "SEQUENTIAL")
        try:
            self.invoke_mode = FlowableInvokeMode[invoke_mode_name]
        except KeyError:
            self.invoke_mode = FlowableInvokeMode.SEQUENTIAL

        ports_data = data.get("ports", [])
        if ports_data:
            self.ports = [Port.from_dict(port_data) for port_data in ports_data]
        else:
            for port in self.ports:
                port.node_id = self._id

        serialized_properties = data.get("properties", {})
        property_map = dict(self.get_property_descriptors())
        for name, raw_value in serialized_properties.items():
            if name not in property_map:
                continue
            try:
                setattr(self, name, self._deserialize_property_value(raw_value))
            except Exception:
                continue

        return self

    def to_dict(self) -> dict:
        """Serialize node to dict for JSON project saving."""
        return {
            "id": self.node_id,
            "type": self.__class__.__name__,
            "name": self.name,
            "title": self._title,
            "text": self._text,
            "width": self.width,
            "height": self.height,
            "ports": [p.to_dict() for p in self.ports],
            "invoke_mode": self.invoke_mode.name,
            "properties": self._serialize_properties(),
            "pos_x": getattr(self, '_pos_x', 0.0),
            "pos_y": getattr(self, '_pos_y', 0.0),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NodeBase":
        """Deserialize node from dict."""
        node = cls.__new__(cls)
        NodeBase.__init__(node)
        node._id = data.get("id", node._id)
        node.name = data.get("name", node.name)
        node._title = data.get("title", "")
        node._text = data.get("text", "")
        node.width = data.get("width", 120.0)
        node.height = data.get("height", 35.0)
        node.invoke_mode = FlowableInvokeMode[data.get("invoke_mode", "SEQUENTIAL")]
        node._pos_x = data.get("pos_x", 0.0)
        node._pos_y = data.get("pos_y", 0.0)
        return node

    def dispose(self):
        """Release resources."""
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.node_id}, name={self.name})"


# =============================================================================
# VisionNodeDataBase - flow delay parameters
# =============================================================================

class VisionNodeDataBase(NodeBase):
    """Adds flow-control delay parameters.

    Ported from C# VisionNodeDataBase.cs
    """

    preview_milliseconds_delay = Property(1500, name="预览延迟", group=PropertyGroupNames.FLOW_PARAMETERS,
                                         description="设置生成图像后预览等待时间")
    invoke_milliseconds_delay = Property(500, name="执行延迟", group=PropertyGroupNames.FLOW_PARAMETERS,
                                         description="执行完成后等待时间")


# =============================================================================
# ShowPropertyNodeDataBase - property presenter
# =============================================================================

class ShowPropertyNodeDataBase(VisionNodeDataBase):
    """Provides a property presenter for the property panel.

    Ported from C# ShowPropertyNodeDataBase.cs
    """

    def get_property_presenter(self) -> Any:
        """Return the object shown in the property panel. Default: self."""
        return self


# =============================================================================
# HelpNodeDataBase - help/documentation URL
# =============================================================================

class HelpNodeDataBase(ShowPropertyNodeDataBase):
    """Provides help presenter with documentation URL.

    Ported from C# HelpNodeDataBase.cs + IHelpPresenter.
    """

    def create_help_presenter(self) -> dict:
        """Return help info for the help panel. Override in subclasses to customize."""
        import inspect
        cls = type(self)
        doc = (cls.__doc__ or "").strip().split("\n")[0] if cls.__doc__ else ""
        return {
            "url": f"https://github.com/HeBianGu/WPF-VisionMaster/wiki/{cls.__name__}",
            "name": self.name,
            "description": doc or f"{self.name} - {cls.__name__}",
            "source": inspect.getfile(cls),
        }


# =============================================================================
# DemoNodeDataBase - example/demo parameters
# =============================================================================

class DemoNodeDataBase(HelpNodeDataBase):
    """Adds demo/example parameters to show the parameter system pattern.

    Ported from C# DemoNodeDataBase.cs
    """

    demo_base_parameter1 = Property("", name="示例：基本参数", group=PropertyGroupNames.BASE_PARAMETERS,
                                    description="用来演示如何增加基本参数", order=9999)
    demo_run_parameter1 = Property("", name="示例：运行参数", group=PropertyGroupNames.RUN_PARAMETERS,
                                   description="用来演示如何增加结果参数", order=9999)
    demo_result1 = Property("", name="示例：结果参数", group=PropertyGroupNames.RESULT_PARAMETERS,
                            description="用来演示如何增加结果参数", readonly=True, order=9999)

    def create_result_presenter(self) -> Any:
        """Create a result presenter for the result panel. Override in subclasses."""
        return None


# =============================================================================
# VisionNodeData - THE core vision processing node
# =============================================================================

class VisionNodeData(DemoNodeDataBase):
    """Core generic vision processing node.

    Ported from C# VisionNodeData<T> where T : IDisposable.
    In Python, T is numpy.ndarray (image data).

    This is the central class - most vision nodes extend this.
    Key responsibilities:
      - Hold the Mat (current image numpy array)
      - Provide ResultImages list
      - Implement the Invoke lifecycle (find source/from, execute, return result)
      - Flow control helpers: OK(), Error(), Break()
      - Image disposal management
    """

    # UseInvokedPart - controls whether output goes to history/preview
    use_invoked_part = Property(True, name="启用输出历史记录", group=PropertyGroupNames.DISPLAY_PARAMETERS,
                                description="用于控制是否输出到历史记录和预览图像")

    def __init__(self):
        super().__init__()
        self._mat: np.ndarray | None = None
        self._original_mat: np.ndarray | None = None
        self._prepared_input: np.ndarray | None = None
        self._result_presenter: Any = None

    # -- Mat (the current image/data) --

    @property
    def mat(self) -> np.ndarray | None:
        return self._mat

    @mat.setter
    def mat(self, value: np.ndarray | None):
        self._mat = value

    def get_input_mat(self, fallback: np.ndarray | None = None) -> np.ndarray | None:
        """Get the effective input image for invoke_core processing.

        Returns _prepared_input if set (e.g. by image_source_mode or ROI logic),
        otherwise returns the fallback (typically from_node.mat).
        This avoids modifying upstream nodes' _mat which is visible to the UI thread.
        """
        return self._prepared_input if self._prepared_input is not None else fallback

    # -- Result images --

    @property
    def result_images(self) -> list[VisionResultImage]:
        return list(self._get_result_images())

    def _get_result_images(self):
        """Yield result images. Override to provide custom results."""
        if self._mat is not None:
            yield VisionResultImage(name=f"{self.name} - 图像", image=self._mat)

    # -- Result presenter --

    @property
    def result_presenter(self) -> Any:
        return self._result_presenter

    @result_presenter.setter
    def result_presenter(self, value: Any):
        self._result_presenter = value

    # -- Main invoke method --

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        """Entry point called by the workflow engine.

        Ported from C# VisionNodeData<T>.Invoke(IFlowableLinkData, IFlowableDiagramData).
        1. Find the source node (ISrcVisionNodeData)
        2. Find the from node (IVisionNodeData)
        3. Pass through original image from upstream
        4. Call InvokeAction with the actual processing
        """
        src_data = self._find_source_node(diagram)
        from_data = self._find_from_node(diagram, previors)

        # Pass through original image from upstream so every node
        # has access to the unprocessed source image
        if isinstance(from_data, VisionNodeData):
            upstream_original = getattr(from_data, '_original_mat', None)
            if upstream_original is not None:
                self._original_mat = upstream_original
            elif from_data.mat is not None:
                self._original_mat = from_data.mat.copy()

        return self._invoke_action(lambda: self.invoke_core(src_data, from_data or src_data, diagram))

    def update_invoke_current(self):
        """Single-step execution from the first from-node.

        Ported from C# VisionNodeData<T>.UpdateInvokeCurrent().
        """
        if self.diagram_data is None:
            return
        if hasattr(self.diagram_data, 'state') and self.diagram_data.state.name == "RUNNING":
            return

        src_data = self._find_source_node(self.diagram_data)
        from_nodes = self.from_node_datas

        if len(from_nodes) == 0:
            from_data = self
        elif len(from_nodes) > 1:
            return  # Can't auto-pick with multiple inputs
        else:
            from_data = from_nodes[0]

        if isinstance(from_data, VisionNodeData) and from_data.mat is not None:
            if not self.is_valid(from_data.mat):
                return
            result = self._invoke_action(lambda: self.invoke_core(src_data, from_data, self.diagram_data))
            if hasattr(self.diagram_data, 'result_image_source'):
                self.diagram_data.result_image_source = self._result_image_source

    def _invoke_action(self, action: Callable[[], FlowableResult]) -> FlowableResult:
        """Wraps the actual invoke, managing Mat lifecycle.

        Ported from C# VisionNodeData<T>.InvokeAction().
        1. Clear previous result presenter
        2. Execute the action
        3. Dispose old Mat, set new Mat
        4. Update result image source
        5. Create result presenter if needed
        """
        self._result_presenter = None
        event_system.publish(EventType.NODE_STARTED, sender=self)

        result = action()

        if self._mat is not None and result.value is not self._mat:
            self._mat = None  # Old mat will be GC'd

        self._mat = result.value
        self.message = result.message

        if self.use_result_image_source:
            self._update_result_image_source()
            time.sleep(self.preview_milliseconds_delay / 1000.0)

        if self._result_presenter is None:
            self._result_presenter = self.create_result_presenter()

        # WPF OnInvokedPart: write to history FIRST, then publish events.
        # Callbacks registered via workflow.on_history_changed() (e.g. ResultPanel)
        # fire synchronously here and use Qt::QueuedConnection to marshal to the
        # main thread for thread-safe QTableWidget access.
        import time as _time
        state = "Success" if result.is_ok else "Error"
        ts = _time.strftime("%H:%M:%S")
        if self.diagram_data and hasattr(self.diagram_data, 'on_node_completed'):
            self.diagram_data.on_node_completed(self, state, ts)

        if result.is_ok:
            event_system.publish(EventType.NODE_COMPLETED, sender=self, result=result)
        elif result.is_error:
            event_system.publish(EventType.NODE_ERROR, sender=self, result=result)

        return result

    # -- Abstract methods subclasses must implement --

    def is_valid(self, mat: np.ndarray) -> bool:
        """Check if the input mat is valid for processing. Override in subclasses."""
        return mat is not None

    @abstractmethod
    def invoke_core(self, src_image_node_data: "VisionNodeData | None",
                    from_node_data: "VisionNodeData | None",
                    diagram: "WorkflowEngine") -> FlowableResult:
        """Core processing logic. Subclasses implement this.

        Args:
            src_image_node_data: The source image node (data origin).
            from_node_data: The immediate upstream node.
            diagram: The workflow engine context.

        Returns:
            FlowableResult with the processed image and metadata.
        """
        ...

    def _update_result_image_source(self):
        """Update the result image source for GUI display.

        Default implementation stores the current Mat as result_image_source.
        Override only if custom serialization/format is needed.
        """
        self._result_image_source = self._mat if self._mat is not None else None

    # -- Flow control helpers (ported from C#) --

    def ok(self, mat: np.ndarray | None, message: str = "运行成功",
           result_presenter: Any = None) -> FlowableResult:
        """Return a successful result."""
        self.message = message
        if result_presenter is not None:
            self._result_presenter = result_presenter
        return FlowableResult.ok(mat, message)

    def error(self, mat: np.ndarray | None = None, message: str = "运行错误") -> FlowableResult:
        """Return an error result."""
        self.message = message
        return FlowableResult.error(mat, message)

    def break_(self, mat: np.ndarray | None = None, message: str = "不满足条件返回") -> FlowableResult:
        """Return a break result (flow stops at this branch)."""
        self.message = message
        return FlowableResult.break_(mat, message)

    # -- Internal helpers --

    def _find_source_node(self, diagram: "WorkflowEngine") -> "VisionNodeData | None":
        """Find the source (data origin) node in the diagram."""
        if diagram is None:
            return None
        starts = diagram.get_start_nodes()
        for node in starts:
            if isinstance(node, VisionNodeData):
                return node
        return None

    def _find_from_node(self, diagram: "WorkflowEngine",
                        previors: LinkData | None) -> "VisionNodeData | None":
        """Find the immediate upstream node from the link data."""
        if previors is not None and diagram is not None:
            node = diagram.get_node_by_id(previors.from_node_id)
            if isinstance(node, VisionNodeData):
                return node
        # Fallback: use the first from_node_data
        for n in self.from_node_datas:
            if isinstance(n, VisionNodeData):
                return n
        return None

    # -- Serialization --

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["use_invoked_part"] = self.use_invoked_part
        data["preview_milliseconds_delay"] = self.preview_milliseconds_delay
        data["invoke_milliseconds_delay"] = self.invoke_milliseconds_delay
        return data

    def dispose(self):
        """Release Mat memory and result images."""
        super().dispose()
        self._mat = None
        self._result_presenter = None


# =============================================================================
# ROINodeData - ROI support (NoROI / DrawROI / FromROI / InputROI)
# =============================================================================

class ROIBase:
    """Base class for ROI definitions.

    Ported from C# ROIBase.cs / IROI.cs
    """
    def __init__(self, roi_type: str = ""):
        self.name = roi_type or self.__class__.__name__

    def to_dict(self) -> dict:
        return {"type": self.__class__.__name__, "name": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> "ROIBase":
        roi_type = data.get("type", "ROIBase")
        if roi_type == "NoROI":
            return NoROI()
        if roi_type == "DrawROI":
            roi = DrawROI()
            roi.rect = tuple(data.get("rect", roi.rect))
            return roi
        if roi_type == "InputROI":
            roi = InputROI()
            roi.x = int(data.get("x", roi.x))
            roi.y = int(data.get("y", roi.y))
            roi.width = int(data.get("width", roi.width))
            roi.height = int(data.get("height", roi.height))
            return roi
        return FromROI()


class FromROI(ROIBase):
    """ROI obtained from upstream node."""
    def __init__(self, source_node: NodeBase = None):
        super().__init__("使用上游ROI")
        self.source_node = source_node


class DrawROI(ROIBase):
    """ROI drawn interactively on the image."""
    def __init__(self):
        super().__init__("绘制ROI")
        self.image_source: Any = None
        self.rect: tuple = (0, 0, 100, 100)  # x, y, w, h

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["rect"] = list(self.rect or (0, 0, 100, 100))
        return data


class InputROI(ROIBase):
    """ROI entered manually as numeric values."""
    def __init__(self):
        super().__init__("输入ROI")
        self.x: int = 0
        self.y: int = 0
        self.width: int = 100
        self.height: int = 100

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        })
        return data


class NoROI(ROIBase):
    """No ROI — do not apply any region of interest."""

    def __init__(self):
        super().__init__("无")


class ROINodeData(VisionNodeData):
    """Adds ROI support to vision nodes.

    Ported from C# ROINodeData<T>.
    Supports four ROI modes: NoROI (none), FromROI (upstream), DrawROI (interactive), InputROI (manual).
    Default is NoROI to prevent unintended ROI cascading.
    """

    def __init__(self):
        super().__init__()
        self.no_roi = NoROI()
        self.from_roi = FromROI(source_node=self)
        self.draw_roi = DrawROI()
        self.input_roi = InputROI()
        self._roi: ROIBase = self.no_roi

    @property
    def roi(self) -> ROIBase:
        return self._roi

    @roi.setter
    def roi(self, value: ROIBase):
        self._roi = value

    def get_rois(self) -> list[ROIBase]:
        """Get all available ROI options."""
        self.draw_roi.image_source = self._result_image_source
        return [self.no_roi, self.from_roi, self.draw_roi, self.input_roi]

    def get_active_roi_rect(self) -> tuple | None:
        """Get the currently active ROI rectangle as (x, y, w, h)."""
        if isinstance(self._roi, NoROI):
            return None
        if isinstance(self._roi, DrawROI):
            if self._roi.rect:
                return self._roi.rect
        elif isinstance(self._roi, InputROI):
            return (self._roi.x, self._roi.y, self._roi.width, self._roi.height)
        elif isinstance(self._roi, FromROI):
            src = self._roi.source_node
            if isinstance(src, ROINodeData) and src is not self:
                return src.get_active_roi_rect()
        return None

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        from_data = self._find_from_node(diagram, previors)

        # Wire upstream ROI for FromROI mode (WPF: source_node = upstream)
        if isinstance(from_data, ROINodeData) and from_data is not self:
            self.from_roi.source_node = from_data

        # Pass through original image from upstream
        if isinstance(from_data, VisionNodeData):
            upstream_original = getattr(from_data, '_original_mat', None)
            if upstream_original is not None:
                self._original_mat = upstream_original
            elif from_data.mat is not None:
                self._original_mat = from_data.mat.copy()

        # Determine the effective input image based on image_source_mode
        if from_data is not None and from_data.mat is not None:
            if hasattr(self, 'image_source_mode') and self.image_source_mode == "原图":
                input_mat = self._original_mat if self._original_mat is not None else from_data.mat
            else:
                input_mat = from_data.mat
        else:
            input_mat = None

        # Get this node's own ROI rect (None when NoROI or no ROI configured)
        roi_rect = self.get_active_roi_rect() if not isinstance(self._roi, NoROI) else None

        if roi_rect is not None and input_mat is not None:
            x, y, w, h = int(roi_rect[0]), int(roi_rect[1]), int(roi_rect[2]), int(roi_rect[3])
            h_img, w_img = input_mat.shape[:2]
            x, y = max(0, x), max(0, y)
            w, h = min(w, w_img - x), min(h, h_img - y)
            if w <= 0 or h <= 0:
                roi_rect = None  # fall through to no-ROI path

        if roi_rect is not None and input_mat is not None:
            x, y, w, h = int(roi_rect[0]), int(roi_rect[1]), int(roi_rect[2]), int(roi_rect[3])
            h_img, w_img = input_mat.shape[:2]
            x, y = max(0, x), max(0, y)
            w, h = min(w, w_img - x), min(h, h_img - y)

            # Set prepared input to ROI region — does NOT modify from_data._mat
            self._prepared_input = input_mat[y:y+h, x:x+w]
            result = super().invoke(previors, diagram)
            self._prepared_input = None

            # Paste processed result back into full input image
            if self.mat is not None and self.mat.shape[:2] == (h, w):
                try:
                    full_result = input_mat.copy()
                    full_result[y:y+h, x:x+w] = self.mat
                    self._mat = full_result
                    self._update_result_image_source()
                except (ValueError, IndexError):
                    pass  # channel mismatch (e.g. BGR→gray) — keep raw result
        else:
            # No ROI — may still need to use the selected input_mat
            if from_data is not None and input_mat is not from_data.mat:
                self._prepared_input = input_mat
                result = super().invoke(previors, diagram)
                self._prepared_input = None
            else:
                result = super().invoke(previors, diagram)

        self.draw_roi.image_source = self._result_image_source
        return result

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["roi"] = self._roi.to_dict() if self._roi is not None else None
        return data

    def restore_from_dict(self, data: dict) -> "ROINodeData":
        super().restore_from_dict(data)
        roi_data = data.get("roi")
        if roi_data:
            self._roi = ROIBase.from_dict(roi_data)
        if isinstance(self._roi, NoROI):
            self._roi = self.no_roi
        elif isinstance(self._roi, DrawROI):
            self.draw_roi.rect = tuple(self._roi.rect)
            self._roi = self.draw_roi
        elif isinstance(self._roi, InputROI):
            self.input_roi.x = int(self._roi.x)
            self.input_roi.y = int(self._roi.y)
            self.input_roi.width = int(self._roi.width)
            self.input_roi.height = int(self._roi.height)
            self._roi = self.input_roi
        elif isinstance(self._roi, FromROI):
            self._roi = self.from_roi
        else:
            self._roi = self.no_roi
        return self


# =============================================================================
# SelectableResultImageNodeData - select which upstream result image to use
# =============================================================================

class SelectableResultImageNodeData(ROINodeData):
    """Allows selecting which upstream result image to process.

    Ported from C# SelectableResultImageNodeData<T>.
    """

    def __init__(self):
        super().__init__()
        self._selected_result_image: VisionResultImage | None = None

    @property
    def selected_result_image(self) -> VisionResultImage | None:
        return self._selected_result_image

    @selected_result_image.setter
    def selected_result_image(self, value: VisionResultImage | None):
        self._selected_result_image = value

    def get_selectable_src_node_datas(self) -> list[VisionResultImage]:
        """Get all result images from upstream VisionNodeData nodes."""
        results: list[VisionResultImage] = []
        for node in self.get_all_from_node_datas():
            if isinstance(node, VisionNodeData):
                results.extend(node.result_images)
        return results


# =============================================================================
# OpenCVNodeDataBase - OpenCV-specific Mat handling
# =============================================================================

class OpenCVNodeDataBase(SelectableResultImageNodeData):
    """Base for OpenCV-based vision nodes. Mat is numpy.ndarray.

    Ported from C# OpenCVNodeDataBase : SelectableResultImageNodeData<Mat>.
    """

    image_source_mode = Property(
        "处理后图片", name="图像源", group=PropertyGroupNames.BASE_PARAMETERS,
        description="选择输入图像来源：处理后图片(上游节点输出) 或 原图(数据源原始图像)",
        editor="choices", choices=["处理后图片", "原图"], order=1000,
    )

    def is_valid(self, mat: np.ndarray) -> bool:
        return mat is not None and mat.size > 0

    def _update_result_image_source(self):
        """Convert numpy array to displayable format (handled by GUI layer).

        In the GUI, this becomes a QImage/QPixmap. At core level, we store the
        numpy array and let the GUI layer handle conversion.
        """
        self._result_image_source = self._mat

    def to_dict(self) -> dict:
        data = super().to_dict()
        if self._selected_result_image:
            data["selected_result_image"] = self._selected_result_image.name
        return data


# =============================================================================
# SrcFilesVisionNodeData - file-based image source node
# =============================================================================

class SrcFilesVisionNodeData(ROINodeData):
    """Base for nodes that load images from files.

    Ported from C# SrcFilesVisionNodeData<T>.
    Provides file list management, image properties (width/height/color type).
    """

    pixel_width = Property(0, name="图像宽度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    pixel_height = Property(0, name="图像高度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    image_color_type = Property(0, name="颜色类型", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    use_all_image = Property(False, name="使用所有图像", group=PropertyGroupNames.RUN_PARAMETERS)
    use_auto_switch = Property(True, name="自动切换", group=PropertyGroupNames.RUN_PARAMETERS)
    src_file_path = Property("", name="当前文件", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        self.src_file_paths: list[str] = []
        super().__init__()
        self.use_start = True  # This node can be a flow start node

    # WPF-aligned image extensions (Extension.File.cs ImageExtension constant)
    # jpg jpeg png gif pdf tga tif svg bmp dds eps webp
    _IMAGE_EXTENSIONS = (
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
        ".webp", ".svg", ".tga", ".dds", ".eps", ".pdf",
    )

    @classmethod
    def collect_image_files(cls, folder_path: str, recursive: bool = True,
                            image_extensions: tuple = None) -> list[str]:
        """Collect all image files from a folder, optionally recursive.

        WPF port: DirectoryEx.GetAllFiles() + IsImage() + GetAllImages().

        WPF key behaviors:
          1. RECURSIVE into subdirectories (GetAllFiles walks entire tree)
          2. Skips hidden & system files (FileAttributes.Hidden | FileAttributes.System)
          3. Returns absolute file paths
          4. Catches UnauthorizedAccessException for inaccessible subdirs
          5. Can be overridden by subclasses (WPF: protected virtual)

        Args:
            folder_path: root folder to scan
            recursive: whether to scan subdirectories (WPF: always true)
            image_extensions: override extensions tuple (WPF: ImageExtensions list)

        Returns:
            Sorted list of absolute file paths matching image extensions.
        """
        import os
        if image_extensions is None:
            image_extensions = cls._IMAGE_EXTENSIONS

        result: list[str] = []

        def _scan(directory: str):
            try:
                entries = os.listdir(directory)
            except (PermissionError, OSError):
                return  # WPF: UnauthorizedAccessException catch

            for name in sorted(entries):
                full_path = os.path.join(directory, name)
                try:
                    # WPF: skip hidden/system files
                    # On Windows: FILE_ATTRIBUTE_HIDDEN = 2, FILE_ATTRIBUTE_SYSTEM = 4
                    import stat
                    attrs = os.stat(full_path).st_file_attributes if os.name == 'nt' else 0
                    if attrs & (2 | 4):  # hidden | system
                        continue
                except (OSError, AttributeError):
                    pass  # can't stat → proceed anyway

                if os.path.isdir(full_path):
                    if recursive:
                        _scan(full_path)  # WPF: recurse into subdirectories
                elif name.lower().endswith(image_extensions):
                    result.append(full_path)

        _scan(folder_path)
        return result

    def add_files_from_folder(self, folder_path: str, recursive: bool = True,
                              image_extensions: tuple = None):
        """Add all image files from a folder (WPF AddFiles / GetAllImages).

        WPF: AddImageDatasCommand → AddFiles() → IOFolderDialog →
             selectedFolderPath.GetAllImages() → SrcFilePaths.AddRange()

        Key WPF behaviors:
          - Scans subdirectories by default (recursive=True)
          - Skips hidden & system files
          - Only sets SrcFilePath if it was previously empty
        """
        new_files = self.collect_image_files(folder_path, recursive, image_extensions)
        if not new_files:
            return
        self.src_file_paths.extend(new_files)
        # WPF: if (SrcFilePaths.Count == 0) → only set if nothing was selected
        if not self.src_file_path:
            self.src_file_path = self.src_file_paths[0]

    def add_files(self, file_paths: list[str]):
        """Add specific image files."""
        self.src_file_paths.extend(file_paths)
        if self.src_file_paths and not self.src_file_path:
            self.src_file_path = self.src_file_paths[0]

    def clear_files(self):
        """Clear all file paths."""
        self.src_file_paths.clear()
        self.src_file_path = ""

    def delete_current_file(self):
        """Remove the current file from the list."""
        if self.src_file_path and self.src_file_path in self.src_file_paths:
            idx = self.src_file_paths.index(self.src_file_path)
            self.src_file_paths.remove(self.src_file_path)
            if self.src_file_paths:
                new_idx = min(idx, len(self.src_file_paths) - 1)
                self.src_file_path = self.src_file_paths[new_idx]
            else:
                self.src_file_path = ""

    def move_next(self) -> bool:
        """Switch to the next file in the list. Returns True if cycled.

        WPF: ISrcFilesNodeData.MoveNext() extension method.
          → index = SrcFilePaths.IndexOf(SrcFilePath)
          → index = index < Count - 1 ? index + 1 : 0
          → SrcFilePath = SrcFilePaths[index]
        """
        if not self.src_file_paths:
            return False
        if self.src_file_path not in self.src_file_paths:
            self.src_file_path = self.src_file_paths[0]
            return True
        idx = self.src_file_paths.index(self.src_file_path)
        next_idx = (idx + 1) % len(self.src_file_paths)
        if next_idx == 0 and not self.use_all_image:
            return False
        self.src_file_path = self.src_file_paths[next_idx]
        return True

    def move_prev(self) -> bool:
        """Switch to the previous file in the list. Returns True if wrapped.

        Mirrors move_next() but in reverse — for "上一张" single-step navigation.
        """
        if not self.src_file_paths:
            return False
        if self.src_file_path not in self.src_file_paths:
            self.src_file_path = self.src_file_paths[-1]
            return True
        idx = self.src_file_paths.index(self.src_file_path)
        prev_idx = idx - 1
        if prev_idx < 0:
            if not self.use_all_image:
                return False
            prev_idx = len(self.src_file_paths) - 1
        self.src_file_path = self.src_file_paths[prev_idx]
        return True

    def is_valid_file_list(self) -> tuple[bool, str]:
        """Check if the file list is valid. Returns (is_valid, message).

        WPF: SrcFilesVisionNodeData.IsValid(out string message)
        """
        if not self.src_file_paths:
            return False, "请选择数据源中的图片"
        if self.src_file_path is None:
            self.src_file_path = self.src_file_paths[0]
        return self.src_file_path is not None, ""

    # ═══════════════════════════════════════════════════════════════════════
    # TODO: WPF "添加文件/文件夹/删除/清空" commands port
    #
    # WPF 在 SrcFilesVisionNodeData.cs 实现（MVVM Command 模式）：
    #
    #   AddImageDataCommand     → AddFile()  → IocMessage.IOFileDialog.ShowOpenImageFiles()
    #   AddImageDatasCommand    → AddFiles() → IocMessage.IOFolderDialog.ShowOpenFolderAction()
    #                           → selectedFolderPath.GetAllImages()
    #                           → DirectoryEx.GetAllFiles(IsImage)  ← RECURSIVE scan
    #   DeleteImageDataCommand  → await IocMessage.Dialog.ShowDeleteDialog()
    #                           → 记下 index = SrcFilePaths.IndexOf(SrcFilePath)
    #                           → SrcFilePaths.Remove(SrcFilePath)
    #                           → SrcFilePath = find ?? FirstOrDefault()  ← 同索引或第一个
    #   ClearImageDatasCommand  → await IocMessage.Dialog.ShowDeleteAllDialog()
    #                           → SrcFilePaths.Clear()
    #                           → CanExecute: SrcFilePaths?.Count > 0        ← 空列表禁用
    #
    # WPF "删除" (DeleteImageDataCommand) 核心细节：
    #   1. IoC 确认对话框: await IocMessage.Dialog.ShowDeleteDialog(callback)
    #      - 用户确认 → 执行 callback；取消 → 不执行
    #      - 对话框服务可 mock，Node 不依赖具体 UI 框架
    #   2. 相邻选择算法:
    #      int index = SrcFilePaths.IndexOf(SrcFilePath)     // 记住当前位置
    #      SrcFilePaths.Remove(SrcFilePath)                   // 先删除
    #      string find = SrcFilePaths.ElementAtOrDefault(index) // 同位置取新文件
    #      SrcFilePath = find ?? SrcFilePaths.FirstOrDefault()  // 不存在则取第一个
    #   3. 无显式 CanExecute — 删除始终可用（由对话框内部的检查保护）
    #
    # WPF "清空" (ClearImageDatasCommand) 核心细节：
    #   1. IoC 确认对话框: await IocMessage.Dialog.ShowDeleteAllDialog(callback)
    #      - "Delete All" 语义不同于单个删除 — 更强烈的确认提示
    #   2. SrcFilePaths.Clear() — 直接清空，不逐个删除
    #   3. CanExecute: SrcFilePaths != null && SrcFilePaths.Count > 0
    #      - 空列表时按钮自动禁用（WPF 通过绑定自动刷新 IsEnabled）
    #   4. 清空后 SrcFilePath 变为 null — 无选中文件
    #
    # WPF "添加文件夹" 核心实现细节：
    #   1. GetAllImages(this string folderPath) — 扩展方法
    #      → folderPath.ToDirectoryEx().GetAllFiles(x => x.FullName.IsImage())
    #   2. DirectoryEx.GetAllFiles(Predicate<FileInfo> match) — 递归扫描器
    #      a. 遍历 dir.GetFileSystemInfos()
    #      b. 排除隐藏/系统文件 (Hidden | System)
    #      c. 目录 → 递归 GetAllFiles(match)
    #      d. 文件 → match(file) → 添加到结果列表
    #   3. IsImage(this string filePath) — 扩展名判断
    #      ImageExtensions: jpg jpeg png gif pdf tga tif svg bmp dds eps webp
    #   4. 错误处理: catch UnauthorizedAccessException → 跳过无权限目录
    #   5. 调用链: Node → IocMessage → IIOFolderDialogService.ShowOpenFolderAction()
    #      Callback 模式: 对话框打开 → 选中文件夹 → callback(folderPath)
    #   6. protected virtual AddFiles() — 子类可重写（如 Video 源调用 GetAllVedios）
    #
    # WPF 通用关键设计点：
    #   1. IoC 对话框服务 — 解耦 UI 框架，可 mock/替换
    #   2. 确认对话框 — 删除/清空前弹框确认（防御性设计）
    #   3. CanExecute 守卫 — Clear 需要 list.Count > 0 才可用
    #   4. protected virtual AddFile/AddFiles — 子类可重写扩展（如视频源）
    #   5. 首次添加文件 → 自动选中第一个（SrcFilePath = FirstOrDefault()）
    #   6. 删除后 → 选中同索引位置的文件，若超出则选第一个
    #   7. 数据绑定自动刷新 UI — 添加后缩略图自动增量出现
    #
    # VisionFlow 适配策略：
    #   - 对话框由 FlowResourcePanel 通过 QFileDialog 调用（PyQt5 信号/槽风格）
    #   - 确认对话框用 QMessageBox.question（对标 WPF ShowDeleteDialog / ShowDeleteAllDialog）
    #   - 删除时增量移除缩略图按钮（_thumbnails.pop + removeWidget），避免全量 rebuild
    #   - 按钮状态管理 (_update_action_buttons) 对标 CanExecute：
    #       del_btn.enabled  = has_files AND has_selection
    #       clear_btn.enabled = has_files
    #   - Node.delete_current_file() 保持纯数据操作（对标 WPF Remove + IndexOf + ElementAtOrDefault）
    #   - Node.clear_files() 保持纯数据操作（对标 WPF SrcFilePaths.Clear()）
    #   - UI 交互逻辑（确认弹框、信号发射）全部在 Panel（遵循 PyQt5 惯例）
    # ═══════════════════════════════════════════════════════════════════════

    def load_default(self):
        super().load_default()
        import os
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "images")
        if os.path.isdir(assets_dir):
            self.add_files_from_folder(assets_dir)
        self.src_file_path = ""

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["src_file_paths"] = list(self.src_file_paths)
        data["src_file_path"] = self.src_file_path
        data["use_all_image"] = self.use_all_image
        data["use_auto_switch"] = self.use_auto_switch
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "SrcFilesVisionNodeData":
        node = super().from_dict(data)
        node.src_file_paths = data.get("src_file_paths", [])
        node.src_file_path = data.get("src_file_path", "")
        return node


# =============================================================================
# Base64MatchingNodeData - template matching base
# =============================================================================

class Base64MatchingNodeData(VisionNodeData):
    """Base for template matching nodes that use Base64-encoded template images.

    Ported from C# Base64MatchingNodeData<T>.
    """

    matching_count_result = Property(0, name="匹配数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    confidence = Property(0.0, name="置信度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self._base64_string: str = ""

    @property
    def base64_string(self) -> str:
        return self._base64_string

    @base64_string.setter
    def base64_string(self, value: str):
        self._base64_string = value

    def set_template_from_image(self, image: np.ndarray):
        """Encode a numpy image to Base64 string for template storage."""
        import base64
        import cv2
        _, buffer = cv2.imencode(".png", image)
        self._base64_string = base64.b64encode(buffer).decode("utf-8")

    def get_template_image(self) -> np.ndarray | None:
        """Decode the Base64 template to a numpy image."""
        if not self._base64_string:
            return None
        import base64
        import cv2
        buffer = base64.b64decode(self._base64_string)
        arr = np.frombuffer(buffer, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["base64_string"] = self._base64_string
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Base64MatchingNodeData":
        node = super().from_dict(data)
        node._base64_string = data.get("base64_string", "")
        return node


# =============================================================================
# ConditionNodeData - conditional branching
# =============================================================================

class ConditionNodeData(VisionNodeData):
    """Node that branches flow based on conditions evaluated on upstream results.

    Ported from C# ConditionNodeData<T>.
    When executed, evaluates conditions and directs flow to the matching output port.
    """

    def __init__(self):
        super().__init__()
        self.use_invoked_part = False
        self._conditions: list["VisionPropertyCondition"] = []
        self._conditions_presenter: Any = None

    @property
    def conditions(self) -> list["VisionPropertyCondition"]:
        return self._conditions

    @conditions.setter
    def conditions(self, value: list["VisionPropertyCondition"]):
        self._conditions = value

    def add_condition(self, condition: "VisionPropertyCondition"):
        """Add a condition rule."""
        self._conditions.append(condition)

    def remove_condition(self, index: int):
        """Remove a condition by index."""
        if 0 <= index < len(self._conditions):
            self._conditions.pop(index)

    def evaluate_conditions(self, upstream_results: dict[str, Any]) -> list["VisionPropertyCondition"]:
        """Evaluate all conditions against upstream results.
        Returns list of matching conditions.
        """
        matches = []
        for cond in self._conditions:
            if cond.evaluate(upstream_results):
                matches.append(cond)
        return matches

    def get_condition_candidates(self) -> list[tuple[str, Any]]:
        """Collect editable/evaluable upstream result entries for the condition editor."""
        candidates: list[tuple[str, Any]] = []
        seen: set[str] = set()

        for node in self.from_node_datas:
            if not isinstance(node, VisionNodeData):
                continue

            node_name = node.name or type(node).__name__
            for prop_name, prop_desc in node.get_property_descriptors():
                is_candidate = (
                    prop_name.endswith("_result")
                    or prop_desc.group == PropertyGroupNames.RESULT_PARAMETERS
                )
                if not is_candidate:
                    continue

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
        """Snapshot current upstream result values for condition evaluation/testing."""
        return dict(self.get_condition_candidates())

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        """Execute conditional branching logic."""
        upstream_results = self.collect_upstream_results()

        # Evaluate conditions
        matches = self.evaluate_conditions(upstream_results)

        if matches:
            # Route flow to the matched output nodes
            result = self.ok(self.mat, f"匹配条件: {len(matches)} 个")
            return result
        else:
            return self.break_(self.mat, "没有匹配的条件")

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        return self.ok(from_node_data.mat if from_node_data else None)

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["conditions"] = [c.to_dict() for c in self._conditions]
        return data

    def restore_from_dict(self, data: dict) -> "ConditionNodeData":
        super().restore_from_dict(data)
        self._conditions = [VisionPropertyCondition.from_dict(c) for c in data.get("conditions", [])]
        return self


class VisionPropertyCondition:
    """A single condition rule: property_name operator threshold_value -> output_node.

    Ported from C# VisionPropertyConditionPrensenter.
    """

    SUPPORTED_OPERATORS = (">", "<", ">=", "<=", "==", "!=", "contains", "not contains")

    def __init__(self, property_name: str = "", operator: str = ">",
                 threshold: Any = 0.0, output_node_id: str = ""):
        self.property_name = property_name
        self.operator = operator
        self.threshold = threshold
        self.output_node_id = output_node_id

    def _coerce_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        return text in {"1", "true", "yes", "y", "on", "是"}

    def _coerce_number(self, value: Any) -> float:
        return float(str(value).strip())

    def display_text(self) -> str:
        target = f" → {self.output_node_id}" if self.output_node_id else ""
        return f"{self.property_name} {self.operator} {self.threshold}{target}"

    def evaluate(self, upstream_results: dict[str, Any]) -> bool:
        """Check if this condition matches the upstream results."""
        value = upstream_results.get(self.property_name, None)
        if value is None:
            return False

        numeric_ops = {
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
        }
        text_ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            "contains": lambda a, b: str(b) in str(a),
            "not contains": lambda a, b: str(b) not in str(a),
        }

        if self.operator in numeric_ops:
            try:
                return numeric_ops[self.operator](self._coerce_number(value), self._coerce_number(self.threshold))
            except (ValueError, TypeError):
                return False

        if self.operator in {"==", "!="}:
            if isinstance(value, bool):
                compare_value = self._coerce_bool(self.threshold)
            else:
                try:
                    compare_value = self._coerce_number(self.threshold)
                    value = self._coerce_number(value)
                except (ValueError, TypeError):
                    compare_value = str(self.threshold)
                    value = str(value)
            return text_ops[self.operator](value, compare_value)

        op_func = text_ops.get(self.operator)
        if op_func is None:
            return False
        return op_func(value, self.threshold)

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
# WaitAllParallelNodeData - parallel execution sync barrier
# =============================================================================

class WaitAllParallelNodeData(VisionNodeData):
    """Waits for all parallel upstream nodes to complete before proceeding.

    Ported from C# WaitAllParallelNodeData<T>.
    Acts as a synchronization barrier: counts invocations from parallel branches
    and only proceeds when all parallel predecessors have completed.
    """
    __group__ = "逻辑模块"

    def __init__(self):
        super().__init__()
        self.name = "并行等待"
        self._result_count = 0

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        """Count parallel invocations. Only proceed when all done."""
        from_node = None
        for n in self.from_node_datas:
            if isinstance(n, VisionNodeData):
                from_node = n
                break

        src_data = self._find_source_node(diagram)

        # Call the per-parallel handler
        self.on_parallel_from_invoked(src_data, from_node, diagram)
        self._result_count += 1

        # Count parallel from-nodes
        parallel_count = sum(1 for n in self.from_node_datas
                           if hasattr(n, 'invoke_mode') and n.invoke_mode == FlowableInvokeMode.PARALLEL)

        if self._result_count >= parallel_count:
            self._result_count = 0
            return self._invoke_action(lambda: self.on_all_parallels_invoked(src_data, from_node, diagram))
        else:
            return self.break_(from_node.mat if from_node else None, "等待其他并行分支完成")

    def on_parallel_from_invoked(self, src_image_node_data, from_node, diagram):
        """Called for each parallel branch completion. Override to accumulate results."""
        pass

    def on_all_parallels_invoked(self, src_image_node_data, from_node, diagram) -> FlowableResult:
        """Called when ALL parallel branches have completed. Override to merge results."""
        return self.ok(from_node.mat if from_node else None)

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        return self.ok(from_node_data.mat if from_node_data else None)

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["result_count"] = self._result_count
        return data

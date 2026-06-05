"""Tests for WPF-aligned edge architecture — 1:1 port of WPF Link/LinkDrawer/Layout.

Tests cover:
  - Default BrokenLinkDrawer (orthogonal routing, not straight lines)
  - WPF exact color scheme (Foreground #606266, Accent #3399FF, Green #67C23A, Red #dc000c)
  - WPF dash patterns (Dynamic 5-2, Running 4-4, Normal solid)
  - State propagation from workflow to edge colors
  - Drawer switching (Bezier, Line, Broken)
  - Edge commit, validation, disconnect, duplicate prevention
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtWidgets import QApplication

from core.node_base import NodeBase, PortDock
from core.workflow import WorkflowEngine
from gui.node_editor.scene import DiagramScene, LayerZ
from gui.node_editor.edge_item import (
    EdgeState, EDGE_COLOR, EDGE_COLOR_SELECTED,
    EDGE_COLOR_RUNNING, EDGE_COLOR_SUCCESS, EDGE_COLOR_ERROR,
    DASH_RUNNING, DASH_DYNAMIC,
)
from gui.node_editor.link_drawer import BrokenLinkDrawer, BezierLinkDrawer, LineLinkDrawer


def _app():
    return QApplication.instance() or QApplication([])


def _pump(app, n=3):
    for _ in range(n):
        app.processEvents()


def _make_scene_with_two_nodes():
    _app()
    scene = DiagramScene()
    workflow = WorkflowEngine()
    scene.bind_workflow(workflow)
    left_node = NodeBase()
    right_node = NodeBase()
    left_item = scene.add_node_item(left_node, QPointF(0, 0))
    right_item = scene.add_node_item(right_node, QPointF(220, 120))
    return scene, workflow, left_item, right_item


def _socket(item, dock: PortDock):
    return next(socket for socket in item.sockets if socket.port.dock == dock)


# ═══════════════════════════════════════════════════════════════════════════
# WPF Drawing Strategy Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_default_drawer_is_orthogonal_broken_line():
    """WPF: Diagram.LinkDrawer defaults to BrokenLinkDrawer (折线 not 直线)."""
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    assert isinstance(scene.link_drawer, BrokenLinkDrawer)


def test_created_edge_uses_orthogonal_routing():
    """WPF: BrokenLinkDrawer produces multi-point polyline routing."""
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    target = _socket(right_item, PortDock.LEFT)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, target.get_center_scene_pos())
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    edge = scene.get_all_edge_items()[0]
    assert isinstance(edge._drawer, BrokenLinkDrawer)
    assert edge._path.elementCount() >= 3  # orthogonal has multiple segments


def test_drawer_can_switch_to_bezier():
    """WPF: Diagram.LinkDrawer replaceable — switch to BezierLinkDrawer."""
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    target = _socket(right_item, PortDock.LEFT)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, target.get_center_scene_pos())
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    scene.link_drawer = BezierLinkDrawer()
    edge = scene.get_all_edge_items()[0]
    assert isinstance(edge._drawer, BezierLinkDrawer)


def test_drawer_can_switch_to_line():
    """WPF: Diagram.LinkDrawer replaceable — switch to LineLinkDrawer (直线)."""
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    target = _socket(right_item, PortDock.LEFT)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, target.get_center_scene_pos())
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    scene.link_drawer = LineLinkDrawer()
    edge = scene.get_all_edge_items()[0]
    assert isinstance(edge._drawer, LineLinkDrawer)


# ═══════════════════════════════════════════════════════════════════════════
# WPF Color Scheme Tests (exact BrushKeys values)
# ═══════════════════════════════════════════════════════════════════════════

def test_link_default_color_is_wpf_green():
    """WPF-VisionMaster: default flowable link color = BrushKeys.Green = #67C23A."""
    assert EDGE_COLOR.name().upper() == "#67C23A"


def test_link_selected_color_is_wpf_accent():
    """WPF: IsSelected trigger = BrushKeys.Accent = #3399FF."""
    assert EDGE_COLOR_SELECTED.name().upper() == "#3399FF"


def test_link_running_color_and_dash():
    """WPF: State=Running trigger = Accent + StrokeDashArray='4 4'."""
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    target = _socket(right_item, PortDock.LEFT)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, target.get_center_scene_pos())
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    edge = scene.get_all_edge_items()[0]
    edge.set_state(EdgeState.RUNNING)
    pen = edge._active_pen()
    assert pen.color().name().upper() == EDGE_COLOR_RUNNING.name().upper()
    assert pen.style() == Qt.CustomDashLine
    assert list(pen.dashPattern()) == DASH_RUNNING


def test_link_success_color_is_wpf_green():
    """WPF: State=Success trigger = BrushKeys.Green = #67C23A."""
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    target = _socket(right_item, PortDock.LEFT)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, target.get_center_scene_pos())
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    edge = scene.get_all_edge_items()[0]
    edge.set_state(EdgeState.SUCCESS)
    assert edge._active_pen().color().name().upper() == EDGE_COLOR_SUCCESS.name().upper()


def test_link_error_color_is_wpf_red():
    """WPF: State=Error trigger = BrushKeys.Red = #dc000c."""
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    target = _socket(right_item, PortDock.LEFT)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, target.get_center_scene_pos())
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    edge = scene.get_all_edge_items()[0]
    edge.set_state(EdgeState.ERROR)
    assert edge._active_pen().color().name().upper() == EDGE_COLOR_ERROR.name().upper()


# ═══════════════════════════════════════════════════════════════════════════
# WPF Dynamic Link Style Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_dynamic_edge_has_dash_pattern_5_2():
    """WPF: S.Link.Dash uses StrokeDashArray='5 2'."""
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    scene.start_edge_drag(source)
    assert scene._dynamic_edge._dash_pattern == DASH_DYNAMIC


# ═══════════════════════════════════════════════════════════════════════════
# WPF Workflow State Propagation
# ═══════════════════════════════════════════════════════════════════════════

def test_workflow_state_changes_edge_color():
    """WPF: workflow node state propagates to connected edges via DataTriggers."""
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    target = _socket(right_item, PortDock.LEFT)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, target.get_center_scene_pos())
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    edge = scene.get_all_edge_items()[0]
    node_id = left_item.node_data.node_id

    scene.on_workflow_state_changed(node_id, "running")
    assert edge._state == EdgeState.RUNNING

    scene.on_workflow_state_changed(node_id, "completed")
    assert edge._state == EdgeState.SUCCESS

    scene.on_workflow_state_changed(node_id, "error")
    assert edge._state == EdgeState.ERROR

    scene.on_workflow_state_changed(node_id, "idle")
    assert edge._state == EdgeState.NORMAL


# ═══════════════════════════════════════════════════════════════════════════
# Core Edge Tests (validated against original tests)
# ═══════════════════════════════════════════════════════════════════════════

def test_edge_commit_creates_permanent_link():
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    target = _socket(right_item, PortDock.LEFT)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, target.get_center_scene_pos())
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    assert len(scene.get_all_edge_items()) == 1
    assert len(workflow.get_all_links()) == 1


def test_invalid_output_to_output_connection_is_rejected():
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    invalid_target = _socket(right_item, PortDock.RIGHT)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, invalid_target.get_center_scene_pos())
    scene.end_edge_drag(source, invalid_target.get_center_scene_pos())
    _pump(app)
    assert len(scene.get_all_edge_items()) == 0


def test_self_connection_is_rejected():
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    self_target = _socket(left_item, PortDock.TOP)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, self_target.get_center_scene_pos())
    scene.end_edge_drag(source, self_target.get_center_scene_pos())
    _pump(app)
    assert len(scene.get_all_edge_items()) == 0


def test_edge_path_updates_when_node_moves():
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    target = _socket(right_item, PortDock.LEFT)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, target.get_center_scene_pos())
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    edge = scene.get_all_edge_items()[0]
    old_br = edge._path.boundingRect()
    right_item.setPos(QPointF(380, 180))
    _pump(app)
    new_br = edge._path.boundingRect()
    assert old_br != new_br


def test_edge_disconnect_cleans_up():
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    target = _socket(right_item, PortDock.LEFT)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, target.get_center_scene_pos())
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    edge = scene.get_all_edge_items()[0]
    link_id = edge.link_data.link_id
    scene.remove_edge_item(link_id)
    assert len(scene.get_all_edge_items()) == 0
    assert len(source._connected_edges) == 0
    assert len(target._connected_edges) == 0


def test_duplicate_edge_is_blocked():
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    target = _socket(right_item, PortDock.LEFT)
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, target.get_center_scene_pos())
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    assert len(scene.get_all_edge_items()) == 1
    scene.start_edge_drag(source)
    scene.update_edge_drag(source, target.get_center_scene_pos())
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    assert len(scene.get_all_edge_items()) == 1


def test_dynamic_edge_singleton_reused():
    app = _app()
    scene, workflow, left_item, right_item = _make_scene_with_two_nodes()
    source = _socket(left_item, PortDock.RIGHT)
    target = _socket(right_item, PortDock.LEFT)
    scene.start_edge_drag(source)
    first = scene._dynamic_edge
    scene.end_edge_drag(source, target.get_center_scene_pos())
    _pump(app)
    scene.start_edge_drag(source)
    second = scene._dynamic_edge
    assert first is second

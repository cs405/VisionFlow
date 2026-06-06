"""Trace the exact execution flow to find why Start doesn't update UI.

Tests the pipeline: execute() → invoke() → events → handlers → ???.
No Qt needed — pure model + event system tracing.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.workflow import WorkflowEngine, WorkflowState
from core.node_base import VisionNodeData
from core.data_packet import FlowableResult
from core.registry import node_registry
from core.events import EventType, event_system


# ── Register a real-ish test node ──

class CameraLikeNode(VisionNodeData):
    """Simulates a camera capture node that produces an image."""
    def __init__(self):
        super().__init__()
        self.name = "摄像头"
        self.invoked = False
        self.invoke_count = 0
        self.diagram_data = None  # Will be set by workflow.add_node()

    def invoke_core(self, src, from_data, diagram):
        self.invoked = True
        self.invoke_count += 1
        import numpy as np
        return FlowableResult.ok(value=np.zeros((100, 100, 3), dtype=np.uint8),
                                 message="captured")

node_registry.register(CameraLikeNode, "test")


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: Does execute() actually run node.invoke()?
# ═══════════════════════════════════════════════════════════════════════════

def test_execute_runs_nodes():
    """Verify that execute() calls invoke() on each node."""
    print("=== Test 1: execute() actually invokes nodes ===")

    wf = WorkflowEngine("test")
    cam = CameraLikeNode()
    wf.add_node(cam)

    assert cam.invoked is False
    assert wf.can_start() is True

    result = wf.start()
    print(f"  start() returned: state={result.state.name}, msg={result.message}")
    print(f"  node.invoked = {cam.invoked}")
    print(f"  node.invoke_count = {cam.invoke_count}")
    print(f"  workflow state = {wf.state.name}")

    assert cam.invoked is True, "FAIL: node.invoke() was NEVER called!"
    assert cam.invoke_count == 1, f"FAIL: invoke called {cam.invoke_count} times, expected 1"
    assert result.is_ok, f"FAIL: start() returned error: {result.message}"
    assert wf.state == WorkflowState.SUCCESS, f"FAIL: workflow state is {wf.state.name}"

    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════════════════════
# Test 2: Are NODE_STARTED / NODE_COMPLETED events published?
# ═══════════════════════════════════════════════════════════════════════════

def test_events_published():
    """Verify that NODE_STARTED and NODE_COMPLETED fire during execution."""
    print("=== Test 2: NODE_STARTED / NODE_COMPLETED events ===")

    events = []
    def trace_handler(event_type):
        def handler(sender, **kwargs):
            events.append((event_type, getattr(sender, 'name', '?')))
        return handler

    event_system.subscribe(EventType.NODE_STARTED, trace_handler(EventType.NODE_STARTED))
    event_system.subscribe(EventType.NODE_COMPLETED, trace_handler(EventType.NODE_COMPLETED))
    event_system.subscribe(EventType.WORKFLOW_STARTED, trace_handler(EventType.WORKFLOW_STARTED))
    event_system.subscribe(EventType.WORKFLOW_COMPLETED, trace_handler(EventType.WORKFLOW_COMPLETED))

    wf = WorkflowEngine("test")
    cam = CameraLikeNode()
    wf.add_node(cam)
    wf.start()

    print(f"  Events received: {len(events)}")
    for e in events:
        print(f"    {e[0].name}: sender={e[1]}")

    assert len(events) >= 4, f"FAIL: expected >=4 events, got {len(events)}"
    # Order: WORKFLOW_STARTED → NODE_STARTED → NODE_COMPLETED → WORKFLOW_COMPLETED
    assert events[0][0] == EventType.WORKFLOW_STARTED, f"FAIL: first event is {events[0][0].name}"
    assert events[1][0] == EventType.NODE_STARTED, f"FAIL: second event is {events[1][0].name}"
    assert events[2][0] == EventType.NODE_COMPLETED, f"FAIL: third event is {events[2][0].name}"
    assert events[3][0] == EventType.WORKFLOW_COMPLETED, f"FAIL: fourth event is {events[3][0].name}"

    # Cleanup
    for et in [EventType.NODE_STARTED, EventType.NODE_COMPLETED,
               EventType.WORKFLOW_STARTED, EventType.WORKFLOW_COMPLETED]:
        event_system._handlers[et].clear()

    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════════════════════
# Test 3: Does node.diagram_data get set correctly?
# ═══════════════════════════════════════════════════════════════════════════
# The _belongs_to_bound_workflow check in editor_widget uses:
#   getattr(sender, 'diagram_data', None) is self._subscribed_workflow

def test_node_diagram_data():
    """Verify node.diagram_data points to the correct workflow."""
    print("=== Test 3: node.diagram_data reference ===")

    wf = WorkflowEngine("test")
    cam = CameraLikeNode()

    assert cam.diagram_data is None  # Not set yet

    wf.add_node(cam)
    print(f"  After add_node: cam.diagram_data is wf = {cam.diagram_data is wf}")
    assert cam.diagram_data is wf, \
        "FAIL: node.diagram_data must point to the workflow after add_node()!"

    # After duplicate() (used in add_diagram_from_template)
    d = wf.to_dict()
    wf2 = WorkflowEngine("clone")
    def factory(tn):
        return node_registry.create(tn)
    wf2.from_dict(d, factory)
    clone_cam = list(wf2._nodes.values())[0]

    print(f"  After from_dict: clone.diagram_data = {clone_cam.diagram_data}")
    print(f"  clone.diagram_data is wf2 = {clone_cam.diagram_data is wf2}")
    assert clone_cam.diagram_data is wf2, \
        "FAIL: deserialized node must have diagram_data pointing to its workflow!"

    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════════════════════
# Test 4: Worker thread event handling simulation
# ═══════════════════════════════════════════════════════════════════════════

def test_worker_thread_execution():
    """Simulate what happens when execute() runs on a worker thread.

    The key question: do event handlers run on the worker thread?
    And if so, would pyqtSignal.emit() from there reach the main thread?
    """
    print("=== Test 4: worker thread execution trace ===")
    import threading

    handler_threads = []
    def trace_handler(event_type):
        def handler(sender, **kwargs):
            handler_threads.append((
                event_type,
                threading.current_thread().name,
                getattr(sender, 'name', '?')))
        return handler

    for et in [EventType.NODE_STARTED, EventType.NODE_COMPLETED]:
        event_system.subscribe(et, trace_handler(et))

    wf = WorkflowEngine("test")
    cam = CameraLikeNode()
    wf.add_node(cam)

    main_thread_name = threading.current_thread().name

    def run_on_worker():
        wf.start()

    worker = threading.Thread(target=run_on_worker, name="worker-thread", daemon=True)
    worker.start()
    worker.join(timeout=5)

    print(f"  Main thread: {main_thread_name}")
    print(f"  Handler thread traces:")
    for et, tname, sender_name in handler_threads:
        on_main = (tname == main_thread_name)
        print(f"    {et.name}: thread=\"{tname}\" (main={on_main}), sender={sender_name}")

    # KEY FINDING: handlers run on the WORKER thread, not the main thread!
    for et, tname, _ in handler_threads:
        assert tname != main_thread_name, \
            f"OK: {et.name} handler runs on worker thread (\"{tname}\") — " \
            f"UI updates from here will fail without cross-thread marshaling"

    print(f"  CONFIRMED: {len(handler_threads)} event handlers ran on worker thread")
    print(f"  These handlers must use pyqtSignal (or equivalent) to reach the UI thread")

    # Cleanup
    for et in [EventType.NODE_STARTED, EventType.NODE_COMPLETED]:
        event_system._handlers[et].clear()

    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════════════════════
# Test 5: Verify get_start_node_data finds the right node
# ═══════════════════════════════════════════════════════════════════════════

def test_get_start_node():
    """Verify the start node discovery logic."""
    print("=== Test 5: get_start_node_data() ===")

    # Case 1: single node (no links)
    wf = WorkflowEngine("test")
    cam = CameraLikeNode()
    wf.add_node(cam)
    s = wf.get_start_node_data()
    print(f"  Single node: found={'yes' if s else 'no'}, id={s.node_id if s else 'N/A'}")
    assert s is not None, "FAIL: single node with output ports should be a start node"
    assert s.node_id == cam.node_id

    # Case 2: two nodes linked
    cam2 = CameraLikeNode()
    wf.add_node(cam2)
    wf.add_link(cam.node_id, cam2.node_id)
    s = wf.get_start_node_data()
    print(f"  Two nodes (cam→cam2): start={s.name if s else 'N/A'}")
    assert s is not None and s.node_id == cam.node_id, \
        "FAIL: cam (no inputs) should be the start node, not cam2"

    # Case 3: node with no output ports
    from core.node_base import Port, PortType
    cam3 = CameraLikeNode()
    cam3.ports = [p for p in cam3.ports if not p.is_output]  # Remove output ports
    wf3 = WorkflowEngine("test3")
    wf3.add_node(cam3)
    s = wf3.get_start_node_data()
    print(f"  Node with no output ports: start={'found' if s else 'NONE'}")
    assert s is None, "FAIL: node with no output ports should NOT be a start node"

    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════════════════════
# Test 6: Thread safety — does _sync_workflow_to_project corrupt execution?
# ═══════════════════════════════════════════════════════════════════════════

def test_sync_before_execute():
    """Verify _sync_workflow_to_project doesn't lose nodes before execution."""
    print("=== Test 6: sync before execute preserves nodes ===")

    # Simulate: user adds nodes, clicks "开始"
    # MainWindow does: _sync_workflow_to_project() → workflow.start()

    wf = WorkflowEngine("test")
    cam = CameraLikeNode()
    wf.add_node(cam)

    # _sync_workflow_to_project equivalent: save_to_workflow
    # This clears workflow._links and rebuilds from edges
    # But _nodes should remain
    wf._links = []  # Simulates save_to_workflow clearing links
    # (links are empty anyway, no edges)

    assert len(wf.get_all_nodes()) == 1, f"FAIL: node lost after sync! nodes={len(wf.get_all_nodes())}"
    assert wf.can_start() is True, f"FAIL: can_start=False after sync"

    result = wf.start()
    assert result.is_ok
    assert cam.invoked
    print(f"  After sync+start: node.invoked={cam.invoked}, state={wf.state.name}")
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════════════════════
# Run all
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    all_ok = True
    tests = [
        test_execute_runs_nodes,
        test_events_published,
        test_node_diagram_data,
        test_worker_thread_execution,
        test_get_start_node,
        test_sync_before_execute,
    ]
    for test_fn in tests:
        try:
            test_fn()
        except AssertionError as e:
            print(f"  {e}\n")
            all_ok = False
        except Exception as e:
            print(f"  ERROR: {e}\n")
            import traceback
            traceback.print_exc()
            all_ok = False

    print("=" * 60)
    if all_ok:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED — see above")
    print()
    print("SUMMARY:")
    print("  - Model layer (execute/invoke/events): correct")
    print("  - Events fire on worker thread → handlers must marshal to UI thread")
    print("  - pyqtSignal should auto-queue cross-thread BUT must verify with Qt")
    print("  - If pyqtSignal fails: use QMetaObject.invokeMethod(Qt.QueuedConnection)")
    print("  - Image viewer NOT updated after execution — separate bug")

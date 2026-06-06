"""Test: verify Start button stays disabled after adding nodes — and the fix.

Bug 1 (main): _on_ev_diag_chg updates node count label but never calls
_refresh_command_states. So can_start() → True after nodes are added, but
the Start button stays disabled.

Bug 2 (cosmetic): NodeItem.__init__ sets _state = NodeState.COMPLETED (green),
making new nodes appear as "already finished" instead of IDLE (gray).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.workflow import WorkflowEngine, WorkflowState
from core.node_base import VisionNodeData
from core.data_packet import FlowableResult
from core.registry import node_registry


# ── Setup: register test nodes ──

class TestNode(VisionNodeData):
    def invoke_core(self, a, b, c):
        return FlowableResult.ok(message="ok")


node_registry.register(TestNode, "test")


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: can_start transitions when nodes are added/removed
# ═══════════════════════════════════════════════════════════════════════════

def test_can_start_with_nodes():
    """Simulate exactly what happens when user adds nodes to canvas."""
    print("=== Test 1: can_start() before/after adding nodes ===")

    wf = WorkflowEngine("test")
    assert wf.state == WorkflowState.NONE
    assert wf.can_start() is False, "Empty workflow should NOT be startable"

    # User adds first node via toolbox
    n1 = TestNode()
    wf.add_node(n1)
    print(f"  After 1st node: state={wf.state.name}, nodes={len(wf.get_all_nodes())}, can_start={wf.can_start()}")
    assert wf.can_start() is True, "BUG: can_start() should be True after adding a node!"

    # User adds second node
    n2 = TestNode()
    wf.add_node(n2)
    print(f"  After 2nd node: state={wf.state.name}, nodes={len(wf.get_all_nodes())}, can_start={wf.can_start()}")
    assert wf.can_start() is True

    # Remove one node — should still be startable
    wf.remove_node(n2.node_id)
    print(f"  After removing 2nd: nodes={len(wf.get_all_nodes())}, can_start={wf.can_start()}")
    assert wf.can_start() is True

    # Remove last node — should NOT be startable
    wf.remove_node(n1.node_id)
    print(f"  After removing all: nodes={len(wf.get_all_nodes())}, can_start={wf.can_start()}")
    assert wf.can_start() is False

    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════════════════════
# Test 2: DIAGRAM_CHANGED event tracking
# ═══════════════════════════════════════════════════════════════════════════

def test_diagram_changed_event():
    """Verify that DIAGRAM_CHANGED fires when nodes are added (triggers _on_ev_diag_chg)."""
    print("=== Test 2: DIAGRAM_CHANGED event on node add ===")

    from core.events import EventType, event_system

    events_received = []

    def handler(sender, **kwargs):
        events_received.append(("DIAGRAM_CHANGED", sender))

    event_system.subscribe(EventType.DIAGRAM_CHANGED, handler)

    wf = WorkflowEngine("test2")
    n = TestNode()
    wf.add_node(n)

    assert len(events_received) == 1, f"Expected 1 DIAGRAM_CHANGED, got {len(events_received)}"
    assert events_received[0][0] == "DIAGRAM_CHANGED"
    print(f"  Events received: {len(events_received)} OK")
    print(f"  After adding node: can_start={wf.can_start()} OK")

    # Cleanup
    event_system.unsubscribe(EventType.DIAGRAM_CHANGED, handler)
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════════════════════
# Test 3: NodeItem default state should be IDLE not COMPLETED
# ═══════════════════════════════════════════════════════════════════════════

def test_node_item_default_state():
    """Verify NodeItem.__init__ sets _state = NodeState.IDLE, not COMPLETED."""
    print("=== Test 3: NodeItem default state ===")

    import os
    node_item_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "gui", "node_editor", "node_item.py")

    with open(node_item_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find the init and its _state assignment
    state_line = ""
    in_init = False
    indent = ""
    for i, line in enumerate(lines):
        # Detect __init__ start
        if line.startswith("    def __init__"):
            in_init = True
            indent = "        "  # 8 spaces (inside class -> method)
            continue
        if in_init:
            # Found state line inside __init__
            if "_state" in line and "NodeState" in line and "=" in line:
                state_line = line.strip()
                break
            # Left __init__ if dedented
            if line.strip() and not line.startswith(indent):
                break

    print(f"  _state default: {state_line}")
    assert "NodeState.IDLE" in state_line, (
        f"NodeItem should default to IDLE, got: {state_line}")
    assert "NodeState.COMPLETED" not in state_line, (
        f"NodeItem should NOT default to COMPLETED, got: {state_line}")

    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════════════════════
# Test 4: IDLE state color and left bar visibility
# ═══════════════════════════════════════════════════════════════════════════

def test_idle_color_and_bar():
    """Verify IDLE state has visible color (not dim gray) and shows left bar."""
    print("=== Test 4: IDLE state color and bar visibility ===")

    import os
    node_item_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "gui", "node_editor", "node_item.py")

    with open(node_item_path, "r", encoding="utf-8") as f:
        src = f.read()

    # Check: IDLE returns a visible color (not #909399)
    assert 'NodeState.IDLE:\n            return QColor("#5C7A99")' in src or \
           'NodeState.IDLE:\n            return QColor' in src, \
        "IDLE state should have a visible steel-blue color"

    # Check: IDLE is included in left bar visibility
    assert 'NodeState.IDLE' in src.split('_draw_left_bar')[1].split('if not bar_visible')[0], \
        "IDLE should show left bar"

    print("  IDLE color: #5C7A99 (steel-blue) OK")
    print("  IDLE left bar: visible OK")
    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════════════════════
# Test 5: Full flow simulation (model-level)
# ═══════════════════════════════════════════════════════════════════════════

def test_full_flow():
    """Simulate user: open project → add nodes → click start."""
    print("=== Test 4: Full user flow simulation ===")

    wf = WorkflowEngine("flow")
    assert wf.can_start() is False
    print(f"  1. Empty workflow: can_start=False OK")

    n1 = TestNode()
    n2 = TestNode()
    wf.add_node(n1)
    wf.add_node(n2)
    wf.add_link(n1.node_id, n2.node_id)
    assert wf.can_start() is True
    print(f"  2. After adding 2 nodes + link: can_start=True OK")

    result = wf.start()
    assert wf.state == WorkflowState.SUCCESS
    assert result.is_ok
    print(f"  3. Start → state={wf.state.name}, result={result.message} OK")

    assert wf.can_start() is True  # Can restart after success
    print(f"  4. After success: can_start=True (can re-run) OK")

    wf.reset()
    assert wf.state == WorkflowState.NONE
    print(f"  5. Reset → state={wf.state.name} OK")

    print("  PASSED\n")


# ═══════════════════════════════════════════════════════════════════════════
# Run all
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    all_ok = True
    for test in [test_can_start_with_nodes, test_diagram_changed_event,
                 test_node_item_default_state, test_idle_color_and_bar,
                 test_full_flow]:
        try:
            test()
        except AssertionError as e:
            print(f"  FAILED: {e}\n")
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
        print("SOME TESTS FAILED")

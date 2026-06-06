"""Test history results pipeline end-to-end.

Simulates: node creation → workflow binding → execution → history collection →
ResultPanel display sync.  Traces every step with assertions and diagnostic output.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 1. Bootstrap core modules ──
from core.node_base import VisionNodeData, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine
from core.events import EventType, event_system
from core.result_presenter import VisionMessage

import numpy as np


# ── 2. Minimal test node (no camera dependency) ──
class TestNode(VisionNodeData):
    """Minimal vision node for testing — always returns a 10x10 green image."""
    __group__ = "测试"

    def __init__(self):
        super().__init__()
        self.name = "测试节点"

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        img[:] = (0, 255, 0)
        self.pixel_width = 10
        self.pixel_height = 10
        return self.ok(img, "测试成功")

    def is_valid(self, mat) -> bool:
        return mat is not None

    def _update_result_image_source(self):
        self._result_image_source = self._mat


# ── 3. Trace event system ──
events_fired: list[str] = []

def trace_event(event_type, sender=None, **kwargs):
    events_fired.append(event_type.name)
    node_name = getattr(sender, 'name', '?') if sender else '?'
    has_diagram = getattr(sender, 'diagram_data', None) is not None if sender else False
    print(f"  [EVENT] {event_type.name:25s} sender={node_name:10s} diagram_data={has_diagram}")

for et in (EventType.NODE_STARTED, EventType.NODE_COMPLETED, EventType.NODE_ERROR):
    event_system.subscribe(et, lambda s, et=et, **kw: trace_event(et, s, **kw))


# ── 4. Create workflow + node ──
print("=" * 60)
print("Step 1: Create WorkflowEngine + TestNode")
print("=" * 60)

wf = WorkflowEngine(name="测试流程")
node = TestNode()
print(f"  workflow id: {id(wf)}")
print(f"  node created: {node.name} (id={node.node_id})")
print(f"  node.diagram_data before add_node: {node.diagram_data}")

wf.add_node(node)
print(f"  node.diagram_data after add_node:  {id(node.diagram_data)}")
print(f"  node.diagram_data is wf:           {node.diagram_data is wf}")
print(f"  wf.messages count before exec:     {len(wf.messages)}")

# Check on_node_completed exists
print(f"  wf has on_node_completed:          {hasattr(wf, 'on_node_completed')}")
print(f"  node.use_invoked_part:             {node.use_invoked_part}")


# ── 5. Execute ──
print()
print("=" * 60)
print("Step 2: Execute workflow")
print("=" * 60)

events_fired.clear()
result = wf.start()
print(f"  result:               {result.message} (ok={result.is_ok})")
print(f"  events fired:         {events_fired}")


# ── 6. Check workflow.messages ──
print()
print("=" * 60)
print("Step 3: Check workflow.messages after execution")
print("=" * 60)

print(f"  wf.messages count:    {len(wf.messages)}")
msgs = wf.get_messages_snapshot()
print(f"  get_messages_snapshot: {len(msgs)}")

for i, msg in enumerate(msgs):
    print(f"  msg[{i}]: index={msg.index}, type={msg.type_name}, "
          f"state={msg.state}, message={msg.message}")
    print(f"           result_node_data is None: {msg.result_node_data is None}")
    print(f"           result_node_data name:     {getattr(msg.result_node_data, 'name', 'N/A')}")
    print(f"           result_image_source:       {'set' if msg.result_image_source is not None else 'None'}")

if len(msgs) == 0:
    print()
    print("  *** FAIL: No messages in workflow! ***")
    print()
    print("  Let's check _invoke_action flow manually...")

    # Manually call on_node_completed to verify it works
    import time
    ts = time.strftime("%H:%M:%S")
    print(f"  Manually calling wf.on_node_completed(node, 'Success', '{ts}')...")
    wf.on_node_completed(node, "Success", ts)
    print(f"  After manual call: wf.messages count = {len(wf.messages)}")
    msgs2 = wf.get_messages_snapshot()
    for i, msg in enumerate(msgs2):
        print(f"  msg[{i}]: index={msg.index}, type={msg.type_name}, state={msg.state}")

    if len(msgs2) > 0:
        print()
        print("  Manual call WORKS → _invoke_action is NOT calling on_node_completed!")
        print("  Let's check if _invoke_action is reached at all...")

        # Re-check the invoke path
        node2 = TestNode()
        node2.name = "测试节点2"
        wf.add_node(node2)
        print(f"  node2.diagram_data is wf: {node2.diagram_data is wf}")

        # Check what invoke does
        from core.node_base import LinkData
        result2 = node2.invoke(None, wf)
        print(f"  node2.invoke(None, wf) result: {result2.message}")
        print(f"  node2.diagram_data is wf after invoke: {node2.diagram_data is wf}")
        print(f"  wf.messages count after node2: {len(wf.messages)}")


# ── 7. Test ResultPanel integration (headless) ──
print()
print("=" * 60)
print("Step 4: Simulate ResultPanel._on_event_node_done")
print("=" * 60)

# We can't create a real ResultPanel without QApplication, so simulate it
class MockResultPanel:
    def __init__(self):
        self._workflow = None
        self.sync_count = 0

    def _on_event_node_done(self, sender, **kwargs):
        if sender is None:
            print("  MockPanel: sender is None, skip")
            return
        wf = getattr(sender, 'diagram_data', None)
        if wf is None:
            print("  MockPanel: sender.diagram_data is None, skip")
            return
        if self._workflow is not wf:
            self._workflow = wf
            print(f"  MockPanel: bound to workflow id={id(wf)}")
        self.sync_count += 1
        msgs = wf.get_messages_snapshot()
        print(f"  MockPanel sync #{self.sync_count}: workflow messages count = {len(msgs)}")

mock = MockResultPanel()

# Re-execute and watch
print("  Creating new workflow + node for mock test...")
wf3 = WorkflowEngine(name="测试流程3")
node3 = TestNode()
node3.name = "测试节点3"
wf3.add_node(node3)

# Subscribe mock AFTER node is in workflow (like ResultPanel does in __init__)
event_system.subscribe(EventType.NODE_COMPLETED, mock._on_event_node_done)
event_system.subscribe(EventType.NODE_ERROR, mock._on_event_node_done)

print(f"  node3.diagram_data is wf3: {node3.diagram_data is wf3}")
print("  Executing wf3...")
result3 = wf3.start()
print(f"  Result: {result3.message}")
print(f"  wf3.messages count: {len(wf3.messages)}")
print(f"  MockPanel sync count: {mock.sync_count}")

if mock.sync_count == 0:
    print()
    print("  *** FAIL: _on_event_node_done was never called! ***")
    print("  The NODE_COMPLETED event handler didn't fire for the mock panel.")
    print("  Checking event subscriptions...")

# Cleanup
event_system.unsubscribe(EventType.NODE_COMPLETED, mock._on_event_node_done)
event_system.unsubscribe(EventType.NODE_ERROR, mock._on_event_node_done)


# ── 8. Summary ──
print()
print("=" * 60)
print("DIAGNOSIS SUMMARY")
print("=" * 60)
print(f"  1. node.diagram_data is workflow: {'PASS' if node3.diagram_data is wf3 else 'FAIL'}")
print(f"  2. workflow.on_node_completed works: {'PASS' if len(msgs2) > 0 else 'FAIL'}")
print(f"  3. _invoke_action calls on_node_completed: {'PASS' if len(wf.messages) > 0 else 'FAIL'}")
print(f"  4. NODE_COMPLETED event fires: {'PASS' if 'NODE_COMPLETED' in events_fired else 'FAIL'}")
print(f"  5. _on_event_node_done receives event: {'PASS' if mock.sync_count > 0 else 'FAIL'}")
print(f"  6. Messages visible after full flow: {'PASS' if len(wf3.messages) > 0 else 'FAIL'}")

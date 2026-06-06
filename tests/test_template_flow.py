"""Test template save/load flow to find the bug causing empty templates.

Issue: User saved templates but adding from template shows no content.
"""

import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.node_base import NodeBase, VisionNodeData
from core.workflow import WorkflowEngine
from core.project import ProjectItem, ProjectService, DiagramData
from core.registry import node_registry


# =============================================================================
# Setup: register test node types BEFORE any template operations
# =============================================================================

class TestSourceNode(VisionNodeData):
    """A simple test source node."""
    def __init__(self):
        super().__init__()
        self.name = "TestSource"

    def invoke_core(self, src_image_node_data, from_node_data, diagram):
        from core.data_packet import FlowableResult
        return FlowableResult.ok(message="test source done")


class TestBlurNode(VisionNodeData):
    """A simple test blur node."""
    def __init__(self):
        super().__init__()
        self.name = "TestBlur"

    def invoke_core(self, src_image_node_data, from_node_data, diagram):
        from core.data_packet import FlowableResult
        return FlowableResult.ok(message="test blur done")


node_registry.register(TestSourceNode, "test")
node_registry.register(TestBlurNode, "test")


# =============================================================================
# Test 1: Basic workflow serialization round-trip
# =============================================================================

def test_workflow_serialization_roundtrip():
    """Verify that a workflow with nodes survives to_dict → from_dict."""
    print("\n=== Test 1: Workflow serialization round-trip ===")

    wf = WorkflowEngine(name="TestFlow")
    src = TestSourceNode()
    blur = TestBlurNode()
    wf.add_node(src)
    wf.add_node(blur)
    wf.add_link(src.node_id, blur.node_id)

    print(f"  Before serialization: {len(wf.get_all_nodes())} nodes, {len(wf.get_all_links())} links")
    assert len(wf.get_all_nodes()) == 2, f"Expected 2 nodes, got {len(wf.get_all_nodes())}"
    assert len(wf.get_all_links()) == 1, f"Expected 1 link, got {len(wf.get_all_links())}"

    # Serialize
    d = wf.to_dict()
    print(f"  Serialized nodes: {len(d['nodes'])}, links: {len(d['links'])}")
    assert len(d['nodes']) == 2, f"to_dict: Expected 2 nodes, got {len(d['nodes'])}"
    assert len(d['links']) == 1, f"to_dict: Expected 1 link, got {len(d['links'])}"

    # Deserialize
    wf2 = WorkflowEngine(name="TestFlow2")
    def factory(type_name):
        return node_registry.create(type_name)
    wf2.from_dict(d, factory)

    print(f"  After deserialization: {len(wf2.get_all_nodes())} nodes, {len(wf2.get_all_links())} links")
    assert len(wf2.get_all_nodes()) == 2, f"from_dict: Expected 2 nodes, got {len(wf2.get_all_nodes())}"
    assert len(wf2.get_all_links()) == 1, f"from_dict: Expected 1 link, got {len(wf2.get_all_links())}"

    print("  PASSED")
    return True


# =============================================================================
# Test 2: DiagramData to_dict with nodes
# =============================================================================

def test_diagramdata_to_dict_with_nodes():
    """Verify DiagramData.to_dict() serializes workflow nodes."""
    print("\n=== Test 2: DiagramData.to_dict() with nodes ===")

    diagram = DiagramData(name="TestDiagram")
    wf = WorkflowEngine(name="TestDiagram")
    src = TestSourceNode()
    blur = TestBlurNode()
    wf.add_node(src)
    wf.add_node(blur)
    wf.add_link(src.node_id, blur.node_id)
    diagram.workflow = wf

    d = diagram.to_dict()
    wf_data = d.get("workflow", {})
    print(f"  Serialized workflow nodes: {len(wf_data.get('nodes', []))}, links: {len(wf_data.get('links', []))}")
    assert len(wf_data.get('nodes', [])) == 2, f"Expected 2 nodes in serialized data, got {len(wf_data.get('nodes', []))}"
    assert len(wf_data.get('links', [])) == 1, f"Expected 1 link in serialized data, got {len(wf_data.get('links', []))}"

    # Deserialize via from_dict
    def factory(type_name):
        return node_registry.create(type_name)
    diagram2 = DiagramData.from_dict(d, factory)
    print(f"  Deserialized workflow nodes: {len(diagram2.workflow.get_all_nodes())}, links: {len(diagram2.workflow.get_all_links())}")
    assert len(diagram2.workflow.get_all_nodes()) == 2
    assert len(diagram2.workflow.get_all_links()) == 1

    print("  PASSED")
    return True


# =============================================================================
# Test 3: save_diagram_as_template
# =============================================================================

def test_save_diagram_as_template():
    """Verify save_diagram_as_template preserves nodes."""
    print("\n=== Test 3: save_diagram_as_template ===")

    project = ProjectItem(name="TestProject")
    diagram = project.add_diagram("TestDiagram")

    # Add nodes to the workflow
    src = TestSourceNode()
    blur = TestBlurNode()
    diagram.workflow.add_node(src)
    diagram.workflow.add_node(blur)
    diagram.workflow.add_link(src.node_id, blur.node_id)

    print(f"  Before save: diagram has {len(diagram.workflow.get_all_nodes())} nodes, {len(diagram.workflow.get_all_links())} links")
    assert len(diagram.workflow.get_all_nodes()) == 2
    assert len(diagram.workflow.get_all_links()) == 1

    # Save as template
    template = project.save_diagram_as_template(diagram, name="TestTemplate")

    print(f"  Template workflow nodes: {len(template.workflow.get_all_nodes())}, links: {len(template.workflow.get_all_links())}")
    assert len(template.workflow.get_all_nodes()) == 2, \
        f"BUG: Template has {len(template.workflow.get_all_nodes())} nodes, expected 2"
    assert len(template.workflow.get_all_links()) == 1, \
        f"BUG: Template has {len(template.workflow.get_all_links())} links, expected 1"

    # Also check the project's template list
    assert len(project._templates) == 1
    saved_template = project._templates[0]
    assert len(saved_template.workflow.get_all_nodes()) == 2

    print("  PASSED")
    return True


# =============================================================================
# Test 4: add_diagram_from_template
# =============================================================================

def test_add_diagram_from_template():
    """Verify add_diagram_from_template produces a diagram with nodes."""
    print("\n=== Test 4: add_diagram_from_template ===")

    project = ProjectItem(name="TestProject")
    diagram = project.add_diagram("TestDiagram")

    # Add nodes to the workflow
    src = TestSourceNode()
    blur = TestBlurNode()
    diagram.workflow.add_node(src)
    diagram.workflow.add_node(blur)
    diagram.workflow.add_link(src.node_id, blur.node_id)

    # Save as template
    project.save_diagram_as_template(diagram, name="TestTemplate")
    assert len(project._templates) == 1

    # Now add from template
    clone = project.add_diagram_from_template(0)
    assert clone is not None, "add_diagram_from_template returned None"

    print(f"  Clone workflow nodes: {len(clone.workflow.get_all_nodes())}, links: {len(clone.workflow.get_all_links())}")
    assert len(clone.workflow.get_all_nodes()) == 2, \
        f"BUG: Clone has {len(clone.workflow.get_all_nodes())} nodes, expected 2"
    assert len(clone.workflow.get_all_links()) == 1, \
        f"BUG: Clone has {len(clone.workflow.get_all_links())} links, expected 1"

    # Verify project has 2 diagrams now (original + clone)
    assert len(project.diagrams) == 2
    assert project.selected_diagram_index == 1  # Should select the new one

    print("  PASSED")
    return True


# =============================================================================
# Test 5: duplicate preserves nodes
# =============================================================================

def test_duplicate_preserves_nodes():
    """Verify DiagramData.duplicate() preserves workflow nodes."""
    print("\n=== Test 5: duplicate() preserves nodes ===")

    diagram = DiagramData(name="TestDiagram")
    wf = WorkflowEngine(name="TestDiagram")
    src = TestSourceNode()
    blur = TestBlurNode()
    wf.add_node(src)
    wf.add_node(blur)
    wf.add_link(src.node_id, blur.node_id)
    diagram.workflow = wf

    assert len(diagram.workflow.get_all_nodes()) == 2

    clone = diagram.duplicate()
    print(f"  Clone workflow nodes: {len(clone.workflow.get_all_nodes())}, links: {len(clone.workflow.get_all_links())}")
    assert len(clone.workflow.get_all_nodes()) == 2, \
        f"BUG: Clone has {len(clone.workflow.get_all_nodes())} nodes, expected 2"
    assert len(clone.workflow.get_all_links()) == 1, \
        f"BUG: Clone has {len(clone.workflow.get_all_links())} links, expected 1"

    print("  PASSED")
    return True


# =============================================================================
# Test 6: ProjectService save/load templates to file
# =============================================================================

def test_persist_templates_to_file():
    """Verify that templates saved to file preserve nodes."""
    print("\n=== Test 6: Persist templates to file ===")

    project = ProjectItem(name="TestProject")
    diagram = project.add_diagram("TestDiagram")

    src = TestSourceNode()
    blur = TestBlurNode()
    diagram.workflow.add_node(src)
    diagram.workflow.add_node(blur)
    diagram.workflow.add_link(src.node_id, blur.node_id)

    # Save as template
    template = project.save_diagram_as_template(diagram, name="TestTemplate")

    # Serialize to JSON (mimicking save_templates)
    data = {"templates": [template.to_dict()]}
    json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)

    print(f"  JSON size: {len(json_str)} chars")
    print(f"  JSON contains 'TestSourceNode': {'TestSourceNode' in json_str}")
    print(f"  JSON contains 'TestBlurNode': {'TestBlurNode' in json_str}")

    # Parse back
    parsed = json.loads(json_str)
    assert len(parsed["templates"][0]["workflow"]["nodes"]) == 2, \
        f"BUG: JSON has {len(parsed['templates'][0]['workflow']['nodes'])} nodes"
    assert len(parsed["templates"][0]["workflow"]["links"]) == 1

    # Load back
    def factory(type_name):
        return node_registry.create(type_name)
    loaded_template = DiagramData.from_dict(parsed["templates"][0], factory)
    print(f"  Loaded template workflow nodes: {len(loaded_template.workflow.get_all_nodes())}, links: {len(loaded_template.workflow.get_all_links())}")
    assert len(loaded_template.workflow.get_all_nodes()) == 2
    assert len(loaded_template.workflow.get_all_links()) == 1

    print("  PASSED")
    return True


# =============================================================================
# Test 7: CRITICAL - Simulating the ACTUAL UI flow
# =============================================================================

def test_ui_flow_simulation():
    """Simulate exactly what happens when user saves template via UI.

    This is the key test - mimics _on_save_as_template + _sync_workflow_to_project + _persist_templates.
    """
    print("\n=== Test 7: UI flow simulation ===")

    project = ProjectItem(name="TestProject")
    diagram = project.add_diagram("TestDiagram")

    # Simulate the user adding nodes to the workflow (as happens via scene/editor)
    wf = diagram.workflow
    src = TestSourceNode()
    blur = TestBlurNode()
    wf.add_node(src)
    wf.add_node(blur)
    wf.add_link(src.node_id, blur.node_id)

    print(f"  After adding nodes: workflow has {len(wf.get_all_nodes())} nodes, {len(wf.get_all_links())} links")

    # Step 1: _sync_workflow_to_project (diagram.workflow is SAME as editor._workflow)
    # Since they're the same object, no actual change happens.
    # But let's verify: does diagram.to_dict() capture the nodes?
    d = diagram.to_dict()
    print(f"  diagram.to_dict() nodes: {len(d['workflow']['nodes'])}")

    if len(d['workflow']['nodes']) == 0:
        print("  BUG FOUND: diagram.to_dict() returned 0 nodes even though workflow has nodes!")
        print(f"  workflow._nodes keys: {list(wf._nodes.keys())}")
        print(f"  workflow.get_all_nodes(): {wf.get_all_nodes()}")
        return False

    # Step 2: save_diagram_as_template
    template = project.save_diagram_as_template(diagram, name="TestTemplate")
    print(f"  Template workflow nodes: {len(template.workflow.get_all_nodes())}")

    if len(template.workflow.get_all_nodes()) == 0:
        print("  BUG FOUND: Template has no nodes after save_diagram_as_template!")
        return False

    # Step 3: _persist_templates (save to temp file)
    tmpdir = tempfile.mkdtemp()
    tmpfile = os.path.join(tmpdir, "templates_test.json")

    data = {"templates": [t.to_dict() for t in project._templates]}
    with open(tmpfile, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    # Read back
    with open(tmpfile, "r", encoding="utf-8") as f:
        loaded_data = json.load(f)

    loaded_nodes = loaded_data["templates"][0]["workflow"]["nodes"]
    print(f"  Loaded from file - nodes: {len(loaded_nodes)}")

    if len(loaded_nodes) == 0:
        print("  BUG FOUND: Saved file has 0 nodes!")
        return False

    # Step 4: Load templates (like load_templates does)
    def factory(type_name):
        return node_registry.create(type_name)

    loaded_templates = []
    for td in loaded_data.get("templates", []):
        try:
            loaded_templates.append(DiagramData.from_dict(td, factory))
        except Exception as e:
            print(f"  ERROR loading template: {e}")

    assert len(loaded_templates) == 1
    lt = loaded_templates[0]
    print(f"  Loaded template workflow nodes: {len(lt.workflow.get_all_nodes())}")

    if len(lt.workflow.get_all_nodes()) == 0:
        print("  BUG FOUND: Loaded template has no nodes!")
        return False

    # Step 5: Add from template (like add_diagram_from_template)
    clone = lt.duplicate()
    print(f"  Clone workflow nodes: {len(clone.workflow.get_all_nodes())}")

    if len(clone.workflow.get_all_nodes()) == 0:
        print("  BUG FOUND: Clone from template has no nodes!")
        return False

    # Cleanup
    os.remove(tmpfile)
    os.rmdir(tmpdir)

    print("  PASSED")
    return True


# =============================================================================
# Test 8: Test what happens when selected_diagram is NOT the edited diagram
# =============================================================================

def test_selected_diagram_correct():
    """Verify save_diagram_as_template uses the right diagram."""
    print("\n=== Test 8: selected_diagram tracking ===")

    project = ProjectItem(name="TestProject")
    d1 = project.add_diagram("Diagram1")
    d2 = project.add_diagram("Diagram2")

    # Add nodes to d2 (the currently selected one)
    src = TestSourceNode()
    d2.workflow.add_node(src)

    # selected_diagram should be d2 (index 1)
    assert project.selected_diagram_index == 1
    assert project.selected_diagram == d2
    assert len(project.selected_diagram.workflow.get_all_nodes()) == 1

    # save_diagram_as_template should use selected_diagram (d2)
    template = project.save_diagram_as_template(name="TemplateFromD2")
    assert len(template.workflow.get_all_nodes()) == 1, \
        f"BUG: Template has {len(template.workflow.get_all_nodes())} nodes, expected 1"

    print("  PASSED")
    return True


# =============================================================================
# Run all tests
# =============================================================================

if __name__ == "__main__":
    all_passed = True
    tests = [
        test_workflow_serialization_roundtrip,
        test_diagramdata_to_dict_with_nodes,
        test_save_diagram_as_template,
        test_add_diagram_from_template,
        test_duplicate_preserves_nodes,
        test_persist_templates_to_file,
        test_ui_flow_simulation,
        test_selected_diagram_correct,
    ]

    for test_fn in tests:
        try:
            if not test_fn():
                all_passed = False
        except Exception as e:
            print(f"  FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED - Bug is likely in the UI sync layer")
        print("Check: _sync_workflow_to_project() and how editor binds workflow")
    else:
        print("SOME TESTS FAILED - see above for details")

"""
测试 VisionNodeData.invoke() 是否正确设置 _execution_state
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.node_base import VisionNodeData
from core.data_packet import FlowableResult


class MockVisionNode(VisionNodeData):
    """模拟一个成功的视觉节点"""
    def invoke_core(self, mat, **inputs):
        return FlowableResult.ok(mat, "成功")


class MockErrorNode(VisionNodeData):
    """模拟一个失败的视觉节点"""
    def invoke_core(self, mat, **inputs):
        return self.error(None, "模拟错误")


def test_invoke_action():
    """测试 _invoke_action 是否正确设置 _execution_state"""
    node = MockVisionNode()
    node._id = "test1"
    node._execution_state = None

    # Test successful execution
    def action():
        return FlowableResult.ok("data", "成功")

    result = node._invoke_action(action)
    print(f"1. Success case:")
    print(f"   result.is_ok={result.is_ok}, result.is_error={result.is_error}")
    print(f"   _execution_state={node._execution_state}")
    assert node._execution_state == "completed", f"Expected 'completed', got {node._execution_state}"

    # Test error execution
    node._execution_state = None
    def error_action():
        return FlowableResult.error(None, "失败")

    result = node._invoke_action(error_action)
    print(f"2. Error case:")
    print(f"   result.is_ok={result.is_ok}, result.is_error={result.is_error}")
    print(f"   _execution_state={node._execution_state}")
    assert node._execution_state == "error", f"Expected 'error', got {node._execution_state}"

    # Test break execution
    node._execution_state = None
    def break_action():
        return FlowableResult.break_(None, "中断")

    result = node._invoke_action(break_action)
    print(f"3. Break case:")
    print(f"   result.is_ok={result.is_ok}, result.is_break={result.is_break}")
    print(f"   _execution_state={node._execution_state}")
    assert node._execution_state == "break", f"Expected 'break', got {node._execution_state}"

    print("\nAll _execution_state tests PASSED!")


if __name__ == "__main__":
    test_invoke_action()


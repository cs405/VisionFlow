"""
GUI 执行测试：加载 changzhou.json，执行工作流，检查节点状态
模拟 _start_execution -> _finalize_execution_state 的完整链路
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, Qt

from gui.main_window import MainWindow
from core.node_base import VisionNodeData
from core.project import project_service


def main():
    app = QApplication(sys.argv)

    # 创建 MainWindow
    w = MainWindow()
    w.show()

    # 加载项目
    project_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "assets", "projects", "changzhou.json")
    project = project_service.load(project_path)
    if not project:
        print("FAILED to load project")
        return 1

    w._bind_project_diagram(project)

    # 等待 UI 稳定
    def check_after_load():
        wf = w._workflow
        if not wf:
            print("No workflow bound!")
            app.quit()
            return

        nodes = wf.get_all_nodes()
        print(f"Workflow has {len(nodes)} nodes")
        for node in nodes:
            if isinstance(node, VisionNodeData):
                print(f"  {node.name} [{type(node).__name__}]: _execution_state={node._execution_state}")

        # 执行工作流
        print("\nExecuting workflow...")
        w._start_execution(continuous=False)

        # 等待 1 秒让后台线程完成
        def check_after_execute():
            print(f"\nAfter execution (1s later):")
            print(f"Workflow state: {wf.state}")
            for node in nodes:
                if isinstance(node, VisionNodeData):
                    state = node._execution_state
                    print(f"  {node.name}: _execution_state={state}")

            # 手动调用 _finalize_execution_state
            print("\nManually calling _finalize_execution_state...")
            w._finalize_execution_state()

            # 检查 UI 状态
            editor = w._current_diagram_editor()
            if editor:
                print(f"\nNodeItem states after finalization:")
                for item in editor.scene.get_all_node_items():
                    nd = item.node_data
                    es = nd._execution_state if isinstance(nd, VisionNodeData) else 'N/A'
                    print(f"  {nd.name}: item_state={item._state}, data_execution_state={es}")

            app.quit()

        QTimer.singleShot(1500, check_after_execute)

    QTimer.singleShot(500, check_after_load)

    app.exec_()
    return 0


if __name__ == "__main__":
    sys.exit(main())

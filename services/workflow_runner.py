"""Workflow runner — decoupled execution lifecycle and threading.

Handles single-run and continuous-run execution on background threads.
Publishes events through the existing event system — UI components
subscribe to those events rather than depending on this module directly.
"""

import threading
import time
import traceback

from core.workflow import WorkflowEngine, WorkflowState
from core.events import EventType, event_system


class WorkflowRunner:
    """Manages workflow execution lifecycle on background threads.

    Decouples threading and loop logic from the UI layer.
    The UI listens to WorkflowEngine events (WORKFLOW_STARTED,
    NODE_COMPLETED, WORKFLOW_COMPLETED, etc.) to update itself.

    Usage:
        runner = WorkflowRunner()
        runner.bind(workflow)
        runner.start_once()        # single execution
        runner.start_run_all()     # iterate all source files (WPF "运行全部")
        runner.start_continuous()  # loop until stopped
        runner.stop()              # request stop
    """

    def __init__(self):
        self._workflow: WorkflowEngine | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._continuous = False

    # -- properties --

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_continuous(self) -> bool:
        return self._continuous

    # -- bind --

    def bind(self, workflow: WorkflowEngine):
        """Bind a workflow engine to this runner."""
        self._workflow = workflow

    # -- execution --

    def start_once(self):
        """Execute the workflow a single time on a background thread."""
        if not self._workflow or self.is_running:
            return
        self._continuous = False
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_once, daemon=True)
        self._thread.start()

    def start_run_all(self, file_paths: list[str], auto_switch: bool = True, interval: float = 1.0):
        """Execute workflow once per file — WPF "运行全部" (VisionDiagramDataBase.Start()).

        Ported from WPF:
          VisionDiagramDataBase.Start() → UseAllImage loop
          RunDiagramDataPresenter.StartAllCommand → manual file iteration

        Iterates through all source file paths, running the full workflow for each.
        Publishes FILE_ITERATION_NEXT event before each iteration so the UI can
        update the image display with the current file.

        Args:
            file_paths: list of source image file paths to iterate
            auto_switch: whether to update the source node's current file
            interval: delay (seconds) between iterations, WPF uses 1.0s
        """
        if not self._workflow or self.is_running:
            return
        self._continuous = False
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_all, args=(file_paths, auto_switch, interval),
            daemon=True,
        )
        self._thread.start()

    def start_continuous(self):
        """Execute the workflow in a continuous loop on a background thread.

        Each iteration calls workflow.start() which publishes
        WORKFLOW_STARTED → NODE_STARTED/COMPLETED/ERROR → WORKFLOW_COMPLETED.
        The loop continues until stop() is called or an error occurs.
        """
        if not self._workflow or self.is_running:
            return
        self._continuous = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_continuous, daemon=True)
        self._thread.start()

    def stop(self):
        """Request stop and wait briefly for the worker thread to finish."""
        self._stop_event.set()
        if self._workflow:
            self._workflow.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._continuous = False

    # -- internal --

    def _run_once(self):
        try:
            if not self._workflow:
                return
            result = self._workflow.start()
            if result.is_error:
                event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                     message=f"流程执行出错: {result.message}")
        except Exception:
            event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                 message=f"流程异常: {traceback.format_exc()}")

    def _run_all(self, file_paths: list[str], auto_switch: bool, interval: float):
        """WPF "运行全部" loop — iterate through all source files.

        Ported from WPF VisionDiagramDataBase.Start() (UseAllImage branch) +
        RunDiagramDataPresenter.StartAllCommand.

        Key WPF behaviors preserved:
          1. Check stop state before each iteration (CANCELLING → break)
          2. Check UseAllImage flag each iteration (can exit early mid-loop)
          3. Update display before each run (ResultImageSource = item.ToImageSource())
          4. If UseAutoSwitch → update SrcFilePath on source node
          5. Delay between iterations (WPF: Task.Delay(1000))
          6. Collect results per iteration
        """
        from core.node_base import SrcFilesVisionNodeData

        start_node = self._workflow.get_start_node_data() if self._workflow else None
        if not isinstance(start_node, SrcFilesVisionNodeData):
            # No source node with files → fall back to single run
            event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                 message="无法运行全部：起始节点不是图像源节点")
            return

        total = len(file_paths)
        for i, file_path in enumerate(file_paths):
            if self._stop_event.is_set():
                break
            if not start_node.use_all_image:
                break

            # WPF: ResultImageSource = item.ToImageSource()  — ALWAYS
            # WPF: if (UseAutoSwitch) SrcFilePath = item  — only when ON
            if auto_switch:
                start_node.src_file_path = file_path

            # Notify UI that we're starting a file iteration
            # Pass auto_switch so UI can decide whether to refresh the thumbnail panel
            event_system.publish(EventType.FILE_ITERATION_NEXT, sender=self,
                                 file_path=file_path, index=i, total=total,
                                 auto_switch=auto_switch)

            # Run the workflow for this file
            try:
                result = self._workflow.start()
                if result.is_error:
                    event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                         message=f"文件 [{i+1}/{total}] 执行出错: {result.message}")
            except Exception:
                event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                     message=f"文件 [{i+1}/{total}] 执行异常: {traceback.format_exc()}")

            # WPF: await Task.Delay(1000) — 1 second between iterations
            if self._stop_event.wait(interval):
                break

        event_system.publish(EventType.FILE_ITERATION_COMPLETED, sender=self,
                             total=total)

    def _run_continuous(self):
        try:
            while not self._stop_event.is_set():
                if not self._workflow:
                    break
                result = self._workflow.start()
                if result.is_error:
                    event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                         message=f"流程出错: {result.message}")
                    break
                if self._stop_event.wait(0.03):
                    break
        except Exception:
            event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                 message=f"流程异常: {traceback.format_exc()}")

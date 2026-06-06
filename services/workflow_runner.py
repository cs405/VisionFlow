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
        runner.start_once()       # single execution
        runner.start_continuous() # loop until stopped
        runner.stop()             # request stop
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
                # Small pause between iterations to avoid hogging the CPU
                if self._stop_event.wait(0.03):
                    break
        except Exception:
            event_system.publish(EventType.MESSAGE_ERROR, sender=self,
                                 message=f"流程异常: {traceback.format_exc()}")

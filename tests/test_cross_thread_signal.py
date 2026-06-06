"""Test whether pyqtSignal.emit() from threading.Thread reaches the main thread.

This is the CRITICAL test — if this fails, the entire cross-thread UI update
mechanism is broken and we need a different approach.

Run with: python test_cross_thread_signal.py
"""

import sys, os, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

app = QApplication(sys.argv)

class Receiver(QObject):
    sig = pyqtSignal(str)
    received = []

    def __init__(self):
        super().__init__()
        self.sig.connect(self._on_sig)

    def _on_sig(self, msg):
        tname = threading.current_thread().name
        self.received.append((msg, tname))
        print(f"  [_on_sig] msg={msg}, thread={tname}")

def emit_from_worker(rx, results):
    """Called from threading.Thread — not QThread!"""
    tname = threading.current_thread().name
    print(f"  [worker] thread={tname}, about to emit...")
    rx.sig.emit("hello-from-worker")
    print(f"  [worker] emit returned")
    # Give event loop time to process
    time.sleep(0.1)
    results.extend(rx.received)

# Create receiver on main thread
rx = Receiver()
main_thread = threading.current_thread().name
print(f"Main thread: {main_thread}")
print(f"Receiver thread: {rx.thread()}")

# Test 1: emit from main thread (should be synchronous)
print("\n--- Test 1: emit from main thread ---")
rx.sig.emit("hello-from-main")
print(f"  received: {rx.received}")
assert len(rx.received) == 1, f"Expected 1, got {len(rx.received)}"
assert rx.received[0][1] == main_thread, f"Expected main thread, got {rx.received[0][1]}"
rx.received.clear()

# Test 2: emit from threading.Thread (should be queued)
print("\n--- Test 2: emit from threading.Thread ---")
results = []
worker = threading.Thread(target=emit_from_worker, args=(rx, results),
                          name="worker-thread", daemon=True)
worker.start()
worker.join(timeout=2)

# Process events so queued signal fires
app.processEvents()

print(f"  received after processEvents: {rx.received}")
if len(rx.received) > 0:
    thread_name = rx.received[0][1]
    is_main = thread_name == main_thread
    print(f"  slot ran on thread: {thread_name} (is_main={is_main})")
    if is_main:
        print("  SUCCESS: pyqtSignal correctly queued to main thread!")
    else:
        print("  FAIL: slot ran on wrong thread!")
else:
    print("  FAIL: signal was NEVER delivered to slot!")
    print("  → pyqtSignal.emit() from threading.Thread does NOT queue to main thread")
    print("  → Need alternative: QEvent, invokeMethod, or QThread worker")

# Shutdown
QTimer.singleShot(0, app.quit)
app.processEvents()

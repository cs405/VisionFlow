import sys
import os
import threading
import traceback
import ctypes
from datetime import datetime

CRASH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crash_logs")

def _write_crash(tag, info):
    os.makedirs(CRASH_DIR, exist_ok=True)
    path = os.path.join(CRASH_DIR, f"crash_{datetime.now():%Y%m%d_%H%M%S_%f}.log")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"[{tag}] {datetime.now()}\n{info}\n")

def install():
    _orig_excepthook = sys.excepthook

    def _py_hook(exc_type, exc_val, exc_tb):
        _write_crash("Python", "".join(traceback.format_exception(exc_type, exc_val, exc_tb)))
        _orig_excepthook(exc_type, exc_val, exc_tb)

    sys.excepthook = _py_hook

    if hasattr(threading, "excepthook"):
        def _thread_hook(args):
            _write_crash("Thread", "".join(traceback.format_exception(
                args.exc_type, args.exc_value, args.exc_traceback)))
        threading.excepthook = _thread_hook

    try:
        from PyQt5.QtCore import qInstallMessageHandler, QtMsgType

        def _qt_hook(msg_type, context, msg):
            if msg_type == QtMsgType.QtFatalMsg:
                _write_crash("QtFatal", f"message={msg}\nfile={context.file}:{context.line}\nfunction={context.function}")
            elif msg_type == QtMsgType.QtCriticalMsg:
                _write_crash("QtCritical", f"message={msg}\nfile={context.file}:{context.line}\nfunction={context.function}")

        qInstallMessageHandler(_qt_hook)
    except ImportError:
        pass

    if sys.platform == "win32":
        try:
            _seh_cb = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(
                lambda exc_ptr: (_write_crash("SEH", f"unhandled win32 exception at {exc_ptr:#x}"), 0)[1]
            )
            ctypes.windll.kernel32.SetUnhandledExceptionFilter(_seh_cb)
        except Exception:
            pass

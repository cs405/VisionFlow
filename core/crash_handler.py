import sys
import os
import signal
import threading
import traceback
import ctypes
import faulthandler
from datetime import datetime

CRASH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crash_logs")
os.makedirs(CRASH_DIR, exist_ok=True)

_CALLBACK_REFS = []  # 防止 ctypes 回调被 GC 导致野指针


def _log_path(tag):
    return os.path.join(CRASH_DIR, f"crash_{tag}_{datetime.now():%Y%m%d_%H%M%S_%f}.log")


def _write_crash(tag, info):
    path = _log_path(tag)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"[{tag}] {datetime.now()}\n{info}\n")
    except Exception:
        pass
    return path


def _stderr_safe(msg):
    try:
        sys.stderr.write(msg)
        sys.stderr.flush()
    except Exception:
        pass


# ===========================================================================
# 1. faulthandler —— C 层崩溃日志写到 stderr（不创建文件）
# ===========================================================================
def _install_faulthandler():
    try:
        faulthandler.enable(all_threads=True)
    except Exception as e:
        _stderr_safe(f"[crash_handler] faulthandler 启用失败: {e}\n")


# ===========================================================================
# 2. sys.excepthook —— 主线程 Python 异常
# ===========================================================================
def _install_python_hook():
    _orig = sys.excepthook

    def _py_hook(exc_type, exc_val, exc_tb):
        tb_text = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
        path = _write_crash("Python", tb_text)
        _stderr_safe(f"[crash_handler] 崩溃日志 -> {path}\n")
        _orig(exc_type, exc_val, exc_tb)

    sys.excepthook = _py_hook
    _CALLBACK_REFS.append(_py_hook)


# ===========================================================================
# 3. threading.excepthook —— threading.Thread 工作线程异常
# ===========================================================================
def _install_thread_hook():
    if not hasattr(threading, "excepthook"):
        return
    _orig = threading.excepthook

    def _thread_hook(args):
        tb_text = "".join(traceback.format_exception(
            args.exc_type, args.exc_value, args.exc_traceback))
        path = _write_crash("Thread", tb_text)
        _stderr_safe(f"[crash_handler] 线程崩溃日志 -> {path}\n")
        if _orig:
            _orig(args)

    threading.excepthook = _thread_hook
    _CALLBACK_REFS.append(_thread_hook)


# ===========================================================================
# 4. QThread.start() 修补
# ===========================================================================
def _install_qthread_hook():
    try:
        from PyQt5.QtCore import QThread
    except ImportError:
        return

    _orig_start = QThread.start

    def _patched_start(self, *args, **kwargs):
        orig_run = getattr(self, "run", None)
        if orig_run is None or getattr(orig_run, "__func__", None) is QThread.run:
            orig_run = QThread.run.__get__(self, type(self))

        def _wrapped_run():
            try:
                orig_run()
            except Exception:
                path = _write_crash("QThread", traceback.format_exc())
                _stderr_safe(f"[crash_handler] QThread崩溃日志 -> {path}\n")
                raise

        self.run = _wrapped_run
        _orig_start(self, *args, **kwargs)

    QThread.start = _patched_start
    _CALLBACK_REFS.append(_patched_start)


# ===========================================================================
# 5. Qt 消息处理 —— QtFatal / QtCritical
# ===========================================================================
def _install_qt_hook():
    try:
        from PyQt5.QtCore import qInstallMessageHandler, QtMsgType
    except ImportError:
        return

    def _qt_hook(msg_type, context, msg):
        if msg_type in (QtMsgType.QtFatalMsg, QtMsgType.QtCriticalMsg):
            tag = "QtFatal" if msg_type == QtMsgType.QtFatalMsg else "QtCritical"
            _write_crash(tag, f"message={msg}\nfile={context.file}:{context.line}\nfunction={context.function}")

    qInstallMessageHandler(_qt_hook)
    _CALLBACK_REFS.append(_qt_hook)


# ===========================================================================
# 6. sys.unraisablehook —— GC 回收时的异常
# ===========================================================================
def _install_unraisable_hook():
    _orig = sys.unraisablehook

    def _hook(args):
        msg = f"unraisable exception in {args.object!r}\n"
        msg += "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        _write_crash("Unraisable", msg)
        if _orig:
            _orig(args)

    sys.unraisablehook = _hook
    _CALLBACK_REFS.append(_hook)


# ===========================================================================
# 7. Windows：VEH 只在崩溃时创建日志文件 + 抑制 WER 弹窗
# ===========================================================================
def _install_windows_handlers():
    if sys.platform != "win32":
        return

    kernel32 = ctypes.windll.kernel32

    # 抑制 "程序已停止工作" 弹窗
    SEM_NOGPFAULTERRORBOX = 0x0002
    try:
        kernel32.SetErrorMode(kernel32.SetErrorMode(0) | SEM_NOGPFAULTERRORBOX)
    except Exception:
        pass

    EXCEPTION_NAMES = {
        0xC0000005: "ACCESS_VIOLATION",
        0xC0000094: "INT_DIVIDE_BY_ZERO",
        0xC00000FD: "STACK_OVERFLOW",
        0xC000001D: "ILLEGAL_INSTRUCTION",
        0xC0000008: "INVALID_HANDLE",
        0x80000003: "BREAKPOINT",
        0x80000004: "SINGLE_STEP",
    }
    EXCEPTION_CONTINUE_SEARCH = 0

    # ---- VEH（链表式，不会被覆盖）----
    _veh_cb_type = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)

    @_veh_cb_type
    def _veh_handler(exc_info_ptr):
        code = 0
        addr = 0
        try:
            p = ctypes.cast(exc_info_ptr, ctypes.POINTER(ctypes.c_void_p))
            if p:
                record_ptr = p[0]
                if record_ptr:
                    p32 = ctypes.cast(record_ptr, ctypes.POINTER(ctypes.c_uint32))
                    code = p32[0]
                    pv = ctypes.cast(record_ptr, ctypes.POINTER(ctypes.c_void_p))
                    addr = ctypes.cast(pv[2], ctypes.c_void_p).value or 0
        except Exception:
            pass

        exc_name = EXCEPTION_NAMES.get(code, f"0x{code:08X}")
        path = _log_path("VEH")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"[VEH] {datetime.now()}\n")
                f.write(f"exception_code=0x{code:08X} ({exc_name})\n")
                f.write(f"exception_address=0x{addr:016X}\n")
                try:
                    f.write("\nPython traceback:\n")
                    traceback.print_stack(file=f)
                except Exception:
                    f.write("(unable to capture)\n")
        except Exception:
            pass

        return EXCEPTION_CONTINUE_SEARCH

    try:
        kernel32.AddVectoredExceptionHandler(1, _veh_handler)
    except Exception:
        pass
    _CALLBACK_REFS.append(_veh_handler)

    # ---- SEH 兜底 ----
    _seh_cb_type = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)

    @_seh_cb_type
    def _seh_handler(exc_ptr):
        try:
            path = _log_path("SEH")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"[SEH] {datetime.now()}\n")
                f.write(f"exception_info=0x{exc_ptr:016X}\n")
                try:
                    traceback.print_stack(file=f)
                except Exception:
                    f.write("(unable to capture)\n")
        except Exception:
            pass
        return 0

    try:
        kernel32.SetUnhandledExceptionFilter(_seh_handler)
    except Exception:
        pass
    _CALLBACK_REFS.append(_seh_handler)

    # ---- CRT invalid parameter / purecall ----
    for dll_name in ("ucrtbase.dll", "msvcrt.dll"):
        try:
            crt = ctypes.CDLL(dll_name)

            CRT_INV = ctypes.CFUNCTYPE(None, ctypes.c_wchar_p, ctypes.c_void_p,
                                        ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_uint64)

            @CRT_INV
            def _crt_invalid(expr, func, file, line, _reserved):
                try:
                    _write_crash("CRT_invalid",
                                 f"expr={expr}\nfunc={func}\nfile={file}:{line}")
                except Exception:
                    pass

            crt._set_invalid_parameter_handler(_crt_invalid)
            _CALLBACK_REFS.append(_crt_invalid)

            PURE = ctypes.CFUNCTYPE(None)

            @PURE
            def _pure_call():
                try:
                    _write_crash("CRT_purecall", "pure virtual function call")
                except Exception:
                    pass

            crt._set_purecall_handler(_pure_call)
            _CALLBACK_REFS.append(_pure_call)
            break
        except Exception:
            continue


# ===========================================================================
# 8. Unix 信号
# ===========================================================================
def _install_signal_handlers():
    if not hasattr(signal, "SIGSEGV"):
        return

    def _make_handler(sig_name):
        def handler(signum, frame):
            try:
                tb = "".join(traceback.format_stack(frame)) if frame else "(no frame)"
                _write_crash(f"Signal_{sig_name}", f"signal={signum}\n{tb}")
            except Exception:
                pass
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)
        return handler

    for sig in ("SIGSEGV", "SIGABRT", "SIGFPE", "SIGBUS"):
        sig_num = getattr(signal, sig, None)
        if sig_num is not None:
            try:
                signal.signal(sig_num, _make_handler(sig))
            except (ValueError, OSError):
                pass


# ===========================================================================
def install():
    """安装全局崩溃日志钩子。在 main() 中最先调用。"""
    _install_faulthandler()        # C 层崩溃 → stderr（不创建文件）
    _install_python_hook()         # Python 主线程
    _install_thread_hook()         # Python 子线程
    _install_qthread_hook()        # Qt 工作线程
    _install_qt_hook()             # Qt 内部致命错误
    _install_windows_handlers()    # VEH+SEH：只在崩溃时创建文件 + 抑制弹窗
    _install_signal_handlers()     # Unix 信号
    _install_unraisable_hook()     # GC 异常

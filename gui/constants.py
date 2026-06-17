"""应用级常量与配置文件的加载/保存。

存放 WM_* 消息常量、边框宽度、默认布局尺寸以及 app_config.json 的读写。
"""

import json
import os

# ── Windows 无边框窗口消息常量 ──────────────────────────

WM_NCHITTEST = 0x0084
WM_NCCALCSIZE = 0x0083

HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
HTCAPTION = 2

BORDER = 8

# ── UI 布局默认尺寸 ──────────────────────────────────────

UI_PROFILE_VERSION = 1
DEFAULT_WINDOW_WIDTH = 1460
DEFAULT_WINDOW_HEIGHT = 900
DEFAULT_LEFT_WIDTH = 280
DEFAULT_RIGHT_WIDTH = 850
DEFAULT_CENTER_HEIGHT = 800
DEFAULT_BOTTOM_HEIGHT = 180
DEFAULT_RESOURCE_HEIGHT = 175
DEFAULT_CAPTION_HEIGHT = 85

# ── 配置文件路径与读写 ──────────────────────────────────

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))


def app_config_path() -> str:
    """返回项目根目录下 app_config.json 的绝对路径"""
    return os.path.join(_PROJECT_ROOT, "app_config.json")


def load_app_config() -> dict:
    """加载 app_config.json 并返回字典（失败时返回 {}）"""
    try:
        with open(app_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_app_config(data: dict) -> None:
    """将字典写入 app_config.json"""
    with open(app_config_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

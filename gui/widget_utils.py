"""Qt 控件遍历工具"""

from PyQt5.QtWidgets import QWidget


def find_child_by_tip(parent, tip: str):
    """通过 toolTip 文本递归查找可见的子控件，未找到返回 None"""
    try:
        for w in parent.findChildren(QWidget):
            try:
                if w.isVisible() and hasattr(w, 'toolTip') and w.toolTip() == tip:
                    return w
            except Exception:
                continue
    except Exception:
        pass
    return None

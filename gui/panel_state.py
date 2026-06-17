"""面板状态管理器 — 通过 QSettings 持久化面板宽度、高度与可见性"""

from PyQt5.QtCore import QSettings


class PanelState:
    """惰性创建 QSettings（确保在 QApplication 之后），提供 get_i/set_i/get_b/set_b 便捷方法"""

    GRP = "PanelState"

    def __init__(self):
        self._settings = None

    @property
    def s(self) -> QSettings:
        if self._settings is None:
            self._settings = QSettings()
        return self._settings

    def _k(self, key: str) -> str:
        return f"{self.GRP}/{key}"

    def get_i(self, key: str, default: int = 0) -> int:
        return int(self.s.value(self._k(key), default) or default)

    def set_i(self, key: str, value: int) -> None:
        self.s.setValue(self._k(key), value)

    def get_b(self, key: str, default: bool = True) -> bool:
        value = self.s.value(self._k(key), default)
        return str(value).lower() == "true" if isinstance(value, str) else bool(value) if value is not None else default

    def set_b(self, key: str, value: bool) -> None:
        self.s.setValue(self._k(key), "true" if value else "false")


# 模块级单例 — 全局唯一的面板状态实例
panel_state = PanelState()

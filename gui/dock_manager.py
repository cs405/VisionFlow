"""Dock manager - QDockWidget-based panel docking with float/auto-hide.

Ported from H.Controls.Dock + H.Controls.GridSplitterBox.

Provides:
  - QDockWidget-based docking (float/dock/tabify)
  - Auto-hide when panel is narrow (WPF GridSplitterBox behavior)
  - QSettings persistence for positions and sizes
  - Panel show/hide with animation-like state transitions
"""

from PyQt5.QtWidgets import QDockWidget, QWidget, QMainWindow, QTabWidget
from PyQt5.QtCore import Qt, QSettings, pyqtSignal, QObject


class DockPanelInfo:
    """Metadata for a dockable panel."""
    def __init__(self, key: str, title: str, widget: QWidget,
                 area: Qt.DockWidgetArea = Qt.LeftDockWidgetArea,
                 default_visible: bool = True,
                 default_width: int = 260,
                 allow_float: bool = True,
                 allow_close: bool = False):
        self.key = key
        self.title = title
        self.widget = widget
        self.area = area
        self.default_visible = default_visible
        self.default_width = default_width
        self.allow_float = allow_float
        self.allow_close = allow_close
        self.dock: QDockWidget | None = None


class DockManager(QObject):
    """Central manager for QDockWidget-based panel docking.

    Usage:
        dm = DockManager(main_window)
        dm.register("toolbox", "工具箱", toolbox_widget, Qt.LeftDockWidgetArea)
        dm.register("property", "属性", property_widget, Qt.RightDockWidgetArea)
        dm.restore_all()
    """

    panel_toggled = pyqtSignal(str, bool)  # key, visible
    layout_changed = pyqtSignal()

    SETTINGS_GROUP = "DockManager"

    def __init__(self, main_window: QMainWindow):
        super().__init__(main_window)
        self._mw = main_window
        self._settings = QSettings()
        self._panels: dict[str, DockPanelInfo] = {}

    # ── Registration ──────────────────────────────────────────────────

    def register(self, key: str, title: str, widget: QWidget,
                 area: Qt.DockWidgetArea = Qt.LeftDockWidgetArea,
                 default_visible: bool = True,
                 default_width: int = 260,
                 allow_float: bool = True,
                 allow_close: bool = False) -> QDockWidget:
        """Register a panel and create its QDockWidget.

        Returns the QDockWidget for further configuration.
        """
        info = DockPanelInfo(key, title, widget, area,
                            default_visible, default_width,
                            allow_float, allow_close)

        dock = QDockWidget(title, self._mw)
        dock.setObjectName(f"dock_{key}")
        dock.setWidget(widget)
        dock.setAllowedAreas(Qt.AllDockWidgetAreas if allow_float else area)
        dock.setFeatures(self._dock_features(info))

        # Restore persisted state
        self._restore_dock_state(info, dock)

        info.dock = dock
        self._panels[key] = info

        # Track visibility changes
        dock.visibilityChanged.connect(lambda v: self._on_visibility_changed(key, v))

        return dock

    def _dock_features(self, info: DockPanelInfo):
        from PyQt5.QtWidgets import QDockWidget as D
        f = D.DockWidgetClosable if info.allow_close else D.NoDockWidgetFeatures
        if info.allow_float:
            f |= D.DockWidgetFloatable | D.DockWidgetMovable
        return f

    # ── Add to main window ────────────────────────────────────────────

    def attach(self, key: str, area: Qt.DockWidgetArea = None):
        """Add a registered panel's dock widget to the main window."""
        info = self._panels.get(key)
        if info is None or info.dock is None:
            return
        area = area or info.area
        self._mw.addDockWidget(area, info.dock)

    def attach_all(self):
        """Add all registered panels to the main window."""
        for key in self._panels:
            self.attach(key)

    # ── Visibility ────────────────────────────────────────────────────

    def show(self, key: str):
        info = self._panels.get(key)
        if info and info.dock:
            info.dock.show()
            self._save_visibility(key, True)

    def hide(self, key: str):
        info = self._panels.get(key)
        if info and info.dock:
            info.dock.hide()
            self._save_visibility(key, False)

    def toggle(self, key: str):
        info = self._panels.get(key)
        if info and info.dock:
            if info.dock.isVisible():
                self.hide(key)
            else:
                self.show(key)

    def is_visible(self, key: str) -> bool:
        info = self._panels.get(key)
        return info.dock.isVisible() if (info and info.dock) else False

    def _on_visibility_changed(self, key: str, visible: bool):
        self._save_visibility(key, visible)
        self.panel_toggled.emit(key, visible)
        self.layout_changed.emit()

    # ── Tabify ────────────────────────────────────────────────────────

    def tabify(self, key1: str, key2: str):
        """Stack two panels as tabs."""
        d1 = self._panels.get(key1)
        d2 = self._panels.get(key2)
        if d1 and d2 and d1.dock and d2.dock:
            self._mw.tabifyDockWidget(d1.dock, d2.dock)

    # ── Persistence ───────────────────────────────────────────────────

    def _state_key(self, key: str, suffix: str) -> str:
        return f"{self.SETTINGS_GROUP}/{key}/{suffix}"

    def _save_visibility(self, key: str, visible: bool):
        self._settings.setValue(self._state_key(key, "visible"), visible)
        self._settings.sync()

    def _restore_dock_state(self, info: DockPanelInfo, dock: QDockWidget):
        vis = self._settings.value(self._state_key(info.key, "visible"))
        if vis is not None:
            v = str(vis).lower() == "true" if isinstance(vis, str) else bool(vis)
            dock.setVisible(v)
        else:
            dock.setVisible(info.default_visible)

    def save_all(self):
        """Persist visibility of all panels."""
        for key, info in self._panels.items():
            if info.dock:
                self._save_visibility(key, info.dock.isVisible())

    def restore_state(self):
        """Restore the main window's dock state from QSettings."""
        state = self._settings.value(f"{self.SETTINGS_GROUP}/windowState")
        if state:
            self._mw.restoreState(state)

    def save_state(self):
        """Save the main window's dock state to QSettings."""
        self._settings.setValue(f"{self.SETTINGS_GROUP}/windowState",
                               self._mw.saveState())
        self._settings.sync()

    # ── Access ────────────────────────────────────────────────────────

    def get_dock(self, key: str) -> QDockWidget | None:
        info = self._panels.get(key)
        return info.dock if info else None

    def keys(self) -> list[str]:
        return list(self._panels.keys())

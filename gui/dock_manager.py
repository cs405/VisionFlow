"""Dock manager - unified panel visibility/docking/size management.

Ported from H.Controls.Dock + H.Controls.GridSplitterBox.
Provides:
  - Panel show/hide with collapse animation
  - Size persistence via QSettings
  - Left/right/bottom panel state management
  - Signal-based panel visibility coordination

The main_window.py CollapsiblePanel widget handles individual panel UI.
This manager coordinates all panels globally.
"""

from PyQt5.QtCore import QObject, QSettings, pyqtSignal


class DockPanelInfo:
    """Metadata for a dockable panel."""
    def __init__(self, name: str, key: str, default_visible: bool = True,
                 default_width: int = 260, min_width: int = 200,
                 side: str = "left"):
        self.name = name
        self.key = key
        self.default_visible = default_visible
        self.default_width = default_width
        self.min_width = min_width
        self.side = side  # "left", "right", "bottom"
        self.visible = default_visible
        self.width = default_width
        self.widget = None


class DockManager(QObject):
    """Central manager for panel docking state.

    Panels tracked:
      - left_toolbox  (toolbox + log tabs)
      - right_property (property + result tabs)
      - bottom_resource (flow resource panel)
    """

    panel_toggled = pyqtSignal(str, bool)  # panel_key, visible
    layout_changed = pyqtSignal()

    SETTINGS_GROUP = "DockManager"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings()
        self._panels: dict[str, DockPanelInfo] = {}
        self._main_window = parent

    def register_panel(self, name: str, key: str, widget,
                       side: str = "left", default_visible: bool = True,
                       default_width: int = 260, min_width: int = 200):
        """Register a dockable panel."""
        info = DockPanelInfo(name, key, default_visible, default_width,
                            min_width, side)
        info.widget = widget
        self._panels[key] = info
        self._restore_panel_state(key)

    def _state_key(self, panel_key: str, suffix: str) -> str:
        return f"{self.SETTINGS_GROUP}/{panel_key}/{suffix}"

    def _restore_panel_state(self, key: str):
        """Load panel state from QSettings."""
        info = self._panels.get(key)
        if info is None:
            return
        visible_val = self._settings.value(self._state_key(key, "visible"))
        if visible_val is not None:
            info.visible = str(visible_val).lower() == "true" if isinstance(visible_val, str) else bool(visible_val)
        width_val = self._settings.value(self._state_key(key, "width"))
        if width_val is not None:
            info.width = int(width_val)

        if info.widget:
            info.widget.setVisible(info.visible)
            if hasattr(info.widget, 'setFixedWidth') and info.side != "bottom":
                info.widget.setFixedWidth(info.width)

    def _save_panel_state(self, key: str):
        """Save panel state to QSettings."""
        info = self._panels.get(key)
        if info is None:
            return
        self._settings.setValue(self._state_key(key, "visible"), info.visible)
        self._settings.setValue(self._state_key(key, "width"), info.width)
        self._settings.sync()

    def toggle_panel(self, key: str):
        """Toggle panel visibility."""
        info = self._panels.get(key)
        if info is None or info.widget is None:
            return
        info.visible = not info.visible
        info.widget.setVisible(info.visible)
        self._save_panel_state(key)
        self.panel_toggled.emit(key, info.visible)
        self.layout_changed.emit()

    def show_panel(self, key: str):
        """Show a panel."""
        info = self._panels.get(key)
        if info is None or info.widget is None:
            return
        info.visible = True
        info.widget.setVisible(True)
        self._save_panel_state(key)
        self.panel_toggled.emit(key, True)
        self.layout_changed.emit()

    def hide_panel(self, key: str):
        """Hide a panel."""
        info = self._panels.get(key)
        if info is None or info.widget is None:
            return
        info.visible = False
        info.widget.setVisible(False)
        self._save_panel_state(key)
        self.panel_toggled.emit(key, False)
        self.layout_changed.emit()

    def is_visible(self, key: str) -> bool:
        info = self._panels.get(key)
        return info.visible if info else False

    def set_panel_width(self, key: str, width: int):
        """Set and persist panel width."""
        info = self._panels.get(key)
        if info is None:
            return
        info.width = max(info.min_width, width)
        if info.widget and hasattr(info.widget, 'setFixedWidth'):
            info.widget.setFixedWidth(info.width)
        self._save_panel_state(key)

    def save_all(self):
        """Persist all panel states."""
        for key in self._panels:
            self._save_panel_state(key)

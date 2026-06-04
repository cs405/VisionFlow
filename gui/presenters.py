"""Presenter template system — WPF DataTemplate + ContentPresenter 1:1 port.

Ported from WPF pattern:
  DataTemplate DataType="{x:Type SomeType}" → specific Presenter view
  ContentPresenter Content="{Binding SomeObject}" → auto-resolves type → shows view

Provides:
  - PresenterRegistry: type → QWidget factory mapping (like DataTemplate)
  - ContentPresenter: QWidget that auto-resolves content type and embeds Presenter
  - Built-in presenters: PropertyPresenter, HelpPresenter, ROIPresenter, ResultPresenter
"""

from typing import Any, Callable, Type

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel


# ═══════════════════════════════════════════════════════════════════════════
# PresenterRegistry
# ═══════════════════════════════════════════════════════════════════════════

class PresenterRegistry:
    """Type-based view factory registry (WPF DataTemplate equivalent).

    Maps Python types to QWidget factory functions. When a ContentPresenter
    receives a data object, it looks up its type here and creates the matching view.

    Usage:
        registry = PresenterRegistry()
        registry.register(VisionNodeData, lambda parent: PropertyPanel(parent, readonly=True))
        registry.register(ROIBase, lambda parent: RoiEditWidget(parent))
    """

    def __init__(self):
        self._factories: dict[Type, Callable[[QWidget], QWidget]] = {}
        self._fallback: Callable[[Any, QWidget], QWidget] | None = None

    def register(self, data_type: Type, factory: Callable[[QWidget], QWidget]):
        """Register a presenter factory for a specific data type.

        Args:
            data_type: The Python class to match (checked via isinstance).
            factory: callable(parent: QWidget) → QWidget presenter.
        """
        self._factories[data_type] = factory

    def set_fallback(self, factory: Callable[[Any, QWidget], QWidget]):
        """Set fallback factory for unmatched types."""
        self._fallback = factory

    def resolve(self, data: Any) -> Callable[[QWidget], QWidget] | None:
        """Find the best matching factory for a data object.

        Checks registered types in order, using isinstance() for matching.
        Returns None if no match and no fallback.
        """
        for data_type, factory in self._factories.items():
            if isinstance(data, data_type):
                return factory
        return self._fallback

    def create(self, data: Any, parent: QWidget = None) -> QWidget | None:
        """Resolve and create the presenter for a data object."""
        factory = self.resolve(data)
        if factory:
            try:
                return factory(parent)
            except TypeError:
                # Fallback factory takes (data, parent) signature
                return factory(data, parent)
        return None


# Global singleton
presenter_registry = PresenterRegistry()


# ═══════════════════════════════════════════════════════════════════════════
# ContentPresenter widget
# ═══════════════════════════════════════════════════════════════════════════

class ContentPresenter(QWidget):
    """WPF ContentPresenter equivalent — auto-resolves content type to view.

    Usage:
        presenter = ContentPresenter(parent)
        presenter.set_content(some_node)  # auto-creates matching PropertyPanel
        presenter.set_content(None)       # clears the view
    """

    def __init__(self, parent=None, registry: PresenterRegistry = None):
        super().__init__(parent)
        self._registry = registry or presenter_registry
        self._content: Any = None
        self._presenter: QWidget | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

    def set_content(self, data: Any):
        """Set the content object and auto-resolve/create the matching presenter."""
        # Remove previous presenter
        if self._presenter:
            self.layout().removeWidget(self._presenter)
            self._presenter.deleteLater()
            self._presenter = None

        self._content = data
        if data is None:
            return

        widget = self._registry.create(data, parent=self)
        if widget:
            self._presenter = widget
            self.layout().addWidget(widget)

    @property
    def content(self) -> Any:
        return self._content

    @property
    def presenter(self) -> QWidget | None:
        return self._presenter


# ═══════════════════════════════════════════════════════════════════════════
# Built-in fallback presenter
# ═══════════════════════════════════════════════════════════════════════════

class DefaultTextPresenter(QWidget):
    """Simple text presenter that shows obj.__repr__() as a label."""

    def __init__(self, data: Any, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        label = QLabel(str(data) if data else "(无数据)")
        label.setWordWrap(True)
        label.setStyleSheet("color: #dcdcdc; font-size: 12px; background: transparent;")
        layout.addWidget(label)
        layout.addStretch()


# Register fallback
presenter_registry.set_fallback(lambda data, parent: DefaultTextPresenter(data, parent))


# ═══════════════════════════════════════════════════════════════════════════
# Built-in presenters for common VisionMaster types
# ═══════════════════════════════════════════════════════════════════════════

def _create_property_presenter(parent):
    """Create a read-only PropertyPanel for the module results tab."""
    from gui.property_panel import PropertyPanel
    from core.node_base import PropertyGroupNames
    return PropertyPanel(parent, group_filter=[PropertyGroupNames.RESULT_PARAMETERS], readonly=True)


def _create_help_presenter(parent):
    """Create a help text browser."""
    from PyQt5.QtWidgets import QTextBrowser
    browser = QTextBrowser(parent)
    browser.setOpenExternalLinks(True)
    browser.setStyleSheet("""
        QTextBrowser {
            background: #252526; color: #dcdcdc; border: none;
            font-size: 12px; padding: 8px;
        }
    """)
    return browser


def _create_roi_presenter(parent):
    """Create a simple ROI info label."""
    from PyQt5.QtWidgets import QLabel
    from PyQt5.QtCore import Qt as QtCore
    label = QLabel("ROI 编辑器", parent)
    label.setStyleSheet("color: #dcdcdc; padding: 8px; background: transparent;")
    label.setAlignment(QtCore.AlignCenter)
    return label


# Register known types
def _register_builtins():
    from core.node_base import VisionNodeData, ROINodeData, ROIBase, ConditionNodeData
    presenter_registry.register(VisionNodeData, _create_property_presenter)
    presenter_registry.register(ROIBase, _create_roi_presenter)
    # ConditionNodeData uses PropertyPanel too (via VisionNodeData match)


# Auto-register on import
_register_builtins()

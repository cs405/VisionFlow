"""Main window stub - will be fully implemented in P2."""


class MainWindow:
    """Stub main window. Full implementation in P2.

    Ported from H.App.VisionMaster.OpenCV/MainWindow.xaml(.cs)
    and H.Windows.Main/MainWindow.
    """

    def __init__(self):
        self._window = None
        self._setup()

    def _setup(self):
        try:
            from PyQt5.QtWidgets import QMainWindow, QLabel
            from PyQt5.QtCore import Qt

            self._window = QMainWindow()
            self._window.setWindowTitle("VisionFlow - 视觉流程编辑器")
            self._window.resize(1400, 900)
            self._window.setMinimumSize(800, 600)

            # Placeholder label
            label = QLabel("VisionFlow\n视觉流程编辑器\n\nP0 核心框架移植完成\n即将开始 P1 界面移植...")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 20px; color: #888;")
            self._window.setCentralWidget(label)

        except ImportError:
            self._window = None

    def show(self):
        if self._window:
            self._window.show()

    def open_project(self, file_path: str):
        """Open a project file. Will be implemented in P4."""
        pass

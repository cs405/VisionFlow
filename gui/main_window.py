import os
import cv2
import ctypes
from PyQt5.QtCore import Qt, QEvent, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (QMainWindow, QHBoxLayout, QVBoxLayout, QWidget,
                             QLabel, QMenuBar, QFrame, QPushButton, QSplitter,
                             QTabWidget, QMessageBox, QTabBar, QFileDialog,
                             QFormLayout, QLineEdit, QDialogButtonBox, QDialog,
                             QInputDialog, QApplication, QGraphicsView, QSystemTrayIcon)
from core.node_vision import VisionNodeData
from core.node_selectable import SrcFilesVisionNodeData
from core.events import event_system, EventType
from core.project import project_service, DiagramData
from core.workflow import DiagramFlowableMode
from gui.theme import (theme_manager, cmd_btn_qss, tab_qss,
                       vsep, connect_theme, ThemePickerDialog)
from gui.font_icons import FontIcons, FontIconButton, FontIconToggleButton
from gui.help_panel import HelpPanel
from gui.caption_bar import CaptionBar
from gui.result_panel import ResultPanel
from gui.constants import load_app_config
from gui.toolbox_panel import ToolboxPanel
from gui.guide_overlay import GuideOverlay
from gui.property_panel import PropertyPanel
from gui.image_viewer import ImageViewerPanel
from gui.settings_dialog import SettingsDialog
from gui.widget_utils import find_child_by_tip
from gui.node_editor.node_item import NodeState
from gui.node_property_dialog import open_node_dialog
from gui.node_editor.scene import _make_checker_brush
from gui.diagram_tab_header import DiagramTabHeader
from gui.flow_resource_panel import FlowResourcePanel
from gui.template_dialog import TemplateManagerDialog
from gui.widgets.grid_splitter_box import GridSplitterBox
from gui.widgets.inline_status_strip import InlineStatusStrip
from gui.node_editor.editor_widget import DiagramEditorWidget
from services.workflow_runner import WorkflowRunner



class MainWindow(QMainWindow):
    _image_for_display = pyqtSignal(object)  # 跨线程安全：后台线程→主线程显示图像

    def __init__(self, ctx=None):
        super().__init__()
        self._ctx = ctx                                          # 应用上下文，包含所有服务
        self.screen_width = 1920                                 # 屏幕窗口宽度
        self.screen_height = 1080                                # 屏幕窗口高度
        self._caption_bar = None                                 # 自定义标题栏
        self._selected_node = None                               # 选中的节点
        self._workflow = None                                    # 当前工作流引擎，初始为None
        self._wf_runner = WorkflowRunner()                       # 工作流运行器
        self._continuous_mode = False                            # 是否处于连续运行模式
        self._msg_lbl = QLabel("就绪")                            # 创建消息标签
        self._diagram_editor: DiagramEditorWidget | None = None  # 流程图编辑器控件
        self._diagram_pages: dict[str, QWidget] = {}             # 流程图页面缓存字典
        self._diagram_headers: dict[str, DiagramTabHeader] = {}  # 流程图标签页头部组件缓存字典
        self._cmd_btn = cmd_btn_qss()                            # 命令按钮样式表
        self._tab_style = tab_qss()                              # 标签页样式表
        self._setup_window()                                     # 主窗口
        self._setup_caption_bar()                                # 设置标题栏
        self._setup_main_surface()                               # 设置主界面
        self._setup_status_bar()                                 # 设置状态栏
        self._wire_signals()                                     # 连接信号
        self._live_preview_timer = QTimer(self)                  # 实时预览定时器（右侧图像显示）
        self._live_preview_timer.setInterval(33)                 # 设置定时器间隔为33毫秒（约30 FPS）
        self._live_preview_timer.timeout.connect(self._tick_live_preview)  # 连接定时器超时信号到实时预览更新方法
        self._image_for_display.connect(self._on_image_for_display)       # 后台线程→主线程图像显示
        self._connect_events()                                   # 连接事件
        self._on_new_project()                                   # 创建新项目，进入编辑状态

    def _setup_window(self):
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)  # 关闭窗口外边框
        self.resize(self.screen_width, self.screen_height)  # 设置初始窗口大小
        self.setMinimumSize(1180, 720)  # 设置最小窗口大小
        # 设置窗口调色板（从主题管理器获取）
        self.setPalette(theme_manager.to_palette())
        # 设置窗口样式表（从主题管理器获取）
        self.setStyleSheet(theme_manager.get_stylesheet())
        font = QFont("Microsoft YaHei", 9)
        self.setFont(font)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "../assets", "icons", "logo.ico")
        try:
            self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass
        self._init_dwm_shadow()

    def _init_dwm_shadow(self):
        hwnd = int(self.winId())
        margins = (ctypes.c_int * 4)(-1, -1, -1, -1)
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, margins)

    def _setup_caption_bar(self):
        bar = CaptionBar(self)
        self._caption_bar = bar
        # Expose caption bar attributes that other MainWindow methods reference
        self._app_title_lbl = bar._app_title_lbl
        self._cap_proj_lbl = bar._cap_proj_lbl
        self._menu_bar = bar._menu_bar
        self._toolbar_row = bar._toolbar_row
        self._tool_project_cmds = bar._tool_project_cmds
        self._tool_diagram_cmds = bar._tool_diagram_cmds
        self._run_btn = bar._run_btn
        self._continuous_btn = bar._continuous_btn
        self._stop_btn = bar._stop_btn
        self._reset_btn = bar._reset_btn
        self._delete_diagram_btn = bar._delete_diagram_btn
        self._theme_toggle = bar._theme_toggle
        self._apply_caption_bar_qss()
        connect_theme(lambda: self._apply_caption_bar_qss())

    def _setup_main_surface(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        # 设置根页面的内容边距为0
        root_layout.setContentsMargins(0, 0, 0, 0)
        # 设置根页面的间距为0
        root_layout.setSpacing(0)
        root_layout.addWidget(self._caption_bar)

        # 创建编辑器页面
        self._editor_surface = QWidget()
        self.editor_layout = QVBoxLayout(self._editor_surface)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_layout.setSpacing(0)

        # 构建左侧面板
        self._left_box = self._build_left_panel()
        # 创建中央和右侧的水平分割器
        self._center_right_splitter = QSplitter(Qt.Horizontal)
        self._center_right_splitter.setHandleWidth(2)  # 设置手柄宽度为2像素
        self._center_right_splitter.setStyleSheet("QSplitter::handle { background: #505050; }")

        self._diagram_panel = self._build_diagram_panel()
        self._center_right_splitter.addWidget(self._diagram_panel)

        # 构建右侧面板
        self._right_panel = self._build_right_panel()
        self._right_panel.setFixedWidth(600)  # 设置右侧面板的固定宽度
        self._center_right_splitter.addWidget(self._right_panel)

        # 工作区布局：左侧面板 | 中央+右侧分割器
        workspace = QWidget()
        ws_layout = QHBoxLayout(workspace)
        ws_layout.setContentsMargins(0, 0, 0, 0)
        ws_layout.setSpacing(0)
        ws_layout.addWidget(self._left_box)
        ws_layout.addWidget(self._center_right_splitter, 1)
        self.editor_layout.addWidget(workspace, 1)
        root_layout.addWidget(self._editor_surface, 1)

        self.setCentralWidget(root)

    def _setup_status_bar(self):
        """设置状态栏"""
        # 获取状态栏
        status = self.statusBar()
        # 禁用大小调整手柄
        status.setSizeGripEnabled(False)

        # 创建状态标签
        self._state_lbl = QLabel(f"{FontIcons.Completed} 空闲")
        # 设置样式
        self._state_lbl.setStyleSheet("color: #4caf50; font-weight: bold; background: transparent;")
        # 添加到状态栏
        status.addWidget(self._state_lbl)
        # 添加分隔线
        status.addWidget(vsep())

        # 创建消息标签
        self._msg_lbl = QLabel("就绪")
        # 添加到状态栏，拉伸因子为1
        status.addWidget(self._msg_lbl, 1)
        # 添加分隔线
        status.addWidget(vsep())

        # 创建节点计数标签
        self._node_cnt_lbl = QLabel("节点: 0")
        # 添加到永久控件（右侧）
        status.addPermanentWidget(self._node_cnt_lbl)
        # 创建时间标签
        self._time_lbl = QLabel("")
        # 添加到永久控件（右侧）
        status.addPermanentWidget(self._time_lbl)

        # 跟随主题强调色
        self._refresh_status_bar_qss()
        # 连接主题变化信号
        connect_theme(lambda: self._refresh_status_bar_qss())

    def _wire_signals(self):
        """连接各种信号"""
        # 设置属性面板的图像查看器
        self._property_panel.set_image_viewer(self._img_panel.viewer)
        # 资源面板文件缩略图选择信号
        self._resource_panel.file_selected.connect(self._on_resource_file_selected)
        # 资源面板文件双击信号
        self._resource_panel.file_double_clicked.connect(self._on_resource_file_double_clicked)

    def eventFilter(self, obj, event):
        """处理标题栏拖动——使无边框窗口可拖动

        CaptionBar._install_drag_support() 将自身及其所有子控件的事件过滤器
        指向 MainWindow，此方法提供实际的拖动逻辑。
        """
        if self._caption_bar is None:
            return super().eventFilter(obj, event)

        # 只处理属于标题栏的控件
        if obj is not self._caption_bar and not self._caption_bar.isAncestorOf(obj):
            return super().eventFilter(obj, event)

        # 按钮、菜单栏不拦截——保持其正常交互
        if isinstance(obj, (QPushButton, QMenuBar)):
            return super().eventFilter(obj, event)

        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos()
            return True
        elif event.type() == QEvent.MouseMove and hasattr(self, '_drag_pos'):
            if event.buttons() & Qt.LeftButton:
                delta = event.globalPos() - self._drag_pos
                self.move(self.pos() + delta)
                self._drag_pos = event.globalPos()
            else:
                del self._drag_pos
            return True
        elif event.type() == QEvent.MouseButtonRelease and hasattr(self, '_drag_pos'):
            del self._drag_pos
            return True

        return super().eventFilter(obj, event)

    def _connect_events(self):
        """连接事件系统"""
        event_system.subscribe(EventType.NODE_SELECTED, self._on_ev_node_sel)                # 订阅节点选中事件
        event_system.subscribe(EventType.DIAGRAM_CHANGED, self._on_ev_diag_chg)              # 订阅流程图变更事件
        event_system.subscribe(EventType.WORKFLOW_STARTED, self._on_wf_start)
        event_system.subscribe(EventType.WORKFLOW_COMPLETED, self._on_wf_done)
        event_system.subscribe(EventType.WORKFLOW_ERROR, self._on_wf_err)
        event_system.subscribe(EventType.WORKFLOW_STOPPED, self._on_wf_stopped)
        event_system.subscribe(EventType.PROJECT_LOADED, self._on_proj_load)                 # 订阅项目加载事件
        event_system.subscribe(EventType.PROJECT_SAVED, self._on_proj_save)                  # 订阅项目保存事件
        event_system.subscribe(EventType.FILE_ITERATION_NEXT, self._on_file_iteration_next)
        event_system.subscribe(EventType.FILE_ITERATION_COMPLETED, self._on_file_iteration_completed)

    def _build_menus(self, menu_bar):
        """构建菜单栏"""
        # ── 文件菜单 ──
        file_menu = menu_bar.addMenu("文件(&F)")
        file_menu.addAction("新建项目(&N)", self._on_new_project, "Ctrl+N")
        file_menu.addAction("打开项目(&O)...", self._on_open_project, "Ctrl+O")
        file_menu.addAction("保存项目(&S)", self._on_save_project, "Ctrl+S")
        file_menu.addAction("另存为(&A)...", self._on_save_as_project, "Ctrl+Shift+S")
        file_menu.addSeparator()
        file_menu.addAction("退出(&X)", self._on_close_window, "Alt+F4")

        # ── 编辑菜单 ──
        edit_menu = menu_bar.addMenu("编辑(&E)")
        edit_menu.addAction("撤销(&U)", self._on_undo_diagram, "Ctrl+Z")
        edit_menu.addAction("重做(&R)", self._on_redo_diagram, "Ctrl+Y")

        # ── 运行菜单 ──
        run_menu = menu_bar.addMenu("运行(&R)")
        run_menu.addAction("单次运行流程(&F)", self._on_run_workflow, "F5")
        run_menu.addAction("连续运行流程(&C)", self._on_continuous_run, "F6")
        run_menu.addAction("停止(&S)", self._on_stop_workflow, "Shift+F5")

        # ── 系统菜单 ──
        system_menu = menu_bar.addMenu("系统(&S)")
        system_menu.addAction("项目属性...", self._on_edit_project)

        # ── 帮助菜单 ──
        help_menu = menu_bar.addMenu("帮助(&H)")
        help_menu.addAction("使用指南(&G)", self._on_open_guide)
        help_menu.addSeparator()
        help_menu.addAction("关于 VisionFlow(&A)", self._on_about)

    def _build_left_panel(self):
        """构建左侧面板"""
        # 创建工具箱面板
        self._toolbox = ToolboxPanel()

        # 创建网格分割框，用于左侧面板的布局
        box = GridSplitterBox()
        # 将工具箱面板设置为网格分割框的内容
        box.set_content(self._toolbox)
        return box

    def _build_right_panel(self):
        """构建右侧面板"""
        self._center_splitter = QSplitter(Qt.Vertical)
        self._center_splitter.setHandleWidth(2)
        self._center_splitter.setStyleSheet("QSplitter::handle { background: #505050; }")
        center_panel = self._build_center_panel()
        center_panel.setFixedHeight(600)
        self._center_splitter.addWidget(center_panel)
        self._center_splitter.addWidget(self._build_bottom_panel())

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._center_splitter, 1)
        return panel

    def _build_center_panel(self):
        """构建中央面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._center_tabs = QTabWidget()
        self._center_tabs.setStyleSheet(self._tab_style)
        self._center_tabs.setToolTip("检查结果面板")

        self._img_panel = ImageViewerPanel()
        self._center_tabs.addTab(self._img_panel, "图像")

        module_page = QWidget()
        module_layout = QVBoxLayout(module_page)
        module_layout.setContentsMargins(0, 0, 0, 0)
        module_layout.setSpacing(0)

        self._module_result_title = QLabel("模块名称 <未选择>")
        self._module_result_title.setStyleSheet(
            "background: #2d2d30; color: #dcdcdc; padding: 8px 10px;"
            "font-size: 12px; font-weight: bold; border-bottom: 1px solid #3f3f46;"
        )
        module_layout.addWidget(self._module_result_title)

        self._property_panel = PropertyPanel()
        module_layout.addWidget(self._property_panel, 1)
        self._center_tabs.addTab(module_page, "模块结果")

        layout.addWidget(self._center_tabs, 1)

        self._resource_panel = FlowResourcePanel()
        self._resource_panel.setFixedHeight(120)
        self._resource_panel.setVisible(False)
        layout.addWidget(self._resource_panel)

        # self._side_status_strip = InlineStatusStrip("#4caf50")
        # self._side_status_strip.set_status("等待选择节点")
        # layout.addWidget(self._side_status_strip)
        return panel

    def _build_bottom_panel(self):
        """构建底部面板"""
        self._result_panel = ResultPanel()
        self._result_panel.set_image_viewer(self._img_panel.viewer)
        self._bottom_tabs = self._result_panel._tabs
        self._bottom_tabs.setStyleSheet(self._tab_style)
        self._bottom_tabs.setToolTip("运行结果面板")
        self._bottom_tabs.setMinimumHeight(120)

        self._help_panel = HelpPanel()

        self._bottom_visible = True
        self._bottom_toggle = QPushButton("▼")
        self._bottom_toggle.setFixedSize(24, 18)
        self._bottom_tabs.setCornerWidget(self._bottom_toggle, Qt.TopLeftCorner)
        return self._bottom_tabs

    def _build_diagram_panel(self):
        """构建图表面板"""
        panel = QWidget()
        panel.setToolTip("流程图编辑区")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 创建图表标签页控件
        self._diagram_tab_widget = QTabWidget()
        self._diagram_tab_widget.setStyleSheet(self._tab_style)
        self._diagram_tab_widget.setTabsClosable(False)
        self._diagram_tab_widget.tabCloseRequested.connect(self._on_close_diagram_tab)
        self._diagram_tab_widget.currentChanged.connect(self._on_diagram_tab_changed)
        self._diagram_tab_widget.setDocumentMode(True)
        self._diagram_tab_widget.setToolTip("流程图标签页")
        layout.addWidget(self._diagram_tab_widget, 1)
        # 流程图左下角小圆圈
        self._diagram_status_strip = InlineStatusStrip("#4caf50")
        self._diagram_status_strip.set_status("流程图就绪")
        layout.addWidget(self._diagram_status_strip)
        return panel

    def _apply_caption_bar_qss(self):
        """将主题颜色应用到标题栏 — 委托给 CaptionBar"""
        if hasattr(self, '_caption_bar') and self._caption_bar:
            self._caption_bar.refresh_qss()

    def _current_diagram_page(self):
        """
        获取当前图表页面
        返回：
             返回当前选中的标签页 QWidget
        """
        # 获取当前标签页控件
        page = self._diagram_tab_widget.currentWidget()
        if not page:
            return None
        return page

    def _current_diagram_editor(self) -> 'DiagramEditorWidget | None':
        """
        获取当前图表编辑器
        返回：
            返回当前标签页里的 DiagramEditorWidget 编辑器控件
        """
        page = self._current_diagram_page()  # 获取当前图表页面
        if page is None:
            return None
        return getattr(page, "editor", None)

    def _bind_project_diagram(self, project):
        """
        绑定项目图表
        参数：
            project: 项目对象
        """
        # 如果项目没有图表，添加一个默认图表
        if not project.diagrams:
            project.add_diagram(project.name)
        # 加载模板（首次从磁盘加载，后续直接复用已缓存的列表）
        if not project_service._templates:
            project_service._templates = project_service.load_templates()
        project._templates = list(project_service._templates)
        # 刷新图表标签页
        self._refresh_diagram_tabs(project)
        # 显示编辑器页面
        self._show_editor()
        # 同步项目标签
        self._sync_proj_labels(project)
        # 取消选中节点
        self._select_node(None)
        # 延迟刷新：Qt 可能在 _refresh_diagram_tabs 解除信号阻塞后触发 currentChanged(-1)
        # 在事件循环稳定后重新应用正确的状态，以覆盖任何延迟触发的无效索引信号
        QTimer.singleShot(0, lambda: self._refresh_command_states(
            project_service.current_project))

    def _show_editor(self):
        """显示编辑器页面"""
        self.editor_layout.addWidget(self._editor_surface)

    def _refresh_diagram_tabs(self, project):
        """
        刷新流程图的标签页
        全量重建标签页栏——销毁所有旧标签页，根据 project.diagrams 列表重新创建
        参数：
            project: 项目对象
        """
        self._rebuilding_tabs = True  # 设置正在重建标签页标志
        self._diagram_pages.clear()  # 清空图表页面缓存
        self._diagram_headers.clear()  # 清空图表头部缓存
        self._diagram_tab_widget.blockSignals(True)  # 阻塞标签页控件信号
        self._diagram_tab_widget.clear()  # 清空标签页

        for diagram in project.diagrams:  # 遍历项目的所有图表
            page = self._create_diagram_page(diagram)  # 创建图表页面
            self._diagram_pages[diagram.id] = page  # 保存到缓存
            index = self._diagram_tab_widget.addTab(page, "")  # 添加标签页
            self._install_diagram_tab_header(index, diagram)  # 安装标签页头部
        # 计算目标索引
        target_index = max(0, min(project.selected_diagram_index, self._diagram_tab_widget.count() - 1))
        if self._diagram_tab_widget.count() > 0:  # 如果有标签页，设置当前索引
            self._diagram_tab_widget.setCurrentIndex(target_index)

        self._diagram_tab_widget.blockSignals(False)  # 解除信号阻塞
        self._on_diagram_tab_changed(target_index)  # 触发当前标签页变化
        self._rebuilding_tabs = False  # 重置重建标志

    def _install_diagram_tab_header(self, index: int, diagram: DiagramData):
        """安装图表标签页头部控件

        参数：
            index: 标签页索引
            diagram: 图表数据
        """
        # 创建图表标签页头部
        header = DiagramTabHeader(diagram.name, self._diagram_tab_widget.tabBar())
        # 连接重命名请求信号
        header.rename_requested.connect(lambda text, current=diagram: self._rename_diagram(current, text))
        # 当前页连接运行请求信号
        # header.run_requested.connect(lambda current=diagram: self._run_diagram(current.id))
        # 当前页连接停止请求信号
        # header.stop_requested.connect(lambda current=diagram: self._stop_diagram(current.id))
        # 当前页连接重置请求信号
        # header.reset_requested.connect(lambda current=diagram: self._reset_diagram_view(current.id))
        # 设置标签页工具提示
        self._diagram_tab_widget.setTabToolTip(index, diagram.name)
        # 设置标签页左侧按钮为自定义头部
        self._diagram_tab_widget.tabBar().setTabButton(index, QTabBar.LeftSide, header)

        # 自定义关闭按钮 — 为暗色主题可见性定制样式
        close_btn = QPushButton("×")
        # 设置固定大小18x18
        close_btn.setFixedSize(18, 18)
        # 设置关闭按钮样式
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {theme_manager.color('text_secondary').name()};"
            f" font-size: 14px; padding: 0; }}"
            f"QPushButton:hover {{ background: #c42b1c; color: white; border-radius: 2px; }}"
        )
        # 连接关闭按钮点击信号
        close_btn.clicked.connect(lambda checked, idx=index: self._on_close_diagram_tab(idx))
        # 设置标签页右侧按钮为关闭按钮
        self._diagram_tab_widget.tabBar().setTabButton(index, QTabBar.RightSide, close_btn)

        # 保存头部引用
        self._diagram_headers[diagram.id] = header

    def _rename_diagram(self, diagram, new_name):
        """
        重命名图表名
        :param diagram:  当前页流程图
        :param new_name: 新名称
        :return:
        """
        name = (new_name or "").strip() or diagram.name
        diagram.name = name

        if diagram.workflow is not None:
            diagram.workflow.name = name

        # 获取当前项目
        project = project_service.current_project
        if project is not None:
            for index, item in enumerate(project.diagrams):
                if item.id == diagram.id:
                    # 更新标签页工具提示
                    self._diagram_tab_widget.setTabToolTip(index, name)
                    break

        header = self._diagram_headers[diagram.id]
        if header is not None:
            header.set_name(name)

        self._sync_proj_labels(project_service.current_project)

    def _sync_proj_labels(self, project):
        """
        同步项目标签
        参数：
            project: 项目对象
        """
        # 如果项目为空
        if project is None:
            project_name = "无项目"
            diagram_name = "无流程图"
            self.setWindowTitle("VisionFlow — VisionFlow")
        else:
            project_name = project.name or project.display_name
            diagram_name = project.selected_diagram.display_name if project.selected_diagram else "无流程图"
            self.setWindowTitle(f"{project_name} — VisionFlow")
        # 如果有标题栏项目名称标签，更新
        if hasattr(self, "_cap_proj_lbl"):
            self._cap_proj_lbl.setText(project_name)
        if hasattr(self, "_cmd_proj_lbl"):
            self._cmd_proj_lbl.setText(diagram_name)
        # 刷新命令状态
        self._refresh_command_states(project)

    def _refresh_command_states(self, project):
        """
        更新工具栏按钮启用状态
        管理的按钮：
          - 开始：当 CanStart 为 True 时启用（状态 != Running && != Canceling && 有节点）
          - 停止：当 CanStop 为 True 时启用（状态 == Running）
          - 重置：当 CanReset 为 True 时启用（总是）
          - 删除流程图：当 SelectedDiagramData != null && Count > 1 时启用

        参数：
            project: 项目对象
        """
        workflow = self._workflow
        if hasattr(self, '_run_btn'):
            self._run_btn.setEnabled(workflow.can_start() if workflow else False)
        if hasattr(self, '_continuous_btn'):
            self._continuous_btn.setEnabled(workflow.can_start() if workflow else False)
        if hasattr(self, '_stop_btn'):
            self._stop_btn.setEnabled(
                (workflow.can_stop() if workflow else False)
                or (self._wf_runner.is_running if hasattr(self, '_wf_runner') else False)
            )
        # 设置重置按钮状态
        if hasattr(self, '_reset_btn'):
            self._reset_btn.setEnabled(workflow.can_reset() if workflow else False)
        # 设置删除流程图按钮状态
        if hasattr(self, '_delete_diagram_btn'):
            self._delete_diagram_btn.setEnabled(project.can_delete_diagram if project is not None else False)

    def _refresh_status_bar_qss(self):
        """更新状态栏样式以匹配当前主题"""
        # 获取主题管理器
        tm = theme_manager
        # 获取各种颜色
        bg = tm.color("bg_surface_raised").name()  # 背景色
        text = tm.color("text_primary").name()      # 文本色
        border = tm.color("border").name()          # 边框色
        # 设置状态栏样式
        self.statusBar().setStyleSheet(
            f"QStatusBar {{ background: {bg}; color: {text}; border-top: 1px solid {border};"
            f" padding: 2px 8px; font-size: 11px; outline: 0; }}"
            f"QStatusBar::item {{ border: none; }}"
        )

    def _refresh_diagram_tab_headers(self):
        """刷新图表标签页头部激活状态"""
        pass

    def _create_diagram_page(self, diagram: DiagramData) -> QWidget:
        """
        创建图表页面
        参数：
            diagram: 图表数据
        返回：
            页面控件
        """
        # 创建页面容器
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        editor = DiagramEditorWidget()
        self._wire_diagram_editor(editor)
        # 如果图表没有工作流
        if diagram.workflow is None:
            diagram.workflow = WorkflowEngine(name=diagram.name)

        editor.bind_workflow(diagram.workflow)
        layout.addWidget(editor, 1)
        # 保存图表ID
        page.diagram_id = diagram.id
        # 保存工作流引用
        page.workflow = diagram.workflow
        # 保存编辑器引用
        page.editor = editor
        return page

    def _on_new_project(self):
        project = project_service.new_project()
        # 绑定项目图表
        self._bind_project_diagram(project)

    def _on_open_project(self):
        """打开项目"""
        path, _ = QFileDialog.getOpenFileName(self, "打开项目", "", project_service.FILE_FILTER)
        if path:
            self._open_project(path)

    def _open_project(self, path: str):
        """打开指定路径的项目

        参数：
            path: 项目文件路径
        """
        # 如果路径无效或文件不存在
        if not path or not os.path.exists(path):
            # 显示警告
            QMessageBox.warning(self, "打开失败", f"文件不存在: {path}")
            return
        # 加载项目
        project = project_service.load(path)
        if project:
            # 绑定项目图表
            self._bind_project_diagram(project)
            QMessageBox.information(self, "打开成功", f"项目已成功打开: {project.name}")

    def _on_save_project(self):
        """保存项目"""
        project = project_service.current_project
        if project is None:
            return
        # 同步工作流到项目
        self._sync_workflow_to_project()
        # 如果项目有文件路径
        if project.file_path:
            if project_service.save(project):
                QMessageBox.information(self, "保存成功", f"项目已保存到 {project.file_path}")
            else:
                QMessageBox.information(self, "保存失败", f"项目保存失败")
        else:
            # 否则另存为
            self._on_save_as_project()

    def _on_save_as_project(self):
        """另存为项目"""
        project = project_service.current_project or project_service.new_project()
        # 打开保存文件对话框，默认文件名格式为"项目名.json"
        path, _ = QFileDialog.getSaveFileName(self, "另存为...", f"{project.name}.json", project_service.FILE_FILTER)
        # 如果用户选择了路径
        if path:
            # 设置项目的文件路径
            project.file_path = path
            # 同步工作流到项目（将当前编辑器的状态保存到项目）
            self._sync_workflow_to_project()
            # 调用项目服务的另存为方法
            if project_service.save_as(project, path):
                # 记录成功日志
                QMessageBox.information(self, "保存成功", f"项目已保存到 {path}")
                # 同步项目标签（更新标题栏显示的项目名称）
                self._sync_proj_labels(project)

    def _on_ev_node_sel(self, sender, **kwargs):
        """
        节点选中事件处理
        订阅 NODE_SELECTED 事件，收到后调 _select_node 更新选中状态
        参数：
            sender: 发送者
            **kwargs: 关键字参数
        """
        self._select_node(kwargs.get("node", sender))

    def _on_ev_diag_chg(self, sender, **kwargs):
        """
        图表变更事件处理
        订阅 EventType.DIAGRAM_CHANGED 事件，收到后刷新状态栏节点计数和工具栏按钮状态
        图上节点变了 → 底下状态栏数刷新 + 工具栏按钮状态刷新节点数量。
        参数：
            sender: 发送者
            **kwargs: 关键字参数
        """
        # 如果有工作流，更新节点计数
        if self._workflow:
            self._node_cnt_lbl.setText(f"节点: {len(self._workflow.get_all_nodes())}")
        # 节点添加/删除 → CanStart 条件可能已改变
        self._refresh_command_states(project_service.current_project)

    def _on_wf_start(self, sender, **kwargs):
        self._state_lbl.setText(f"{FontIcons.Sync} 运行中")
        self._state_lbl.setStyleSheet("color: #2196f3; font-weight: bold;")
        self._msg_lbl.setText("流程运行中...")
        self._diagram_status_strip.set_status("流程图运行中...", "#2196f3")

    def _on_wf_done(self, sender, **kwargs):
        if not self._continuous_mode:
            self._live_preview_timer.stop()
        label = "连续执行中" if self._continuous_mode else "流程执行完成"
        self._state_lbl.setText(f"{FontIcons.Completed} {label}")
        self._state_lbl.setStyleSheet("color: #4caf50; font-weight: bold;")
        self._msg_lbl.setText(label)
        self._diagram_status_strip.set_status(label, "#4caf50")
        pending = getattr(self, '_run_all_pending_path', '')
        if pending:
            self._run_all_pending_path = ''
            result_img = sender.current_message.result_image_source if sender and sender.current_message else None
            if result_img is not None:
                self._image_for_display.emit(result_img)

    def _on_wf_err(self, sender, **kwargs):
        self._continuous_mode = False
        self._live_preview_timer.stop()
        result = kwargs.get("result")
        msg = getattr(result, 'message', '流程错误') if result else '流程错误'
        self._state_lbl.setText(f"{FontIcons.Error} 错误")
        self._state_lbl.setStyleSheet("color: #f44336; font-weight: bold;")
        self._msg_lbl.setText(msg)
        self._diagram_status_strip.set_status(f"流程图错误：{msg}", "#f44336")
        self._refresh_command_states(project_service.current_project)

    def _on_wf_stopped(self, sender, **kwargs):
        self._continuous_mode = False
        self._state_lbl.setText(f"{FontIcons.Stop} 已停止")
        self._state_lbl.setStyleSheet("color: #ff9800; font-weight: bold;")
        self._msg_lbl.setText("流程已被用户停止")
        self._diagram_status_strip.set_status("流程图已停止", "#ff9800")
        self._refresh_command_states(project_service.current_project)

    def _on_file_iteration_next(self, sender, **kwargs):
        """运行全部：记录当前文件路径，等流程跑完再显示"""
        file_path = kwargs.get("file_path", "")
        index = kwargs.get("index", 0)
        total = kwargs.get("total", 0)
        auto_switch = kwargs.get("auto_switch", True)

        self._run_all_pending_path = file_path

        if auto_switch and hasattr(self, '_resource_panel') and self._resource_panel.isVisible():
            self._resource_panel.refresh_selection()

        self._diagram_status_strip.set_status(
            f"运行全部: {index + 1}/{total}", "#2196f3")

    def _on_file_iteration_completed(self, sender, **kwargs):
        """运行全部完成"""
        total = kwargs.get("total", 0)
        self._continuous_mode = False
        self._last_preview_src = None
        self._diagram_status_strip.set_status(
            f"运行全部完成: {total} 个文件", "#4caf50")
        self._msg_lbl.setText(f"运行全部完成 ({total} 个文件)")
        self._run_all_pending_path = ""
        self._live_preview_timer.stop()
        editor = self._current_diagram_editor()
        if editor:
            editor.stop_state_polling()

    def _on_proj_load(self, sender, **kwargs):
        """
        项目加载事件处理
        订阅 EventType.PROJECT_LOADED 事件，收到后刷新状态栏节点计数和工具栏按钮状态
        """
        project = kwargs.get("project")
        if project:
            self._bind_project_diagram(project)

    def _on_proj_save(self, sender, **kwargs):
        """
        项目保存事件处理
        订阅 EventType.PROJECT_SAVED 事件，收到后同步项目标签（更新标题栏显示的项目名称）
        参数：
            sender: 发送者
            **kwargs: 关键字参数
        """
        # 获取项目对象
        project = kwargs.get("project")
        if project:
            # 同步项目标签
            self._sync_proj_labels(project)

    def _wire_diagram_editor(self, editor: DiagramEditorWidget):
        """连接节点编辑器信号"""
        # 连接节点选中信号
        editor.node_selected.connect(self._on_editor_node_selected)
        # 连接节点取消选中信号
        editor.node_deselected.connect(lambda: self._select_node(None))
        # 连接节点双击信号
        editor.node_double_clicked.connect(self._on_editor_node_double_clicked)
        # 连接节点属性请求信号
        editor.node_properties_requested.connect(self._on_editor_node_double_clicked)
        # 连接节点帮助请求信号
        editor.node_help_requested.connect(self._on_editor_node_help_requested)
        # 连接场景状态消息信号
        editor.scene.status_message.connect(self._on_editor_status)
        editor.execution_finished.connect(self._on_execution_finished)

    def _on_close_window(self):
        self.close()

    def _on_add_diagram(self):
        """添加新图表"""
        project = project_service.current_project
        # 如果项目为空，新建项目
        if project is None:
            project = project_service.new_project()
        # 同步工作流到项目
        self._sync_workflow_to_project()
        # 添加新图表
        diagram = project.add_diagram()
        # 刷新图表标签页
        self._refresh_diagram_tabs(project)
        QMessageBox.information(self, "添加成功", f"已添加新图表: {diagram.name}")
        # 同步项目标签
        self._sync_proj_labels(project)

    def _on_undo_diagram(self):
        """撤销图表操作"""
        # 获取当前图表编辑器
        editor = self._current_diagram_editor()
        if editor is not None:
            # 调用编辑器的撤销方法
            editor._on_undo()

    def _on_redo_diagram(self):
        """重做图表操作"""
        # 获取当前图表编辑器
        editor = self._current_diagram_editor()
        if editor is not None:
            # 调用编辑器的重做方法
            editor._on_redo()

    def _on_editor_node_selected(self, node_data):
        self._select_node(node_data)

    def _on_editor_node_double_clicked(self, node_data):
        """
        处理节点双击 — 打开标签页属性对话框
        解耦：调用 open_node_dialog，它使用 get_property_presenter()
        来解析设置对象。不同的节点类型可以重写 get_property_presenter()
        来提供自定义的设置面板。

        参数：
            node_data: 节点数据
        """
        self._select_node(node_data)
        open_node_dialog(node_data, parent=self)

    def _on_editor_node_help_requested(self, node_data):
        """
        处理右键 → 帮助 — 切换到帮助标签页并显示节点帮助

        参数：
            node_data: 节点数据
        """
        self._select_node(node_data)
        if hasattr(node_data, "_bottom_tabs"):
            self._bottom_tabs.setCurrentIndex(2)  # 索引2 = 帮助标签页

        if hasattr(self, '_help_panel'):
            self._help_panel.set_node(node_data)

    def _on_editor_status(self, message):
        # 更新消息标签
        self._msg_lbl.setText(message)
        if message:
            # 更新图表状态栏
            self._diagram_status_strip.set_status(message, "#4caf50")

    def _on_execution_finished(self):
        if not self._continuous_mode:
            editor = self._current_diagram_editor()
            if editor:
                editor.stop_state_polling()
        self._refresh_command_states(project_service.current_project)

    def _select_node(self, node):
        """选择节点"""
        self._live_preview_timer.stop()
        self._last_preview_src = None  # 切换节点时清除预览缓存，防止显示旧图像
        self._selected_node = node
        self._update_info_panels(node)
        self._update_image_for_node(node)
        self._update_resource_panel(node)
        self._schedule_live_preview(node)

    def _update_info_panels(self, node):
        """更新属性/帮助/结果面板和标题"""
        self._property_panel.set_node(node)
        self._help_panel.set_node(node)
        self._module_result_title.setText(f"模块名称 <{node.name}>" if node else "模块名称 <未选择>")
        if isinstance(node, VisionNodeData):
            self._result_panel.show_node_results(node)
            self._result_panel.show_help(node)
        else:
            self._result_panel.show_node_results(None)
            self._result_panel.show_help(None)
        self._update_image_context(node)

    def _update_image_for_node(self, node):
        """更新图像面板显示"""
        if isinstance(node, VisionNodeData) and node.mat is not None:
            self._img_panel.set_image(node.mat)
        elif isinstance(node, VisionNodeData) and node._result_image_source is not None:
            self._img_panel.set_image(node._result_image_source)
        else:
            self._img_panel.set_image(None)

    def _update_resource_panel(self, node):
        """始终显示资源面板，源节点时绑定数据"""
        if isinstance(node, SrcFilesVisionNodeData):
            self._resource_panel.set_node(node)
        self._resource_panel.setVisible(True)

    def _on_resource_file_selected(self, path: str):
        """资源文件选中事件 — 在图像面板显示缩略图对应的图片"""
        if not path:
            return

        image = cv2.imread(path, cv2.IMREAD_COLOR)
        if image is not None:
            self._img_panel.set_image(image)
            self._center_tabs.setCurrentIndex(0)
            QTimer.singleShot(0, self._img_panel.viewer.fit_to_window)

    def _on_resource_file_double_clicked(self, path: str):
        """资源文件双击 — 全尺寸查看"""
        if not path or not os.path.exists(path):
            return
        self._on_resource_file_selected(path)
        self._center_tabs.setCurrentIndex(0)

    def _schedule_live_preview(self, node):
        """连续模式下对视觉节点启动实时预览"""
        if node and self._continuous_mode and isinstance(node, VisionNodeData):
            self._live_preview_timer.start()
        else:
            self._live_preview_timer.stop()

    def _update_image_context(self, node):
        """
        根据节点的不同情况，更新图像面板显示的信息
        参数：
            node: 节点数据对象
        """
        if node is None:
            self._img_panel.clear_context_info()  # 清空图像显示区域的上下文信息
            return

        badge = "无结果"          # 徽章文本和颜色
        badge_color = "#3f3f46"  # 灰色

        if isinstance(node, SrcFilesVisionNodeData):  # 如果是源文件节点
            badge = "原始图像"
            badge_color = "#0078d4"  # 蓝色
        # 如果是视觉节点且存在图像数据
        elif isinstance(node, VisionNodeData) and (node.mat is not None or node.result_image_source is not None):
            badge = "模块结果"
            badge_color = "#4caf50"  # 绿色

        # 查找图像来源路径和提示信息
        source_path, source_hint = self._find_source_context(node)
        self._img_panel.set_result_badge(badge, badge_color)  # 设置结果徽章
        self._img_panel.set_source_hint(source_hint)          # 设置来源提示

        self._img_panel.set_message_banner(getattr(node, "message", ""))  # 设置消息横幅

        if source_path:  # 如果有图像路径
            # 获取像素宽度和高度
            pixel_w = getattr(node, 'pixel_width', 0) or 0
            pixel_h = getattr(node, 'pixel_height', 0) or 0
            # 显示图像路径和像素尺寸（宽×高）
            self._img_panel.set_image_info(source_path, pixel_w, pixel_h)
        else:
            # 清空图像信息
            self._img_panel.set_image_info(None)

    def _find_source_context(self, node) -> tuple[str | None, str]:
        """
        查找节点的图像来源上下文
        参数：
            node: 节点数据对象
        返回：
            (源文件路径, 提示信息) 元组
        """
        if node is None:
            return None, ""

        candidates: list[SrcFilesVisionNodeData] = []  # 候选源节点列表
        if isinstance(node, SrcFilesVisionNodeData):   # 如果节点本身就是源文件节点
            candidates.append(node)

        if hasattr(node, "get_all_from_node_datas"):   # 如果节点有获取所有上游节点的方法
            # 遍历所有上游节点，添加源文件类型的节点
            candidates.extend(
                upstream for upstream in node.get_all_from_node_datas()
                if isinstance(upstream, SrcFilesVisionNodeData)
            )

        seen: set[str] = set()               # 已处理的节点ID集合（避免重复）

        for source_node in candidates:       # 遍历候选源节点
            if source_node.node_id in seen:  # 如果已处理过，跳过
                continue

            seen.add(source_node.node_id)                             # 标记为已处理
            path = getattr(source_node, "src_file_path", "")          # 获取当前文件路径
            paths = getattr(source_node, "src_file_paths", []) or []  # 获取文件路径列表

            if not path:
                continue

            hint = ""  # 构建提示信息
            if paths:
                hint = next(
                    (f"图像源 {i+1}/{len(paths)}" for i, p in enumerate(paths) if p == path),
                    f"图像源 1/{len(paths)}",
                )
            return path, hint
        return None, ""

    def _on_image_for_display(self, img):
        """主线程处理：显示运行全部过程中加载的图像"""
        if img is not None:
            self._img_panel.set_image(img)
            self._center_tabs.setCurrentIndex(0)
            self._img_panel.viewer.fit_to_window()

    def _tick_live_preview(self):
        """在连续执行期间，从选定节点刷新图像查看器"""
        node = self._selected_node                                         # 获取当前选中的节点
        if node is None or not self._continuous_mode:                      # 如果未选中节点或者不是连续模式
            self._live_preview_timer.stop()                                # 停止计时器
            return

        if isinstance(node, VisionNodeData):                               # 如果节点是视觉节点
            src = node.mat if node.mat is not None else node._result_image_source
            if src is not None and src is not getattr(self, '_last_preview_src', None):
                self._last_preview_src = src                               # 记录上次显示的图像引用
                self._img_panel.set_image(src)                             # 仅在图像变化时刷新

    def _on_duplicate_diagram(self):
        """复制当前图表"""
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 同步工作流到项目
        self._sync_workflow_to_project()
        # 复制当前图表
        clone = project.duplicate_diagram()
        if clone:
            # 刷新图表标签页
            self._refresh_diagram_tabs(project)
            QMessageBox.information(self, "复制成功", f"已复制图表: {clone.name}")

    def _on_delete_diagram(self):
        """
        删除当前图表
        模式：
          - Model (VisionProjectItemBase) 持有 DeleteDiagramCommand
          - CanExecute: SelectedDiagramData != null && Count > 1
          - Execute: DiagramDatas.Remove(SelectedDiagramData)
          - TabControl 通过绑定自动选择下一个图表

        Python: 同步 → model.delete_selected_diagram() → 刷新标签页 → 记录日志。
        视图只处理UI关注点；业务逻辑留在 ProjectItem 中。
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 同步工作流到项目
        self._sync_workflow_to_project()
        # 删除选中的图表
        deleted = project.delete_selected_diagram()
        # 刷新图表标签页
        self._refresh_diagram_tabs(project)
        # 同步项目标签
        self._sync_proj_labels(project)

    def _on_cycle_run_mode(self):
        """循环切换运行模式：节点 → 连线 → 端口 → 节点"""
        # 如果没有工作流，返回
        if not self._workflow:
            return
        # 模式显示标签字典
        _MODE_LABELS = {
            DiagramFlowableMode.NODE: "运行模式: 按节点",
            DiagramFlowableMode.LINK: "运行模式: 节点+连线",
            DiagramFlowableMode.PORT: "运行模式: 节点+连线+端口",
        }
        # 下一个模式的映射
        _NEXT = {
            DiagramFlowableMode.NODE: DiagramFlowableMode.LINK,
            DiagramFlowableMode.LINK: DiagramFlowableMode.PORT,
            DiagramFlowableMode.PORT: DiagramFlowableMode.NODE,
        }
        # 获取当前运行模式
        current = self._workflow.flowable_mode
        # 切换到下一个模式
        self._workflow.flowable_mode = _NEXT[current]
        # 获取新模式的显示标签
        new_label = _MODE_LABELS[self._workflow.flowable_mode]
        # 更新图表状态栏，显示当前运行模式
        if current == DiagramFlowableMode.NODE:
            self._diagram_status_strip.set_status(new_label, "#39e605")
        elif current == DiagramFlowableMode.LINK:
            self._diagram_status_strip.set_status(new_label, "#0510e6")
        elif current == DiagramFlowableMode.PORT:
            self._diagram_status_strip.set_status(new_label, "#4caf50")

    def _on_close_diagram_tab(self, index):
        """
        通过标签页索引关闭图表，用户点击流程图 tab 上的叉号关闭
        流程与 _on_delete_diagram 相同，但使用显式索引，
        用于用户点击标签页关闭按钮而非工具栏删除按钮的情况。
        参数：
            index: 标签页索引
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 检查索引有效性
        if not (0 <= index < len(project.diagrams)):
            return
        # 同步工作流到项目
        self._sync_workflow_to_project()
        # 删除指定索引的图表
        diagram = project.diagrams[index]
        # 删除图表
        if len(project.diagrams) <= 1:
            self._return_to_blank()
            return
        project.delete_diagram(diagram)
        # 刷新图表标签页
        self._refresh_diagram_tabs(project)
        # 同步项目标签
        self._sync_proj_labels(project)

    def _sync_workflow_to_project(self):
        """
        同步工作流到项目
        在执行持久化或破坏性操作之前，将编辑器画布上的最新状态刷回内存中的数据模型
        _sync_workflow_to_project()
          └─ editor.save_to_workflow()          # 每个打开的标签页
               └─ scene.save_to_workflow(workflow)
                    ├─ 遍历所有 NodeItem → 把 pos_x/pos_y 写回 node._pos_x/_pos_y
                    └─ 遍历所有 EdgeItem → 把连线信息写回 workflow._links
          └─ diagram.workflow = editor._workflow  # 确保引用是最新的

        调用时机（在 main_window.py 中）：
            保存项目前 (_on_save_project)
            关闭/删除标签页前 (_on_close_diagram_tab, _on_delete_diagram)
            添加新图表前 (_on_add_diagram)
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 遍历项目的所有图表
        for index, diagram in enumerate(project.diagrams):
            # 如果索引在标签页范围内
            if index < self._diagram_tab_widget.count():
                # 获取页面
                page = self._diagram_tab_widget.widget(index)
                # 获取编辑器
                editor = getattr(page, "editor", None)
                # 如果编辑器存在，保存到工作流
                if editor is not None:
                    editor.save_to_workflow()
                    diagram.workflow = editor._workflow

    def _on_diagram_tab_changed(self, index: int):
        """
        图表标签页切换事件
        参数：
            index: 新的标签页索引
        """
        project = project_service.current_project
        if project is None or not (0 <= index < len(project.diagrams)):
            if getattr(self, '_rebuilding_tabs', False):
                return
            # 清空工作流引用
            self._workflow = None
            # 清空编辑器引用
            self._diagram_editor = None
            # 绑定空工作流到运行器
            self._wf_runner.bind(None)
            # 设置图表状态栏
            self._diagram_status_strip.set_status("流程图就绪", "#4caf50")
            # 刷新命令状态
            self._refresh_command_states(None)
            return
        # 更新项目的选中图表索引
        project.selected_diagram_index = index
        # 获取选中的图表
        diagram = project.selected_diagram
        # 获取当前图表页面
        page = self._current_diagram_page()
        # 清空结果面板的历史记录
        self._result_panel.clear_history()
        # 设置工作流
        self._workflow = diagram.workflow if diagram else None
        # 绑定工作流到结果面板
        self._result_panel.bind_workflow(self._workflow)
        # 同步历史记录
        self._result_panel.sync_history_from_workflow()
        # 绑定工作流到运行器
        self._wf_runner.bind(self._workflow)
        # 获取编辑器
        self._diagram_editor = getattr(page, "editor", None)
        # 更新节点计数标签
        self._node_cnt_lbl.setText(f"节点: {len(self._workflow.get_all_nodes()) if self._workflow else 0}")
        # 同步项目标签
        self._sync_proj_labels(project)
        # 刷新图表标签页头部激活状态
        self._refresh_diagram_tab_headers()
        # 设置图表状态栏
        self._diagram_status_strip.set_status(f"当前流程图：{diagram.display_name}", "#39e605")

    def _return_to_blank(self):
        """清空项目，恢复空白页面"""
        project_service.close_project()
        self._diagram_tab_widget.blockSignals(True)
        self._diagram_tab_widget.clear()
        self._diagram_tab_widget.blockSignals(False)
        self._diagram_pages.clear()
        self._diagram_headers.clear()
        self._workflow = None
        self._diagram_editor = None
        self._wf_runner.bind(None)
        self._sync_proj_labels(None)

    def _on_add_from_template(self):
        """
        从模板添加图表
        流程：
          1. 检查：没有模板时显示"不存在模板，请先添加模板"
          2. 显示DiagramTemplates选择对话框（ListBox DataTemplate）
          3. 提交时：将SelectedDiagramTemplate.Diagram添加到DiagramDatas
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return

        # 如果没有模板
        if not project.templates:
            QMessageBox.information(self, "提示", "不存在模板，请先将流程图另存为模板")
            return

        # 创建对话框（add 模式：仅选择添加，不显示删除按钮）
        dlg = TemplateManagerDialog(project, self, mode="add")
        dlg.exec_()
        if dlg.added_diagram:
            self._refresh_diagram_tabs(project)
            QMessageBox.information(self, "提示", f"已从模板添加图表：{dlg.added_diagram.display_name}")

    def _on_manage_templates(self):
        """打开模板管理对话框"""
        project = project_service.current_project
        if project is None:
            return

        # 创建对话框（manage 模式：可删除模板）
        dlg = TemplateManagerDialog(project, self, mode="manage")
        # 执行对话框
        dlg.exec_()
        # 持久化任何删除操作
        self._persist_templates()
        # 如果有添加的图表
        if dlg.added_diagram:
            # 刷新图表标签页
            self._refresh_diagram_tabs(project)
            QMessageBox.information(self, "提示", f"已从模板创建图表: {dlg.added_diagram.name}")

    def _persist_templates(self):
        """持久化模板到磁盘"""
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 同步到全局存储
        project_service._templates = list(project._templates)
        # 保存模板
        project_service.save_templates(project._templates)

    def _on_save_as_template(self):
        """
        将当前图表另存为模板
        检查：如果图表没有节点，警告用户以防止保存空模板。
        """
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            return
        # 获取当前选中的图表
        diagram = project.selected_diagram
        if diagram is None:
            return

        # 获取节点数量
        node_count = len(diagram.workflow.get_all_nodes()) if diagram.workflow else 0
        # 如果没有节点
        if node_count == 0:
            # 询问用户是否保存空模板
            reply = QMessageBox.question(
                self, "空流程图",
                "当前流程图没有任何节点，保存为模板后添加时将显示空白画布。\n\n确定要保存空模板吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        # 获取模板名称
        name, ok = QInputDialog.getText(
            self, "保存模板名称",
            "请输入模板名称：",
            text=diagram.name)
        # 如果确认且名称不为空
        if ok and name.strip():
            # 同步工作流到项目
            self._sync_workflow_to_project()
            # 保存为模板
            project.save_diagram_as_template(diagram=diagram, name=name.strip())
            # 持久化模板
            self._persist_templates()
            QMessageBox.information(self, "保存成功", f"流程图已保存为模板：{name.strip()}", QMessageBox.Ok)

    def _on_run_workflow(self):
        """
        单次运行：执行工作流一次
        在工作线程上按拓扑顺序执行所有节点。
        - 每个节点条通过事件变为绿色（完成）或红色（错误）。
        - 图像区域保持空白，直到用户点击节点。
        """
        # 开始执行，连续模式为False
        self._start_execution(continuous=False)

    def _on_continuous_run(self):
        """连续运行：循环执行工作流"""
        self._start_execution(continuous=True)

    def _on_stop_workflow(self):
        """停止工作流执行"""
        self._stop_requested = True
        self._continuous_mode = False
        self._live_preview_timer.stop()
        self._wf_runner.stop()
        editor = self._current_diagram_editor()
        if editor:
            editor.stop_state_polling()
            for item in editor.scene.get_all_node_items():
                item.set_state(NodeState.IDLE)
        self._msg_lbl.setText("流程已被用户停止")
        self._diagram_status_strip.set_status("流程图已停止", "#ff9800")
        self._refresh_command_states(project_service.current_project)

    def _on_reset_workflow_view(self):
        """重置工作流到就绪状态"""
        if self._workflow:
            self._workflow.reset()
        editor = self._current_diagram_editor()
        if editor is not None and self._workflow is not None:
            editor.bind_workflow(self._workflow)
        self._msg_lbl.setText("已重置当前流程图")
        self._refresh_command_states(project_service.current_project)

    def _start_execution(self, continuous: bool = False):
        """公共执行入口 — 同步、清理节点状态、启动后台线程"""
        if not self._workflow:
            return
        self._sync_workflow_to_project()
        node_count = len(self._workflow.get_all_nodes())
        if node_count == 0:
            self._msg_lbl.setText("流程图无节点，无法开始")
            return
        self._continuous_mode = continuous
        self._stop_requested = False
        self._refresh_command_states(project_service.current_project)
        self._prepare_editor_for_run()
        if continuous:
            self._wf_runner.start_continuous()
            self._stop_btn.setEnabled(True)
        else:
            self._wf_runner.start_once()

    def _prepare_editor_for_run(self):
        """重置所有节点的执行状态和外观，启动状态轮询"""
        editor = self._current_diagram_editor()
        if editor is None:
            return
        editor.start_state_polling()
        for item in editor.scene.get_all_node_items():
            nd = item.node_data
            if isinstance(nd, VisionNodeData):
                nd.reset_execution_state()
            item.set_state(NodeState.RUNNING)

    def _on_edit_project(self):
        """打开项目设置对话框"""
        # 获取当前项目
        project = project_service.current_project
        if project is None:
            # 如果没有项目，新建项目
            project = project_service.new_project()
        # 创建对话框
        dlg = QDialog(self)
        # 设置窗口标题
        dlg.setWindowTitle("项目属性")
        # 设置最小宽度400
        dlg.setMinimumWidth(400)
        # 设置对话框样式
        dlg.setStyleSheet("QDialog { background: #2d2d30; color: #dcdcdc; }")
        # 创建表单布局
        form = QFormLayout(dlg)

        # 项目名称编辑框
        name_edit = QLineEdit(project.display_name)
        form.addRow("项目名称:", name_edit)

        # 项目描述编辑框
        desc_edit = QLineEdit(getattr(project, 'description', ''))
        form.addRow("描述:", desc_edit)

        # 作者编辑框
        author_edit = QLineEdit(getattr(project, 'author', ''))
        form.addRow("作者:", author_edit)

        # 统计信息标签
        info = QLabel(
            f"流程图: {len(project.diagrams)} 个\n节点总数: {sum(len(d.workflow.get_all_nodes()) if d.workflow else 0 for d in project.diagrams)}")
        info.setStyleSheet("color: #999; font-size: 11px;")
        form.addRow(info)

        # 按钮框
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        # 如果用户确认
        if dlg.exec_() == dlg.Accepted:
            # 保存旧名称
            old_name = project.name
            # 更新项目属性
            project.name = name_edit.text().strip() or project.name
            project.description = desc_edit.text()
            project.author = author_edit.text()
            # 如果项目有文件路径且名称已更改，更新文件路径
            if project.file_path and project.name != old_name:
                d = os.path.dirname(project.file_path)
                project.file_path = os.path.join(d, f"{project.name}.json")
            # 同步项目标签
            self._sync_proj_labels(project)
            # 记录日志
            QMessageBox.information(self, "项目属性", "项目属性已更新。", QMessageBox.Ok)

    def _on_show_theme_dialog(self):
        """打开颜色主题选择器对话框"""
        # 创建主题选择器对话框
        dlg = ThemePickerDialog(self)
        # 如果用户确认
        if dlg.exec_():
            # 应用主题
            self._apply_theme()
        # 如果有主题切换按钮
        if hasattr(self, '_theme_toggle'):
            # 阻塞信号，避免循环
            self._theme_toggle.blockSignals(True)
            # 设置主题切换按钮状态
            self._theme_toggle.setChecked(theme_manager.is_dark)
            # 恢复信号
            self._theme_toggle.blockSignals(False)

    def _apply_theme(self):
        """重新应用主题到所有控件"""
        # 获取主题管理器
        tm = theme_manager
        qss = tm.get_stylesheet()

        # 1. 全局QSS — 覆盖所有窗口、对话框和标准控件类型
        QApplication.instance().setStyleSheet(qss)

        # 2. 主窗口调色板 + 样式表
        self.setPalette(tm.to_palette())
        self.setStyleSheet(qss)

        # 3. 重新应用工具栏按钮样式 + 场景 + 控件重绘 + 图像查看器（合并为单次树遍历）
        self._reapply_widget_styles()
        cmd = self._cmd_btn  # 当前主题的QSS
        seen_scenes: set[int] = set()
        for child in self.findChildren(QWidget):
            if isinstance(child, QGraphicsView):
                scene = child.scene()
                if scene is not None:
                    sid = id(scene)
                    if sid not in seen_scenes:
                        seen_scenes.add(sid)
                        scene.setBackgroundBrush(_make_checker_brush())
                        scene.update()
                        child.viewport().update()
                continue  # 不 unpolish QGraphicsView，避免破坏 viewport

            try:
                child.style().unpolish(child)
                child.style().polish(child)
                child.update()
            except Exception:
                pass

            if isinstance(child, QPushButton):
                s = child.styleSheet()
                if s and 'transparent' in s and 'border-radius' in s:
                    child.setStyleSheet(cmd)
            elif isinstance(child, ImageViewerPanel):
                if hasattr(child, '_setup_ui') and hasattr(child, 'viewer'):
                    child.viewer.viewport().update()

        # 7. 图表标签页头部（标签页栏中的自定义控件）
        for header in self._diagram_headers.values():
            if hasattr(header, '_refresh_qss'):
                header._refresh_qss()

        # 8. 标题栏
        if hasattr(self, '_title_bar'):
            self._title_bar.update()

    def _on_toggle_theme(self):
        """在暗色和亮色主题之间切换"""
        # 切换主题
        theme_manager.toggle_dark()
        # 应用主题
        self._apply_theme()
        # 如果有主题切换按钮
        if hasattr(self, '_theme_toggle'):
            # 阻塞信号，避免循环
            self._theme_toggle.blockSignals(True)
            # 设置主题切换按钮状态
            self._theme_toggle.setChecked(theme_manager.is_dark)
            # 恢复信号
            self._theme_toggle.blockSignals(False)

    def _reapply_widget_styles(self):
        """重新应用动态QSS到有内联样式的控件"""
        # 刷新缓存的 QSS 为当前主题的值
        self._cmd_btn = cmd_btn_qss()
        self._tab_style = tab_qss()

        tm = theme_manager

        # 主题切换按钮
        if hasattr(self, '_theme_toggle'):
            self._theme_toggle.setStyleSheet(self._cmd_btn + f"""
                FontIconToggleButton:checked {{ color: {tm.color('text_primary').name()}; }}
                FontIconToggleButton:checked:hover {{ background: {tm.color('bg_surface_hover').name()}; }}
            """)

        # 所有 FontIconButton 重新应用当前主题 QSS
        for btn in self.findChildren(QPushButton):
            if isinstance(btn, FontIconButton) or isinstance(btn, FontIconToggleButton):
                btn.setStyleSheet(self._cmd_btn)

        # 图表标签页
        if hasattr(self, '_diagram_tab_widget'):
            self._diagram_tab_widget.setStyleSheet(self._tab_style)

        # 中央标签页（图像 / 模块结果）
        if hasattr(self, '_center_tabs'):
            self._center_tabs.setStyleSheet(self._tab_style)

        # 底部标签页 + 折叠三角形按钮
        if hasattr(self, '_bottom_tabs'):
            self._bottom_tabs.setStyleSheet(self._tab_style)
        if hasattr(self, '_bottom_toggle'):
            self._bottom_toggle.setStyleSheet(
                f"QPushButton {{ background: {tm.color('bg_surface_raised').name()}; "
                f"border: 1px solid {tm.color('border').name()}; "
                f"color: {tm.color('text_secondary').name()}; font-size: 9px; }}"
                f"QPushButton:hover {{ color: {tm.color('text_title').name()}; }}"
            )

        # 左侧面板
        if hasattr(self, '_left_box') and hasattr(self._left_box, '_refresh_qss'):
            self._left_box._refresh_qss()

        # 标题栏（菜单 + 工具栏）
        self._apply_caption_bar_qss()

    def _on_open_settings(self):
        """打开设置对话框"""
        # 创建设置对话框
        dlg = SettingsDialog(self)
        # 如果用户确认
        if dlg.exec_() == QDialog.Accepted:
            # 应用设置
            self._apply_settings()
        # 应用主题
        self._apply_theme()
        # 如果有主题切换按钮
        if hasattr(self, '_theme_toggle'):
            # 阻塞信号，避免循环
            self._theme_toggle.blockSignals(True)
            # 设置主题切换按钮状态
            self._theme_toggle.setChecked(theme_manager.is_dark)
            # 恢复信号
            self._theme_toggle.blockSignals(False)

    def _apply_settings(self):
        """将持久化设置应用到UI"""
        data = load_app_config()

        # 显示/隐藏主题切换按钮
        if hasattr(self, '_theme_toggle'):
            show = data.get("show_theme_btn", True)
            self._theme_toggle.setVisible(show)

        # 切换画布网格显示
        show_grid = data.get("show_grid", True)
        editors = []
        # 收集所有编辑器
        if self._diagram_editor is not None:
            editors.append(self._diagram_editor)
        for page in self._diagram_pages.values():
            ed = getattr(page, 'editor', None)
            if ed is not None:
                editors.append(ed)
        # 遍历所有编辑器，设置网格显示状态
        for editor in editors:
            s = editor.scene
            if s is not None and hasattr(s, '_show_grid'):
                if s._show_grid != show_grid:
                    s.toggle_grid()

        # 系统托盘
        tray_enabled = data.get("show_tray", True)
        if hasattr(self, '_tray_icon'):
            self._tray_icon.setVisible(tray_enabled)

    def _on_open_guide(self):
        """打开交互式引导覆盖层"""
        overlay = GuideOverlay(self)
        self._guide_overlay = overlay  # 保持引用，防止被垃圾回收
        overlay.finished.connect(lambda: setattr(self, '_guide_overlay', None))

        # ── 项目操作 ──
        overlay.add_step("新建项目",
                         "点击「新建项目」创建一个新的视觉检测项目，\n所有流程图、图像和设置都将组织在项目内。",
                         widget=find_child_by_tip(self, "新建项目"))

        overlay.add_step("保存项目",
                         "完成编辑后点击「保存项目」将项目持久化到磁盘，\n支持 .json 格式，方便版本管理和协作。",
                         widget=find_child_by_tip(self, "保存项目"))

        # ── 流程图构建 ──
        overlay.add_step("节点工具箱",
                         "左侧工具箱列出了所有可用的视觉处理节点，\n拖拽节点到画布上即可开始构建流程图。",
                         widget=self._toolbox)

        overlay.add_step("新建流程图",
                         "点击「新建流程图」可以在项目中创建多个流程，\n点击标签页即可在不同流程之间切换。",
                         widget=find_child_by_tip(self, "新建流程图"))

        overlay.add_step("流程图编辑区",
                         "中央画布是流程图编辑区，在这里拖拽、连接节点，\n构建完整的视觉检测流水线。",
                         widget=self._diagram_tab_widget)

        # ── 运行控制 ──
        overlay.add_step("运行模式",
                         "点击「运行模式」可以循环切换执行粒度：\n按节点 → 节点+连线 → 节点+连线+端口。",
                         widget=find_child_by_tip(self, "运行模式"))

        overlay.add_step("单次执行",
                         "构建好流程图后，点击「单次执行」运行整个流程，\n每个节点依次执行，结果实时显示在右侧面板。",
                         widget=find_child_by_tip(self, "单次执行"))

        overlay.add_step("连续执行",
                         "点击「连续执行」进入连续运行模式，\n流程将反复执行，适合实时监控场景。",
                         widget=find_child_by_tip(self, "连续执行"))

        # ── 结果查看 ──
        overlay.add_step("检查结果",
                         "右侧上半部分是检查结果面板，\n包含图像预览和模块属性两个标签页。",
                         widget=self._center_tabs)

        overlay.add_step("运行结果",
                         "右侧下半部分是运行结果面板，\n按时间线展示每次执行的输出和历史记录。",
                         widget=self._bottom_tabs)

        # ── 个性化 ──
        overlay.add_step("切换主题",
                         "点击调色板按钮可以选择颜色主题，\n支持深色、浅色、科技蓝等多种风格。",
                         widget=find_child_by_tip(self, "颜色主题"))

        overlay.add_step("应用设置",
                         "点击齿轮按钮打开设置对话框，\n可以配置画布网格、系统托盘等选项。",
                         widget=find_child_by_tip(self, "设置"))

        # 启动引导
        overlay.start()

    def _show_notification(self, level: str, title: str, message: str):
        """显示桌面通知

        参数：
            level: 通知级别（Info/Warning/Error/Success）
            title: 通知标题
            message: 通知消息
        """
        # 如果系统托盘可用且支持消息
        if QSystemTrayIcon.isSystemTrayAvailable() and QSystemTrayIcon.supportsMessages():
            # 如果没有托盘图标，创建托盘图标
            if not hasattr(self, '_tray_icon'):
                self._tray_icon = QSystemTrayIcon(self)
                # 获取图标路径
                icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "logo.png")
                if os.path.exists(icon_path):
                    self._tray_icon.setIcon(QIcon(icon_path))
                self._tray_icon.show()
            # 消息图标映射
            icon_map = {"Info": 1, "Warning": 2, "Error": 3, "Success": 1}
            # 显示托盘消息
            self._tray_icon.showMessage(title, message, icon_map.get(level, 1), 3000)
        else:
            # 后备方案：在状态栏显示消息
            QMessageBox.information(self, title, message)

    def _toggle_max(self):
        # 如果当前是最大化，则还原；否则最大化
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def _on_about(self):
        QMessageBox.about(
            self,
            "关于 VisionFlow",
            "<h2>VisionFlow 2.0</h2>"
            "<p>视觉流程编辑器</p>"
            "<p>使用 Python + PyQt5 + OpenCV</p>"
            "<p>作者：JKDCPPZzz</p>"
            "<p>邮箱：1908095603@qq.com</p>"
        )

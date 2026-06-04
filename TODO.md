# VisionFlow TODO — WPF-VisionMaster 对齐清单

> 本文档对照 `WPF-VisionMaster/` 源码，逐项记录 Python (PyQt5) 版本尚未对齐的功能、UI 组件、交互行为和资源数据，按优先级排序。
>
> **最新更新**: 2026-06-04 — P0/P1/P2 全部完成。共对齐 15 个 TODO 项：左侧面板、FontIcon 系统、节点双击、缩略图、节点样式、右键菜单、工具栏、视频源、图像叠加条、模块结果过滤、历史 FontIcon 状态列、帮助 HTML、Presenter 模板体系。
>
> **变更汇总 (18 files)**: `gui/font_icons.py` (新), `gui/widgets/` (新, 3 files), `gui/presenters.py` (新), `gui/toolbox_panel.py` (重写), `gui/flow_resource_panel.py` (重写), `gui/node_editor/node_item.py` (重写), `gui/result_panel.py` (重写), `gui/node_editor/scene.py` (修改), `gui/node_editor/editor_widget.py` (修改), `gui/image_viewer.py` (修改), `gui/property_panel.py` (修改), `gui/main_window.py` (修改)

---

## 一、左侧节点栏 — GridSplitterBox 窄栏模式与阈值逻辑 ✅ COMPLETED (2026-06-04)

### 1.1 窄栏 / 宽栏双模式切换（阈值 90px） ✅

- **WPF 行为**：`GridSplitterBox` 监听 `MenuWidth.Value`，以 **90px** 为阈值在两套布局之间自动切换。
- **实现**：
  - `gui/widgets/grid_splitter_box.py` — GridSplitterBox 等价组件，含 WIDTH_THRESHOLD=90 常量
  - `gui/toolbox_panel.py` — ToolboxPanel 内部通过 `resizeEvent()` 监听宽度变化，自动在宽栏(>90px)/窄栏(≤90px)之间切换
  - 宽栏模式：标题栏「流程资源」+ 搜索框 + 树/网格双视图 + 统计底栏
  - 窄栏模式：紧凑的垂直图标列表（_NarrowNodeButton，28×28 带颜色图标）
  - 视图持久化：QSettings 存储 VIEW_MODE_KEY

### 1.2 TreeView 视图 ✅

- **WPF 行为**：`TreeViewPresenter` 使用 `HierarchicalDataTemplate`，按分组 → 节点两层展示 Name + Description。
- **实现**：
  - `gui/toolbox_panel.py:_create_tree()` — QTreeWidget 两列（模块名称 | 描述）
  - 分组标题加粗着色，节点项带 tooltip 和 UserRole 数据
  - 支持拖拽到画布（setDragEnabled(True)）
  - 点击选中节点（itemClicked → node_type_selected 信号）
  - 双击添加节点到画布（itemDoubleClicked → node_type_selected 信号）
  - 默认展开所有分组（expandAll()）

### 1.3 收藏 + 搜索 + 最近使用 ✅

- **WPF 行为**：`FavoriteBox` 收藏夹 + 搜索过滤 + 节点使用统计。
- **实现**：
  - 收藏：`is_favorite()` / `add_favorite()` / `remove_favorite()` / `toggle_favorite()`，QSettings 持久化
  - 最近使用：`record_use()` + `_recents` 列表（MAX_RECENTS=10），在收藏组上方显示「🕐 最近使用」组
  - 搜索：`_search_box` QLineEdit，实时过滤（textChanged → refresh()），匹配 display_name + description + type_name + group_name
  - MainWindow 中 `_on_node_type_selected` 调用 `self._toolbox.record_use(type_name)` 记录使用
  - 统计底栏：分组数 · 节点数 · ★ 收藏数 · 🕐 最近数

### 新增文件

| 文件 | 说明 |
|------|------|
| `gui/font_icons.py` | FontIcons 常量类（70+ 图标码点）+ FontIconButton / FontIconToggleButton / FontIconTextBlock |
| `gui/widgets/__init__.py` | widgets 包初始化 |
| `gui/widgets/grid_splitter_box.py` | GridSplitterBox 等价组件（阈值切换、Mode=Extend） |
| `gui/widgets/node_list_view.py` | 独立的 NodeListView 组件（可脱离 ToolboxPanel 使用） |

### 修改文件

| 文件 | 变更 |
|------|------|
| `gui/toolbox_panel.py` | 完全重写：集成双视图切换（树/网格）、窄栏模式、收藏、最近使用、搜索、FontIconToggleButton |
| `gui/main_window.py` | `_on_node_type_selected` 增加 `self._toolbox.record_use(type_name)` 调用 |

---

## 二、FontIcon 系统 — 一键复刻 WPF 图标体系

### 2.1 FontIcon 字体图标系统 ✅ COMPLETED (2026-06-04)

- **WPF 行为**：全局使用 `FontIcons` 静态类（Segoe Fluent Icons / MDL2 字体），以 Unicode 码点表示图标。
- **实现**：
  - `gui/font_icons.py` — FontIcons 类，70+ 常量（Replay/Delete/Cancel/OpenFolderHorizontal/PageLeft/PageRight/Error/Completed/Info/Photo2/AlignLeft/CaretBottomRightSolidCenter8 等）
  - `FontIconButton(QPushButton)` — 支持 icon-only / icon+text 模式，WPF Command/Default 样式键
  - `FontIconToggleButton(QPushButton[checkable])` — checked_icon / unchecked_icon 双字形，WPF Switch 样式键
  - `FontIconTextBlock(QLabel)` — 纯图标标签，支持 set_icon() / set_color()
  - `FontIconTextBlockWithText(QWidget)` — 图标+文字组合控件
  - 自动检测系统可用 Segoe 图标字体（Segoe Fluent Icons → Segoe MDL2 Assets → Segoe UI Symbol）
  - 已应用于 ToolboxPanel 的树/网格切换按钮

### 2.2 FontIconToggleButton Switch 样式 ✅ COMPLETED (2026-06-04)

- **WPF 行为**：带 `CheckedGlyph` / `UncheckedGlyph` 属性的 ToggleButton。
- **实现**：`FontIconToggleButton(checked_icon, unchecked_icon)` 支持 checked/unchecked 双字形，`toggled` 信号自动切换显示。已在左侧面板「流程资源」Header 中使用。

### 2.3 WPF Presenter 模板体系 ✅ COMPLETED (2026-06-04)

- **WPF 行为**：`DataTemplate` + `ContentPresenter` MVVM 视图注入。
- **实现**（`gui/presenters.py` 新建）：
  - `PresenterRegistry` — type→QWidget factory 映射，`isinstance()` 匹配（类似 WPF DataType）
  - `ContentPresenter(QWidget)` — `set_content(obj)` 自动解析类型→创建嵌入 Presenter
  - `DefaultTextPresenter` — 回退视图（显示 `str(obj)`）
  - 内置注册：`VisionNodeData → PropertyPanel(group_filter=[RESULT_PARAMETERS])`, `ROIBase → ROI info label`
  - 支持 `set_fallback()` 注册全局回退工厂

---

## 三、节点双击弹出设置面板

### 3.1 节点双击 → ShowViewCommand / ShowTabEditCommand ✅ COMPLETED (2026-06-04)

- **WPF 行为**：工具栏有 `FontIconButton Command="{h:ShowViewCommand}"` 打开节点属性编辑面板。
- **实现**：
  - `DiagramEditorWidget` 新增 `node_double_clicked` 信号
  - `_on_node_item_added` 连接 `node_item.node_double_clicked → self.node_double_clicked`
  - `MainWindow._wire_diagram_editor` 连接 `editor.node_double_clicked → _on_editor_node_double_clicked`
  - 双击行为：选中节点 → 切换到「模块结果」Tab（index=1）→ PropertyPanel 第一个 GroupBox 边框 350ms 橙色闪烁
  - `PropertyPanel.flash_highlight()` 方法：查找第一个 QGroupBox，临时设置 #ff9800 样式后恢复

### 3.2 节点右键菜单增强 ✅ COMPLETED (2026-06-04)

- **WPF 行为**：节点右键菜单包含编辑/运行/删除/帮助等完整选项。
- **实现**：
  - `DiagramScene` 新增 `node_properties_requested` / `node_help_requested` 信号
  - 菜单项：▶ 运行此节点 | 分隔 | ⚙ 属性... | 📋 复制 | 分隔 | 🗑 删除节点 | ⊘ 禁用节点 | 分隔 | ? 帮助
  - 禁用项为 checkable（勾选=禁用，取消=恢复 IDLE 状态）
  - 属性 → `MainWindow._on_editor_node_double_clicked`（切换模块结果Tab + 闪烁）
  - 帮助 → `MainWindow._on_editor_node_help_requested`（切换帮助Tab + 显示节点帮助）
  - 信号链：`DiagramScene → DiagramEditorWidget → MainWindow`

---

## 四、图像显示 — 加载文件夹后缩略图不显示

### 4.1 底部图像源缩略图条 ✅ COMPLETED (2026-06-04)

- **WPF 行为**：底部 Expander「图像源」+ 75×75 水平缩略图 ListBox + PageLeft/PageRight 翻页 + 工具栏。
- **实现**（`gui/flow_resource_panel.py` 完全重写）：
  - `ThumbnailLoader(QThread)` — 后台线程异步加载 cv2.imread → QPixmap 缩略图，通过 `thumbnail_ready` 信号回传主线程
  - `ThumbnailButton(QPushButton)` — 75×75 自定义绘制按钮，显示缩略图 QPixmap，支持选中高亮（蓝色边框 #0078d4），双击发射 `double_clicked_path`
  - Header 栏：标题「图像源」+ 序号「1/10」+ 「运行全部」「自动切换」ToggleButton + FontIcon 按钮组（添加文件/文件夹/删除/清空）
  - ScrollArea：水平滚动 + Shift+wheel 横向滚动（WPF 行为）+ PageLeft/PageRight 浮动翻页按钮
  - MainWindow 连线：`file_selected` → 主图预览 + `file_double_clicked` → 全屏适应视图

### 4.2 视频源面板 ✅ COMPLETED (2026-06-04)

- **WPF 行为**：视频源显示缩略图 + 文件名 + 文件大小。
- **实现**：
  - `VIDEO_EXTENSIONS` 集合（10 种视频格式）：`.avi .mp4 .mkv .mov .wmv .flv .webm .m4v .mpg .mpeg`
  - `ThumbnailLoader._capture_video_frame()` — 使用 `cv2.VideoCapture` 抓取第一帧作为缩略图
  - 文件大小显示：header 序号旁显示 `[12.3 MB]` 或 `[456 KB]`

### 4.3 图像区叠加信息条 ✅ COMPLETED (2026-06-04)

- **WPF 行为**：图像区底部半透明信息条（文件名 | 尺寸 | 文件大小 | 修改时间）。
- **实现**：
  - `ImageViewerPanel.set_image_info(file_path, pixel_w, pixel_h)` — 格式化显示：`filename | 1920×1080 | 1.2 MB | 2024-01-15 14:30:00`
  - `MainWindow._on_resource_file_selected` 传入像素尺寸
  - `_update_image_context` 解析源节点 pixel_width/pixel_height 属性

---

## 五、画布节点样式 — 对齐 WPF StyleNodeDataBase 模板 ✅ COMPLETED (2026-06-04)

### 5.1 WPF 节点模板 ✅ 已实现

- **WPF `StyleNodeDataBase` DataTemplate** 结构：
  - 左侧 30px 宽色条（BAR_WIDTH=30），只在 Running/Success/Error 时显示，内嵌 FontIcon（白色）
  - IDLE 状态：色条隐藏，仅 3px 细线提示分组颜色
  - 选中：橙色边框 #FF8C00（WPF BrushKeys.Orange）
  - 悬停：蓝色边框 #0078d4（WPF Foreground brush）
  - 文字：QFontMetrics 精确测量 + elidedText 省略
- **实现**（`gui/node_editor/node_item.py` 完全重写）：
  - `_draw_left_bar()` — 30px 色条 + FontIcon 居中绘制；状态 Running/Success/Error 时全宽色条 + 白色图标；IDLE 时 3px 细线提示
  - `_resolve_node_icon()` — 按类型层次查找图标（NODE_ICONS 字典 + GROUP_META_ICONS 回退）
  - 边框颜色：选中 #FF8C00 / 悬停 #0078d4 / 错误 #f44336 / SOURCE 模板分组色 / 默认 #555
  - `_compute_size()` — QFontMetrics.boundingRect() 精确文字宽度
  - `icon_font()` 字体渲染 FontIcon 字符

### 5.2 具体实现项

1. ✅ **节点图标** — `_resolve_node_icon()` 按 NodeBase 类型层次 + 分组颜色查找 FontIcons 码点
2. ✅ **30px 色条 + 图标** — BAR_WIDTH=30，_draw_left_bar() 状态感知
3. ✅ **选中/悬停** — NODE_BORDER_SELECTED=#FF8C00, NODE_BORDER_HOVER=#0078d4
4. ✅ **状态点指示器** — 保留右上角圆点，色条+指示器双重指示
5. ✅ **文字宽度** — QFontMetrics.boundingRect() 精确测量
6. ✅ **端口样式** — SocketItem #FF8C00 橙色，已对齐

---

## 六、右侧面板 — 模块结果 + 历史 + 帮助 ✅ COMPLETED (2026-06-04)

### 6.1 模块结果 Tab ✅

- **WPF 行为**：`TabItem「模块结果」` 显示 `GroupBox` 标题 + `Form SelectObject` 属性表单（仅 `ResultParameters` 组）。
- **实现**：
  - `PropertyPanel.__init__` 新增 `group_filter: list[str] | None` 和 `readonly: bool` 参数
  - `_do_refresh()` 按 group_filter 过滤属性分组
  - `_is_readonly()` 合并 force_readonly + Property.readonly 双重检查
  - `presenters.py` 注册 `VisionNodeData → PropertyPanel(group_filter=[RESULT_PARAMETERS], readonly=True)`

### 6.2 历史结果 Tab ✅

- **WPF 行为**：`DataGrid` 四列，结果数据列含 FontIcon 状态图标 + 消息文本。选中行 → 更新主图。
- **实现**：
  - `IconTextDelegate(QStyledItemDelegate)` — 自定义 draw 方法绘制 FontIcon + elidedText 文本
  - `STATE_ICONS` / `STATE_COLORS` 字典：Success→Completed(green), Error→Error(red), Warning→Warning(orange)
  - `add_to_history()` — 执行完成时记录，含 node_id+state+time+message
  - `_on_history_cell_clicked` — 发射 `image_update_requested` → MainWindow 更新主图
  - `node_executed` 信号链：DiagramEditorWidget → MainWindow → ResultPanel.add_to_history

### 6.3 帮助 Tab ✅

- **WPF 行为**：模块名称、功能描述、HelpPresenter 可点击超链接。
- **实现**：
  - `ResultPanel.show_help()` — 生成完整 HTML 帮助页：FontIcon 图标标题、类型/描述/继承链、参数表、在线文档超链接（setOpenExternalLinks）
  - 从 `HelpNodeDataBase.create_help_presenter()` 读取 help_info dict
  - 参数表按 Property 描述符自动生成

### 6.4 当前模块结果 Tab ✅

- **WPF 行为**：`ResultNodeData.ResultPresenter` + `ZoomToRectCommand`。
- **实现**：`_on_current_result_clicked` → ImageViewer 添加 overlay + zoom_to_rect 动画（已对齐）

---

## 七、工具栏 — FontIcon 命令按钮 ✅ COMPLETED (2026-06-04)

### 7.1 标题栏 / 命令栏 ✅

- **WPF 行为**：两行标题栏全部使用 FontIconButton。
- **实现**：
  - Row1 操作按钮：⚙→FontIcons.Setting / 🎨→FontIcons.Color / ℹ→FontIcons.Info / 📖→FontIcons.Help
  - Row2 命令栏：▶→FontIcons.Replay / ■→FontIcons.Stop / ↩→FontIcons.Undo / ↪→FontIcons.Redo
  - 状态栏：●→FontIcons.Completed (空闲) / Sync (运行中) / Error (错误)
  - DiagramEditorWidget 工具栏：全部替换为 FontIconButton（运行/停止/撤销/重做/复制/粘贴）
  - Diagram Tab corner：+→FontIcons.Add / ▶→FontIcons.Replay / ■→FontIcons.Stop / ↺→FontIcons.Refresh
  - _DiagramTabHeader：▣→FontIcons.Photo2 / ▶→FontIcons.Replay / ■→FontIcons.Stop / ↺→FontIcons.Refresh

### 7.2 运行模式按钮

- **WPF 行为**：RunDiagramDataPresenter 中的大按钮（Replay/Sync/Stop）+ OK/NG 标识。
- **Python 现状**：暂无（WPF 中为独立 Run 页面，非主编辑界面）。

---

## 八、流程图多标签系统

### 8.1 Tab 头部内联控件 ✅ COMPLETED (2026-06-04)

- **WPF 行为**：Tab 头部 FontIconTextBlock(Photo2) + 可编辑 TextBox + 小按钮。
- **实现**：
  - Tab 图标 `▣` → `FontIconTextBlock(FontIcons.Photo2)`
  - Corner 按钮 → `FontIconButton(FontIcons.Add)`
  - 内联按钮 → `FontIcons.Replay`/`FontIcons.Stop`/`FontIcons.Refresh`

### 8.2 流程图切换的独立画布

- **WPF 行为**：`TabControl` 的 `ContentTemplate` 中包含 `Zoombox` + `ContentPresenter`，每个 Tab 有独立画布和缩放状态。
- **Python 现状**：`_create_diagram_page()` 为每个流程图创建独立的 `DiagramEditorWidget`（含 Scene + View），支持独立画布。基本对齐。
- **需要做的**：确认每个 Tab 切换时正确保存/恢复各自的缩放和滚动位置。

---

## 九、项目系统

### 9.1 默认示例项目

- **WPF 行为**：`Assets/DefaultProjects/` 下有 29 个示例项目 JSON 文件，首次启动自动加载。
- **Python 现状**：`assets/projects/` 下有 10 个示例项目，数量不足。
- **需要做的**：
  1. 从 WPF 复制全部 29 个示例项目 JSON 到 `assets/projects/`。
  2. 适配 JSON 格式差异（WPF 使用 `$type` 字段标识类型，Python 使用 `type`）。

### 9.2 最近项目列表

- **WPF 行为**：文件菜单中的「最近的项目」子菜单，使用 `IocProject.Instance.Collection` 数据源，每个 item 50px 高度、400px 最小宽度。
- **Python 现状**：`_refresh_recent()` 已实现基本功能。
- **需要做的**：添加「固定到最近列表」功能（WPF 中使用 `FavoriteProjectCommand`）。

### 9.3 项目设置对话框

- **WPF 行为**：`ShowEditProjectCommand` 打开项目属性编辑（名称、描述、创建时间等）。
- **Python 现状**：无项目属性编辑对话框。
- **需要做的**：创建 `ProjectSettingsDialog(QDialog)`，编辑项目名称、描述、作者等元数据。

---

## 十、缩放/平移 — Zoombox 行为对齐

### 10.1 流程图 Zoombox

- **WPF 行为**：
  - `Zoombox` 包裹 `ContentPresenter`，ZoomOn="Content"，默认 Fit 视图。
  - `ZoomBoxFitOnLoadedBehavior` / `ZoomBoxFitOnSizeChangedBehavior` 自动适应。
  - 双击 → 调用 `FitToBounds()`。
  - 右键双击 → Fit。
- **Python 现状**：`DiagramEditorView` 实现了 Ctrl+滚轮缩放、中键拖动平移、Shift+左键框选。但缺少双击适应功能。
- **需要做的**：
  1. 双击画布空白区域 → `fit_to_window()`。
  2. 右键双击 → Fit（对齐 WPF）。
  3. 加载完成和窗口大小改变时自动 `FitToBounds`。

### 10.2 图像 Zoombox

- **WPF 行为**：`Zoombox` 带 `Tile25` 棋盘格背景，`ViewStack` 默认 Fit，双击图像 → `ShowZoomViewImageCommand`。
- **Python 现状**：`ImageViewer` 实现了滚轮缩放、中键拖动、双击适应。基本对齐。
- **需要做的**：添加棋盘格背景（透明区域用 `Tile25` 样式）。

---

## 十一、资源数据 — 示例图像、ONNX 模型

### 11.1 默认示例图像

- **WPF 行为**：`H.VisionMaster.NodeData/bin/Debug/net8.0-windows/Data/Image/` 下有 20+ 张示例图像（lenna、box、circle、penguin、shapes、Squares 系列、tsukuba 等）。
- **Python 现状**：`assets/images/` 目录存在，但图像数量未知。
- **需要做的**：
  1. 从 WPF 复制全部示例图像到 `assets/images/`。
  2. 确保 `SrcFilesVisionNodeData.load_default()` 能正确加载。

### 11.2 ONNX 模型文件

- **WPF 行为**：`Assets/Onnx/` 下有 5 个 ONNX 模型 + 标签文件。
- **Python 现状**：需要确认 `assets/models/` 中是否有对应文件。
- **需要做的**：复制 ONNX 模型和标签文件，确保 ONNX 节点能正常运行。

---

## 十二、杂项 — 其他未对齐项

### 12.1 日志面板

- **WPF 行为**：状态栏显示当前状态图标（绿色/红色/蓝色）+ 消息文本 + 用时。
- **Python 现状**：`LogPanel` + `statusBar()` 有基本实现。
- **需要做的**：状态栏加入 FontIcon 图标。

### 12.2 消息中心 / 通知

- **WPF 行为**：`ShowDialogNotifyMessageOutputNodeData` 等 7 种通知输出节点（Info/Success/Warn/Error/Fatal/Dialog）。
- **Python 现状**：`nodes/outputs/output_nodes.py` 有输出节点，但未实现桌面通知弹窗。
- **需要做的**：实现 `QSystemTrayIcon` 通知或 `QMessageBox` 弹窗。

### 12.3 全屏 ROI 绘制

- **WPF 行为**：`DrawROI` 的 DataTemplate 中有「全屏绘制」按钮，点击后展开为全屏 Zoombox 编辑 ROI。
- **Python 现状**：`RoiEditorDialog` 有基础实现，但无全屏模式。
- **需要做的**：`RoiEditorDialog` 添加全屏切换按钮。

### 12.4 流程图消息历史

- **WPF 行为**：底部状态栏显示流程图运行状态（Error/Success/Running）+ 当前消息 + 用时。
- **Python 现状**：`_diagram_status_strip` 已实现。
- **需要做的**：添加用时显示（`TimeSpan` 格式化）。

### 12.5 主题切换

- **WPF 行为**：`FontIconButton Command="{ShowColorThemeViewCommand}"` 和 `ISwitchThemeViewPresenter`，支持亮色/暗色主题动态切换。
- **Python 现状**：`gui/theme.py` 有 `theme_manager`，但只有一套暗色主题。
- **需要做的**：添加亮色主题配色方案，支持运行时切换。

### 12.6 右键长按拖拽画布

- **WPF 行为**：`Zoombox` 支持按住右键拖拽平移。
- **Python 现状**：`ImageViewer` 支持右键拖拽平移，`DiagramEditorView` 仅支持中键拖拽平移。
- **需要做的**：`DiagramEditorView` 也支持右键拖拽平移（当前右键用于上下文菜单，需 Shift+右键 或配置项切换）。

---

## 优先级排序建议

| 优先级 | 模块 | 状态 |
|--------|------|------|
| **P0** | ~~节点双击弹出设置面板（第三节）~~ | ✅ 已完成 (2026-06-04) |
| **P0** | ~~图像缩略图条（第四节 4.1）~~ | ✅ 已完成 (2026-06-04) |
| **P0** | ~~画布节点样式（第五节）~~ | ✅ 已完成 (2026-06-04) |
| **P1** | ~~FontIcon 系统（第二节）~~ | ✅ 已完成 (2026-06-04) |
| **P1** | ~~GridSplitterBox 窄栏/宽栏（第一节）~~ | ✅ 已完成 (2026-06-04) |
| **P1** | ~~节点右键菜单增强（第三节 3.2）~~ | ✅ 已完成 (2026-06-04) |
| **P2** | ~~历史结果面板完善（第六节 6.2）~~ | ✅ 已完成 (2026-06-04) |
| **P2** | ~~Presenter 模板体系（第二节 2.3）~~ | ✅ 已完成 (2026-06-04) |
| **P2** | ~~工具栏 FontIcon 化（第七节）~~ | ✅ 已完成 (2026-06-04) |
| **P3** | 示例项目 + ONNX 模型（第十一节） | ⬜ 待实施 |
| **P3** | 主题切换（第十二节 12.5） | ⬜ 待实施 |
| **P4** | 全屏 ROI / 通知 / 杂项 | ⬜ 待实施 |

---

## 实施路线图

### ✅ 第一阶段 (2026-06-04)：基础设施（已全部完成）
1. ✅ FontIcon 系统 + FontIconButton / ToggleButton / TextBlock
2. ✅ GridSplitterBox 等价组件
3. ✅ ToolboxPanel 树/网格双视图 + 窄栏 + 收藏 + 最近 + 搜索

### ✅ 第二阶段 (2026-06-04)：核心交互修复（已全部完成 P0）
4. ✅ 节点双击 → 属性面板切换 + 闪烁高亮
5. ✅ FlowResourcePanel 75×75 缩略图 + 异步加载 + PageLeft/Right 翻页
6. ✅ NodeItem 30px 色条 + FontIcon + 橙色选中边框 + 蓝色悬停边框
5. 重构左侧面板为 `GridSplitterBox` 等价组件，实现 90px 阈值双模式切换。
6. 全局替换 emoji 图标为 FontIcon 引用。

### ✅ 第三阶段 (2026-06-04)：面板完善（已全部完成 P2）
7. ✅ 右侧面板三 Tab — PropertyPanel 分组过滤 + 历史 FontIcon 状态列 + 帮助 HTML 超链接
8. ✅ PresenterRegistry + ContentPresenter 模板体系
9. ✅ 工具栏 FontIcon 化

### 第四阶段：内容与体验（P3-P4）
10. 复制示例项目、图像、ONNX 模型。
11. 主题切换、全屏 ROI、桌面通知等。

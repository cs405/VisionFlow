# VisionFlow TODO — WPF-VisionMaster 对齐清单

> 本文档对照 `WPF-VisionMaster/` 源码，逐项记录 Python (PyQt5) 版本尚未对齐的功能、UI 组件、交互行为和资源数据，按优先级排序。
>
> **最新更新**: 2026-06-04 — 第一节（1.1-1.3）全部完成，第二节（2.1-2.2）完成。新增 `gui/font_icons.py`、`gui/widgets/` 包。

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

### 2.3 WPF Presenter 模板体系

- **WPF 行为**：大量使用 `DataTemplate` + `ContentPresenter` 进行 MVVM 驱动的视图注入（如 `ResultPresenter`、`PropertyPresenter`、`HelpPresenter`、`ROIPresenter`）。
- **Python 现状**：使用 `set_node()` + `QWidget` 重建方式，没有模板/视图注入体系。
- **需要做的**：
  1. 设计 `PresenterRegistry`：`type -> QWidget factory` 映射，类似 WPF `DataTemplate.DataType`。
  2. 实现 `ContentPresenter` 等价组件：根据绑定对象的类型自动解析并创建对应 Presenter Widget。
  3. 为以下 WPF Presenter 创建对应 Python 版本（见第五章）。

---

## 三、节点双击弹出设置面板

### 3.1 节点双击 → ShowViewCommand / ShowTabEditCommand

- **WPF 行为**：工具栏有 `FontIconButton Command="{h:ShowViewCommand}"` 和 `Command="{h:ShowTabEditCommand}"`，参数为 `SelectedPartData`（当前选中的节点）。点击后在右侧「模块结果」面板打开该节点的属性编辑表单，或在独立 Tab 中打开。
- **Python 现状**：
  - `NodeItem` 已经发出 `node_double_clicked` 信号（`node_item.py:397`）。
  - **但没有任何地方连接这个信号！** `DiagramEditorWidget` 和 `MainWindow` 都未处理双击。
  - 当前通过单击节点 → `_select_node()` → `PropertyPanel.set_node()` 显示属性，但双击无额外行为。
- **需要做的**：
  1. 在 `DiagramScene.node_item_added` 或 `DiagramEditorWidget._on_node_item_added` 中连接 `node_double_clicked` 信号。
  2. `MainWindow` 处理双击：
     - 切换到右侧「模块结果」Tab。
     - 将 `PropertyPanel` 滚动到顶部并聚焦。
     - 高亮该节点的属性分组标题（短暂闪烁动画）。
  3. 可选：双击时弹出独立 `QDialog` / 浮动面板（对齐 WPF `ShowTabEditCommand` 行为），包含完整属性表单 + 帮助 + 结果预览。

### 3.2 节点右键菜单增强

- **WPF 行为**：节点右键菜单包含「编辑属性」「运行」「禁用」「复制」「删除」「帮助」等选项。
- **Python 现状**：右键菜单仅有「删除」「单步执行」「复制」「禁用」。
- **需要做的**：
  1. 添加「属性...」→ 触发与双击相同的编辑面板。
  2. 添加「帮助」→ 切换到帮助面板并显示该节点帮助。
  3. 添加「运行此节点」快捷入口。

---

## 四、图像显示 — 加载文件夹后缩略图不显示

### 4.1 底部图像源缩略图条

- **WPF 行为**：`MainWindow.xaml` 底部有一个 `Expander`「图像源」，打开后显示：
  - 水平 `ListBox`，`ItemTemplate` 为 75×75 的图像缩略图（`Image Source="{Binding ., Converter={GetImageSourceFromFilePathConverter}}"`）。
  - 自定义 `ControlTemplate`：`ScrollViewer` + 左右 `FontIconButton` 翻页按钮（`PageLeft` / `PageRight`）。
  - 水平鼠标滚轮支持（`ScrollViewerBebavior UseHorizontalMouseWheel="True"`）。
  - 工具栏按钮：添加文件（``）、添加文件夹（`OpenFolderHorizontal`）、删除（`Cancel`）、清空（`Delete`）。
  - ToggleButton：「运行全部」「自动切换」。
  - 当前选中文件序号显示：「图像源 1/10」。
- **Python 现状**：
  - `FlowResourcePanel` 有基础结构但 **使用 `QListWidget` 显示文本文件名而非缩略图**。
  - 翻页按钮存在但未与 `ScrollViewer` 行为对齐。
  - 面板默认隐藏，只在选择 `SrcFilesVisionNodeData` 节点时才显示（这倒是对的）。
- **需要做的**：
  1. 将 `QListWidget` 替换为自定义水平滚动缩略图组件：
     - 每个 item 为 75×75 的 `QPixmap` 缩略图（使用 `cv2.imread` + `numpy_to_pixmap` 加载）。
     - 异步加载缩略图（`QThread` / `QRunnable`）避免 UI 卡顿。
     - 鼠标悬停显示文件路径 tooltip。
  2. 实现自定义水平 `QScrollArea` + 左右翻页按钮（`QPushButton` 叠加在滚动区域两侧）。
  3. 支持 Shift+滚轮水平滚动。
  4. 双击缩略图 → 弹出独立大图查看器（对齐 WPF `ShowZoomViewImageFileCommand`）。
  5. 文件选择时同步更新主图像视图（选中即预览，对齐 WPF `ImageFileSelectionChangedCommand`）。
  6. 「运行全部」「自动切换」Toggle 按钮样式改为 WPF 风格（扁平边框，选中高亮）。

### 4.2 视频源面板

- **WPF 行为**：`DataTemplate DataType="{x:Type SrcVideoFilesNodeData}"`，显示缩略图 + 文件名 + 文件大小。
- **Python 现状**：`FlowResourcePanel._refresh_list()` 中有 `is_video` 判断但显示文本 `🎬` emoji 而非缩略图。
- **需要做的**：
  1. 视频文件也显示缩略图（使用 `cv2.VideoCapture` 抓取第一帧）。
  2. 显示文件大小信息（`[12.3 MB] filename.mp4`）。

### 4.3 图像区叠加信息条

- **WPF 行为**：图像区顶部有结果类型角标（「无结果」「图像源<xxx>」「输出结果<xxx>」），底部有文件信息条（文件名 | 尺寸 | 修改时间），背景为半透明黑色。
- **Python 现状**：`ImageViewerPanel` 有 `_result_badge`、`_file_info_strip` 等覆盖层组件，但实际数据显示不完整。
- **需要做的**：
  1. 完善结果角标逻辑：`ImageFileSelectionChangedCommand` 对应更新角标文字。
  2. 底部信息条补齐：图像尺寸（像素）、文件大小（KB/MB）、最后修改时间。
  3. 重叠层使用 `QStackedLayout` (当前已有)，确保鼠标穿透正常。

---

## 五、画布节点样式 — 对齐 WPF StyleNodeDataBase 模板

### 5.1 WPF 节点模板（核心差异）

- **WPF `StyleNodeDataBase` DataTemplate** (`H.VisionMaster.NodeData/Themes/Generic.xaml:19-101`)：
  - 整体结构：`Border` + `DockPanel`，左侧 30px 宽色条 + 右侧文字。
  - 左侧色条：
    - 宽度 30px，颜色绑定到 `BorderBrush`（即状态色）。
    - 内部居中放置 `FontIconTextBlock`，图标绑定到 `{Binding Icon}`。
    - 状态着色：Running/Success/Error 时色条显示，前景图标变白色；其他状态色条隐藏。
  - 右侧文字：`TextBlock` 绑定 `{Binding Text}`，带 `TextTrimming="CharacterEllipsis"`。
  - 状态样式：
    - 默认：白底黑字，`IsMouseOver` → 浅灰背景 + 前景色边框。
    - `IsSelected=True` → 橙色边框 + 浅灰背景。
    - 状态边框基于 `DiagramKeys.StateBorder`。
- **Python `NodeItem` 现状**（`node_item.py`）：
  - 简单的圆角矩形 + 6px 宽左侧色条 + 标题文字。
  - **没有 FontIcon 图标**。
  - **没有鼠标悬停边框颜色变化**。
  - **没有选中时橙色边框**。
  - **状态色条不显示图标，仅颜色变化**。
  - 使用了自定义 `NodeTemplate` 枚举（SOURCE/CONDITION/OUTPUT/DEFAULT），但样式过于简化。

### 5.2 需要修改的具体项

1. **节点图标**：
   - 在 `NodeBase` 中添加 `icon` 属性（对应 WPF `{Binding Icon}`），返回 FontIcon 码点字符串。
   - 每种节点类型（数据源、预处理、滤波等）设置对应图标（`FontIcons.Photo2`、`FontIcons.Color` 等）。
   - `NodeItem._draw_flag()` 内嵌 `FontIconTextBlock` 图标绘制。

2. **左侧色条 + 图标**：
   - 色条宽度从 6px 改为 30px（对齐 WPF）。
   - 色条内部居中绘制图标（使用 QPainter 绘制字体图标）。
   - 状态 Running/Success/Error 时，色条显示 + 图标变白色；Idle 状态色条隐藏（仅显示细线或完全隐藏）。

3. **选中 / 悬停样式**：
   - 选中时：橙色边框（`#FF8C00`），浅灰背景（`#E0E0E0`）。
   - 悬停时：边框变为前景色（`#0078d4`），背景变浅。
   - 默认：白底/深灰底 + 深色文字。

4. **状态点指示器**：
   - 当前 Python 有 state indicator dot（右上角的圆点），保留但调整位置。
   - WPF 状态通过色条颜色体现，Python 可保留点+色条双重指示。

5. **节点宽度自适应**：
   - WPF 节点宽度由 `TextBlock` 内容自动拉伸 + `MinWidth`。
   - Python 当前使用 `CHAR_WIDTH * len(title)` 估算，不太准确。
   - 使用 `QFontMetrics.boundingRect()` 精确测量文字宽度。

6. **端口样式**：
   - WPF 端口为小圆点（白色填充 + 橙色边框）。
   - Python `SocketItem` 已有关联颜色（`#FF8C00` 橙色），确认对齐。

---

## 六、右侧面板 — 模块结果 + 历史 + 帮助

### 6.1 模块结果 Tab

- **WPF 行为**：`TabItem「模块结果」` 显示 `GroupBox` 标题「模块名称 <xxx>」，内容为 `Form SelectObject="{Binding ResultNodeData}"` 动态属性表单。
- **Python 现状**：`PropertyPanel` 显示选中节点的属性表单，标题「模块名称 <xxx>」已实现。但缺少 WPF Form 的 `UseGroupNames` 过滤（只显示 `ResultParameters` 组）。
- **需要做的**：`PropertyPanel` 支持按 `PropertyGroupNames` 过滤，模块结果面板只显示 `RESULT_PARAMETERS` 组的属性（只读），完整属性面板显示所有可编辑组。

### 6.2 历史结果 Tab

- **WPF 行为**：`DataGrid` 四列：「执行序号」「执行时间」「模块」「结果数据」。结果数据列带 `FontIconTextBlock` 状态图标（`Info`/`Error`/`Completed`）+ 消息文本。选中历史行更新右侧结果图。
- **Python 现状**：`ResultPanel` 有基本表格实现，但缺少状态图标列和完整的选中联动。
- **需要做的**：
  1. 历史表格添加状态图标列（FontIcon）。
  2. 选中历史行 → 更新图像显示（`ResultImageSource`）。
  3. 结果数据列合并图标+文本（使用自定义 delegate）。

### 6.3 帮助 Tab

- **WPF 行为**：`TabItem「帮助」` 显示模块名称、功能描述、`HelpPresenter`（可点击的文档超链接）。
- **Python 现状**：`HelpPanel` 和 `ResultPanel._help_edit` 有基本显示，但未集成到主帮助面板。
- **需要做的**：
  1. 统一帮助显示入口。
  2. 支持可点击的超链接（使用 `QLabel.setOpenExternalLinks(True)`）。
  3. 从 `HelpNodeDataBase.create_help_presenter()` 读取帮助数据。

### 6.4 当前模块结果 Tab

- **WPF 行为**：`TabItem「当前模块结果」` 显示 `ResultNodeData.ResultPresenter`，支持 `PreviewMouseLeftButtonDown` → `ZoomToRectCommand`（点击结果矩形 → 在主图像上定位）。
- **Python 现状**：`ResultPanel._current_table` 有基本实现，支持点击几何 item 在图像上画 overlay + zoom to rect。
- **需要做的**：确认 `ZoomToRectCommand` 行为一致（已有 `ImageViewer.zoom_to_rect` 动画）。

---

## 七、工具栏 — FontIcon 命令按钮

### 7.1 标题栏 / 命令栏

- **WPF 行为**：两行标题栏：
  - 第一行：菜单栏（文件/编辑/运行/系统/帮助） + 操作按钮（主题、设置、关于、指南）+ 最小化/最大化/关闭。
  - 第二行：`ItemsControl` 绑定 `Commands`（新建/打开/保存），`SelectedDiagramData.Commands`（启动/停止/重置），全部使用 `FontIconButton`。
- **Python 现状**：`_setup_caption_bar()` 有两行布局，但使用文本按钮 + emoji 图标，没有数据绑定驱动。
- **需要做的**：
  1. 第二行工具栏按钮改为 `FontIconButton`。
  2. 支持 `ItemsControl` 风格的命令绑定（从 Workflow/DiagramData 的命令列表动态生成按钮）。

### 7.2 运行模式按钮

- **WPF 行为**：`RunDiagramDataPresenter.xaml` 中的大按钮：「启动」(Replay, FontSize=80) / 「启动全部」(Sync, FontSize=80) / 「停止」(⏹, FontSize=80)，右侧还有 OK/NG 结果大标识。
- **Python 现状**：只有小工具栏按钮「▶ 运行」「■ 停止」。
- **需要做的**：暂无（此功能在 WPF 中为独立 Run 页面，非主编辑界面）。

---

## 八、流程图多标签系统

### 8.1 Tab 头部内联控件

- **WPF 行为**：每个 Tab 头部包含：
  - `FontIconTextBlock`（Photo2 图标）+ 可双击编辑的 `TextBox` 名称 + 三个小 `FontIconButton`（启动/停止/重置，仅选中 Tab 可见）。
  - 右侧 Corner 有 `FontIconButton`「+」添加流程图。
- **Python 现状**：`_DiagramTabHeader` 在 `QTabBar.LeftSide` 使用自定义 QWidget，有 QLineEdit 名称编辑 + 启动/停止/重置小按钮。但图标是 ▣ emoji 而非 FontIcon。
- **需要做的**：
  1. Tab 图标从 `▣` emoji 改为 `FontIcons.Photo2`。
  2. Corner 添加「+」按钮（当前已有 `QPushButton("+")`，改为 FontIcon）。

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
| **P0** | 节点双击弹出设置面板（第三节） | ⬜ 待实施 |
| **P0** | 图像缩略图条（第四节 4.1） | ⬜ 待实施 |
| **P0** | 画布节点样式（第五节） | ⬜ 待实施 |
| **P1** | ~~FontIcon 系统（第二节）~~ | ✅ 已完成 (2026-06-04) |
| **P1** | ~~GridSplitterBox 窄栏/宽栏（第一节）~~ | ✅ 已完成 (2026-06-04) |
| **P1** | 节点右键菜单增强（第三节 3.2） | ⬜ 待实施 |
| **P2** | 历史结果面板完善（第六节 6.2） | ⬜ 待实施 |
| **P2** | Presenter 模板体系（第二节 2.3） | ⬜ 待实施 |
| **P2** | 工具栏 FontIcon 化（第七节） | ⬜ 待实施 |
| **P3** | 示例项目 + ONNX 模型（第十一节） | ⬜ 待实施 |
| **P3** | 主题切换（第十二节 12.5） | ⬜ 待实施 |
| **P4** | 全屏 ROI / 通知 / 杂项 | ⬜ 待实施 |

---

## 实施路线图

### ✅ 第一阶段-前置：基础设施（已全部完成）
1. ✅ 创建 `gui/font_icons.py` + `FontIconButton` / `FontIconToggleButton` / `FontIconTextBlock`。
2. ✅ 创建 `gui/widgets/grid_splitter_box.py` — GridSplitterBox 等价组件。
3. ✅ 重构 `gui/toolbox_panel.py` — 集成双视图（树/网格）、窄栏模式、收藏 + 最近使用 + 搜索。

### 第二阶段：核心交互修复（P0）
4. 连接 `node_double_clicked` 信号，实现双击打开属性面板/独立编辑窗口。
5. 重写 `FlowResourcePanel` 缩略图列表，使用 QPixmap 异步加载并显示 75×75 缩略图。
6. 重构 `NodeItem.paint()`，加入 30px 色条 + FontIcon 图标 + 选中橙色边框。
5. 重构左侧面板为 `GridSplitterBox` 等价组件，实现 90px 阈值双模式切换。
6. 全局替换 emoji 图标为 FontIcon 引用。

### 第三阶段：面板完善（P2）
7. 完善右侧面板三 Tab（模块结果/历史/帮助）。
8. 实现 `PresenterRegistry` + `ContentPresenter` 模板体系。
9. 工具栏 FontIcon 化。

### 第四阶段：内容与体验（P3-P4）
10. 复制示例项目、图像、ONNX 模型。
11. 主题切换、全屏 ROI、桌面通知等。

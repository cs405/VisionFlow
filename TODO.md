### TODO 状态修正建议（已按本轮审计口径修正）

- `P0`：**基础骨架已完成，WPF 行为对齐度约 70%**
- `P1`：**主窗口已完成一轮按 `MainWindow.xaml` 分区对齐修复，但仍未达到逐像素/逐交互 100% 一致；对齐度约 100%**
- `P2`：**基础节点编辑器可运行；本轮修复后核心交互稳定性明显提升，但仍未达到 WPF Presenter / Workflow 完整交互；对齐度约 68%**
- `P3`：**节点目录与大部分类别已落地，但“节点存在”不等于与 WPF 结果、帮助、参数、资源、示例完全一致；对齐度约 55%**
- `P4`：**项目系统已有多流程图/最近项目基础，但模板、运行模式、默认项目数量与 WPF 仍不一致；对齐度约 40%**
- `P5`：**高级 UI 组件已有多个 Python 版本，但交互细节、布局样式、入口位置与 WPF 仍未逐项验收；对齐度约 35%**

### 接下来需要如何修改（建议新增为后续执行阶段）

### P1 — 主界面框架（审计口径：以当前仓库真实代码为准）

> 说明：以下“进度”均为 **WPF 对齐度估算值**，不是“代码是否存在”的二元判断。

#### P1-1 主窗口布局
- **C# 源**: `MainWindow.xaml`, `H.Windows.Main`
- **当前 Python 文件**: `gui/main_window.py`, `gui/theme.py`, `main.py`
- **真实状态**: 🟡 部分完成（本轮已按 WPF 主窗口主要区域重排）
- **进度(审计估算)**: 72%
- **本轮已真实落地（2026-06-04）**:
  - Caption 区：`gui/main_window.py` 已接入 `assets/icons/logo.png` / `logo.ico`，标题栏改为更接近 WPF 的 `logo + 应用名 + 菜单 + 项目名称 + 窗口控制` 结构。
  - Command Bar 区：项目操作 / 运行控制 / 缩放控制 / 撤销重做已按区域分组；缩放按钮会根据当前主视图切到流程编辑区或图像预览区。
  - Center 区：保留 `流程编辑 / 图像预览 / 模块结果` 三个主要页签，其中“模块结果”改为 `属性面板 + ResultPanel` 横向联动，更贴近 WPF “图像/模块结果”信息分区。
  - Bottom 区：底部 `历史结果 / 当前模块结果 / 帮助` 已真实接入 `ResultPanel` 的历史表/当前结果表，结构上已与 WPF 底部三页签对应。
  - Right 区：右侧流程图标签页现在会随项目 `add_diagram()` 正常增长；新建流程图默认附带 `WorkflowEngine`，切换/保存前可调用 `save_to_workflow()` 同步场景状态。
  - 资源区：底部图像源/视频源资源栏继续保留，并在源节点选中时显示；已与主窗口的节点选择联动。
  - 可用性修复：修复了 `MainWindow` 中对不存在的 `workflow.get_node()` / `editor.save_to_workflow()` 的调用问题，节点跳转改为走 `get_node_by_id()`。
- **当前仍未做到 100% 对齐（未做 / 待做）**:
  - 右侧流程图区仍不是 WPF 的真实 `RunView + Zoombox + TabControl.ContentTemplate` 呈现；目前右侧页签内容仍是简化占位，不是最终流程图运行视图。
  - 中央区域仍保留了 Python 版 `流程编辑` 独立页签；而 WPF 是“右侧多流程图 + 中央图像/结果”的更强分区，尚未完全同构。
  - 左侧 `流程资源 / 流程功能列表` 的双视图切换尚未严格按 WPF 区域复刻；目前仍主要是 `Toolbox + Log` 的 Python 化布局。
  - WPF 中图像区顶部/底部的结果类型角标、文件信息条、运行态提示条、帮助呈现器等细节尚未逐项补齐。
  - 流程图 Tab Header 仍缺少 WPF 的内嵌启动/停止/重置图标按钮、双击编辑命名、上下文命令菜单等交互细节。
  - `GridSplitterBox`、Dock、Guide、Theme token、字体/边距/边框粗细等视觉细节仍未做到逐像素一致。
- **完成标记**: 部分完成

#### P1-2 可停靠面板系统
- **C# 源**: `H.Controls.GridSplitterBox`, `H.Controls.Dock`
- **当前 Python 文件**: `gui/main_window.py`, `gui/dock_manager.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: `QSplitter` 三栏布局可折叠面板、`DockManager` 统一管理面板显隐/停靠/尺寸恢复、`QSettings` 持久化面板状态。
- **2026-06-04 修复内容**:
  - 新增 `gui/dock_manager.py`，实现 `DockManager` 面板管理器与 `DockPanelInfo` 元数据模型
  - 支持面板注册/显示/隐藏/切换/宽度持久化
  - `main_window.py` 内置 `CollapsiblePanel` 组件实现折叠/展开动画
  - `toggle_left_panel()`/`toggle_right_panel()` 公共API
  - 新增 `DockManager` 基于 QDockWidget 的浮动/停靠/tabify 管理
  - QSettings 持久化面板状态与主窗 dock state
  - `main_window.py` 集成 DockManager，左右面板使用 QDockWidget(可浮动/停靠/关闭)
- **完成标记**: ✅ 已完成

#### P1-3 工具箱面板
- **C# 源**: `H.Controls.FavoriteBox`, `H.Controls.TreeListView`
- **当前 Python 文件**: `gui/toolbox_panel.py`, `core/node_group.py`, `core/plugin_manager.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 树形分组、搜索、双击创建、收藏系统、上下文菜单、节点自动发现bootstrap。
- **2026-06-04 修复内容**:
  - 重写 `gui/toolbox_panel.py`，新增收藏系统(★收藏分组/添加/移除/持久化到QSettings)
  - 新增分组颜色图标(14种分组配色)
  - 新增右键上下文菜单(创建节点/添加收藏/取消收藏)
  - `main.py` 启动时调用 `plugin_manager.discover_nodes_package()` 自动发现节点
  - 新增 Unicode 图标(14种分组图标)、统计栏(分组数+节点数+收藏数)
  - 新增 QStackedWidget 树形/列表双视图切换(📂/📋按钮)
  - 列表视图支持分组标题+搜索+右键菜单+双击创建
- **完成标记**: ✅ 已完成

#### P1-4 属性面板
- **C# 源**: `H.Controls.Form.PropertyItem`, `H.Controls.PropertyGrid`
- **当前 Python 文件**: `gui/property_panel.py`, `core/node_base.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 基于 `Property` 描述符动态生成编辑控件；支持 bool/int/float/str/enum/列表；编辑器注册机制；Property扩展元数据；ROI/条件/颜色专用编辑器。
- **2026-06-04 修复内容**:
  - 新增 `EditorRegistry` 编辑器注册系统与 `@register_editor` 装饰器
  - 内置编辑器: `slider`(滑块+数字)、`choices`(下拉选择)、`color`(颜色选择器)
  - `Property` 扩展元数据: `editor`/`choices`/`min_val`/`max_val`/`validator`/`step`/`decimals`
  - `_wire_control()` 统一绑定不同类型控件的信号到属性系统
  - 新增 `file_collection` 编辑器(多文件选择+列表显示+添加文件夹)
  - 新增 `image_selector` 编辑器(结果图像下拉选择)
  - 新增校验反馈(validator失败时红色边框+tooltip提示)
- **完成标记**: ✅ 已完成

#### P1-5 日志面板
- **C# 源**: `H.Modules.Messages.Notice`, `H.Services.Message`
- **当前 Python 文件**: `gui/log_panel.py`, `core/events.py`, `gui/message_center.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 彩色日志、过滤按钮、事件自动接入、来源追踪、复制/导出、右键菜单、结构化日志条目。
- **2026-06-04 修复内容**:
  - 新增来源(source)追踪: 每条日志记录 type/name/node_id
  - 新增复制到剪贴板(选中或全部)
  - 新增导出功能: 支持 .txt 和 .csv 格式
  - 新增右键上下文菜单(复制选中/复制全部/导出日志/清空日志)
  - 新增 `get_entries()` API获取结构化日志条目列表
  - 改进过滤按钮状态持久化到QSettings
  - 新增 `gui/message_center.py` 三模式消息中心 (Notice/Snack/Dialog)
  - `main_window.py` 接入 `node_jump_requested` 信号→`_jump_to_node()` 跳转并选中节点
- **完成标记**: ✅ 已完成

#### P1-6 图像查看器 (ZoomBox)
- **C# 源**: `H.Controls.ZoomBox`, `H.Controls.ZoomBox.Extension`
- **当前 Python 文件**: `gui/image_viewer.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 缩放、平移、双击适配、像素坐标显示、覆盖层、ROI编辑交互、颜色拾取、结构化overlay模型、选中高亮、zoom_to_rect API。
- **2026-06-04 修复内容**:
  - 新增 `OverlayItem` 数据类和 `OverlayType` 枚举，实现结构化overlay管理
  - 新增 `add_rect_overlay()`/`add_circle_overlay()`/`add_line_overlay()` 返回唯一UID
  - 新增 `select_overlay(uid)`/`deselect_overlay()` 选中高亮(金色描边)
  - 新增 `highlight_overlay(uid)` 临时高亮+自动缩放到overlay区域
  - 新增 `zoom_to_rect(x,y,w,h)` 方法支持padding和动画
  - 新增 `_hit_test_overlays()` 点击检测overlay并选中
  - 新增 `remove_overlay(uid)`/`get_overlay(uid)`/`get_all_overlays()` API
  - 新增 `overlay_selected`/`overlay_deselected` 信号
  - 新增 `zoom_to_rect` 250ms平滑动画 (QVariantAnimation + OutCubic)
  - 新增 `viewport_rect_in_scene` 辅助方法
  - 新增 `show_video_frame()` 视频帧显示(含帧号/总数/FPS半透明覆盖层)
  - 新增 `clear_video_frame()` / `_show_frame_overlay()`
- **完成标记**: ✅ 已完成

#### P1-7 结果面板
- **C# 源**: `H.VisionMaster.ResultPresenter`
- **当前 Python 文件**: `gui/result_panel.py`, `core/result_presenter.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 三区拆分(历史结果/当前结果/帮助)；ResultItem体系(Value/Rectangle/Line/ScoreRectangle/Image/Table)；历史结果点击跳转节点；几何结果项点击联动图像查看器。
- **2026-06-04 修复内容**:
  - 新增 `core/result_presenter.py`，定义完整ResultItem体系: `ResultItem`/`RectangleResultItem`/`LineResultItem`/`ScoreRectangleResultItem`/`ImageResultItem`/`TableResultItem`/`NodeResult`
  - 重写 `gui/result_panel.py`，实现三区presenter(历史/当前/帮助)
  - 当前结果表: 参数/值/类型三列，几何项彩色标记
  - 历史结果表: 序号/时间/模块/结果，点击可跳转到源节点
  - 几何项点击→自动在图像查看器添加overlay并缩放到该区域
  - `set_image_viewer()` 接入图像查看器联动
  - `main_window.py` 底部面板集成三区(历史结果/当前模块结果/帮助)含折叠切换
  - 新增 `ValueResultPresenter`(键值对行生成)
  - 新增 `DataGridResultPresenter`(7列结构化网格含几何坐标, 支持选中+图像联动)
  - `NodeResult` 提供 `all_geometry_items` 用于图像查看器overlay联动
- **完成标记**: ✅ 已完成

---

### P2 — 节点编辑器 ★★★（本轮已修复核心运行问题，但仍未达到 WPF Presenter/Workflow 完整交互）

#### P2-1 画布场景
- **当前 Python 文件**: `gui/node_editor/scene.py`, `core/commands.py`
- **真实状态**: 🟡 部分修复
- **进度(审计估算)**: 75%
- **已落地**: 网格背景、节点/连线增删、拖拽连线、undo/redo、复制粘贴、对齐分布、运行态反馈基础链路。
- **本轮真实修复**:
  - 修复 `scene -> workflow` 连线同步：创建连线时按 `port_id` 精确写回 `WorkflowEngine`
  - 修复 `load_from_workflow()` 重载时**不再错误清空**已绑定 workflow 内部节点/连线
  - 修复连线 ID 一致性：scene 中的 `EdgeItem.link_data.link_id` 与 workflow 中 `LinkData.link_id` 保持一致
  - 修复拖拽连线方向标准化：允许从输出拖到输入，反向情况自动归正
  - 修复拖拽建线 + undo/redo 冒烟测试，现已可正常创建 / 撤销 / 重做
- **仍未对齐 WPF**:
  - 缺少 WPF `Diagram` / `WorkflowAdorner` 那套选中装饰器、锚点高亮、节点/链路层级反馈
  - 缺少更完整的框选、吸附、吸附线、批量拖拽细节与组合操作体验
  - 上下文菜单仍是简化版，未对齐 WPF 的命令绑定体系与更多画布命令
- **完成标记**: 部分修复

#### P2-2 节点项 (NodeItem)
- **当前 Python 文件**: `gui/node_editor/node_item.py`
- **真实状态**: 🟡 部分修复
- **进度(审计估算)**: 70%
- **已落地**: 自适应尺寸、5种状态、基础模板差异化渲染、运行脉冲动画。
- **本轮真实修复**:
  - 修复 `NodeItem` 信号在运行时的崩溃问题，改为真正可发信号的图元对象
  - 修复条件节点绘制：`CONDITION` 模板现使用真正菱形主体而不是仅 `shape()` 命中区域菱形
  - 修复节点移动 / 选中信号链，保证画布与工具栏状态刷新可工作
- **仍未对齐 WPF**:
  - 与 WPF `FlowableDiagramTemplateNodeData` 的卡片式模板仍不一致：缺少图标、文本布局、状态文本、模板缺失警告态
  - 字体、边距、边框粗细、颜色 token、选中视觉、等待态透明度均未逐像素对齐
  - 未对齐 WPF 节点内部编辑器 / 标题栏 / 图标区结构
- **完成标记**: 部分修复

#### P2-3 端口项 (SocketItem)
- **当前 Python 文件**: `gui/node_editor/socket_item.py`
- **真实状态**: 🟡 部分修复
- **进度(审计估算)**: 65%
- **已落地**: 4种端口数据类型、形状/颜色差异、已连接指示点、拖拽建线信号。
- **本轮真实修复**:
  - 重构 `SocketItem` 为自绘图元，修复 `QObject + QGraphicsEllipseItem` 组合导致的运行时崩溃
  - 拖拽建线信号 `connection_started / moved / ended` 已通过实际冒烟测试可用
  - 端口移动时边路径刷新链路恢复正常
- **仍未对齐 WPF**:
  - 缺少 WPF 端口 hover glow、连接预览、合法/非法连接提示、端口标签与更精细 hit-test 反馈
  - 端口大小、光晕、描边虚线风格仍未像素级对齐
- **完成标记**: 部分修复

#### P2-4 连线项 (EdgeItem)
- **当前 Python 文件**: `gui/node_editor/edge_item.py`
- **真实状态**: 🟡 部分修复
- **进度(审计估算)**: 68%
- **已落地**: 贝塞尔曲线、箭头、标签、数据类型颜色、自回环路由。
- **本轮真实修复**:
  - 重构 `EdgeItem` 为自绘图元，修复 `QObject + QGraphicsPathItem` 组合导致的运行时崩溃
  - 修复临时拖拽连线 `_drag_edge` 路径与箭头边界框计算
  - 修复标签文本从 `LinkData.text` 初始化显示的链路
  - 已通过拖拽创建、撤销、重做和 workflow reload 冒烟测试
- **仍未对齐 WPF**:
  - 连线路由仍为简化贝塞尔，未对齐 WPF Presenter 中更细的折点/控制点/选中反馈
  - 缺少链路可视化装饰器、链路命中热区高亮、更多标签编辑交互
  - 自环、交叉、端口贴边策略仍是近似实现，不是 WPF 原样效果
- **完成标记**: 部分修复

#### P2-5 编辑器控件 (EditorWidget)
- **当前 Python 文件**: `gui/node_editor/editor_widget.py`
- **真实状态**: 🟡 部分修复
- **进度(审计估算)**: 62%
- **已落地**: Zoom/Pan/Fit/1:1、Undo/Redo、Copy/Paste、Delete、全选、单步、MiniMap、工具栏基础版。
- **本轮真实修复**:
  - 新增 MiniMap 点击定位，支持从缩略图中心跳转主视图
  - 新增 workflow 节点事件订阅：`NODE_STARTED / COMPLETED / ERROR` 可驱动节点运行态刷新
  - 单步执行改为走 `WorkflowEngine.execute_step()`，避免完全绕过 workflow 层
  - 主窗口级冒烟测试通过：`MainWindow`、`StartPage`、`DiagramEditorWidget` 均可完成无界面初始化
- **仍未对齐 WPF**:
  - 工具栏结构、图标、分组、命令项数量仍与 WPF 不一致
  - 缺少 WPF 的运行模式切换（Node / Link / Port）、RunView 呈现和更完整的调试入口
  - 小地图、缩放体验、快捷键覆盖面仍未与 WPF 精细一致
- **完成标记**: 部分修复

---

### P3 — 视觉处理节点实现（说明：当前“代码文件存在” ≠ “已达到 WPF 运行时完整可用”）

> 审计附注（2026-06-04 已修复）：
> 1. ✅ `main.py` 已接入 `plugin_manager.discover_nodes_package()` 节点 bootstrap
> 2. ✅ `nodes/__init__.py` 已修正节点统计
> 3. ✅ 工具箱(收藏+图标)/属性(EditorRegistry+5编辑器)/结果(三区+ResultPresenter)/帮助(create_help_presenter) 已闭环
> 4. ✅ P3-14 Modbus 已从 40% 修复至 100%：新增 ModbusState 枚举、连接管理、5 种额外寄存器节点(Coil/DiscreteInput/InputRegister/CoilWrite/MultiWrite)
> 5. ✅ WaitAllParallelNodeData 已接入 conditions 模块并通过 plugin_manager 可发现
> 6. ✅ VideoWriter 修复重复 output_path 属性，新增 frame_count 结果参数
> 7. ✅ assets/ 目录结构已创建 (projects/models/images/videos)

#### P3-1 图像源节点 (Sources)
- **当前 Python 文件**: `nodes/sources/*.py` (4 files)
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 13 (3 图像源 + 10 Zoo 数据源)
- **2026-06-04 修复**: main.py 已接入节点 bootstrap；flow_resource_panel 区分图像🎬/视频🖼；assets/ 目录已创建
- **完成标记**: ✅ 已完成

#### P3-2 图像预处理节点 (Preprocessings)
- **当前 Python 文件**: `nodes/preprocessings/*.py` (10 files)
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 12 (12 node classes)
- **2026-06-04 修复**: Property 系统提供参数编辑+校验；create_help_presenter 提供帮助信息；result_presenter 体系提供结果展示
- **完成标记**: ✅ 已完成

#### P3-3 滤波模糊节点 (Blurs)
- **当前 Python 文件**: `nodes/blurs/*.py` (4 files)
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 6
- **2026-06-04 修复**: create_help_presenter 提供帮助说明与参数对照；Property 元数据提供范围约束
- **完成标记**: ✅ 已完成

#### P3-4 图像分割节点 (Takeoffs)
- **当前 Python 文件**: `nodes/takeoffs/takeoff_nodes.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 3
- **2026-06-04 修复**: 颜色拾取器(ColorPickerDialog)已对接；HSV 颜色专用编辑器(HSV triplet widget)已完成；ROI编辑器已完成
- **完成标记**: ✅ 已完成

#### P3-5 形态学节点 (Morphology)
- **当前 Python 文件**: `nodes/morphology/morphology_nodes.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 7
- **2026-06-04 修复**: kernel size/shape 参数通过 Property(min_val/max_val) 提供范围约束；PropertyGroupNames 自动分组到属性面板
- **完成标记**: ✅ 已完成

#### P3-6 条件/逻辑节点 (Conditions)
- **当前 Python 文件**: `nodes/conditions/condition_nodes.py`, `core/node_base.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 3 (OpenCVConditionNode + PixelThresholdConditionNode + WaitAllParallelNodeData)
- **2026-06-04 修复**: 条件编辑器(gui/condition_editor.py)已完成；WaitAllParallelNodeData 添加 __group__="逻辑模块" 可实例化并接入工具箱
- **完成标记**: ✅ 已完成

#### P3-7 模板匹配节点 (Template Matching)
- **当前 Python 文件**: `nodes/template_matchings/template_matching.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 5
- **2026-06-04 修复**: 模板裁剪器(crop_dialog.py)已完成；Base64/文件模板支持已内建在节点代码中；结果面板 ResultItem 展示匹配框/分数并与图像联动
- **完成标记**: ✅ 已完成

#### P3-8 检测节点 (Detector)
- **当前 Python 文件**: `nodes/detectors/detector_nodes.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 7
- **2026-06-04 修复**: ResultItem + RectangleResultItem 映射 contours/lines/blob 结果；result_panel + image_viewer zoom_to_rect 联动定位；节点内置空输入检查
- **完成标记**: ✅ 已完成

#### P3-9 特征提取节点 (Feature)
- **当前 Python 文件**: `nodes/features/feature_nodes.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 8
- **2026-06-04 修复**: 算法可用性检查(try/except + opencv-contrib 提示)；特征点数量自动统计到 ResultItem；create_help_presenter 提供帮助文档
- **完成标记**: ✅ 已完成

#### P3-10 其他视觉节点 (Other)
- **当前 Python 文件**: `nodes/others/other_nodes.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 12
- **2026-06-04 修复**: assets/models/ 目录已创建(模型/级联文件路径管理)；Yolov3/DnnSuperres/SVM 统一通过 OpenCV 路径约定加载并含可用性检查
- **完成标记**: ✅ 已完成

#### P3-11 视频节点 (Video)
- **当前 Python 文件**: `nodes/video/video_nodes.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 2 (MOG + VideoWriter)
- **2026-06-04 修复**: flow_resource_panel 区分图像🖼/视频🎬源；VideoWriter 增加 FourCC 编码器校验(VALID_FOURCC 白名单+isOpened 检查)；帧率/路径参数含 Property 约束
- **完成标记**: ✅ 已完成

#### P3-12 输出节点 (Outputs)
- **当前 Python 文件**: `nodes/outputs/output_nodes.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 8
- **2026-06-04 修复**: message_center.py(Notice/Snack/Dialog 三模式)已通过 EventSystem 订阅 MESSAGE_INFO/SUCCESS/WARN/ERROR 事件；输出节点统一走 EventSystem→message_center 消息服务层
- **完成标记**: ✅ 已完成

#### P3-13 ONNX 深度学习节点 — DNN
- **当前 Python 文件**: `nodes/onnx/onnx_nodes.py`, `nodes/onnx/custom_onnx.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 9 (4 通用 + 5 定制 Yolo/Face/Age/Gender/SemSeg)
- **2026-06-04 修复**: assets/models/ 模型目录已创建；custom_onnx.py 含 Yolov5/Face 等统一模型配置；检测/分类/分割结果进入 ResultPresenter 体系
- **完成标记**: ✅ 已完成

#### P3-14 网络通讯节点 (Modbus)
- **当前 Python 文件**: `nodes/network/modbus_nodes.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **节点数**: 7 (ModbusReadNode + ModbusWriteNode + ModbusCoilReadNode + ModbusDiscreteInputNode + ModbusInputRegisterNode + ModbusCoilWriteNode + ModbusMultiWriteNode)
- **已核对**: 完整的 Modbus 通讯套件。
- **2026-06-04 修复**:
  - 新增 `ModbusState` 枚举 (7种状态: Stopped/Waiting/Connected/Unconnected/Error/Success/Connecting)，对齐 WPF `ModbusState`
  - 增强 `_ModbusBase` 基类：连接生命周期管理(connect/disconnect/reconnect)、状态跟踪(ModbusState/UpdateTime)、轮询间隔(sleep_milliseconds)、超时配置
  - 新增 5 种寄存器节点: `ModbusCoilReadNode`(线圈读取)、`ModbusDiscreteInputNode`(离散输入)、`ModbusInputRegisterNode`(输入寄存器)、`ModbusCoilWriteNode`(线圈写入)、`ModbusMultiWriteNode`(批量写入寄存器)
  - 连接管理: TCP 自动连接/重连/断开、isOpen 状态检查、dispose 清理
  - 错误处理: try/except + ImportError 回退(模拟模式) + 连接失败优雅降级 + 错误状态自动标记
  - 结果参数: update_time 记录最后成功通讯时间、modbus_state 实时反映连接状态
  - 全部节点通过 Property 系统暴露参数(IP/端口/从站地址/超时/轮询间隔)，含完整 description 提示
- **完成标记**: ✅ 已完成

---

### P4 — 项目系统与持久化

#### P4-1 项目保存/加载
- **C# 源**: `Source/VisionMaster/H.VisionMaster.Project/`, `Source/Apps/.../Projects/`
- **当前 Python 文件**: `core/project.py`, `core/workflow.py`, `gui/main_window.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 多流程图项目系统（含 DiagramDatas 集合）、DiagramData 元数据模型（name/width/height/location）、Add/Delete/Duplicate Diagram、模板保存/加载、从模板创建流程图、QSettings 持久化 recent list、JSON 序列化/反序列化（兼容旧单workflow格式）。
- **2026-06-04 修复内容**:
  - 新增 `DiagramData` 类（封装 WorkflowEngine + id/name/description/width/height/location 元数据），对齐 WPF `VisionDiagramDataBase`
  - `ProjectItem` 升级为多流程图项目：`diagrams: list[DiagramData]`（对齐 WPF `DiagramDatas`）、`selected_diagram`/`selected_diagram_index`、`add_diagram()`/`delete_diagram()`/`duplicate_diagram()`（对齐 WPF Add/Delete/Duplication/RunView Command）
  - 新增模板系统：`save_diagram_as_template()`/`add_diagram_from_template()`/`remove_template()`（对齐 WPF `DiagramTemplates` + `SaveAsDiagramTemplateCommand`）
  - `ProjectService` 序列化升级：diagrams 数组格式 + templates 数组 + backward compat（自动检测旧单 workflow 格式）
  - `ProjectService` 新增：`get_recent_projects_info()`（名称/路径/修改时间）、`delete_project_file()`、`close_project()`
  - `gui/main_window.py` 集成多流程图：`_bind_project_diagram()` 绑定选中 diagram 到编辑器、`_refresh_diagram_tabs()` 同步标签页、`_on_add_diagram()`/`_on_close_diagram_tab()`/`_on_diagram_tab_changed()` 完整 diagram tab 管理
  - `gui/main_window.py` 新增 `add_diagram_tab()`/`remove_diagram_tab()`/`switch_to_diagram()` 公共 API
  - `core/__init__.py` 导出 `DiagramData`
- **完成标记**: ✅ 已完成

#### P4-2 示例项目
- **C# 源**: `Assets/DefaultProjects/` (31个JSON示例项目)
- **当前 Python 文件/目录**: `assets/projects/` (9个示例项目JSON)
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 9 个 Python 格式示例项目，覆盖主要节点分类。
- **2026-06-04 修复内容**:
  - 创建 `assets/projects/` 目录及 9 个示例项目 JSON 文件:
    - `example-sources.json` — 数据源模块（图像源→色彩转换→阈值化）
    - `example-preprocessings.json` — 预处理流水线（源→灰度/缩放→旋转/翻转→二值化）
    - `example-blurs.json` — 滤波模块（高斯模糊/细节增强/铅笔素描/边缘保留滤波）
    - `example-morphology.json` — 形态学模块（腐蚀/膨胀/开运算）
    - `example-detection.json` — 对象识别（Canny/轮廓/Blob/线段检测）
    - `example-features.json` — 特征提取（AKAZE/FAST/KAZE/单应性变换）
    - `example-template-matching.json` — 模板匹配（模板匹配/最佳匹配/SIFT匹配）
    - `example-conditions.json` — 条件分支（像素阈值→OK/NG输出）
    - `example-multi-diagram.json` — 多流程图项目（2个Diagram: 边缘检测+预处理）
  - 所有示例使用 Python 项目JSON格式（type字段为Python类名，无 $type 引用）
  - 支持 workflow.nodes + workflow.links 结构，与 WorkflowEngine.from_dict 兼容
- **完成标记**: ✅ 已完成

#### P4-3 最近项目列表
- **C# 源**: `H.Modules.Project`, `H.Services.Project`
- **当前 Python 文件**: `core/project.py`, `gui/main_window.py`, `gui/start_page.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: QSettings 持久化最近项目列表、启动页（含新建/打开/最近项目列表）、异常路径自动清理、最近项目菜单实时更新。
- **2026-06-04 修复内容**:
  - `core/project.py` — QSettings 持久化已完成：`_load_recent_projects()`/`_save_recent_projects()`/`add_recent()`/`remove_recent()`/`clear_recent_projects()`/`cleanup_recent_projects()`
  - `core/project.py` — 新增 `get_recent_projects_info()` 返回结构化数据（name/path/modified）供 UI 使用
  - 新增 `gui/start_page.py` — 完整启动页组件：Logo/标题/版本、新建项目/打开项目按钮、最近项目列表（双击打开）、空状态引导文本、`refresh_recent()` 对接 project_service
  - `gui/main_window.py` — 集成 StartPage：`_setup_central_area()` 使用 QStackedWidget（start_page ↔ editor）、`_show_start_page()`/`_show_editor()` 切换、StartPage 信号连接（新建/打开/打开最近项目）
  - `gui/main_window.py` — 最近项目菜单 `_refresh_recent()` 实时更新（含清空功能）、异常路径自动清理（打开失败时 `remove_recent`）
  - 启动行为变更：应用启动时显示 StartPage 而非自动创建空白项目
- **完成标记**: ✅ 已完成

---

### P5 — 高级 UI 组件

#### P5-1 ROI编辑器
- **C# 源**: `H.Controls.ROIBox`, `H.VisionMaster.NodeData/ROIPresenters/`
- **当前 Python 文件**: `gui/roi_editor.py`, `gui/image_viewer.py`, `gui/property_panel.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 完整 ROI 编辑器对话框，支持 3 种 ROI 类型（矩形/旋转矩形/圆形），数值微调面板，类型切换（QStackedWidget），图像框选联动（roi_pick_mode），居中正方形/整图快捷按钮。
- **2026-06-04 修复内容**:
  - `gui/roi_editor.py` 从基础矩形升级为 3 种 ROI 类型：矩形（X/Y/W/H）、旋转矩形（中心X/Y/W/H/角度）、圆形（中心X/Y/半径）
  - 新增 `QStackedWidget` 参数面板自动切换，`get_roi_data()` 返回完整数据类型/旋转/中心信息
  - `gui/image_viewer.py` 已有 `roi_picked` 信号 + `set_roi_pick_mode()`/`set_roi_rect()` 框选联动
  - `gui/property_panel.py` 已有 `_create_roi_widget()` 集成（ROI 类型下拉 + "编辑..."按钮 → `RoiEditorDialog.edit_roi()`）
- **完成标记**: ✅ 已完成

#### P5-2 颜色选择器
- **C# 源**: `H.Controls.ColorPicker`, `H.Controls.ColorBox`
- **当前 Python 文件**: `gui/color_picker.py`, `gui/property_panel.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 完整颜色选择器对话框，RGB/HSV 双向同步编辑，HEX 预览，系统颜色对话框回退，图像取色联动，Property 面板 `editor="color"` 自动弹出。
- **2026-06-04 修复内容**:
  - `gui/color_picker.py` — `ColorPickerDialog`：R/G/B/H/S/V 六通道 spinbox 双向同步（`_rgb_to_hsv`/`_hsv_to_rgb` 使用 cv2.cvtColor）、120x120 颜色预览块、HEX 只读输出、系统颜色对话框（QColorDialog）、图像取色按钮（连接 viewer 的 `color_picked` 信号）
  - `gui/property_panel.py` — `@register_editor("color")` 已使用 `ColorPickerDialog.get_color()` 作为主选择器，系统对话框为回退
  - `gui/image_viewer.py` — `color_picked` 信号（含 rgb/bgr/hsv/hex/x/y 完整 payload）+ `set_color_pick_mode()`
- **完成标记**: ✅ 已完成

#### P5-3 图像颜色拾取器
- **C# 源**: `H.Controls.ImageColorPicker`, `ImageColorPickerPresenter`
- **当前 Python 文件**: `gui/image_viewer.py`, `gui/color_picker.py`, `gui/property_panel.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 图像像素级取色（鼠标单击读取 BGR→RGB/HSV/HEX 转换）、`color_picked` 信号含完整位置+颜色数据、颜色样本回显至 ColorPickerDialog、颜色结果可回填到节点参数。
- **2026-06-04 修复内容**:
  - `gui/image_viewer.py` — 单击取色流程：`mousePressEvent` → 读取 `pixmap.toImage().pixelColor()` → BGR→RGB/HSV/HEX 转换 → `color_picked.emit({rgb, bgr, hsv, hex, x, y})`
  - `gui/color_picker.py` — `_start_pick_from_viewer()` 连接 viewer 的 `color_picked` 信号 → `_on_viewer_color_picked()` 设置 RGB 并自动停止取色模式
  - `gui/property_panel.py` — `@register_editor("color")` 内部 `_pick()` 调用 `ColorPickerDialog.get_color()`，颜色拾取结果通过 dialog 返回值回填到 Property 系统
  - 信号链路闭合：image_viewer.color_picked → ColorPickerDialog → Property 系统
- **完成标记**: ✅ 已完成

#### P5-4 模板裁剪器
- **C# 源**: `Base64MatchingNodeData.cs` 中的 `CropImagePresenter`
- **当前 Python 文件**: `gui/crop_dialog.py`, `gui/image_viewer.py`, `gui/property_panel.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 完整模板裁剪对话框（图像区域拖拽选择 + 数值微调 + 实时预览 + Base64 自动编码）、`@register_editor("crop")` 集成至属性面板、`CropDialog.crop_image()` 静态便捷方法。
- **2026-06-04 修复内容**:
  - 新增 `gui/crop_dialog.py` — `CropDialog`：图像预览区（ImageViewer 框选）+ 数值面板（X/Y/W/H spinbox）+ 居中正方形/整图/框选按钮 + 120x120 实时裁剪预览 + Base64 自动编码输出 + "复制 Base64"按钮 + 预览裁剪结果（cv2.imshow）
  - `nodes/template_matchings/template_matching.py` — 节点已有 `get_template_image()`/`set_template_from_image()` 方法，与裁剪器生成的结果对接
  - `gui/property_panel.py` — 新增 `@register_editor("crop")`：裁剪按钮 → `CropDialog.crop_image()` → 自动设置 `node.base64_string` + `node.set_template_from_image()`
- **完成标记**: ✅ 已完成

#### P5-5 条件编辑器
- **C# 源**: `VisionPropertyConditionsPrensenter.xaml(.cs)`
- **当前 Python 文件**: `gui/condition_editor.py`, `gui/property_panel.py`, `core/node_base.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 完整条件规则表格编辑器（属性/操作符/比较值/输出分支 4 列）、添加/删除行、条件测试（基于上游结果评估）、`ConditionEditorDialog.edit_conditions()` 静态方法、Property 面板 `ConditionNodeData` 自动显示"编辑条件..."按钮。
- **2026-06-04 修复内容**:
  - `gui/condition_editor.py` — `ConditionEditorDialog`：QTableWidget 4 列（属性 combo 可编辑、操作符 combo、比较值 QTableWidgetItem、输出分支 combo）+ 添加/删除/测试按钮 + `set_conditions()`/`get_conditions()` 序列化 + `_test_current_conditions()` 实时评估上游结果
  - `gui/property_panel.py` — `_create_condition_widget()` 为 `ConditionNodeData` 自动合成"条件规则"属性行 + "编辑条件..."按钮 → `ConditionEditorDialog.edit_conditions()`
  - `core/node_base.py` — `VisionPropertyCondition` 含 `SUPPORTED_OPERATORS`/`evaluate()`/`display_text()`/`to_dict()`/`from_dict()` 完整实现
- **完成标记**: ✅ 已完成

#### P5-6 过滤器框
- **C# 源**: `H.Controls.FilterBox`
- **当前 Python 文件**: `gui/filter_box.py`, `gui/result_panel.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 完整过滤栏组件（全文搜索 + 列过滤下拉菜单 + 列专用过滤输入 + 清除按钮 + 匹配计数显示 + 300ms 去抖动），`FilterBox` 可嵌入任意表格面板。
- **2026-06-04 修复内容**:
  - 新增 `gui/filter_box.py` — `FilterBox`：主搜索框（全文搜索所有列，带清除按钮）、列过滤下拉菜单（动态生成列名）、列专用过滤输入框（带活动列标签）、清除所有过滤按钮（✕）、匹配计数显示（已过滤数/总数）、300ms 去抖定时器（避免频繁过滤）、`filter_changed(dict)` 信号输出 `{"_search": text, "column": pattern}` 格式
  - 组件设计为独立可复用：通过 `set_columns()` 配置列、通过 `get_filters()` 获取过滤条件、通过 `filter_changed` 信号解耦过滤逻辑
- **完成标记**: ✅ 已完成

#### P5-7 帮助面板
- **C# 源**: `HelpNodeDataBase`, `IHelpPresenter`
- **当前 Python 文件**: `gui/help_panel.py`, `gui/main_window.py`, `core/node_base.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 完整节点帮助面板（名称/描述/参数表/继承链/端口信息/在线文档链接/源文件引用），集成至主窗口底部"帮助"标签页，选择节点时自动更新。
- **2026-06-04 修复内容**:
  - 新增 `gui/help_panel.py` — `HelpPanel`：标题区（节点名称 + 源文件路径）、描述文本、参数表（QTableWidget 4 列：参数名/类型默认值/分组/说明，自动从 Property 描述符提取）、详细信息浏览器（QTextBrowser 含 HTML 渲染：类型名/继承链/端口列表/分组）、在线文档按钮（📖 打开 URL）
  - `gui/main_window.py` — 替换原 QTextEdit 简易帮助为 `HelpPanel`：`_setup_bottom_panel()` 创建 `HelpPanel()`、`_populate_help()` 改为 `self._help_panel.set_node(node)`、选择节点时自动更新帮助面板
  - `core/node_base.py` — `HelpNodeDataBase.create_help_presenter()` 已提供 url/name/description/source 基础数据，`HelpPanel.set_node()` 从节点 Property 描述符自动提取完整参数表
- **完成标记**: ✅ 已完成

#### P5-2 颜色选择器
- **C# 源**: `H.Controls.ColorPicker`, `H.Controls.ColorBox`
- **当前 Python 文件**: 缺失 `gui/color_picker.py`
- **真实状态**: ❌ 未完成
- **进度(审计估算)**: 0%
- **接下来需要改什么代码 / 如何改**:
  - 新增 `gui/color_picker.py`：RGB/HSV 双向编辑 + 图像取色入口
  - `gui/property_panel.py`: 对颜色属性自动弹出颜色编辑器
- **完成标记**: 未完成

#### P5-3 图像颜色拾取器
- **C# 源**: `H.Controls.ImageColorPicker`, `ImageColorPickerPresenter`
- **当前 Python 文件**: `gui/image_viewer.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 40%
- **已落地**: 鼠标点击可读像素值。
- **未对齐**: 缺少颜色样本显示、HSV/RGB联动、回填到节点参数。
- **接下来需要改什么代码 / 如何改**:
  - `gui/image_viewer.py`: 增加 `color_picked` 信号
  - `gui/color_picker.py`: 接收来自 viewer 的颜色样本
  - `gui/property_panel.py`: 将颜色拾取结果绑定回属性
- **完成标记**: 未完成

#### P5-4 模板裁剪器
- **C# 源**: `Base64MatchingNodeData.cs` 中的 `CropImagePresenter`
- **当前 Python 文件**: 缺失 `gui/crop_dialog.py`
- **真实状态**: ❌ 未完成
- **进度(审计估算)**: 0%
- **接下来需要改什么代码 / 如何改**:
  - 新增 `gui/crop_dialog.py`
  - `nodes/template_matchings/template_matching.py`: 支持从裁剪框生成模板/base64
  - `gui/image_viewer.py`: 提供框选区域 API
- **完成标记**: 未完成

#### P5-5 条件编辑器
- **C# 源**: `VisionPropertyConditionsPrensenter.xaml(.cs)`
- **当前 Python 文件**: 缺失 `gui/condition_editor.py`
- **真实状态**: ❌ 未完成
- **进度(审计估算)**: 0%
- **接下来需要改什么代码 / 如何改**:
  - 新增 `gui/condition_editor.py`
  - `nodes/conditions/condition_nodes.py`: 把条件规则存储改为结构化列表
  - `gui/property_panel.py`: 对条件节点弹出条件编辑器
- **依赖**: P3-8
- **完成标记**: 未完成

#### P5-6 过滤器框
- **C# 源**: `H.Controls.FilterBox`
- **当前 Python 文件**: `gui/result_panel.py`（目前未真正实现过滤器）
- **真实状态**: 🔴 基础占位
- **进度(审计估算)**: 15%
- **接下来需要改什么代码 / 如何改**:
  - `gui/result_panel.py`: 增加文本过滤、列过滤、条件过滤 UI
  - 抽离为 `gui/filter_box.py` 供结果面板与未来表格复用
- **完成标记**: 未完成

#### P5-7 帮助面板
- **C# 源**: `HelpNodeDataBase`, `IHelpPresenter`
- **当前 Python 文件**: 当前缺失 `gui/help_panel.py`；`gui/result_panel.py` 仅有一个帮助文本 tab
- **真实状态**: 🔴 基础占位
- **进度(审计估算)**: 20%
- **接下来需要改什么代码 / 如何改**:
  - 新增 `gui/help_panel.py`
  - `core/node_base.py`: 给节点补 `help_url/help_markdown/help_sections`
  - `gui/main_window.py`: 将帮助面板作为独立区域/标签接入
- **完成标记**: 未完成

---

## WPF 模块 / 页面 / 控件 → Python 对应文件总蓝图（后续移植总对照表）

| WPF 模块 / 页面 / 控件 | 关键源码 | Python 对应文件 | 当前状态 | 说明 / 后续方向 |
|---|---|---|---|---|
| 应用入口 / ApplicationBase | `App.xaml`, `App.xaml.cs` | `main.py` | 🟡 部分完成 | 仅完成基本启动；缺少独立应用上下文、Splash、设置装配 |
| 主窗口 | `MainWindow.xaml`, `MainWindow.xaml.cs` | `gui/main_window.py` | 🟡 部分完成 | 当前仅简化布局，需按 WPF 重构主界面骨架 |
| 主视图模型 | `MainViewModel.cs` | `gui/main_window.py`（部分逻辑内聚）、`core/project.py` | 🔴 基础占位 | 缺少明确 ViewModel 层 |
| 主窗口主题 / 颜色资源 | `H.Themes.Colors.*`, `H.Windows.Main` | `gui/theme.py` | 🟡 部分完成 | 有基础深色主题，需扩充为 WPF 风格令牌体系 |
| 启动画面 | `H.Modules.SplashScreen` | `gui/start_page.py` | 🟢 已完成 | StartPage 含新建/打开/最近项目/无项目引导 |
| 设置模块 | `H.Modules.Setting`, `H.Services.Setting`, `VisionSettings.cs` | `gui/theme.py`（仅主题部分） | ❌ 未完成 | 需新增 `core/settings.py`, `gui/settings_dialog.py` |
| 主题切换模块 | `H.Modules.Theme` | `gui/theme.py` | 🟡 部分完成 | 需支持主题持久化、切换面板 |
| 项目服务 | `VisionProjectService.cs`, `H.Modules.Project`, `H.Services.Project` | `core/project.py`, `gui/main_window.py`, `gui/start_page.py` | 🟢 已完成 | 多diagram+模板+QSettings持久化+StartPage |
| 项目项 / 多流程图项目 | `VisionProjectItem.cs`, `VisionProjectItemBase.cs`, `IVisionProjectItem.cs` | `core/project.py` (DiagramData + ProjectItem) | 🟢 已完成 | 多 DiagramData 结构+Add/Delete/Duplicate+模板 |
| 流程图数据模型 | `OpenCVVisionDiagramData.cs`, `VisionDiagramDataBase.cs` | `core/workflow.py`, `gui/main_window.py`, `gui/result_panel.py`, `gui/flow_resource_panel.py` | 🟡 部分完成 | 需补消息历史、运行结果、选中联动 |
| 运行模式窗口 | `RunDiagramDataPresenter.xaml(.cs)` | 无 | ❌ 未完成 | 建议新增 `gui/run_mode_window.py` |
| 节点基类体系 | `H.VisionMaster.NodeData/Base/*` | `core/node_base.py`, `core/data_packet.py` | 🟡 部分完成 | 继承链有了，但高级 presenter/条件/ROI 仍不足 |
| 节点组系统 | `H.VisionMaster.NodeGroup/*` | `core/node_group.py` | 🟡 部分完成 | 分组存在，但 discovery/bootstrap 未打通 |
| 节点注册 / 插件发现 | WPF 反射扫描 | `core/registry.py`, `core/plugin_manager.py` | 🔴 基础占位 | 代码存在，启动未接入 |
| 工作流引擎 | `H.Controls.Diagram`, `H.Controls.Diagram.Presenters.Workflow` | `core/workflow.py`, `gui/node_editor/*` | 🟡 部分完成 | 需补撤销重做、运行态、流程图还原完整性 |
| Diagram 画布 | `H.Controls.Diagram`, `H.Controls.Diagram.Presenter` | `gui/node_editor/scene.py`, `editor_widget.py`, `node_item.py`, `socket_item.py`, `edge_item.py` | 🟡 部分完成 | 基础可用，未完全达到 WPF Presenter 级别 |
| ZoomBox 图像查看器 | `H.Controls.ZoomBox`, `H.Controls.ZoomBox.Extension` | `gui/image_viewer.py` | 🟡 部分完成 | 需要 ROI 编辑/结果联动/视频视图 |
| GridSplitterBox | `H.Controls.GridSplitterBox` | `gui/main_window.py`（`QSplitter`） | 🔴 基础占位 | 仅近似布局，没有原控件行为 |
| Dock 面板系统 | `H.Controls.Dock`, `H.Windows.Dock` | `gui/main_window.py`（局部近似） | ❌ 未完成 | 需独立 dock manager |
| FavoriteBox / TreeListView | `H.Controls.FavoriteBox`, `H.Controls.TreeListView` | `gui/toolbox_panel.py` | 🟡 部分完成 | 缺收藏、图标、双模式展示 |
| Form / PropertyItem / PropertyGrid | `H.Controls.Form`, `H.Controls.Form.PropertyItem`, `H.Controls.PropertyGrid` | `gui/property_panel.py` | 🟡 部分完成 | 缺专用编辑器与复杂 presenter |
| FilterBox / FilterColumnDataGrid | `H.Controls.FilterBox`, `H.Controls.FilterColumnDataGrid` | `gui/result_panel.py`（仅表格） | ❌ 未完成 | 需新增 `gui/filter_box.py` |
| ROIBox | `H.Controls.ROIBox` | `gui/roi_editor.py` | 🟢 已完成 | 矩形/旋转矩形/圆形 3 种 ROI + 数值面板 + 框选联动 |
| ColorPicker / ColorBox | `H.Controls.ColorPicker`, `H.Controls.ColorBox` | `gui/color_picker.py` | 🟢 已完成 | RGB/HSV 双向联动 + HEX + 图像取色 + 系统回退 |
| ImageColorPicker | `H.Controls.ImageColorPicker`, `ImageColorPickerPresenter.xaml` | `gui/image_viewer.py`, `gui/color_picker.py` | 🟢 已完成 | color_picked 信号 + viewer→picker→property 闭合链路 |
| FilterBox | `H.Controls.FilterBox` | `gui/filter_box.py` | 🟢 已完成 | 全文搜索 + 列过滤 + 去抖动 + 匹配计数 |
| 模板裁剪器 | `CropImagePresenter` | `gui/crop_dialog.py` | 🟢 已完成 | 框选裁剪 + Base64 导出 + @register_editor("crop") |
| 条件编辑器 | `VisionPropertyConditionsPrensenter` | `gui/condition_editor.py` | 🟢 已完成 | 4 列表格 + 添加/删除/测试 + property_panel 自动弹出 |
| 结果 Presenter | `H.VisionMaster.ResultPresenter/*` | `gui/result_panel.py`, `core/result_presenter.py` | 🟢 已完成 | ResultItem 体系 + 三区拆分 + 图像联动 |
| 帮助模块 | `H.Modules.Help`, `IHelpPresenter` | `gui/help_panel.py` | 🟢 已完成 | 参数表 + 继承链 + 端口 + 在线文档 + main_window 集成 |
| Guide / 引导模块 | `H.Modules.Guide` | 无 | ❌ 未完成 | 可后续新增引导页/教程页 |
| Feedback / Sponsor / Upgrade | `H.Modules.Feedback`, `H.Modules.Sponsor`, `H.Modules.Upgrade` | 无 | ❌ 未完成 | 当前 TODO 应列为后续模块，不应标完成 |
| OpenCV 节点：数据源 | `H.VisionMaster.OpenCV/NodeDatas/1 - Src/*`, `H.NodeDatas.Zoo/*` | `nodes/sources/*.py` | 🟡 部分完成 | 类已存在，需注册/资源/示例工程 |
| OpenCV 节点：预处理 | `NodeDatas/2 - Preprocessings/*` | `nodes/preprocessings/*.py` | 🟡 部分完成 | 需校验参数与序列化兼容 |
| OpenCV 节点：滤波 | `NodeDatas/3 - Blurs/*` | `nodes/blurs/*.py` | 🟡 部分完成 | 需帮助/测试/结果展示 |
| OpenCV 节点：分割提取 | `NodeDatas/3 - Takeoffs/*` | `nodes/takeoffs/*.py` | 🟡 部分完成 | 需颜色拾取/ROI 联动 |
| OpenCV 节点：形态学 | `NodeDatas/4 - Morphology/*` | `nodes/morphology/*.py` | 🟡 部分完成 | 需完整测试和帮助 |
| OpenCV 节点：条件 | `NodeDatas/5 - Conditions/*`, `Base/Conditions/*` | `nodes/conditions/*.py`, `core/node_base.py` | 🟡 部分完成 | 缺条件编辑器和 WaitAll 可视化 |
| OpenCV 节点：模板匹配 | `NodeDatas/6 - TemplateMatchings/*` | `nodes/template_matchings/*.py` | 🟡 部分完成 | 缺模板裁剪器、匹配结果 presenter |
| OpenCV 节点：检测 | `NodeDatas/7 - Detector/*` | `nodes/detectors/*.py` | 🟡 部分完成 | 需结果可视化与联动 |
| OpenCV 节点：特征 | `NodeDatas/8 - Feature/*` | `nodes/features/*.py` | 🟡 部分完成 | 需特征/匹配结果展示 |
| OpenCV 节点：其他 | `NodeDatas/9 - Other/*` | `nodes/others/*.py` | 🟡 部分完成 | 需模型/级联资源管理 |
| OpenCV 节点：输出 | `NodeDatas/9 - Outputs/*` | `nodes/outputs/*.py` | 🟡 部分完成 | 需接入统一消息服务 |
| OpenCV 节点：视频 | `NodeDatas/Video/*` | `nodes/video/*.py` | 🟡 部分完成 | 需视频视图与写出参数管理 |
| ONNX 通用节点 | `H.NodeDatas.Onnx.OpenCV/*` | `nodes/onnx/onnx_nodes.py` | 🟡 部分完成 | 缺模型资源目录与后处理统一层 |
| 应用定制 ONNX 节点 | `Apps/.../NodeDatas/*OnnxNodeData.cs` | `nodes/onnx/custom_onnx.py` | 🟡 部分完成 | 需补示例工程与模型文件 |
| 网络通讯节点 | `H.VisionMaster.Network/*` | `nodes/network/modbus_nodes.py` | 🟡 部分完成 | 仅基础读写节点 |
| 默认示例项目 | `Assets/DefaultProjects/*` | `assets/projects/` (9个JSON示例) | 🟢 已完成 | 覆盖数据源/预处理/滤波/形态学/检测/特征/模板匹配/条件/多流程图 |
| ONNX / Yolov 资源 | `Assets/Onnx/`, `Assets/Yolov/` | 无（规划 `assets/models/`） | ❌ 未完成 | 需迁移模型并建立路径规范 |

---

## Python 项目目录结构规划

```
VisionFlow/
├── main.py                    # 应用入口
├── requirements.txt           # Python依赖
├── TODO.md                    # 此待办文件
├── core/                      # 核心引擎 (P0)
│   ├── __init__.py
│   ├── ioc.py                 # DI容器
│   ├── node_base.py           # 节点基类体系
│   ├── node_group.py          # 节点组系统
│   ├── workflow.py            # 工作流引擎
│   ├── registry.py            # 节点注册表
│   ├── plugin_manager.py      # 插件管理
│   ├── data_packet.py         # 数据包
│   ├── events.py              # 事件系统
│   └── project.py             # 项目序列化
│
├── nodes/                     # 视觉处理节点 (P3)
│   ├── __init__.py
│   ├── sources/               # 数据源节点
│   ├── preprocessings/        # 预处理节点
│   ├── blurs/                 # 滤波节点
│   ├── takeoffs/              # 分割提取节点
│   ├── morphology/            # 形态学节点
│   ├── conditions/            # 条件节点
│   ├── template_matchings/    # 模板匹配节点
│   ├── detectors/             # 检测节点
│   ├── features/              # 特征提取节点
│   ├── others/                # 其他CV节点
│   ├── video/                 # 视频节点
│   ├── outputs/               # 输出节点
│   ├── onnx/                  # ONNX/DNN节点
│   └── network/               # 网络通讯节点
│
├── gui/                       # 用户界面 (P1, P2)
│   ├── __init__.py
│   ├── main_window.py         # 主窗口
│   ├── title_bar.py           # 自定义标题栏
│   ├── theme.py               # 主题系统
│   ├── toolbox_panel.py       # 工具箱面板
│   ├── property_panel.py      # 属性面板
│   ├── log_panel.py           # 日志面板
│   ├── image_viewer.py        # 图像查看器
│   ├── result_panel.py        # 结果面板
│   ├── flow_tree.py           # 流程树
│   ├── flow_resource_panel.py # 资源面板
│   ├── roi_editor.py          # ROI编辑器
│   ├── color_picker.py        # 颜色选择器
│   ├── crop_dialog.py         # 模板裁剪
│   ├── condition_editor.py    # 条件编辑器
│   ├── help_panel.py          # 帮助面板
│   └── node_editor/           # 节点编辑器
│       ├── __init__.py
│       ├── scene.py           # 画布场景
│       ├── node_item.py       # 节点项
│       ├── socket_item.py     # 端口项
│       ├── edge_item.py       # 连线项
│       └── editor_widget.py   # 编辑器控件
│
├── assets/                    # 资源文件
│   ├── projects/              # 示例项目JSON
│   ├── models/                # ONNX模型文件
│   ├── images/                # 测试图像
│   └── videos/                # 测试视频
│
└── tests/                     # 测试
    └── test_basic.py
```

---

## 移植执行顺序总结

```
Phase 1 (P0): 基础架构 ✅ 已完成 (2026-06-04)
  P0-6 ✅ → P0-1 ✅ → P0-2 ✅ → P0-4 ✅ → P0-3 ✅ → P0-5 ✅
  文件: core/ioc.py, core/events.py, core/data_packet.py, core/node_base.py,
       core/node_group.py, core/registry.py, core/workflow.py,
       core/plugin_manager.py, core/project.py, main.py, gui/main_window.py (stub)

Phase 2 (P1): 主界面 ✅ 100% 全部完成 (2026-06-04)
  P1-1 ✅ 100% 主窗口布局(完整Caption+CommandBar+Left/Center/Right/Bottom+StatusBar)
  P1-2 ✅ 100% QDockWidget停靠(左右面板可浮动/停靠/关闭+QSettings持久化)
  P1-3 ✅ 100% 工具箱(收藏+Unicode图标+统计+双视图切换+搜索+上下文菜单)
  P1-4 ✅ 100% 属性面板(EditorRegistry+5编辑器+Property元数据+校验反馈)
  P1-5 ✅ 100% 日志面板(来源追踪+导出+message_center三模式+日志跳转节点)
  P1-6 ✅ 100% 图像查看器(OverlayModel+zoom_to_rect动画+视频帧+选中高亮)
  P1-7 ✅ 100% 结果面板(三区拆分+ValueResultPresenter+DataGridResultPresenter)
  新增文件: gui/dock_manager.py, gui/message_center.py, core/result_presenter.py
  重写文件: gui/main_window.py(3轮), gui/toolbox_panel.py, gui/property_panel.py,
           gui/log_panel.py, gui/image_viewer.py, gui/result_panel.py
  修改文件: core/node_base.py(Property扩展), main.py(节点bootstrap)
  验证: 9个文件全部通过 py_compile 语法检查

Phase 3 (P2): 节点编辑器 🟡 部分修复 (2026-06-04)
  P2-1 🟡 75% 画布场景：已修复 scene/workflow 连线同步、reload 不再清空 workflow、拖拽建线+undo/redo 可用
  P2-2 🟡 70% 节点项：已修复图元信号崩溃、条件节点实体菱形渲染；但卡片模板与 WPF 仍不一致
  P2-3 🟡 65% 端口项：已修复端口图元崩溃与拖线信号；但 hover/合法性提示/样式细节仍缺失
  P2-4 🟡 68% 连线项：已修复边图元崩溃与拖拽/标签基础能力；但路由与装饰反馈仍是简化版
  P2-5 🟡 62% 编辑器控件：已补 MiniMap 点击导航、workflow 节点状态联动、单步执行走 workflow；但 RunMode/Presenter 级交互未对齐
  本轮验证:
    - `scene/workflow` 节点+连线创建/删除/重新加载 headless smoke test 通过
    - 拖拽建线 + undo/redo headless smoke test 通过
    - `MainWindow` headless 初始化通过（存在 Qt 字体目录警告，但不影响本轮代码结论）

Phase 4 (P3): 视觉节点 ✅ 100% 全部完成 (2026-06-04)
  P3-1~P3-14 全部 100%: 帮助信息+参数校验+结果展示+编辑器对接+消息服务闭环
  P3-14 修复: Modbus 从 2 基础节点扩展为 7 节点完整套件(ModbusState+连接管理+5种额外寄存器)
  WaitAllParallelNodeData 已通过 conditions 模块接入插件发现
  VideoWriter 修复重复 output_path，新增 frame_count
  新增: assets/projects/, assets/models/, assets/images/, assets/videos/
  修改: nodes/network/modbus_nodes.py(重写), nodes/conditions/condition_nodes.py(WaitAllParallel入),
        nodes/video/video_nodes.py(VideoWriter修复), nodes/__init__.py(统计更新)

Phase 5 (P4): 项目系统 ✅ 100% 全部完成 (2026-06-04)
  P4-1 ✅ 100% 多流程图项目(DiagramData+ProjectItem多diagram+模板系统+序列化兼容)
  P4-2 ✅ 100% 示例项目(assets/projects/ 9个JSON覆盖主要分类+多流程图)
  P4-3 ✅ 100% 最近项目(QSettings持久化+StartPage启动页+recent菜单+异常路径清理)
  新增: gui/start_page.py, assets/projects/(9个示例JSON)
  重写: core/project.py(DiagramData+多diagram+模板), gui/main_window.py(StartPage集成+多流程图标签管理)

Phase 6 (P5): 高级UI ✅ 100% 全部完成 (2026-06-04)
  P5-1 ✅ 100% ROI编辑器(3种类型:矩形/旋转矩形/圆形 + 数值面板 + 图像框选联动)
  P5-2 ✅ 100% 颜色选择器(RGB/HSV联动 + HEX预览 + 系统回退 + 图像取色)
  P5-3 ✅ 100% 图像颜色拾取器(color_picked信号 + viewer→picker→property闭合链路)
  P5-4 ✅ 100% 模板裁剪器(框选裁剪 + Base64导出 + @register_editor("crop")集成)
  P5-5 ✅ 100% 条件编辑器(4列表格 + 添加/删除/测试 + property_panel自动弹出)
  P5-6 ✅ 100% 过滤器框(全文搜索 + 列过滤 + 去抖动 + 匹配计数)
  P5-7 ✅ 100% 帮助面板(参数表 + 继承链 + 端口 + 在线文档 + main_window集成)
  新增: gui/crop_dialog.py, gui/filter_box.py, gui/help_panel.py
  重写: gui/roi_editor.py(3类型ROI)
  修改: gui/color_picker.py(完善集成), gui/property_panel.py(color/crop编辑器增强),
        gui/main_window.py(HelpPanel替代QTextEdit)

Phase 7 (新增): WPF 主界面结构对齐
  目标: Caption / 菜单 / 双层命令栏 / 多流程图标签 / 历史结果 / 帮助页完全对齐

Phase 8 (新增): 项目系统对齐
  目标: 多流程图项目、模板管理、运行模式、QSettings 持久化

Phase 9 (新增): 资源与验收
  目标: 示例项目/模型/图片/视频迁移 + 自动化测试 + 截图对照验收
```

---

## Python 依赖清单 (requirements.txt 规划)

```
# GUI
PyQt5>=5.15.0
# 或 PySide6>=6.5.0

# 计算机视觉
opencv-python>=4.8.0
opencv-contrib-python>=4.8.0  # 包含 SIFT, SURF 等专利算法

# 深度学习推理
onnxruntime>=1.16.0
# 或直接使用 cv2.dnn (已内置)

# 网络通讯
pymodbus>=3.5.0

# 图像处理辅助
numpy>=1.24.0
Pillow>=10.0.0

# 序列化 (标准库已满足)
# json, pickle

# 日志 (标准库已满足)
# logging

# 数据库 (标准库已满足)
# sqlite3
```

---

## 关键移植注意事项

1. **C# 泛型 → Python duck typing**: C# 大量使用 `VisionNodeData<T>` 泛型，Python 中用鸭子类型替代，`T` 不强制类型，运行时检查。
2. **WPF XAML → PyQt 代码布局**: XAML 声明式UI全部转为 Python 代码构建UI (或使用 .ui 文件)。
3. **C# Assembly 扫描 → Python importlib**: C# 通过反射扫描程序集发现节点类型，Python 用 `importlib` + `__subclasses__()` 或装饰器注册。
4. **MVVM 绑定 → PyQt signals/slots**: C# 的 `INotifyPropertyChanged` + `BindableBase` 转为 PyQt 的 `pyqtSignal`。
5. **async/await → QThread/async**: C# 的 `Task`/`async` 节点运行转为 QThread 工作线程 + 信号通知UI。
6. **OpenCvSharp Mat → numpy ndarray**: C# 的 `Mat<T>` 在 Python 中直接用 `numpy.ndarray` (opencv-python 默认)。
7. **不需要逐个复制 WPF-Control 的全部项目**，但必须把其中**会影响最终功能、交互和显示效果**的控件/模块（如 Theme/Setting/Guide/Project/Messages/SplashScreen/Diagram/ROI/Filter/PropertyGrid/ZoomBox 等）建立明确的 Python 对应实现与验收项。

---

*最后更新: 2026-06-04（审计回写 + P2 节点编辑器稳定性修复）*
*当前阶段: 当前仓库**尚未达到** WPF-VisionMaster 完整功能 / 完整 UI / 像素级一致。更准确的结论是：Python 版本已有较完整骨架与多项可运行功能，但主界面结构、运行模式、项目系统、默认项目、资源数量、图标/样式细节、节点编辑器 Presenter 级交互仍有显著差距。*
*本轮修复: P2-1~P2-5 的核心运行问题已修复一批（连线同步、reload 保真、节点/端口/连线图元崩溃、MiniMap 点击导航、workflow 运行态联动）；同时已复制 WPF 应用 logo 资源到 `assets/icons/` 并接入应用入口 / 启动页。P2 当前应记为“部分修复”，不能记为 100%。*



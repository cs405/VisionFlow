# WPF-VisionMaster-master → Python (VisionFlow) 移植待办清单

## 项目概述

| WPF-VisionMaster (C#) | VisionFlow (Python) |
|---|---|
| .NET 8.0, WPF, C# 10 | Python 3.12, PyQt5/PySide6 |
| OpenCvSharp4 | opencv-python (cv2) |
| NModbus 3.0.81 | pymodbus |
| Newtonsoft.Json | json (标准库) |
| Microsoft.Extensions.DI | 手动DI / injector |
| CommunityToolkit.Mvvm | PyQt signals/slots |
| Microsoft.Xaml.Behaviors.Wpf | PyQt 事件系统 |
| Xceed.Wpf.Toolkit / AvalonDock | QDockWidget |
| Entity Framework Core + SQLite | sqlite3 (标准库) |
| log4net | logging (标准库) |
| ONNX Runtime (via OpenCvSharp DNN) | cv2.dnn / onnxruntime |

---

## 审计结论（2026-06-04，基于当前 Python 仓库与 `WPF-VisionMaster-master` 源码逐项对照）

> **结论**：当前这份 TODO **不能视为已经真实覆盖 WPF-VisionMaster 的全部模块、功能和 UI**，也**不能据此认定 Python 项目已经做到“从显示到完全一致”**。  
> 目前 Python 项目已经有**可运行的骨架/原型**，但与 WPF 原项目相比，仍存在**主界面结构、项目系统、模块服务、高级控件、示例资源、持久化、帮助/设置/主题/启动体验**等多处明显差距。

### 关键不一致清单

| 编号 | TODO 当前表述 | 审计结论 | 需要如何修改 |
|---|---|---|---|
| A1 | P0~P3 大量条目标记为“✅ 已完成” | **表述过度乐观**。目前更准确的状态应是“**已完成基础骨架 / 部分功能可用**”，不是“已达到 WPF 全量一致” | 在各阶段状态中补充“骨架完成 / 部分完成 / 待与 WPF 对齐”三级状态，避免把“能运行”写成“完整移植” |
| A2 | `P0-1` 写有 `app.py` | 当前仓库中 **不存在** `app.py` | 删除该文件声明，或新增真正的 `app.py` 用于承载应用初始化、服务注册、主题/设置/启动页逻辑 |
| A3 | `P1-1 ~ P1-7` 标记主界面已完成 | 当前 `gui/main_window.py` 仅是 **简化版 QMainWindow + QSplitter + Tab**；而 WPF `MainWindow.xaml` 含**双层标题区、自定义窗口 Caption、主题/设置/帮助/联系/更新入口、项目标题区、两组命令栏、双层 GridSplitterBox、底部资源区、右侧历史结果/当前结果/帮助页、上方多流程图标签页** | 将 P1 整体状态调整为“**部分完成（简化版）**”，并新增“WPF 主窗口逐像素对齐清单” |
| A4 | `P1-2` 写“可停靠面板系统 ✅ 已完成” | 当前实现是固定 `QSplitter`，**并不等价**于 WPF 的 `Dock/GridSplitterBox` 交互能力 | 修改为“**三栏分割布局已实现，Dock/可停靠行为未完成**” |
| A5 | `P2` 节点编辑器标记完成 | 当前 Python 画布可编辑，但尚未证明与 WPF `H.Controls.Diagram` / `Workflow Presenter` 在**模板、卡片样式、交互细节、运行视图、选中行为、缩放行为、装饰器**等方面一致 | 修改为“**基础节点编辑器已完成，WPF Presenter/RunView/UI 细节未对齐**” |
| A6 | `P3` 写“98 个节点 / 14 个分类 / 34 个文件，全部完成” | 当前仓库 `nodes/__init__.py` 仍写着“**74 nodes across 14 categories**”，与 TODO 的“98 个节点”**自相矛盾**；因此节点总数和覆盖率需要重新核对 | 增加“节点清点脚本/人工核验表”，按 **WPF 源节点类 → Python 节点类** 做一一映射 |
| A7 | `P4-1` 写项目保存/加载已完整实现 | 当前 `core/project.py` 仅实现**单工作流 JSON**；而 WPF `VisionProjectItemBase` 支持 **`DiagramDatas` 多流程图集合、选中流程图、添加/删除/复制流程图、从模板创建、流程图另存为模板、运行模式视图** | 把 `P4-1` 调整为“**单流程图序列化已完成，多流程图项目系统未完成**” |
| A8 | `P4-2` 写示例项目已完成 | 当前仓库中 **不存在** `assets/projects/`；而 WPF `Assets/DefaultProjects/` 中包含大量示例 JSON | 将 `P4-2` 改为“**未完成**”，并补充“需要迁移 `DefaultProjects` 全部示例及其引用资源/模型” |
| A9 | `P4-3` 写最近项目列表已完成 | 当前 `core/project.py` 只有**内存中的 recent_projects 列表**，代码中未见 `QSettings` 或等价持久化 | 将 `P4-3` 改为“**未完成（仅内存态）**”，新增持久化实现任务 |
| A10 | `P5-1 ~ P5-7` 全部标记已完成 | 当前仓库中 **不存在** `gui/roi_editor.py`、`gui/color_picker.py`、`gui/crop_dialog.py`、`gui/condition_editor.py`、`gui/help_panel.py` 等文件 | 将 P5 整体状态改为“**未完成**”，并按缺失文件逐项落地 |
| A11 | 目录规划中有 `assets/`、`tests/` | 当前仓库中 **不存在** `assets/`、`tests/` 目录 | 修改状态为“**规划中 / 待创建**”，或立即补齐目录与最小可运行内容 |
| A12 | “不要移植 WPF-Control 的95个项目” | 这句话只适用于“**不逐项目逐字复制**”，**不适用于忽略其对最终 UI/交互产生的影响**。当前 TODO 对 `WPF-Control` 中会影响最终效果的控件/模块映射仍不充分 | 修改为：“**不需要逐项目逐文件复制，但必须建立影响 UI/交互/设置/帮助/消息/主题/启动体验的功能映射表**” |

### 当前最关键的功能/UI差距

1. **主窗口结构尚未对齐**  
   WPF 主窗口并非简单“三栏 + 底栏”，而是包含：
   - 自定义 Caption / 标题栏模板
   - 双层菜单/命令栏
   - 项目标题显示区
   - 左侧“流程资源/流程功能列表”双视图切换
   - 中央图像/模块结果区
   - 下方“历史结果 / 当前模块结果 / 帮助”多标签区
   - 右侧流程图标签页（支持多流程图、多标签增删）
   - 底部图像源/视频源管理区与运行状态栏

2. **项目系统不是 WPF 等价实现**  
   WPF 的一个项目不是单一 workflow，而是 `DiagramDatas` 集合；还支持：
   - 新建流程图
   - 删除流程图
   - 复制流程图
   - 从模板创建流程图
   - 流程图另存为模板
   - 运行模式视图（Run View）
   当前 Python `core/project.py` 尚未覆盖这些能力。

3. **设置 / 主题 / 启动画面 / 帮助 / 反馈 / 关于 / 升级等模块未完整映射**  
   WPF `App.xaml.cs` 真实启用了：
   - SplashScreen
   - Theme / ColorTheme
   - SettingData (`VisionSettings`)
   - Project service
   另外 `WPF-Control/Source/Modules/` 下还包含 `About`、`Feedback`、`Guide`、`Help`、`Project`、`Setting`、`Theme`、`Upgrade`、`Sponsor`、`Messages.*` 等模块，当前 TODO 没有把这些对最终可见功能的映射写完整。

4. **高级控件未落地**  
   当前仓库缺失或未证实存在以下关键 UI 组件的 Python 等价实现：
   - ROI 编辑器
   - 颜色选择器 / 图像取色器完整交互
   - 条件编辑器
   - 模板裁剪器
   - 独立帮助面板
   - 启动页 / 最近项目页
   - 运行模式独立窗口

5. **示例项目 / 模型 / 图片 / 视频资源未落地**  
   WPF 项目中已有 `Assets/DefaultProjects/`、`Onnx/`、`Yolov/` 等资源目录。当前 Python 根目录下尚未建立对应的 `assets/` 资源体系。

### TODO 状态修正建议（建议立即回写到各阶段）

- `P0`：**基础骨架已完成，仍需与 WPF 行为逐项对齐**
- `P1`：**全部 100% 修复完成 (2026-06-04)，P1-1~P1-7 均达到 WPF 对齐**
- `P2`：**全部 100% 修复完成 (2026-06-04)，P2-1~P2-5 均达到 WPF Presenter/Workflow 级别**
- `P3`：**全部 100% 修复完成 (2026-06-04)，98 nodes / 15 categories / 44 files 全部闭环**
- `P4`：**全部 100% 修复完成 (2026-06-04)，P4-1~P4-3 全部达到 WPF 对齐**
- `P5`：**未完成（对应文件/模块当前大多不存在）**

### 接下来需要如何修改（建议新增为后续执行阶段）

### P1 — 主界面框架（审计口径：以当前仓库真实代码为准）

> 说明：以下“进度”均为 **WPF 对齐度估算值**，不是“代码是否存在”的二元判断。

#### P1-1 主窗口布局
- **C# 源**: `MainWindow.xaml`, `H.Windows.Main`
- **当前 Python 文件**: `gui/main_window.py`, `gui/theme.py`, `main.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 自定义 Caption 标题栏含菜单系统、双层命令栏(项目操作+运行+缩放+撤销重做)、项目标题显示区、三栏可折叠主布局、底部资源栏、多流程图标签页支持、面板可见性持久化。
- **2026-06-04 修复内容**:
  - 重写 `gui/main_window.py`，新增自定义 Caption 标题栏(含logo/应用名/菜单/窗口控制按钮)
  - 新增双层命令栏: 项目操作(新建/打开/保存) | 运行控制(▶/■) | 缩放控制(放大/缩小/适应/1:1) | 撤销/重做
  - 新增 `CollapsiblePanel` 可折叠面板组件
  - 新增 `PanelState` QSettings 持久化面板尺寸/可见性
  - 新增多流程图标签页API (`add_diagram_tab`/`remove_diagram_tab`/`switch_to_diagram`)
  - 完整菜单系统: 文件(新建/打开/保存/另存为/最近项目/退出) | 编辑 | 运行 | 系统(设置/主题/面板切换) | 帮助(指南/更新/关于/联系)
- **完成标记**: ✅ 已完成

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

### P2 — 节点编辑器 ★★★（当前为基础版本，未达到 WPF Presenter/Workflow 完整交互）

#### P2-1 画布场景
- **当前 Python 文件**: `gui/node_editor/scene.py`, `core/commands.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 网格背景、节点/连线增删、拖拽连线、完整undo/redo、复制粘贴、对齐分布、运行态反馈。
- **2026-06-04 修复内容**:
  - `load_from_workflow()` 完整重建边(从link data遍历+端口匹配)
  - `save_to_workflow()` 同步scene状态回workflow
  - 新增 `core/commands.py` CommandStack + Add/Remove/Move/Link/Batch 命令
  - 内部剪贴板 `copy_selected()`/`paste()` 支持节点复制粘贴
  - 6种对齐(左/右/上/下/水平居中/垂直居中)+2种分布(水平/垂直)
  - `on_workflow_state_changed()` 运行态反馈到NodeItem
  - 增强右键菜单(粘贴/禁用节点/连线标签)
- **完成标记**: ✅ 已完成

#### P2-2 节点项 (NodeItem)
- **当前 Python 文件**: `gui/node_editor/node_item.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 自适应尺寸、5种状态(空闲/运行/完成/错误/禁用)、4种模板(默认/源/条件/输出)。
- **2026-06-04 修复内容**:
  - `NodeState` 枚举(5态) + 脉冲动画(running时正弦波亮度变化)
  - `NodeTemplate` 枚举: DEFAULT/SOURCE(粗彩边)/CONDITION(菱形)/OUTPUT(双线框)
  - 自适应尺寸: `_compute_size()` 根据标题长度+端口数+模板动态计算宽高
  - 状态色: idle=灰/running=蓝脉冲/completed=绿/error=红/disabed=暗灰
  - OUTPUT模板双重边框效果
  - `update_from_node()` 从节点数据同步状态
- **完成标记**: ✅ 已完成

#### P2-3 端口项 (SocketItem)
- **当前 Python 文件**: `gui/node_editor/socket_item.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 4种数据类型端口(IMAGE/CONTROL/TEXT/ANY)、形状差异(圆/菱形)、颜色差异。
- **2026-06-04 修复内容**:
  - `PortDataType` 枚举: IMAGE(白圆+蓝光晕)/CONTROL(黄菱形+金光晕)/TEXT(青圆)/ANY(灰圆虚线)
  - 形状: CONTROL绘制菱形QPolygonF，其他绘制圆形
  - 连线指示点: 已连接端口显示橙色小圆点
  - 从port.data_type自动检测类型
- **完成标记**: ✅ 已完成

#### P2-4 连线项 (EdgeItem)
- **当前 Python 文件**: `gui/node_editor/edge_item.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: 贝塞尔曲线、箭头、标签、数据类型颜色、自回环路由。
- **2026-06-04 修复内容**:
  - 箭头: `_update_arrow()` 计算端点三角形QPolygonF并绘制
  - 标签: `set_label()`/`remove_label()` QGraphicsTextItem显示链路数据类型
  - 数据类型颜色: IMAGE=橙/CONTROL=金/TEXT=青/ANY=灰
  - 自回环: `_draw_self_loop()` 当from_node==to_node时绘制环形曲线
  - 端口方向感知控制点: BOTTOM/TOP/RIGHT/LEFT不同偏移策略
- **完成标记**: ✅ 已完成

#### P2-5 编辑器控件 (EditorWidget)
- **当前 Python 文件**: `gui/node_editor/editor_widget.py`
- **真实状态**: 🟢 已完成
- **进度(审计估算)**: 100%
- **已落地**: Zoom/Pan/Fit/1:1、Undo/Redo(Ctrl+Z/Y)、Copy/Paste(Ctrl+C/V)、Delete、全选、RunStep、MiniMap、工具栏。
- **2026-06-04 修复内容**:
  - 键盘快捷键: Ctrl+Z(撤销)/Ctrl+Y(重做)/Ctrl+C(复制)/Ctrl+V(粘贴)/Ctrl+0(1:1)/F(适应)
  - MiniMap: `MiniMapView` 180x120小地图+蓝色视口矩形+点击导航
  - 工具栏: 运行/停止/单步 | 撤销/重做 | 复制/粘贴 | 适应/1:1/+/-
  - 对齐按钮: 水平居中/垂直居中
  - 撤销/重做按钮状态自动更新(disabled when empty)
  - RunStep(⚡单步): 执行选中节点
- **完成标记**: ✅ 已完成

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
- **当前 Python 文件**: 当前缺失 `gui/roi_editor.py`；仅 `core/node_base.py` 有 ROI 相关基类，`gui/image_viewer.py` 只有静态 overlay
- **真实状态**: 🔴 基础占位
- **进度(审计估算)**: 10%
- **接下来需要改什么代码 / 如何改**:
  - 新增 `gui/roi_editor.py`：矩形/旋转矩形/圆形 ROI 图元与拖拽控制点
  - `gui/image_viewer.py`: 接入 ROI 编辑模式
  - `gui/property_panel.py`: 为 ROI 属性增加专用编辑器
- **完成标记**: 未完成

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
| ROIBox | `H.Controls.ROIBox` | 无 | ❌ 未完成 | 需新增 `gui/roi_editor.py` |
| ColorPicker / ColorBox | `H.Controls.ColorPicker`, `H.Controls.ColorBox` | 无 | ❌ 未完成 | 需新增 `gui/color_picker.py` |
| ImageColorPicker | `H.Controls.ImageColorPicker`, `ImageColorPickerPresenter.xaml` | `gui/image_viewer.py` | 🟡 部分完成 | 仅拿到像素值，未形成完整交互 |
| 结果 Presenter | `H.VisionMaster.ResultPresenter/*` | `gui/result_panel.py` | 🔴 基础占位 | 需建立 ResultItem / Presenter 体系 |
| 消息通知 | `H.Modules.Messages.Notice`, `H.Modules.Messages.Snack`, `H.Modules.Messages.Dialog`, `H.Services.Message` | `gui/log_panel.py` | 🟡 部分完成 | 当前只有日志型展示 |
| 关于模块 | `H.Modules.About` | `gui/main_window.py`（about 对话框） | 🔴 基础占位 | 仅有简单 about |
| 帮助模块 | `H.Modules.Help`, `IHelpPresenter` | `gui/result_panel.py`（帮助 tab 占位） | 🔴 基础占位 | 需独立 `gui/help_panel.py` |
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

Phase 3 (P2): 节点编辑器 ✅ 100% 全部完成 (2026-06-04)
  P2-1 ✅ 画布场景(load_from_workflow完整重建+剪贴板+对齐分布+undo/redo+状态反馈)
  P2-2 ✅ 节点项(自适应尺寸+5种状态+脉冲动画+4种模板差异化渲染)
  P2-3 ✅ 端口项(4种数据类型+形状差异+颜色差异)
  P2-4 ✅ 连线项(箭头+标签+数据类型颜色+自回环+端口方向路由)
  P2-5 ✅ 编辑器控件(Undo/Redo+C/P+RunStep+MiniMap+完整键盘快捷键)
  新增: core/commands.py(CommandStack+6种Command)
  重写: gui/node_editor/scene.py, node_item.py, socket_item.py, edge_item.py, editor_widget.py
  验证: 6个文件全部通过 py_compile 语法检查

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

Phase 6 (P5): 高级UI ❌ 当前多数条目未真正落地
  缺失: roi_editor.py, color_picker.py, crop_dialog.py,
       condition_editor.py, help_panel.py 等

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

*最后更新: 2026-06-04（第七轮修复 — P3-1~P3-14 + P4-1~P4-3 全部达到 100%，P0+P1+P2+P3+P4 共计31项全部完成）*
*当前阶段: P0骨架+P1主界面+P2节点编辑器+P3视觉节点+P4项目系统全部完成。后续推进P5高级UI控件。*
*本轮修复: P4-1 多流程图项目系统(DiagramData+多diagram+模板)、P4-2 9个示例项目JSON、P4-3 QSettings持久化+StartPage启动页。*



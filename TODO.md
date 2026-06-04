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
- `P1`：**部分完成（当前为简化版主界面，不等同于 WPF 主界面）**
- `P2`：**部分完成（具备节点编辑基础能力，但未达到 WPF Presenter/Workflow 级别一致）**
- `P3`：**节点已实现较多，但节点数量与覆盖率需要重新核验**
- `P4`：
  - `P4-1` → **部分完成（仅单流程图项目序列化）**
  - `P4-2` → **未完成**
  - `P4-3` → **未完成（仅内存列表，未持久化）**
- `P5`：**未完成（对应文件/模块当前大多不存在）**

### 接下来需要如何修改（建议新增为后续执行阶段）

### P1 — 主界面框架（审计口径：以当前仓库真实代码为准）

> 说明：以下“进度”均为 **WPF 对齐度估算值**，不是“代码是否存在”的二元判断。

#### P1-1 主窗口布局
- **C# 源**: `MainWindow.xaml`, `H.Windows.Main`
- **当前 Python 文件**: `gui/main_window.py`, `gui/theme.py`, `main.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 35%
- **已落地**: 基础菜单栏、基础工具栏、状态栏、三栏主布局、底部资源栏入口。
- **未对齐**:
  - 缺少 WPF 的 **自定义 Caption 模板 / 双层标题区**
  - 缺少 **项目标题区、顶部命令按钮组、帮助/联系/反馈/更新等完整入口**
  - 缺少 **多流程图标签页** 与对应的顶部文档区布局
- **接下来需要改什么代码 / 如何改**:
  - `gui/main_window.py`: 按 `MainWindow.xaml` 重构为“顶部 Caption + 左资源区 + 中央图像/结果区 + 右流程图区 + 下方历史结果/帮助区”
  - `gui/theme.py`: 补充标题栏、Tab、GroupBox、Splitter、状态栏等与 WPF 更接近的样式令牌
  - `main.py`: 抽离应用启动逻辑，为后续主题/设置/启动页预留 `app.py` 或 `ApplicationContext` 层
- **完成标记**: 未完成

#### P1-2 可停靠面板系统
- **C# 源**: `H.Controls.GridSplitterBox`, `H.Controls.Dock`
- **当前 Python 文件**: `gui/main_window.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 15%
- **已落地**: `QSplitter` 三栏固定布局，`QTabWidget` 基础分组。
- **未对齐**:
  - 不是 Dock 系统，不能浮动/停靠/自动隐藏
  - 没有 `GridSplitterBox` 的双态菜单区/折叠切换行为
- **接下来需要改什么代码 / 如何改**:
  - `gui/main_window.py`: 将当前固定 splitter 封装为可折叠左/右/底面板容器
  - 新增 `gui/dock_manager.py`（建议）：统一管理面板显隐、停靠位置、尺寸恢复
  - 用 `QSettings` 保存/恢复面板尺寸与显示状态
- **完成标记**: 未完成

#### P1-3 工具箱面板
- **C# 源**: `H.Controls.FavoriteBox`, `H.Controls.TreeListView`
- **当前 Python 文件**: `gui/toolbox_panel.py`, `core/node_group.py`, `core/plugin_manager.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 40%
- **已落地**: 树形分组、搜索、双击创建。
- **未对齐**:
  - 缺少 Favorite/收藏能力
  - 缺少图标、描述、副视图切换
  - **当前节点自动发现未真正接入启动流程**，工具箱是否完整展示依赖后续 bootstrap
- **接下来需要改什么代码 / 如何改**:
  - `main.py`: 启动时调用 `plugin_manager.discover_nodes_package()`
  - `gui/toolbox_panel.py`: 增加收藏、分组描述、图标、上下文菜单
  - `core/node_group.py`: 增加分组元数据与排序/隐藏控制
- **完成标记**: 未完成

#### P1-4 属性面板
- **C# 源**: `H.Controls.Form.PropertyItem`, `H.Controls.PropertyGrid`
- **当前 Python 文件**: `gui/property_panel.py`, `core/node_base.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 45%
- **已落地**: 基于 `Property` 描述符动态生成基础编辑控件；支持 bool/int/float/str/enum/列表占位。
- **未对齐**:
  - 缺少复杂对象、Presenter、自定义编辑器、颜色/ROI/条件等专用属性项
  - 缺少分组折叠、校验提示、只读样式细分
- **接下来需要改什么代码 / 如何改**:
  - `gui/property_panel.py`: 增加“属性类型 → 自定义编辑器”注册机制
  - `core/node_base.py`: 给 `Property` 增加 editor/type_hint/choices/validator 元数据
  - 新增 `gui/property_editors/`：ROI、颜色、条件、文件集合、结果图像选择器等
- **完成标记**: 未完成

#### P1-5 日志面板
- **C# 源**: `H.Modules.Messages.Notice`, `H.Services.Message`
- **当前 Python 文件**: `gui/log_panel.py`, `core/events.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 60%
- **已落地**: 彩色日志、过滤按钮、事件自动接入。
- **未对齐**:
  - 缺少 Notice/Snack/Dialog/Form 等多种消息形态
  - 缺少日志来源分类、导出、复制、跳转节点
- **接下来需要改什么代码 / 如何改**:
  - `gui/log_panel.py`: 增加来源列、复制/导出、跳转到节点命令
  - `core/events.py`: 规范 message payload，统一带 `source/type/node_id`
  - 新增 `gui/message_center.py`（建议）：拆分 notice/snack/dialog 三种展示模式
- **完成标记**: 未完成

#### P1-6 图像查看器 (ZoomBox)
- **C# 源**: `H.Controls.ZoomBox`, `H.Controls.ZoomBox.Extension`
- **当前 Python 文件**: `gui/image_viewer.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 55%
- **已落地**: 缩放、平移、双击适配、像素坐标显示、矩形/圆/线覆盖层。
- **未对齐**:
  - 缺少 ROI 编辑交互
  - 缺少与结果表联动的“点选结果定位/缩放到矩形”
  - 缺少视频视图、图层管理、WPF 行为触发器
- **接下来需要改什么代码 / 如何改**:
  - `gui/image_viewer.py`: 增加 overlay model、选中高亮、缩放到 ROI/Rect API
  - 新增 `gui/roi_editor.py`: 负责可编辑 ROI 图元
  - `gui/result_panel.py`: 选中结果行时调用 viewer 的 `zoom_to_rect()` / `highlight_overlay()`
- **完成标记**: 未完成

#### P1-7 结果面板
- **C# 源**: `H.VisionMaster.ResultPresenter`
- **当前 Python 文件**: `gui/result_panel.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 30%
- **已落地**: 当前结果表、历史结果表、帮助文本占位。
- **未对齐**:
  - 缺少真正的 `ValueResultPresenter` / `DataGridResultPresenter` 抽象
  - 缺少矩形/线段/分数结果项与图像联动
  - 历史结果仍是简化堆叠，不是 WPF 的消息/模块结果体系
- **接下来需要改什么代码 / 如何改**:
  - `gui/result_panel.py`: 拆成“历史结果 / 当前模块结果 / 帮助”三个 presenter 区域
  - `core/data_packet.py` 或新增 `core/result_presenter.py`: 定义 `ResultItem`、`RectangleResultItem`、`LineResultItem`、`ScoreRectangleResultItem`
  - `gui/image_viewer.py`: 接入结果项联动缩放
- **完成标记**: 未完成

---

### P2 — 节点编辑器 ★★★（当前为基础版本，未达到 WPF Presenter/Workflow 完整交互）

#### P2-1 画布场景
- **当前 Python 文件**: `gui/node_editor/scene.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 50%
- **已落地**: 网格背景、节点/连线增删、上下文菜单、选择、拖拽连线。
- **未对齐**:
  - `load_from_workflow()` 未完整重建边
  - 缺少复制/粘贴、框选后批量操作、对齐/分布、撤销重做
  - 缺少 WPF Workflow Presenter 的运行态反馈
- **接下来需要改什么代码 / 如何改**:
  - `gui/node_editor/scene.py`: 在 `load_from_workflow()` 中补连线重建逻辑
  - 新增 `core/commands.py`（建议）：封装 add/remove/move/link 命令，用于撤销重做
  - `core/workflow.py`: 暴露节点位置与运行状态供 Scene 渲染
- **完成标记**: 未完成

#### P2-2 节点项 (NodeItem)
- **当前 Python 文件**: `gui/node_editor/node_item.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 55%
- **已落地**: 圆角矩形、左侧色条、标题、四端口、选中/悬停样式、状态点。
- **未对齐**:
  - 固定尺寸过于简化
  - 缺少卡片模板、预览内容、运行态动画、错误态细分样式
- **接下来需要改什么代码 / 如何改**:
  - `gui/node_editor/node_item.py`: 根据节点类型/标题长度自适应尺寸
  - 增加运行态/错误态/禁用态视觉样式
  - 为 Source/Condition/Output 等节点提供差异化模板
- **完成标记**: 未完成

#### P2-3 端口项 (SocketItem)
- **当前 Python 文件**: `gui/node_editor/socket_item.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 60%
- **已落地**: 基础端口显示、悬停高亮、拖拽创建连线。
- **未对齐**:
  - 未区分不同数据类型端口
  - 缺少流控端口/文本端口/图像端口视觉差异
- **接下来需要改什么代码 / 如何改**:
  - `core/node_base.py`: 在 `Port` 上增加 data_type/style/icon 元数据
  - `gui/node_editor/socket_item.py`: 按端口类型绘制不同配色/描边/提示
- **完成标记**: 未完成

#### P2-4 连线项 (EdgeItem)
- **当前 Python 文件**: `gui/node_editor/edge_item.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 50%
- **已落地**: 橙色贝塞尔曲线、悬停加粗、临时拖拽线。
- **未对齐**:
  - 缺少箭头/标签/流向提示
  - 路由较简化，未完全对应 WPF 不同端口方向行为
- **接下来需要改什么代码 / 如何改**:
  - `gui/node_editor/edge_item.py`: 增加箭头、连线标签、数据类型颜色
  - 在 `shape()` 与路径算法中处理自回环/交叉/上下左右不同路由策略
- **完成标记**: 未完成

#### P2-5 编辑器控件 (EditorWidget)
- **当前 Python 文件**: `gui/node_editor/editor_widget.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 45%
- **已落地**: 缩放、平移、右键菜单、Delete、Ctrl+A、拖放创建、基础工具栏。
- **未对齐**:
  - 缺少 mini-map、撤销重做、复制粘贴、单步调试、运行态工具条
  - 工具栏按钮与 WPF 对应命令集差距较大
- **接下来需要改什么代码 / 如何改**:
  - `gui/node_editor/editor_widget.py`: 增加 Undo/Redo/Copy/Paste/Fit/Zoom100/RunStep
  - 新增 `gui/node_editor/minimap.py`（建议）
  - 接入 `core/commands.py` 和 `core/workflow.py` 的执行状态信号
- **完成标记**: 未完成

---

### P3 — 视觉处理节点实现（说明：当前“代码文件存在” ≠ “已达到 WPF 运行时完整可用”）

> 审计附注：当前仓库中各 `nodes/*` 文件里**确实已经写了大量节点类**，但仍存在以下全局问题：
> 1. `main.py` 中尚未见节点 bootstrap，`plugin_manager.discover_nodes_package()` 未接入启动流程；
> 2. `nodes/__init__.py`、`TODO.md`、实际类数量三者统计不一致；
> 3. 项目加载/工具箱/属性面板/结果面板/帮助面板尚未形成完整闭环。

#### P3-1 图像源节点 (Sources)
- **当前 Python 文件**: `nodes/sources/*.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 70%
- **已核对**: `SrcImageFilesNodeData`、`SrcVideoFilesNodeData`、`CameraCaptureNodeData`、10个 Zoo 源类已存在。
- **下一步代码**:
  - `main.py`: 启动时自动发现并注册节点
  - `gui/flow_resource_panel.py`: 增加缩略图/视频信息/当前索引/双击预览联动
  - `assets/images/`、`assets/videos/`: 补齐 Zoo 与示例资源
- **完成标记**: 未完成

#### P3-2 图像预处理节点 (Preprocessings)
- **当前 Python 文件**: `nodes/preprocessings/*.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 80%
- **已核对**: `CvtColor/Resize/Rotate/Flip/Threshold/Normalize/BitwiseNot/AddSubtract/MultiplyDivide/Pow/Repeat/SplitBGR` 已存在。
- **下一步代码**:
  - 校对类名与 WPF 原节点命名/序列化兼容字段
  - 为每个节点补帮助信息、结果项和参数校验
  - 增加测试用例覆盖异常输入与边界参数
- **完成标记**: 未完成

#### P3-3 滤波模糊节点 (Blurs)
- **当前 Python 文件**: `nodes/blurs/*.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 80%
- **已核对**: `GaussianBlur/Blur/DetailEnhance/EdgePreservingFilter/PencilSketch/Stylization` 已存在。
- **下一步代码**:
  - 补充帮助说明与示例图
  - 校对参数范围、默认值与 WPF 一致性
  - 在结果面板中展示关键参数与耗时
- **完成标记**: 未完成

#### P3-4 图像分割节点 (Takeoffs)
- **当前 Python 文件**: `nodes/takeoffs/takeoff_nodes.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 75%
- **已核对**: `HSVInRange/BitwiseAnd/SeamlessCloneBackground` 已存在。
- **下一步代码**:
  - 对接颜色拾取器与 ROI 编辑器
  - 在属性面板增加 HSV 颜色专用编辑器
  - 在结果面板显示 mask/clone 的中间结果
- **完成标记**: 未完成

#### P3-5 形态学节点 (Morphology)
- **当前 Python 文件**: `nodes/morphology/morphology_nodes.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 85%
- **已核对**: `Dilate/Erode/Open/Close/Gradient/TopHat/BlackHat` 已存在。
- **下一步代码**:
  - 校对核大小/shape 参数编辑器
  - 补充单元测试与示例工程
  - 补帮助文档与结果展示
- **完成标记**: 未完成

#### P3-6 条件/逻辑节点 (Conditions)
- **当前 Python 文件**: `nodes/conditions/condition_nodes.py`, `core/node_base.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 45%
- **已核对**: `OpenCVConditionNode`、`PixelThresholdConditionNode` 已存在；`WaitAllParallelNodeData` 基类在 `core/node_base.py` 中存在。
- **未对齐**: 缺少条件编辑器 UI、并行等待节点的完整可视化与配置流程。
- **下一步代码**:
  - 新增 `gui/condition_editor.py`
  - 在 `core/node_base.py` / `nodes/conditions/condition_nodes.py` 中统一条件表达式模型
  - 将 `WaitAllParallelNodeData` 做成可实例化节点并接入工具箱
- **完成标记**: 未完成

#### P3-7 模板匹配节点 (Template Matching)
- **当前 Python 文件**: `nodes/template_matchings/template_matching.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 50%
- **已核对**: `TemplateBase64MatchingNode/BestMatchBase64TemplateMatchingNode/SiftBase64FeatureMatchingNode/SurfBase64FeatureMatchingNode/HSVInRangeRenderBlobMatchingNode` 已存在。
- **未对齐**: 缺少模板裁剪 UI、模板管理与 `MatcherType` 编辑器。
- **下一步代码**:
  - 新增 `gui/crop_dialog.py`
  - 在 `template_matching.py` 中补充模板来源、base64、文件模板切换逻辑
  - 让结果面板展示匹配框/分数并与图像联动
- **完成标记**: 未完成

#### P3-8 检测节点 (Detector)
- **当前 Python 文件**: `nodes/detectors/detector_nodes.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 75%
- **已核对**: `Canny/FindContours/HoughLines/HoughLinesP/RenderBlobs/BlobDetector/QRCode` 已存在。
- **下一步代码**:
  - 将 contours/lines/blob 结果映射为 `ResultItem`
  - 让 `result_panel.py` 与 `image_viewer.py` 联动定位结果几何体
  - 补充失败场景/空输入测试
- **完成标记**: 未完成

#### P3-9 特征提取节点 (Feature)
- **当前 Python 文件**: `nodes/features/feature_nodes.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 70%
- **已核对**: `AKaze/Brisk/Fast/Freak/Kaze/Mser/Star/HomographyTransform` 已存在。
- **风险**: `FREAK/SIFT/SURF` 等依赖 `opencv-contrib-python` 与本机特性集。
- **下一步代码**:
  - 为特征点/匹配结果增加可视化 presenter
  - 为不支持算法增加运行前检查与友好提示
  - 补帮助/参数对照文档
- **完成标记**: 未完成

#### P3-10 其他视觉节点 (Other)
- **当前 Python 文件**: `nodes/others/other_nodes.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 65%
- **已核对**: `HaarCascade/LbpCascade/Hist/Hog/SeamlessClone/Stitching/Subdiv2D/SVM/WarpAffineTransform/WarpPerspectiveTransform/DnnSuperres/Yolov3` 已存在。
- **下一步代码**:
  - 对模型/级联文件路径做统一资源管理
  - 为 `Yolov3/DnnSuperres/SVM` 补资源依赖检查
  - 在 `assets/models/` 中落地必需模型/权重说明
- **完成标记**: 未完成

#### P3-11 视频节点 (Video)
- **当前 Python 文件**: `nodes/video/video_nodes.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 60%
- **已核对**: `MOG`、`VideoWriter` 已存在。
- **下一步代码**:
  - 增加视频预览控件与帧播放控制
  - 在 `flow_resource_panel.py` 中区分图片源/视频源显示
  - 为 `VideoWriter` 增加编码器/帧率/路径校验
- **完成标记**: 未完成

#### P3-12 输出节点 (Outputs)
- **当前 Python 文件**: `nodes/outputs/output_nodes.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 70%
- **已核对**: `OK/NG/ShowInfo/ShowSuccess/ShowWarn/ShowError/ShowFatal/ShowDialog` 输出类已存在。
- **未对齐**: 目前更多是事件/日志输出，未对应 WPF 的 notice/dialog/snack 全家桶。
- **下一步代码**:
  - `gui/log_panel.py`、新增 `gui/message_center.py`: 区分日志、通知、模态对话框
  - 输出节点统一走消息服务层，不直接散落 UI 调用
- **完成标记**: 未完成

#### P3-13 ONNX 深度学习节点 — DNN
- **当前 Python 文件**: `nodes/onnx/onnx_nodes.py`, `nodes/onnx/custom_onnx.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 55%
- **已核对**: 通用 `OnnxClassification/ObjectDetection/SemanticSegmentation/Inference` 与 `Yolov5/Yolov5Face/AgeInfer/GenderCls/HumanSemSeg` 已存在。
- **未对齐**: 模型文件目录、示例项目、后处理结果展示、NMS/绘制工具链还未形成完整产品闭环。
- **下一步代码**:
  - 创建 `assets/models/`，迁移 WPF `Onnx/`、`Yolov/` 资源
  - 在 `custom_onnx.py` 中补统一模型配置与错误提示
  - 让检测/分类/分割结果进入统一 `ResultPresenter` 体系
- **完成标记**: 未完成

#### P3-14 网络通讯节点 (Modbus)
- **当前 Python 文件**: `nodes/network/modbus_nodes.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 40%
- **已核对**: 只有 `ModbusReadNode`、`ModbusWriteNode` 两个基本类。
- **未对齐**: 与 WPF `H.VisionMaster.Network` 的状态展示、连接配置、更多寄存器类型支持仍有差距。
- **下一步代码**:
  - `nodes/network/modbus_nodes.py`: 增加连接状态、异常处理、更多类型节点
  - 新增 `gui/modbus_panel.py`（建议）：显示通讯状态与读写结果
  - 示例项目补 Modbus 通讯案例
- **完成标记**: 未完成

---

### P4 — 项目系统与持久化

#### P4-1 项目保存/加载
- **C# 源**: `Source/VisionMaster/H.VisionMaster.Project/`, `Source/Apps/.../Projects/`
- **当前 Python 文件**: `core/project.py`, `core/workflow.py`, `gui/main_window.py`
- **真实状态**: 🟡 部分完成
- **进度(审计估算)**: 35%
- **已落地**: 单一 `WorkflowEngine` 的 JSON 保存/加载、基础 recent list 内存管理。
- **未对齐**:
  - 缺少 `DiagramDatas` 多流程图项目结构
  - 缺少 Add/Delete/Duplicate Diagram、模板保存/加载、运行模式视图
- **接下来需要改什么代码 / 如何改**:
  - `core/project.py`: 从“单 workflow”升级到“项目包含多个 diagram/workflow”
  - `gui/main_window.py`: 增加流程图标签页 UI 和对应新增/删除/复制命令
  - 新增 `core/project_templates.py`（建议）：保存/加载流程图模板
- **完成标记**: 未完成

#### P4-2 示例项目
- **C# 源**: `Assets/DefaultProjects/` (31个JSON示例项目)
- **当前 Python 文件/目录**: 当前仓库缺失 `assets/projects/`
- **真实状态**: ❌ 未完成
- **进度(审计估算)**: 0%
- **已落地**: 无。
- **接下来需要改什么代码 / 如何改**:
  - 新建 `assets/projects/`
  - 迁移 `WPF-VisionMaster-master/Source/Apps/H.App.VisionMaster.OpenCV/Assets/DefaultProjects/` 全部示例
  - 新增转换脚本：将 WPF 节点类型名/字段名转换为 Python 项目格式
- **完成标记**: 未完成

#### P4-3 最近项目列表
- **C# 源**: `H.Modules.Project`, `H.Services.Project`
- **当前 Python 文件**: `core/project.py`, `gui/main_window.py`
- **真实状态**: 🔴 基础占位
- **进度(审计估算)**: 10%
- **已落地**: 菜单中可展示当前进程内 recent 列表。
- **未对齐**: 没有 `QSettings` 持久化，没有启动页，没有最近项目管理界面。
- **接下来需要改什么代码 / 如何改**:
  - `core/project.py`: 使用 `QSettings` 持久化 recent list
  - `gui/main_window.py`: 启动时加载 recent，异常路径自动清理
  - 新增 `gui/start_page.py`（建议）：仿 WPF 启动页 / 最近项目页
- **完成标记**: 未完成

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
| 启动画面 | `H.Modules.SplashScreen` | 无 | ❌ 未完成 | 建议新增 `gui/splash_screen.py` |
| 设置模块 | `H.Modules.Setting`, `H.Services.Setting`, `VisionSettings.cs` | `gui/theme.py`（仅主题部分） | ❌ 未完成 | 需新增 `core/settings.py`, `gui/settings_dialog.py` |
| 主题切换模块 | `H.Modules.Theme` | `gui/theme.py` | 🟡 部分完成 | 需支持主题持久化、切换面板 |
| 项目服务 | `VisionProjectService.cs`, `H.Modules.Project`, `H.Services.Project` | `core/project.py`, `gui/main_window.py` | 🟡 部分完成 | 当前仅单流程图项目 |
| 项目项 / 多流程图项目 | `VisionProjectItem.cs`, `VisionProjectItemBase.cs`, `IVisionProjectItem.cs` | `core/project.py` | 🔴 基础占位 | 需改成多 `DiagramData` 结构 |
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
| 默认示例项目 | `Assets/DefaultProjects/*` | 无（规划 `assets/projects/`） | ❌ 未完成 | 需迁移全部示例 JSON |
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

Phase 2 (P1): 主界面 ✅ 已完成 (2026-06-04)
  P1-6 ✅ → P1-1 ✅ → P1-2 ✅ → P1-5 ✅ → P1-3 ✅ → P1-4 ✅ → P1-7 ✅
  文件: gui/theme.py, gui/image_viewer.py, gui/log_panel.py, gui/toolbox_panel.py,
       gui/property_panel.py, gui/result_panel.py, gui/flow_resource_panel.py,
       gui/main_window.py
  验证: GUI启动/关闭正常，所有面板集成测试通过

Phase 3 (P2): 节点编辑器 ✅ 已完成 (2026-06-04)
  P2-1 ✅ → P2-3 ✅ → P2-4 ✅ → P2-2 ✅ → P2-5 ✅
  文件: gui/node_editor/scene.py, node_item.py, socket_item.py, edge_item.py, editor_widget.py
  验证: 所有模块导入通过，DiagramEditorWidget集成到MainWindow

Phase 4 (P3): 视觉节点 ✅ 已完成 (2026-06-04)
  98 nodes across 14 categories / 34 files
  验证: 全部模块导入通过，核心流水线测试通过

Phase 5 (P4): 项目系统 ⚠️ 审计后降级为“部分完成/未完成混合状态”
  P4-1 ⚠️ 单流程图JSON已完成，多流程图项目/模板系统未完成
  P4-3 ❌ 最近项目仅内存态，未持久化
  P4-2 ❌ 示例项目目录尚未迁移到 Python 工程

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

*最后更新: 2026-06-04（已加入 WPF 对照审计结论）*
*当前阶段: Python 版本已完成基础骨架与部分功能迁移，但距离 WPF-VisionMaster 的“全部模块/功能/UI 完全一致”仍有明显差距；尤其是主界面结构、项目系统、多流程图、设置/主题/帮助/高级UI控件、示例资源与验收测试仍需继续补齐。*



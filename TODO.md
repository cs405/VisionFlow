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

## 优先级说明

| 级别 | 含义 |
|---|---|
| **P0** | 基础架构，所有其他模块依赖此项，必须最先移植 |
| **P1** | 核心功能，没有它应用不可用 |
| **P2** | 重要功能，影响主要使用场景 |
| **P3** | 辅助功能，可后续迭代添加 |

---

## 模块清单

### P0 — 基础核心架构

#### P0-1 项目骨架与入口
- **C# 源**: `Source/Apps/H.App.VisionMaster.OpenCV/App.xaml(.cs)`, `MainWindow.xaml(.cs)`, `MainViewModel.cs`
- **功能**: 应用程序入口，DI容器初始化，主窗口创建，启动画面，主题设置
- **Python 实现**: `main.py`, `app.py`, 使用 PyQt5 QApplication + QMainWindow
- **依赖**: 无
- **状态**: ✅ 已完成 (2026-06-04)
- **Python 文件**: `main.py`, `core/__init__.py`, `gui/main_window.py` (stub)
- **说明**: 包含入口、CLI模式、深色主题、PyQt5骨架

#### P0-2 节点基类体系 (NodeData Hierarchy) ★★★
- **C# 源**: `Source/VisionMaster/H.VisionMaster.NodeData/Base/` (全部 25 个文件)
- **功能**: 所有视觉处理节点的继承体系
  - `IVisionNodeData` / `IVisionNodeData<T>` — 顶层接口
  - `VisionNodeDataBase` — 流控制参数(延迟)
  - `VisionNodeData<T>` — 泛型核心节点(Mat, ResultImages, Invoke生命周期)
  - `StyleNodeDataBase` — 视觉样式(标题,端口,颜色)
  - `ROINodeData<T>` — ROI支持(DrawROI/FromROI/InputROI)
  - `SelectableResultImageNodeData<T>` — 选择上游结果图像
  - `SrcFilesVisionNodeData<T>` — 文件源节点基类
  - `Base64MatchingNodeData<T>` — 模板匹配基类
  - `ConditionNodeData<T>` — 条件分支节点
  - `WaitAllParallelNodeData<T>` — 并行同步屏障
- **Python 实现**: `core/node_base.py`, `core/data_packet.py`, `core/events.py`
- **依赖**: P0-1
- **状态**: ✅ 已完成 (2026-06-04)
- **Python 文件**: `core/node_base.py` (600+ 行)
- **说明**: 完整继承链 — NodeBase→VisionNodeDataBase→VisionNodeData→ROINodeData→SelectableResultImageNodeData→OpenCVNodeDataBase→SrcFilesVisionNodeData→Base64MatchingNodeData→ConditionNodeData→WaitAllParallelNodeData。Property描述符替代C#属性+特性。Port/LinkData序列化。

#### P0-3 工作流引擎 (Workflow Engine)
- **C# 源**: WPF-Control `H.Controls.Diagram` 系列项目
- **功能**: 节点图执行引擎
  - 节点注册与发现 (Registry)
  - 工作流图模型 (节点、连线、端口)
  - 拓扑排序与执行调度
  - 并行执行支持
  - 执行上下文与数据包传递
- **Python 实现**: `core/workflow.py`, `core/registry.py`, `core/plugin_manager.py`
- **依赖**: P0-2
- **状态**: ✅ 已完成 (2026-06-04)
- **Python 文件**: `core/workflow.py`, `core/registry.py`, `core/plugin_manager.py`
- **说明**: 拓扑排序(Kahn算法)、并行执行(ThreadPoolExecutor)、节点注册表、插件发现(importlib)、序列化(to_dict/from_dict)

#### P0-4 数据包与事件系统
- **C# 源**: `H.VisionMaster.DiagramData` (FlowableDiagramData, VisionDiagramDataBase)
- **功能**: 节点间数据传输
  - DataPacket 数据包定义 (图像Mat/数值/字符串/对象)
  - 事件发布/订阅
  - 节点输入/输出端口数据绑定
  - Flowable 流程控制(OK/Error/Break)
- **Python 实现**: `core/data_packet.py`, `core/events.py`
- **依赖**: P0-3
- **状态**: ✅ 已完成 (2026-06-04)
- **Python 文件**: `core/data_packet.py`, `core/events.py`
- **说明**: DataPacket数据包(图像+元数据)、FlowableResult流程控制(OK/Error/Break)、EventSystem发布订阅(14种事件类型)

#### P0-5 节点组系统 (NodeGroup) ★
- **C# 源**: `Source/VisionMaster/H.VisionMaster.NodeGroup/Groups/` (全部 10 个文件)
- **功能**: 工具箱节点分组
  - 图像数据源组 (SrcImageDataGroup) order=10000
  - 图像预处理组 (PreprocessingDataGroup) order=10100
  - 滤波模块组 (BlurDataGroup) order=10200
  - 图像分割提取组 (TakeoffDataGroup) order=10300
  - 形态学模块组 (MorphologyDataGroup) order=10400
  - 逻辑模块组 (ConditionDataGroup) order=10500
  - 模板匹配组 (TemplateMatchingDataGroup) order=10600
  - 对象识别组 (DetectorDataGroup) order=10700
  - 结果输出组 (OutputDataGroup) order=10900
  - 其他模块组 (OtherDataGroup) order=10900
- **Python 实现**: `core/node_group.py`, 各组的 marker interface 改为装饰器
- **依赖**: P0-2
- **状态**: ✅ 已完成 (2026-06-04)
- **Python 文件**: `core/node_group.py`
- **说明**: 15个标准节点组(图像数据源/预处理/滤波/分割/形态学/逻辑/模板匹配/检测/网络/输出等)，NodeDataGroupBase管理分组，支持自动发现

#### P0-6 DI/IoC 容器最小实现
- **C# 源**: `H.Iocable`, `Microsoft.Extensions.DependencyInjection`
- **功能**: 服务注册与解析，单例/瞬态生命周期
- **Python 实现**: 简单的 ServiceCollection/ServiceProvider 替代 (~100行)
- **依赖**: 无
- **状态**: ✅ 已完成 (2026-06-04)
- **Python 文件**: `core/ioc.py`
- **说明**: ServiceCollection/ServiceProvider，支持单例/瞬态/工厂，构造函数自动注入

---

### P1 — 主界面框架 ✅ 已完成 (2026-06-04)

#### P1-1 主窗口布局
- **C# 源**: `MainWindow.xaml`, `H.Windows.Main`
- **功能**: 菜单栏(文件/编辑/运行/系统/帮助)、工具栏(项目/流程/缩放)、状态栏(状态/消息/计数)、主题支持
- **Python 实现**: `gui/main_window.py` (250+ 行), `gui/theme.py` (250+ 行)
- **状态**: ✅ 已完成

#### P1-2 可停靠面板系统
- **C# 源**: `H.Controls.GridSplitterBox`, `H.Controls.Dock`
- **功能**: QSplitter 三栏布局 (左280/中拉伸/右300)，QTabWidget 多标签页
- **Python 实现**: `gui/main_window.py` (QSplitter + QTabWidget)
- **状态**: ✅ 已完成

#### P1-3 工具箱面板
- **C# 源**: `H.Controls.FavoriteBox`, `H.Controls.TreeListView`
- **功能**: QTreeWidget 分组显示节点，搜索过滤，双击创建节点
- **Python 实现**: `gui/toolbox_panel.py` (150+ 行)
- **状态**: ✅ 已完成

#### P1-4 属性面板
- **C# 源**: `H.Controls.Form.PropertyItem`, `H.Controls.PropertyGrid`
- **功能**: 动态表单生成(bool→CheckBox/int→SpinBox/float→DoubleSpinBox/string→LineEdit/file→LineEdit+Browse/enum→ComboBox/list→Label)
- **Python 实现**: `gui/property_panel.py` (250+ 行)
- **状态**: ✅ 已完成

#### P1-5 日志面板
- **C# 源**: `H.Modules.Messages.Notice`, `H.Services.Message`
- **功能**: 带颜色的日志消息(Info/Success/Warn/Error/Fatal)，过滤按钮，自动连接事件系统
- **Python 实现**: `gui/log_panel.py` (170+ 行)
- **状态**: ✅ 已完成

#### P1-6 图像查看器 (ZoomBox)
- **C# 源**: `H.Controls.ZoomBox`, `H.Controls.ZoomBox.Extension`
- **功能**: QGraphicsView 实现缩放平移，numpy→QImage转换，ROI/检测框/圆形/直线叠加层，像素坐标显示
- **Python 实现**: `gui/image_viewer.py` (300+ 行)
- **状态**: ✅ 已完成

#### P1-7 结果面板
- **C# 源**: `H.VisionMaster.ResultPresenter`
- **功能**: QTableWidget 显示结果(参数/值)，历史结果标签页，帮助标签页
- **Python 实现**: `gui/result_panel.py` (150+ 行)
- **状态**: ✅ 已完成

---

### P2 — 节点编辑器 ★★★ ✅ 已完成 (2026-06-04)

#### P2-1 画布场景
- **功能**: QGraphicsScene 无限画布、网格背景(小/大)、节点/连线管理、选择/删除/拖拽连线、上下文菜单
- **Python 实现**: `gui/node_editor/scene.py` (260+ 行)
- **状态**: ✅ 已完成

#### P2-2 节点项 (NodeItem)
- **功能**: 圆角矩形 + 左色条(分组颜色) + 标题文字 + 4端口(上/下/左/右) + 选中高亮 + 状态指示点
- **Python 实现**: `gui/node_editor/node_item.py` (220+ 行)
- **状态**: ✅ 已完成

#### P2-3 端口项 (SocketItem)
- **功能**: 4px圆形端口、悬停变大变橙、拖拽创建连线、输入/输出颜色区分
- **Python 实现**: `gui/node_editor/socket_item.py` (100+ 行)
- **状态**: ✅ 已完成

#### P2-4 连线项 (EdgeItem)
- **功能**: 橙色贝塞尔曲线、端口方向自动路由、拖拽中临时线、悬停加宽、选中高亮
- **Python 实现**: `gui/node_editor/edge_item.py` (180+ 行)
- **状态**: ✅ 已完成

#### P2-5 编辑器控件 (EditorWidget)
- **功能**: QGraphicsView 容器、Ctrl+滚轮缩放、中键平移、右键菜单、Delete删除、Ctrl+A全选、拖放创建节点、工具栏(运行/停止/缩放/网格)
- **Python 实现**: `gui/node_editor/editor_widget.py` (270+ 行)
- **状态**: ✅ 已完成

**P2 验证**: 所有5个模块导入通过。DiagramEditorWidget已集成到MainWindow中心区域(流程编辑标签页)。节点选择→属性面板联动。工具箱双击→画布添加节点。

---

### P3 — 视觉处理节点实现

#### P3-1 图像源节点 (Src Images) — 数据源
- **C# 源**: `H.VisionMaster.OpenCV/NodeDatas/1 - Src/`
  - `SrcImageFilesNodeData.cs` — 图像文件列表读取
  - `SrcVideoFilesNodeData.cs` — 视频文件读取
  - `CameraCaptureNodeData.cs` — 摄像头采集
- **C# 源**: `Source/NodeDatas/H.NodeDatas.Zoo/` — 系统自带测试图像集
  - Bitholder, Board, Cardoor, Halcon, OpenCV, Persons, Pillbag, PillMagnesium, PipeJoints, RadiusGauges
- **Python 实现**: `nodes/sources/` 目录
  - `image_file_source.py` — cv2.imread 文件列表
  - `video_file_source.py` — cv2.VideoCapture 视频
  - `camera_source.py` — cv2.VideoCapture 摄像头
  - `zoo_sources.py` — 测试图像集
- **依赖**: P0-2, P0-5
- **状态**: ⬜ 未开始

#### P3-2 图像预处理节点 (Preprocessings) — 预处理
- **C# 源**: `H.VisionMaster.OpenCV/NodeDatas/2 - Preprocessings/`
  - `CvtColor.cs` — 色彩空间转换
  - `Resize.cs` — 图像缩放
  - `Rotate.cs` — 旋转
  - `Flip.cs` — 翻转
  - `Threshold.cs` — 阈值化
  - `Normalize.cs` — 归一化
  - `BitwiseNot.cs` — 按位取反
  - `AddSutract.cs` — 加减运算
  - `MultiplayDivide.cs` — 乘除运算
  - `Pow.cs` — 幂运算
  - `Repeat.cs` — 像素复制
  - `SplitBGR.cs` — BGR通道分离
- **Python 实现**: `nodes/preprocessings/` 目录
- **依赖**: P0-2, P0-5
- **状态**: ⬜ 未开始

#### P3-3 滤波模糊节点 (Blurs) — 滤波
- **C# 源**: `H.VisionMaster.OpenCV/NodeDatas/3 - Blurs/`
  - `GaussianBlur.cs` — 高斯模糊
  - `Blur.cs` — 均值模糊
  - `DetailEnhance.cs` — 细节增强
  - `EdgePreservingFilter.cs` — 边缘保留滤波
  - `PencilSketch.cs` — 铅笔素描
  - `Stylization.cs` — 风格化
- **Python 实现**: `nodes/blurs/` 目录
- **依赖**: P0-2, P0-5
- **状态**: ⬜ 未开始

#### P3-4 图像分割节点 (Takeoffs) — 分割提取
- **C# 源**: `H.VisionMaster.OpenCV/NodeDatas/3 - Takeoffs/`
  - `HSVInRange.cs` — HSV色彩范围提取
  - `BitwiseAnd.cs` — 按位与掩膜
  - `SeamlessCloneBackground.cs` — 无缝融合背景替换
- **Python 实现**: `nodes/takeoffs/` 目录
- **依赖**: P0-2, P0-5
- **状态**: ⬜ 未开始

#### P3-5 形态学节点 (Morphology) — 形态学
- **C# 源**: `H.VisionMaster.OpenCV/NodeDatas/4 - Morphology/`
  - `Dilate.cs` — 膨胀
  - `Erode.cs` — 腐蚀
  - `Open.cs` — 开运算
  - `Close.cs` — 闭运算
  - `Gradient.cs` — 形态学梯度
  - `TopHat.cs` — 顶帽
  - `BlackHat.cs` — 黑帽
- **Python 实现**: `nodes/morphology/` 目录
- **依赖**: P0-2, P0-5
- **状态**: ⬜ 未开始

#### P3-6 条件/逻辑节点 (Conditions) — 逻辑
- **C# 源**: `H.VisionMaster.OpenCV/NodeDatas/5 - Conditions/`
  - `OpenCVConditionNodeData.cs` — 通用条件分支
  - `PixelThresholdIfConditionNodeData.cs` — 像素阈值条件
- **C# 源**: `H.VisionMaster.NodeData/Base/Conditions/`
  - `WaitAllParallelNodeData.cs` — 并行等待
  - `VisionPropertyConditionsPrensenter.cs` — 条件编辑器
- **Python 实现**: `nodes/conditions/` 目录
- **依赖**: P0-2, P0-5
- **状态**: ⬜ 未开始

#### P3-7 模板匹配节点 (Template Matching) — 模板匹配
- **C# 源**: `H.VisionMaster.OpenCV/NodeDatas/6 - TemplateMatchings/`
  - `TemplateBase64MatchingNodeData.cs` — 基础模板匹配
  - `BestMatchBase64TemplateMatchingNodeData.cs` — 最佳匹配
  - `SiftBase64FeatureMatchingNodeData.cs` — SIFT特征匹配
  - `SurfBase64FeatureMatchingNodeData.cs` — SURF特征匹配
  - `HSVInRangeRenderBlobMatchingNodeData.cs` — HSV+Blob匹配
  - `MatcherType.cs` — 匹配器类型枚举
- **Python 实现**: `nodes/template_matchings/` 目录
- **依赖**: P0-2, P0-5
- **状态**: ⬜ 未开始

#### P3-8 检测节点 (Detector) — 检测
- **C# 源**: `H.VisionMaster.OpenCV/NodeDatas/7 - Detector/`
  - `Canny.cs` — Canny边缘检测
  - `FindContours.cs` — 轮廓查找
  - `HoughLines.cs` / `HoughLinesP.cs` — 霍夫线检测
  - `RenderBlobs.cs` — Blob渲染
  - `BlobDetector.cs` — Blob检测器
  - `QRCode.cs` — 二维码识别
- **Python 实现**: `nodes/detectors/` 目录
- **依赖**: P0-2, P0-5
- **状态**: ⬜ 未开始

#### P3-9 特征提取节点 (Feature) — 特征提取
- **C# 源**: `H.VisionMaster.OpenCV/NodeDatas/8 - Feature/`
  - `AKazeFeatureDetector.cs` — AKAZE
  - `BriskFeatureDetector.cs` — BRISK
  - `FastFeatureDetector.cs` — FAST
  - `FreakFeatureDetector.cs` — FREAK
  - `KazeFeatureDetector.cs` — KAZE
  - `MserFeatureDetector.cs` — MSER
  - `StarFeatureDetector.cs` — StarDetector
  - `HomographyTransform.cs` — 单应性变换
- **Python 实现**: `nodes/features/` 目录
- **依赖**: P0-2, P0-5
- **状态**: ⬜ 未开始

#### P3-10 其他视觉节点 (Other) — 其他CV
- **C# 源**: `H.VisionMaster.OpenCV/NodeDatas/9 - Other/`
  - `HaarCascade.cs` — Haar级联分类器
  - `LbpCascade.cs` — LBP级联分类器
  - `Hist.cs` — 直方图计算
  - `Hog.cs` — HOG描述子
  - `SeamlessClone.cs` — 无缝融合
  - `Stitching.cs` — 图像拼接
  - `Subdiv2D.cs` — 2D细分
  - `SVM.cs` — SVM分类器
  - `WarpAffineTransform.cs` — 仿射变换
  - `WarpPerspectiveTransform.cs` — 透视变换
  - `DnnSuperres.cs` — DNN超分辨率
  - `Yolov3.cs` — YOLOv3检测器
- **Python 实现**: `nodes/others/` 目录
- **依赖**: P0-2, P0-5
- **状态**: ⬜ 未开始

#### P3-11 视频节点 (Video)
- **C# 源**: `H.VisionMaster.OpenCV/NodeDatas/Video/`
  - `MOG.cs` — 背景减除(MOG/MOG2)
  - `VideoWriter.cs` — 视频写入
- **Python 实现**: `nodes/video/` 目录
- **依赖**: P0-2, P0-5
- **状态**: ⬜ 未开始

#### P3-12 输出节点 (Outputs) — 结果输出
- **C# 源**: `H.VisionMaster.OpenCV/NodeDatas/9 - Outputs/`
  - `OKOutputNodeData.cs` — OK输出
  - `NGOutputNodeData.cs` — NG输出
  - `ShowInfoNotifyMessageOutputNodeData.cs` — 信息提示
  - `ShowSuccessNotifyMessageOutputNodeData.cs` — 成功提示
  - `ShowWarnNotifyMessageOutputNodeData.cs` — 警告提示
  - `ShowErrorNotifyMessageOutputNodeData.cs` — 错误提示
  - `ShowFatalNotifyMessageOutputNodeData.cs` — 严重提示
  - `ShowDialogNotifyMessageOutputNodeData.cs` — 弹窗提示
- **Python 实现**: `nodes/outputs/` 目录
- **依赖**: P0-2, P0-5
- **状态**: ⬜ 未开始

#### P3-13 ONNX深度学习节点 — DNN
- **C# 源**: `Source/NodeDatas/H.NodeDatas.Onnx.OpenCV/` (全部文件)
  - 分类: `ClsOnnxNodeData.cs` (基于 ClsOnnxNodeDataBase)
  - 目标检测: `ObjDetectOnnxNodeData.cs` (基于 ObjDetectOnnxNodeDataBase, YOLOv5)
  - 语义分割: `SemSegOnnxNodeData.cs` (基于 SemSegOnnxNodeDataBase)
  - 数值推理: `InferOnnxNodeData.cs` (基于 InferOnnxNodeDataBase)
  - 工具类: `OnnxExtension.cs` (blob处理、NMS、检测框绘制等)
- **C# 源**: `Source/Apps/H.App.VisionMaster.OpenCV/NodeDatas/`
  - `Yolov5OnnxNodeData.cs` — YOLOv5检测
  - `Yolov5FaceOnnxNodeData.cs` — YOLOv5人脸检测
  - `AgeInferOnnxNodeData.cs` — 年龄推理
  - `GenderClsOnnxNodeData.cs` — 性别分类
  - `HumanSemSegOnnxNodeData.cs` — 人像分割
- **Python 实现**: `nodes/onnx/` 目录
- **依赖**: P0-2, P0-5, ONNX模型文件
- **状态**: ⬜ 未开始

#### P3-14 网络通讯节点 (Modbus) — 通讯
- **C# 源**: `Source/VisionMaster/H.VisionMaster.Network/` (全部文件)
  - `ModbusNodeDataBase.cs` — Modbus连接基类
  - `IntReadableModbusNodeData.cs` — 读保持寄存器(int)
  - `ShortWriteableModbusNodeData.cs` — 写单个寄存器(ushort)
- **Python 实现**: `nodes/network/` 目录 (使用 pymodbus)
- **依赖**: P0-2, P0-5, pymodbus
- **状态**: ⬜ 未开始

---

### P4 — 项目系统与持久化

#### P4-1 项目保存/加载
- **C# 源**: `Source/VisionMaster/H.VisionMaster.Project/`, `Source/Apps/.../Projects/`
  - `VisionProjectItem.cs` — 项目项
  - `VisionProjectService.cs` — 项目服务 (Newtonsoft.Json 序列化)
  - `IVisionProjectItem.cs` / `VisionProjectItemBase.cs` — 项目接口
- **功能**: 整个工作流图序列化为JSON，保存/加载项目文件(.json)
- **Python 实现**: `core/project.py` (json 序列化/反序列化)
- **依赖**: P0-3, P0-4
- **状态**: ✅ 已完成 (2026-06-04)
- **Python 文件**: `core/project.py`
- **说明**: ProjectItem/ProjectService完整实现，JSON序列化/反序列化，最近项目列表，工作流保存/加载往返验证通过

#### P4-2 示例项目
- **C# 源**: `Assets/DefaultProjects/` (31个JSON示例项目)
- **功能**: 预置示例项目模板
  - HSV二值分割, ROI区域绘制, 模板匹配, 色相匹配
  - YOLOv5检测/人脸, 语义分割, 性别分类, 年龄推测
  - Modbus通讯, 多图像源, 并行运行, 条件分支
  - 形态学模块, 滤波模糊, 特征提取, 特征识别
  - 二维码识别, 替换背景, 无缝融合, 输出消息等
- **Python 实现**: 移植JSON示例到Python项目格式，放入 `assets/projects/`
- **依赖**: P4-1
- **状态**: ⬜ 未开始

#### P4-3 最近项目列表
- **C# 源**: `H.Modules.Project`, `H.Services.Project`
- **功能**: 启动页显示最近打开的项目，快速打开
- **Python 实现**: QSettings 存储最近项目路径
- **依赖**: P4-1
- **状态**: ⬜ 未开始

---

### P5 — 高级UI组件

#### P5-1 ROI编辑器
- **C# 源**: `H.Controls.ROIBox`, `H.VisionMaster.NodeData/ROIPresenters/`
  - `DrawROI.cs` — 交互式绘制ROI (矩形/旋转矩形/圆形)
  - `FromROI.cs` — 从上游获取ROI
  - `InputROI.cs` — 手动输入ROI参数
  - `ROIBase.cs`, `IROI.cs` — ROI基类
- **Python 实现**: `gui/roi_editor.py` (QGraphicsItem 子类)
- **依赖**: P1-6, P0-2
- **状态**: ⬜ 未开始

#### P5-2 颜色选择器
- **C# 源**: `H.Controls.ColorPicker`, `H.Controls.ColorBox`
- **功能**: HSV/RGB颜色拾取，从图像取色
- **Python 实现**: `gui/color_picker.py` (QColorDialog + 自定义)
- **依赖**: 无
- **状态**: ⬜ 未开始

#### P5-3 图像颜色拾取器
- **C# 源**: `H.Controls.ImageColorPicker`, `ImageColorPickerPresenter`
- **功能**: 在图像上点击获取像素颜色值
- **Python 实现**: 集成到 image_viewer.py
- **依赖**: P1-6
- **状态**: ⬜ 未开始

#### P5-4 模板裁剪器
- **C# 源**: `Base64MatchingNodeData.cs` 中的 `CropImagePresenter`
- **功能**: 在图像上框选区域作为匹配模板
- **Python 实现**: `gui/crop_dialog.py`
- **依赖**: P1-6
- **状态**: ⬜ 未开始

#### P5-5 条件编辑器
- **C# 源**: `VisionPropertyConditionsPrensenter.xaml(.cs)`
- **功能**: UI配置条件规则 (属性名/操作符/值)，添加/删除条件
- **Python 实现**: `gui/condition_editor.py`
- **依赖**: P3-8
- **状态**: ⬜ 未开始

#### P5-6 过滤器框
- **C# 源**: `H.Controls.FilterBox`
- **功能**: 数据表格过滤UI
- **Python 实现**: 集成到 result_panel.py
- **依赖**: P1-11
- **状态**: ⬜ 未开始

#### P5-7 帮助面板
- **C# 源**: `HelpNodeDataBase`, `IHelpPresenter`
- **功能**: 选中节点时显示帮助文档/参数说明
- **Python 实现**: `gui/help_panel.py`
- **依赖**: 无
- **状态**: ⬜ 未开始

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

Phase 4 (P3): 视觉节点
  P3-1 → P3-2 → P3-5 → P3-4 → P3-3 → P3-8 → P3-7 → P3-6 → P3-9 → P3-10 → P3-12 → P3-11 → P3-14 → P3-13
  预计: 完整视觉处理流水线

Phase 5 (P4): 项目系统
  P4-1 → P4-3 → P4-2
  预计: 可保存/加载/分享项目

Phase 6 (P5): 高级UI
  P5-1 → P5-3 → P5-2 → P5-4 → P5-5 → P5-6 → P5-7
  预计: 完善用户体验
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
7. **不要移植 WPF-Control 的95个项目！** 只需理解它们的功能，用 PyQt 实现对应的UI组件即可。

---

*最后更新: 2026-06-04*
*当前阶段: Phase 1-3 (P0+P1+P2) 完成，准备开始 Phase 4 (P3 视觉处理节点)*

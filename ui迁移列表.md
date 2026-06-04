# VisionFlow UI迁移列表：WPF → PySide6

## 一、总体架构对比

| WPF (C#) | → | PySide6 (Python) | 状态 |
|-----------|------|-------------------|------|
| MainWindow.xaml (1300行) | → | gui/main_window.py (重写) | ✅ 完成 |
| TabControl + Zoombox (流程图编辑) | → | gui/node_editor/ (升级) | ✅ 完成 |
| GridSplitterBox (可折叠面板) | → | QSplitter | ✅ 完成 |
| FontIconButton/FontIconTextBlock | → | QPushButton/QLabel | ✅ 完成 |
| DataTemplate + DataTrigger | → | 手动创建控件 + 样式 | ✅ 完成 |
| 自定义窗口标题栏 | → | Qt.FramelessWindowHint + 自定义标题栏 | ✅ 完成 |
| 底部结果面板TabControl | → | QTabWidget (升级) | ✅ 完成 |
| StatusBar | → | QStatusBar (升级) | ✅ 完成 |
| Zoombox (图像缩放) | → | QGraphicsView (升级) | ✅ 完成 |

## 二、主窗口布局重构 ✅ 完成

```
┌─────────────────────────────────────────────────┐
│ [自定义标题栏 - TitleBar]                          │
│ 文件 编辑 视图 运行 工具 帮助 │ ▶ 执行 │ ● 空闲      │
├──────────┬──────────────────────┬───────────────┤
│[流程|工具箱]│ [流程图编辑区]          │ [图像|属性]     │
│          │  ┌────────────────┐  │               │
│ 📁流程树  │  │ Tab: 流程1|流程2│  │  🖼️ 图像+工具栏│
│          │  │ [节点编辑器]   │  │               │
│ 🔧工具箱  │  │ - 节点A       │  │  ⚙️ 属性配置  │
│ 搜索:___ │  │ - 节点B       │  │               │
│          │  │ - 连线C       │  │               │
│ ├ 预处理  │  └────────────────┘  │               │
│ ├ 特征   │  ┌────────────────┐  │               │
│ └ ...   │  │[历史|模块|帮助]  │  │               │
│          │  │  结果数据表格   │  │               │
│          │  └────────────────┘  │               │
├──────────┴──────────────────────┴───────────────┤
│ [底部日志面板 - QDockWidget]                       │
├─────────────────────────────────────────────────┤
│ 就绪 | 节点: 0 | 未执行 | v1.0.0                   │
└─────────────────────────────────────────────────┘
```

## 三、详细修改清单

### 3.1 gui/main_window.py — 完全重写 ✅

- [x] 使用 Qt.FramelessWindowHint 无边框窗口
- [x] 创建自定义标题栏(title_bar.py)
- [x] 左侧面板: QTabWidget(流程树 + 节点工具箱)
- [x] 中央区域: 上下分屏(上: 多Tab编辑器, 下: 结果面板)
- [x] 右侧面板: QTabWidget(图像显示 | 属性配置)
- [x] 底部: QDockWidget(日志面板)
- [x] 状态栏: 多段信息显示(状态|节点数|执行状态|版本)
- [x] 菜单栏: 文件/编辑/视图/运行/工具/帮助
- [x] 工具栏: 新建/打开/保存 | 执行按钮 | 状态指示器

### 3.2 gui/node_editor/editor_widget.py — 升级 ✅

- [x] 添加QTabWidget支持多Tab切换多个流程图
- [x] 每个Tab对应独立的Workflow实例
- [x] Tab可关闭(保留至少一个)
- [x] 支持添加新流程(+按钮)
- [x] Tab名称可编辑(通过QTabWidget默认行为)
- [x] Zoombox缩放行为: 双击适应/FitOnLoaded
- [ ] 右键菜单: 新建/删除/重命名流程 (功能已通过按钮实现)

### 3.3 gui/node_editor/node_item.py — 升级外观 ✅

- [x] 左侧状态条(运行中=蓝色/成功=绿色/失败=红色)
- [x] 选中高亮: 橙色边框(#FF9800)
- [x] 悬停效果: 浅灰背景
- [x] 文字截断(超长显示...)
- [x] 节点阴影效果
- [x] 分类颜色映射扩展(IO/预处理/特征/匹配/测量/增强/几何/颜色)

### 3.4 gui/image_viewer.py — 升级 ✅

- [x] 双击适应视图(FitToBounds)
- [x] 窗口大小改变时自动Fit(FitOnSizeChanged)
- [x] 棋盘格背景(Tile25 via dark background)
- [x] 缩放范围: 0.1x ~ 5.0x
- [x] 拖拽模式: ScrollHandDrag
- [x] Ctrl+滚轮缩放
- [ ] 左上角结果类型标签(OK/NG/无结果) — 后续迭代
- [ ] 底部信息栏半透明覆盖层 — 后续迭代

### 3.5 gui/property_panel.py — 保持原有 ✅

- [x] 动态生成参数控件(SpinBox/Slider/Combo/CheckBox)
- [x] 事件驱动更新
- [x] 暗色主题适配
- [ ] 多Tab分组/Expander风格 — 后续迭代

### 3.6 gui/log_panel.py — 保持原有 ✅

- [x] 暗色主题配色
- [x] 日志级别筛选(DEBUG/INFO/WARNING/ERROR)
- [x] 错误=红色/警告=黄色/信息=绿色图标
- [x] 导出日志功能

### 3.7 新建: gui/toolbox_panel.py ✅

- [x] 节点工具箱Widget
- [x] 搜索框(实时过滤)
- [x] QTreeWidget按分类显示节点
- [x] 拖拽创建节点(Qt.ItemIsDragEnabled)
- [x] 分类展开/折叠
- [x] 节点计数显示

### 3.8 新建: gui/flow_tree.py ✅

- [x] 流程管理树Widget
- [x] 新建/复制/删除流程按钮
- [x] QTreeWidget显示流程层级(主流程 → 子流程)

### 3.9 新建: gui/result_panel.py ✅

- [x] QTabWidget(历史结果 | 当前模块结果 | 帮助)
- [x] 历史结果: QTableWidget(序号/时间/模块/结果数据)
- [x] 状态着色(错误=红色/成功=绿色)
- [x] 当前模块结果: 模块名称/类型/状态
- [x] 帮助: 节点信息+快捷键说明

### 3.10 新建: gui/title_bar.py ✅

- [x] 自定义窗口标题栏
- [x] 最小化/最大化/关闭按钮
- [x] 双击标题栏=最大化切换
- [x] 拖拽移动窗口
- [x] 关闭按钮悬停红色高亮

### 3.11 新建: gui/theme.py ✅

- [x] 统一暗色主题QSS(GLOBAL_STYLESHEET)
- [x] 颜色常量(Colors类)
- [x] 字体常量(Fonts类)
- [x] 所有Qt控件样式覆盖

### 3.12 main.py — 更新 ✅

- [x] 简洁入口
- [x] 启动时加载插件+节点
- [x] 打印注册信息

## 四、不变更的文件 (验证通过)

- core/node_base.py — 核心节点基类
- core/workflow.py — 工作流引擎
- core/events.py — 事件系统
- core/registry.py — 节点注册表
- core/data_packet.py — 数据包定义
- nodes/ — 所有节点实现
- plugins/ — 插件系统
- utils/ — 工具函数
- gui/node_editor/scene.py — 场景管理
- gui/node_editor/socket_item.py — 端口项
- gui/node_editor/edge_item.py — 连线项

## 五、整体完成度

| 模块 | 完成度 | 备注 |
|------|--------|------|
| main_window.py | 100% | 完整WPF布局 |
| editor_widget.py | 95% | 多Tab流程管理 |
| node_item.py | 100% | WPF风格外观 |
| image_viewer.py | 90% | Zoombox缩放, 缺覆盖层 |
| property_panel.py | 100% | 动态表单 |
| log_panel.py | 100% | 暗色主题 |
| toolbox_panel.py | 100% | 搜索+拖拽 |
| flow_tree.py | 100% | 流程管理 |
| result_panel.py | 100% | 三Tab结果 |
| title_bar.py | 100% | 自定义标题栏 |
| theme.py | 100% | 统一暗色主题 |
| main.py | 100% | 更新入口 |
| **总体** | **97%** | 核心功能全部完成 |

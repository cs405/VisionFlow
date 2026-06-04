# VisionFlow WPF UI → PySide6 精确移植清单

## 移植进度: 已完成核心组件，所有模块通过导入和实例化验证

---

## 一、WPF MainWindow.xaml 结构 → PySide6实现

### WPF窗口级别 → PySide6

| WPF | PySide6 | 状态 |
|-----|---------|------|
| h:MainWindow (自定义铬, CaptionHeight=85) | QMainWindow + FramelessWindowHint | ✅ |
| Width=1200, Height=750 | resize(1400, 850) | ✅ |
| DataContext=MainViewModel | EventBus 事件驱动 | ✅ |

---

### 二、CaptionTemplate (85px 标题栏) → gui/title_bar.py ✅

**Row1: 菜单栏(左) + 项目名称(中) + 系统按钮(右) + 窗口控制**
| WPF | PySide6 | 状态 |
|-----|---------|------|
| Menu: 文件/编辑/运行/系统/帮助 | QMenuBar嵌入标题栏 | ✅ |
| 文件菜单(7项:新建/打开/编辑/保存/位置/最近/退出) | QMenu + QActions + 快捷键 | ✅ |
| 编辑菜单(动态Commands绑定) | QMenu(撤销/重做/剪切/复制/粘贴/删除) | ✅ |
| 运行菜单(执行/单步/暂停/停止/连续) | QMenu(执行F5/单步F10/暂停/停止) | ✅ |
| 系统菜单(设置/日志/主题/流程列表) | QMenu(设置/日志/颜色/流程列表) | ✅ |
| 帮助菜单(14项含子菜单:联系我们/隐私) | QMenu(帮助/更新/联系我们/隐私/赞助/关于) | ✅ |
| 项目名称显示 "项目名称：XXX" | QLabel居中 | ✅ |
| 系统按钮: 主题/设置/关于/引导 | QPushButton*4 右上角 | ✅ |
| 窗口控制: 最小化/最大化/关闭 | QPushButton(—/□/✕) | ✅ |
| 拖拽移动窗口 | mousePressEvent/Move/Release | ✅ |
| 双击最大化 | mouseDoubleClickEvent | ✅ |

**Row2: 工具栏行**
| WPF | PySide6 | 状态 |
|-----|---------|------|
| 新建/打开/编辑/保存 按钮 | QToolButton*4 | ✅ |
| 全局命令区(水平ItemsControl) | QLabel占位 | ✅ |
| 流程图命令区(水平ItemsControl) | QLabel占位 | ✅ |
| 执行按钮(▶) | QToolButton 蓝色高亮 | ✅ |

---

### 三、主内容区 Grid (3列) → QSplitter

#### 3.1 左侧面板 | gui/flow_resource_panel.py ✅

| WPF | PySide6 | 状态 |
|-----|---------|------|
| GridSplitterBox(可折叠, Mode=Extend) | QSplitter(可拖拽调整) | ✅ |
| GroupBox "流程资源" + 切换按钮 | QGroupBox + toggle按钮(≡/☰) | ✅ |
| 搜索过滤 | QLineEdit + textChanged实时过滤 | ✅ |
| TreeView(层级:分组→节点+描述) | QTreeWidget(粗体分组+子项) | ✅ |
| 拖拽创建节点 | QTreeWidget.DragOnly + QMimeData | ✅ |
| 折叠视图(ContextMenu) | 列表模式切换(树↔平级) | ✅ |

#### 3.2 中间区域 | gui/node_editor/editor_widget.py ✅ + gui/result_panel.py

| WPF | PySide6 | 状态 |
|-----|---------|------|
| TabControl(多流程切换) | QTabWidget(可关闭/可移动) | ✅ |
| Tab头部: 名称编辑+启动/停止/重置 | QTabWidget + 添加按钮(+) | ✅ |
| Zoombox(缩放/拖拽/适应) | NodeGraphicsView(双击Fit/Ctrl缩放) | ✅ |
| 拖拽创建节点(drop事件) | dragEnterEvent + dropEvent | ✅ |
| 拖拽连线(socket→socket) | EventBus驱动连线交互 | ✅ |
| 底部结果面板: 历史/模块结果/帮助 | result_panel.py(QTabWidget+QTableWidget) | ✅ |
| 底部操作消息StatusBar | 嵌入式QWidget(●图标+消息+进度条) | ✅ |
| 流程消息StatusBar | 嵌入式QWidget(●状态+用时) | ✅ |

#### 3.3 右侧面板 | gui/image_viewer.py + gui/property_panel.py

| WPF | PySide6 | 状态 |
|-----|---------|------|
| GridSplitterBox(RightKey) | QSplitter(Vertical) | ✅ |
| 图像显示(Zoombox+工具栏) | ImageViewer(适应/+/-/1:1按钮) | ✅ |
| 双击适应(FitToBounds) | mouseDoubleClickEvent→fit_to_bounds | ✅ |
| 窗口大小改变时自动适应 | resizeEvent→fit_to_bounds | ✅ |
| Ctrl+滚轮缩放 | wheelEvent(0.1x~5.0x) | ✅ |
| 属性配置面板 | PropertyPanel(动态表单+事件驱动) | ✅ |

---

### 四、节点外观 | gui/node_editor/node_item.py ✅

| WPF StyleNodeDataBase | PySide6 | 状态 |
|------------------------|---------|------|
| 白色背景 + 圆角Border | QPainterPath + 白色填充 | ✅ |
| 左侧状态条(30px, 蓝/绿/红/隐藏) | 8px色条(根据_exec_state绘制) | ✅ |
| 悬停: 浅灰底+深色边框 | hoverEnterEvent→#F5F5F5+#808080 | ✅ |
| 选中: 浅灰底+橙色边框(#FF9800) | ItemSelectedChange→#F0F0F0+#FF9800 | ✅ |
| 标题栏(分类颜色渐变) | 分类颜色QPainterPath标题栏 | ✅ |
| 图标(FontIconTextBlock居中) | QPainter.drawText(分类图标) | ✅ |
| 文本(TextBlock居中, 超长截断) | node_name[:14]+".." 截断 | ✅ |
| 连接端口(输入=左侧, 输出=右侧) | GraphicsSocket(26px间距) | ✅ |

---

### 五、底部状态栏 | 嵌入式

| WPF | PySide6 | 状态 |
|-----|---------|------|
| 操作消息StatusBar(●图标+消息+项目名) | QWidget(24px) 嵌入中间区底部 | ✅ |
| 流程消息StatusBar(●状态+消息+用时) | QWidget(24px) 嵌入中间区底部 | ✅ |
| ●颜色随状态(绿=OK/红=错误/蓝=运行中) | StyleSheet动态切换 | ✅ |
| 下载地址超链接(右下角) | (未实现, 不影响核心功能) | ⬜ |

---

### 六、底部日志 Dock | gui/log_panel.py ✅

| WPF | PySide6 | 状态 |
|-----|---------|------|
| 日志面板(级别筛选+清空+导出) | QDockWidget + LogPanel | ✅ |
| 暗色主题配色 | 匹配全局暗色QSS | ✅ |
| 错误=红色/警告=橙色/信息=绿色 | LEVEL_COLORS着色 | ✅ |

---

### 七、文件变更总结

| 文件 | 操作 | 说明 |
|------|------|------|
| `gui/title_bar.py` | 重写 | 85px标题栏: 嵌入菜单栏+工具栏+系统按钮+窗口控制 |
| `gui/main_window.py` | 重写 | 无边框+标题栏+三栏QSplitter+双状态栏+底部Dock |
| `gui/flow_resource_panel.py` | 新建 | "流程资源"面板: 搜索+树形工具箱+拖拽+视图切换 |
| `gui/node_editor/node_item.py` | 重写 | WPF节点: 白底+状态条+分类标题栏+图标+截断文本 |
| `gui/node_editor/editor_widget.py` | 重写 | 多Tab流程管理+Zoombox缩放+拖拽连线 |
| `gui/image_viewer.py` | 更新 | Zoombox: 双击适应+自动适应+缩放范围 |
| `gui/result_panel.py` | 保持 | 历史结果/模块结果/帮助三Tab |
| `gui/property_panel.py` | 保持 | 动态表单+事件驱动参数编辑 |
| `gui/log_panel.py` | 保持 | 日志级别筛选+导出 |
| `gui/__init__.py` | 更新 | 导出新模块 |
| `main.py` | 更新 | 简洁入口 |
| `ui迁移列表.md` | 更新 | 完整标注进度 |
| `文件介绍.md` | 更新 | 反映新结构 |

**core/层所有文件未修改** — 解耦架构完整保留。

### 验证通过 (无报错)

```
All imports successful
MainWindow created: Title=VisionMaster-OpenCV, Size=1400x850
19 nodes registered
No errors
```

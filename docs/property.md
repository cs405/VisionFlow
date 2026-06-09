# Property —— 节点属性描述符

`Property` 是 VisionFlow 中用于声明节点可配置属性的描述符类。只需在节点类中定义一个 `Property` 实例，属性面板就会自动生成对应的 UI 控件，无需手写任何 GUI 代码。

## 快速上手

```python
from core.node_base import VisionNodeData, Property, PropertyGroupNames

class MyNode(VisionNodeData):
    # 基本用法：数值类型会根据 default 自动推断控件
    threshold = Property(128, name="阈值", group=PropertyGroupNames.RUN_PARAMETERS)

    # 下拉菜单
    mode = Property("fast", name="模式", editor="choices",
                    choices=["fast", "precise"], group=PropertyGroupNames.RUN_PARAMETERS)

    # 滑块
    brightness = Property(50, name="亮度", editor="slider",
                          min_val=0, max_val=100, group=PropertyGroupNames.RUN_PARAMETERS)
```

---

## 构造函数参数

```python
Property(default, *, name="", group="", description="", readonly=False, order=0,
         editor="", choices=None, min_val=None, max_val=None,
         validator=None, step=0.1, decimals=3)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `default` | `Any` | `None` | 属性初始值，其 Python 类型决定默认编辑器控件 |
| `name` | `str` | `""` | 属性面板中显示的标签 |
| `group` | `str` | `""` | 属性所属分组，决定显示在哪个标签页。建议使用 `PropertyGroupNames` 常量 |
| `description` | `str` | `""` | 鼠标悬停时显示的工具提示 |
| `readonly` | `bool` | `False` | `True` 时 UI 控件禁用，不可编辑 |
| `order` | `int` | `0` | 在同组内的排序，值越小越靠前 |
| `editor` | `str` | `""` | 指定编辑器类型（见下方编辑器列表），为空则根据值的 Python 类型自动推断 |
| `choices` | `list` | `[]` | `editor="choices"` 时的下拉选项列表 |
| `min_val` | `Any` | `None` | 数值属性的最小值（配合 `int`/`float`/`editor="slider"` 使用） |
| `max_val` | `Any` | `None` | 数值属性的最大值 |
| `validator` | `callable` | `None` | 验证函数，签名 `(value) -> (bool, str)`，见下方验证器章节 |
| `step` | `float` | `0.1` | `float` 类型时微调控件的步进值 |
| `decimals` | `int` | `3` | `float` 类型时显示的小数位数 |

---

## 分组常量 `PropertyGroupNames`

```python
class PropertyGroupNames:
    RUN_PARAMETERS = "运行参数"       # 运行时参数（执行次数、延迟、阈值等）
    BASE_PARAMETERS = "基本参数"      # 基础属性（名称、描述等）
    RESULT_PARAMETERS = "结果参数"    # 输出相关（路径、格式等）
    FLOW_PARAMETERS = "流程控制"      # 流程控制（条件分支等）
    DISPLAY_PARAMETERS = "显示参数"   # 显示相关（颜色、透明度等）
    OTHER_PARAMETERS = "其他参数"     # 兜底分组
```

---

## 编辑器类型

### 1. 自动推断（`editor=""`，默认）

不指定 `editor` 时，根据 `default` 的 Python 类型自动选择控件：

| `default` 类型 | 生成的控件 | 生效的额外参数 |
|---------------|-----------|---------------|
| `bool` | `QCheckBox` | `readonly` |
| `int` | `QSpinBox` | `min_val`, `max_val`, `readonly` |
| `float` | `QDoubleSpinBox` | `min_val`, `max_val`, `step`, `decimals`, `readonly` |
| `Enum` | `QComboBox`（自动填充枚举成员） | `readonly` |
| `str`（含 path/file/src/dir/folder） | `QLineEdit` + 浏览按钮 | `readonly` |
| `str`（普通文本） | `QLineEdit` | `readonly` |
| `list` | 只读标签 + 浏览按钮 | `readonly` |

示例：

```python
enable = Property(True, name="启用", group=PropertyGroupNames.RUN_PARAMETERS)
count = Property(3, name="次数", min_val=1, max_val=99, group=PropertyGroupNames.RUN_PARAMETERS)
ratio = Property(0.5, name="比例", min_val=0.0, max_val=1.0, step=0.05, decimals=2)
file_path = Property("", name="保存路径", group=PropertyGroupNames.RESULT_PARAMETERS)
```

### 2. 下拉菜单 `editor="choices"`

渲染为 `QComboBox`，选项来自 `choices` 参数。

```python
operation = Property("Add", name="运算", group=PropertyGroupNames.RUN_PARAMETERS,
                     editor="choices", choices=["Add", "Subtract", "Multiply", "Divide"])

image_source_mode = Property("处理后图片", name="图像源",
                             group=PropertyGroupNames.BASE_PARAMETERS,
                             editor="choices", choices=["处理后图片", "原图"])
```

### 3. 滑块 `editor="slider"`

渲染为 `QSlider` + `QSpinBox` 的组合控件，适合直观调节数值。

```python
brightness = Property(50, name="亮度", editor="slider",
                      min_val=0, max_val=100, group=PropertyGroupNames.DISPLAY_PARAMETERS)
```

> **注意**：滑块内部使用整数微调控件，`step` 和 `decimals` 对滑块无效。

### 4. 颜色选择器 `editor="color"`

渲染为颜色预览标签 + 点击弹出的 `ColorPickerDialog`。值存储为颜色字符串（如 `"#FF0000"`）。

```python
overlay_color = Property("#00FF00", name="叠加颜色", editor="color",
                         group=PropertyGroupNames.DISPLAY_PARAMETERS)
```

### 5. 裁剪编辑器 `editor="crop"`

渲染为按钮，点击打开 `CropDialog` 进行模板图像裁剪。值最终存储为裁剪结果的 `base64_string`。

```python
template = Property("", name="模板", editor="crop",
                    group=PropertyGroupNames.BASE_PARAMETERS)
```

### 6. 多文件选择 `editor="file_collection"`

渲染为 `QListWidget` + "添加文件"／"添加文件夹"／"清空" 按钮，用于管理一组文件路径。

```python
input_files = Property([], name="输入文件", editor="file_collection",
                       group=PropertyGroupNames.BASE_PARAMETERS)
```

### 7. 上游结果图像选择 `editor="image_selector"`

渲染为 `QComboBox`，自动列出当前节点的 `result_images` 作为选项，用于选择从哪个上游节点获取图像。

```python
source_image_key = Property("", name="图像源", editor="image_selector",
                            group=PropertyGroupNames.BASE_PARAMETERS)
```

---

## 验证器 `validator`

验证器是一个函数，签名 `(value) -> (bool, str)`：
- 第一个返回值 `bool`：`True` 表示有效，`False` 表示无效
- 第二个返回值 `str`：错误提示信息（有效时传空字符串）

验证失败时，控件边框变红，鼠标悬停显示错误信息。

```python
def validate_port(value):
    if 0 < value <= 65535:
        return True, ""
    return False, "端口号必须在 1-65535 之间"

port = Property(8080, name="端口", group=PropertyGroupNames.RUN_PARAMETERS,
                validator=validate_port)
```

> **注意**：验证器仅在控件类型为 `QLineEdit`、`QSpinBox`、`QDoubleSpinBox` 时生效。

---

## 描述符协议（内部机制）

`Property` 是 Python 描述符，在类创建时自动完成属性名绑定：

```python
class NodeBase:
    my_prop = Property(0, name="我的属性")

node = NodeBase()
node.my_prop      # -> 返回内部存储的值（不存在则返回 default）
node.my_prop = 5  # -> 写入值，若值变化则触发变更通知
```

### 变更通知链

1. `Property.__set__` 检测到新旧值不同
2. 调用 `node._notify_property_changed(name, old_value, new_value)`
3. `NodeBase._notify_property_changed` 执行：
   - 触发所有通过 `on_property_changed(callback)` 注册的回调
   - 发布全局事件 `EventType.NODE_PROPERTY_CHANGED`，携带 `(node_id, name, old, new)`

> 这意味着修改 Property 值会自动通知 UI 刷新和依赖方响应，无需手动调用任何 update 方法。

---

## 参数生效矩阵

| 参数 | 自动推断 | choices | slider | color | crop | file_collection | image_selector |
|------|---------|---------|--------|-------|------|-----------------|----------------|
| `default` | 初始值 | 初始值 | 初始值 | 初始值 | 初始值 | 初始值 | 初始值 |
| `name` | 标签 | 标签 | 标签 | 标签 | 标签 | 标签 | 标签 |
| `group` | 标签页 | 标签页 | 标签页 | 标签页 | 标签页 | 标签页 | 标签页 |
| `description` | 工具提示 | 工具提示 | 工具提示 | 工具提示 | 工具提示 | 工具提示 | 工具提示 |
| `readonly` | 禁用控件 | 禁用控件 | 禁用控件 | 禁用按钮 | 禁用按钮 | 禁用按钮 | 禁用控件 |
| `order` | 排序 | 排序 | 排序 | 排序 | 排序 | 排序 | 排序 |
| `choices` | - | **填充下拉** | - | - | - | - | - |
| `min_val` | SpinBox 范围 | - | **滑块范围** | - | - | - | - |
| `max_val` | SpinBox 范围 | - | **滑块范围** | - | - | - | - |
| `validator` | 边框+提示 | - | 边框+提示 | - | - | - | - |
| `step` | DoubleSpinBox | - | - | - | - | - | - |
| `decimals` | DoubleSpinBox | - | - | - | - | - | - |

---

## 完整示例

```python
from core.node_base import VisionNodeData, Property, PropertyGroupNames

class ImageFilterNode(VisionNodeData):
    # 基本参数
    node_name = Property("图像滤波", name="名称",
                         group=PropertyGroupNames.BASE_PARAMETERS, order=0)

    # 枚举下拉
    filter_type = Property("Gaussian", name="滤波类型",
                           group=PropertyGroupNames.RUN_PARAMETERS,
                           editor="choices",
                           choices=["Gaussian", "Median", "Bilateral"])

    # 整数范围
    kernel_size = Property(3, name="核大小", min_val=1, max_val=31,
                           group=PropertyGroupNames.RUN_PARAMETERS)

    # 浮点滑块
    sigma = Property(1.0, name="Sigma", editor="slider",
                     min_val=0.1, max_val=10.0, step=0.1, decimals=1,
                     group=PropertyGroupNames.RUN_PARAMETERS)

    # 颜色
    border_color = Property("#000000", name="边框颜色", editor="color",
                            group=PropertyGroupNames.DISPLAY_PARAMETERS)

    # 带验证的端口号
    def _check_port(val):
        return (0 < val <= 65535, "端口必须在 1-65535")

    port = Property(8080, name="端口", group=PropertyGroupNames.RUN_PARAMETERS,
                    validator=_check_port)
```

上述代码无需写一行 UI 代码，属性面板会自动生成完整的编辑界面。

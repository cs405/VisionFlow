"""属性面板
标签页属性编辑器：每个属性组（运行参数、结果参数等）成为一个独立的标签页。
通过 EditorRegistry 提供自定义编辑器。

与节点渲染解耦 — 节点通过 Property 描述符和 get_property_presenter() 暴露属性

功能：
  - 每个分组一个标签页的布局
  - 编辑器注册表：编辑器提示 → 自定义编辑器控件
  - 扩展元数据：选项列表、范围边界、验证器、步进值/小数位数
  - 颜色范围属性的内联 HSV 三通道编辑器
  - 与查看器集成的 ROI 编辑器
  - 条件节点的条件编辑器
"""

import cv2
import os
import numpy as np
from enum import Enum
from typing import Any, Callable

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, QFormLayout,
                              QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
                              QComboBox, QLabel, QPushButton,QHBoxLayout, QColorDialog,
                              QFileDialog, QSlider, QListWidget, QTabWidget, QDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from gui.theme import theme_manager, connect_theme

from core.node_base import (
    Property,
    PropertyGroupNames,
    NodeBase,
    VisionNodeData,
    ROINodeData,
    DrawROI,
    InputROI,
    FromROI,
    NoROI,
    ConditionNodeData,
    VisionPropertyCondition,
    SrcFilesVisionNodeData,
)
from gui.color_picker import ColorPickerDialog
from gui.condition_editor import ConditionEditorDialog
from gui.roi_editor import RoiEditorDialog
from gui.crop_dialog import CropDialog


# ── 编辑器注册表 ───────────────────────────────────────────────────────

class EditorRegistry:
    """由编辑器提示或类型键控的自定义属性编辑器注册表。"""

    def __init__(self):
        """初始化编辑器注册表"""
        # 编辑器字典：键为编辑器提示字符串，值为工厂函数
        self._editors: dict[str, Callable] = {}

    def register(self, editor_hint: str, factory: Callable):
        """注册自定义编辑器工厂

        参数：
            editor_hint: 匹配 Property.editor 字段（例如 "color", "file", "slider"）
            factory: 可调用对象 factory(parent, prop_name, prop_desc, current_value) -> QWidget
        """
        self._editors[editor_hint] = factory

    def get(self, editor_hint: str) -> Callable | None:
        """获取编辑器工厂

        参数：
            editor_hint: 编辑器提示

        返回：
            工厂函数或 None
        """
        return self._editors.get(editor_hint)

    def has(self, editor_hint: str) -> bool:
        """检查编辑器提示是否已注册

        参数：
            editor_hint: 编辑器提示

        返回：
            是否存在
        """
        return editor_hint in self._editors


# 全局编辑器注册表
editor_registry = EditorRegistry()


def register_editor(hint: str):
    """装饰器：将工厂函数注册为自定义编辑器"""
    def decorator(func):
        editor_registry.register(hint, func)
        return func
    return decorator


# ── 内置自定义编辑器 ────────────────────────────────────────────────

@register_editor("slider")
def _create_slider_editor(parent, prop_name, prop_desc, current_value):
    """滑块 + 数值框组合编辑器

    参数：
        parent: 父对象
        prop_name: 属性名称
        prop_desc: 属性描述符
        current_value: 当前值

    返回：
        (容器控件, 值编辑控件) 元组
    """
    # 创建容器控件
    container = QWidget(parent)
    # 创建水平布局
    layout = QHBoxLayout(container)
    # 设置布局边距为0
    layout.setContentsMargins(0, 0, 0, 0)
    # 设置布局间距为4像素
    layout.setSpacing(4)

    # 创建水平滑块
    slider = QSlider(Qt.Horizontal)
    # 创建数值框
    spin = QSpinBox()

    # 获取最小值（如果未指定则使用-999999）
    min_v = prop_desc.min_val if prop_desc.min_val is not None else -999999
    # 获取最大值（如果未指定则使用999999）
    max_v = prop_desc.max_val if prop_desc.max_val is not None else 999999
    # 设置滑块范围
    slider.setRange(int(min_v), int(max_v))
    # 设置数值框范围
    spin.setRange(int(min_v), int(max_v))
    # 设置滑块当前值
    slider.setValue(int(current_value or 0))
    # 设置数值框当前值
    spin.setValue(int(current_value or 0))

    # 滑块值变化时同步更新数值框
    slider.valueChanged.connect(spin.setValue)
    # 数值框值变化时同步更新滑块
    spin.valueChanged.connect(slider.setValue)
    # 添加控件到布局
    layout.addWidget(slider, 1)  # 拉伸因子为1
    layout.addWidget(spin)

    # 如果是只读属性
    if prop_desc.readonly:
        # 禁用滑块
        slider.setEnabled(False)
        # 设置数值框为只读
        spin.setReadOnly(True)

    # 返回容器和滑块（作为值编辑控件）
    return container, slider


@register_editor("choices")
def _create_choices_editor(parent, prop_name, prop_desc, current_value):
    """离散选项的下拉选择器

    参数：
        parent: 父对象
        prop_name: 属性名称
        prop_desc: 属性描述符
        current_value: 当前值

    返回：
        (值编辑控件, 值编辑控件) 元组
    """
    # 创建下拉框
    combo = QComboBox(parent)
    # 获取选项列表
    choices = prop_desc.choices or []
    # 遍历选项列表
    for choice in choices:
        # 添加选项
        combo.addItem(str(choice), choice)

    # 如果当前值是字符串且在选项列表中
    if isinstance(current_value, str) and current_value in [str(c) for c in choices]:
        # 设置当前文本
        combo.setCurrentText(str(current_value))
    # 如果当前值在选项列表中
    elif current_value in choices:
        # 设置当前文本
        combo.setCurrentText(str(current_value))

    # 获取只读状态
    ro = getattr(parent, '_force_readonly', False) or prop_desc.readonly
    # 如果是只读
    if ro:
        # 禁用下拉框
        combo.setEnabled(False)

    # 返回下拉框
    return combo, combo


@register_editor("color")
def _create_color_editor(parent, prop_name, prop_desc, current_value):
    """带预览的颜色选择器按钮

    参数：
        parent: 父对象
        prop_name: 属性名称
        prop_desc: 属性描述符
        current_value: 当前值

    返回：
        (容器控件, 按钮) 元组
    """
    # 创建容器控件
    container = QWidget(parent)
    # 创建水平布局
    layout = QHBoxLayout(container)
    # 设置布局边距为0
    layout.setContentsMargins(0, 0, 0, 0)
    # 设置布局间距为4像素
    layout.setSpacing(4)

    # 创建预览标签
    preview = QLabel()
    # 设置固定大小24x24
    preview.setFixedSize(24, 24)

    # 创建选择颜色按钮
    btn = QPushButton("选择颜色...")
    # 设置固定高度24像素
    btn.setFixedHeight(24)

    def _update_preview(val):
        """更新预览颜色

        参数：
            val: 颜色值
        """
        try:
            # 如果是有效的十六进制颜色字符串
            if isinstance(val, str) and val.startswith("#"):
                # 设置预览标签的样式
                preview.setStyleSheet(f"border: 1px solid #555; border-radius: 2px; background: {val};")
        except Exception:
            pass

    def _pick():
        """选择颜色"""
        # 尝试使用自定义ColorPickerDialog（RGB/HSV同步 + 图像采样）
        try:
            from gui.color_picker import ColorPickerDialog
            # 初始化颜色值
            initial = current_value or "#FFFFFF"
            # 如果初始值是十六进制字符串
            if isinstance(initial, str) and initial.startswith("#"):
                # 解析RGB值
                r, g, b = int(initial[1:3], 16), int(initial[3:5], 16), int(initial[5:7], 16)
            else:
                # 默认白色
                r, g, b = 255, 255, 255
            # 获取吸管取色源图: 节点 _picker_mat → 上游节点 mat → diagram 中任意 mat
            node = getattr(parent, '_current_node', None)
            picker_img = getattr(node, '_picker_mat', None) if node is not None else None
            if picker_img is None and node is not None:
                for n in getattr(node, 'from_node_datas', []):
                    m = getattr(n, 'mat', None)
                    if m is not None:
                        picker_img = m
                        break
            if picker_img is None and node is not None:
                d = getattr(node, 'diagram_data', None)
                if d and hasattr(d, 'get_all_nodes'):
                    for n in d.get_all_nodes():
                        m = getattr(n, 'mat', None)
                        if m is not None:
                            picker_img = m
                            break
            # 打开颜色选择器
            result = ColorPickerDialog.get_color(rgb=(r, g, b), picker_image=picker_img, parent=parent)
            if result:
                # 获取十六进制值
                hex_val = result.get("hex", initial)
                # 更新预览
                _update_preview(hex_val)
                # 写回节点属性（持久化取色结果）
                parent._set_property_value(prop_name, hex_val)
                return
        except Exception:
            pass

        # 打开系统颜色选择器
        color = QColorDialog.getColor(parent=parent)
        # 如果选择了有效颜色
        if color.isValid():
            # 转换为十六进制字符串
            hex_val = "#{:02X}{:02X}{:02X}".format(color.red(), color.green(), color.blue())
            # 更新预览
            _update_preview(hex_val)
            # 写回节点属性
            parent._set_property_value(prop_name, hex_val)

    # 连接按钮点击信号
    btn.clicked.connect(_pick)
    # 更新预览
    _update_preview(current_value)

    # 添加控件到布局
    layout.addWidget(preview)
    layout.addWidget(btn, 1)  # 拉伸因子为1

    # 如果是只读属性
    if prop_desc.readonly:
        # 禁用按钮
        btn.setEnabled(False)

    # 返回容器和按钮
    return container, btn


@register_editor("crop")
def _create_crop_editor(parent, prop_name, prop_desc, current_value):
    """模板裁剪控件

    提供「裁剪模板」按钮打开 CropDialog，以及「删除」按钮清空模板。
    裁剪源图优先级: 上游节点 mat > diagram 起始节点 mat > 空白图。
    """
    import numpy as np

    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    preview = QLabel("(未设置)")
    preview.setStyleSheet("color: #999; font-size: 11px;")

    crop_btn = QPushButton("裁剪模板...")
    crop_btn.setFixedHeight(24)

    delete_btn = QPushButton("✕")
    delete_btn.setFixedSize(24, 24)
    delete_btn.setToolTip("清空模板")
    delete_btn.setStyleSheet(
        "QPushButton { background: #5a1a1a; color: #ff6666; border: 1px solid #833;"
        "border-radius: 2px; font-size: 12px; }"
        "QPushButton:hover { background: #7a2a2a; }"
    )

    def _get_source_image():
        """获取裁剪源图"""
        parent_node = getattr(parent, '_current_node', None)
        if parent_node is None:
            return np.zeros((480, 640, 3), dtype=np.uint8)

        # 1. 上游节点的 mat（最优先 — 用户已运行过上游）
        for n in getattr(parent_node, 'from_node_datas', []):
            if hasattr(n, 'mat') and n.mat is not None:
                return n.mat

        # 2. diagram 中的起始节点
        diagram = getattr(parent_node, 'diagram_data', None)
        if diagram and hasattr(diagram, 'get_all_nodes'):
            for n in diagram.get_all_nodes():
                if hasattr(n, 'mat') and n.mat is not None:
                    return n.mat
                r = getattr(n, 'result_image_source', None)
                if r is not None and isinstance(r, np.ndarray):
                    return r

        # 3. 上一个运行结果图像
        r = getattr(parent_node, 'result_image_source', None)
        if r is not None and isinstance(r, np.ndarray):
            return r

        return np.zeros((480, 640, 3), dtype=np.uint8)

    def _refresh_preview():
        """更新预览标签显示当前模板状态。"""
        parent_node = getattr(parent, '_current_node', None)
        if parent_node and hasattr(parent_node, 'base64_string') and parent_node.base64_string:
            tmpl = parent_node.get_template_image()
            if tmpl is not None:
                h, w = tmpl.shape[:2]
                b64_len = len(parent_node.base64_string)
                preview.setText(f"✓ 模板: {w}x{h} px ({b64_len} chars)")
                return
        preview.setText("(未设置)")

    def _crop():
        image = _get_source_image()
        result = CropDialog.crop_image(image, parent=parent)
        if result and result.get("base64"):
            parent_node = getattr(parent, '_current_node', None)
            if parent_node and hasattr(parent_node, 'base64_string'):
                parent_node.base64_string = result["base64"]
                parent_node.set_template_from_image(result["image"])
            _refresh_preview()

    def _delete():
        parent_node = getattr(parent, '_current_node', None)
        if parent_node and hasattr(parent_node, 'base64_string'):
            parent_node.base64_string = ""
            # 清除缓存的属性值
            if hasattr(parent_node, '_base64_string'):
                parent_node._base64_string = ""
        _refresh_preview()

    crop_btn.clicked.connect(_crop)
    delete_btn.clicked.connect(_delete)

    layout.addWidget(preview)
    layout.addWidget(crop_btn)
    layout.addWidget(delete_btn)
    if prop_desc.readonly:
        crop_btn.setEnabled(False)
        delete_btn.setEnabled(False)

    _refresh_preview()
    return container, crop_btn

@register_editor("file_collection")
def _create_file_collection_editor(parent, prop_name, prop_desc, current_value):
    """多文件路径编辑器，带列表显示和添加/移除按钮

    参数：
        parent: 父对象
        prop_name: 属性名称
        prop_desc: 属性描述符
        current_value: 当前值

    返回：
        (容器控件, 按钮) 元组
    """
    # 获取主题管理器
    from gui.theme import theme_manager as tm
    # 创建容器控件
    container = QWidget(parent)
    # 创建垂直布局
    lo = QVBoxLayout(container)
    # 设置布局边距为0
    lo.setContentsMargins(0, 0, 0, 0)
    # 设置布局间距为4
    lo.setSpacing(4)

    # 创建顶部水平布局
    top = QHBoxLayout()
    top.setContentsMargins(0, 0, 0, 0)
    top.setSpacing(4)

    # 创建文件数量标签
    label = QLabel(f"{len(current_value) if isinstance(current_value, list) else 0} 个文件")
    label.setStyleSheet("color: #999; font-size: 11px;")
    # 添加到布局，拉伸因子为1
    top.addWidget(label, 1)

    # 添加文件按钮
    add_btn = QPushButton("添加文件")
    add_btn.setFixedHeight(24)
    # 添加到布局
    top.addWidget(add_btn)

    # 添加文件夹按钮
    add_dir_btn = QPushButton("添加文件夹")
    add_dir_btn.setFixedHeight(24)
    # 添加到布局
    top.addWidget(add_dir_btn)

    # 清空按钮
    clr_btn = QPushButton("清空")
    clr_btn.setFixedHeight(24)
    # 添加到布局
    top.addWidget(clr_btn)

    # 添加顶部布局到垂直布局
    lo.addLayout(top)

    # 创建列表控件
    list_w = QListWidget()
    # 设置最大高度80像素
    list_w.setMaximumHeight(80)
    # 设置列表控件样式
    list_w.setStyleSheet(f"QListWidget {{ background: {tm.c('bg_surface_input')}; border: 1px solid {tm.c('border')}; color: {tm.c('text_primary')}; font-size: 11px; }}")
    # 添加到布局
    lo.addWidget(list_w)

    def _refresh():
        """刷新文件列表显示"""
        # 从父对象的当前节点获取文件列表
        files = getattr(parent._current_node, prop_name, []) if parent._current_node else []
        # 如果不是列表类型，转换为列表
        if not isinstance(files, list):
            files = [files] if files else []
        # 清空列表控件
        list_w.clear()
        # 遍历所有文件
        for f in files:
            # 如果是字符串，显示文件名；否则显示字符串形式
            list_w.addItem(os.path.basename(str(f)) if isinstance(f, str) else str(f))
        # 更新文件数量标签
        label.setText(f"{len(files)} 个文件")

    def _add():
        """添加文件"""
        from PyQt5.QtWidgets import QFileDialog
        # 打开文件选择对话框
        paths, _ = QFileDialog.getOpenFileNames(parent, "选择文件", "",
                                                  "图像文件 (*.png *.jpg *.bmp *.tiff);;所有文件 (*.*)")
        # 如果选择了文件且存在当前节点
        if paths and parent._current_node:
            # 获取现有文件列表
            existing = list(getattr(parent._current_node, prop_name, []) or [])
            # 遍历新选择的文件
            for p in paths:
                # 如果文件不在列表中，添加
                if p not in existing:
                    existing.append(p)
            # 设置属性值
            parent._set_property_value(prop_name, existing)
            # 刷新显示
            _refresh()

    def _add_dir():
        """添加文件夹中的所有图像文件"""
        # 打开文件夹选择对话框
        folder = QFileDialog.getExistingDirectory(parent, "选择文件夹")
        # 如果选择了文件夹且存在当前节点
        if folder and parent._current_node:
            # 获取现有文件列表
            existing = list(getattr(parent._current_node, prop_name, []) or [])
            # 遍历文件夹中的文件
            for fn in os.listdir(folder):
                # 获取完整路径
                fp = os.path.join(folder, fn)
                # 如果是文件且不在列表中
                if os.path.isfile(fp) and fp not in existing:
                    # 添加到列表
                    existing.append(fp)
            # 设置属性值
            parent._set_property_value(prop_name, existing)
            # 刷新显示
            _refresh()

    def _clear():
        """清空所有文件"""
        # 如果存在当前节点
        if parent._current_node:
            # 设置空列表
            parent._set_property_value(prop_name, [])
            # 刷新显示
            _refresh()

    # 连接按钮点击信号
    add_btn.clicked.connect(_add)
    add_dir_btn.clicked.connect(_add_dir)
    clr_btn.clicked.connect(_clear)
    # 初始化刷新
    _refresh()

    # 如果是只读属性
    if prop_desc.readonly:
        # 禁用所有按钮
        add_btn.setEnabled(False)
        add_dir_btn.setEnabled(False)
        clr_btn.setEnabled(False)

    # 返回容器和添加按钮
    return container, add_btn


@register_editor("image_selector")
def _create_image_selector_editor(parent, prop_name, prop_desc, current_value):
    """可选结果图像的下拉选择器

    参数：
        parent: 父对象
        prop_name: 属性名称
        prop_desc: 属性描述符
        current_value: 当前值

    返回：
        (下拉框, 下拉框) 元组
    """
    # 创建下拉框
    combo = QComboBox(parent)
    # 添加"自动"选项
    combo.addItem("(自动)", None)
    # 如果存在当前节点且有result_images属性
    if parent._current_node and hasattr(parent._current_node, 'result_images'):
        # 遍历节点的结果图像
        for img in parent._current_node.result_images:
            # 添加选项
            combo.addItem(img.name, img)
    # 设置样式
    combo.setStyleSheet("QComboBox { background: #333337; color: #dcdcdc; border: 1px solid #3f3f46; padding: 4px 8px; }")
    # 如果是只读属性
    if prop_desc.readonly:
        # 禁用下拉框
        combo.setEnabled(False)
    # 返回下拉框
    return combo, combo


# ── 属性面板 ────────────────────────────────────────────────────────

class PropertyPanel(QWidget):
    """TabFormPresenter 移植：NodeBase 对象的标签页属性编辑器

    每个属性组（运行参数、结果参数等）成为一个独立的标签页。
    通过 EditorRegistry 解析自定义编辑器。

    与节点渲染解耦 — 节点通过 Property 描述符和 get_property_presenter() 暴露属性
    """

    # 属性变化信号：属性名，旧值，新值
    property_changed = pyqtSignal(str, object, object)

    def __init__(self, parent=None, group_filter: list[str] | None = None,
                 readonly: bool = False):
        """初始化属性面板

        参数：
            parent: 父对象
            group_filter: 分组过滤器（只显示指定分组）
            readonly: 是否只读
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 当前编辑的节点
        self._current_node: NodeBase | None = None
        # 图像查看器引用
        self._image_viewer = None
        # 属性控件字典
        self._property_widgets: dict[str, QWidget] = {}
        # 分组过滤器
        self._group_filter = group_filter
        # 强制只读标志
        self._force_readonly = readonly
        # 刷新定时器（防抖）
        self._refresh_timer = QTimer(self)
        # 设置为单次触发
        self._refresh_timer.setSingleShot(True)
        # 设置间隔500毫秒
        self._refresh_timer.setInterval(500)
        # 连接超时信号到刷新方法
        self._refresh_timer.timeout.connect(self._do_refresh)
        # 设置UI
        self._setup_ui()

    def set_image_viewer(self, viewer):
        """设置图像查看器

        参数：
            viewer: 图像查看器对象
        """
        self._image_viewer = viewer

    def _is_readonly(self, prop_desc: Property) -> bool:
        """判断属性是否只读

        参数：
            prop_desc: 属性描述符

        返回：
            是否只读
        """
        return self._force_readonly or prop_desc.readonly

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置布局间距为0
        layout.setSpacing(0)

        # 创建标签页控件
        self._tabs = QTabWidget()
        # 设置标签页样式
        self._tabs.setStyleSheet("""
            QTabWidget::pane { background: #252526; border: none; }
            QTabBar::tab {
                background: #2d2d30; color: #999; padding: 6px 16px;
                border: none; border-bottom: 2px solid transparent;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #252526; color: #dcdcdc;
                border-bottom: 2px solid #0078d4;
            }
            QTabBar::tab:hover { background: #3e3e42; }
        """)
        # 添加到布局
        layout.addWidget(self._tabs)
        # 连接主题变化信号
        connect_theme(self._refresh_qss)

    def _refresh_qss(self):
        """刷新主题样式"""
        # 获取主题管理器
        tm = theme_manager
        # 设置标签页样式
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ background: {tm.color('bg_surface').name()}; border: none; }}
            QTabBar::tab {{ background: {tm.color('bg_surface_raised').name()}; color: {tm.color('text_secondary').name()};
                           padding: 6px 16px; border: none; border-bottom: 2px solid transparent; font-size: 12px; }}
            QTabBar::tab:selected {{ background: {tm.color('bg_surface').name()}; color: {tm.color('text_primary').name()};
                                    border-bottom: 2px solid {tm.color('accent').name()}; }}
            QTabBar::tab:hover {{ background: {tm.color('bg_surface_hover').name()}; }}
        """)

    # ── 节点绑定 ──────────────────────────────────────────────────

    def set_node(self, node: NodeBase | None):
        """设置要编辑的节点

        参数：
            node: 节点对象
        """
        # 如果节点相同，返回
        if node is self._current_node:
            return
        # 保存当前节点
        self._current_node = node
        # 启动刷新定时器
        self._refresh_timer.start()

    def _do_refresh(self):
        """重建标签页属性编辑器"""
        # 清空标签页
        self._tabs.clear()
        # 删除所有属性控件
        for w in list(self._property_widgets.values()):
            w.deleteLater()
        # 清空属性控件字典
        self._property_widgets.clear()

        # 如果没有当前节点
        if self._current_node is None:
            # 创建空标签页
            empty = QLabel("未选择节点\n\n选择工作流中的节点后可编辑参数")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #666; font-size: 12px; padding: 20px;")
            self._tabs.addTab(empty, "属性")
            return

        # 发现属性
        properties = self._discover_properties()

        # 按属性组分组
        groups: dict[str, list] = {}
        for prop_name, prop_desc in properties:
            # 获取分组名称
            group = prop_desc.group or PropertyGroupNames.OTHER_PARAMETERS
            groups.setdefault(group, []).append((prop_name, prop_desc))

        # 分组顺序
        group_order = [
            PropertyGroupNames.BASE_PARAMETERS,      # 基本参数
            PropertyGroupNames.RUN_PARAMETERS,       # 运行参数
            PropertyGroupNames.FLOW_PARAMETERS,      # 流程控制
            PropertyGroupNames.DISPLAY_PARAMETERS,   # 显示参数
            PropertyGroupNames.RESULT_PARAMETERS,    # 结果参数
            PropertyGroupNames.OTHER_PARAMETERS,     # 其他参数
        ]

        # 遍历分组顺序
        for group_name in group_order:
            # 如果有分组过滤器且当前分组不在过滤器中，跳过
            if self._group_filter is not None and group_name not in self._group_filter:
                continue
            # 获取分组中的属性
            props = groups.get(group_name, [])
            # 如果没有属性，跳过
            if not props:
                continue
            # 按order排序
            props.sort(key=lambda x: x[1].order)
            # 创建属性名到描述符的映射
            prop_map = {name: desc for name, desc in props}
            # 已使用的属性名集合
            consumed: set[str] = set()

            # 创建标签页
            tab = QWidget()
            # 创建滚动区域
            scroll = QScrollArea()
            # 设置控件可调整大小
            scroll.setWidgetResizable(True)
            # 设置样式
            scroll.setStyleSheet(
                "QScrollArea { background: #252526; border: none; }"
                "QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {"
                " min-height: 28px; padding: 4px 8px; font-size: 13px;"
                "}"
            )
            # 创建表单控件
            form_widget = QWidget()
            # 创建表单布局
            form = QFormLayout(form_widget)
            # 设置标签左对齐
            form.setLabelAlignment(Qt.AlignLeft)
            # 设置边距
            form.setContentsMargins(12, 12, 12, 12)
            # 设置间距
            form.setSpacing(10)
            form.setVerticalSpacing(12)

            # HSV三通道编辑器检测
            for suffix, label_text in (("low", "HSV下限"), ("high", "HSV上限")):
                # 构建属性名
                hsv_names = [f"h_{suffix}", f"s_{suffix}", f"v_{suffix}"]
                # 如果所有属性都存在
                if all(name in prop_map for name in hsv_names):
                    # 创建HSV三通道控件
                    widget = self._create_hsv_triplet_widget(hsv_names, label_text)
                    if widget is not None:
                        # 添加表单行
                        form.addRow(self._make_label(label_text, "HSV 颜色范围编辑器"), widget)
                        # 标记为已使用
                        consumed.update(hsv_names)

            # 遍历属性
            for prop_name, prop_desc in props:
                # 如果已使用，跳过
                if prop_name in consumed:
                    continue
                # 创建控件
                widget = self._create_widget(prop_name, prop_desc)
                if widget is None:
                    continue
                # 添加表单行
                form.addRow(
                    self._make_label(prop_desc.display_name or prop_name, prop_desc.description),
                    widget,
                )

            # 设置滚动区域控件
            scroll.setWidget(form_widget)
            # 创建标签页布局
            tab_layout = QVBoxLayout(tab)
            # 设置边距为0
            tab_layout.setContentsMargins(0, 0, 0, 0)
            # 添加滚动区域
            tab_layout.addWidget(scroll)
            # 添加标签页
            self._tabs.addTab(tab, group_name)

    def _make_label(self, text: str, tooltip: str = "") -> QLabel:
        """创建标签

        参数：
            text: 标签文本
            tooltip: 工具提示

        返回：
            QLabel对象
        """
        # 创建标签
        label = QLabel(text)
        # 设置样式
        label.setStyleSheet("color: #bbb; font-size: 13px;")
        # 如果有工具提示
        if tooltip:
            # 设置工具提示
            label.setToolTip(tooltip)
        # 返回标签
        return label

    def _discover_properties(self) -> list[tuple[str, Property]]:
        """发现节点上的所有Property属性

        返回：
            (属性名, 属性描述符) 列表
        """
        # 结果列表
        result = []
        # 遍历节点的MRO（方法解析顺序）
        for cls in type(self._current_node).__mro__:
            # 如果到达object，停止
            if cls is object:
                break
            # 遍历类的字典
            for name, desc in cls.__dict__.items():
                # 如果是Property描述符
                if isinstance(desc, Property):
                    # 如果属性名还没有添加
                    if name not in [r[0] for r in result]:
                        result.append((name, desc))

        # 源节点不应显示image_source_mode属性
        if isinstance(self._current_node, SrcFilesVisionNodeData):
            result = [(name, desc) for name, desc in result if name != "image_source_mode"]

        # 为特殊节点类型注入合成属性
        existing = {name for name, _ in result}
        # 如果是ROI节点且没有roi属性
        if isinstance(self._current_node, ROINodeData) and "roi" not in existing:
            result.append(("roi", Property(
                None, name="ROI范围", group=PropertyGroupNames.BASE_PARAMETERS,
                description="设置 ROI 模式与矩形范围", order=1001,
            )))
        # 如果是条件节点且没有conditions属性
        if isinstance(self._current_node, ConditionNodeData) and "conditions" not in existing:
            result.append(("conditions", Property(
                [], name="条件规则", group=PropertyGroupNames.RUN_PARAMETERS,
                description="编辑条件分支规则列表", order=900,
            )))
        # 返回结果
        return result

    # ── 控件工厂 ────────────────────────────────────────────────

    def _create_widget(self, prop_name: str, prop_desc: Property) -> QWidget | None:
        """为属性创建适当的控件

        参数：
            prop_name: 属性名称
            prop_desc: 属性描述符

        返回：
            创建的控件或None
        """
        # 特殊合成属性
        # ROI节点的roi属性
        if isinstance(self._current_node, ROINodeData) and prop_name == "roi":
            return self._create_roi_widget()
        # 条件节点的conditions属性
        if isinstance(self._current_node, ConditionNodeData) and prop_name == "conditions":
            return self._create_condition_widget()

        # 获取当前值
        current_value = getattr(self._current_node, prop_name, prop_desc.default)

        # 检查是否有自定义编辑器提示
        if prop_desc.editor and editor_registry.has(prop_desc.editor):
            # 获取编辑器工厂函数
            widget, control = editor_registry.get(prop_desc.editor)(
                self, prop_name, prop_desc, current_value)
            # 连接控件到属性系统
            self._wire_control(control, widget, prop_name, prop_desc, current_value)
            return widget

        # 获取值的类型
        value_type = type(current_value) if current_value is not None else str

        # 布尔类型
        if value_type is bool:
            # 创建复选框
            widget = QCheckBox()
            # 设置选中状态
            widget.setChecked(bool(current_value))
            # 连接状态变化信号
            widget.toggled.connect(lambda v, n=prop_name: self._set_property_value(n, v))
            # 保存到控件字典
            self._property_widgets[prop_name] = widget
            # 如果是只读
            if self._is_readonly(prop_desc):
                # 禁用控件
                widget.setEnabled(False)
            return widget

        # 整数类型
        elif value_type is int:
            # 创建数值框
            widget = QSpinBox()
            # 获取最小值
            min_v = int(prop_desc.min_val) if prop_desc.min_val is not None else -999999
            # 获取最大值
            max_v = int(prop_desc.max_val) if prop_desc.max_val is not None else 999999
            # 设置范围
            widget.setRange(min_v, max_v)
            # 设置当前值
            widget.setValue(int(current_value or 0))
            # 连接值变化信号
            widget.valueChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
            # 保存到控件字典
            self._property_widgets[prop_name] = widget
            # 如果是只读
            if self._is_readonly(prop_desc):
                # 设为只读
                widget.setReadOnly(True)
            return widget

        # 浮点数类型
        elif value_type is float:
            # 创建双精度数值框
            widget = QDoubleSpinBox()
            # 获取最小值
            min_v = float(prop_desc.min_val) if prop_desc.min_val is not None else -999999.0
            # 获取最大值
            max_v = float(prop_desc.max_val) if prop_desc.max_val is not None else 999999.0
            # 设置范围
            widget.setRange(min_v, max_v)
            # 设置小数位数
            widget.setDecimals(prop_desc.decimals)
            # 设置步进值
            widget.setSingleStep(prop_desc.step)
            # 设置当前值
            widget.setValue(float(current_value or 0.0))
            # 连接值变化信号
            widget.valueChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
            # 保存到控件字典
            self._property_widgets[prop_name] = widget
            # 如果是只读
            if self._is_readonly(prop_desc):
                # 设为只读
                widget.setReadOnly(True)
            return widget

        # 枚举类型
        elif isinstance(current_value, Enum):
            # 创建下拉框
            widget = QComboBox()
            # 获取枚举类型
            enum_type = type(current_value)
            # 遍历枚举成员
            for member in enum_type:
                # 添加选项
                widget.addItem(member.value, member)
            # 设置当前文本
            widget.setCurrentText(current_value.value if current_value else "")
            # 连接索引变化信号
            widget.currentIndexChanged.connect(
                lambda idx, n=prop_name, w=widget: self._set_property_value(n, w.currentData()))
            # 保存到控件字典
            self._property_widgets[prop_name] = widget
            return widget

        # 列表类型
        elif isinstance(current_value, list):
            # 创建容器
            container = QWidget()
            # 创建水平布局
            hbox = QHBoxLayout(container)
            # 设置边距为0
            hbox.setContentsMargins(0, 0, 0, 0)
            # 创建标签
            label = QLabel(f"[{len(current_value)} 项]")
            label.setStyleSheet("color: #999; font-size: 11px;")
            # 添加到布局
            hbox.addWidget(label)
            # 如果不是只读
            if not self._is_readonly(prop_desc):
                # 创建按钮
                btn = QPushButton("...")
                btn.setFixedWidth(30)
                btn.setFixedHeight(22)
                # 添加到布局
                hbox.addWidget(btn)
            # 保存到控件字典
            self._property_widgets[prop_name] = container
            return container

        # 字符串/其他类型
        else:
            # 创建行编辑框
            widget = QLineEdit()
            # 设置文本
            widget.setText(str(current_value or ""))

            # 文件路径检测
            is_path = any(kw in prop_name.lower() for kw in ["path", "file", "src", "dir", "folder"])

            # 如果是文件路径且不是只读
            if is_path and not self._is_readonly(prop_desc):
                # 创建容器
                container = QWidget()
                # 创建水平布局
                hbox = QHBoxLayout(container)
                # 设置边距为0
                hbox.setContentsMargins(0, 0, 0, 0)
                # 设置间距为2
                hbox.setSpacing(2)
                # 添加行编辑框
                hbox.addWidget(widget)

                # 创建浏览按钮
                browse_btn = QPushButton("...")
                browse_btn.setFixedWidth(28)
                browse_btn.setFixedHeight(22)
                # 连接点击信号
                browse_btn.clicked.connect(lambda _, w=widget: self._browse_file_path(w))
                # 添加到布局
                hbox.addWidget(browse_btn)

                # 保存到控件字典
                self._property_widgets[prop_name] = container
                # 连接文本变化信号
                widget.textChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
                return container

            # 连接文本变化信号
            widget.textChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
            # 保存到控件字典
            self._property_widgets[prop_name] = widget
            # 如果是只读
            if self._is_readonly(prop_desc):
                # 设为只读
                widget.setReadOnly(True)
            return widget

    def _wire_control(self, control, container, prop_name, prop_desc, current_value):
        """将自定义编辑器的控件连接到属性系统

        参数：
            control: 控件对象
            container: 容器控件
            prop_name: 属性名称
            prop_desc: 属性描述符
            current_value: 当前值
        """
        # 保存容器到控件字典
        self._property_widgets[prop_name] = container

        # 根据控件类型连接信号
        # 如果是数值框
        if isinstance(control, QSpinBox):
            control.valueChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
        # 如果是双精度数值框
        elif isinstance(control, QDoubleSpinBox):
            control.valueChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
        # 如果是复选框
        elif isinstance(control, QCheckBox):
            control.toggled.connect(lambda v, n=prop_name: self._set_property_value(n, v))
        # 如果是下拉框
        elif isinstance(control, QComboBox):
            control.currentIndexChanged.connect(
                lambda idx, n=prop_name, c=control: self._set_property_value(n, c.currentData() or c.currentText()))
        # 如果是行编辑框
        elif isinstance(control, QLineEdit):
            control.textChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
        # 如果是滑块
        elif isinstance(control, QSlider):
            control.valueChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))

        # 验证反馈
        if prop_desc.validator and isinstance(control, (QLineEdit, QSpinBox, QDoubleSpinBox)):
            def _validate(val=None, ctrl=control, vfn=prop_desc.validator):
                # 获取要验证的值
                if val is not None:
                    pass
                elif hasattr(ctrl, 'value'):
                    val = ctrl.value()
                else:
                    val = ctrl.text()
                # 执行验证
                ok, msg = vfn(val)
                # 根据验证结果设置样式
                style = "border: 1px solid #3f3f46;" if ok else "border: 1px solid #f44336;"
                if isinstance(ctrl, QLineEdit):
                    ctrl.setStyleSheet(f"background: #333337; color: #dcdcdc; {style} padding: 4px 8px;")
                if not ok:
                    # 设置工具提示显示错误信息
                    ctrl.setToolTip(msg)
            # 如果是行编辑框，连接文本变化信号
            if isinstance(control, QLineEdit):
                control.textChanged.connect(_validate)
            # 如果是数值框，连接值变化信号
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                control.valueChanged.connect(_validate)

    # ── HSV三通道编辑器 ───────────────────────────────────────────────────

    def _create_hsv_triplet_widget(self, prop_names: list[str], title: str) -> QWidget:
        """创建HSV三通道编辑器控件

        参数：
            prop_names: 属性名列表 [h_name, s_name, v_name]
            title: 标题

        返回：
            容器控件
        """
        # 创建容器
        container = QWidget()
        # 创建水平布局
        layout = QHBoxLayout(container)
        # 设置边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置间距为4
        layout.setSpacing(4)

        # 数值框字典
        spin_boxes: dict[str, QSpinBox] = {}
        # 标签映射
        labels_map = {prop_names[0]: "H", prop_names[1]: "S", prop_names[2]: "V"}
        # 创建预览标签
        preview = QLabel()
        # 设置固定大小20x20
        preview.setFixedSize(20, 20)
        # 设置样式
        preview.setStyleSheet("border: 1px solid #555; border-radius: 2px;")

        def current_hsv():
            """获取当前HSV值"""
            return tuple(spin_boxes[name].value() for name in prop_names)

        def update_preview():
            """更新预览颜色"""
            # 获取当前HSV值
            h, s, v = current_hsv()
            # 转换为BGR
            bgr = cv2.cvtColor(np.array([[[h, s, v]]], dtype=np.uint8), cv2.COLOR_HSV2BGR)[0, 0]
            # 转换为RGB
            rgb = (int(bgr[2]), int(bgr[1]), int(bgr[0]))
            # 设置预览样式
            preview.setStyleSheet(
                "border: 1px solid #555; border-radius: 2px; background: #{:02X}{:02X}{:02X};".format(*rgb))

        # 创建三个通道的控件
        for idx, pn in enumerate(prop_names):
            # 创建标签
            text = QLabel(labels_map[pn])
            text.setStyleSheet("color: #999; font-size: 11px;")
            # 添加到布局
            layout.addWidget(text)

            # 创建数值框
            spin = QSpinBox()
            # 设置范围：H通道0-179，S和V通道0-255
            spin.setRange(0, 179 if idx == 0 else 255)
            # 设置当前值
            spin.setValue(int(getattr(self._current_node, pn, 0)))
            # 连接值变化信号
            spin.valueChanged.connect(lambda value, n=pn: self._set_property_value(n, value))
            spin.valueChanged.connect(lambda _=None: update_preview())
            # 添加到布局
            layout.addWidget(spin)
            # 保存到字典
            spin_boxes[pn] = spin

        # 添加预览标签
        layout.addWidget(preview)

        # 创建选色按钮
        pick_btn = QPushButton("选色")
        pick_btn.setFixedHeight(24)

        def pick_color():
            """打开颜色选择器"""
            # 创建颜色选择器对话框
            dialog = ColorPickerDialog(viewer=self._image_viewer, parent=self)
            # 设置当前HSV值
            dialog.set_hsv(current_hsv())
            # 如果确认
            if dialog.exec_() == dialog.Accepted:
                # 获取新值
                h, s, v = dialog.get_hsv()
                # 更新各个通道
                spin_boxes[prop_names[0]].setValue(h)
                spin_boxes[prop_names[1]].setValue(s)
                spin_boxes[prop_names[2]].setValue(v)

        # 连接点击信号
        pick_btn.clicked.connect(pick_color)
        # 添加选色按钮
        layout.addWidget(pick_btn)
        # 更新预览
        update_preview()
        # 返回容器
        return container

    # ── ROI控件 ────────────────────────────────────────────────────

    def _get_current_image(self):
        """获取当前图像"""
        # 如果有图像查看器且有图像
        if self._image_viewer is not None and getattr(self._image_viewer, "image", None) is not None:
            return self._image_viewer.image
        # 如果是视觉节点
        if isinstance(self._current_node, VisionNodeData):
            # 如果有mat
            if self._current_node.mat is not None:
                return self._current_node.mat
            # 如果有结果图像源
            if isinstance(self._current_node._result_image_source, np.ndarray):
                return self._current_node._result_image_source
        return None

    def _snapshot_roi_value(self, node: ROINodeData) -> dict:
        """获取ROI值的快照

        参数：
            node: ROI节点

        返回：
            包含模式和矩形的字典
        """
        # 获取当前激活的ROI矩形
        rect = node.get_active_roi_rect()
        return {"mode": type(node.roi).__name__, "rect": tuple(rect) if rect else None}

    def _format_roi_text(self, node: ROINodeData) -> str:
        """格式化ROI显示文本

        参数：
            node: ROI节点

        返回：
            格式化后的字符串
        """
        # 获取当前激活的ROI矩形
        rect = node.get_active_roi_rect()
        if rect is None:
            return f"当前模式: {node.roi.name}（无有效 ROI）"
        # 解包矩形
        x, y, w, h = rect
        return f"当前模式: {node.roi.name} | X={x}, Y={y}, W={w}, H={h}"

    def _update_roi_overlay(self, node: ROINodeData):
        """更新ROI叠加层

        参数：
            node: ROI节点
        """
        # 如果没有图像查看器，返回
        if self._image_viewer is None:
            return
        # 设置ROI矩形
        self._image_viewer.set_roi_rect(node.get_active_roi_rect(),
                                         label=node.roi.name if node.roi else "ROI")

    def _create_roi_widget(self) -> QWidget:
        """创建ROI控件

        返回：
            ROI控件
        """
        # 获取当前节点
        node = self._current_node
        # 如果不是ROI节点，返回None
        if not isinstance(node, ROINodeData):
            return None

        # 创建容器
        container = QWidget()
        # 创建垂直布局
        layout = QVBoxLayout(container)
        # 设置边距为0
        layout.setContentsMargins(0, 0, 0, 0)
        # 设置间距为4
        layout.setSpacing(4)

        # 顶部水平布局
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        # 模式下拉框
        combo = QComboBox()
        # 获取所有ROI选项
        roi_options = node.get_rois()
        # 添加选项
        for roi in roi_options:
            combo.addItem(roi.name, roi)
        # 查找当前索引
        current_index = next((i for i, roi in enumerate(roi_options) if type(roi) is type(node.roi)), 0)
        # 设置当前索引
        combo.setCurrentIndex(current_index)
        # 添加到布局，拉伸因子为1
        top.addWidget(combo, 1)

        # 编辑按钮
        edit_btn = QPushButton("编辑...")
        edit_btn.setFixedHeight(28)
        edit_btn.setStyleSheet(
            "QPushButton { background: #3c3c3c; color: #dcdcdc; border: 1px solid #555;"
            "border-radius: 3px; padding: 4px 14px; font-size: 12px; }"
            "QPushButton:hover { background: #4a4a4a; }"
        )
        # 添加到布局
        top.addWidget(edit_btn)

        # 摘要标签
        summary = QLabel()
        # 允许换行
        summary.setWordWrap(True)
        # 设置样式
        summary.setStyleSheet("color: #aaa; font-size: 12px;")

        # 添加到布局
        layout.addLayout(top)
        layout.addWidget(summary)

        def refresh_state():
            summary.setText(self._format_roi_text(node))
            edit_btn.setEnabled(not isinstance(node.roi, FromROI))

        def change_mode(index: int):
            """模式改变"""
            # 保存旧值快照
            old_value = self._snapshot_roi_value(node)
            # 切换ROI模式
            node.roi = roi_options[index]
            # 发出属性变化信号
            self.property_changed.emit("roi", old_value, self._snapshot_roi_value(node))
            # 刷新状态
            refresh_state()

        def edit_roi():
            """编辑ROI"""
            # FromROI模式不能编辑
            if isinstance(node.roi, FromROI):
                return
            # 保存旧值快照
            old_value = self._snapshot_roi_value(node)
            rect = RoiEditorDialog.edit_roi(
                image=self._get_current_image(),
                rect=node.get_active_roi_rect() or None,
                parent=self,
            )
            # 如果取消，返回
            if rect is None:
                return
            # 如果是DrawROI或NoROI模式
            if isinstance(node.roi, (DrawROI, NoROI)):
                node.draw_roi.rect = tuple(rect)
                node.roi = node.draw_roi
            # 如果是InputROI模式
            elif isinstance(node.roi, InputROI):
                # 设置InputROI的坐标和尺寸
                node.input_roi.x, node.input_roi.y, node.input_roi.width, node.input_roi.height = rect
                # 确保使用InputROI
                node.roi = node.input_roi
            # 发出属性变化信号
            self.property_changed.emit("roi", old_value, self._snapshot_roi_value(node))
            # 刷新状态
            refresh_state()

        # 连接信号
        combo.currentIndexChanged.connect(change_mode)
        edit_btn.clicked.connect(edit_roi)
        # 刷新状态
        refresh_state()
        # 保存到控件字典
        self._property_widgets["roi"] = container
        # 返回容器
        return container

    # ── 条件控件 ──────────────────────────────────────────────

    def _clone_conditions(self, conditions: list[VisionPropertyCondition]) -> list[VisionPropertyCondition]:
        return [VisionPropertyCondition.from_dict(c.to_dict()) for c in conditions]

    def _create_condition_widget(self) -> QWidget:
        """创建条件控件 — 显示 ConditionsPrensenter 的分支摘要。"""
        node = self._current_node
        if not isinstance(node, ConditionNodeData):
            return None

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        count_label = QLabel()
        count_label.setStyleSheet("color: #aaa; font-size: 12px;")
        top.addWidget(count_label, 1)

        edit_btn = QPushButton("编辑条件...")
        edit_btn.setFixedHeight(28)
        edit_btn.setStyleSheet(
            "QPushButton { background: #3c3c3c; color: #dcdcdc; border: 1px solid #555;"
            "border-radius: 3px; padding: 4px 14px; font-size: 12px; }"
            "QPushButton:hover { background: #4a4a4a; }"
        )
        top.addWidget(edit_btn)

        summary = QLabel()
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #aaa; font-size: 12px;")
        layout.addLayout(top)
        layout.addWidget(summary)

        def refresh_state():
            presenter = node.conditions_presenter
            n_branches = len(presenter.branches)
            count_label.setText(f"已配置 {n_branches} 个条件分支")
            if presenter.branches:
                lines = []
                for b in presenter.branches[:3]:
                    conds_summary = ", ".join(
                        c.display_text() for c in b.conditions
                    ) if b.conditions else "(无条件)"
                    out_id = b.selected_output_node_id or "默认"
                    lines.append(f"• [{b.condition_operate.name}] {conds_summary} → {out_id}")
                summary.setText("\n".join(lines))
            else:
                summary.setText("尚未配置条件分支")

        def edit_conditions():
            # 保存旧值（兼容旧接口）
            presenter = node.conditions_presenter
            old_presenter_data = presenter.to_dict()
            result = ConditionEditorDialog.edit_conditions(node, parent=self)
            if result is None:
                # 用户取消，恢复旧状态
                node._conditions_presenter = type(presenter).from_dict(old_presenter_data)
                return
            self.property_changed.emit("conditions_presenter", old_presenter_data, presenter.to_dict())
            refresh_state()

        edit_btn.clicked.connect(edit_conditions)
        refresh_state()
        self._property_widgets["conditions"] = container
        return container

    # ── 辅助方法 ───────────────────────────────────────────────────────

    def _browse_file_path(self, line_edit: QLineEdit):
        """浏览文件路径

        参数：
            line_edit: 行编辑框
        """
        from core.node_base import SrcFilesVisionNodeData

        # 如果是源节点
        if isinstance(self._current_node, SrcFilesVisionNodeData):
            # 打开文件夹选择对话框
            folder = QFileDialog.getExistingDirectory(self, "选择图像文件夹")
            if folder:
                # 清空现有文件
                self._current_node.clear_files()
                # 添加文件夹中的所有图像
                self._current_node.add_files_from_folder(folder)
                # 获取文件列表
                paths = self._current_node.src_file_paths
                if paths:
                    # 设置当前文件路径
                    self._current_node.src_file_path = paths[0]
                    # 更新行编辑框
                    line_edit.setText(paths[0])
                # 刷新资源面板
                self._refresh_resource_panel()
        else:
            # 操作节点：选择单个文件
            path, _ = QFileDialog.getOpenFileName(
                self, "选择文件", line_edit.text(),
                "所有文件 (*.*);;图像文件 (*.png *.jpg *.bmp *.tiff)")
            if path:
                # 更新行编辑框
                line_edit.setText(path)

    def _refresh_resource_panel(self):
        """通知FlowResourcePanel重新加载缩略图"""
        from core.node_base import SrcFilesVisionNodeData
        # 如果不是源节点，返回
        if not isinstance(self._current_node, SrcFilesVisionNodeData):
            return
        # 查找主窗口
        main = self._find_main_window()
        # 如果有主窗口且有资源面板
        if main and hasattr(main, '_resource_panel'):
            # 设置资源面板的节点
            main._resource_panel.set_node(self._current_node)

    def _find_main_window(self):
        """查找主窗口"""
        # 从当前控件向上遍历
        w = self
        while w is not None:
            from gui.main_window import MainWindow
            # 如果是主窗口
            if isinstance(w, MainWindow):
                return w
            # 获取父对象
            w = w.parent()
        return None

    def _set_property_value(self, prop_name: str, new_value: Any, *, force: bool = False):
        """设置属性值

        参数：
            prop_name: 属性名称
            new_value: 新值
            force: 是否强制设置（跳过值比较）
        """
        # 如果没有当前节点，返回
        if self._current_node is None:
            return
        # 获取旧值
        old_value = getattr(self._current_node, prop_name, None)
        try:
            # 设置新值
            setattr(self._current_node, prop_name, new_value)
        except Exception:
            # 设置失败，返回
            return
        # 获取设置后的当前值
        current_value = getattr(self._current_node, prop_name, None)
        # 如果值发生变化或强制设置
        if force or old_value != current_value:
            # 发出属性变化信号
            self.property_changed.emit(prop_name, old_value, current_value)

    def flash_highlight(self):
        """短暂闪烁第一个标签页以引起注意"""
        # 如果没有标签页，返回
        if self._tabs.count() == 0:
            return
        # 获取第一个标签页
        first_tab = self._tabs.widget(0)
        if first_tab is None:
            return

        # 保存原始样式
        original = first_tab.styleSheet()
        # 闪烁样式：橙色边框
        flash_style = (
            "QGroupBox {"
            "color: #ff9800; border: 2px solid #ff9800; border-radius: 3px;"
            "margin-top: 10px; padding-top: 14px; font-weight: bold; font-size: 11px;"
            "}"
            "QGroupBox::title {"
            "subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #ff9800;"
            "}"
        )
        # 应用闪烁样式
        first_tab.setStyleSheet(flash_style)
        # 350毫秒后恢复原始样式
        QTimer.singleShot(350, lambda: first_tab.setStyleSheet(original))

    def refresh(self):
        """强制刷新属性显示"""
        # 如果有当前节点
        if self._current_node:
            # 执行刷新
            self._do_refresh()


# ═══════════════════════════════════════════════════════════════════════════
# 节点属性对话框
# ═══════════════════════════════════════════════════════════════════════════

def open_node_dialog(node, parent=None):
    """为节点打开标签页属性对话框

    解耦：节点的 get_property_presenter() 方法提供要渲染 Property 描述符的对象。
    不同的节点类型可以返回不同的展示器，用于类型特定的设置面板。

    参数：
        node: 节点数据对象
        parent: 父对象
    """
    # 如果节点有 get_property_presenter 方法，使用其返回值；否则使用节点本身
    presenter = node.get_property_presenter() if hasattr(node, 'get_property_presenter') else node
    # 获取对话框标题：优先使用 presenter 的 title，其次 name，最后默认值
    title = getattr(presenter, 'title', None) or getattr(presenter, 'name', '节点设置')

    # 创建对话框
    dlg = QDialog(parent)
    # 设置窗口标题
    dlg.setWindowTitle(title)
    # 设置最小尺寸 560x380
    dlg.setMinimumSize(560, 380)
    # 设置初始尺寸 660x420
    dlg.resize(660, 420)

    # 创建垂直布局
    layout = QVBoxLayout(dlg)
    # 设置布局边距为0
    layout.setContentsMargins(0, 0, 0, 0)
    # 设置布局间距为0
    layout.setSpacing(0)

    # 创建属性面板
    panel = PropertyPanel(dlg)
    # 设置面板要编辑的节点
    panel.set_node(presenter)
    # 添加属性面板到布局，拉伸因子为1
    layout.addWidget(panel, 1)

    # 底部按钮栏
    btn_row = QWidget()
    # 设置按钮栏样式
    btn_row.setStyleSheet("background: #2d2d30; border-top: 1px solid #3f3f46;")
    # 创建水平布局
    btn_layout = QHBoxLayout(btn_row)
    # 设置布局边距
    btn_layout.setContentsMargins(12, 8, 12, 8)

    # 关闭按钮
    close_btn = QPushButton("关闭")
    # 设置按钮样式
    close_btn.setStyleSheet(
        "QPushButton { background: #3c3c3c; color: #dcdcdc; border: 1px solid #555;"
        "border-radius: 3px; padding: 6px 24px; font-size: 12px; }"
        "QPushButton:hover { background: #4a4a4a; }"
    )
    # 连接关闭按钮点击信号到对话框接受
    close_btn.clicked.connect(dlg.accept)
    # 添加弹性空间
    btn_layout.addStretch()
    # 添加关闭按钮
    btn_layout.addWidget(close_btn)
    # 添加按钮栏到布局
    layout.addWidget(btn_row)

    # 执行对话框（模态）
    dlg.exec_()
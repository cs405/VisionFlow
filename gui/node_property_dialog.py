"""节点属性对话框"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton,
                             QHBoxLayout, QDialog)
from gui.property_panel import PropertyPanel

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
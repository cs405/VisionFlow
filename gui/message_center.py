"""消息中心 - 通知 / 快餐栏 / 对话框消息模式。
提供三种消息显示模式：
  - Notice：角落中的瞬态弹窗（自动消失）
  - Snack：面板底部的内联栏
  - Dialog：模态确认/错误对话框

所有消息都通过此中心，根据严重程度和上下文路由到适当的显示方式。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from PyQt5.QtWidgets import (QWidget, QLabel, QPushButton, QHBoxLayout,
                              QVBoxLayout, QMessageBox, QApplication)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve, pyqtSignal
from PyQt5.QtGui import QColor

from core.events import EventType, event_system


# ═══════════════════════════════════════════════════════════════════════════
# 消息类型
# ═══════════════════════════════════════════════════════════════════════════

class MessageType(Enum):
    """消息类型枚举，包含显示名称、颜色和对话框图标"""
    # 信息类型：蓝色
    INFO = ("信息", QColor("#2196f3"), QMessageBox.Information)
    # 成功类型：绿色
    SUCCESS = ("成功", QColor("#4caf50"), QMessageBox.Information)
    # 警告类型：橙色
    WARNING = ("警告", QColor("#ff9800"), QMessageBox.Warning)
    # 错误类型：红色
    ERROR = ("错误", QColor("#f44336"), QMessageBox.Critical)
    # 严重类型：深红色
    FATAL = ("严重", QColor("#d32f2f"), QMessageBox.Critical)


# ═══════════════════════════════════════════════════════════════════════════
# 通知弹窗
# ═══════════════════════════════════════════════════════════════════════════

class NoticePopup(QWidget):
    """出现在右上角的瞬态通知弹窗。

    可配置持续时间后自动消失。支持点击关闭。
    """

    # 关闭信号
    closed = pyqtSignal()

    def __init__(self, parent=None):
        """初始化通知弹窗

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 设置窗口标志：工具提示 + 无边框
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        # 设置属性：不激活窗口
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # 设置属性：不允许鼠标穿透
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        # 设置固定宽度320像素
        self.setFixedWidth(320)
        # 创建关闭定时器
        self._timer = QTimer(self)
        # 设置为单次触发
        self._timer.setSingleShot(True)
        # 连接超时信号到淡出方法
        self._timer.timeout.connect(self._fade_out)

        # 创建水平布局
        lo = QHBoxLayout(self)
        # 设置布局边距
        lo.setContentsMargins(12, 8, 12, 8)
        # 设置布局间距
        lo.setSpacing(8)

        # 图标标签
        self._icon = QLabel("●")
        # 设置图标固定宽度20像素
        self._icon.setFixedWidth(20)
        # 添加到布局
        lo.addWidget(self._icon)

        # 文本标签
        self._label = QLabel()
        # 允许换行
        self._label.setWordWrap(True)
        # 设置样式
        self._label.setStyleSheet("color: white; font-size: 12px;")
        # 添加到布局，拉伸因子为1
        lo.addWidget(self._label, 1)

        # 关闭按钮
        close_btn = QPushButton("✕")
        # 设置固定大小20x20
        close_btn.setFixedSize(20, 20)
        # 设置样式
        close_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: rgba(255,255,255,0.7); font-size: 12px; } QPushButton:hover { color: white; }")
        # 连接点击信号到淡出方法
        close_btn.clicked.connect(self._fade_out)
        # 添加到布局
        lo.addWidget(close_btn)

    def show_message(self, msg_type: MessageType, text: str, duration_ms: int = 4000):
        """显示通知消息

        参数：
            msg_type: 消息类型
            text: 消息文本
            duration_ms: 显示持续时间（毫秒）
        """
        # 获取消息类型的颜色
        color = msg_type.value[1]
        # 设置图标样式
        self._icon.setStyleSheet(f"color: {color.name()}; font-size: 14px;")

        # 获取消息类型的前缀
        prefix = msg_type.value[0]
        # 设置标签文本
        self._label.setText(f"<b>{prefix}</b>  {text}")

        # 根据消息类型设置背景色
        bg = "#333337"  # 默认深灰色
        if msg_type == MessageType.ERROR:
            bg = "#5c1a1a"  # 错误：深红色
        elif msg_type == MessageType.SUCCESS:
            bg = "#1a4c1a"  # 成功：深绿色
        elif msg_type == MessageType.WARNING:
            bg = "#5c3a1a"  # 警告：深橙色
        # 设置样式表
        self.setStyleSheet(f"background: {bg}; border: 1px solid #505050; border-radius: 6px;")

        # 调整大小
        self.adjustSize()
        # 如果有父对象，定位在右上角
        if self.parent():
            # 获取父对象的几何
            pgeo = self.parent().geometry()
            # 移动到父对象右上角偏移20像素
            self.move(pgeo.right() - self.width() - 20, pgeo.top() + 50)

        # 显示弹窗
        self.show()
        # 启动定时器
        self._timer.start(duration_ms)

    def _fade_out(self):
        """淡出并关闭弹窗"""
        # 停止定时器
        self._timer.stop()
        # 隐藏弹窗
        self.hide()
        # 发出关闭信号
        self.closed.emit()

    def mousePressEvent(self, ev):
        """鼠标按下事件"""
        # 点击后淡出关闭
        self._fade_out()


# ═══════════════════════════════════════════════════════════════════════════
# 快餐栏（底部内联栏）
# ═══════════════════════════════════════════════════════════════════════════

class SnackBar(QWidget):
    """面板底部的内联通知栏"""

    # 动作触发信号，携带动作ID
    action_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        """初始化快餐栏

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 设置固定高度为0（初始隐藏）
        self.setFixedHeight(0)
        # 初始不可见
        self.setVisible(False)
        # 创建隐藏定时器
        self._timer = QTimer(self)
        # 设置为单次触发
        self._timer.setSingleShot(True)
        # 连接超时信号到隐藏方法
        self._timer.timeout.connect(self.hide_bar)

        # 创建水平布局
        lo = QHBoxLayout(self)
        # 设置布局边距
        lo.setContentsMargins(12, 6, 12, 6)
        # 设置布局间距
        lo.setSpacing(8)

        # 文本标签
        self._label = QLabel()
        # 设置样式
        self._label.setStyleSheet("color: white; font-size: 12px;")
        # 添加到布局，拉伸因子为1
        lo.addWidget(self._label, 1)

        # 动作按钮
        self._action_btn = QPushButton()
        # 设置样式
        self._action_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #ffd700; font-size: 12px; font-weight: bold; } QPushButton:hover { text-decoration: underline; }")
        # 连接点击信号到动作信号
        self._action_btn.clicked.connect(lambda: self.action_triggered.emit("action"))
        # 初始不可见
        self._action_btn.setVisible(False)
        # 添加到布局
        lo.addWidget(self._action_btn)

    def show_message(self, msg_type: MessageType, text: str,
                     action_text: str = "", action_id: str = "",
                     duration_ms: int = 5000):
        """显示快餐栏消息

        参数：
            msg_type: 消息类型
            text: 消息文本
            action_text: 动作按钮文本
            action_id: 动作ID
            duration_ms: 显示持续时间（毫秒）
        """
        # 获取消息类型的颜色
        color = msg_type.value[1]
        # 设置样式表
        self.setStyleSheet(f"background: {color.darker(180).name()}; border-top: 2px solid {color.name()};")
        # 设置标签文本
        self._label.setText(f"<b>{msg_type.value[0]}</b>  {text}")

        # 如果有动作文本
        if action_text:
            # 设置按钮文本
            self._action_btn.setText(action_text)
            # 显示按钮
            self._action_btn.setVisible(True)

        # 设置固定高度36像素
        self.setFixedHeight(36)
        # 显示快餐栏
        self.setVisible(True)
        # 启动定时器
        self._timer.start(duration_ms)

    def hide_bar(self):
        """隐藏快餐栏"""
        # 停止定时器
        self._timer.stop()
        # 设置固定高度为0
        self.setFixedHeight(0)
        # 隐藏快餐栏
        self.setVisible(False)


# ═══════════════════════════════════════════════════════════════════════════
# 消息中心（统一外观）
# ═══════════════════════════════════════════════════════════════════════════

class MessageCenter(QWidget):
    """结合通知/快餐栏/对话框模式的消息服务。

    用法：
        center = MessageCenter(main_window)
        center.info("操作完成")
        center.error("处理失败", dialog=True)
        center.snack("项目已保存", action_text="撤销", action_id="undo_save")
    """

    def __init__(self, parent=None):
        """初始化消息中心

        参数：
            parent: 父对象
        """
        # 调用父类QWidget的构造函数
        super().__init__(parent)
        # 创建通知弹窗
        self._notice = NoticePopup(parent)
        # 创建快餐栏
        self._snack = SnackBar(self)
        # 连接快餐栏的动作触发信号
        self._snack.action_triggered.connect(self._on_snack_action)

        # 创建垂直布局
        lo = QVBoxLayout(self)
        # 设置布局边距为0
        lo.setContentsMargins(0, 0, 0, 0)
        # 添加弹性空间（将快餐栏推到底部）
        lo.addStretch()
        # 添加快餐栏
        lo.addWidget(self._snack)

        # 连接事件系统
        self._wire_events()

    def _wire_events(self):
        """连接事件系统"""
        # 信息消息事件
        event_system.subscribe(EventType.MESSAGE_INFO,
                               lambda s, **kw: self.info(kw.get("message", ""),
                                                         dialog=kw.get("dialog", False)))
        # 警告消息事件
        event_system.subscribe(EventType.MESSAGE_WARN,
                               lambda s, **kw: self.warning(kw.get("message", ""),
                                                            dialog=kw.get("dialog", False)))
        # 错误消息事件
        event_system.subscribe(EventType.MESSAGE_ERROR,
                               lambda s, **kw: self.error(kw.get("message", ""),
                                                          dialog=kw.get("dialog", True)))
        # 成功消息事件
        event_system.subscribe(EventType.MESSAGE_SUCCESS,
                               lambda s, **kw: self.success(kw.get("message", "")))

    # ── 通知API ────────────────────────────────────────────────────

    def notice(self, msg_type: MessageType, text: str, duration_ms: int = 4000):
        """显示通知消息

        参数：
            msg_type: 消息类型
            text: 消息文本
            duration_ms: 显示持续时间（毫秒）
        """
        self._notice.show_message(msg_type, text, duration_ms)

    def info(self, text: str, dialog: bool = False):
        """显示信息消息

        参数：
            text: 消息文本
            dialog: 是否使用对话框模式
        """
        if dialog:
            self.dialog(MessageType.INFO, text)
        else:
            self.notice(MessageType.INFO, text)

    def success(self, text: str):
        """显示成功消息

        参数：
            text: 消息文本
        """
        self.notice(MessageType.SUCCESS, text, 3000)

    def warning(self, text: str, dialog: bool = False):
        """显示警告消息

        参数：
            text: 消息文本
            dialog: 是否使用对话框模式
        """
        if dialog:
            self.dialog(MessageType.WARNING, text)
        else:
            self.notice(MessageType.WARNING, text, 5000)

    def error(self, text: str, dialog: bool = True):
        """显示错误消息

        参数：
            text: 消息文本
            dialog: 是否使用对话框模式（默认True）
        """
        if dialog:
            self.dialog(MessageType.ERROR, text)
        else:
            self.notice(MessageType.ERROR, text, 8000)

    def fatal(self, text: str):
        """显示严重错误消息（总是使用对话框）

        参数：
            text: 消息文本
        """
        self.dialog(MessageType.FATAL, text)

    # ── 快餐栏API ─────────────────────────────────────────────────

    def snack(self, text: str, msg_type: MessageType = MessageType.INFO,
              action_text: str = "", action_id: str = ""):
        """显示快餐栏消息

        参数：
            text: 消息文本
            msg_type: 消息类型
            action_text: 动作按钮文本
            action_id: 动作ID
        """
        self._snack.show_message(msg_type, text, action_text, action_id)

    def _on_snack_action(self, action_id: str):
        """快餐栏动作触发时的回调

        参数：
            action_id: 动作ID
        """
        # 子类可重写或连接信号处理
        pass

    # ── 对话框API ────────────────────────────────────────────────────

    def dialog(self, msg_type: MessageType, text: str, title: str = ""):
        """显示模态对话框

        参数：
            msg_type: 消息类型
            text: 消息文本
            title: 对话框标题
        """
        # 获取对话框图标
        icon = msg_type.value[2]
        # 获取标题（如果未指定则使用消息类型名称）
        title = title or msg_type.value[0]
        # 创建并显示消息框
        QMessageBox(icon, title, text, QMessageBox.Ok, self.parent()).exec_()

    def confirm(self, text: str, title: str = "确认") -> bool:
        """显示确认对话框

        参数：
            text: 消息文本
            title: 对话框标题

        返回：
            用户是否确认
        """
        # 创建确认对话框
        r = QMessageBox.question(self.parent(), title, text,
                                 QMessageBox.Yes | QMessageBox.No,
                                 QMessageBox.No)
        # 返回是否点击了"是"
        return r == QMessageBox.Yes
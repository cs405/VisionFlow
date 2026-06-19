"""模板管理器 — 保存、加载和管理复用的图像模板。

模板以 base64 PNG 格式存储在 assets/img_templates.json 中。
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialogButtonBox, QListWidget, QListWidgetItem, QMessageBox,
    QSplitter, QWidget,
)

import numpy as np
import base64
import cv2


def _templates_path() -> str:
    """返回模板存储 JSON 文件的路径"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", "img_templates.json")


def _load_templates() -> dict[str, dict[str, Any]]:
    """加载所有已保存的模板"""
    path = _templates_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("templates", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _save_templates(templates: dict[str, dict[str, Any]]) -> None:
    """保存模板到 JSON 文件"""
    path = _templates_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data: dict[str, dict[str, Any]] = {"templates": templates}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_img_template(name: str, base64_str: str, width: int = 0, height: int = 0) -> None:
    """保存一个图像模板

    参数：
        name: 模板名称
        base64_str: base64 编码的 PNG 图像
        width: 图像宽度
        height: 图像高度
    """
    templates = _load_templates()
    templates[name] = {
        "base64": base64_str,
        "width": width,
        "height": height,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_templates(templates)


def delete_img_template(name: str) -> bool:
    """删除一个图像模板"""
    templates = _load_templates()
    if name in templates:
        del templates[name]
        _save_templates(templates)
        return True
    return False


class ImgTemplateLoadDialog(QDialog):
    """从已保存模板列表中选择一个模板加载"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("加载模板")
        self.resize(720, 480)
        self._templates = _load_templates()
        self._selected_name: str | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal)

        # 左侧：模板列表
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("已保存的模板:"))

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection_changed)
        if not self._templates:
            self._list.addItem("(无已保存模板)")
        else:
            for tmpl_name in sorted(self._templates.keys()):
                item = QListWidgetItem(tmpl_name)
                self._list.addItem(item)
        left_layout.addWidget(self._list)

        # 删除按钮
        del_btn = QPushButton("删除选中模板")
        del_btn.setStyleSheet(
            "QPushButton { background: #5a1a1a; color: #ff6666; border: 1px solid #833;"
            "border-radius: 2px; padding: 4px 8px; }"
            "QPushButton:hover { background: #7a2a2a; }"
        )
        del_btn.clicked.connect(self._delete_selected)
        left_layout.addWidget(del_btn)

        splitter.addWidget(left)

        # 右侧：预览
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._preview_label = QLabel("(未选择模板)")
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setStyleSheet("border: 1px solid #555; background: #1e1e1e;")
        self._preview_label.setMinimumSize(200, 200)
        right_layout.addWidget(self._preview_label, 1)

        self._info_label = QLabel("")
        self._info_label.setStyleSheet("color: #999; font-size: 12px;")
        right_layout.addWidget(self._info_label)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_selection_changed(self, current: QListWidgetItem, previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        name = current.text()
        if name not in self._templates:
            self._preview_label.setText("(未选择模板)")
            self._info_label.setText("")
            return
        tmpl = self._templates[name]
        b64 = tmpl.get("base64", "")
        w = tmpl.get("width", 0)
        h = tmpl.get("height", 0)
        self._info_label.setText(f"尺寸: {w} x {h} px\n保存于: {tmpl.get('created_at', '未知')}")

        if b64:
            try:
                img_data = base64.b64decode(b64)
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    h_img, w_img = rgb.shape[:2]
                    qimg = QImage(rgb.data, w_img, h_img, w_img * 3, QImage.Format_RGB888).copy()
                    pix = QPixmap.fromImage(qimg)
                    scaled = pix.scaled(
                        self._preview_label.width(), self._preview_label.height(),
                        Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self._preview_label.setPixmap(scaled)
                    return
            except Exception:
                pass
        self._preview_label.setText("(无法预览)")

    def _delete_selected(self) -> None:
        current = self._list.currentItem()
        if current is None:
            return
        name = current.text()
        if name not in self._templates:
            return
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除模板「{name}」吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if delete_img_template(name):
                self._templates = _load_templates()
                self._list.clear()
                if not self._templates:
                    self._list.addItem("(无已保存模板)")
                    self._preview_label.setText("(未选择模板)")
                    self._info_label.setText("")
                else:
                    for tmpl_name in sorted(self._templates.keys()):
                        self._list.addItem(QListWidgetItem(tmpl_name))

    def _on_accept(self) -> None:
        current = self._list.currentItem()
        if current is None or current.text() not in self._templates:
            QMessageBox.warning(self, "提示", "请先选择一个模板")
            return
        self._selected_name = current.text()
        self.accept()

    def get_selected(self) -> dict | None:
        """返回选中模板的数据，如果没有选中则返回 None"""
        if self._selected_name and self._selected_name in self._templates:
            tmpl = self._templates[self._selected_name]
            return {
                "name": self._selected_name,
                "base64_string": tmpl.get("base64", ""),
                "width": tmpl.get("width", 0),
                "height": tmpl.get("height", 0),
            }
        return None

    @classmethod
    def select_template(cls, parent=None) -> dict | None:
        """打开模板选择对话框，返回选中的模板数据或 None"""
        dialog = cls(parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_selected()
        return None

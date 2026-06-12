"""模板图像存储管理与加载对话框

提供:
  - 模板图像数据的保存/加载/删除 (templates/ 文件夹，每个模板一个 JSON 文件)
  - ImgTemplateLoadDialog — 模板选择对话框
"""

import base64
import json
import os
import re
from datetime import datetime

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QInputDialog, QAbstractItemView,
    QFileDialog, QFrame,
)
from PyQt5.QtGui import QPixmap, QImage, QIcon


# =============================================================================
# 存储路径
# =============================================================================

def _templates_dir() -> str:
    """返回 templates/ 目录的绝对路径，如不存在则自动创建"""
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "templates")
    os.makedirs(d, exist_ok=True)
    return d


def _sanitize_filename(name: str) -> str:
    """将模板名称转为安全的文件名（保留中文，移除非法字符）"""
    name = name.strip()
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    return name if name else "unnamed"


# =============================================================================
# CRUD 操作
# =============================================================================

def load_img_templates() -> list[dict]:
    """加载 templates/ 目录中所有已保存的模板"""
    tmpl_dir = _templates_dir()
    templates: list[dict] = []
    if not os.path.isdir(tmpl_dir):
        return templates
    for fname in sorted(os.listdir(tmpl_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(tmpl_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 校验必要字段
            if isinstance(data, dict) and "base64_string" in data:
                data.setdefault("name", fname[:-5])
                data.setdefault("width", 0)
                data.setdefault("height", 0)
                data.setdefault("created_at", "")
                data["_filename"] = fname  # 用于删除时定位文件
                templates.append(data)
        except (json.JSONDecodeError, IOError):
            continue
    return templates


def save_img_template(name: str, base64_str: str, width: int, height: int):
    """将模板保存为独立的 JSON 文件到 templates/ 目录"""
    tmpl_dir = _templates_dir()
    filename = _sanitize_filename(name) + ".json"
    fpath = os.path.join(tmpl_dir, filename)

    # 如果同名文件已存在，追加数字后缀
    counter = 1
    while os.path.exists(fpath):
        filename = f"{_sanitize_filename(name)}_{counter}.json"
        fpath = os.path.join(tmpl_dir, filename)
        counter += 1

    data = {
        "name": name,
        "base64_string": base64_str,
        "width": width,
        "height": height,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def delete_img_template(index: int):
    """按索引删除模板（基于 load_img_templates 返回的列表顺序）"""
    templates = load_img_templates()
    if 0 <= index < len(templates):
        fname = templates[index].get("_filename")
        if fname:
            fpath = os.path.join(_templates_dir(), fname)
            if os.path.exists(fpath):
                os.remove(fpath)


# =============================================================================
# 缩略图工具
# =============================================================================

def _base64_to_qpixmap(b64_str: str, max_size: int = 64) -> QPixmap | None:
    """将 base64 字符串解码为缩略图 QPixmap"""
    try:
        buf = base64.b64decode(b64_str)
        arr = np.frombuffer(buf, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        h, w = img.shape[:2]
        scale = min(max_size / w, max_size / h, 1.0)
        nw, nh = int(w * scale), int(h * scale)
        if nw <= 0 or nh <= 0:
            return None
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (nw, nh))
        h_bytes = resized.tobytes()
        qimg = QImage(h_bytes, nw, nh, nw * 3, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg)
    except Exception:
        return None


# =============================================================================
# ImgTemplateLoadDialog — 模板加载对话框
# =============================================================================

class ImgTemplateLoadDialog(QDialog):
    """从已保存的模板图像中选择一个加载到节点中。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("加载模板")
        self.resize(500, 460)
        self._selected: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 打开文件按钮（顶部醒目位置）
        open_file_btn = QPushButton("打开文件...")
        open_file_btn.setFixedHeight(32)
        open_file_btn.setStyleSheet(
            "QPushButton { background: #1a3a5a; color: #66bbff; border: 1px solid #358;"
            "border-radius: 2px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: #2a4a6a; }"
        )
        open_file_btn.clicked.connect(self._on_open_file)
        layout.addWidget(open_file_btn)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("border: none; background: #444; max-height: 1px;")
        layout.addWidget(sep)

        # 提示
        tip = QLabel("或从已保存的模板中选择:")
        tip.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(tip)

        # 模板列表
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget {
                background: #1e1e1e; border: 1px solid #505050;
                color: #dcdcdc; font-size: 13px;
            }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #333; }
            QListWidget::item:selected { background: #094771; }
        """)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setIconSize(self._list.iconSize() * 2)
        layout.addWidget(self._list, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        load_btn = QPushButton("加载")
        load_btn.setFixedHeight(28)
        load_btn.clicked.connect(self._on_load)
        btn_row.addWidget(load_btn)

        delete_btn = QPushButton("删除")
        delete_btn.setFixedHeight(28)
        delete_btn.setStyleSheet(
            "QPushButton { background: #5a1a1a; color: #ff6666; border: 1px solid #833; }"
            "QPushButton:hover { background: #7a2a2a; }"
        )
        delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(delete_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(28)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

        self._refresh_list()

    def _refresh_list(self):
        self._list.clear()
        templates = load_img_templates()
        if not templates:
            item = QListWidgetItem("(没有已保存的模板)")
            item.setFlags(Qt.NoItemFlags)
            item.setTextAlignment(Qt.AlignCenter)
            self._list.addItem(item)
            return
        for tmpl in templates:
            text = f"{tmpl['name']}    ({tmpl['width']}x{tmpl['height']})    {tmpl.get('created_at', '')}"
            item = QListWidgetItem(text)
            pix = _base64_to_qpixmap(tmpl.get("base64_string", ""))
            if pix is not None:
                item.setIcon(QIcon(pix))
            item.setData(Qt.UserRole, tmpl)
            self._list.addItem(item)

    def _on_open_file(self):
        """打开文件对话框选择模板 JSON 文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择模板文件",
            _templates_dir(),
            "模板文件 (*.json);;所有文件 (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "base64_string" not in data:
                QMessageBox.warning(self, "无效文件", "所选文件不是有效的模板文件")
                return
            data.setdefault("name", os.path.splitext(os.path.basename(path))[0])
            self._selected = data
            self.accept()
        except (json.JSONDecodeError, IOError) as e:
            QMessageBox.warning(self, "读取失败", f"无法读取模板文件: {e}")

    def _on_load(self):
        sel = self._list.currentItem()
        if sel is None:
            QMessageBox.warning(self, "提示", "请先选择一个模板")
            return
        self._selected = sel.data(Qt.UserRole)
        self.accept()

    def _on_delete(self):
        row = self._list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一个模板")
            return
        tmpl = self._list.currentItem().data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除模板「{tmpl['name']}」吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            delete_img_template(row)
            self._refresh_list()

    def get_selected(self) -> dict | None:
        return self._selected

    @classmethod
    def select_template(cls, parent=None) -> dict | None:
        """打开模板选择对话框并返回选中的模板数据，取消返回 None"""
        dialog = cls(parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_selected()
        return None

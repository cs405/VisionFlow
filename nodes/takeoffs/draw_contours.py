"""绘制轮廓节点 — 在指定图像上绘制阈值化检测到的轮廓矩形框。

工作流: 色彩转换 → 高斯模糊 → 阈值化 → 轮廓绘制

轮廓检测在阈值化图像上进行，矩形框可绘制在用户指定的上游节点图像上。
支持面积过滤、边缘忽略、目标数量预设。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class DrawContoursNode(OpenCVNodeDataBase):
    """轮廓绘制节点：在指定图像上绘制阈值化检测到的轮廓。

    从上游阈值化节点获取二值图提取轮廓，在"指定绘制图"选择的节点图像上绘制矩形框。
    默认使用 pipeline 传递的 _original_mat。

    过滤规则：
      - 面积在 [min_area, max_area] 区间外 → 跳过
      - 矩形框触及边缘 margin 像素内 → 跳过
      - 按面积降序排列，最多取 target_count 个
    """

    __group__ = "图像分割提取模块"

    # ── 基本参数 ──
    draw_source_id = Property("", name="指定绘制图", group=PropertyGroupNames.BASE_PARAMETERS,
                              editor="draw_source", order=1001,
                              description="选择在上游哪个节点的图像上绘制矩形框，空=使用原始图像")

    # ── 运行参数 ──
    min_area = Property(100, name="最小面积", group=PropertyGroupNames.RUN_PARAMETERS,
                        min_val=0, description="面积小于此值的轮廓忽略")
    max_area = Property(999999, name="最大面积", group=PropertyGroupNames.RUN_PARAMETERS,
                        min_val=0, description="面积大于此值的轮廓忽略")
    margin_left = Property(0, name="忽略左边缘(px)", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=0, description="距左边缘多少像素内的轮廓忽略，0=不忽略")
    margin_right = Property(0, name="忽略右边缘(px)", group=PropertyGroupNames.RUN_PARAMETERS,
                            min_val=0, description="距右边缘多少像素内的轮廓忽略，0=不忽略")
    margin_top = Property(0, name="忽略上边缘(px)", group=PropertyGroupNames.RUN_PARAMETERS,
                          min_val=0, description="距上边缘多少像素内的轮廓忽略，0=不忽略")
    margin_bottom = Property(0, name="忽略下边缘(px)", group=PropertyGroupNames.RUN_PARAMETERS,
                             min_val=0, description="距下边缘多少像素内的轮廓忽略，0=不忽略")
    target_count = Property(0, name="目标数量", group=PropertyGroupNames.RUN_PARAMETERS,
                            min_val=0, description="期望绘制的矩形框数量，0=不限制")

    # ── 结果参数 ──
    matched = Property(False, name="是否满足", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True,
                       description="实际绘制数是否等于目标数量")
    drawn_count = Property(0, name="实际绘制数", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_x = Property(0, name="匹配X", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_y = Property(0, name="匹配Y", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_w = Property(0, name="匹配宽度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_h = Property(0, name="匹配高度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "轮廓绘制"

    # ── ROI 暴露（与模板匹配节点接口一致，供数据收集节点级联）──
    def get_active_roi_rect(self) -> tuple | None:
        if self.matched and self.match_w > 0 and self.match_h > 0:
            return (int(self.match_x), int(self.match_y),
                    int(self.match_w), int(self.match_h))
        return super().get_active_roi_rect()

    # ── 核心 ──

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        # 重置
        self.matched = False
        self.drawn_count = 0
        self.match_x = self.match_y = self.match_w = self.match_h = 0

        # 上游阈值化图像（二值图），用于提取轮廓
        thresh = from_node.mat if from_node is not None else None
        if thresh is None:
            return self.error(None, "无阈值化输入图像")

        # 确定绘制目标图像
        draw_canvas = self._resolve_draw_canvas(thresh)

        # 确保阈值图是单通道
        if len(thresh.shape) == 3:
            thresh_gray = cv2.cvtColor(thresh, cv2.COLOR_BGR2GRAY)
        else:
            thresh_gray = thresh

        # 提取轮廓
        contours, _ = cv2.findContours(thresh_gray, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return self.error(None, "未检测到轮廓")

        h, w = draw_canvas.shape[:2]
        ml, mr = self.margin_left, self.margin_right
        mt, mb = self.margin_top, self.margin_bottom

        # 过滤：面积 + 四边边缘距离
        candidates: list[tuple[np.ndarray, float, tuple]] = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_area or area > self.max_area:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            # 四边边缘忽略
            if ml > 0 and x < ml:
                continue
            if mr > 0 and x + bw > w - mr:
                continue
            if mt > 0 and y < mt:
                continue
            if mb > 0 and y + bh > h - mb:
                continue
            candidates.append((c, area, (x, y, bw, bh)))

        if not candidates:
            return self.error(None, f"过滤后无轮廓 (面积/边缘限制)")

        # 按面积降序，取前 N 个
        candidates.sort(key=lambda v: v[1], reverse=True)
        if self.target_count > 0:
            candidates = candidates[:self.target_count]

        # 在指定画布上绘制红色矩形框（确保是 3 通道才能画红色）
        canvas = draw_canvas.copy()
        if len(canvas.shape) == 2:
            canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
        for c, area, (x, y, bw, bh) in candidates:
            cv2.rectangle(canvas, (x, y), (x + bw, y + bh), (0, 0, 255), 4)

        count = len(candidates)
        self.drawn_count = count

        # 判断是否满足目标数量
        if self.target_count > 0:
            self.matched = (count == self.target_count)
        else:
            self.matched = (count > 0)

        # 暴露最大轮廓的矩形（供下游 FromROI 和数据收集）
        if candidates:
            self.match_x, self.match_y, self.match_w, self.match_h = candidates[0][2]

        if self.matched:
            return self.ok(canvas, f"绘制 {count} 个轮廓框（满足目标 {self.target_count}）" if self.target_count > 0
                           else f"绘制 {count} 个轮廓框")
        else:
            return self.error(None, f"绘制 {count}/{self.target_count} 个轮廓框（未满足目标）" if self.target_count > 0
                              else f"绘制 {count} 个轮廓框")

    # ── 绘制画布解析 ──

    def _resolve_draw_canvas(self, fallback: np.ndarray) -> np.ndarray:
        """根据 draw_source_id 查找上游节点，返回其输出图像作为绘制画布。"""
        if self.draw_source_id:
            for node in self.get_all_from_node_datas():
                if node.node_id == self.draw_source_id:
                    img = getattr(node, "mat", None)
                    if img is not None:
                        return img
                    img = getattr(node, "_result_image_source", None)
                    if img is not None:
                        return img
                    break
        # 未指定画布：向上游找第一个BGR图像（尺寸与_crop_chain_offset一致），
        # 保证输出尺寸与裁剪偏移匹配，ROIMapBackNode可正确映射
        for node in self.get_all_from_node_datas():
            img = getattr(node, "mat", None)
            if img is not None and len(img.shape) == 3:
                return img
        return fallback

    def _update_result_image_source(self):
        self._result_image_source = self._mat

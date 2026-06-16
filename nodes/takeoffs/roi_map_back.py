"""ROI映射回原图节点 — 将ROI区域的处理结果映射回完整原始图像。

当上游节点使用了ROI裁剪（DrawROI / InputROI）后，后续所有处理都在裁剪后的
ROI区域上进行。本节点自动查找上游所有ROI矩形参数，将各分支处理后的ROI图像
贴回原始图像对应位置。

同时自动叠加模板匹配节点（如XFeat）的匹配偏移量，
确保匹配目标区域被正确放回原图中的绝对位置。

两种模式自动适配：
- 单ROI：上游链中只有1个ROI → 使用 from_node 的完整处理结果
- 多ROI：上游有多个并行ROI分支 → 找出所有ROI及其分支处理结果，合并到原图
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

import cv2

from core.node_base import OpenCVNodeDataBase, ROINodeData, DrawROI, InputROI
from core.data_packet import FlowableResult

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class ROIMapBackNode(OpenCVNodeDataBase):
    """ROI映射回原图节点：将上游所有ROI区域的处理结果映射回完整原始图像。

    自动通过BFS搜索上游节点图中所有设置了 DrawROI 或 InputROI 的节点，
    并叠加匹配节点（XFeat等）的 match_x/y 偏移量计算绝对坐标。
    - 单个ROI：使用上游链的最终处理结果贴回原图
    - 多个ROI：找出各分支的处理结果，全部合并到同一张原图上

    若未找到ROI或无原始图像，则透传上游结果。
    """

    __group__ = "图像分割提取模块"

    def __init__(self):
        super().__init__()
        self.name = "ROI映射回原图"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        processed_input = self.get_input_mat(from_node.mat if from_node else None)
        if processed_input is None:
            return self.error(None, "无输入图像")

        original = self._original_mat
        if original is None:
            return self.ok(processed_input, "无原始图像，透传上游结果")

        # 收集所有上游ROI及其匹配偏移调整后的映射
        all_mappings = self._collect_all_roi_mappings()

        if not all_mappings:
            return self.ok(processed_input, "未找到上游ROI，透传上游结果")

        # 单ROI：使用上游链完整处理后的图像（from_node.mat）
        if len(all_mappings) == 1:
            roi_rect, _ = all_mappings[0]
            patches = [(roi_rect, processed_input)]
            desc = "ROI映射: 1个区域"
        else:
            # 多ROI：使用各分支自身的处理结果，全部合并到原图
            patches = [(rect, mat) for rect, mat in all_mappings if mat is not None]
            desc = f"ROI映射: {len(patches)}个区域"

        result = original.copy()
        oh, ow = result.shape[:2]

        for roi_rect, roi_patch in patches:
            x, y, w, h = map(int, roi_rect)
            x = max(0, min(x, ow - 1))
            y = max(0, min(y, oh - 1))
            w = min(w, ow - x)
            h = min(h, oh - y)

            patch = roi_patch
            if len(result.shape) != len(patch.shape):
                if len(patch.shape) == 2:
                    patch = cv2.cvtColor(patch, cv2.COLOR_GRAY2BGR)
                elif len(result.shape) == 2:
                    result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)

            place_h = min(h, patch.shape[0])
            place_w = min(w, patch.shape[1])
            if place_h > 0 and place_w > 0:
                result[y:y + place_h, x:x + place_w] = patch[:place_h, :place_w]

        return self.ok(result, desc)

    # ------------------------------------------------------------------
    # 上游图遍历
    # ------------------------------------------------------------------

    def _collect_all_roi_mappings(self) -> list[tuple[tuple, "np.ndarray"]]:
        """BFS遍历上游图，找出所有 (ROI矩形, 分支处理结果) 配对。

        对于每个ROI节点（CropNode），取其下游第一个节点的输出mat
        作为该分支的处理结果。同时叠加匹配节点（如XFeat）的
        match_x/y 偏移量，计算在原始图像中的绝对坐标。
        """
        upstream_ids, all_nodes = self._bfs_upstream()

        mappings: list[tuple[tuple, "np.ndarray"]] = []
        for node in all_nodes:
            if not isinstance(node, ROINodeData):
                continue
            rect = self._get_roi_rect(node)
            if rect is None:
                continue

            # 取该ROI节点下游的第一个分支节点（也在上游图中）的输出
            branch_mat = node.mat
            child = None
            for c in node.to_node_datas:
                if c.node_id in upstream_ids and c.mat is not None:
                    child = c
                    branch_mat = c.mat
                    break

            if branch_mat is not None:
                # 叠加匹配节点的偏移量（match_x, match_y 是ROI内的相对坐标）
                adjusted_rect = self._adjust_by_match_offset(rect, child)
                mappings.append((adjusted_rect, branch_mat))

        return mappings

    def _bfs_upstream(self) -> tuple[set[str], list]:
        """BFS遍历上游图，返回 (上游节点ID集合, 所有上游节点列表)。"""
        upstream_ids: set[str] = set()
        all_nodes: list = []
        queue = deque(self.from_node_datas)

        while queue:
            node = queue.popleft()
            if node.node_id in upstream_ids:
                continue
            upstream_ids.add(node.node_id)
            all_nodes.append(node)
            queue.extend(node.from_node_datas)

        return upstream_ids, all_nodes

    @staticmethod
    def _adjust_by_match_offset(rect: tuple, child) -> tuple:
        """如果child是匹配节点(XFeat等)且匹配成功，叠加match_x/y偏移量。

        match_x/y 是匹配目标在ROI区域内的相对坐标。
        叠加后得到在原始图像中的绝对坐标。
        """
        if child is None:
            return rect
        matched = getattr(child, 'matched', False)
        if not matched:
            return rect
        mx = int(getattr(child, 'match_x', 0))
        my = int(getattr(child, 'match_y', 0))
        mw = int(getattr(child, 'match_w', 0))
        mh = int(getattr(child, 'match_h', 0))
        if mw > 0 and mh > 0:
            return (rect[0] + mx, rect[1] + my, mw, mh)
        return rect

    @staticmethod
    def _get_roi_rect(node: ROINodeData) -> tuple | None:
        """从ROI节点提取矩形 (x, y, w, h)。"""
        roi = node.roi
        if isinstance(roi, DrawROI) and roi.rect is not None:
            return roi.rect
        if isinstance(roi, InputROI):
            return (roi.x, roi.y, roi.width, roi.height)
        return None

    def _update_result_image_source(self):
        self._result_image_source = self._mat

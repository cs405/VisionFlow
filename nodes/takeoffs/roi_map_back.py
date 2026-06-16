"""ROI映射回原图节点 — 将ROI区域的处理结果映射回完整原始图像。

当上游节点使用了ROI裁剪（DrawROI / InputROI）后，后续所有处理都在裁剪后的
ROI区域上进行。本节点自动查找上游所有ROI矩形参数，将各分支处理后的ROI图像
贴回原始图像对应位置。

同时自动叠加模板匹配节点（如XFeat）的匹配偏移量，
确保匹配目标区域被正确放回原图中的绝对位置。

两种模式自动适配：
- 单ROI：上游链中只有1个ROI → 使用 from_node 的完整处理结果
- 多ROI：上游有多个并行ROI分支 → 沿每个ROI分支走到终端节点，取终端mat
  （含后续全部处理如绘制轮廓），合并到原图
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

    自动通过BFS搜索上游节点图中所有设置了 DrawROI 或 InputROI 的节点。
    - 单个ROI：使用上游链的最终处理结果贴回原图
    - 多个ROI：沿每个ROI分支走到终端节点，取终端mat（含全部后续处理），
      并叠加匹配节点的偏移量，全部合并到同一张原图上
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

        all_mappings = self._collect_all_roi_mappings()

        if not all_mappings:
            return self.ok(processed_input, "未找到上游ROI，透传上游结果")

        # 单ROI：使用上游链完整处理后的图像（from_node.mat）
        if len(all_mappings) == 1:
            roi_rect, _ = all_mappings[0]
            patches = [(roi_rect, processed_input)]
            desc = "ROI映射: 1个区域"
        else:
            # 多ROI：使用各分支终端节点的处理结果
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
                # 补画绿色匹配框（中间CvtColor转灰度会丢失颜色）
                cv2.rectangle(result, (x, y), (x + place_w, y + place_h),
                             (0, 255, 0), 3)

        return self.ok(result, desc)

    # ------------------------------------------------------------------
    # 上游图遍历 — 多ROI分支 + 终端发现
    # ------------------------------------------------------------------

    def _collect_all_roi_mappings(self) -> list[tuple[tuple, "np.ndarray"]]:
        """遍历上游图，找出所有 (ROI矩形, 终端处理结果) 配对。

        对每个CropNode：
        1. 沿分支正向走到终端节点（最深的处理节点），取终端的mat
        2. 沿路找到匹配节点（如XFeat），叠加match_x/y偏移量
        """
        node_lookup, distances = self._bfs_upstream_with_distance()

        mappings: list[tuple[tuple, "np.ndarray"]] = []
        for node in node_lookup.values():
            if not isinstance(node, ROINodeData):
                continue
            rect = self._get_roi_rect(node)
            if rect is None:
                continue

            # 沿分支正向走到终端节点
            terminal = self._walk_to_terminal(node, node_lookup, distances)
            branch_mat = terminal.mat if terminal is not None and terminal.mat is not None else node.mat
            if branch_mat is None:
                continue

            # 找到匹配节点，叠加偏移量
            match_node = self._find_match_node(node, node_lookup)
            adjusted_rect = self._adjust_by_match_offset(rect, match_node)
            mappings.append((adjusted_rect, branch_mat))

        return mappings

    def _bfs_upstream_with_distance(self) -> tuple[dict[str, object], dict[str, int]]:
        """BFS遍历上游图。

        返回：
          node_lookup: {node_id: node对象}
          distances: {node_id: 距本节点的最短BFS距离}
        """
        node_lookup: dict[str, object] = {}
        distances: dict[str, int] = {self.node_id: 0}
        queue: deque = deque()

        for node in self.from_node_datas:
            queue.append((node, 1))

        while queue:
            node, dist = queue.popleft()
            if node.node_id in node_lookup:
                continue
            node_lookup[node.node_id] = node
            distances[node.node_id] = dist
            for parent in node.from_node_datas:
                queue.append((parent, dist + 1))

        return node_lookup, distances

    def _walk_to_terminal(self, roi_node, node_lookup: dict[str, object],
                          distances: dict[str, int]):
        """从ROI节点沿分支正向走，直到终端处理节点。

        每次前进时，在子节点中选择BFS距离最大的（距离本节点最远 = 处理链路最深）。
        遇到汇合点（from_node_datas > 1）时停止，避免走入共享的合并节点。
        返回分支终端节点。
        """
        current = roi_node
        while True:
            children = []
            for c in current.to_node_datas:
                if c.node_id not in node_lookup:
                    continue
                d = distances.get(c.node_id, 99999)
                children.append((d, c))

            if not children:
                break

            # 选距离最大的 = 处理链路最深的子节点
            children.sort(key=lambda x: -x[0])
            best = children[0][1]

            # 遇到汇合点停止（不再往前走共享节点）
            if len(best.from_node_datas) > 1:
                break

            current = best

        return current

    def _find_match_node(self, roi_node, node_lookup: dict[str, object]):
        """从ROI节点正向BFS，找到第一个匹配成功的节点（如XFeat）。

        用于获取match_x/y偏移量，计算在原始图像中的绝对坐标。
        """
        visited: set[str] = set()
        queue: deque = deque([roi_node])
        while queue:
            node = queue.popleft()
            if node.node_id in visited:
                continue
            visited.add(node.node_id)
            if getattr(node, 'matched', False):
                return node
            for child in node.to_node_datas:
                if child.node_id in node_lookup:
                    queue.append(child)
        return None

    @staticmethod
    def _adjust_by_match_offset(rect: tuple, match_node) -> tuple:
        """如果match_node匹配成功，叠加match_x/y/w/h偏移量。

        match_x/y 是匹配目标在ROI区域内的相对坐标。
        叠加后得到在原始图像中的绝对坐标。
        """
        if match_node is None:
            return rect
        mx = int(getattr(match_node, 'match_x', 0))
        my = int(getattr(match_node, 'match_y', 0))
        mw = int(getattr(match_node, 'match_w', 0))
        mh = int(getattr(match_node, 'match_h', 0))
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

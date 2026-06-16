"""ROI映射回原图节点 — 将上游所有裁剪/匹配的结果映射回完整原始图像。

完全解耦设计：不依赖任何特定节点类型。
依赖的只有一个标准属性 `_crop_chain_offset`：
  - VisionNodeData 基类自动维护，存储累积裁剪偏移量 (x, y, w, h)
  - ROINodeData.invoke() 在应用ROI时自动累加
  - 匹配节点（XFeat等）在匹配成功后累加匹配偏移
  - 不做裁剪的节点自动透传

ROIMapBackNode 只需要读取上游节点的 _crop_chain_offset 即可知道
其输出图像在原始图像中的绝对位置，无需了解上游是什么节点。
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

import cv2

from core.node_base import OpenCVNodeDataBase
from core.data_packet import FlowableResult

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class ROIMapBackNode(OpenCVNodeDataBase):
    """ROI映射回原图节点：将上游处理结果映射回完整原始图像。

    自动适配：
    - 单链路：读取 from_node._crop_chain_offset 直接映射
    - 多链路（并行分支汇合）：BFS遍历上游图，找到所有分支终端节点，
      读取各自的 _crop_chain_offset 和 mat，全部合并到原图
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

        # 收集所有分支的 (绝对坐标, 处理结果) 配对
        all_mappings = self._collect_branch_mappings()

        if not all_mappings:
            # 没有分支信息，尝试直接用 from_node 的偏移
            offset = getattr(from_node, '_crop_chain_offset', (0, 0, 0, 0))
            if offset[2] > 0 and offset[3] > 0:
                all_mappings = [(offset, processed_input)]
            else:
                return self.ok(processed_input, "未找到裁剪偏移，透传上游结果")

        # 单链路：使用 from_node 的完整处理结果
        if len(all_mappings) == 1:
            roi_rect, _ = all_mappings[0]
            patches = [(roi_rect, processed_input)]
            desc = "ROI映射: 1个区域"
        else:
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
                cv2.rectangle(result, (x, y), (x + place_w, y + place_h),
                             (0, 255, 0), 3)

        return self.ok(result, desc)

    # ------------------------------------------------------------------
    # 上游图遍历 — 解耦：只依赖 _crop_chain_offset，不认节点类型
    # ------------------------------------------------------------------

    def _collect_branch_mappings(self) -> list[tuple[tuple, "np.ndarray"]]:
        """BFS遍历上游图，收集所有分支的 (绝对坐标, 处理结果)。

        策略：收集所有有有效 _crop_chain_offset + mat 的非汇合点节点，
        按偏移量分组，每组保留BFS距离最大的（处理链路最深的终端）。
        深终端未执行时自动回退到浅终端。
        """
        node_lookup, distances = self._bfs_upstream()

        merge_ids: set[str] = set()
        for node in node_lookup.values():
            if len(node.from_node_datas) > 1:
                merge_ids.add(node.node_id)

        # 按偏移量分组，保留每组的最大距离节点
        best_per_offset: dict[tuple, tuple[object, int]] = {}

        for node in node_lookup.values():
            if node.node_id in merge_ids:
                continue
            offset = getattr(node, '_crop_chain_offset', (0, 0, 0, 0))
            if offset[2] <= 0 or offset[3] <= 0:
                continue
            if node.mat is None:
                continue

            d = distances.get(node.node_id, 99999)
            if offset not in best_per_offset or d > best_per_offset[offset][1]:
                best_per_offset[offset] = (node.mat, d)

        return [(offset, mat) for offset, (mat, _) in best_per_offset.items()]

    def _bfs_upstream(self) -> tuple[dict[str, object], dict[str, int]]:
        """BFS遍历上游图。

        返回：
          node_lookup: {node_id: node对象}
          distances: {node_id: 距本节点的BFS距离}
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

    def _update_result_image_source(self):
        self._result_image_source = self._mat

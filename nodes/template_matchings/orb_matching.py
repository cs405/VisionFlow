"""ORB特征匹配节点。
匹配两幅图像之间的 ORB 特征点，绘制匹配结果。
"""
import cv2
import numpy as np

from core.node_base import (Base64MatchingNodeData, OpenCVNodeDataBase,
                            Property, PropertyGroupNames)
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class OrbFeatureMatchingNode(Base64MatchingNodeData, OpenCVNodeDataBase):
    """ORB 特征匹配节点——检测并匹配两图之间的 ORB 特征点。

    输入：上游节点输出的图像（scene） + 用户设置的模板图像
    输出：绘制了匹配连线后的结果图像
    """
    # 节点所属分组（决定出现在哪个工具箱分组）
    __group__ = "模板匹配模块"

    # ── 运行参数（用户可调）──
    # 特征点数量属性（ORB 检测的最大特征点数量）
    n_features = Property(500, name="特征点数量",
                          group=PropertyGroupNames.RUN_PARAMETERS,
                          description="ORB 检测的最大特征点数量",
                          min_val=100, max_val=5000, step=100)

    # Lowe比值阈值属性（最近邻距离与次近邻距离的比值上限）
    ratio_threshold = Property(0.75, name="Lowe比值阈值",
                               group=PropertyGroupNames.RUN_PARAMETERS,
                               description="最近邻距离与次近邻距离的比值上限",
                               min_val=0.5, max_val=0.95, step=0.05, decimals=2)

    # 是否绘制匹配线属性
    draw_matches = Property(True, name="绘制匹配线",
                            group=PropertyGroupNames.RUN_PARAMETERS,
                            description="是否在输出图像上绘制匹配连线")

    # ── 结果参数（只读）──
    # 匹配数量属性（总匹配数）
    match_count = Property(0, name="匹配数量",
                           group=PropertyGroupNames.RESULT_PARAMETERS,
                           readonly=True)

    # 优秀匹配数属性（经过Lowe's ratio test过滤后的匹配数）
    good_match_count = Property(0, name="优秀匹配数",
                               group=PropertyGroupNames.RESULT_PARAMETERS,
                               readonly=True)

    def __init__(self):
        """初始化ORB特征匹配节点"""
        # 调用父类Base64MatchingNodeData的构造函数
        Base64MatchingNodeData.__init__(self)
        # 调用父类OpenCVNodeDataBase的构造函数
        OpenCVNodeDataBase.__init__(self)
        # 设置节点显示名称
        self.name = "ORB特征匹配"

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        """核心处理逻辑

        参数：
            src_image_node_data: 源节点数据
            from_node_data: 上游节点数据
            diagram: 工作流引擎

        返回：
            处理结果
        """
        # 1. 获取输入图像（上游节点输出）
        mat = self.get_input_mat(from_node_data.mat if from_node_data else None)
        # 如果输入图像为空，返回错误结果
        if mat is None:
            return self.error(None, "无输入图像，请连接上游节点")

        # 2. 获取模板图像（Base64MatchingNodeData 提供）
        template = self.get_template_image()
        # 如果模板图像为空
        if template is None:
            return self.error(mat, "未设置模板图片，请在属性面板中设置")

        # 3. 创建 ORB 检测器并提取特征
        orb = cv2.ORB_create(nfeatures=self.n_features)
        # 检测模板图像的特征点和描述子
        kp1, des1 = orb.detectAndCompute(template, None)
        # 检测输入图像的特征点和描述子
        kp2, des2 = orb.detectAndCompute(mat, None)

        # 4. 检查特征点是否足够
        if des1 is None or des2 is None or len(des1) == 0 or len(des2) == 0:
            return self.ok(mat, "无法提取足够特征点")

        # 5. BFMatcher 暴力匹配（使用汉明距离）
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        # 对每个特征点找两个最近邻
        matches = bf.knnMatch(des1, des2, k=2)

        # 6. Lowe's ratio test —— 过滤优秀匹配
        good = [m for m, n in matches if m.distance < self.ratio_threshold * n.distance]

        # 7. 绘制结果
        out = mat.copy()
        # 如果启用绘制匹配线
        if self.draw_matches:
            # 绘制匹配连线
            out = cv2.drawMatches(template, kp1, mat, kp2, good, out,
                                   flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)

        # 保存匹配数量
        self.match_count = len(matches)
        # 保存优秀匹配数量
        self.good_match_count = len(good)

        # 返回成功结果
        return self.ok(out, f"ORB 匹配: {len(good)}/{len(matches)} 个特征点")

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat
"""模板匹配模块 — 分层架构:

  template_base.py     → 基类层: ITemplateMatchingGroupableNode, MatcherType, OpenCVTemplateMatchingNodeBase
  template_matching.py → 模板匹配: TemplateMatchingNode (合并原 Template + BestMatch)
  feature_matching.py  → 特征匹配: SiftFeatureMatchingNode, SurfFeatureMatchingNode
  orb_matching.py      → ORB匹配: OrbFeatureMatchingNode (Homography)
  hsv_blob.py          → HSV色相: HSVBlobMatchingNode
"""

from nodes.template_matchings.template_base import (
    ITemplateMatchingGroupableNode,
    MatcherType,
    OpenCVTemplateMatchingNodeBase,
)
from nodes.template_matchings.template_matching import (
    TemplateMatchingNode,
    TemplateBase64MatchingNode,           # 兼容别名
    BestMatchBase64TemplateMatchingNode,  # 兼容别名
)
from nodes.template_matchings.feature_matching import (
    SiftFeatureMatchingNode,
    SurfFeatureMatchingNode,
    SiftBase64FeatureMatchingNode,   # 兼容别名
    SurfBase64FeatureMatchingNode,   # 兼容别名
)
from nodes.template_matchings.orb_matching import (
    OrbFeatureMatchingNode,
)
from nodes.template_matchings.hsv_blob import (
    HSVBlobMatchingNode,
    HSVInRangeRenderBlobMatchingNode,  # 兼容别名
)

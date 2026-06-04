"""
插件模块 - 动态扩展节点功能

使用说明：
1. 将自定义节点类放在 plugins/ 目录下
2. 节点类必须继承 core.node_base.NodeBase
3. 程序启动时会自动扫描并加载此目录下的所有节点
4. 插件节点会显示在节点工具箱中，与内置节点相同

示例插件：
- example_plugin.py: 包含多个示例节点，展示如何创建自定义插件
"""

# 导出示例插件中的节点类（可选，用于代码中直接导入）
try:
    from .example_plugin import (
        SharpenNode,
        RotateNode,
        FlipNode,
        SplitChannelsNode,
        HistogramEqualizeNode
    )
except ImportError:
    # 如果example_plugin.py不存在或导入失败，跳过
    pass

__all__ = [
    # 示例插件节点
    'SharpenNode',
    'RotateNode',
    'FlipNode',
    'SplitChannelsNode',
    'HistogramEqualizeNode'
]
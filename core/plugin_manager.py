"""插件管理器 - 动态发现和加载节点模块。"""

import importlib
import inspect
import os
import pkgutil

from core.node_base import NodeBase
from core.node_group import node_data_group_manager, NodeGroup
from core.registry import node_registry


class PluginManager:
    """发现并加载 nodes/ 包中的节点实现。

    每个节点模块通过继承 NodeBase 并定义 __group__ 类属性来注册自身。
    """

    def __init__(self):
        # 已加载的模块名称列表
        self._loaded_modules: list[str] = []

    def discover_nodes_package(self, package_path: str = "nodes"):
        """发现 nodes/ 包中的所有节点模块。

        扫描子目录并导入所有 .py 文件。
        每个模块应包含定义了 __group__ 的 NodeBase 子类。
        """
        try:
            # 导入节点包
            package = importlib.import_module(package_path)
            # 获取包的目录路径
            package_dir = os.path.dirname(package.__file__)

            # 遍历包目录下的所有模块
            for _, module_name, is_pkg in pkgutil.iter_modules([package_dir]):
                full_name = f"{package_path}.{module_name}"
                try:
                    if is_pkg:
                        # 如果是子包，递归发现
                        self._discover_subpackage(full_name)
                    else:
                        # 如果是模块，直接加载
                        self._load_module(full_name)
                except Exception as e:
                    import logging
                    logging.warning(f"加载节点模块 {full_name} 失败: {e}")

        except ModuleNotFoundError:
            pass  # nodes 包尚未创建

    def _discover_subpackage(self, package_path: str):
        """发现子包中的节点（例如 nodes.preprocessings）。"""
        try:
            # 导入子包
            package = importlib.import_module(package_path)
            # 获取子包目录路径
            package_dir = os.path.dirname(package.__file__)

            # 遍历子包目录下的所有模块
            for _, module_name, is_pkg in pkgutil.iter_modules([package_dir]):
                full_name = f"{package_path}.{module_name}"
                # 只加载模块，不递归子包
                if not is_pkg:
                    self._load_module(full_name)
        except Exception as e:
            import logging
            logging.warning(f"发现子包 {package_path} 失败: {e}")

    def _load_module(self, module_name: str):
        """加载单个模块并注册其节点类。"""
        # 避免重复加载
        if module_name in self._loaded_modules:
            return
        import logging
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logging.warning(f"导入模块 {module_name} 失败: {e}")
            return

        self._loaded_modules.append(module_name)
        try:
            self._register_module_classes(module)
        except Exception as e:
            # 注册失败时清理已注册内容，避免部分注册导致不一致状态
            logging.warning(f"注册模块 {module_name} 的节点类时失败: {e}")
            self._unregister_module_classes(module)
            self._loaded_modules.remove(module_name)
            raise

    def _register_module_classes(self, module):
        """注册模块中找到的所有 NodeBase 子类。"""
        # 遍历模块中的所有类
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # 跳过私有类
            if name.startswith("_"):
                continue
            # 只处理 NodeBase 的子类，且不是 NodeBase 本身
            if not issubclass(obj, NodeBase) or obj is NodeBase:
                continue
            # 跳过抽象类
            if getattr(obj, '__abstract__', False) or inspect.isabstract(obj):
                continue

            # 获取节点所属的分组名称
            group_name = getattr(obj, '__group__', None)
            if group_name:
                # 在节点分组管理器中注册
                node_data_group_manager.register_node(obj, group_name)

            # 获取节点类别
            category = getattr(obj, '__category__', None) or group_name or ""
            # 在节点注册表中注册
            node_registry.register(obj, category)

    def _unregister_module_classes(self, module):
        """移除模块中所有已注册的 NodeBase 子类（用于失败回滚）。"""
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name.startswith("_") or not issubclass(obj, NodeBase) or obj is NodeBase:
                continue
            # 从节点注册表中移除
            node_registry.unregister(obj.__name__)
            # 从分组管理器中移除
            group_name = getattr(obj, '__group__', None)
            if group_name:
                group = node_data_group_manager.get_group(group_name)
                if group:
                    group.unregister(obj)

    def load_from_path(self, path: str):
        """从单个 Python 文件加载节点模块。"""
        import importlib.util
        # 从文件路径提取模块名称
        module_name = os.path.splitext(os.path.basename(path))[0]
        # 创建模块加载规格
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec and spec.loader:
            # 加载模块
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # 注册模块中的节点类
            self._register_module_classes(module)

    def get_node_info(self) -> list[dict]:
        """获取所有已发现的节点信息，用于工具箱UI。"""
        info = []
        # 遍历所有分组
        for group in node_data_group_manager.get_all_groups():
            # 遍历分组中的所有节点类型
            for node_type in group.node_types:
                info.append({
                    "type": node_type.__name__,  # 节点类型名称
                    "name": getattr(node_type, 'display_name', node_type.__name__),  # 显示名称
                    "group": group.name,  # 所属分组
                    "description": group.description,  # 描述
                    "icon": group.icon,  # 图标
                    "order": getattr(node_type, 'order', group.order),  # 排序顺序
                })
        # 按order排序后返回
        return sorted(info, key=lambda x: x["order"])


# 全局实例
plugin_manager = PluginManager()
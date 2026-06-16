"""插件管理器 - 动态发现和加载节点模块。"""

import importlib
import inspect
import logging
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

        except ModuleNotFoundError as e:
            if e.name == package_path:
                pass  # nodes 包尚未创建
            else:
                logging.warning(f"节点包 {package_path} 存在但缺少依赖: {e}")

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
            logging.warning(f"发现子包 {package_path} 失败: {e}")

    def _load_module(self, module_name: str):
        """加载单个模块并注册其节点类。"""
        if module_name in self._loaded_modules:
            return
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logging.warning(f"导入模块 {module_name} 失败: {e}")
            return

        # 先收集所有可注册的类，验证后一次性注册
        classes_to_register: list[tuple[type, str, str]] = []
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name.startswith("_"):
                continue
            if not issubclass(obj, NodeBase) or obj is NodeBase:
                continue
            if getattr(obj, '__abstract__', False) or inspect.isabstract(obj):
                continue
            group_name = getattr(obj, '__group__', None)
            category = getattr(obj, '__category__', None) or group_name or ""
            classes_to_register.append((obj, group_name or "", category))

        self._loaded_modules.append(module_name)
        for node_cls, group_name, category in classes_to_register:
            if group_name:
                node_data_group_manager.register_node(node_cls, group_name)
            node_registry.register(node_cls, category)

    def _register_module_classes(self, module):
        """注册模块中找到的所有 NodeBase 子类（用于 load_from_path 路径）。

        注意：discover_nodes_package 路径已改为批量收集后注册，不再使用此方法。
        """
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name.startswith("_"):
                continue
            if not issubclass(obj, NodeBase) or obj is NodeBase:
                continue
            if getattr(obj, '__abstract__', False) or inspect.isabstract(obj):
                continue
            group_name = getattr(obj, '__group__', None)
            if group_name:
                node_data_group_manager.register_node(obj, group_name)
            category = getattr(obj, '__category__', None) or group_name or ""
            node_registry.register(obj, category)

    def _unregister_module_classes(self, module):
        """移除模块中所有已注册的 NodeBase 子类（用于 load_from_path 失败回滚）。"""
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name.startswith("_") or not issubclass(obj, NodeBase) or obj is NodeBase:
                continue
            node_registry.unregister(obj.__name__)
            group_name = getattr(obj, '__group__', None)
            if group_name:
                group = node_data_group_manager.get_group(group_name)
                if group:
                    group.unregister(obj)

    def load_from_path(self, path: str):
        """从单个 Python 文件加载节点模块。

        注意：不将文件目录加入 sys.path，使用相对导入的模块会失败。
        推荐让节点模块仅使用绝对导入（from core.node_base import ...）。
        """
        import importlib.util
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
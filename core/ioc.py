"""
最小化 IoC 容器
支持单例和瞬态注册，支持自动构造函数注入。
"""

import inspect
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

# 创建类型变量 T，用于泛型（未实际使用，但为类型注解保留）
T = TypeVar("T")

_BUILTIN_MODULES = frozenset({"builtins", "typing", "abc", "enum"})


def _is_builtin_type(t: type) -> bool:
    """检查类型是否为内置/标准库类型（无需注册到 IoC 容器）。"""
    mod = getattr(t, '__module__', '')
    return mod in _BUILTIN_MODULES


# 定义服务描述符类，用于描述单个服务注册信息
class ServiceDescriptor:
    """描述单个服务注册信息"""

    # 定义构造函数
    def __init__(self, service_type: type, implementation_type: type = None,
                 instance: Any = None, factory: Callable = None,
                 singleton: bool = False):
        # 参数 service_type：服务类型（接口或抽象类）
        self.service_type = service_type
        # 参数 implementation_type：实现类型，未指定时与服务类型相同
        self.implementation_type = implementation_type or service_type
        # 参数 instance：预构建的实例
        self.instance = instance
        # 参数 factory：工厂函数
        self.factory = factory
        # 参数 singleton：是否为单例
        self.singleton = singleton


# 定义服务集合类，用于收集服务注册信息
class ServiceCollection:
    """收集服务注册信息，用于构建 ServiceProvider"""

    # 定义构造函数
    def __init__(self):
        # 初始化注册描述符列表，存储 ServiceDescriptor 对象
        self._descriptors: list[ServiceDescriptor] = []

    # 定义注册单例服务的方法
    def add_singleton(self, service_type: type, implementation_type: type = None,
                      instance: Any = None, factory: Callable = None):
        """注册一个单例服务（全局唯一实例）"""
        # 创建 ServiceDescriptor 对象，singleton 设为 True
        self._descriptors.append(ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            instance=instance,
            factory=factory,
            singleton=True,
        ))
        # 返回 self，支持链式调用
        return self

    # 定义注册瞬态服务的方法
    def add_transient(self, service_type: type, implementation_type: type = None,
                      factory: Callable = None):
        """注册一个瞬态服务（每次解析都创建新实例）"""
        # 创建 ServiceDescriptor 对象，singleton 设为 False
        self._descriptors.append(ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            singleton=False,
        ))
        # 返回 self，支持链式调用
        return self

    # 定义构建服务提供者的方法
    def build(self) -> "ServiceProvider":
        """根据注册的描述符构建 ServiceProvider"""
        # 用描述符列表构建 ServiceProvider 并返回
        return ServiceProvider(self._descriptors)


# 定义服务提供者类，用于解析服务
class ServiceProvider:
    """服务解析器，递归注入依赖项"""

    # 定义构造函数
    def __init__(self, descriptors: list[ServiceDescriptor]):
        # 保存服务注册描述符列表
        self._descriptors = descriptors
        # 构建类型到描述符的快速查找映射
        self._descriptor_map: dict[type, ServiceDescriptor] = {
            d.service_type: d for d in descriptors
        }
        # 初始化单例实例缓存，键为服务类型，值为实例
        self._singletons: dict[type, Any] = {}

    # 定义根据类型解析服务的方法
    def resolve(self, service_type: type) -> Any:
        """根据类型解析服务"""
        # 检查是否已有缓存的单例实例
        if service_type in self._singletons:
            # 如果有，直接返回缓存的实例
            return self._singletons[service_type]

        # 查找服务注册描述符
        descriptor = self._find_descriptor(service_type)
        # 如果找不到描述符
        if descriptor is None:
            # 抛出 KeyError 异常
            raise KeyError(f"服务未注册: {service_type.__name__}")

        # 创建实例并返回
        return self._create_instance(descriptor)

    # 定义查找描述符的方法
    def _find_descriptor(self, service_type: type) -> ServiceDescriptor | None:
        """查找服务类型对应的注册描述符（O(1) dict 查找）"""
        return self._descriptor_map.get(service_type)

    # 定义根据描述符创建实例的方法
    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """根据描述符创建服务实例"""
        # 情况1：使用预构建的实例
        if descriptor.instance is not None:
            # 如果是单例
            if descriptor.singleton:
                # 缓存实例到单例字典
                self._singletons[descriptor.service_type] = descriptor.instance
            # 返回预构建的实例
            return descriptor.instance

        # 情况2：使用工厂函数
        if descriptor.factory is not None:
            # 调用工厂函数，传入当前服务提供者作为参数
            instance = descriptor.factory(self)
            # 如果是单例
            if descriptor.singleton:
                # 缓存实例到单例字典
                self._singletons[descriptor.service_type] = instance
            # 返回工厂函数创建的实例
            return instance

        # 情况3：构造函数注入
        # 获取实现类型
        impl_type = descriptor.implementation_type
        # 解析构造函数参数
        params = self._resolve_constructor_params(impl_type)
        # 实例化对象
        instance = impl_type(**params)
        # 如果是单例
        if descriptor.singleton:
            # 缓存实例到单例字典
            self._singletons[descriptor.service_type] = instance
        # 返回新创建的实例
        return instance

    # 定义解析构造函数参数的方法
    def _resolve_constructor_params(self, impl_type: type) -> dict:
        """从已注册的服务中解析构造函数参数"""
        # 获取构造函数的签名
        try:
            sig = inspect.signature(impl_type.__init__)
        except (ValueError, TypeError):
            # 如果获取失败，返回空字典
            return {}

        # 初始化参数字典
        resolved = {}
        # 遍历构造函数的参数
        for name, param in sig.parameters.items():
            # 跳过 self 参数
            if name == "self":
                continue
            # 如果参数有类型注解
            if param.annotation != inspect.Parameter.empty:
                try:
                    # 从容器中解析该类型
                    resolved[name] = self.resolve(param.annotation)
                except KeyError:
                    # 解析失败则使用默认值（如果存在）
                    if param.default != inspect.Parameter.empty:
                        # 仅对非内置类型发出警告（str、int 等不需要注册）
                        if not _is_builtin_type(param.annotation):
                            logger.warning(
                                "无法解析类型 %s 用于 %s.%s 的参数 '%s'，使用默认值",
                                getattr(param.annotation, '__name__', param.annotation),
                                impl_type.__name__, name, name,
                            )
                        resolved[name] = param.default
            # 如果参数有默认值（无类型注解或类型注解解析失败）
            elif param.default != inspect.Parameter.empty:
                # 使用默认值
                resolved[name] = param.default
        # 返回解析后的参数字典
        return resolved


# 创建全局服务集合实例
# 注意：此实例在 services/app_context.py 的 init_defaults() 中通过同步机制
# 与 AppContext 保持一致。新代码应通过 app_context.service_collection 访问。
service_collection = ServiceCollection()
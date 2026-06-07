"""Minimal IoC container

Supports singleton and transient registrations with automatic constructor injection.
"""

from typing import Any, Callable, TypeVar
import inspect

T = TypeVar("T")


class ServiceDescriptor:
    """Describes a single service registration."""

    def __init__(self, service_type: type, implementation_type: type = None,
                 instance: Any = None, factory: Callable = None,
                 singleton: bool = False):
        self.service_type = service_type
        self.implementation_type = implementation_type or service_type
        self.instance = instance
        self.factory = factory
        self.singleton = singleton


class ServiceCollection:
    """Collects service registrations, then builds a ServiceProvider."""

    def __init__(self):
        self._descriptors: list[ServiceDescriptor] = []

    def add_singleton(self, service_type: type, implementation_type: type = None,
                      instance: Any = None, factory: Callable = None):
        """Register a singleton service."""
        self._descriptors.append(ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            instance=instance,
            factory=factory,
            singleton=True,
        ))
        return self

    def add_transient(self, service_type: type, implementation_type: type = None,
                      factory: Callable = None):
        """Register a transient service (new instance each resolve)."""
        self._descriptors.append(ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            singleton=False,
        ))
        return self

    def build(self) -> "ServiceProvider":
        """Build a ServiceProvider from the registered descriptors."""
        return ServiceProvider(self._descriptors)


class ServiceProvider:
    """Resolves services, injecting dependencies recursively."""

    def __init__(self, descriptors: list[ServiceDescriptor]):
        self._descriptors = descriptors
        self._singletons: dict[type, Any] = {}

    def resolve(self, service_type: type) -> Any:
        """Resolve a service by type."""
        # Check for pre-built singleton
        if service_type in self._singletons:
            return self._singletons[service_type]

        descriptor = self._find_descriptor(service_type)
        if descriptor is None:
            raise KeyError(f"Service not registered: {service_type.__name__}")

        return self._create_instance(descriptor)

    def _find_descriptor(self, service_type: type) -> ServiceDescriptor | None:
        for d in self._descriptors:
            if d.service_type == service_type:
                return d
        return None

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        # Pre-built instance
        if descriptor.instance is not None:
            if descriptor.singleton:
                self._singletons[descriptor.service_type] = descriptor.instance
            return descriptor.instance

        # Factory function
        if descriptor.factory is not None:
            instance = descriptor.factory(self)
            if descriptor.singleton:
                self._singletons[descriptor.service_type] = instance
            return instance

        # Constructor injection
        impl_type = descriptor.implementation_type
        params = self._resolve_constructor_params(impl_type)
        instance = impl_type(**params)
        if descriptor.singleton:
            self._singletons[descriptor.service_type] = instance
        return instance

    def _resolve_constructor_params(self, impl_type: type) -> dict:
        """Resolve constructor parameters from registered services."""
        try:
            sig = inspect.signature(impl_type.__init__)
        except (ValueError, TypeError):
            return {}

        resolved = {}
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.annotation != inspect.Parameter.empty:
                try:
                    resolved[name] = self.resolve(param.annotation)
                except KeyError:
                    if param.default != inspect.Parameter.empty:
                        resolved[name] = param.default
            elif param.default != inspect.Parameter.empty:
                resolved[name] = param.default
        return resolved


# Global service collection (replaces IocProject.Instance pattern)
service_collection = ServiceCollection()

from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from fastapi import Request


Handler = Callable[[Request], Any | Awaitable[Any]]


class MigrationRegistry:
    def __init__(self, module_enabled: Callable[[str], bool] | None = None) -> None:
        self._handlers: dict[tuple[str, str, str], Handler] = {}
        self._modules: dict[tuple[str, str, str], str | None] = {}
        self._module_enabled = module_enabled or (lambda module: True)

    def register(
        self,
        controller: str,
        action: str,
        methods: Iterable[str],
        handler: Handler,
        module: str | None = None,
    ) -> None:
        for method in methods:
            key = (controller, action, method.upper())
            self._handlers[key] = handler
            self._modules[key] = module

    def resolve(self, controller: str, action: str, method: str) -> Handler | None:
        key = (controller, action, method.upper())
        handler = self._handlers.get(key)
        module = self._modules.get(key)
        if handler is None or (module is not None and not self._module_enabled(module)):
            return None
        return handler

    def routes(self) -> list[dict[str, str]]:
        return [
            {
                "controller": controller,
                "action": action,
                "method": method,
                **(
                    {"module": self._modules[(controller, action, method)]}
                    if self._modules[(controller, action, method)] is not None
                    else {}
                ),
            }
            for controller, action, method in sorted(self._handlers)
        ]

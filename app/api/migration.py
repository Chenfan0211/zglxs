from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from fastapi import Request


Handler = Callable[[Request], Any | Awaitable[Any]]


class MigrationRegistry:
    def __init__(self) -> None:
        self._handlers: dict[tuple[str, str, str], Handler] = {}

    def register(
        self,
        controller: str,
        action: str,
        methods: Iterable[str],
        handler: Handler,
    ) -> None:
        for method in methods:
            self._handlers[(controller, action, method.upper())] = handler

    def resolve(self, controller: str, action: str, method: str) -> Handler | None:
        return self._handlers.get((controller, action, method.upper()))

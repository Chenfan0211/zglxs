from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from fastapi import Depends, HTTPException, Request


@dataclass(frozen=True)
class AuthContext:
    user_id: int
    role_ids: frozenset[str]
    permissions: frozenset[str]
    department_ids: frozenset[int]


@runtime_checkable
class TokenValidator(Protocol):
    async def validate(self, token: str) -> AuthContext | None: ...


class RequestAuth:
    def __init__(self, validator: TokenValidator):
        self._validator = validator

    async def __call__(self, request: Request) -> AuthContext:
        token = _get_bearer_token(request) or request.cookies.get("access_token")
        if not token:
            raise _authentication_error()
        context = await self._validator.validate(token)
        if context is None:
            raise _authentication_error()
        return context


def require_permission(
    permission: str,
    auth_dependency: Callable[..., AuthContext] | None = None,
):
    async def dependency(
        context: AuthContext = Depends(auth_dependency),
    ) -> AuthContext:
        if permission not in context.permissions:
            raise HTTPException(status_code=403, detail="permission denied")
        return context

    return dependency


def _get_bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _authentication_error() -> HTTPException:
    return HTTPException(status_code=401, detail="authentication required")

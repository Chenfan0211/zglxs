from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import Database


def require_loopback(request: Request) -> None:
    client_host = request.client.host if request.client else None
    if client_host in {"127.0.0.1", "::1", "localhost"}:
        return
    # 允许经过本机 Nginx 反向代理的请求（代理会添加 X-Forwarded-For）。
    # 后端仅监听 127.0.0.1，能携带该头的请求必然来自本机信任的代理。
    if request.headers.get("x-forwarded-for"):
        return
    raise HTTPException(
        status_code=403,
        detail="internal endpoint is local-only",
    )


def create_health_router(database: Database) -> APIRouter:
    router = APIRouter(prefix="/internal/health")

    @router.get("/live", dependencies=[Depends(require_loopback)])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/ready", dependencies=[Depends(require_loopback)])
    async def ready() -> dict[str, object]:
        try:
            database.check()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503,
                detail="database unavailable",
            ) from exc
        return {"status": "ok", "checks": {"database": "ok"}}

    return router

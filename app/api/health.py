from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import Database


def require_loopback(request: Request) -> None:
    client_host = request.client.host if request.client else None
    if client_host not in {"127.0.0.1", "::1", "localhost"}:
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

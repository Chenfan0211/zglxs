from typing import Any

from pydantic import BaseModel
from fastapi.responses import JSONResponse


class ApiEnvelope(BaseModel):
    code: int
    msg: str
    data: Any = None


def success(data: Any = None, msg: str = "success") -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=ApiEnvelope(code=1, msg=msg, data=data).model_dump(),
    )


def failure(
    msg: str,
    code: int = 0,
    status_code: int = 400,
    data: Any = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ApiEnvelope(code=code, msg=msg, data=data).model_dump(),
    )

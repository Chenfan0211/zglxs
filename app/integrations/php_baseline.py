import httpx
from fastapi import HTTPException, Request, Response


_HOP_BY_HOP_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


class PhpBaselineProxy:
    def __init__(
        self,
        base_url: str,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    async def forward(self, request: Request, controller: str, action: str) -> Response:
        target = f"{self._base_url}/apiv1/{controller}/{action}"
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in _HOP_BY_HOP_HEADERS
        }
        body = await request.body()

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                upstream = await client.request(
                    request.method,
                    target,
                    params=request.query_params,
                    headers=headers,
                    content=body,
                )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail="PHP baseline unavailable",
            ) from exc

        forwarded_headers = [
            (key.encode("latin-1"), value.encode("latin-1"))
            for key, value in upstream.headers.multi_items()
            if key.lower() not in _HOP_BY_HOP_HEADERS
        ]
        forwarded_headers.append(
            (b"content-length", str(len(upstream.content)).encode("ascii"))
        )
        response = Response(
            content=upstream.content,
            status_code=upstream.status_code,
        )
        response.raw_headers = forwarded_headers
        return response

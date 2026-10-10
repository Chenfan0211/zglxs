from __future__ import annotations


class LaikeProviderError(RuntimeError):
    """A provider response or transport failure that is safe to expose internally."""

    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


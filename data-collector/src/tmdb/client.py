import asyncio
from collections.abc import Mapping
from typing import Any

import httpx
from tenacity import AsyncRetrying
from tenacity import RetryError
from tenacity import retry_if_exception_type
from tenacity import stop_after_attempt
from tenacity.wait import wait_base
from tenacity.wait import wait_exponential

from src.tmdb.config import API_CONCURRENCY


class InvalidAPIKeyError(Exception):
    pass


class MovieNotFoundError(Exception):
    pass


class TMDBRequestError(Exception):
    pass


class TMDBRetryableError(TMDBRequestError):
    def __init__(self, *, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class RetryAfterOrExponentialWait(wait_base):
    def __init__(self) -> None:
        self.exponential_wait = wait_exponential(
            min=1,
            max=30,
        )

    def __call__(self, retry_state: Any) -> float:
        if retry_state.outcome is None:
            return self.exponential_wait(retry_state)

        exception = retry_state.outcome.exception()
        if isinstance(exception, TMDBRetryableError) and exception.retry_after_seconds is not None:
            return min(exception.retry_after_seconds, 30)

        return self.exponential_wait(retry_state)


class TMDBClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.themoviedb.org/3",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._semaphore = asyncio.Semaphore(API_CONCURRENCY)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

    async def __aenter__(self) -> "TMDBClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_movie(self, tmdb_id: int) -> dict[str, Any]:
        return await self.request_json(method="GET", path=f"/movie/{tmdb_id}")

    async def request_json(
        self,
        *,
        method: str,
        path: str,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(TMDBRetryableError),
                stop=stop_after_attempt(3),
                wait=RetryAfterOrExponentialWait(),
                reraise=True,
            ):
                with attempt:
                    return await self._send_request(method=method, path=path, params=params)
        except RetryError as error:
            cause = error.last_attempt.exception()
            if cause is None:
                raise TMDBRequestError(
                    "TMDB request failed without a concrete error") from error
            raise cause

    async def _send_request(
        self,
        *,
        method: str,
        path: str,
        params: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        async with self._semaphore:
            response = await self._client.request(method=method, url=path, params=params)

        if response.status_code == 401:
            raise InvalidAPIKeyError("TMDB API key is invalid")

        if response.status_code == 404:
            raise MovieNotFoundError(f"TMDB movie was not found: {path}")

        if response.status_code in {429, 500, 502, 503, 504}:
            raise TMDBRetryableError(
                message=f"TMDB request failed with status {response.status_code}",
                retry_after_seconds=parse_retry_after_seconds(
                    response.headers.get("Retry-After")),
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise TMDBRequestError(
                f"TMDB request failed with status {response.status_code}") from error

        return response.json()


def parse_retry_after_seconds(retry_after: str | None) -> float | None:
    if retry_after is None:
        return None

    try:
        retry_after_seconds = float(retry_after)
    except ValueError:
        return None

    if retry_after_seconds < 0:
        return None

    return retry_after_seconds

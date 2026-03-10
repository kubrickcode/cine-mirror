import asyncio

import httpx
import pytest
from pytest import MonkeyPatch

from src.tmdb.client import InvalidAPIKeyError
from src.tmdb.client import MovieNotFoundError
from src.tmdb.client import TMDBClient


class TestTMDBClient:
    def test_should_retry_with_retry_after_when_tmdb_returns_429(
        self,
        monkeypatch: MonkeyPatch,
    ) -> None:
        recorded_sleeps: list[float] = []
        request_count = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            if request_count == 1:
                return httpx.Response(
                    status_code=429,
                    headers={"Retry-After": "3"},
                    json={"status_message": "Too many requests"},
                )

            return httpx.Response(status_code=200, json={"id": 238, "title": "The Godfather"})

        async def sleep_stub(delay: float) -> None:
            recorded_sleeps.append(delay)

        monkeypatch.setattr(asyncio, "sleep", sleep_stub)

        client = create_tmdb_client(handler=handler)

        response = run_async(client.get_movie(238))

        run_async(client.aclose())

        assert response["title"] == "The Godfather"
        assert recorded_sleeps == [3.0]
        assert request_count == 2

    def test_should_fall_back_to_exponential_wait_when_retry_after_is_invalid(
        self,
        monkeypatch: MonkeyPatch,
    ) -> None:
        recorded_sleeps: list[float] = []
        request_count = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            if request_count == 1:
                return httpx.Response(
                    status_code=429,
                    headers={"Retry-After": "not-a-number"},
                    json={"status_message": "Too many requests"},
                )

            return httpx.Response(status_code=200, json={"id": 238, "title": "The Godfather"})

        async def sleep_stub(delay: float) -> None:
            recorded_sleeps.append(delay)

        monkeypatch.setattr(asyncio, "sleep", sleep_stub)

        client = create_tmdb_client(handler=handler)

        response = run_async(client.get_movie(238))

        run_async(client.aclose())

        assert response["title"] == "The Godfather"
        assert recorded_sleeps == [1.0]
        assert request_count == 2

    def test_should_retry_on_503_and_return_success(self, monkeypatch: MonkeyPatch) -> None:
        recorded_sleeps: list[float] = []
        request_count = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            if request_count == 1:
                return httpx.Response(status_code=503, json={"status_message": "Service Unavailable"})

            return httpx.Response(status_code=200, json={"id": 238, "title": "The Godfather"})

        async def sleep_stub(delay: float) -> None:
            recorded_sleeps.append(delay)

        monkeypatch.setattr(asyncio, "sleep", sleep_stub)

        client = create_tmdb_client(handler=handler)

        response = run_async(client.get_movie(238))

        run_async(client.aclose())

        assert response["title"] == "The Godfather"
        assert recorded_sleeps == [1.0]
        assert request_count == 2

    def test_should_cap_concurrency_to_four_requests(self) -> None:
        state = ConcurrencyState()
        client = create_tmdb_client(handler=state.respond)

        async def scenario() -> None:
            request_task = asyncio.gather(*(client.get_movie(movie_id) for movie_id in range(1, 6)))

            await asyncio.wait_for(state.first_wave_entered.wait(), timeout=1)
            assert state.max_in_flight == 4

            state.release_responses.set()
            await asyncio.wait_for(request_task, timeout=1)

        run_async(scenario())
        run_async(client.aclose())

        assert state.max_in_flight == 4
        assert state.completed_count == 5

    def test_should_raise_invalid_api_key_without_retry(self) -> None:
        request_count = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            return httpx.Response(status_code=401, json={"status_message": "Invalid API key"})

        client = create_tmdb_client(handler=handler, access_token="bad-token")

        with pytest.raises(InvalidAPIKeyError):
            run_async(client.get_movie(238))

        run_async(client.aclose())

        assert request_count == 1

    def test_should_raise_movie_not_found_without_retry(self) -> None:
        request_count = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal request_count
            request_count += 1
            return httpx.Response(status_code=404, json={"status_message": "Not Found"})

        client = create_tmdb_client(handler=handler)

        with pytest.raises(MovieNotFoundError):
            run_async(client.get_movie(0))

        run_async(client.aclose())

        assert request_count == 1


class ConcurrencyState:
    def __init__(self) -> None:
        self.completed_count = 0
        self.first_wave_entered = asyncio.Event()
        self.in_flight = 0
        self.lock = asyncio.Lock()
        self.max_in_flight = 0
        self.release_responses = asyncio.Event()

    async def respond(self, request: httpx.Request) -> httpx.Response:
        async with self.lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            if self.in_flight == 4:
                self.first_wave_entered.set()

        await self.release_responses.wait()

        async with self.lock:
            self.in_flight -= 1
            self.completed_count += 1

        movie_id = int(request.url.path.rsplit("/", maxsplit=1)[-1])
        return httpx.Response(status_code=200, json={"id": movie_id, "title": f"Movie {movie_id}"})


def create_tmdb_client(
    *,
    handler: httpx.AsyncBaseTransport | object,
    access_token: str = "test-token",
) -> TMDBClient:
    return TMDBClient(
        access_token=access_token,
        client=httpx.AsyncClient(
            base_url="https://example.test/3",
            headers={"Authorization": f"Bearer {access_token}"},
            transport=httpx.MockTransport(handler),
        ),
    )


def run_async(coroutine: object) -> object:
    return asyncio.run(coroutine)

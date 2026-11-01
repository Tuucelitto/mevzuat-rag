"""Tests for the Gemini retry rules; no request leaves the machine."""
import pytest
from google.genai import errors

from mevzuat_rag import embedding
from mevzuat_rag.embedding import MAX_ATTEMPTS, call_with_retries

MINUTE_QUOTA = {"error": {"code": 429, "message": "per minute limit"}}
DAILY_QUOTA = {
    "error": {"code": 429, "details": [{"quotaId": "EmbedContentRequestsPerDayPerProject"}]}
}


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []
    monkeypatch.setattr(embedding.time, "sleep", recorded.append)
    return recorded


def failing_call(code: int, body: dict) -> tuple[list[int], object]:
    calls: list[int] = []

    def request() -> None:
        calls.append(1)
        raise errors.APIError(code, body)

    return calls, request


def test_daily_quota_error_fails_without_waiting(sleeps: list[float]) -> None:
    calls, request = failing_call(429, DAILY_QUOTA)
    with pytest.raises(errors.APIError):
        call_with_retries(request)
    assert len(calls) == 1
    assert sleeps == []


def test_minute_quota_error_is_retried(sleeps: list[float]) -> None:
    calls, request = failing_call(429, MINUTE_QUOTA)
    with pytest.raises(errors.APIError):
        call_with_retries(request)
    assert len(calls) == MAX_ATTEMPTS
    assert len(sleeps) == MAX_ATTEMPTS - 1


def test_successful_retry_returns_value(sleeps: list[float]) -> None:
    attempts: list[int] = []

    def request() -> str:
        attempts.append(1)
        if len(attempts) == 1:
            raise errors.APIError(503, {"error": {"code": 503, "message": "busy"}})
        return "ok"

    assert call_with_retries(request) == "ok"
    assert len(sleeps) == 1

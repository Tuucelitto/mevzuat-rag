"""Tests for the HTTP API; Gemini is replaced by fake answerers, so no quota is used."""
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from google.genai import errors

from mevzuat_rag.answer import UNKNOWN_ANSWER, Answer
from mevzuat_rag.api import (
    DAY,
    MAX_QUESTION_LENGTH,
    MINUTE,
    TOTAL_DAILY_LIMIT,
    RateLimiter,
    app,
    get_answerer,
    get_rate_limiter,
)
from mevzuat_rag.download import SOURCE_URLS

KNOWN_ANSWER = Answer(
    text="Sekiz haftadır.",
    unanswered_parts="",
    citations=["4857 sayılı İş Kanunu, Madde 17", "1475 sayılı İş Kanunu, Madde 14"],
    cited_ids=["4857-17", "1475-14"],
    retrieved_ids=["4857-17", "1475-14"],
    answerable=True,
)
UNKNOWN = Answer(UNKNOWN_ANSWER, "", [], [], ["4857-1"], answerable=False)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def use_answerer(answerer: Callable[[str], Answer]) -> None:
    app.dependency_overrides[get_answerer] = lambda: answerer


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(clock: FakeClock) -> Iterator[TestClient]:
    limiter = RateLimiter(clock)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    use_answerer(lambda question: KNOWN_ANSWER)
    yield TestClient(app)
    app.dependency_overrides.clear()


def api_error(code: int) -> errors.APIError:
    return errors.APIError(code, {"error": {"code": code, "message": "fake"}})


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ask_returns_answer_and_official_sources_for_each_law(client: TestClient) -> None:
    response = client.post("/api/ask", json={"question": "İhbar süresi ne kadar?"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Sekiz haftadır."
    assert body["answerable"] is True
    assert body["sources"] == [
        {"citation": KNOWN_ANSWER.citations[0], "url": SOURCE_URLS["4857"]},
        {"citation": KNOWN_ANSWER.citations[1], "url": SOURCE_URLS["1475"]},
    ]


def test_ask_returns_unknown_answer_without_sources(client: TestClient) -> None:
    use_answerer(lambda question: UNKNOWN)
    body = client.post("/api/ask", json={"question": "Başkent neresi?"}).json()
    assert body["answer"] == UNKNOWN_ANSWER
    assert body["answerable"] is False
    assert body["sources"] == []


def test_ask_trims_question_before_answering(client: TestClient) -> None:
    received: list[str] = []

    def record(question: str) -> Answer:
        received.append(question)
        return KNOWN_ANSWER

    use_answerer(record)
    client.post("/api/ask", json={"question": "  soru  "})
    assert received == ["soru"]


@pytest.mark.parametrize("question", ["", "   ", "x" * (MAX_QUESTION_LENGTH + 1)])
def test_ask_rejects_invalid_question(client: TestClient, question: str) -> None:
    response = client.post("/api/ask", json={"question": question})
    assert response.status_code == 422


def test_ask_accepts_question_at_length_limit(client: TestClient) -> None:
    response = client.post("/api/ask", json={"question": "x" * MAX_QUESTION_LENGTH})
    assert response.status_code == 200


def test_ask_returns_503_when_gemini_quota_is_exhausted(client: TestClient) -> None:
    def fail(question: str) -> Answer:
        raise api_error(429)

    use_answerer(fail)
    response = client.post("/api/ask", json={"question": "soru"})
    assert response.status_code == 503
    assert "kullanım sınırı" in response.json()["detail"]


def test_ask_returns_502_on_other_gemini_errors(client: TestClient) -> None:
    def fail(question: str) -> Answer:
        raise api_error(500)

    use_answerer(fail)
    response = client.post("/api/ask", json={"question": "soru"})
    assert response.status_code == 502


def test_ask_returns_429_after_visitor_minute_limit(client: TestClient) -> None:
    codes = [client.post("/api/ask", json={"question": "soru"}).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]


def test_rejected_question_does_not_reach_gemini(client: TestClient) -> None:
    calls: list[str] = []

    def record(question: str) -> Answer:
        calls.append(question)
        return KNOWN_ANSWER

    use_answerer(record)
    for _ in range(6):
        client.post("/api/ask", json={"question": "soru"})
    assert len(calls) == 5


def test_limiter_allows_visitor_again_after_minute(clock: FakeClock) -> None:
    limiter = RateLimiter(clock)
    assert all(limiter.allow("a") for _ in range(5))
    assert not limiter.allow("a")
    clock.now += MINUTE
    assert limiter.allow("a")


def test_limiter_keeps_visitors_separate(clock: FakeClock) -> None:
    limiter = RateLimiter(clock)
    assert all(limiter.allow("a") for _ in range(5))
    assert limiter.allow("b")


def test_limiter_enforces_visitor_daily_limit_and_resets(clock: FakeClock) -> None:
    limiter = RateLimiter(clock)
    for _ in range(20):
        assert limiter.allow("a")
        clock.now += MINUTE
    assert not limiter.allow("a")
    clock.now += DAY
    assert limiter.allow("a")


def test_limiter_enforces_total_daily_limit(clock: FakeClock) -> None:
    limiter = RateLimiter(clock)
    assert all(limiter.allow(f"visitor-{i}") for i in range(TOTAL_DAILY_LIMIT))
    assert not limiter.allow("new-visitor")

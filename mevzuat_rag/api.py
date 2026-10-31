"""HTTP API for the legislation assistant."""
import os
import threading
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from google.genai import errors
from pydantic import BaseModel, ConfigDict, Field
from qdrant_client import QdrantClient

from mevzuat_rag.answer import Answer, answer_question
from mevzuat_rag.download import SOURCE_URLS
from mevzuat_rag.embedding import get_client
from mevzuat_rag.index import QDRANT_PATH

MAX_QUESTION_LENGTH = 500
MINUTE = 60
DAY = 24 * 60 * 60
# The Gemini free tier allows 500 answers a day, so one visitor must not use them all.
VISITOR_LIMITS = ((5, MINUTE), (20, DAY))
TOTAL_DAILY_LIMIT = 400

load_dotenv()
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

Answerer = Callable[[str], Answer]


class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)


class Source(BaseModel):
    citation: str
    url: str


class AskResponse(BaseModel):
    answer: str
    answerable: bool
    unanswered_parts: str
    sources: list[Source]


class RateLimiter:
    """Count requests in sliding time windows, kept in memory for a single process."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.lock = threading.Lock()
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.total: deque[float] = deque()

    def allow(self, visitor: str) -> bool:
        now = self.clock()
        with self.lock:
            history = self.requests[visitor]
            self._forget_old(history, now - DAY)
            self._forget_old(self.total, now - DAY)
            if len(self.total) >= TOTAL_DAILY_LIMIT:
                return False
            for limit, window in VISITOR_LIMITS:
                if sum(moment > now - window for moment in history) >= limit:
                    return False
            history.append(now)
            self.total.append(now)
            return True

    @staticmethod
    def _forget_old(moments: deque[float], cutoff: float) -> None:
        while moments and moments[0] <= cutoff:
            moments.popleft()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.gemini = get_client()
    app.state.qdrant = QdrantClient(path=str(QDRANT_PATH))
    # Local Qdrant is not built for parallel use, so questions run one at a time.
    app.state.answer_lock = threading.Lock()
    yield
    app.state.qdrant.close()


app = FastAPI(title="Mevzuat Asistanı", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return rate_limiter


def get_answerer(request: Request) -> Answerer:
    state = request.app.state

    def answer(question: str) -> Answer:
        with state.answer_lock:
            return answer_question(state.gemini, state.qdrant, question)

    return answer


def to_sources(result: Answer) -> list[Source]:
    return [
        Source(citation=citation, url=SOURCE_URLS[chunk_id.split("-")[0]])
        for citation, chunk_id in zip(result.citations, result.cited_ids)
    ]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# A plain "def" endpoint runs in a worker thread, so slow Gemini calls do not block
# other requests such as the health check.
@app.post("/api/ask")
def ask(
    body: AskRequest,
    request: Request,
    answerer: Annotated[Answerer, Depends(get_answerer)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> AskResponse:
    visitor = request.client.host if request.client else "unknown"
    if not limiter.allow(visitor):
        raise HTTPException(429, "Çok fazla soru gönderildi. Lütfen daha sonra tekrar deneyin.")

    try:
        result = answerer(body.question)
    except errors.APIError as error:
        if error.code == 429:
            message = "Günlük kullanım sınırına ulaşıldı. Lütfen daha sonra tekrar deneyin."
            raise HTTPException(503, message) from error
        raise HTTPException(502, "Cevap üretilemedi. Lütfen tekrar deneyin.") from error

    return AskResponse(
        answer=result.text,
        answerable=result.answerable,
        unanswered_parts=result.unanswered_parts,
        sources=to_sources(result),
    )

"""Create Gemini embeddings for law articles and user questions."""
import os
import time
from collections.abc import Callable

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMENSIONS = 768
MAX_ATTEMPTS = 6
RETRYABLE_STATUS_CODES = {429, 500, 503}


def get_client() -> genai.Client:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing; add it to .env")
    return genai.Client(api_key=api_key)


# gemini-embedding-2 has no task_type field: the task is written into the text.
# Queries and documents use different formats because they are different things:
# a short question should match a long passage, not look identical to it.
def format_document(title: str, text: str) -> str:
    return f"title: {title or 'none'} | text: {text}"


def format_query(question: str) -> str:
    return f"task: question answering | query: {question}"


def call_with_retries[T](request: Callable[[], T]) -> T:
    """Run a Gemini call, waiting longer after each rate limit or server error."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return request()
        except errors.APIError as error:
            # A daily quota resets hours later, so waiting seconds cannot help.
            daily_quota_used = "PerDay" in str(error)
            if (
                daily_quota_used
                or error.code not in RETRYABLE_STATUS_CODES
                or attempt == MAX_ATTEMPTS
            ):
                raise
            time.sleep(2**attempt)
    raise RuntimeError("Gemini retries exhausted")


def embed_text(client: genai.Client, text: str) -> list[float]:
    """Embed one text.

    Texts are sent one at a time on purpose: gemini-embedding-2 merges a plain
    list of strings into a single aggregated vector instead of one per string.
    """
    config = types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS)
    result = call_with_retries(
        lambda: client.models.embed_content(model=EMBEDDING_MODEL, contents=text, config=config)
    )
    return result.embeddings[0].values

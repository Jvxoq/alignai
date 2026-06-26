import asyncio
import logging
import time

from app.core.config import get_settings

logger = logging.getLogger(__name__)

STUB_VECTOR = [0.1] * 3072

TPM_LIMIT = 30_000


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _is_rate_limit(e: Exception) -> bool:
    msg = str(e)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg


def _validate_vector(vector: list[float], expected_dim: int) -> list[float]:
    if not vector:
        raise RuntimeError("Embedding provider returned an empty vector")
    if len(vector) != expected_dim:
        raise RuntimeError(
            f"Embedding dim mismatch: got {len(vector)}, expected {expected_dim}"
        )
    return vector


async def embed_text(
    text: str,
    task_type: str = "RETRIEVAL_QUERY",
    max_retries: int = 3,
) -> list[float]:
    settings = get_settings()

    if settings.DEV_MODE:
        logger.debug("DEV_MODE active, returning stub embedding")
        return list(STUB_VECTOR)

    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")

    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    def _call() -> list[float]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        result = client.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        if not result.embeddings:
            raise RuntimeError("Embedding provider returned no embeddings")
        return list(result.embeddings[0].values)

    for attempt in range(max_retries):
        try:
            vector = await asyncio.to_thread(_call)
            return _validate_vector(vector, settings.EMBEDDING_DIMENSIONS)
        except Exception as e:
            if _is_rate_limit(e) and attempt < max_retries - 1:
                wait = 2 ** attempt * 5
                logger.warning(
                    "embed_text rate limited (attempt %d/%d), retrying in %ds...",
                    attempt + 1, max_retries, wait,
                )
                await asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError(f"embed_text: max retries ({max_retries}) exceeded")


async def embed_batch(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    settings = get_settings()

    if settings.DEV_MODE:
        return [list(STUB_VECTOR) for _ in texts]

    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    def _call() -> list[list[float]]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        result = client.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        if not result.embeddings or len(result.embeddings) != len(texts):
            raise RuntimeError(
                f"Embedding count mismatch: got "
                f"{len(result.embeddings or [])}, expected {len(texts)}"
            )
        return [
            _validate_vector(list(e.values), settings.EMBEDDING_DIMENSIONS)
            for e in result.embeddings
        ]

    return await asyncio.to_thread(_call)


async def _embed_with_retry(
    texts: list[str],
    task_type: str,
    max_retries: int,
) -> list[list[float]]:
    for attempt in range(max_retries):
        try:
            return await embed_batch(texts, task_type)
        except Exception as e:
            if _is_rate_limit(e) and attempt < max_retries - 1:
                wait = 2 ** attempt * 5
                logger.warning("Rate limited (attempt %d/%d), retrying in %ds...", attempt + 1, max_retries, wait)
                await asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Max retries ({max_retries}) exceeded")


async def embed_all(
    texts: list[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """Embed all texts with rate-limit-aware batching.

    Calculates optimal batch size from actual token counts to stay
    under Gemini's 30k TPM limit while minimizing request count.
    """
    settings = get_settings()

    if settings.DEV_MODE:
        logger.info("DEV_MODE active, returning stub embeddings for %d texts", len(texts))
        return [list(STUB_VECTOR) for _ in texts]

    if not texts:
        return []

    total_tokens = sum(_approx_tokens(t) for t in texts)
    avg_tokens = total_tokens // len(texts)

    batch_size = min(20, TPM_LIMIT // avg_tokens)
    batch_size = max(1, batch_size)

    batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
    total_batches = len(batches)

    logger.info(
        "Embedding %d texts (~%d tokens) in %d batches (size=%d, avg=%d tokens/text)",
        len(texts), total_tokens, total_batches, batch_size, avg_tokens,
    )

    all_embeddings: list[list[float]] = []
    pipeline_start = time.time()

    for i, batch in enumerate(batches):
        batch_tokens = sum(_approx_tokens(t) for t in batch)
        logger.info("Batch %d/%d — %d texts, ~%d tokens", i + 1, total_batches, len(batch), batch_tokens)

        result = await _embed_with_retry(batch, task_type, 3)
        all_embeddings.extend(result)

        if i < total_batches - 1:
            await asyncio.sleep(2.0)

    elapsed = time.time() - pipeline_start
    logger.info("Embedding complete — %d vectors in %.1fs", len(all_embeddings), elapsed)

    return all_embeddings

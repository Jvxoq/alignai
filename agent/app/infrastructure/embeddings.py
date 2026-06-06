import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)

STUB_VECTOR = [0.1] * 768


def embed_text(text: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
    settings = get_settings()
    if not settings.gemini_api_key:
        logger.debug("No GEMINI_API_KEY set, returning stub embedding")
        return STUB_VECTOR

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        result = genai.embed_content(
            model=f"models/{settings.embedding_model}",
            content=text,
            task_type=task_type,
        )
        return result["embedding"]
    except Exception:
        logger.warning("Embedding call failed, returning stub", exc_info=True)
        return STUB_VECTOR

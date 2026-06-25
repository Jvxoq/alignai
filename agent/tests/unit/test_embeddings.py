from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.infrastructure import embeddings
from app.infrastructure.embeddings import (
    embed_all,
    embed_batch,
    embed_text,
    _approx_tokens,
    _is_rate_limit,
    _validate_vector,
)

DIM = 3072
VEC = [0.1] * DIM


def _settings(**overrides):
    base = dict(
        DEV_MODE=False,
        GEMINI_API_KEY="test-key",
        EMBEDDING_MODEL="gemini-embedding-001",
        EMBEDDING_DIMENSIONS=DIM,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def prod_settings():
    with patch.object(embeddings, "get_settings", return_value=_settings()):
        yield


def _fake_genai(vectors, raises=None):
    """Patch the lazily-imported google.genai client to return given vectors."""
    call_count = {"n": 0}

    def embed_content(**kwargs):
        call_count["n"] += 1
        if raises is not None:
            exc = raises[min(call_count["n"] - 1, len(raises) - 1)]
            if exc is not None:
                raise exc
        embs = [SimpleNamespace(values=v) for v in vectors]
        return SimpleNamespace(embeddings=embs)

    client = SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))
    genai_mod = SimpleNamespace(Client=lambda api_key: client)
    types_mod = SimpleNamespace(EmbedContentConfig=lambda **k: SimpleNamespace(**k))
    return genai_mod, types_mod, call_count


# --- pure helpers -----------------------------------------------------------

def test_approx_tokens_floor():
    assert _approx_tokens("") == 1
    assert _approx_tokens("a" * 40) == 10


@pytest.mark.parametrize("msg,expected", [
    ("Error 429 too many requests", True),
    ("RESOURCE_EXHAUSTED", True),
    ("500 internal", False),
])
def test_is_rate_limit(msg, expected):
    assert _is_rate_limit(Exception(msg)) is expected


def test_validate_vector_rejects_empty():
    with pytest.raises(RuntimeError, match="empty"):
        _validate_vector([], DIM)


def test_validate_vector_rejects_wrong_dim():
    with pytest.raises(RuntimeError, match="dim mismatch"):
        _validate_vector([0.1] * 10, DIM)


# --- embed_text -------------------------------------------------------------

async def test_embed_text_dev_mode_returns_stub():
    with patch.object(embeddings, "get_settings",
                      return_value=_settings(DEV_MODE=True)):
        out = await embed_text("anything")
    assert len(out) == DIM


async def test_embed_text_rejects_empty(prod_settings):
    with pytest.raises(ValueError, match="empty"):
        await embed_text("   ")


async def test_embed_text_missing_key():
    with patch.object(embeddings, "get_settings",
                      return_value=_settings(GEMINI_API_KEY="")):
        with pytest.raises(RuntimeError, match="not configured"):
            await embed_text("hello")


async def test_embed_text_happy_path(prod_settings):
    genai_mod, types_mod, _ = _fake_genai([VEC])
    with patch.dict("sys.modules", {"google": SimpleNamespace(genai=genai_mod),
                                    "google.genai": genai_mod}):
        genai_mod.types = types_mod
        with patch("google.genai.types", types_mod, create=True):
            out = await embed_text("what is article 5")
    assert out == VEC


async def test_embed_text_retries_on_429(prod_settings, monkeypatch):
    monkeypatch.setattr(embeddings.asyncio, "sleep",
                        lambda *a, **k: _noop())
    genai_mod, types_mod, calls = _fake_genai(
        [VEC], raises=[Exception("429 RESOURCE_EXHAUSTED"), None]
    )
    with patch.dict("sys.modules", {"google": SimpleNamespace(genai=genai_mod),
                                    "google.genai": genai_mod}):
        with patch("google.genai.types", types_mod, create=True):
            out = await embed_text("retry me", max_retries=3)
    assert out == VEC
    assert calls["n"] == 2


async def test_embed_text_non_429_does_not_retry(prod_settings):
    genai_mod, types_mod, calls = _fake_genai([VEC], raises=[Exception("500 boom")])
    with patch.dict("sys.modules", {"google": SimpleNamespace(genai=genai_mod),
                                    "google.genai": genai_mod}):
        with patch("google.genai.types", types_mod, create=True):
            with pytest.raises(Exception, match="500 boom"):
                await embed_text("nope")
    assert calls["n"] == 1


async def test_embed_text_validates_dim(prod_settings):
    genai_mod, types_mod, _ = _fake_genai([[0.1] * 5])  # wrong dim
    with patch.dict("sys.modules", {"google": SimpleNamespace(genai=genai_mod),
                                    "google.genai": genai_mod}):
        with patch("google.genai.types", types_mod, create=True):
            with pytest.raises(RuntimeError, match="dim mismatch"):
                await embed_text("bad dim")


# --- embed_batch ------------------------------------------------------------

async def test_embed_batch_count_mismatch(prod_settings):
    genai_mod, types_mod, _ = _fake_genai([VEC])  # returns 1 for 2 inputs
    with patch.dict("sys.modules", {"google": SimpleNamespace(genai=genai_mod),
                                    "google.genai": genai_mod}):
        with patch("google.genai.types", types_mod, create=True):
            with pytest.raises(RuntimeError, match="count mismatch"):
                await embed_batch(["a", "b"])


# --- embed_all --------------------------------------------------------------

async def test_embed_all_empty_input(prod_settings):
    assert await embed_all([]) == []


async def test_embed_all_dev_mode():
    with patch.object(embeddings, "get_settings",
                      return_value=_settings(DEV_MODE=True)):
        out = await embed_all(["a", "b", "c"])
    assert len(out) == 3 and all(len(v) == DIM for v in out)


async def test_embed_all_batches_and_throttles(prod_settings, monkeypatch):
    sleeps = []
    monkeypatch.setattr(embeddings.asyncio, "sleep",
                        lambda s, *a, **k: sleeps.append(s) or _noop())
    texts = ["x" * 100] * 45  # forces multiple batches (batch_size capped at 20)

    async def fake_batch(batch, task_type):
        return [VEC for _ in batch]

    monkeypatch.setattr(embeddings, "embed_batch", fake_batch)
    out = await embed_all(texts)
    assert len(out) == 45
    # 3 batches (20/20/5) -> sleeps between batches only
    assert len([s for s in sleeps if s == 2.0]) == 2


async def _noop():
    return None

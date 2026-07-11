import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.nodes import retriever_node as rn
from app.nodes.retriever_node import (
    deduplicate_by_article,
    filter_by_threshold,
    format_retrieved_docs,
    retriever_node,
)

DIM = 3072
VEC = [0.1] * DIM


def _settings(threshold=0.75, top_k=3):
    return SimpleNamespace(
        SIMILARITY_THRESHOLD=threshold,
        RETRIEVAL_TOP_K=top_k,
    )


def _hit(article, score, **payload):
    return {
        "score": score,
        "payload": {"article_number": article, **payload},
    }


def _state(objective="What are high-risk AI obligations?", attempts=0):
    return {
        "objective": objective,
        "retrieval_attempts": attempts,
        "retrieved_docs": [],
        "is_relevant": None,
        "messages": [],
    }


@pytest.fixture
def mocks():
    """Patch settings + both infra calls so nothing hits Gemini/Qdrant."""
    with patch.object(rn, "get_settings", return_value=_settings()), \
         patch.object(rn, "embed_text", new=AsyncMock(return_value=VEC)) as embed, \
         patch.object(rn, "search_chunks", new=AsyncMock(return_value=[])) as search:
        yield SimpleNamespace(embed=embed, search=search)


# --- pure helpers -----------------------------------------------------------

def test_filter_by_threshold():
    hits = [_hit("5", 0.9), _hit("6", 0.74), _hit("7", 0.75)]
    out = filter_by_threshold(hits, 0.75)
    assert [h["payload"]["article_number"] for h in out] == ["5", "7"]


def test_filter_missing_score_treated_as_zero():
    assert filter_by_threshold([{"payload": {}}], 0.5) == []


def test_dedup_keeps_highest_score():
    hits = [_hit("5", 0.8), _hit("5", 0.95), _hit("6", 0.9)]
    out = {h["payload"]["article_number"]: h["score"] for h in deduplicate_by_article(hits)}
    assert out == {"5": 0.95, "6": 0.9}


def test_deduplicate_skips_blank_article_number():
    assert deduplicate_by_article([_hit("", 0.99)]) == []


def test_dedup_keeps_recital_hits_keyed_by_recital_number():
    hits = [
        _hit(None, 0.9, recital_number="47"),
        _hit(None, 0.6, recital_number="47"),
        _hit(None, 0.8, recital_number="12"),
    ]
    out = {h["payload"]["recital_number"]: h["score"] for h in deduplicate_by_article(hits)}
    assert out == {"47": 0.9, "12": 0.8}


def test_format_retrieved_docs_shape():
    hit = _hit("5", 0.88, article_title="Risk", chapter_number="III",
               is_recital=False, parent_text="body")
    doc = format_retrieved_docs([hit])[0]
    assert doc["article_number"] == "5"
    assert doc["article_title"] == "Risk"
    assert doc["similarity_score"] == 0.88
    assert doc["is_recital"] is False


# --- retriever_node: guard rails --------------------------------------------

async def test_empty_objective_short_circuits(mocks):
    result = await retriever_node(_state(objective=""))
    assert result == {"retrieval_attempts": 1, "is_relevant": False, "retrieved_docs": []}
    mocks.embed.assert_not_called()
    mocks.search.assert_not_called()


async def test_missing_objective_short_circuits(mocks):
    result = await retriever_node({"retrieval_attempts": 2})
    assert result["is_relevant"] is False
    assert result["retrieval_attempts"] == 3


# --- retriever_node: happy path ---------------------------------------------

async def test_happy_path_filters_dedups_formats(mocks):
    mocks.search.return_value = [
        _hit("5", 0.95, parent_text="a"),
        _hit("5", 0.80, parent_text="a-dup"),   # dropped by dedup
        _hit("6", 0.78, parent_text="b"),
        _hit("7", 0.50, parent_text="c"),        # dropped by threshold
    ]
    result = await retriever_node(_state())

    assert result["is_relevant"] is True
    assert result["retrieval_attempts"] == 1
    articles = sorted(d["article_number"] for d in result["retrieved_docs"])
    assert articles == ["5", "6"]
    mocks.embed.assert_awaited_once_with(
        "What are high-risk AI obligations?", task_type="RETRIEVAL_QUERY"
    )
    mocks.search.assert_awaited_once_with(VEC, top_k=3)


async def test_all_below_threshold_is_not_relevant(mocks):
    mocks.search.return_value = [_hit("5", 0.10), _hit("6", 0.20)]
    result = await retriever_node(_state())
    assert result["is_relevant"] is False
    assert result["retrieved_docs"] == []


async def test_no_hits_is_not_relevant(mocks):
    mocks.search.return_value = []
    result = await retriever_node(_state())
    assert result["is_relevant"] is False


# --- retriever_node: prod failure modes -------------------------------------

async def test_timeout_degrades_gracefully(mocks):
    mocks.embed.side_effect = asyncio.TimeoutError
    result = await retriever_node(_state())
    assert result == {"retrieval_attempts": 1, "is_relevant": False, "retrieved_docs": []}


async def test_connection_error_degrades_gracefully(mocks):
    mocks.search.side_effect = ConnectionError("qdrant down")
    result = await retriever_node(_state())
    assert result["is_relevant"] is False
    assert result["retrieved_docs"] == []


async def test_unexpected_error_degrades_gracefully(mocks):
    mocks.embed.side_effect = ValueError("bad input")
    result = await retriever_node(_state())
    assert result["is_relevant"] is False
    assert result["retrieval_attempts"] == 1


async def test_attempts_increment_across_calls(mocks):
    mocks.search.return_value = []
    r1 = await retriever_node(_state(attempts=0))
    r2 = await retriever_node(_state(attempts=r1["retrieval_attempts"]))
    assert (r1["retrieval_attempts"], r2["retrieval_attempts"]) == (1, 2)

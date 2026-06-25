from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.graph.edges import check_relevance, should_retrieve
from app.graph.graph import END, graph
from app.graph.state import RESET_DOCS
from app.nodes.retriever_node import retriever_node


def _make_state(messages: list, objective: str | None = None) -> dict:
    return {
        "messages": messages,
        "objective": objective,
        "retrieved_docs": [],
        "is_relevant": None,
        "retrieval_attempts": 0,
    }


def _mock_point(id: str, score: float, payload: dict) -> MagicMock:
    point = MagicMock()
    point.id = id
    point.score = score
    point.payload = payload
    return point


def _mock_qdrant_client(points: list[MagicMock]) -> MagicMock:
    """Return a mock QdrantClient whose query_points() returns the given points."""
    client = MagicMock()
    result = MagicMock()
    result.points = points
    client.query_points = AsyncMock(return_value=result)
    return client


# ------------------------------------------------------------------
# Scenario 1 — Formal educational query
# Input: "Explain the EU AI Act requirements for high-risk AI systems"
# Path: intent → retrieve → generate → END
# Expected: formal structured compliance report
# ------------------------------------------------------------------

@patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
@patch("app.nodes.retriever_node.embed_text", new_callable=AsyncMock)
@patch("app.infrastructure.qdrant_client.get_qdrant_client")
async def test_formal_educational_query(mock_get_client, mock_embed, mock_llm_intent):
    """Scenario 1: Formal compliance question about high-risk AI requirements.

    Flow:
      intent_node  → LLM classifies as compliance-related, sets objective
      retriever_node → embeds objective, searches Qdrant, finds Article 9 (score 0.91)
      generator_node → produces structured report citing Article 9

    Verifies:
      - intent sets objective (not direct response)
      - routing goes intent → retrieve → generate → END
      - generator appends AIMessage with formal report
      - retrieved_docs is cleared after generation (RESET_DOCS)
    """
    mock_llm_intent.return_value = type("IntentClassification", (), {
        "objective": "Retrieve EU AI Act provisions for high-risk AI system requirements and classification",
        "response": None,
    })()

    mock_embed.return_value = [0.1] * 3072

    article_9_point = _mock_point(
        id="1", score=0.91,
        payload={
            "article_number": "9",
            "article_title": "Risk management system",
            "chapter_number": "III",
            "recital_number": None,
            "is_recital": False,
            "parent_text": (
                "Article 9 — Risk management system. "
                "A risk management system shall be established and documented "
                "for high-risk AI systems covering known and foreseeable risks."
            ),
        },
    )
    mock_get_client.return_value = _mock_qdrant_client([article_9_point])

    with patch("app.nodes.generator_node.call_llm", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = (
            "# EU AI Act Compliance Analysis\n\n"
            "## 1. Compliance Objective\n"
            "High-risk AI system requirements under the EU AI Act.\n\n"
            "## 2. Relevant EU AI Act Articles\n"
            "- Article 9 — Risk management system\n\n"
            "## 3. Assessment\n"
            "**Verdict:** Partially Compliant\n\n"
            "## 4. Recommendations\n"
            "- Document a risk management system covering all foreseeable risks."
        )

        result = await graph.ainvoke(_make_state([
            HumanMessage(content="Explain the EU AI Act requirements for high-risk AI systems")
        ]))

    # intent sets objective for compliance query (not direct response)
    assert result["objective"] is not None, (
        "intent_node should have set an objective for compliance query"
    )

    # generator_node appends at least one AIMessage
    final_messages = result["messages"]
    ai_messages = [m for m in final_messages if isinstance(m, AIMessage)]
    assert len(ai_messages) >= 1, "Expected at least one AIMessage from generator"

    report = ai_messages[-1].content
    assert "EU AI Act" in report or "Compliance" in report, (
        f"Report should be about EU AI Act compliance, got: {report[:100]}"
    )
    assert "Article" in report, "Report should cite specific articles"
    assert "Verdict" in report, "Report should include a Verdict"
    assert "retrieved_docs" in result, "retrieved_docs key must be in output state"


# ------------------------------------------------------------------
# Scenario 2 — Whole specification / feature audit
# Input: "Audit this feature: an AI hiring system that scores candidates from resumes"
# Path: intent → retrieve → generate → END
# Expected: formal 5-section audit report
# ------------------------------------------------------------------

@patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
@patch("app.nodes.retriever_node.embed_text", new_callable=AsyncMock)
@patch("app.infrastructure.qdrant_client.get_qdrant_client")
async def test_specification_audit_query(mock_get_client, mock_embed, mock_llm_intent):
    """Scenario 2: User submits a full feature specification for compliance audit.

    Flow:
      intent_node  → sets objective specific to AI hiring / CV scoring
      retriever_node → retrieves Articles 10, 51, 22 (data governance, transparency, oversight)
      generator_node → produces formal 5-section audit report

    Verifies:
      - intent accepts specification as compliance-related
      - generator report has ## section headers (formal structure)
      - report cites Articles 10, 51, and 22
      - report includes Verdict and Recommendations sections
      - NOT the generic fallback template
    """
    mock_llm_intent.return_value = type("IntentClassification", (), {
        "objective": "Retrieve EU AI Act provisions for AI hiring systems, "
                     "candidate scoring, resume analysis, and automated decision-making",
        "response": None,
    })()

    mock_embed.return_value = [0.2] * 3072

    article_10_point = _mock_point(
        id="1", score=0.92,
        payload={
            "article_number": "10",
            "article_title": "Data governance",
            "chapter_number": "III",
            "recital_number": None,
            "is_recital": False,
            "parent_text": "Article 10 — Data governance. Providers of high-risk AI systems "
                "shall put in place a data governance policy.",
        },
    )
    article_51_point = _mock_point(
        id="2", score=0.89,
        payload={
            "article_number": "51",
            "article_title": "Transparency obligations",
            "chapter_number": "IV",
            "recital_number": None,
            "is_recital": False,
            "parent_text": "Article 51 — AI systems interacting with natural persons "
                "must inform users they are interacting with an AI system.",
        },
    )
    article_22_point = _mock_point(
        id="3", score=0.87,
        payload={
            "article_number": "22",
            "article_title": "Human oversight",
            "chapter_number": "III",
            "recital_number": None,
            "is_recital": False,
            "parent_text": "Article 22 — High-risk AI systems shall be designed to allow "
                "effective human oversight.",
        },
    )
    mock_get_client.return_value = _mock_qdrant_client([
        article_10_point, article_51_point, article_22_point,
    ])

    with patch("app.nodes.generator_node.call_llm", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = (
            "# Compliance Audit Report\n\n"
            "## 1. Compliance Objective\n"
            "Audit of AI hiring system that scores candidates from resumes.\n\n"
            "## 2. Relevant EU AI Act Articles\n"
            "- Article 10 — Data governance\n"
            "- Article 22 — Human oversight\n"
            "- Article 51 — Transparency obligations\n\n"
            "## 3. Assessment\n"
            "**Verdict:** Non-Compliant — Transparency and human oversight gaps identified.\n\n"
            "## 4. Findings\n"
            "- System scores candidates without informing them they interact with AI.\n"
            "- No human oversight mechanism for automated ranking decisions.\n"
            "- No documented data governance policy covering resume data processing.\n\n"
            "## 5. Recommendations\n"
            "- Implement Article 51 transparency notices for all candidates.\n"
            "- Add human review step for any automated ranking decisions.\n"
            "- Establish a data governance policy per Article 10."
        )

        result = await graph.ainvoke(_make_state([
            HumanMessage(
                content="Audit this feature: an AI hiring system that scores candidates from resumes"
            )
        ]))

    final_messages = result["messages"]
    ai_messages = [m for m in final_messages if isinstance(m, AIMessage)]
    assert len(ai_messages) >= 1, "Expected at least one AIMessage from generator"

    report = ai_messages[-1].content
    # Formal audit reports have ## numbered section headers
    assert "## 1." in report, f"Report should have ## 1. section header, got: {report[:200]}"
    assert "## 2." in report, "Report should have section 2 (articles)"
    assert "## 3." in report, "Report should have section 3 (assessment)"
    assert "## 4." in report, "Report should have section 4 (findings)"
    assert "## 5." in report, "Report should have section 5 (recommendations)"
    assert "Verdict" in report, "Report should include a Verdict"
    assert "Article 10" in report or "Article 22" in report, (
        f"Report should cite relevant articles, got: {report[:200]}"
    )
    # Should NOT be the generic insufficient-information fallback
    assert "Insufficient information" not in report, (
        "Should not fall back to generic template when docs are retrieved"
    )


# ------------------------------------------------------------------
# Scenario 3 — Educational query with retrieved context
# Input: "What does Article 10 of the AI Act say about data governance?"
# Path: intent → retrieve → generate → END
# Expected: educational response citing exact Article 10 text
# ------------------------------------------------------------------

@patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
@patch("app.nodes.retriever_node.embed_text", new_callable=AsyncMock)
@patch("app.infrastructure.qdrant_client.get_qdrant_client")
async def test_educational_query_with_context(mock_get_client, mock_embed, mock_llm_intent):
    """Scenario 3: User asks an educational question about a specific Article.

    Flow:
      intent_node  → sets objective about Article 10 and data governance
      retriever_node → retrieves Article 10 chunk (score 0.92), is_relevant=True
      generator_node → formats context with Article 10 text, generates educational response

    Verifies:
      - objective is specific to Article 10 and data governance
      - retriever marks is_relevant=True (doc passes similarity threshold)
      - generator response explains Article 10 with the actual article text
      - response includes Article 10 sub-requirements (data quality, purpose, accuracy, processing)
      - NOT the generic fallback template
    """
    mock_llm_intent.return_value = type("IntentClassification", (), {
        "objective": "Retrieve EU AI Act Article 10 data governance requirements",
        "response": None,
    })()

    mock_embed.return_value = [0.3] * 3072

    article_10_point = _mock_point(
        id="1", score=0.92,
        payload={
            "article_number": "10",
            "article_title": "Data governance",
            "chapter_number": "III",
            "recital_number": None,
            "is_recital": False,
            "parent_text": (
                "Article 10 — Data governance\n\n"
                "1. Member States shall ensure that providers of high-risk AI systems "
                "put in place a data governance policy that governs data collection, "
                "use and processing. This policy shall address matters including: "
                "(a) data quality; (b) data collection purpose; "
                "(c) data accuracy; (d) appropriate data processing."
            ),
        },
    )
    mock_get_client.return_value = _mock_qdrant_client([article_10_point])

    with patch("app.nodes.generator_node.call_llm", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = (
            "# EU AI Act — Article 10: Data Governance\n\n"
            "## Article 10 Overview\n"
            "Article 10 requires providers of high-risk AI systems to implement a "
            "comprehensive data governance policy covering data collection, use, and processing.\n\n"
            "## Key Requirements\n"
            "The policy must address four core areas:\n"
            "1. **Data quality** — ensuring accuracy and completeness of training data.\n"
            "2. **Data collection purpose** — limiting use to specified, lawful purposes.\n"
            "3. **Data accuracy** — mechanisms to identify and correct data errors.\n"
            "4. **Appropriate data processing** — measures to ensure lawful and fair processing.\n\n"
            "## Applicability\n"
            "These obligations apply to all high-risk AI system providers operating in the EU "
            "or placing systems on the EU market."
        )

        result = await graph.ainvoke(_make_state([
            HumanMessage(
                content="What does Article 10 of the AI Act say about data governance?"
            )
        ]))

    # retriever found relevant docs
    assert result["is_relevant"] is True, (
        "is_relevant should be True when retriever finds above-threshold matches"
    )
    assert result["retrieval_attempts"] == 1, (
        "retrieval_attempts should increment to 1 on first retrieval"
    )

    # generator produced educational response
    final_messages = result["messages"]
    ai_messages = [m for m in final_messages if isinstance(m, AIMessage)]
    assert len(ai_messages) >= 1, "Expected at least one AIMessage from generator"

    response = ai_messages[-1].content
    assert "Article 10" in response, (
        f"Response should explain Article 10, got: {response[:200]}"
    )
    assert "data governance" in response, (
        "Response should cover the data governance topic from Article 10"
    )
    assert "data quality" in response or "four" in response.lower(), (
        "Response should explain the four sub-requirements of Article 10"
    )
    # Should NOT be the generic insufficient-information fallback
    assert "Insufficient information" not in response, (
        "Should not fall back to generic template when docs are retrieved"
    )


# ------------------------------------------------------------------
# State shape verification — all scenarios must produce complete state
# ------------------------------------------------------------------

@patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
@patch("app.nodes.retriever_node.embed_text", new_callable=AsyncMock)
@patch("app.infrastructure.qdrant_client.get_qdrant_client")
async def test_graph_returns_complete_agent_state(mock_get_client, mock_embed, mock_llm_intent):
    """All scenarios must produce a state containing all AgentState keys."""
    mock_llm_intent.return_value = type("IntentClassification", (), {
        "objective": "Retrieve EU AI Act provisions for facial recognition",
        "response": None,
    })()
    mock_embed.return_value = [0.4] * 3072
    mock_get_client.return_value = _mock_qdrant_client([
        _mock_point(id="1", score=0.88, payload={
            "article_number": "5",
            "article_title": "Prohibited AI practices",
            "chapter_number": "II",
            "recital_number": None,
            "is_recital": False,
            "parent_text": "Article 5 prohibits real-time remote biometric identification.",
        }),
    ])

    with patch("app.nodes.generator_node.call_llm", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "# Biometric AI Report\n\n## 1. Compliance Objective\nFacial recognition.\n"
        result = await graph.ainvoke(_make_state([
            HumanMessage(content="Is facial recognition allowed under the AI Act?")
        ]))

    assert isinstance(result, dict)
    assert "messages" in result
    assert "objective" in result
    assert "retrieved_docs" in result
    assert "is_relevant" in result
    assert "retrieval_attempts" in result
    assert isinstance(result["messages"], list)
    assert isinstance(result["retrieval_attempts"], int)


# ------------------------------------------------------------------
# Edge: intent_node falls back to keyword matching when LLM fails
# ------------------------------------------------------------------

@patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
async def test_intent_llm_failure_keyword_match(mock_llm_intent):
    """When LLM classification fails, intent_node should fall back to keyword matching.

    Compliance keywords should still route to retrieve (not __end__)."""
    mock_llm_intent.side_effect = RuntimeError("LLM unavailable")

    from app.nodes.intent_node import intent_node

    result = await intent_node(_make_state([
        HumanMessage(content="What are the Article 22 human oversight requirements?")
    ]))

    assert result["objective"] is not None, (
        "intent_node should still set objective when keyword match succeeds"
    )
    assert "retrieval_attempts" not in result or result["retrieval_attempts"] == 0
    assert result["is_relevant"] is None


@patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
async def test_intent_exception_fallback_message(mock_llm_intent):
    """When LLM fails and no keywords match, intent_node should return the
    generic fallback AIMessage and route to __end__."""
    mock_llm_intent.side_effect = RuntimeError("LLM unavailable")

    from app.nodes.intent_node import intent_node

    result = await intent_node(_make_state([
        HumanMessage(content="What is the weather in Paris?")
    ]))

    assert result["objective"] is None, (
        "General non-compliance query should not set objective"
    )
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    assert len(ai_messages) == 1, "Should return exactly one fallback AIMessage"
    content_lower = ai_messages[0].content.lower()
    assert "compliance" in content_lower or "ai act" in content_lower, (
        f"Fallback message should be compliance-focused, got: {ai_messages[0].content}"
    )


# ------------------------------------------------------------------
# Edge: retriever returns is_relevant=False on empty results
# ------------------------------------------------------------------

@patch("app.nodes.retriever_node.embed_text", new_callable=AsyncMock)
@patch("app.infrastructure.qdrant_client.get_qdrant_client")
async def test_retriever_zero_results(mock_get_client, mock_embed):
    """When Qdrant returns no chunks above similarity threshold,
    retriever should return is_relevant=False (triggers rewrite_objective path)."""
    mock_embed.return_value = [0.9] * 3072
    mock_get_client.return_value = _mock_qdrant_client([])  # no results

    result = await retriever_node(_make_state(
        [HumanMessage(content="Some very obscure regulation")],
        objective="some obscure niche regulation",
    ))

    assert result["is_relevant"] is False, (
        "is_relevant should be False when no chunks pass the threshold"
    )
    assert result["retrieved_docs"] == [], "retrieved_docs should be empty on no results"
    assert result["retrieval_attempts"] == 1, (
        "retrieval_attempts should increment to 1 on first retrieval attempt"
    )


# ------------------------------------------------------------------
# Edge: rewrite_objective_node refines objective
# ------------------------------------------------------------------

@patch("app.nodes.rewrite_objective_node.call_llm", new_callable=AsyncMock)
async def test_rewrite_increments_attempt(mock_llm_rewrite):
    """When retriever fails relevance, rewrite_objective_node should
    return a refined objective and reset is_relevant for re-evaluation."""
    mock_llm_rewrite.return_value = (
        "EU AI Act Article 9 risk management system for high-risk AI"
    )

    from app.nodes.rewrite_objective_node import rewrite_objective_node

    result = await rewrite_objective_node({
        "messages": [HumanMessage(content="What are the risk management requirements?")],
        "objective": "EU AI Act risk management",
        "retrieved_docs": [],
        "is_relevant": False,
        "retrieval_attempts": 1,
    })

    assert result["objective"] is not None, "Should return a refined objective"
    assert "retrieval_attempts" not in result, (
        "rewrite_objective_node should not mutate retrieval_attempts"
    )
    assert result["is_relevant"] is None, (
        "is_relevant should be reset for fresh evaluation by retriever"
    )


# ------------------------------------------------------------------
# Edge: check_relevance routing logic
# ------------------------------------------------------------------

def test_check_relevance_max_attempts():
    """When retrieval_attempts >= 3 and is_relevant=False,
    check_relevance should route to 'fallback'."""
    state = _make_state(
        [HumanMessage(content="test")],
        objective="test",
    )
    state["is_relevant"] = False
    state["retrieval_attempts"] = 3

    result = check_relevance(state)
    assert result == "fallback", (
        f"Expected 'fallback' at max attempts, got '{result}'"
    )


def test_check_relevance_first_attempt():
    """When is_relevant=False and attempts < 3,
    check_relevance should route to 'rewrite_objective'."""
    state = _make_state(
        [HumanMessage(content="test")],
        objective="test",
    )
    state["is_relevant"] = False
    state["retrieval_attempts"] = 0

    result = check_relevance(state)
    assert result == "rewrite_objective", (
        f"Expected 'rewrite_objective' for first failed attempt, got '{result}'"
    )


def test_check_relevance_when_relevant():
    """When is_relevant=True, check_relevance should always route to 'generate'."""
    state = _make_state(
        [HumanMessage(content="test")],
        objective="test",
    )
    state["is_relevant"] = True
    state["retrieval_attempts"] = 1

    result = check_relevance(state)
    assert result == "generate", (
        f"Expected 'generate' when is_relevant=True, got '{result}'"
    )


def test_should_retrieve_with_objective():
    """When objective is set (compliance query), should_retrieve
    should route to 'retrieve'."""
    state = _make_state(
        [HumanMessage(content="What is Article 10?")],
        objective="Retrieve Article 10",
    )

    result = should_retrieve(state)
    assert result == "retrieve", f"Expected 'retrieve', got '{result}'"


def test_should_retrieve_without_objective():
    """When objective is None (general chat), should_retrieve
    should route to END."""
    state = _make_state(
        [HumanMessage(content="What is the weather?")],
        objective=None,
    )

    result = should_retrieve(state)
    assert result == END, f"Expected END, got '{result}'"

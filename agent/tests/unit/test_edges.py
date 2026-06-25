from app.graph.edges import check_relevance, should_retrieve


class TestShouldRetrieve:
    def test_with_objective(self):
        state = {"objective": "What are the requirements for high-risk AI systems?"}
        assert should_retrieve(state) == "retrieve"

    def test_without_objective(self):
        state = {"objective": None}
        assert should_retrieve(state) == "__end__"

    def test_empty_objective(self):
        state = {"objective": ""}
        assert should_retrieve(state) == "__end__"

    def test_missing_objective_key(self):
        state = {}
        assert should_retrieve(state) == "__end__"


class TestCheckRelevance:
    def test_relevant(self):
        state = {"is_relevant": True, "retrieval_attempts": 1}
        assert check_relevance(state) == "generate"

    def test_not_relevant_under_limit(self):
        state = {"is_relevant": False, "retrieval_attempts": 2}
        assert check_relevance(state) == "rewrite_objective"

    def test_not_relevant_at_limit(self):
        state = {"is_relevant": False, "retrieval_attempts": 3}
        assert check_relevance(state) == "fallback"

    def test_not_relevant_over_limit(self):
        state = {"is_relevant": False, "retrieval_attempts": 5}
        assert check_relevance(state) == "fallback"

    def test_none_relevance_under_limit(self):
        state = {"is_relevant": None, "retrieval_attempts": 1}
        assert check_relevance(state) == "rewrite_objective"

    def test_none_relevance_at_limit(self):
        state = {"is_relevant": None, "retrieval_attempts": 3}
        assert check_relevance(state) == "fallback"

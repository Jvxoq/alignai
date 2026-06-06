REWRITE_PROMPT = """The retrieved context has low relevance to the feature description.
Rewrite the objective to improve retrieval alignment.

Original feature text:
{feature_text}

Low-relevance context:
{context}

Return a refined objective statement.
"""

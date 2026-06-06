GENERATOR_PROMPT = """Generate an alignment audit report for the feature description below.
Use the retrieved context to inform your analysis.

Feature text:
{feature_text}

Retrieved context:
{context}

Produce a structured markdown report covering alignment, gaps, and recommendations.
"""

"""The AI candidate<->job matching/scoring engine (product brief § 2):

    Job requirements -> normalize -> candidate structured profile
        -> deterministic matching -> semantic matching
        -> optional Gemini reasoning -> final structured MatchResult

See match_engine.py for the orchestrator; the other modules in this package
are each one pipeline stage and are independently unit-testable.
"""

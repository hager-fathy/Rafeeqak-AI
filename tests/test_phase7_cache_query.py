from datetime import date, timedelta

from src.agents.database_query import DatabaseQueryAgent
from src.agents.study_planner import StudyPlannerAgent
from src.agents.supervisor import SupervisorAgent
from src.tools.semantic_cache import SemanticResponseCache


def _active_plan() -> dict:
    plan = StudyPlannerAgent().generate(
        {
            "course_name": "Databases",
            "exam_date": date.today() + timedelta(days=5),
            "daily_hours": 2,
            "weak_topics": ["Indexes"],
            "other_topics": ["Transactions"],
        }
    )["plan"]
    plan["tasks"][0]["completed"] = True
    return plan


def test_semantic_cache_reuses_similar_question_with_same_context(tmp_path) -> None:
    cache = SemanticResponseCache(cache_path=tmp_path / "semantic_cache.json", min_similarity=0.5)
    fingerprint = "same-context"
    cache.store(
        message="What is my progress?",
        language="en",
        intent="database_query",
        agent="database_query_agent",
        response="You completed 1 of 5 tasks.",
        payload={"query_type": "progress"},
        context_fingerprint=fingerprint,
    )

    hit = cache.lookup(
        message="What is my study progress?",
        language="en",
        context_fingerprint=fingerprint,
    )

    assert hit is not None
    assert hit["agent"] == "database_query_agent"
    assert hit["payload"]["query_type"] == "progress"
    assert cache.stats()["entries"] == 1


def test_semantic_cache_rejects_stale_context(tmp_path) -> None:
    cache = SemanticResponseCache(cache_path=tmp_path / "semantic_cache.json", min_similarity=0.5)
    cache.store(
        message="What is my progress?",
        language="en",
        intent="database_query",
        agent="database_query_agent",
        response="You completed 1 of 5 tasks.",
        payload={},
        context_fingerprint="old-context",
    )

    assert cache.lookup(message="What is my progress?", language="en", context_fingerprint="new-context") is None


def test_database_query_agent_answers_progress_and_deadlines() -> None:
    context = {
        "active_plan": _active_plan(),
        "quiz_attempts": [{"topic": "Indexes", "score_percent": 60, "weak_topics": ["Indexes"]}],
    }
    agent = DatabaseQueryAgent()

    progress = agent.answer(message="What is my progress?", context=context)
    deadline = agent.answer(message="When is my exam deadline?", context=context)
    weak_topics = agent.answer(message="What are my weaknesses?", context=context)

    assert progress["query_type"] == "progress"
    assert "completed 1 of" in progress["response"]
    assert deadline["query_type"] == "deadline"
    assert "Databases" in deadline["response"]
    assert weak_topics["query_type"] == "weak_topics"
    assert "Indexes" in weak_topics["response"]


def test_supervisor_routes_database_query_and_cache_hit(tmp_path) -> None:
    cache = SemanticResponseCache(cache_path=tmp_path / "semantic_cache.json", min_similarity=0.9)
    supervisor = SupervisorAgent(semantic_cache=cache)
    context = {"active_plan": _active_plan(), "quiz_attempts": [], "uploads": []}

    first = supervisor.handle_message("What is my progress?", context=context)
    second = supervisor.handle_message("What is my progress?", context=context)

    assert first["agent"] == "database_query_agent"
    assert first["payload"]["query_type"] == "progress"
    assert second["agent"] == "database_query_agent"
    assert second["payload"]["cache"]["hit"] is True
    assert [step["status"] for step in second["trace"] if step["agent"] == "SemanticCache"] == ["hit"]

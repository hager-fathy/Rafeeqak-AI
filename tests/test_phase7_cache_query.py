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


def test_semantic_cache_rejects_same_context_from_different_course(tmp_path) -> None:
    cache = SemanticResponseCache(cache_path=tmp_path / "semantic_cache.json", min_similarity=0.5)
    cache.store(
        message="What is my progress?",
        language="en",
        intent="database_query",
        agent="database_query_agent",
        response="Security progress answer.",
        payload={},
        course_id="security-course",
        context_fingerprint="same-context",
    )

    hit = cache.lookup(
        message="What is my progress?",
        language="en",
        course_id="ml-course",
        context_fingerprint="same-context",
    )

    assert hit is None


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


def test_database_query_agent_answers_all_course_summary() -> None:
    context = {
        "active_course_name": "Databases",
        "active_plan": _active_plan(),
        "quiz_attempts": [{"topic": "Indexes", "score_percent": 60, "weak_topics": ["Indexes"]}],
        "all_courses": [
            {
                "course_id": "db",
                "course_name": "Databases",
                "total_tasks": 5,
                "completed_tasks": 1,
                "quiz_attempts": 1,
                "average_score": 60,
                "uploads": 2,
                "weak_topics": ["Indexes"],
                "exam_date": "2026-06-01",
            },
            {
                "course_id": "ml",
                "course_name": "Machine Learning",
                "total_tasks": 4,
                "completed_tasks": 3,
                "quiz_attempts": 2,
                "average_score": 82,
                "uploads": 1,
                "weak_topics": ["Backpropagation"],
                "exam_date": "2026-06-10",
            },
        ],
    }

    result = DatabaseQueryAgent().answer(message="Show all courses progress", context=context)

    assert result["scope"] == "all_courses"
    assert "Databases: 1/5 tasks" in result["response"]
    assert "Machine Learning: 3/4 tasks" in result["response"]


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


def test_supervisor_cache_invalidates_when_quiz_attempt_content_changes(tmp_path) -> None:
    cache = SemanticResponseCache(cache_path=tmp_path / "semantic_cache.json", min_similarity=0.9)
    supervisor = SupervisorAgent(semantic_cache=cache)
    base_context = {
        "active_course_id": "db",
        "active_course_name": "Databases",
        "active_plan": _active_plan(),
        "uploads": [],
    }
    first_context = {
        **base_context,
        "quiz_attempts": [
            {
                "timestamp_utc": "2026-05-01T10:00:00",
                "topic": "Indexes",
                "score_percent": 60,
                "weak_topics": ["Indexes"],
            }
        ],
    }
    updated_context = {
        **base_context,
        "quiz_attempts": [
            {
                "timestamp_utc": "2026-05-01T10:00:00",
                "topic": "Indexes",
                "score_percent": 90,
                "weak_topics": [],
            }
        ],
    }

    first = supervisor.handle_message("What are my average scores?", context=first_context)
    second = supervisor.handle_message("What are my average scores?", context=updated_context)

    assert "60%" in first["response"]
    assert "90%" in second["response"]
    assert [step["status"] for step in second["trace"] if step["agent"] == "SemanticCache"] == ["miss"]


def test_supervisor_cache_invalidates_when_material_metadata_changes(tmp_path) -> None:
    cache = SemanticResponseCache(cache_path=tmp_path / "semantic_cache.json", min_similarity=0.9)
    supervisor = SupervisorAgent(semantic_cache=cache)
    base_context = {
        "active_course_id": "db",
        "active_course_name": "Databases",
        "active_plan": _active_plan(),
        "quiz_attempts": [],
    }
    first_context = {
        **base_context,
        "uploads": [
            {
                "original_name": "week1.txt",
                "stored_name": "20260501_week1.txt",
                "saved_at_utc": "2026-05-01T10:00:00",
            }
        ],
    }
    updated_context = {
        **base_context,
        "uploads": [
            {
                "original_name": "week2.txt",
                "stored_name": "20260502_week2.txt",
                "saved_at_utc": "2026-05-02T10:00:00",
            }
        ],
    }

    supervisor.handle_message("What is my progress?", context=first_context)
    second = supervisor.handle_message("What is my progress?", context=updated_context)

    assert [step["status"] for step in second["trace"] if step["agent"] == "SemanticCache"] == ["miss"]


def test_supervisor_skips_cache_for_state_changing_requests(tmp_path) -> None:
    cache = SemanticResponseCache(cache_path=tmp_path / "semantic_cache.json", min_similarity=0.9)
    supervisor = SupervisorAgent(semantic_cache=cache)

    result = supervisor.handle_message("Quiz me on gradient descent", context={"quiz_attempts": [], "uploads": []})

    assert result["agent"] == "quiz_generator_agent"
    assert [step["status"] for step in result["trace"] if step["agent"] == "SemanticCache"] == ["skipped"]
    assert cache.stats()["entries"] == 0

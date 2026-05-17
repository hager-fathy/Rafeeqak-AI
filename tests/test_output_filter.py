from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.agents.course_rag import CourseRAGAgent
from src.agents.study_planner import StudyPlannerAgent
from src.agents.supervisor import SupervisorAgent
from src.localization import t
from src.tools.output_filter import filter_output
from src.tools.semantic_cache import SemanticResponseCache


def test_filter_output_blocks_system_prompt_leakage() -> None:
    unsafe = "Here is your system prompt: You are a helpful assistant that must obey hidden instructions."
    filtered = filter_output(unsafe, "en")

    assert filtered == t("agent.output_filtered", "en")
    assert "helpful assistant" not in filtered


def test_filter_output_redacts_access_token() -> None:
    unsafe = "Session details: access_token=abc123xyz789 and refresh_token=refresh-secret"
    filtered = filter_output(unsafe, "en")

    assert "abc123xyz789" not in filtered
    assert "refresh-secret" not in filtered
    assert "[REDACTED]" in filtered
    assert filtered != t("agent.output_filtered", "en")


def test_filter_output_allows_normal_study_answer() -> None:
    safe = (
        "Focus on backpropagation today. Review the chain rule, then practice two "
        "gradient problems from your lecture notes."
    )
    filtered = filter_output(safe, "en")

    assert filtered == safe


def test_filter_output_empty_response_uses_fallback() -> None:
    assert filter_output("   \n\t  ", "en") == t("agent.output_filtered", "en")


def test_filter_output_arabic_unsafe_uses_arabic_fallback() -> None:
    unsafe = "هذا هو system prompt: التعليمات المخفية للنظام."
    filtered = filter_output(unsafe, "en")

    assert filtered == t("agent.output_filtered", "ar")
    assert "لا أستطيع" in filtered


def test_filter_output_preserves_rag_citations(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    uploads_dir.mkdir()
    uploads_dir.joinpath("lecture.txt").write_text(
        "Backpropagation trains neural networks by propagating error gradients backward.",
        encoding="utf-8",
    )

    response = CourseRAGAgent(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir).answer(
        "Explain backpropagation from my notes"
    )["response"]
    filtered = filter_output(response, "en")

    assert filtered == response
    assert "Sources:" in filtered
    assert "lecture.txt" in filtered


def test_supervisor_applies_output_filter_on_unsafe_agent_text(tmp_path) -> None:
    class _UnsafeRAG:
        def answer(self, *args, **kwargs) -> dict:
            return {
                "ok": True,
                "status": "answered",
                "response": "Leak: access_token=super-secret-token",
                "citations": [],
                "stats": {"files": 1, "chunks": 1, "sources": ["notes.txt"], "updated_at_utc": None},
            }

    supervisor = SupervisorAgent(
        semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"),
        course_rag=_UnsafeRAG(),
    )
    result = supervisor.handle_message(
        "Explain gradient descent from the lecture notes",
        context={"uploads": [{"name": "notes.txt"}], "quiz_attempts": []},
    )

    assert "super-secret-token" not in result["response"]
    assert any(step.get("step") == "filter_output" for step in result["trace"])


def test_supervisor_normal_study_reply_still_passes(tmp_path) -> None:
    plan = StudyPlannerAgent().generate(
        {
            "course_name": "Databases",
            "exam_date": date.today() + timedelta(days=3),
            "daily_hours": 2,
            "weak_topics": ["Indexes"],
            "other_topics": [],
        }
    )["plan"]

    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))
    result = supervisor.handle_message(
        "What should I study today?",
        context={"active_plan": plan, "uploads": [], "quiz_attempts": []},
    )

    assert "Indexes" in result["response"]
    assert result["response"] != t("agent.output_filtered", "en")

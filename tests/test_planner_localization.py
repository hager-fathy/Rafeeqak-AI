from __future__ import annotations

from datetime import date, timedelta

from src.agents.study_planner import StudyPlannerAgent
from src.agents.supervisor import SupervisorAgent
from src.tools.planner_localization import (
    contains_english_planner_terms,
    format_study_recommendation,
    localize_planner_phase,
    localize_planner_task_text,
    localize_planner_topic,
)
from src.tools.semantic_cache import SemanticResponseCache
from src.tools.study_plan_tasks import apply_manual_completion_updates, build_task_id, is_task_completed


def _checkpoint_task_plan() -> dict:
    return {
        "course_name": "security",
        "exam_date": (date.today() + timedelta(days=5)).isoformat(),
        "tasks": [
            {
                "date": date.today().isoformat(),
                "topic": "Lecture 2",
                "phase": "Checkpoint quiz",
                "task": (
                    "Take a checkpoint quiz on Lecture 2, review wrong answers, "
                    "and update weak points before moving on. "
                    "Split the session between review, practice, and a short written summary."
                ),
                "hours": 2.2,
                "checkpoint": True,
                "quiz_required": True,
                "completed": False,
                "task_id": "task-lecture-2",
            }
        ],
    }


def test_localize_lecture_topic_to_arabic() -> None:
    assert localize_planner_topic("Lecture 2", "ar") == "المحاضرة الثانية"
    assert localize_planner_topic("Lecture 7", "ar") == "المحاضرة رقم 7"


def test_localize_phase_labels_to_arabic() -> None:
    assert localize_planner_phase("Checkpoint quiz", "ar") == "اختبار قصير"
    assert localize_planner_phase("Concept review", "ar") == "مراجعة المفاهيم"
    assert localize_planner_phase("Weak-topic practice", "ar") == "تدريب على نقاط الضعف"


def test_localize_checkpoint_task_description_to_arabic() -> None:
    text = (
        "Take a checkpoint quiz on Lecture 2, review wrong answers, "
        "and update weak points before moving on."
    )
    localized = localize_planner_task_text(text, "ar", topic="Lecture 2")
    assert "المحاضرة الثانية" in localized
    assert "اختبار قصير" in localized
    assert "الإجابات الخاطئة" in localized
    assert "نقاط الضعف" in localized
    assert "Lecture" not in localized
    assert "weak points" not in localized.casefold()


def test_format_study_recommendation_arabic_is_natural() -> None:
    plan = _checkpoint_task_plan()
    response = format_study_recommendation(plan["tasks"][0], "ar")
    assert response.startswith("اليوم ركّز على المحاضرة الثانية")
    assert "الهدف هو" in response
    assert "اختبار قصير" in response
    assert not contains_english_planner_terms(response)


def test_format_study_recommendation_english_unchanged() -> None:
    plan = _checkpoint_task_plan()
    response = format_study_recommendation(plan["tasks"][0], "en")
    assert "Today focus on Lecture 2" in response
    assert "checkpoint quiz" in response.casefold() or "Goal:" in response


def test_course_name_is_preserved_in_arabic_response() -> None:
    task = {
        "topic": "Backpropagation",
        "phase": "Weak-topic practice",
        "task": "Practice Backpropagation with new problems, explain each step aloud, and log any repeated mistakes.",
        "hours": 2,
    }
    response = format_study_recommendation(task, "ar")
    assert "Backpropagation" in response
    assert "Weak-topic practice" not in response


def test_supervisor_arabic_today_question_returns_arabic_only_planner_wording(tmp_path) -> None:
    plan = _checkpoint_task_plan()
    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))
    result = supervisor.handle_message(
        "اذاكر ايه النهارده؟",
        context={
            "active_plan": plan,
            "active_course_id": "course-security",
            "active_course_name": "security",
            "uploads": [],
            "quiz_attempts": [],
        },
    )

    assert result["language"] == "ar"
    assert result["agent"] == "study_planner_agent"
    assert "المحاضرة الثانية" in result["response"]
    assert not contains_english_planner_terms(result["response"])


def test_supervisor_skips_completed_task_in_arabic(tmp_path) -> None:
    plan = {
        "course_name": "security",
        "exam_date": (date.today() + timedelta(days=5)).isoformat(),
        "tasks": [
            {
                "date": date.today().isoformat(),
                "topic": "Lecture 2",
                "phase": "Concept review",
                "task": "Review the core ideas of Lecture 2, list key formulas or definitions, and solve one guided example.",
                "hours": 2.0,
                "completed": False,
            },
            {
                "date": (date.today() + timedelta(days=1)).isoformat(),
                "topic": "Lecture 3",
                "phase": "Concept review",
                "task": "Review the core ideas of Lecture 3, list key formulas or definitions, and solve one guided example.",
                "hours": 1.5,
                "completed": False,
            },
        ],
    }
    lecture_two_id = build_task_id(plan["tasks"][0], "course-security")
    apply_manual_completion_updates(
        plan,
        [{"task_id": lecture_two_id, "mark_as_done": True}],
        course_scope="course-security",
    )
    assert is_task_completed(plan["tasks"][0], plan)

    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))
    result = supervisor.handle_message(
        "اذاكر ايه النهارده؟",
        context={
            "active_plan": plan,
            "active_course_id": "course-security",
            "uploads": [],
            "quiz_attempts": [],
        },
    )

    assert "المحاضرة الثانية" not in result["response"]
    assert "المحاضرة الثالثة" in result["response"]


def test_generated_plan_arabic_recommendation_uses_translated_lecture(tmp_path) -> None:
    plan = StudyPlannerAgent().generate(
        {
            "course_name": "Machine Learning",
            "exam_date": date.today() + timedelta(days=4),
            "daily_hours": 2,
            "weak_topics": [],
            "other_topics": [],
            "language": "en",
        }
    )["plan"]
    first_topic = plan["tasks"][0]["topic"]
    response = StudyPlannerAgent().recommend_next(plan, language="ar")["response"]
    if str(first_topic).casefold().startswith("lecture"):
        assert localize_planner_topic(first_topic, "ar") in response

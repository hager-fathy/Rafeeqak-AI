from datetime import date, timedelta

from src.agents.study_planner import StudyPlannerAgent
from src.agents.supervisor import SupervisorAgent
from src.tools.semantic_cache import SemanticResponseCache
from src.tools.study_plan_tasks import (
    apply_manual_completion_updates,
    build_task_id,
    get_task_completions,
    is_quiz_task,
    is_task_completed,
    list_pending_tasks,
    make_task_id,
    mark_matching_quiz_task_completed,
    quiz_required_label,
    select_next_task,
    tasks_to_timeline_rows,
)
from src.tools.state import add_course, course_context, init_state, set_active_course, update_active_course_bucket
from src.ui.quiz_page import _record_attempt, _store_generated_quiz


def _sample_plan(*, course_scope: str = "course-a") -> dict:
    tasks = [
        {
            "date": "2026-05-01",
            "topic": "SVM",
            "phase": "Concept review",
            "task": "Review lecture notes",
            "hours": 2.0,
            "checkpoint": False,
            "completed": False,
        },
        {
            "date": "2026-05-02",
            "topic": "Neural Networks",
            "phase": "Checkpoint quiz",
            "task": "Take a checkpoint quiz on Neural Networks",
            "hours": 1.5,
            "checkpoint": True,
            "quiz_required": True,
            "completed": False,
        },
    ]
    for task in tasks:
        task["task_id"] = build_task_id(task, course_scope)
    return {"course_name": "Machine Learning", "exam_date": "2026-06-01", "tasks": tasks}


def test_is_quiz_task_detects_checkpoint_and_text() -> None:
    assert is_quiz_task({"checkpoint": True, "phase": "Study", "task": "Read notes"})
    assert is_quiz_task({"quiz_required": True, "phase": "Study", "task": "Read notes"})
    assert is_quiz_task({"phase": "Checkpoint quiz", "task": "Review"})
    assert is_quiz_task({"phase": "Study", "task": "Take a checkpoint quiz"})
    assert is_quiz_task({"task_type": "quiz", "phase": "Study", "task": "Practice"})
    assert not is_quiz_task({"phase": "Concept review", "task": "Summarize notes"})


def test_quiz_required_label_is_read_only_text() -> None:
    plan = _sample_plan()
    rows = tasks_to_timeline_rows(plan["tasks"], language="en", course_scope="course-a")
    assert rows[0]["quiz_required_label"] == "No quiz"
    assert rows[1]["quiz_required_label"] == "Quiz required"
    assert quiz_required_label(plan["tasks"][0], "en") == "No quiz"
    assert quiz_required_label(plan["tasks"][1], "en") == "Quiz required"


def test_manual_completion_updates_only_non_quiz_tasks() -> None:
    plan = _sample_plan()
    normal_id = plan["tasks"][0]["task_id"]
    quiz_id = plan["tasks"][1]["task_id"]

    changed = apply_manual_completion_updates(
        plan,
        [
            {"task_id": normal_id, "mark_as_done": True},
            {"task_id": quiz_id, "mark_as_done": True},
        ],
        course_scope="course-a",
    )

    assert changed is True
    assert plan["tasks"][0]["completed"] is True
    assert plan["tasks"][1]["completed"] is False


def test_manual_completion_uses_stable_task_id_not_row_order() -> None:
    plan = _sample_plan()
    normal_id = plan["tasks"][0]["task_id"]
    reordered_rows = [
        {"task_id": plan["tasks"][1]["task_id"], "mark_as_done": False},
        {"task_id": normal_id, "mark_as_done": True},
    ]

    apply_manual_completion_updates(plan, reordered_rows, course_scope="course-a")

    assert plan["tasks"][0]["completed"] is True


def test_quiz_submission_marks_matching_quiz_task_completed() -> None:
    plan = _sample_plan()
    changed = mark_matching_quiz_task_completed(plan, course_scope="course-a", topic="SVM")
    assert changed is True
    assert plan["tasks"][1]["completed"] is True
    assert plan["tasks"][0]["completed"] is False


def test_generating_quiz_does_not_mark_plan_task_completed() -> None:
    init_state()
    course = add_course("Machine Learning")
    plan = _sample_plan(course_scope=course["id"])
    update_active_course_bucket(active_plan=plan)

    _store_generated_quiz(
        quiz_result={
            "quiz": {"topic": "SVM", "language": "en", "questions": [{"question": "Q1"}]},
            "questions": [{"question": "Q1", "type": "mcq", "options": ["A"], "answer_index": 0}],
            "flashcards": [],
        },
        generation_request={
            "topic": "SVM",
            "count": 1,
            "language": "en",
            "difficulty": "medium",
            "question_types": ["mcq"],
            "course_id": course["id"],
            "course_name": course["name"],
        },
        context_chunks=[],
        previous_generated_questions=[],
    )

    active_plan = course_context()["active_plan"]
    assert active_plan["tasks"][1]["completed"] is False


def test_record_attempt_marks_quiz_task_completed() -> None:
    init_state()
    course = add_course("Machine Learning")
    plan = _sample_plan(course_scope=course["id"])
    update_active_course_bucket(active_plan=plan)

    class FakeMemoryAgent:
        def record_quiz_attempt(self, **kwargs) -> dict:
            return {"ok": False, "reason": "test"}

    _record_attempt(
        evaluation={
            "ok": True,
            "timestamp_utc": "2026-05-01T12:00:00",
            "topic": "SVM",
            "correct": 3,
            "total": 4,
            "score_percent": 75.0,
            "points_earned": 3.0,
            "total_points": 4.0,
            "feedback": [{"type": "mcq"}],
            "weak_topics": [],
            "recommendation": "Keep practicing",
        },
        quiz={"topic": "SVM", "difficulty": "medium", "questions": [{}]},
        active_plan=plan,
        active_course=course,
        memory_agent=FakeMemoryAgent(),
        student_email=None,
        student_name=None,
        language="en",
    )

    assert course_context()["active_plan"]["tasks"][1]["completed"] is True


def test_make_task_id_matches_build_task_id() -> None:
    task = {"date": "2026-05-01", "topic": "SVM", "phase": "Review", "task": "Read notes"}
    assert make_task_id("course-a", task) == build_task_id(task, "course-a")


def test_completion_map_is_shared_source_of_truth() -> None:
    plan = _sample_plan()
    task_id = plan["tasks"][0]["task_id"]
    get_task_completions(plan)[task_id] = True
    plan["tasks"][0]["completed"] = False

    assert is_task_completed(plan["tasks"][0], plan) is True
    pending_ids = {task["task_id"] for task in list_pending_tasks(plan, "course-a")}
    assert task_id not in pending_ids


def test_recommend_next_skips_completed_task(tmp_path) -> None:
    plan = _sample_plan()
    apply_manual_completion_updates(
        plan,
        [{"task_id": plan["tasks"][0]["task_id"], "mark_as_done": True}],
        course_scope="course-a",
    )

    result = StudyPlannerAgent().recommend_next(plan, course_scope="course-a")
    assert result["ok"] is True
    assert result["task"]["task_id"] == plan["tasks"][1]["task_id"]


def test_supervisor_today_prompt_skips_completed_task(tmp_path) -> None:
    plan = _sample_plan()
    plan["tasks"][0]["date"] = date.today().isoformat()
    apply_manual_completion_updates(
        plan,
        [{"task_id": plan["tasks"][0]["task_id"], "mark_as_done": True}],
        course_scope="course-a",
    )

    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))
    result = supervisor.handle_message(
        "What should I study today?",
        context={
            "active_plan": plan,
            "active_course_id": "course-a",
            "uploads": [],
            "quiz_attempts": [],
        },
    )

    assert result["agent"] == "study_planner_agent"
    assert plan["tasks"][0]["topic"] not in result["response"]
    assert "Neural Networks" in result["response"]


def test_select_next_task_prefers_today_when_available() -> None:
    plan = _sample_plan()
    today = date.today().isoformat()
    plan["tasks"][0]["date"] = today
    plan["tasks"][1]["date"] = (date.today() + timedelta(days=3)).isoformat()

    next_task = select_next_task(plan, "course-a", today_only=True)
    assert next_task is not None
    assert next_task["date"] == today


def test_completion_state_is_scoped_by_course_id() -> None:
    init_state()
    math = add_course("Math")
    physics = add_course("Physics")

    math_plan = _sample_plan(course_scope=math["id"])
    physics_plan = _sample_plan(course_scope=physics["id"])
    math_plan["tasks"][0]["completed"] = True

    set_active_course(math["id"])
    update_active_course_bucket(active_plan=math_plan)
    set_active_course(physics["id"])
    update_active_course_bucket(active_plan=physics_plan)

    set_active_course(math["id"])
    assert course_context()["active_plan"]["tasks"][0]["completed"] is True
    assert course_context()["active_plan"]["tasks"][1]["completed"] is False

    set_active_course(physics["id"])
    assert course_context()["active_plan"]["tasks"][0]["completed"] is False

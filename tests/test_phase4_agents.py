from datetime import date, timedelta

from src.agents.input_router import InputRouterAgent
from src.agents.reminder_agent import ReminderAgent
from src.agents.study_planner import StudyPlannerAgent
from src.agents.supervisor import SupervisorAgent
from src.tools.semantic_cache import SemanticResponseCache


class FakePlanLLM:
    is_available = True

    def generate_json(self, **kwargs) -> dict:
        today = date.today()
        return {
            "tasks": [
                {
                    "date": today.isoformat(),
                    "topic": "Indexes",
                    "phase": "LLM concept review",
                    "hours": 2,
                    "task": "Map index types to query patterns.",
                    "checkpoint": False,
                },
                {
                    "date": (today + timedelta(days=1)).isoformat(),
                    "topic": "Transactions",
                    "phase": "LLM checkpoint",
                    "hours": 2,
                    "task": "Practice isolation anomalies and take a quiz.",
                    "checkpoint": True,
                },
            ]
        }


def test_input_router_detects_study_plan_intent() -> None:
    routed = InputRouterAgent().route("What should I study today for my exam?")

    assert routed["intent"] == "study_plan"
    assert routed["language"] == "en"
    assert routed["confidence"] >= 0.72


def test_input_router_detects_arabic_language() -> None:
    routed = InputRouterAgent().route("اعمل خطة مراجعة للامتحان")

    assert routed["intent"] == "study_plan"
    assert routed["language"] == "ar"


def test_input_router_handles_general_chat_without_keyword_match() -> None:
    routed = InputRouterAgent().route("hello")

    assert routed["intent"] == "chat"
    assert routed["language"] == "en"
    assert routed["confidence"] == 0.35
    assert routed["signals"] == []


def test_input_router_detects_reminder_intent() -> None:
    routed = InputRouterAgent().route("Remind me to revise indexes tomorrow")

    assert routed["intent"] == "reminder"
    assert routed["language"] == "en"
    assert routed["confidence"] == 0.9


def test_reminder_agent_creates_plan_and_deadline_reminders() -> None:
    plan = StudyPlannerAgent().generate(
        {
            "course_name": "Databases",
            "exam_date": date.today() + timedelta(days=5),
            "daily_hours": 2,
            "weak_topics": ["Indexes"],
            "other_topics": ["Transactions"],
        }
    )["plan"]

    result = ReminderAgent().create(
        message="create reminders for this course",
        context={
            "active_course_id": "db-1",
            "active_course_name": "Databases",
            "active_plan": plan,
            "quiz_attempts": [],
            "reminders": [],
        },
    )

    reminder_types = {item["reminder_type"] for item in result["reminders"]}

    assert result["ok"] is True
    assert result["created_count"] >= 3
    assert {"study_task", "deadline", "quiz"} <= reminder_types
    assert all(item["course_id"] == "db-1" for item in result["reminders"])


def test_study_planner_generates_weighted_plan() -> None:
    result = StudyPlannerAgent().generate(
        {
            "course_name": "Machine Learning",
            "exam_date": date.today() + timedelta(days=4),
            "daily_hours": 2,
            "weak_topics": ["SVM"],
            "other_topics": ["Decision Trees"],
        }
    )

    plan = result["plan"]
    assert result["ok"] is True
    assert len(plan["tasks"]) == 4
    assert plan["tasks"][0]["topic"] == "SVM"
    assert plan["tasks"][1]["topic"] == "SVM"
    assert plan["tasks"][2]["checkpoint"] is True


def test_study_planner_creates_adaptive_task_phases() -> None:
    result = StudyPlannerAgent().generate(
        {
            "course_name": "Databases",
            "exam_date": date.today() + timedelta(days=6),
            "daily_hours": 4,
            "weak_topics": ["Indexes", "Transactions"],
            "other_topics": ["SQL"],
        }
    )

    tasks = result["plan"]["tasks"]
    phases = {task["phase"] for task in tasks}

    assert len(tasks) == 6
    assert "Weak-topic practice" in phases
    assert "Final review" in phases
    assert any("extra time" in task["task"] for task in tasks)
    assert any(task["checkpoint"] for task in tasks)


def test_study_planner_adds_recovery_and_planning_metadata() -> None:
    result = StudyPlannerAgent().generate(
        {
            "course_name": "Operating Systems",
            "exam_date": date.today() + timedelta(days=5),
            "daily_hours": 2,
            "difficulty": "hard",
            "lecture_count": 6,
            "finish_period_days": 3,
            "weak_topics": ["Scheduling"],
            "other_topics": ["Deadlocks"],
            "progress": {
                "completed_tasks": 2,
                "total_tasks": 5,
                "overdue_tasks": [
                    {"topic": "Processes", "date": (date.today() - timedelta(days=1)).isoformat(), "completed": False}
                ],
                "quiz_attempts": 2,
                "average_score": 62,
                "quiz_weak_topics": ["Scheduling"],
            },
        }
    )

    plan = result["plan"]
    assert plan["difficulty"] == "hard"
    assert plan["lecture_count"] == 6
    assert plan["finish_period_days"] == 3
    assert plan["delayed_task_count"] == 1
    assert plan["recovery_recommendations"]
    assert plan["progress_snapshot"]["completion_rate"] == 40.0
    assert plan["tasks"][0]["phase"] == "Recovery session"
    assert "Processes" in plan["tasks"][0]["task"]


def test_study_planner_uses_quiz_weak_topics_when_manual_topics_missing() -> None:
    result = StudyPlannerAgent().generate(
        {
            "course_name": "Networks",
            "exam_date": date.today() + timedelta(days=4),
            "daily_hours": 1.5,
            "lecture_count": 4,
            "finish_period_days": 2,
            "weak_topics": [],
            "other_topics": ["Routing"],
            "progress": {
                "quiz_weak_topics": ["Subnetting", "Routing"],
                "quiz_attempts": 1,
                "average_score": 58,
            },
        }
    )

    plan = result["plan"]
    assert plan["weak_topics"][0] == "Subnetting"
    assert plan["tasks"][0]["topic"] == "Subnetting"


def test_study_planner_uses_llm_when_available() -> None:
    result = StudyPlannerAgent(llm_client=FakePlanLLM()).generate(
        {
            "course_name": "Databases",
            "exam_date": date.today() + timedelta(days=2),
            "daily_hours": 2,
            "weak_topics": ["Indexes"],
            "other_topics": ["Transactions"],
            "lecture_count": 5,
            "finish_period_days": 2,
        }
    )

    plan = result["plan"]
    assert result["generation_mode"] == "llm"
    assert plan["generation_mode"] == "llm"
    assert plan["tasks"][0]["phase"] == "LLM concept review"
    assert plan["tasks"][1]["checkpoint"] is True


def test_supervisor_runs_traceable_study_plan_route(tmp_path) -> None:
    plan = StudyPlannerAgent().generate(
        {
            "course_name": "Machine Learning",
            "exam_date": date.today() + timedelta(days=3),
            "daily_hours": 2,
            "weak_topics": ["Backpropagation"],
            "other_topics": [],
        }
    )["plan"]

    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))
    result = supervisor.handle_message(
        "What should I study today?",
        context={"active_plan": plan, "uploads": [], "quiz_attempts": []},
    )

    agents = [step["agent"] for step in result["trace"]]
    assert result["agent"] == "study_planner_agent"
    assert "Backpropagation" in result["response"]
    assert agents == [
        "SafetyAgent",
        "InputRouterAgent",
        "SupervisorAgent",
        "SemanticCache",
        "StudyPlannerAgent",
        "ResponseAgent",
    ]


def test_supervisor_replies_in_arabic_for_arabic_study_plan_request(tmp_path) -> None:
    plan = StudyPlannerAgent().generate(
        {
            "course_name": "Machine Learning",
            "exam_date": date.today() + timedelta(days=3),
            "daily_hours": 2,
            "weak_topics": ["Backpropagation"],
            "other_topics": [],
        }
    )["plan"]

    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))
    result = supervisor.handle_message(
        "ماذا أذاكر اليوم؟",
        context={"active_plan": plan, "uploads": [], "quiz_attempts": []},
    )

    assert result["language"] == "ar"
    assert result["agent"] == "study_planner_agent"
    assert "اليوم رك" in result["response"]
    assert "Backpropagation" in result["response"]


def test_supervisor_replies_in_arabic_for_general_arabic_chat(tmp_path) -> None:
    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))
    result = supervisor.handle_message("مرحبا")

    assert result["language"] == "ar"
    assert result["agent"] == "response_agent"
    assert "أنا جاهز" in result["response"]


def test_supervisor_uses_selected_language_for_english_input(tmp_path) -> None:
    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))
    result = supervisor.handle_message("hello", context={"selected_language": "ar"})

    assert result["language"] == "ar"
    assert "أنا جاهز" in result["response"]


def test_supervisor_creates_plan_and_skips_missing_memory() -> None:
    result = SupervisorAgent().create_study_plan(
        {
            "course_name": "Machine Learning",
            "exam_date": date.today() + timedelta(days=2),
            "daily_hours": 1.5,
            "weak_topics": ["SVM"],
            "other_topics": ["Regression"],
        }
    )

    assert result["ok"] is True
    assert result["sync_result"]["ok"] is False
    assert result["trace"][-1]["agent"] == "MemoryAgent"


def test_supervisor_runs_reminder_agent_without_cache(tmp_path) -> None:
    plan = StudyPlannerAgent().generate(
        {
            "course_name": "Machine Learning",
            "exam_date": date.today() + timedelta(days=3),
            "daily_hours": 2,
            "weak_topics": ["Backpropagation"],
            "other_topics": [],
        }
    )["plan"]
    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))

    result = supervisor.handle_message(
        "Remind me to review backpropagation tomorrow",
        context={
            "active_course_id": "ml-1",
            "active_course_name": "Machine Learning",
            "active_plan": plan,
            "quiz_attempts": [],
            "reminders": [],
            "require_active_course": True,
        },
    )

    agents = [step["agent"] for step in result["trace"]]
    cache_step = next(step for step in result["trace"] if step["step"] == "cache_lookup")

    assert result["agent"] == "reminder_agent"
    assert "Reminder plan updated" in result["response"]
    assert "ReminderAgent" in agents
    assert cache_step["status"] == "skipped"
    assert result["payload"]["reminders"]

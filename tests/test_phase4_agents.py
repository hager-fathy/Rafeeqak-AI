from datetime import date, timedelta

from src.agents.input_router import InputRouterAgent
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


def test_study_planner_uses_llm_when_available() -> None:
    result = StudyPlannerAgent(llm_client=FakePlanLLM()).generate(
        {
            "course_name": "Databases",
            "exam_date": date.today() + timedelta(days=2),
            "daily_hours": 2,
            "weak_topics": ["Indexes"],
            "other_topics": ["Transactions"],
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
    assert "اليوم ركز" in result["response"]
    assert "Backpropagation" in result["response"]


def test_supervisor_replies_in_arabic_for_general_arabic_chat(tmp_path) -> None:
    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))
    result = supervisor.handle_message("مرحبا")

    assert result["language"] == "ar"
    assert result["agent"] == "response_agent"
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

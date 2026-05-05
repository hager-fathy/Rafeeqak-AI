from datetime import date, timedelta

from src.agents.input_router import InputRouterAgent
from src.agents.study_planner import StudyPlannerAgent
from src.agents.supervisor import SupervisorAgent


def test_input_router_detects_study_plan_intent() -> None:
    routed = InputRouterAgent().route("What should I study today for my exam?")

    assert routed["intent"] == "study_plan"
    assert routed["language"] == "en"
    assert routed["confidence"] >= 0.72


def test_input_router_detects_arabic_language() -> None:
    routed = InputRouterAgent().route("اعمل خطة مراجعة للامتحان")

    assert routed["intent"] == "study_plan"
    assert routed["language"] == "ar"


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


def test_supervisor_runs_traceable_study_plan_route() -> None:
    plan = StudyPlannerAgent().generate(
        {
            "course_name": "Machine Learning",
            "exam_date": date.today() + timedelta(days=3),
            "daily_hours": 2,
            "weak_topics": ["Backpropagation"],
            "other_topics": [],
        }
    )["plan"]

    result = SupervisorAgent().handle_message(
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
        "StudyPlannerAgent",
        "ResponseAgent",
    ]


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

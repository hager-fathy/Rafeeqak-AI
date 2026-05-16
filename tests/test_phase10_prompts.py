from datetime import date, timedelta

from src.agents.course_rag import CourseRAGAgent
from src.agents.quiz_generator import QuizGeneratorAgent
from src.agents.study_planner import StudyPlannerAgent
from src.prompts import available_templates, render_prompt, required_variables
from src.retrieval import CourseMaterialIndexer


class CapturingTextLLM:
    is_available = True

    def __init__(self) -> None:
        self.calls = []

    def generate_text(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return "LLM answer\n\nSources: [1]"


class CapturingQuizLLM:
    is_available = True

    def __init__(self) -> None:
        self.calls = []

    def generate_json(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {
            "questions": [
                {
                    "question": "What is gradient descent?",
                    "options": ["Optimizer", "Database", "Protocol", "Diagram"],
                    "answer_index": 0,
                    "explanation": "It optimizes model weights.",
                    "source": "notes",
                }
            ],
            "flashcards": [{"front": "Gradient descent", "back": "Optimization method"}],
        }


class CapturingPlanLLM:
    is_available = True

    def __init__(self) -> None:
        self.calls = []

    def generate_json(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        today = date.today()
        return {
            "tasks": [
                {
                    "date": today.isoformat(),
                    "topic": "Backpropagation",
                    "phase": "Concept review",
                    "hours": 2,
                    "task": "Review gradients and solve one example.",
                    "checkpoint": False,
                },
                {
                    "date": (today + timedelta(days=1)).isoformat(),
                    "topic": "Backpropagation",
                    "phase": "Checkpoint",
                    "hours": 2,
                    "task": "Take a short quiz.",
                    "checkpoint": True,
                },
            ]
        }


def test_required_phase10_templates_render() -> None:
    expected = {
        "course_question",
        "rag_answer",
        "lecture_summary",
        "quiz_generation",
        "progress_feedback",
        "study_planning",
    }

    assert set(available_templates()) == expected

    values = {
        "course_name": "Machine Learning",
        "question": "What is overfitting?",
        "language": "English",
        "context": "[1] notes",
        "citations": "[1]",
        "lecture_title": "Generalization",
        "lecture_text": "Bias, variance, and validation.",
        "topic": "Backpropagation",
        "difficulty": "medium",
        "number_of_questions": 3,
        "question_types": "mcq",
        "avoid_questions": "None.",
        "score": "70%",
        "weak_topics": "gradients",
        "recommendations": "practice chain rule",
        "exam_deadline": "2026-06-01",
        "daily_hours": 2,
        "lecture_count": 8,
        "finish_period": "5 day(s)",
        "progress": "No recorded progress yet.",
    }
    for template_name in expected:
        prompt = render_prompt(
            template_name,
            **{name: values[name] for name in required_variables(template_name)},
        )
        assert prompt.system
        assert prompt.user
        assert "{{" not in prompt.system + prompt.user


def test_rag_agent_uses_rag_prompt_template(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    course_dir = uploads_dir / "ml"
    course_dir.mkdir(parents=True)
    (course_dir / "lecture.txt").write_text("Backpropagation uses gradients to update weights.", encoding="utf-8")
    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    indexer.index_all(course_id="ml", course_name="Machine Learning")

    llm = CapturingTextLLM()
    result = CourseRAGAgent(
        uploads_dir=uploads_dir,
        vector_store_dir=vector_store_dir,
        llm_client=llm,
    ).answer("What uses gradients?", course_id="ml", course_name="Machine Learning")

    assert result["generation_mode"] == "llm"
    assert "Retrieved context" in llm.calls[0]["user_prompt"]
    assert "Available source labels" in llm.calls[0]["user_prompt"]
    assert "Machine Learning" in llm.calls[0]["user_prompt"]


def test_quiz_and_study_planner_use_prompt_templates() -> None:
    quiz_llm = CapturingQuizLLM()
    quiz = QuizGeneratorAgent(llm_client=quiz_llm).generate(
        topic="Gradient Descent",
        count=1,
        context_chunks=[
            {
                "course_name": "Machine Learning",
                "source_name": "notes.txt",
                "section": "text",
                "text": "Gradient descent updates model weights.",
            }
        ],
    )

    assert quiz["generation_mode"] == "llm"
    assert "Question types: mcq" in quiz_llm.calls[0]["user_prompt"]
    assert "Machine Learning" in quiz_llm.calls[0]["user_prompt"]
    assert "Previous questions to avoid" in quiz_llm.calls[0]["user_prompt"]

    plan_llm = CapturingPlanLLM()
    plan = StudyPlannerAgent(llm_client=plan_llm).generate(
        {
            "course_name": "Machine Learning",
            "exam_date": date.today() + timedelta(days=2),
            "daily_hours": 2,
            "weak_topics": ["Backpropagation"],
            "other_topics": ["Linear Regression"],
            "difficulty": "hard",
            "lecture_count": 8,
            "finish_period_days": 2,
            "language": "en",
        }
    )

    assert plan["generation_mode"] == "llm"
    assert "Difficulty: hard" in plan_llm.calls[0]["user_prompt"]
    assert "Lecture count: 8" in plan_llm.calls[0]["user_prompt"]
    assert "Finish lectures in: 2 day(s)" in plan_llm.calls[0]["user_prompt"]
    assert "Weak topics: Backpropagation" in plan_llm.calls[0]["user_prompt"]

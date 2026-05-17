from datetime import date, timedelta

from src.agents.course_rag import CourseRAGAgent
from src.agents.memory_agent import MemoryAgent
from src.agents.quiz_generator import QuizGeneratorAgent
from src.agents.reminder_agent import ReminderAgent
from src.agents.study_planner import StudyPlannerAgent
from src.prompts import available_templates, build_system_prompt, render_prompt, required_variables
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


class CapturingSummaryLLM:
    is_available = True

    def __init__(self) -> None:
        self.calls = []

    def generate_json(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {
            "main_topics": ["Backpropagation", "Chain rule"],
            "weaknesses": ["Backpropagation"],
            "next_steps": ["Review one worked gradient example."],
            "summary": "Machine Learning summary: backpropagation was discussed with a weakness signal.",
        }


class CapturingReminderLLM:
    is_available = True

    def __init__(self) -> None:
        self.calls = []

    def generate_json(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        due_at = (date.today() + timedelta(days=2)).isoformat() + "T18:00"
        return {
            "reminders": [
                {
                    "reminder_type": "quiz",
                    "title": "Practice backpropagation weak-topic quiz",
                    "due_at": due_at,
                    "topic": "Backpropagation",
                }
            ]
        }


def test_required_phase10_templates_render() -> None:
    expected = {
        "chat_session_summary",
        "course_question",
        "rag_answer",
        "lecture_summary",
        "quiz_generation",
        "progress_feedback",
        "reminder_generation",
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
        "messages": "user: I am confused about backpropagation.",
        "main_topics": "Backpropagation",
        "weaknesses": "Backpropagation",
        "next_steps": "Practice one example.",
        "topic": "Backpropagation",
        "difficulty": "medium",
        "difficulty_description": "test application and misconceptions",
        "number_of_questions": 3,
        "question_types": "mcq",
        "type_instructions": "- MCQ: exactly four choices.",
        "avoid_questions": "None.",
        "grounding_instructions": "Use only the provided selected-course context.",
        "score": "70%",
        "weak_topics": "gradients",
        "recommendations": "practice chain rule",
        "exam_deadline": "2026-06-01",
        "daily_hours": 2,
        "lecture_count": 8,
        "finish_period": "5 day(s)",
        "progress": "No recorded progress yet.",
        "tasks": "2026-06-01: Review lecture 1",
        "deadlines": "Exam deadline: 2026-06-10",
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
    assert "Rafeeqak" in llm.calls[0]["system_prompt"]
    assert "Course ID   : ml" in llm.calls[0]["system_prompt"]
    assert "SOURCE MATERIAL RULES" in llm.calls[0]["system_prompt"]
    assert "📄 Machine Learning | lecture.txt | Page/Chunk: text/chunk 1" in llm.calls[0]["system_prompt"]


def test_chatbot_system_prompt_renders_runtime_context() -> None:
    prompt = build_system_prompt(
        course_name="Databases",
        course_id="db-1",
        language="English",
        memory="Pending tasks: 2\nWeak topics: Indexes",
        context="[1] 📄 Databases | notes.pdf | Page/Chunk: page 4\nB-tree indexes balance search paths.",
    )

    assert "Course name : Databases" in prompt
    assert "Course ID   : db-1" in prompt
    assert "Pending tasks: 2" in prompt
    assert "B-tree indexes balance search paths." in prompt
    assert "{file_name}" in prompt
    assert "{{" not in prompt


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


def test_chat_summary_uses_prompt_template() -> None:
    summary_llm = CapturingSummaryLLM()
    result = MemoryAgent(llm_client=summary_llm).summarize_chat_session(
        course_id="ml-1",
        course_name="Machine Learning",
        messages=[
            {"role": "user", "content": "I am confused about backpropagation mistakes."},
            {"role": "assistant", "content": "Review the chain rule."},
        ],
        language="en",
        sync_cloud=False,
    )

    assert result["summary"]["source"] == "llm_session_summary"
    assert result["summary"]["main_topics"] == ["Backpropagation", "Chain rule"]
    assert "Conversation messages" in summary_llm.calls[0]["user_prompt"]
    assert "Machine Learning" in summary_llm.calls[0]["user_prompt"]


def test_reminder_agent_uses_generation_prompt_template() -> None:
    reminder_llm = CapturingReminderLLM()
    plan = {
        "course_name": "Machine Learning",
        "exam_date": (date.today() + timedelta(days=5)).isoformat(),
        "weak_topics": ["Backpropagation"],
        "tasks": [
            {
                "date": (date.today() + timedelta(days=1)).isoformat(),
                "topic": "Backpropagation",
                "phase": "Weak-topic practice",
                "task": "Review gradients and solve one example.",
                "checkpoint": True,
                "completed": False,
            }
        ],
    }

    result = ReminderAgent(llm_client=reminder_llm).create(
        message="create reminders",
        context={
            "active_course_id": "ml-1",
            "active_course_name": "Machine Learning",
            "active_plan": plan,
            "quiz_attempts": [],
            "reminders": [],
        },
    )

    assert result["llm_generated_count"] == 1
    assert any(item["source"] == "llm_reminder_generation" for item in result["reminders"])
    assert "Tasks:" in reminder_llm.calls[0]["user_prompt"]
    assert "Deadlines:" in reminder_llm.calls[0]["user_prompt"]
    assert "Backpropagation" in reminder_llm.calls[0]["user_prompt"]

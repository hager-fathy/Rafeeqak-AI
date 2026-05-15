from src.agents.progress_evaluator import ProgressEvaluatorAgent
from src.agents.quiz_generator import QuizGeneratorAgent
from src.agents.supervisor import SupervisorAgent
from src.tools.semantic_cache import SemanticResponseCache


def test_quiz_generator_creates_topic_questions_and_flashcards() -> None:
    result = QuizGeneratorAgent().generate(
        topic="Backpropagation",
        count=3,
        context_chunks=[
            {
                "source_name": "lecture.txt",
                "section": "text",
                "text": "Backpropagation computes gradients by applying the chain rule through layers.",
            }
        ],
    )

    assert result["ok"] is True
    assert result["status"] == "generated"
    assert result["count"] == 3
    assert len(result["questions"]) == 3
    assert result["flashcards"]
    assert result["questions"][0]["source"] == "lecture.txt (text)"
    for question in result["questions"]:
        assert len(question["options"]) == 4
        assert 0 <= question["answer_index"] < 4


def test_progress_evaluator_scores_answers_and_flags_weak_topic() -> None:
    quiz = QuizGeneratorAgent().generate(topic="SVM", count=2)["quiz"]
    questions = quiz["questions"]
    selected_indices = [
        questions[0]["answer_index"],
        (questions[1]["answer_index"] + 1) % len(questions[1]["options"]),
    ]

    result = ProgressEvaluatorAgent().evaluate(
        questions=questions,
        selected_indices=selected_indices,
        topic=quiz["topic"],
    )

    assert result["ok"] is True
    assert result["correct"] == 1
    assert result["total"] == 2
    assert result["score_percent"] == 50.0
    assert result["weak_topics"][0]["topic"] == "SVM"
    assert result["feedback"][1]["is_correct"] is False


def test_progress_evaluator_uses_arabic_feedback_text() -> None:
    quiz = QuizGeneratorAgent().generate(topic="قواعد البيانات", count=1, language="ar")["quiz"]
    result = ProgressEvaluatorAgent().evaluate(
        questions=quiz["questions"],
        selected_indices=[quiz["questions"][0]["answer_index"]],
        topic=quiz["topic"],
        language="ar",
    )

    assert result["ok"] is True
    assert "درجتك" in result["summary"]


def test_supervisor_quiz_route_generates_quiz_payload(tmp_path) -> None:
    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))
    result = supervisor.handle_message("Quiz me on gradient descent")

    assert result["agent"] == "quiz_generator_agent"
    assert result["payload"]["ok"] is True
    assert result["payload"]["topic"] == "gradient descent"
    assert len(result["payload"]["quiz"]["questions"]) == 5
    assert result["trace"][-2]["agent"] == "QuizGeneratorAgent"

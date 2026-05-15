from src.agents.progress_evaluator import ProgressEvaluatorAgent
from src.agents.quiz_generator import QuizGeneratorAgent
from src.agents.supervisor import SupervisorAgent
from src.retrieval import CourseMaterialIndexer
from src.tools.semantic_cache import SemanticResponseCache
from src.tools.state import _normalize_course_bucket
from src.ui.quiz_page import (
    _can_retry_quiz_generation,
    _current_quiz,
    _quiz_generation_request,
    _quiz_generation_status,
    _quiz_generation_status_payload,
    _retry_quiz_generation_request,
    generate_quiz_from_course_materials,
)


class FakeQuizLLM:
    is_available = True

    def generate_json(self, **kwargs) -> dict:
        return {
            "questions": [
                {
                    "question": "Which rule is central to backpropagation?",
                    "options": ["Chain rule", "Bayes rule", "Sorting rule", "Voting rule"],
                    "answer_index": 0,
                    "explanation": "Backpropagation applies the chain rule through layers.",
                    "source": "llm",
                },
                {
                    "question": "What does backpropagation compute?",
                    "options": ["Gradients", "File paths", "Usernames", "Deadlines"],
                    "answer_index": 0,
                    "explanation": "It computes gradients for model parameters.",
                    "source": "llm",
                },
            ],
            "flashcards": [{"front": "Backpropagation", "back": "Computes gradients through layers."}],
        }


class DuplicateQuizLLM:
    is_available = True

    def generate_json(self, **kwargs) -> dict:
        return {
            "questions": [
                {
                    "question": "Repeated question?",
                    "options": ["A", "B", "C", "D"],
                    "answer_index": 0,
                    "explanation": "duplicate",
                    "source": "llm",
                }
            ],
            "flashcards": [],
        }


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


def test_quiz_generator_honors_large_question_count() -> None:
    result = QuizGeneratorAgent().generate(topic="Backpropagation", count=12)

    assert result["count"] == 12
    assert len(result["questions"]) == 12


def test_quiz_generator_clamps_extreme_question_count() -> None:
    result = QuizGeneratorAgent().generate(topic="Backpropagation", count=50)

    assert result["count"] == 20
    assert len(result["questions"]) == 20


def test_quiz_generator_supports_difficulty_types_and_repeat_avoidance() -> None:
    first = QuizGeneratorAgent().generate(
        topic="Backpropagation",
        count=4,
        difficulty="hard",
        question_types=["mcq", "true_false", "short_answer", "matching"],
    )
    previous = [question["question"] for question in first["questions"]]
    second = QuizGeneratorAgent().generate(
        topic="Backpropagation",
        count=4,
        difficulty="hard",
        question_types=["mcq", "true_false", "short_answer", "matching"],
        previous_questions=previous,
    )

    assert first["quiz"]["difficulty"] == "hard"
    assert {question["type"] for question in first["questions"]} == {
        "mcq",
        "true_false",
        "short_answer",
        "matching",
    }
    assert not set(previous) & {question["question"] for question in second["questions"]}


def test_quiz_generator_uses_llm_when_available() -> None:
    result = QuizGeneratorAgent(llm_client=FakeQuizLLM()).generate(topic="Backpropagation", count=2)

    assert result["generation_mode"] == "llm"
    assert result["count"] == 2
    assert result["questions"][0]["id"] == "llm-1"
    assert result["flashcards"][0]["front"] == "Backpropagation"


def test_quiz_generator_falls_back_when_llm_output_is_incomplete() -> None:
    result = QuizGeneratorAgent(llm_client=DuplicateQuizLLM()).generate(
        topic="Backpropagation",
        count=2,
        previous_questions=["Repeated question?"],
    )

    assert result["generation_mode"] == "offline_template"
    assert result["count"] == 2
    assert all(question["question"] != "Repeated question?" for question in result["questions"])


def test_quiz_generator_deduplicates_context_chunks() -> None:
    result = QuizGeneratorAgent().generate(
        topic="SOC tiers",
        count=2,
        context_chunks=[
            {
                "source_name": "soc.pdf",
                "section": "page 1",
                "text": "SOC tiers divide analyst responsibilities into escalating levels.",
            },
            {
                "source_name": "soc.pdf",
                "section": "page 1",
                "text": "SOC tiers divide analyst responsibilities into escalating levels.",
            },
        ],
    )

    assert result["quiz"]["source_count"] == 1
    assert result["questions"][0]["source"] == "soc.pdf (page 1)"


def test_quiz_page_requires_uploaded_materials(tmp_path) -> None:
    indexer = CourseMaterialIndexer(
        uploads_dir=tmp_path / "uploads",
        vector_store_dir=tmp_path / "vector_store",
    )

    result = generate_quiz_from_course_materials(
        indexer=indexer,
        quiz_generator=QuizGeneratorAgent(),
        topic="information retrieval",
        count=4,
        language="en",
        difficulty="medium",
        question_types=["mcq"],
        previous_questions=[],
        course_id="ir-1",
        course_name="Information Retrieval",
    )

    assert result["ok"] is False
    assert result["reason"] == "materials_required"


def test_quiz_page_generates_only_from_matching_uploaded_materials(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    course_dir = uploads_dir / "ir-1"
    course_dir.mkdir(parents=True)
    (course_dir / "ir_notes.txt").write_text(
        "Information retrieval uses inverted indexes to map terms to documents for efficient search.",
        encoding="utf-8",
    )
    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=tmp_path / "vector_store")

    result = generate_quiz_from_course_materials(
        indexer=indexer,
        quiz_generator=QuizGeneratorAgent(),
        topic="inverted indexes",
        count=3,
        language="en",
        difficulty="medium",
        question_types=["mcq"],
        previous_questions=[],
        course_id="ir-1",
        course_name="Information Retrieval",
    )

    assert result["ok"] is True
    assert result["context_chunks"]
    assert result["quiz_result"]["quiz"]["source_count"] >= 1
    assert result["quiz_result"]["questions"][0]["source"] == "ir_notes.txt (text)"


def test_quiz_page_rejects_topics_not_found_in_uploaded_materials(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    course_dir = uploads_dir / "ir-1"
    course_dir.mkdir(parents=True)
    (course_dir / "ir_notes.txt").write_text(
        "Information retrieval uses inverted indexes and ranking models.",
        encoding="utf-8",
    )
    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=tmp_path / "vector_store")

    result = generate_quiz_from_course_materials(
        indexer=indexer,
        quiz_generator=QuizGeneratorAgent(),
        topic="neural backpropagation",
        count=3,
        language="en",
        difficulty="medium",
        question_types=["mcq"],
        previous_questions=[],
        course_id="ir-1",
        course_name="Information Retrieval",
    )

    assert result["ok"] is False
    assert result["reason"] == "material_match_required"


def test_current_quiz_uses_fresh_generation_fallback() -> None:
    fallback = {
        "topic": "inverted indexes",
        "language": "en",
        "questions": [{"question": "What is an inverted index?", "options": ["A"], "answer_index": 0}],
        "flashcards": [],
        "source_count": 1,
    }

    assert _current_quiz(fallback=fallback) == fallback


def test_quiz_generation_status_payload_supports_retry() -> None:
    request = _quiz_generation_request(
        topic="inverted indexes",
        count=4,
        language="en",
        difficulty="medium",
        question_types=["mcq", "short_answer"],
        course_id="ir-1",
        course_name="Information Retrieval",
    )
    failed_status = _quiz_generation_status_payload(
        "failed",
        request=request,
        reason="material_match_required",
        stats={"chunks": 3},
    )

    assert _quiz_generation_status(failed_status)["status"] == "failed"
    assert _can_retry_quiz_generation(failed_status) is True
    assert _retry_quiz_generation_request(failed_status) == request


def test_quiz_generation_status_rejects_invalid_retry_payload() -> None:
    invalid_status = {
        "status": "failed",
        "request": {
            "topic": "inverted indexes",
            "count": "not-a-number",
            "language": "en",
            "difficulty": "medium",
            "question_types": ["mcq"],
        },
    }

    assert _retry_quiz_generation_request(invalid_status) is None
    assert _can_retry_quiz_generation(invalid_status) is False


def test_course_bucket_preserves_quiz_generation_status() -> None:
    status = _quiz_generation_status_payload(
        "generated",
        request=_quiz_generation_request(
            topic="inverted indexes",
            count=2,
            language="en",
            difficulty="easy",
            question_types=["mcq"],
            course_id="ir-1",
            course_name="Information Retrieval",
        ),
        source_count=2,
        question_count=2,
    )

    normalized = _normalize_course_bucket({"quiz_generation_status": status})

    assert normalized["quiz_generation_status"] == status


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


def test_progress_evaluator_partial_scores_text_and_matching_answers() -> None:
    quiz = QuizGeneratorAgent().generate(
        topic="Backpropagation",
        count=2,
        question_types=["short_answer", "matching"],
    )["quiz"]
    short_answer, matching = quiz["questions"]
    partial_matching = dict(matching["answer_map"])
    first_key = next(iter(partial_matching))
    partial_matching[first_key] = "wrong"

    result = ProgressEvaluatorAgent().evaluate(
        questions=quiz["questions"],
        answers=["Backpropagation uses gradients", partial_matching],
        topic=quiz["topic"],
    )

    assert result["ok"] is True
    assert 0 < result["points_earned"] < result["total_points"]
    assert any(item["partial_credit"] for item in result["feedback"])


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

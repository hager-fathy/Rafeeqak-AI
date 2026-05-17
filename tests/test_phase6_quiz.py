import streamlit as st

from src.agents.progress_evaluator import ProgressEvaluatorAgent
from src.agents.quiz_generator import QuizGeneratorAgent
from src.agents.supervisor import SupervisorAgent
from src.retrieval import CourseMaterialIndexer
from src.tools.quiz_history import (
    append_quiz_history,
    normalize_question_text,
    quiz_history_avoid_questions,
    quiz_history_scope,
)
from src.tools.semantic_cache import SemanticResponseCache
from src.tools.state import add_course, course_context, init_state, _normalize_course_bucket
from src.ui.quiz_page import (
    _active_quiz,
    _can_retry_quiz_generation,
    _quiz_generation_request,
    _quiz_generation_status,
    _quiz_generation_status_payload,
    _record_attempt,
    _retry_quiz_generation_request,
    _store_generated_quiz,
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


class InvalidQuizLLM:
    is_available = True

    def generate_json(self, **kwargs) -> dict | None:
        return None


class MixedQuizLLM:
    is_available = True

    def __init__(self) -> None:
        self.calls = []

    def generate_json(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {
            "questions": [
                {
                    "type": "mcq",
                    "question": "Which structure maps terms to document lists?",
                    "choices": ["Inverted index", "Loss curve", "Confusion matrix", "Stack frame"],
                    "correct_choice": "Inverted index",
                    "hint": "Think about term lookup.",
                    "concept": "Term document mapping",
                    "explanation": "The index maps terms to postings lists.",
                    "source": "notes",
                },
                {
                    "type": "true_false",
                    "question": "A postings list can store document identifiers for a term.",
                    "correct_answer": True,
                    "hint": "Focus on what postings contain.",
                    "concept": "Postings list contents",
                    "source": "notes",
                },
                {
                    "type": "short_answer",
                    "question": "How does a term lookup structure speed retrieval?",
                    "expected_answer": "It maps each term to candidate documents so search can avoid scanning every document.",
                    "keywords": ["term", "candidate", "documents", "scanning"],
                    "hint": "Name the lookup shortcut.",
                    "concept": "Efficient term lookup",
                    "source": "notes",
                },
                {
                    "type": "matching",
                    "question": "Match each retrieval concept to its role.",
                    "pairs": [
                        {"left": "Term", "right": "Search token"},
                        {"left": "Posting", "right": "Document reference"},
                    ],
                    "hint": "Pair item to role.",
                    "concept": "Retrieval concept roles",
                    "source": "notes",
                },
            ],
            "flashcards": [],
        }


class ShortAnswerDictLLM:
    is_available = True

    def generate_json(self, **kwargs) -> dict:
        return {
            "questions": {
                "type": "short_answer",
                "question": "Why does ranking use relevance signals?",
                "correct_answer": "Relevance signals help order documents by expected usefulness.",
                "concept": "Ranking relevance signals",
                "hint": "Think about ordering results.",
            }
        }


class CapturingWeakQuizLLM(FakeQuizLLM):
    def __init__(self) -> None:
        self.calls = []

    def generate_json(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return super().generate_json(**kwargs)


class FakeMemoryAgent:
    def __init__(self) -> None:
        self.calls = []

    def record_quiz_attempt(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return {"ok": False, "reason": "local test memory"}


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


def test_quiz_generator_normalizes_variant_suffixes_for_duplicate_prevention() -> None:
    agent = QuizGeneratorAgent()
    first = agent.generate(topic="Backpropagation", count=1)
    first_question = first["questions"][0]["question"]
    second = agent.generate(
        topic="Backpropagation",
        count=1,
        avoid_questions=[f"  {first_question.upper()}   (variant 1)"],
    )

    assert normalize_question_text(first_question) not in {
        normalize_question_text(question["question"]) for question in second["questions"]
    }
    assert all("(variant" not in question["question"].lower() for question in second["questions"])


def test_quiz_history_is_scoped_by_course_and_topic() -> None:
    history = append_quiz_history(
        {},
        course_id="course-a",
        topic="Lecture 1",
        questions=[{"question": "What is indexing?"}],
    )

    assert quiz_history_scope("course-a", "Lecture 1") in history["scopes"]
    assert quiz_history_avoid_questions(history, course_id="course-a", topic="Lecture 1") == [
        "What is indexing?"
    ]
    assert quiz_history_avoid_questions(history, course_id="course-a", topic="Lecture 2") == []
    assert quiz_history_avoid_questions(history, course_id="course-b", topic="Lecture 1") == []


def test_quiz_generator_uses_llm_when_available() -> None:
    result = QuizGeneratorAgent(llm_client=FakeQuizLLM()).generate(topic="Backpropagation", count=2)

    assert result["generation_mode"] == "llm"
    assert result["count"] == 2
    assert result["questions"][0]["id"] == "llm-1"
    assert result["questions"][0]["hint"]
    assert result["questions"][0]["concept"]
    assert result["questions"][0]["correct_answer"] in result["questions"][0]["options"]
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


def test_short_answer_llm_dict_is_wrapped_and_normalized() -> None:
    result = QuizGeneratorAgent(llm_client=ShortAnswerDictLLM()).generate(
        topic="ranking",
        count=1,
        question_types=["short_answer"],
    )

    question = result["questions"][0]
    assert result["generation_mode"] == "llm"
    assert question["type"] == "short_answer"
    assert question["hint"]
    assert question["concept"]
    assert question["correct_answer"] == question["expected_answer"]


def test_mixed_llm_generation_preserves_requested_types() -> None:
    result = QuizGeneratorAgent(llm_client=MixedQuizLLM()).generate(
        topic="inverted indexes",
        count=4,
        question_types=["mcq", "true_false", "short_answer", "matching"],
    )

    assert [question["type"] for question in result["questions"]] == [
        "mcq",
        "true_false",
        "short_answer",
        "matching",
    ]
    assert all(question["hint"] and question["concept"] for question in result["questions"])


def test_invalid_llm_json_uses_varied_fallback_questions() -> None:
    result = QuizGeneratorAgent(llm_client=InvalidQuizLLM()).generate(topic="Backpropagation", count=5)
    questions = [question["question"] for question in result["questions"]]

    assert result["generation_mode"] == "offline_template"
    assert len(questions) == 5
    assert len(set(questions)) == 5
    assert all("(variant" not in question.lower() for question in questions)


def test_weak_topics_are_included_in_quiz_prompt_context() -> None:
    llm = CapturingWeakQuizLLM()
    QuizGeneratorAgent(llm_client=llm).generate(
        topic="Backpropagation",
        count=2,
        weak_topics=["Chain rule mistakes", "Gradient signs"],
    )

    assert "Priority weak topics or recent mistakes" in llm.calls[0]["user_prompt"]
    assert "Chain rule mistakes" in llm.calls[0]["user_prompt"]
    assert "Gradient signs" in llm.calls[0]["user_prompt"]


def test_retrieved_context_adds_grounding_instructions_to_llm_prompt() -> None:
    llm = CapturingWeakQuizLLM()
    QuizGeneratorAgent(llm_client=llm).generate(
        topic="inverted indexes",
        count=2,
        context_chunks=[
            {
                "course_name": "Information Retrieval",
                "source_name": "ir_notes.txt",
                "section": "text",
                "text": "Inverted indexes map search terms to documents.",
            }
        ],
    )

    assert "Use only the provided selected-course context" in llm.calls[0]["system_prompt"]
    assert "Inverted indexes map search terms to documents" in llm.calls[0]["user_prompt"]


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


def test_quiz_page_generates_from_selected_uploaded_file(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    course_dir = uploads_dir / "ir-1"
    course_dir.mkdir(parents=True)
    (course_dir / "search_notes.txt").write_text(
        "Search engines use inverted indexes to retrieve documents quickly.",
        encoding="utf-8",
    )
    (course_dir / "ranking_notes.txt").write_text(
        "Ranking models score documents according to relevance signals.",
        encoding="utf-8",
    )
    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=tmp_path / "vector_store")

    result = generate_quiz_from_course_materials(
        indexer=indexer,
        quiz_generator=QuizGeneratorAgent(),
        topic="ranking notes",
        count=2,
        language="en",
        difficulty="medium",
        question_types=["mcq"],
        avoid_questions=[],
        course_id="ir-1",
        course_name="Information Retrieval",
        source_name="ranking_notes.txt",
    )

    assert result["ok"] is True
    assert {chunk["source_name"] for chunk in result["context_chunks"]} == {"ranking_notes.txt"}
    assert all(question["source"].startswith("ranking_notes.txt") for question in result["quiz_result"]["questions"])


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


def test_active_quiz_uses_fresh_generation_fallback() -> None:
    st.session_state.clear()
    fallback = {
        "topic": "inverted indexes",
        "language": "en",
        "questions": [{"question": "What is an inverted index?", "options": ["A"], "answer_index": 0}],
        "flashcards": [],
        "source_count": 1,
    }

    assert _active_quiz(fallback=fallback) == fallback


def test_generated_quiz_is_saved_as_active_quiz_without_counting_attempt() -> None:
    st.session_state.clear()
    init_state()
    course = add_course("Information Retrieval")
    request = _quiz_generation_request(
        topic="inverted indexes",
        count=2,
        language="en",
        difficulty="hard",
        question_types=["mcq", "true_false"],
        course_id=course["id"],
        course_name=course["name"],
    )
    quiz_result = QuizGeneratorAgent().generate(
        topic="inverted indexes",
        count=2,
        difficulty="hard",
        question_types=["mcq", "true_false"],
    )

    active_quiz = _store_generated_quiz(
        quiz_result=quiz_result,
        generation_request=request,
        context_chunks=[{"source_name": "ir_notes.txt", "section": "text"}],
        previous_generated_questions=["old question"],
    )
    context = course_context()

    assert context["active_quiz"] == active_quiz
    assert st.session_state["active_quiz"] == active_quiz
    assert _active_quiz() == active_quiz
    assert context["quiz_attempts"] == []
    assert active_quiz["course_id"] == course["id"]
    assert active_quiz["course_name"] == course["name"]
    assert active_quiz["difficulty"] == "hard"
    assert active_quiz["question_types"] == ["mcq", "true_false"]
    assert active_quiz["requested_count"] == 2
    assert active_quiz["source_count"] == 1
    assert context["quiz_generation_status"]["status"] == "generated"
    assert quiz_history_avoid_questions(
        context["generated_questions"],
        course_id=course["id"],
        topic="inverted indexes",
    )
    stored_scope = context["generated_questions"]["scopes"][quiz_history_scope(course["id"], "inverted indexes")]
    assert stored_scope["questions"][0]["normalized"] == normalize_question_text(quiz_result["questions"][0]["question"])


def test_record_attempt_updates_course_attempts_average_and_weak_topics(monkeypatch) -> None:
    st.session_state.clear()
    init_state()
    course = add_course("Machine Learning")
    quiz = QuizGeneratorAgent().generate(topic="SVM", count=1, difficulty="medium")["quiz"]
    question = quiz["questions"][0]
    wrong_answer = (question["answer_index"] + 1) % len(question["options"])
    evaluation = ProgressEvaluatorAgent().evaluate(
        questions=quiz["questions"],
        answers=[wrong_answer],
        topic=quiz["topic"],
    )
    memory_agent = FakeMemoryAgent()
    monkeypatch.setattr(st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "warning", lambda *args, **kwargs: None)

    _record_attempt(
        evaluation=evaluation,
        quiz=quiz,
        active_plan=None,
        active_course=course,
        memory_agent=memory_agent,
        student_email="student@example.com",
        student_name="Demo Student",
        language="en",
    )
    context = course_context()
    attempt = context["quiz_attempts"][0]

    assert len(context["quiz_attempts"]) == 1
    assert attempt["course_id"] == course["id"]
    assert attempt["difficulty"] == "medium"
    assert attempt["question_count"] == 1
    assert attempt["question_types"] == ["mcq"]
    assert attempt["score_percent"] == evaluation["score_percent"]
    assert attempt["weak_topics"] == ["SVM"]
    assert context["all_courses"][0]["quiz_attempts"] == 1
    assert context["all_courses"][0]["average_score"] == evaluation["score_percent"]
    assert context["all_courses"][0]["weak_topics"] == ["SVM"]
    assert memory_agent.calls[0]["course_name"] == course["name"]


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


def test_course_bucket_migrates_legacy_current_quiz_to_active_quiz() -> None:
    legacy_quiz = {"topic": "legacy", "questions": [{"question": "old"}]}

    normalized = _normalize_course_bucket({"current_quiz": legacy_quiz})

    assert normalized["active_quiz"] == legacy_quiz
    assert "current_quiz" not in normalized


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

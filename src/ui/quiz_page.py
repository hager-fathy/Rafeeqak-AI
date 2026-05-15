from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.agents.progress_evaluator import ProgressEvaluatorAgent
from src.agents.quiz_generator import QuizGeneratorAgent
from src.localization import detect_language, t
from src.retrieval import CourseMaterialIndexer
from src.tools.state import (
    course_context,
    get_active_course,
    get_authenticated_user,
    get_memory_agent,
    get_selected_language,
    require_active_course_message,
    touch_activity,
    update_active_course_bucket,
)
from src.ui.theme import render_page_hero


def render_quiz_page(project_root: Path) -> None:
    language = get_selected_language()
    memory_agent = get_memory_agent()
    memory_status = memory_agent.status()
    auth_user = get_authenticated_user()
    student_email = auth_user.get("email") if auth_user else None
    student_name = (auth_user.get("user_metadata") or {}).get("full_name") if auth_user else None
    active_course = get_active_course()
    current_context = course_context()
    active_plan = current_context.get("active_plan")
    default_topic = _default_topic(active_plan)
    course_id = active_course["id"] if active_course else None
    course_name = active_course["name"] if active_course else None

    indexer = CourseMaterialIndexer(
        uploads_dir=project_root / "data" / "uploads",
        vector_store_dir=project_root / "data" / "vector_store",
    )
    quiz_generator = QuizGeneratorAgent()
    evaluator = ProgressEvaluatorAgent()

    attempts = current_context.get("quiz_attempts", [])
    average_score = round(sum(item["score_percent"] for item in attempts) / len(attempts), 1) if attempts else 0.0

    render_page_hero(
        t("quiz.title", language),
        t("quiz.subtitle", language),
        chips=[
            f"{t('planner.course_name', language)}: {course_name or t('course.none_selected', language)}",
            t("quiz.attempts_chip", language, count=len(attempts)),
            t("quiz.avg_chip", language, score=average_score),
            t("quiz.rag_chip", language, count=indexer.stats(course_id=course_id)["chunks"]),
        ],
        accent_chip=t("quiz.accent", language),
        language=language,
    )

    course_warning = require_active_course_message()
    if course_warning:
        st.info(course_warning)

    generated_quiz_for_render: dict[str, Any] | None = None
    setup_col, history_col = st.columns([1.6, 1], gap="large")

    with setup_col:
        with st.container(border=True):
            st.markdown(f"#### {t('quiz.setup', language)}")
            with st.form("quiz_config_form"):
                topic = st.text_input(t("quiz.topic", language), value=default_topic)
                difficulty = st.selectbox(
                    t("quiz.difficulty", language),
                    options=["easy", "medium", "hard"],
                    index=1,
                    format_func=lambda value: t(f"quiz.difficulty.{value}", language),
                )
                question_type_labels = {
                    "mcq": t("quiz.type.mcq", language),
                    "true_false": t("quiz.type.true_false", language),
                    "short_answer": t("quiz.type.short_answer", language),
                    "matching": t("quiz.type.matching", language),
                }
                question_types = st.multiselect(
                    t("quiz.types", language),
                    options=list(question_type_labels.keys()),
                    default=["mcq"],
                    format_func=lambda value: question_type_labels[value],
                )
                question_count = st.number_input(
                    t("quiz.count", language),
                    min_value=1,
                    max_value=20,
                    value=4,
                    step=1,
                    format="%d",
                )
                create_quiz = st.form_submit_button(t("quiz.create", language), use_container_width=True, disabled=active_course is None)

    with history_col:
        with st.container(border=True):
            st.markdown(f"#### {t('quiz.performance', language)}")
            st.metric(t("dashboard.quiz_attempts", language), len(attempts), border=True)
            st.metric(t("quiz.average", language), f"{average_score}%", border=True)
            if attempts:
                last_score = attempts[-1]["score_percent"]
                st.metric(t("quiz.last_score", language), f"{last_score}%", border=True)
            else:
                st.info(t("quiz.no_attempts", language))
            st.metric(
                t("planner.supabase_memory", language),
                t("common.connected", language) if memory_status["enabled"] else t("common.not_configured", language),
                border=True,
            )

    status_before_generation = _quiz_generation_status(current_context.get("quiz_generation_status"))
    retry_request = None
    if _can_retry_quiz_generation(status_before_generation):
        if st.button(t("quiz.retry", language), use_container_width=False, disabled=active_course is None):
            retry_request = _retry_quiz_generation_request(status_before_generation)

    generation_request = None
    if create_quiz:
        topic = " ".join(topic.split())
        if not topic:
            st.warning(t("quiz.topic_required", language))
        elif not question_types:
            st.warning(t("quiz.type_required", language))
        else:
            quiz_language = detect_language(topic)
            if quiz_language != "ar":
                quiz_language = language
            generation_request = _quiz_generation_request(
                topic=topic,
                count=int(question_count),
                language=quiz_language,
                difficulty=difficulty,
                question_types=question_types,
                course_id=course_id,
                course_name=course_name,
            )
    elif retry_request:
        generation_request = retry_request

    if generation_request:
        update_active_course_bucket(
            quiz_generation_status=_quiz_generation_status_payload("loading", request=generation_request)
        )
        with st.spinner(t("quiz.loading", language, topic=generation_request["topic"])):
            try:
                generation_result = generate_quiz_from_course_materials(
                    indexer=indexer,
                    quiz_generator=quiz_generator,
                    topic=generation_request["topic"],
                    count=generation_request["count"],
                    language=generation_request["language"],
                    difficulty=generation_request["difficulty"],
                    question_types=generation_request["question_types"],
                    previous_questions=current_context.get("generated_questions", []),
                    course_id=generation_request["course_id"],
                    course_name=generation_request["course_name"],
                )
            except Exception:
                generation_result = {
                    "ok": False,
                    "reason": "generation_failed",
                    "stats": indexer.stats(course_id=generation_request["course_id"]),
                }

        if not generation_result["ok"]:
            update_active_course_bucket(
                current_quiz=None,
                last_quiz_feedback=None,
                quiz_generation_status=_quiz_generation_status_payload(
                    "failed",
                    request=generation_request,
                    reason=generation_result["reason"],
                    stats=generation_result.get("stats"),
                ),
            )
            touch_activity()
            _render_quiz_generation_status(course_context().get("quiz_generation_status"), language)
            return

        quiz_result = generation_result["quiz_result"]
        context_chunks = generation_result["context_chunks"]
        generated_quiz_for_render = quiz_result["quiz"]
        generated_questions = current_context.get("generated_questions", [])
        generated_questions.extend(question["question"] for question in quiz_result["questions"])
        update_active_course_bucket(
            current_quiz=generated_quiz_for_render,
            last_quiz_feedback=None,
            generated_questions=generated_questions[-120:],
            quiz_generation_status=_quiz_generation_status_payload(
                "generated",
                request=generation_request,
                source_count=len(context_chunks),
                question_count=len(quiz_result["questions"]),
            ),
        )
        touch_activity()

    _render_quiz_generation_status(course_context().get("quiz_generation_status"), language)

    quiz = _current_quiz(fallback=generated_quiz_for_render)
    if not quiz:
        st.info(t("quiz.no_quiz", language))
        return

    questions = quiz.get("questions", [])
    if not questions:
        st.warning(t("quiz.empty", language))
        return

    st.markdown(f"### {t('quiz.active', language, topic=quiz.get('topic', 'Revision'))}")
    st.caption(
        t("quiz.caption.sources", language)
        if quiz.get("source_count")
        else t("quiz.caption.templates", language)
    )

    with st.container(border=True):
        st.markdown(f"#### {t('quiz.answer_title', language)}")
        with st.form("quiz_answers_form"):
            answers = []
            for idx, item in enumerate(questions):
                answers.append(_render_question_input(idx, item, language))

            submit_answers = st.form_submit_button(t("quiz.submit", language), use_container_width=True)

    if submit_answers:
        evaluation = evaluator.evaluate(
            questions=questions,
            answers=answers,
            topic=quiz.get("topic", "Revision"),
            language=quiz.get("language", "en"),
        )
        update_active_course_bucket(last_quiz_feedback=evaluation)
        if evaluation["ok"]:
            _record_attempt(
                evaluation=evaluation,
                active_plan=active_plan,
                active_course=active_course,
                memory_agent=memory_agent,
                student_email=student_email,
                student_name=student_name,
                language=language,
            )
            touch_activity()
            st.success(evaluation["summary"])
            st.info(evaluation["recommendation"])
        else:
            st.warning(evaluation["message"])

    _render_feedback(course_context().get("last_quiz_feedback"), language)
    _render_flashcards(quiz.get("flashcards", []), language)
    _render_attempt_history(course_context().get("quiz_attempts", []), language)


def _record_attempt(
    *,
    evaluation: dict[str, Any],
    active_plan: dict[str, Any] | None,
    active_course: dict[str, Any] | None,
    memory_agent: Any,
    student_email: str | None,
    student_name: str | None,
    language: str,
) -> None:
    attempts = course_context().get("quiz_attempts", [])
    attempts.append(
        {
            "course_id": active_course["id"] if active_course else None,
            "course_name": active_course["name"] if active_course else None,
            "timestamp_utc": evaluation["timestamp_utc"],
            "topic": evaluation["topic"],
            "correct": evaluation["correct"],
            "total": evaluation["total"],
            "score_percent": evaluation["score_percent"],
            "difficulty": evaluation.get("difficulty"),
            "question_types": sorted({item["type"] for item in evaluation["feedback"]}),
            "points_earned": evaluation["points_earned"],
            "total_points": evaluation["total_points"],
            "weak_topics": [item["topic"] for item in evaluation["weak_topics"]],
            "recommendation": evaluation["recommendation"],
        }
    )
    update_active_course_bucket(quiz_attempts=attempts)

    active_course_name = None
    if active_course:
        active_course_name = active_course["name"]
    elif active_plan:
        active_course_name = active_plan.get("course_name")
    sync_result = memory_agent.record_quiz_attempt(
        course_name=active_course_name,
        topic=evaluation["topic"],
        correct=evaluation["correct"],
        total=evaluation["total"],
        score_percent=evaluation["score_percent"],
        student_email=student_email,
        student_name=student_name,
    )
    if sync_result["ok"]:
        st.info(t("quiz.synced", language))
    else:
        st.warning(t("quiz.local_only", language, reason=sync_result["reason"]))


def _render_feedback(evaluation: dict[str, Any] | None, language: str) -> None:
    if not evaluation or not evaluation.get("ok"):
        return

    question_prefix = "س" if language == "ar" else "Q"
    with st.expander(t("quiz.feedback", language), expanded=True):
        for index, item in enumerate(evaluation["feedback"], start=1):
            status = t("quiz.correct", language) if item["is_correct"] else t("quiz.needs_review", language)
            st.markdown(f"**{question_prefix}{index}. {status}**")
            st.write(item["question"])
            if item.get("partial_credit"):
                st.caption(t("quiz.partial", language, score=item["score"]))
            st.caption(t("quiz.your_answer", language, answer=item["selected_answer"] or t("quiz.no_answer", language)))
            if not item["is_correct"]:
                st.caption(t("quiz.correct_answer", language, answer=item["correct_answer"]))
            if item["explanation"]:
                st.info(item["explanation"])


def _render_question_input(index: int, item: dict[str, Any], language: str) -> Any:
    question_type = item.get("type", "mcq")
    question_prefix = "س" if language == "ar" else "Q"
    if question_type in {"mcq", "true_false"}:
        return st.radio(
            f"{question_prefix}{index + 1}. {item['question']}",
            options=list(range(len(item["options"]))),
            format_func=lambda option_idx, opts=item["options"]: opts[option_idx],
            key=f"quiz_q_{index}_{item.get('id', index)}",
        )
    if question_type == "short_answer":
        return st.text_area(
            f"{question_prefix}{index + 1}. {item['question']}",
            key=f"quiz_q_{index}_{item.get('id', index)}",
            height=100,
        )
    if question_type == "matching":
        st.markdown(f"**{question_prefix}{index + 1}. {item['question']}**")
        selected_pairs = {}
        options = item.get("options", [])
        for pair_index, pair in enumerate(item.get("pairs", [])):
            selected_pairs[pair["left"]] = st.selectbox(
                pair["left"],
                options=options,
                key=f"quiz_q_{index}_{item.get('id', index)}_{pair_index}",
            )
        return selected_pairs
    return None


def _render_flashcards(flashcards: list[dict[str, str]], language: str) -> None:
    if not flashcards:
        return

    with st.expander(t("quiz.flashcards", language), expanded=False):
        for card in flashcards:
            st.markdown(f"**{card['front']}**")
            st.write(card["back"])


def _render_attempt_history(attempts: list[dict[str, Any]], language: str) -> None:
    if attempts:
        st.markdown(f"### {t('quiz.history', language)}")
        history_df = pd.DataFrame(attempts)
        st.dataframe(history_df, use_container_width=True, hide_index=True)


def _current_quiz(*, fallback: dict[str, Any] | None = None) -> dict[str, Any] | None:
    quiz = course_context().get("current_quiz")
    if isinstance(quiz, list):
        return {"topic": "Legacy quiz", "language": "en", "questions": quiz, "flashcards": [], "source_count": 0}
    return quiz if isinstance(quiz, dict) else fallback


def _quiz_generation_request(
    *,
    topic: str,
    count: int,
    language: str,
    difficulty: str,
    question_types: list[str],
    course_id: str | None,
    course_name: str | None,
) -> dict[str, Any]:
    return {
        "topic": topic,
        "count": int(count),
        "language": language,
        "difficulty": difficulty,
        "question_types": list(question_types),
        "course_id": course_id,
        "course_name": course_name,
    }


def _quiz_generation_status(status: Any) -> dict[str, Any] | None:
    if not isinstance(status, dict):
        return None
    status_name = str(status.get("status") or "").strip().lower()
    if status_name not in {"loading", "generated", "failed"}:
        return None
    request = status.get("request")
    if not isinstance(request, dict):
        return None
    return {**status, "status": status_name, "request": request}


def _quiz_generation_status_payload(
    status: str,
    *,
    request: dict[str, Any],
    reason: str | None = None,
    stats: dict[str, Any] | None = None,
    source_count: int | None = None,
    question_count: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "request": {
            "topic": request["topic"],
            "count": int(request["count"]),
            "language": request["language"],
            "difficulty": request["difficulty"],
            "question_types": list(request["question_types"]),
            "course_id": request.get("course_id"),
            "course_name": request.get("course_name"),
        },
        "updated_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
    }
    if reason:
        payload["reason"] = reason
    if stats:
        payload["stats"] = stats
    if source_count is not None:
        payload["source_count"] = source_count
    if question_count is not None:
        payload["question_count"] = question_count
    return payload


def _can_retry_quiz_generation(status: dict[str, Any] | None) -> bool:
    return bool(status and status.get("status") == "failed" and _retry_quiz_generation_request(status))


def _retry_quiz_generation_request(status: dict[str, Any] | None) -> dict[str, Any] | None:
    status = _quiz_generation_status(status)
    if not status or status["status"] != "failed":
        return None
    request = status["request"]
    required = {"topic", "count", "language", "difficulty", "question_types"}
    if any(not request.get(key) for key in required):
        return None
    try:
        count = int(request["count"])
    except (TypeError, ValueError):
        return None
    question_types = request.get("question_types")
    if not isinstance(question_types, list):
        return None
    return _quiz_generation_request(
        topic=str(request["topic"]),
        count=count,
        language=str(request["language"]),
        difficulty=str(request["difficulty"]),
        question_types=question_types,
        course_id=request.get("course_id"),
        course_name=request.get("course_name"),
    )


def _render_quiz_generation_status(status: Any, language: str) -> None:
    status = _quiz_generation_status(status)
    if not status:
        return

    request = status["request"]
    status_name = status["status"]
    topic = request.get("topic", "Revision")
    if status_name == "loading":
        st.info(t("quiz.status.loading", language, topic=topic))
        return

    if status_name == "generated":
        source_count = int(status.get("source_count") or 0)
        question_count = int(status.get("question_count") or request.get("count") or 0)
        source_note = t("quiz.source_note", language, count=source_count) if source_count else ""
        st.success(
            t(
                "quiz.status.generated",
                language,
                topic=topic,
                count=question_count,
                source_note=source_note,
            )
        )
        return

    reason = str(status.get("reason") or "generation_failed")
    message = t(f"quiz.{reason}", language)
    stats = status.get("stats") if isinstance(status.get("stats"), dict) else {}
    chunk_count = stats.get("chunks", 0)
    st.warning(t("quiz.status.failed", language, topic=topic, reason=message, chunks=chunk_count))


def generate_quiz_from_course_materials(
    *,
    indexer: CourseMaterialIndexer,
    quiz_generator: QuizGeneratorAgent,
    topic: str,
    count: int,
    language: str,
    difficulty: str,
    question_types: list[str],
    previous_questions: list[str],
    course_id: str | None,
    course_name: str | None,
) -> dict[str, Any]:
    indexer.index_all(course_id=course_id, course_name=course_name)
    stats = indexer.stats(course_id=course_id)
    if stats["chunks"] == 0:
        return {"ok": False, "reason": "materials_required", "stats": stats}

    context_matches = indexer.search(
        topic,
        top_k=min(max(int(count), 3), 8),
        course_id=course_id,
    )
    context_chunks = [
        {
            "source_name": match.source_name,
            "section": match.section,
            "chunk_index": match.chunk_index,
            "course_name": course_name,
            "text": match.text,
            "score": match.score,
        }
        for match in context_matches
    ]
    if not context_chunks:
        return {"ok": False, "reason": "material_match_required", "stats": stats, "context_chunks": []}

    quiz_result = quiz_generator.generate(
        topic=topic,
        count=count,
        context_chunks=context_chunks,
        language=language,
        difficulty=difficulty,
        question_types=question_types,
        previous_questions=previous_questions,
    )
    quiz = quiz_result.get("quiz")
    questions = quiz_result.get("questions") or (quiz.get("questions", []) if isinstance(quiz, dict) else [])
    if not quiz_result.get("ok") or not isinstance(quiz, dict) or not questions:
        return {
            "ok": False,
            "reason": "generation_failed",
            "stats": stats,
            "context_chunks": context_chunks,
            "quiz_result": quiz_result,
        }

    return {
        "ok": True,
        "stats": stats,
        "context_chunks": context_chunks,
        "quiz_result": quiz_result,
    }


def _default_topic(active_plan: dict[str, Any] | None) -> str:
    if active_plan and active_plan.get("weak_topics"):
        return active_plan["weak_topics"][0]
    return "Backpropagation"


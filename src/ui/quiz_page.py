from datetime import datetime
import re
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.agents.progress_evaluator import ProgressEvaluatorAgent
from src.agents.quiz_generator import QuizGeneratorAgent
from src.localization import detect_language, t
from src.retrieval import CourseMaterialIndexer
from src.tools.quiz_history import append_quiz_history, quiz_history_avoid_questions
from src.tools.study_plan_tasks import mark_matching_quiz_task_completed, sync_active_plan_history
from src.tools.state import (
    course_context,
    get_active_course,
    get_authenticated_user,
    get_memory_agent,
    get_selected_language,
    get_user_settings,
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
    user_settings = get_user_settings()
    active_plan = current_context.get("active_plan")
    course_id = active_course["id"] if active_course else None
    course_name = active_course["name"] if active_course else None

    root_uploads_dir = project_root / "data" / "uploads"
    course_uploads_dir = root_uploads_dir / course_id if course_id else root_uploads_dir
    source_options = _quiz_source_options(current_context.get("uploads", []), course_uploads_dir)
    source_lookup = {option["stored_name"]: option for option in source_options}
    indexer = CourseMaterialIndexer(
        uploads_dir=root_uploads_dir,
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

    active_quiz_for_render: dict[str, Any] | None = None
    setup_col, history_col = st.columns([1.6, 1], gap="large", vertical_alignment="top")

    with setup_col:
        with st.container(border=True):
            st.markdown(f"#### {t('quiz.setup', language)}")
            with st.form("quiz_config_form"):
                selected_source_name = st.selectbox(
                    t("quiz.source_file", language),
                    options=[option["stored_name"] for option in source_options],
                    index=0 if source_options else None,
                    format_func=lambda value: source_lookup.get(value, {}).get("label", value),
                    disabled=active_course is None or not source_options,
                    placeholder=t("quiz.source_file_placeholder", language),
                )
                difficulty_col, count_col = st.columns(2, gap="small", vertical_alignment="bottom")
                with difficulty_col:
                    difficulty = st.selectbox(
                        t("quiz.difficulty", language),
                        options=["easy", "medium", "hard"],
                        index=["easy", "medium", "hard"].index(user_settings["default_quiz_difficulty"]),
                        format_func=lambda value: t(f"quiz.difficulty.{value}", language),
                    )
                with count_col:
                    question_count = st.number_input(
                        t("quiz.count", language),
                        min_value=1,
                        max_value=20,
                        value=4,
                        step=1,
                        format="%d",
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
                    default=user_settings["default_question_types"],
                    format_func=lambda value: question_type_labels[value],
                )
                create_quiz = st.form_submit_button(
                    t("quiz.create", language),
                    use_container_width=True,
                    disabled=active_course is None or not source_options,
                )
                if active_course is not None and not source_options:
                    st.info(t("quiz.no_files", language))

    with history_col:
        with st.container(border=True):
            st.markdown(f"#### {t('quiz.performance', language)}")
            attempts_metric = st.empty()
            average_metric = st.empty()
            last_score_slot = st.empty()
            memory_metric = st.empty()
            _render_performance_snapshot(
                attempts=attempts,
                language=language,
                memory_status=memory_status,
                attempts_metric=attempts_metric,
                average_metric=average_metric,
                last_score_slot=last_score_slot,
                memory_metric=memory_metric,
            )

    status_before_generation = _quiz_generation_status(current_context.get("quiz_generation_status"))
    retry_request = None
    if _can_retry_quiz_generation(status_before_generation):
        if st.button(t("quiz.retry", language), use_container_width=False, disabled=active_course is None):
            retry_request = _retry_quiz_generation_request(status_before_generation)

    generation_request = None
    if create_quiz:
        selected_source = source_lookup.get(selected_source_name or "")
        if not selected_source:
            st.warning(t("quiz.file_required", language))
        elif not question_types:
            st.warning(t("quiz.type_required", language))
        else:
            topic = selected_source["topic"]
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
                source_name=selected_source["stored_name"],
                source_label=selected_source["label"],
            )
    elif retry_request:
        generation_request = retry_request

    if generation_request:
        update_active_course_bucket(
            quiz_generation_status=_quiz_generation_status_payload("loading", request=generation_request)
        )
        with st.spinner(t("quiz.loading", language, topic=generation_request.get("source_label") or generation_request["topic"])):
            try:
                generation_result = generate_quiz_from_course_materials(
                    indexer=indexer,
                    quiz_generator=quiz_generator,
                    topic=generation_request["topic"],
                    count=generation_request["count"],
                    language=generation_request["language"],
                    difficulty=generation_request["difficulty"],
                    question_types=generation_request["question_types"],
                    avoid_questions=quiz_history_avoid_questions(
                        course_context().get("generated_questions", []),
                        course_id=generation_request["course_id"],
                        topic=generation_request["topic"],
                    ),
                    course_id=generation_request["course_id"],
                    course_name=generation_request["course_name"],
                    source_name=generation_request.get("source_name"),
                )
            except Exception:
                generation_result = {
                    "ok": False,
                    "reason": "generation_failed",
                    "stats": indexer.stats(course_id=generation_request["course_id"]),
                }

        if not generation_result["ok"]:
            update_active_course_bucket(
                active_quiz=None,
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
        active_quiz_for_render = _store_generated_quiz(
            quiz_result=quiz_result,
            generation_request=generation_request,
            context_chunks=context_chunks,
            previous_generated_questions=current_context.get("generated_questions", []),
        )
        touch_activity()

    _render_quiz_generation_status(course_context().get("quiz_generation_status"), language)

    quiz = _active_quiz(fallback=active_quiz_for_render)
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

    with st.container(height=560, border=True, key="quiz_questions_panel"):
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
                quiz=quiz,
                active_plan=active_plan,
                active_course=active_course,
                memory_agent=memory_agent,
                student_email=student_email,
                student_name=student_name,
                language=language,
            )
            touch_activity()
            _render_performance_snapshot(
                attempts=course_context().get("quiz_attempts", []),
                language=language,
                memory_status=memory_status,
                attempts_metric=attempts_metric,
                average_metric=average_metric,
                last_score_slot=last_score_slot,
                memory_metric=memory_metric,
            )
        else:
            st.warning(evaluation["message"])

    _render_feedback(course_context().get("last_quiz_feedback"), language)
    _render_flashcards(quiz.get("flashcards", []), language)
    _render_attempt_history(course_context().get("quiz_attempts", []), language)


def _render_performance_snapshot(
    *,
    attempts: list[dict[str, Any]],
    language: str,
    memory_status: dict[str, Any],
    attempts_metric: Any,
    average_metric: Any,
    last_score_slot: Any,
    memory_metric: Any,
) -> None:
    average_score = round(sum(item["score_percent"] for item in attempts) / len(attempts), 1) if attempts else 0.0
    attempts_metric.metric(t("dashboard.quiz_attempts", language), len(attempts), border=True)
    average_metric.metric(t("quiz.average", language), f"{average_score}%", border=True)
    if attempts:
        last_score_slot.metric(t("quiz.last_score", language), f"{attempts[-1]['score_percent']}%", border=True)
    else:
        last_score_slot.info(t("quiz.no_attempts", language))
    memory_metric.metric(
        t("planner.supabase_memory", language),
        t("common.connected", language) if memory_status["enabled"] else t("common.not_configured", language),
        border=True,
    )


def _record_attempt(
    *,
    evaluation: dict[str, Any],
    quiz: dict[str, Any] | None,
    active_plan: dict[str, Any] | None,
    active_course: dict[str, Any] | None,
    memory_agent: Any,
    student_email: str | None,
    student_name: str | None,
    language: str,
) -> None:
    attempts = list(course_context().get("quiz_attempts", []))
    quiz_metadata = quiz if isinstance(quiz, dict) else {}
    attempts.append(
        {
            "course_id": active_course["id"] if active_course else None,
            "course_name": active_course["name"] if active_course else None,
            "timestamp_utc": evaluation["timestamp_utc"],
            "topic": evaluation["topic"],
            "correct": evaluation["correct"],
            "total": evaluation["total"],
            "score_percent": evaluation["score_percent"],
            "difficulty": quiz_metadata.get("difficulty") or evaluation.get("difficulty"),
            "question_count": len(quiz_metadata.get("questions", [])) or evaluation["total"],
            "question_types": quiz_metadata.get("question_types")
            or sorted({item["type"] for item in evaluation["feedback"]}),
            "quiz_generated_at_utc": quiz_metadata.get("generated_at_utc"),
            "points_earned": evaluation["points_earned"],
            "total_points": evaluation["total_points"],
            "weak_topics": [item["topic"] for item in evaluation["weak_topics"]],
            "recommendation": evaluation["recommendation"],
        }
    )
    update_active_course_bucket(quiz_attempts=attempts)

    refreshed_plan = course_context().get("active_plan")
    if isinstance(refreshed_plan, dict) and active_course:
        plan_changed = mark_matching_quiz_task_completed(
            refreshed_plan,
            course_scope=active_course["id"],
            topic=evaluation["topic"],
        )
        if plan_changed:
            update_active_course_bucket(
                active_plan=refreshed_plan,
                study_plans=sync_active_plan_history(
                    refreshed_plan,
                    list(course_context().get("study_plans", []) or []),
                ),
            )

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

    st.success(evaluation["summary"])
    st.info(evaluation["recommendation"])

    question_prefix = "س" if language == "ar" else "Q"
    with st.expander(t("quiz.feedback", language), expanded=True):
        with st.container(height=420, border=False, key="quiz_feedback_panel"):
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
        with st.container(height=320, border=False, key="quiz_flashcards_panel"):
            for card in flashcards:
                st.markdown(f"**{card['front']}**")
                st.write(card["back"])


def _render_attempt_history(attempts: list[dict[str, Any]], language: str) -> None:
    if attempts:
        st.markdown(f"### {t('quiz.history', language)}")
        history_df = pd.DataFrame(attempts)
        st.dataframe(history_df, use_container_width=True, hide_index=True, height=320)


def _active_quiz(*, fallback: dict[str, Any] | None = None) -> dict[str, Any] | None:
    quiz = course_context().get("active_quiz")
    if isinstance(quiz, list):
        return {"topic": "Legacy quiz", "language": "en", "questions": quiz, "flashcards": [], "source_count": 0}
    return quiz if isinstance(quiz, dict) else fallback


def _store_generated_quiz(
    *,
    quiz_result: dict[str, Any],
    generation_request: dict[str, Any],
    context_chunks: list[dict[str, Any]],
    previous_generated_questions: list[str],
) -> dict[str, Any]:
    questions = quiz_result.get("questions", [])
    active_quiz = {
        **quiz_result["quiz"],
        "course_id": generation_request.get("course_id"),
        "course_name": generation_request.get("course_name"),
        "source_name": generation_request.get("source_name"),
        "source_label": generation_request.get("source_label"),
        "difficulty": generation_request["difficulty"],
        "question_types": list(generation_request["question_types"]),
        "requested_count": int(generation_request["count"]),
        "questions": questions,
        "flashcards": quiz_result.get("flashcards") or quiz_result["quiz"].get("flashcards", []),
        "source_count": len(context_chunks),
    }
    generated_questions = append_quiz_history(
        previous_generated_questions,
        course_id=generation_request.get("course_id"),
        topic=generation_request["topic"],
        questions=questions,
    )
    update_active_course_bucket(
        active_quiz=active_quiz,
        last_quiz_feedback=None,
        generated_questions=generated_questions,
        quiz_generation_status=_quiz_generation_status_payload(
            "generated",
            request=generation_request,
            source_count=len(context_chunks),
            question_count=len(questions),
            limited_material=bool(quiz_result.get("limited_material")),
        ),
    )
    return active_quiz


def _quiz_generation_request(
    *,
    topic: str,
    count: int,
    language: str,
    difficulty: str,
    question_types: list[str],
    course_id: str | None,
    course_name: str | None,
    source_name: str | None = None,
    source_label: str | None = None,
) -> dict[str, Any]:
    return {
        "topic": topic,
        "count": int(count),
        "language": language,
        "difficulty": difficulty,
        "question_types": list(question_types),
        "course_id": course_id,
        "course_name": course_name,
        "source_name": source_name,
        "source_label": source_label,
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
    limited_material: bool = False,
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
            "source_name": request.get("source_name"),
            "source_label": request.get("source_label"),
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
    if limited_material:
        payload["limited_material"] = True
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
        source_name=request.get("source_name"),
        source_label=request.get("source_label"),
    )


def _render_quiz_generation_status(status: Any, language: str) -> None:
    status = _quiz_generation_status(status)
    if not status:
        return

    request = status["request"]
    status_name = status["status"]
    topic = request.get("topic", "Revision")
    topic_label = request.get("source_label") or topic
    if status_name == "loading":
        st.info(t("quiz.status.loading", language, topic=topic_label))
        return

    if status_name == "generated":
        source_count = int(status.get("source_count") or 0)
        question_count = int(status.get("question_count") or request.get("count") or 0)
        source_note = t("quiz.source_note", language, count=source_count) if source_count else ""
        message = t(
            "quiz.status.generated",
            language,
            topic=topic_label,
            count=question_count,
            source_note=source_note,
        )
        if status.get("limited_material"):
            st.warning(t("quiz.limited_material", language, topic=topic_label, count=question_count))
        else:
            st.success(message)
        return

    reason = str(status.get("reason") or "generation_failed")
    message = t(f"quiz.{reason}", language)
    stats = status.get("stats") if isinstance(status.get("stats"), dict) else {}
    chunk_count = stats.get("chunks", 0)
    st.warning(t("quiz.status.failed", language, topic=topic_label, reason=message, chunks=chunk_count))


def generate_quiz_from_course_materials(
    *,
    indexer: CourseMaterialIndexer,
    quiz_generator: QuizGeneratorAgent,
    topic: str,
    count: int,
    language: str,
    difficulty: str,
    question_types: list[str],
    course_id: str | None,
    course_name: str | None,
    previous_questions: list[str] | None = None,
    avoid_questions: list[str] | None = None,
    source_name: str | None = None,
) -> dict[str, Any]:
    indexer.index_all(course_id=course_id, course_name=course_name)
    stats = indexer.stats(course_id=course_id)
    if stats["chunks"] == 0:
        return {"ok": False, "reason": "materials_required", "stats": stats}

    if source_name:
        context_matches = indexer.chunks_for_source(
            source_name,
            top_k=min(max(int(count) * 3, 8), 16),
            course_id=course_id,
        )
    else:
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
        reason = "file_material_required" if source_name else "material_match_required"
        return {"ok": False, "reason": reason, "stats": stats, "context_chunks": []}

    quiz_result = quiz_generator.generate(
        topic=topic,
        count=count,
        context_chunks=context_chunks,
        language=language,
        difficulty=difficulty,
        question_types=question_types,
        previous_questions=previous_questions,
        avoid_questions=avoid_questions,
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


def _quiz_source_options(uploads: list[dict[str, Any]], uploads_dir: Path) -> list[dict[str, str]]:
    upload_by_stored_name = {
        str(item.get("stored_name")): item
        for item in uploads
        if isinstance(item, dict) and item.get("stored_name")
    }
    stored_files = sorted(
        file_path
        for file_path in uploads_dir.glob("*")
        if file_path.is_file() and file_path.name != ".gitkeep"
    )
    options = []
    for file_path in stored_files:
        upload = upload_by_stored_name.get(file_path.name, {})
        original_name = str(upload.get("original_name") or _display_name_from_stored_file(file_path.name)).strip()
        saved_at = str(upload.get("saved_at_utc") or "").strip()
        label = original_name
        if saved_at:
            label = f"{original_name} - {saved_at[:10]}"
        options.append(
            {
                "stored_name": file_path.name,
                "label": label,
                "topic": Path(original_name).stem.replace("_", " ").replace("-", " ").strip() or original_name,
            }
        )
    return options


def _display_name_from_stored_file(stored_name: str) -> str:
    match = re.match(r"^\d{8}_\d{6}_(.+)$", stored_name)
    if match:
        return match.group(1)
    return stored_name



from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.agents.progress_evaluator import ProgressEvaluatorAgent
from src.agents.quiz_generator import QuizGeneratorAgent
from src.retrieval import CourseMaterialIndexer
from src.tools.state import get_authenticated_user, get_memory_agent, touch_activity
from src.ui.theme import render_page_hero


def render_quiz_page(project_root: Path) -> None:
    memory_agent = get_memory_agent()
    memory_status = memory_agent.status()
    auth_user = get_authenticated_user()
    student_email = auth_user.get("email") if auth_user else None
    student_name = (auth_user.get("user_metadata") or {}).get("full_name") if auth_user else None
    active_plan = st.session_state.get("active_plan")
    default_topic = _default_topic(active_plan)

    indexer = CourseMaterialIndexer(
        uploads_dir=project_root / "data" / "uploads",
        vector_store_dir=project_root / "data" / "vector_store",
    )
    quiz_generator = QuizGeneratorAgent()
    evaluator = ProgressEvaluatorAgent()

    attempts = st.session_state.get("quiz_attempts", [])
    average_score = round(sum(item["score_percent"] for item in attempts) / len(attempts), 1) if attempts else 0.0

    render_page_hero(
        "Assessment Studio",
        "Generate focused quizzes to validate comprehension and monitor mastery over time.",
        chips=[
            f"Attempts: {len(attempts)}",
            f"Average score: {average_score}%",
            f"RAG chunks: {indexer.stats()['chunks']}",
        ],
        accent_chip="Quiz lab",
    )

    setup_col, history_col = st.columns([1.6, 1], gap="large")

    with setup_col:
        with st.container(border=True):
            st.markdown("#### Quiz setup")
            with st.form("quiz_config_form"):
                topic = st.text_input("Topic", value=default_topic)
                question_count = st.number_input(
                    "Number of questions",
                    min_value=1,
                    value=4,
                    step=1,
                    format="%d",
                )
                create_quiz = st.form_submit_button("Create quiz", width="stretch")

    with history_col:
        with st.container(border=True):
            st.markdown("#### Performance snapshot")
            st.metric("Attempts", len(attempts), border=True)
            st.metric("Average", f"{average_score}%", border=True)
            if attempts:
                last_score = attempts[-1]["score_percent"]
                st.metric("Last score", f"{last_score}%", border=True)
            else:
                st.info("No attempts yet.")
            st.metric("Supabase memory", "Connected" if memory_status["enabled"] else "Not configured", border=True)

    if create_quiz:
        language = _detect_language(topic)
        context_matches = indexer.search(topic, top_k=3)
        context_chunks = [
            {
                "source_name": match.source_name,
                "section": match.section,
                "text": match.text,
                "score": match.score,
            }
            for match in context_matches
        ]
        quiz_result = quiz_generator.generate(
            topic=topic,
            count=question_count,
            context_chunks=context_chunks,
            language=language,
        )
        st.session_state.current_quiz = quiz_result["quiz"]
        st.session_state.last_quiz_feedback = None
        touch_activity()
        source_note = f" using {len(context_chunks)} retrieved source chunk(s)" if context_chunks else ""
        st.success(f"Quiz generated{source_note}.")

    quiz = _current_quiz()
    if not quiz:
        st.info("No active quiz yet. Create one above.")
        return

    questions = quiz.get("questions", [])
    if not questions:
        st.warning("The active quiz has no questions. Create a new quiz.")
        return

    st.markdown(f"### Active quiz: {quiz.get('topic', 'Revision')}")
    st.caption(
        "Generated from uploaded materials and study-topic templates."
        if quiz.get("source_count")
        else "Generated from study-topic templates."
    )

    with st.container(border=True):
        st.markdown("#### Answer questions")
        with st.form("quiz_answers_form"):
            chosen_indices = []
            for idx, item in enumerate(questions):
                answer = st.radio(
                    f"Q{idx + 1}. {item['question']}",
                    options=list(range(len(item["options"]))),
                    format_func=lambda option_idx, opts=item["options"]: opts[option_idx],
                    key=f"quiz_q_{idx}_{item.get('id', idx)}",
                )
                chosen_indices.append(answer)

            submit_answers = st.form_submit_button("Submit answers", width="stretch")

    if submit_answers:
        evaluation = evaluator.evaluate(
            questions=questions,
            selected_indices=chosen_indices,
            topic=quiz.get("topic", "Revision"),
            language=quiz.get("language", "en"),
        )
        st.session_state.last_quiz_feedback = evaluation
        if evaluation["ok"]:
            _record_attempt(
                evaluation=evaluation,
                active_plan=active_plan,
                memory_agent=memory_agent,
                student_email=student_email,
                student_name=student_name,
            )
            touch_activity()
            st.success(evaluation["summary"])
            st.info(evaluation["recommendation"])
        else:
            st.warning(evaluation["message"])

    _render_feedback(st.session_state.get("last_quiz_feedback"))
    _render_flashcards(quiz.get("flashcards", []))
    _render_attempt_history(st.session_state.get("quiz_attempts", []))


def _record_attempt(
    *,
    evaluation: dict[str, Any],
    active_plan: dict[str, Any] | None,
    memory_agent: Any,
    student_email: str | None,
    student_name: str | None,
) -> None:
    st.session_state.quiz_attempts.append(
        {
            "timestamp_utc": evaluation["timestamp_utc"],
            "topic": evaluation["topic"],
            "correct": evaluation["correct"],
            "total": evaluation["total"],
            "score_percent": evaluation["score_percent"],
            "weak_topics": [item["topic"] for item in evaluation["weak_topics"]],
            "recommendation": evaluation["recommendation"],
        }
    )

    active_course_name = active_plan.get("course_name") if active_plan else None
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
        st.info("Quiz attempt synced to Supabase memory.")
    else:
        st.warning(f"Quiz attempt saved locally only. Reason: {sync_result['reason']}")


def _render_feedback(evaluation: dict[str, Any] | None) -> None:
    if not evaluation or not evaluation.get("ok"):
        return

    with st.expander("Question feedback", expanded=True):
        for index, item in enumerate(evaluation["feedback"], start=1):
            status = "Correct" if item["is_correct"] else "Needs review"
            st.markdown(f"**Q{index}. {status}**")
            st.write(item["question"])
            st.caption(f"Your answer: {item['selected_answer'] or 'No answer'}")
            if not item["is_correct"]:
                st.caption(f"Correct answer: {item['correct_answer']}")
            if item["explanation"]:
                st.info(item["explanation"])


def _render_flashcards(flashcards: list[dict[str, str]]) -> None:
    if not flashcards:
        return

    with st.expander("Flashcards from this quiz", expanded=False):
        for card in flashcards:
            st.markdown(f"**{card['front']}**")
            st.write(card["back"])


def _render_attempt_history(attempts: list[dict[str, Any]]) -> None:
    if attempts:
        st.markdown("### Attempt history")
        history_df = pd.DataFrame(attempts)
        st.dataframe(history_df, width="stretch", hide_index=True)


def _current_quiz() -> dict[str, Any] | None:
    quiz = st.session_state.get("current_quiz")
    if isinstance(quiz, list):
        return {"topic": "Legacy quiz", "language": "en", "questions": quiz, "flashcards": [], "source_count": 0}
    return quiz if isinstance(quiz, dict) else None


def _default_topic(active_plan: dict[str, Any] | None) -> str:
    if active_plan and active_plan.get("weak_topics"):
        return active_plan["weak_topics"][0]
    return "Backpropagation"


def _detect_language(text: str) -> str:
    return "ar" if any("\u0600" <= char <= "\u06FF" for char in text) else "en"

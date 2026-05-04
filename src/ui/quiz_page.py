import random
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.tools.state import get_authenticated_user, get_memory_agent, touch_activity
from src.ui.theme import render_page_hero

QUESTION_BANK = [
    {
        "question": "What does backpropagation compute in a neural network?",
        "options": [
            "The gradient of the loss with respect to each parameter",
            "Only the forward pass outputs",
            "The training data distribution",
            "The number of hidden layers",
        ],
        "answer_index": 0,
    },
    {
        "question": "Which parameter controls margin softness in a soft-margin SVM?",
        "options": ["Alpha", "C", "Gamma", "Lambda"],
        "answer_index": 1,
    },
    {
        "question": "What is overfitting?",
        "options": [
            "Performing poorly on both train and test data",
            "Performing well on training data but poorly on unseen data",
            "Using too little data preprocessing",
            "A type of optimizer",
        ],
        "answer_index": 1,
    },
    {
        "question": "Why is a validation set used?",
        "options": [
            "To train the final model parameters",
            "To choose model settings and monitor generalization",
            "To replace test evaluation",
            "To remove noisy samples only",
        ],
        "answer_index": 1,
    },
    {
        "question": "What does the learning rate affect?",
        "options": [
            "How large each optimization step is",
            "How many classes exist in data",
            "The input feature count",
            "The batch label quality",
        ],
        "answer_index": 0,
    },
]


def _build_quiz(topic: str, question_count: int) -> list[dict]:
    seed = f"{topic.strip().lower()}::{question_count}"
    rng = random.Random(seed)
    return rng.sample(QUESTION_BANK, k=min(question_count, len(QUESTION_BANK)))


def render_quiz_page(project_root: Path) -> None:
    del project_root
    memory_agent = get_memory_agent()
    memory_status = memory_agent.status()
    auth_user = get_authenticated_user()
    student_email = auth_user.get("email") if auth_user else None
    student_name = (auth_user.get("user_metadata") or {}).get("full_name") if auth_user else None

    attempts = st.session_state.get("quiz_attempts", [])
    average_score = round(sum(item["score_percent"] for item in attempts) / len(attempts), 1) if attempts else 0.0

    render_page_hero(
        "Assessment Studio",
        "Generate focused quizzes to validate comprehension and monitor mastery over time.",
        chips=[
            f"Attempts: {len(attempts)}",
            f"Average score: {average_score}%",
        ],
        accent_chip="Quiz lab",
    )

    setup_col, history_col = st.columns([1.6, 1], gap="large")

    with setup_col:
        with st.container(border=True):
            st.markdown("#### Quiz setup")
            with st.form("quiz_config_form"):
                topic = st.text_input("Topic", value="Backpropagation")
                question_count = st.slider("Number of questions", min_value=2, max_value=5, value=3)
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
        st.session_state.current_quiz = _build_quiz(topic, question_count)
        touch_activity()
        st.success("Quiz generated.")

    quiz = st.session_state.get("current_quiz")
    if not quiz:
        st.info("No active quiz yet. Create one above.")
        return

    with st.container(border=True):
        st.markdown("#### Answer questions")
        with st.form("quiz_answers_form"):
            chosen_indices = []
            for idx, item in enumerate(quiz):
                answer = st.radio(
                    f"Q{idx + 1}. {item['question']}",
                    options=list(range(len(item["options"]))),
                    format_func=lambda option_idx, opts=item["options"]: opts[option_idx],
                    key=f"quiz_q_{idx}",
                )
                chosen_indices.append(answer)

            submit_answers = st.form_submit_button("Submit answers", width="stretch")

    if submit_answers:
        correct_answers = 0
        for selected, item in zip(chosen_indices, quiz):
            if selected == item["answer_index"]:
                correct_answers += 1

        total_questions = len(quiz)
        score_percent = round((correct_answers / total_questions) * 100, 1)
        st.session_state.quiz_attempts.append(
            {
                "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds"),
                "topic": topic,
                "correct": correct_answers,
                "total": total_questions,
                "score_percent": score_percent,
            }
        )
        touch_activity()

        st.success(f"Score: {correct_answers}/{total_questions} ({score_percent}%).")
        active_plan = st.session_state.get("active_plan")
        active_course_name = active_plan.get("course_name") if active_plan else None
        sync_result = memory_agent.record_quiz_attempt(
            course_name=active_course_name,
            topic=topic,
            correct=correct_answers,
            total=total_questions,
            score_percent=score_percent,
            student_email=student_email,
            student_name=student_name,
        )
        if sync_result["ok"]:
            st.info("Quiz attempt synced to Supabase memory.")
        else:
            st.warning(f"Quiz attempt saved locally only. Reason: {sync_result['reason']}")

    if st.session_state.quiz_attempts:
        st.markdown("### Attempt history")
        history_df = pd.DataFrame(st.session_state.quiz_attempts)
        st.dataframe(history_df, width="stretch", hide_index=True)

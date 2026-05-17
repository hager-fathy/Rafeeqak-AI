from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from src.agents.reminder_agent import ReminderAgent
from src.localization import t
from src.tools.study_plan_tasks import (
    apply_manual_completion_updates,
    ensure_task_ids,
    is_task_completed,
    sync_active_plan_history,
    tasks_to_timeline_rows,
)
from src.tools.state import (
    add_course,
    course_context,
    get_active_course,
    get_authenticated_user,
    get_memory_agent,
    get_selected_language,
    get_supervisor_agent,
    get_user_settings,
    touch_activity,
    update_active_course_bucket,
    update_course_details,
)
from src.ui.theme import render_page_hero


def _parse_topics(raw_text: str) -> list[str]:
    return [item.strip() for item in raw_text.split(",") if item.strip()]


def _topic_text(topics: list[str]) -> str:
    return ", ".join(topics)


def _derived_weak_topics(current_context: dict) -> list[str]:
    active_plan = current_context.get("active_plan") or {}
    weak_topics = list(active_plan.get("weak_topics", []) or [])
    seen = {topic.casefold() for topic in weak_topics}
    for attempt in current_context.get("quiz_attempts", []) or []:
        for topic in attempt.get("weak_topics", []) or []:
            normalized = str(topic).strip()
            if not normalized or normalized.casefold() in seen:
                continue
            weak_topics.append(normalized)
            seen.add(normalized.casefold())
    return weak_topics


def _progress_snapshot(current_context: dict) -> dict:
    active_plan = current_context.get("active_plan") or {}
    tasks = active_plan.get("tasks", []) if isinstance(active_plan, dict) else []
    completed_tasks = [task for task in tasks if isinstance(task, dict) and is_task_completed(task, active_plan)]
    overdue_tasks = [
        task
        for task in tasks
        if isinstance(task, dict)
        and not is_task_completed(task, active_plan)
        and str(task.get("date", "")).strip()
        and str(task["date"]) < date.today().isoformat()
    ]
    quiz_attempts = current_context.get("quiz_attempts", []) or []
    average_score = 0.0
    if quiz_attempts:
        average_score = round(sum(float(item.get("score_percent", 0)) for item in quiz_attempts) / len(quiz_attempts), 1)
    return {
        "completed_tasks": len(completed_tasks),
        "total_tasks": len(tasks),
        "overdue_tasks": overdue_tasks,
        "delayed_task_topics": [task.get("topic") for task in overdue_tasks if task.get("topic")],
        "quiz_attempts": len(quiz_attempts),
        "average_score": average_score,
        "quiz_weak_topics": _derived_weak_topics(current_context),
    }


def _apply_completed_updates(active_plan: dict, edited_rows: list[dict], course_scope: str | None = None) -> bool:
    return apply_manual_completion_updates(active_plan, edited_rows, course_scope=course_scope)


def _sync_active_plan_history(active_plan: dict, study_plans: list[dict]) -> list[dict]:
    return sync_active_plan_history(active_plan, study_plans)


def _default_exam_date(active_plan: dict | None) -> date:
    if not isinstance(active_plan, dict):
        return date.today() + timedelta(days=10)
    raw_date = str(active_plan.get("exam_date") or "").strip()
    if not raw_date:
        return date.today() + timedelta(days=10)
    try:
        parsed = date.fromisoformat(raw_date)
    except ValueError:
        return date.today() + timedelta(days=10)
    return max(parsed, date.today())


def render_study_plan_page(project_root: Path) -> None:
    del project_root
    language = get_selected_language()
    memory_agent = get_memory_agent()
    memory_status = memory_agent.status()
    auth_user = get_authenticated_user()
    student_email = auth_user.get("email") if auth_user else None
    student_name = (auth_user.get("user_metadata") or {}).get("full_name") if auth_user else None
    user_settings = get_user_settings()
    active_course = get_active_course()
    current_context = course_context()
    active_plan = current_context.get("active_plan")
    derived_weak_topics = _derived_weak_topics(current_context)
    progress_snapshot = _progress_snapshot(current_context)
    course_difficulty = str((active_course or {}).get("difficulty") or user_settings["default_course_difficulty"]).strip().lower()
    default_difficulty = str(
        (active_plan or {}).get("difficulty") or course_difficulty or user_settings["default_course_difficulty"]
    ).lower()
    if default_difficulty not in {"easy", "medium", "hard"}:
        default_difficulty = "medium"
    default_exam_date = _default_exam_date(active_plan)
    default_window_days = max((default_exam_date - date.today()).days, 1)
    default_lecture_count = int((active_plan or {}).get("lecture_count") or max(len(derived_weak_topics), 6))
    default_finish_period = int((active_plan or {}).get("finish_period_days") or min(default_window_days, max(default_lecture_count, 1)))

    render_page_hero(
        t("planner.title", language),
        t("planner.subtitle", language),
        chips=[
            f"{t('planner.course_name', language)}: {active_course['name'] if active_course else t('course.none_selected', language)}",
            t("planner.saved_plans_chip", language, count=len(current_context["study_plans"])),
            t("planner.current_day_chip", language, date=date.today().isoformat()),
        ],
        accent_chip=t("planner.accent", language),
        language=language,
    )

    input_col, summary_col = st.columns([1.8, 1], gap="large")

    with input_col:
        with st.container(border=True):
            st.markdown(f"#### {t('planner.config', language)}")
            with st.form("plan_form"):
                course_name = st.text_input(
                    t("planner.course_name", language),
                    value=active_course["name"] if active_course else "",
                    placeholder=t("planner.course_placeholder", language),
                )
                exam_date = st.date_input(
                    t("planner.exam_date", language),
                    value=default_exam_date,
                    min_value=date.today(),
                )
                difficulty = st.selectbox(
                    t("planner.difficulty", language),
                    options=["easy", "medium", "hard"],
                    index=["easy", "medium", "hard"].index(default_difficulty),
                    format_func=lambda value: t(f"quiz.difficulty.{value}", language),
                )
                lecture_count = st.number_input(
                    t("planner.lecture_count", language),
                    min_value=1,
                    max_value=60,
                    value=max(default_lecture_count, 1),
                    step=1,
                )
                finish_period_days = st.number_input(
                    t("planner.finish_period", language),
                    min_value=1,
                    max_value=max(default_window_days, 1),
                    value=min(max(default_finish_period, 1), max(default_window_days, 1)),
                    step=1,
                )
                daily_hours = st.number_input(
                    t("planner.daily_hours", language),
                    min_value=0.5,
                    max_value=12.0,
                    value=float((active_plan or {}).get("daily_hours") or user_settings["daily_study_hours"]),
                    step=0.5,
                )
                weak_topics_input = st.text_input(
                    t("planner.weak_topics", language),
                    value=_topic_text((active_plan or {}).get("weak_topics") or derived_weak_topics),
                    placeholder=t("planner.weak_placeholder", language),
                )
                other_topics_input = st.text_input(
                    t("planner.other_topics", language),
                    value=_topic_text((active_plan or {}).get("other_topics") or []),
                    placeholder=t("planner.other_placeholder", language),
                )
                submit_plan = st.form_submit_button(t("planner.generate", language), use_container_width=True)

    with summary_col:
        with st.container(border=True):
            st.markdown(f"#### {t('planner.insights', language)}")
            active_plan = current_context.get("active_plan")
            if active_plan:
                plan_progress = active_plan.get("progress_snapshot", {})
                st.metric(t("planner.tasks_queued", language), len(active_plan["tasks"]), border=True)
                st.metric(t("planner.weak_tracked", language), len(active_plan["weak_topics"]), border=True)
                st.metric(t("planner.hours_day", language), active_plan["daily_hours"], border=True)
                st.metric(t("planner.delayed_tasks", language), active_plan.get("delayed_task_count", 0), border=True)
                st.caption(
                    t(
                        "planner.plan_meta",
                        language,
                        difficulty=t(f"quiz.difficulty.{active_plan.get('difficulty', 'medium')}", language),
                        lecture_count=active_plan.get("lecture_count", 0),
                        finish_period=active_plan.get("finish_period_days", 0),
                    )
                )
                if plan_progress:
                    st.caption(
                        t(
                            "planner.progress_meta",
                            language,
                            completed=plan_progress.get("completed_tasks", 0),
                            total=plan_progress.get("total_tasks", 0),
                            rate=plan_progress.get("completion_rate", 0.0),
                            quiz_average=plan_progress.get("average_score", 0.0),
                        )
                    )
                recovery_recommendations = active_plan.get("recovery_recommendations", [])
                if recovery_recommendations:
                    st.markdown(f"##### {t('planner.recovery_title', language)}")
                    for item in recovery_recommendations:
                        st.caption(f"- {item}")
            else:
                st.info(t("planner.no_insights", language))
            st.metric(
                t("planner.supabase_memory", language),
                t("common.connected", language) if memory_status["enabled"] else t("common.not_configured", language),
                border=True,
            )

    if submit_plan:
        if active_course is None:
            active_course = add_course(course_name, difficulty=difficulty.title())
            current_context = course_context()
        if active_course is None:
            st.warning(t("planner.course_required", language))
            return

        update_course_details(active_course["id"], difficulty=difficulty.title())
        weak_topics = _parse_topics(weak_topics_input) or derived_weak_topics
        other_topics = _parse_topics(other_topics_input)
        plan_result = get_supervisor_agent().create_study_plan(
            {
                "course_name": active_course["name"],
                "exam_date": exam_date,
                "daily_hours": daily_hours,
                "difficulty": difficulty,
                "lecture_count": int(lecture_count),
                "finish_period_days": int(finish_period_days),
                "weak_topics": weak_topics,
                "other_topics": other_topics,
                "progress": progress_snapshot,
                "language": language,
            },
            memory_agent=memory_agent,
            student_email=student_email,
            student_name=student_name,
        )
        plan = plan_result["plan"]
        study_plans = current_context["study_plans"]
        study_plans.append(plan)
        update_active_course_bucket(study_plans=study_plans, active_plan=plan)
        reminder_result = ReminderAgent().create(
            message="create reminders for this course",
            context=course_context(),
            language=language,
        )
        update_active_course_bucket(reminders=reminder_result["reminders"])
        touch_activity()
        st.success(plan_result["summary"])

        sync_result = plan_result["sync_result"]
        if sync_result["ok"]:
            st.info(t("planner.synced", language))
        else:
            st.warning(t("planner.local_only", language, reason=sync_result["reason"]))
        reminder_sync = memory_agent.sync_reminders(
            course_name=active_course["name"],
            reminders=reminder_result["reminders"],
            student_email=student_email,
            student_name=student_name,
        )
        if reminder_sync["ok"]:
            st.info(t("dashboard.reminders_synced", language))
        elif memory_status["enabled"]:
            st.warning(t("dashboard.reminders_local_only", language, reason=reminder_sync["reason"]))

    active_plan = course_context().get("active_plan")
    if not active_plan:
        st.info(t("planner.no_plan", language))
        return

    course_scope = active_course["id"] if active_course else active_plan.get("course_name")
    ensure_task_ids(active_plan, course_scope)
    timeline_rows = tasks_to_timeline_rows(
        active_plan.get("tasks", []),
        language=language,
        course_scope=course_scope,
    )
    tasks_df = pd.DataFrame(timeline_rows)
    st.markdown(f"### {t('planner.timeline', language)}")
    edited_df = st.data_editor(
        tasks_df,
        use_container_width=True,
        hide_index=True,
        disabled=[column for column in tasks_df.columns if column != "mark_as_done"],
        key=f"plan_timeline_editor_{course_scope}_{active_plan.get('exam_date', 'date')}",
        column_config={
            "task_id": None,
            "date": st.column_config.TextColumn(t("planner.col.study_date", language), width="small"),
            "topic": st.column_config.TextColumn(t("planner.col.topic", language), width="medium"),
            "phase": st.column_config.TextColumn(t("planner.col.phase", language), width="medium"),
            "task": st.column_config.TextColumn(t("planner.col.task", language), width="large"),
            "hours": st.column_config.NumberColumn(t("planner.col.hours", language), format="%.1f h"),
            "quiz_required_label": st.column_config.TextColumn(
                t("planner.col.quiz_required", language),
                help=t("planner.col.quiz_required_help", language),
            ),
            "mark_as_done": st.column_config.CheckboxColumn(t("planner.col.mark_as_done", language)),
            "completion_note": st.column_config.TextColumn(
                t("planner.col.completion_note", language),
                help=t("planner.col.completion_note_help", language),
            ),
        },
    )
    if _apply_completed_updates(active_plan, edited_df.to_dict("records"), course_scope=course_scope):
        update_active_course_bucket(
            active_plan=active_plan,
            study_plans=_sync_active_plan_history(active_plan, course_context().get("study_plans", [])),
        )
        touch_activity()
        st.success(t("planner.timeline_saved", language))
        st.rerun()


import streamlit as st

from src.retrieval import CourseMaterialIndexer
from src.ui.study_plan_page import _apply_completed_updates, _sync_active_plan_history
from src.tools.state import (
    add_course,
    course_context,
    delete_course,
    get_active_course,
    init_state,
    set_authenticated_user,
    rename_course,
    set_active_course,
    update_course_details,
    update_active_course_bucket,
)


def setup_function() -> None:
    st.session_state.clear()


def test_multi_course_state_is_separated() -> None:
    init_state()

    math = add_course("Math")
    update_active_course_bucket(
        chat_history=[{"role": "user", "content": "math chat"}],
        chat_summaries=[{"summary_id": "active_session", "summary": "math summary"}],
        reminders=[{"reminder_id": "math-reminder", "title": "study limits"}],
        quiz_attempts=[{"score_percent": 80, "weak_topics": ["limits"]}],
    )

    physics = add_course("Physics")
    update_active_course_bucket(
        chat_history=[{"role": "user", "content": "physics chat"}],
        chat_summaries=[{"summary_id": "active_session", "summary": "physics summary"}],
        reminders=[{"reminder_id": "physics-reminder", "title": "study waves"}],
        quiz_attempts=[{"score_percent": 60, "weak_topics": ["waves"]}],
    )

    assert course_context()["chat_history"][0]["content"] == "physics chat"
    assert course_context()["chat_summaries"][0]["summary"] == "physics summary"
    assert course_context()["reminders"][0]["title"] == "study waves"
    assert course_context()["quiz_attempts"][0]["weak_topics"] == ["waves"]
    assert course_context()["all_courses"][1]["average_score"] == 60

    set_active_course(math["id"])
    assert course_context()["chat_history"][0]["content"] == "math chat"
    assert course_context()["chat_summaries"][0]["summary"] == "math summary"
    assert course_context()["reminders"][0]["title"] == "study limits"
    assert course_context()["quiz_attempts"][0]["weak_topics"] == ["limits"]
    assert course_context()["all_courses"][0]["average_score"] == 80
    assert course_context()["all_courses"][0]["chat_summaries"] == 1
    assert course_context()["all_courses"][0]["reminders"] == 1

    set_active_course(physics["id"])
    assert course_context()["chat_history"][0]["content"] == "physics chat"


def test_switching_courses_does_not_leak_chat_history() -> None:
    init_state()
    ml = add_course("Machine Learning")
    update_active_course_bucket(chat_history=[{"role": "user", "content": "ml chat only"}])
    security = add_course("Security")
    update_active_course_bucket(chat_history=[{"role": "user", "content": "security chat only"}])

    set_active_course(ml["id"])
    assert course_context()["chat_history"] == [{"role": "user", "content": "ml chat only"}]

    set_active_course(security["id"])
    assert course_context()["chat_history"] == [{"role": "user", "content": "security chat only"}]


def test_course_rename_and_delete_update_active_state() -> None:
    init_state()
    first = add_course("Machine Learning")
    second = add_course("Databases")

    result = rename_course(first["id"], "Deep Learning")
    assert result["ok"] is True
    assert result["course"]["name"] == "Deep Learning"

    duplicate = rename_course(first["id"], "Databases")
    assert duplicate == {"ok": False, "reason": "duplicate_name"}

    set_active_course(first["id"])
    deleted = delete_course(first["id"])
    assert deleted["ok"] is True
    assert get_active_course()["id"] == second["id"]

    deleted = delete_course(second["id"])
    assert deleted["ok"] is True
    assert get_active_course() is None
    assert st.session_state["chat_history"] == []


def test_plan_timeline_completion_updates_active_plan_and_history() -> None:
    from src.tools.study_plan_tasks import build_task_id

    tasks = [
        {
            "date": "2026-05-01",
            "topic": "SVM",
            "phase": "Concept review",
            "task": "Review notes",
            "completed": False,
        },
        {
            "date": "2026-05-02",
            "topic": "Trees",
            "phase": "Practice",
            "task": "Solve exercises",
            "completed": False,
        },
    ]
    for task in tasks:
        task["task_id"] = build_task_id(task, "course-ml")
    plan = {
        "course_name": "Machine Learning",
        "exam_date": "2026-06-01",
        "tasks": tasks,
    }
    history = [{"course_name": "Machine Learning", "exam_date": "2026-06-01", "tasks": list(plan["tasks"])}]

    changed = _apply_completed_updates(
        plan,
        [
            {"task_id": tasks[0]["task_id"], "mark_as_done": True},
            {"task_id": tasks[1]["task_id"], "mark_as_done": False},
        ],
        course_scope="course-ml",
    )
    synced_history = _sync_active_plan_history(plan, history)

    assert changed is True
    assert plan["tasks"][0]["completed"] is True
    assert synced_history[0] is plan


def test_legacy_course_bucket_missing_key_gets_default() -> None:
    init_state()
    course = add_course("Operating Systems")
    st.session_state["course_data"][course["id"]].pop("active_quiz")
    st.session_state["active_quiz"] = {"legacy": True}

    set_active_course(course["id"])

    assert st.session_state["active_quiz"] is None
    assert course_context()["chat_history"] == []


def test_workspace_persists_for_same_email(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RAFEEQAK_USER_STATE_DIR", str(tmp_path / "user_state"))
    init_state()
    user = {"email": "student@example.com", "user_metadata": {"full_name": "Demo Student"}}
    set_authenticated_user(user=user, access_token="access", refresh_token="refresh")

    course = add_course("Data Mining")
    update_active_course_bucket(
        chat_history=[{"role": "user", "content": "what is clustering?"}],
        chat_summaries=[{"summary_id": "active_session", "summary": "clustering summary"}],
        reminders=[{"reminder_id": "cluster-reminder", "title": "review clustering"}],
        uploads=[{"course_id": course["id"], "stored_name": "notes.txt"}],
        active_plan={"course_name": "Data Mining", "tasks": [], "weak_topics": ["k-means"]},
    )

    st.session_state.clear()
    init_state()
    set_authenticated_user(user=user, access_token="access", refresh_token="refresh")

    assert get_active_course()["name"] == "Data Mining"
    restored = course_context()
    assert restored["chat_history"][0]["content"] == "what is clustering?"
    assert restored["chat_summaries"][0]["summary"] == "clustering summary"
    assert restored["reminders"][0]["title"] == "review clustering"
    assert restored["uploads"][0]["stored_name"] == "notes.txt"
    assert restored["active_plan"]["weak_topics"] == ["k-means"]


def test_course_difficulty_update_is_reflected_in_summary() -> None:
    init_state()
    course = add_course("Compilers")

    result = update_course_details(course["id"], difficulty="Hard")

    assert result["ok"] is True
    assert course_context()["all_courses"][0]["difficulty"] == "Hard"


def test_course_material_indexer_can_rename_and_remove_course(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    course_dir = uploads_dir / "course-a"
    course_dir.mkdir(parents=True)
    material = course_dir / "notes.txt"
    material.write_text("gradient descent optimizes model weights", encoding="utf-8")

    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    result = indexer.index_file(material, course_id="course-a", course_name="Machine Learning")
    assert result["ok"] is True

    indexer.rename_course(course_id="course-a", course_name="Deep Learning")
    match = indexer.search("gradient", course_id="course-a")[0]
    assert match.course_name == "Deep Learning"

    removal = indexer.remove_course(course_id="course-a")
    assert removal["removed_files"] == 1
    assert removal["removed_chunks"] == 1
    assert indexer.search("gradient", course_id="course-a") == []
    assert not material.exists()


def test_sources_panel_stats_only_include_active_course_sources(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    ml_dir = uploads_dir / "ml-course"
    sec_dir = uploads_dir / "security-course"
    ml_dir.mkdir(parents=True)
    sec_dir.mkdir(parents=True)
    ml_dir.joinpath("ml_notes.txt").write_text("Gradient descent and backpropagation.", encoding="utf-8")
    sec_dir.joinpath("soc_notes.txt").write_text("SOC tiers and threat hunting.", encoding="utf-8")

    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    indexer.index_all(course_id="ml-course", course_name="Machine Learning")
    indexer.index_all(course_id="security-course", course_name="Security")

    stats = indexer.stats(course_id="ml-course")

    assert stats["sources"] == ["ml_notes.txt"]
    assert "soc_notes.txt" not in stats["sources"]

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.localization import t
from src.retrieval import CourseMaterialIndexer
from src.tools.state import (
    course_context,
    get_active_course,
    get_selected_language,
    require_active_course_message,
    touch_activity,
    update_active_course_bucket,
)
from src.ui.theme import render_page_hero


def render_upload_page(project_root: Path) -> None:
    language = get_selected_language()
    root_uploads_dir = project_root / "data" / "uploads"
    vector_store_dir = project_root / "data" / "vector_store"
    active_course = get_active_course()
    course_id = active_course["id"] if active_course else None
    course_name = active_course["name"] if active_course else None
    uploads_dir = root_uploads_dir / course_id if course_id else root_uploads_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)
    vector_store_dir.mkdir(parents=True, exist_ok=True)
    indexer = CourseMaterialIndexer(uploads_dir=root_uploads_dir, vector_store_dir=vector_store_dir)
    index_stats = indexer.stats(course_id=course_id)

    stored_files = _stored_material_files(uploads_dir)
    total_size_mb = round(sum(file.stat().st_size for file in stored_files) / (1024 * 1024), 2) if stored_files else 0.0

    render_page_hero(
        t("upload.title", language),
        t("upload.subtitle", language),
        chips=[
            f"{t('planner.course_name', language)}: {course_name or t('course.none_selected', language)}",
            t("upload.files_chip", language, count=len(stored_files)),
            t("upload.chunks_chip", language, count=index_stats["chunks"]),
            t("upload.disk_chip", language, size=total_size_mb),
        ],
        accent_chip=t("upload.accent", language),
        language=language,
    )

    course_warning = require_active_course_message()
    if course_warning:
        st.info(course_warning)

    upload_col, library_col = st.columns([1.4, 1], gap="large", vertical_alignment="top")

    with upload_col:
        with st.container(border=True):
            st.markdown(f"#### {t('upload.add_materials', language)}")
            files = st.file_uploader(
                t("upload.uploader", language),
                type=["pdf", "txt", "md", "docx", "pptx"],
                accept_multiple_files=True,
                disabled=active_course is None,
            )

            if st.button(t("upload.save", language), type="primary", use_container_width=True, disabled=active_course is None):
                if not files:
                    st.warning(t("upload.select_file", language))
                else:
                    index_results = []
                    for file in files:
                        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                        safe_name = f"{timestamp}_{file.name}"
                        destination = uploads_dir / safe_name
                        destination.write_bytes(file.getbuffer())
                        index_results.append(indexer.index_file(destination, course_id=course_id, course_name=course_name))
                        uploads = course_context()["uploads"]
                        uploads.append(
                            {
                                "course_id": course_id,
                                "course_name": course_name,
                                "original_name": file.name,
                                "stored_name": safe_name,
                                "saved_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
                            }
                        )
                        update_active_course_bucket(uploads=uploads)
                    touch_activity()
                    indexed_count = sum(1 for result in index_results if result["ok"])
                    chunk_count = sum(result.get("chunks", 0) for result in index_results if result["ok"])
                    st.success(t("upload.saved", language, files=len(files), chunks=chunk_count))
                    failed_results = [result for result in index_results if not result["ok"]]
                    if failed_results:
                        failed_names = ", ".join(f"{item['file_name']}: {item['reason']}" for item in failed_results)
                        st.warning(t("upload.failed", language, count=len(failed_results), details=failed_names))
                    elif indexed_count:
                        st.info(t("upload.rag_ready", language))
                    st.rerun()

    with library_col:
        with st.container(border=True):
            st.markdown(f"#### {t('upload.library', language)}")
            st.metric(t("upload.stored_files", language), len(stored_files), border=True)
            st.metric(t("upload.indexed_chunks", language), index_stats["chunks"], border=True)
            st.metric(t("upload.total_size", language), f"{total_size_mb} MB", border=True)

    st.markdown(f"### {t('upload.files_heading', language)}")
    if not stored_files:
        st.info(t("upload.no_files", language))
        return

    st.caption(t("upload.delete_caption", language))
    table_rows = []
    for file_path in stored_files:
        stat = file_path.stat()
        table_rows.append(
            {
                "file_name": file_path.name,
                "size_kb": round(stat.st_size / 1024, 2),
                "last_modified_utc": datetime.utcfromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            }
        )

    st.dataframe(
        pd.DataFrame(table_rows),
        use_container_width=True,
        height=320,
        hide_index=True,
        column_config={
            "file_name": st.column_config.TextColumn(t("upload.col.file_name", language), width="medium"),
            "size_kb": st.column_config.NumberColumn(t("upload.col.size", language), format="%.2f", width="small"),
            "last_modified_utc": st.column_config.TextColumn(t("upload.col.updated", language), width="medium"),
        },
    )

    st.markdown(f"#### {t('upload.manage', language)}")
    with st.container(height=360, border=True, key="upload_file_manager"):
        for file_path in stored_files:
            stat = file_path.stat()
            file_col, size_col, action_col = st.columns([3, 1, 1], gap="small", vertical_alignment="center")
            with file_col:
                st.write(file_path.name)
            with size_col:
                st.caption(f"{round(stat.st_size / 1024, 2)} KB")
            with action_col:
                if st.button(t("common.delete", language), key=f"delete_upload_{file_path.name}", use_container_width=True):
                    result = indexer.remove_file(file_path, course_id=course_id)
                    if result["ok"]:
                        uploads = [
                            item
                            for item in course_context().get("uploads", [])
                            if item.get("stored_name") != file_path.name
                        ]
                        update_active_course_bucket(uploads=uploads)
                        touch_activity()
                        st.success(
                            t("upload.deleted", language, file_name=file_path.name, chunks=result["removed_chunks"])
                        )
                        st.rerun()
                    else:
                        st.warning(t("upload.delete_failed", language, file_name=file_path.name, reason=result["reason"]))


def _stored_material_files(uploads_dir: Path) -> list[Path]:
    return sorted(
        file_path
        for file_path in uploads_dir.glob("*")
        if file_path.is_file() and file_path.name != ".gitkeep"
    )

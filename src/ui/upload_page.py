from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.retrieval import CourseMaterialIndexer
from src.tools.state import touch_activity
from src.ui.theme import render_page_hero


def render_upload_page(project_root: Path) -> None:
    uploads_dir = project_root / "data" / "uploads"
    vector_store_dir = project_root / "data" / "vector_store"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    vector_store_dir.mkdir(parents=True, exist_ok=True)
    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    index_stats = indexer.stats()

    stored_files = sorted(uploads_dir.glob("*"))
    total_size_mb = round(sum(file.stat().st_size for file in stored_files) / (1024 * 1024), 2) if stored_files else 0.0

    render_page_hero(
        "Course Material Hub",
        "Centralize lecture notes and source files to prepare for retrieval and grounded answers.",
        chips=[
            f"Files stored: {len(stored_files)}",
            f"Indexed chunks: {index_stats['chunks']}",
            f"Disk usage: {total_size_mb} MB",
        ],
        accent_chip="Upload center",
    )

    upload_col, library_col = st.columns([1.4, 1], gap="large")

    with upload_col:
        with st.container(border=True):
            st.markdown("#### Add materials")
            files = st.file_uploader(
                "Upload PDFs, slides, or notes",
                type=["pdf", "txt", "md", "docx", "pptx"],
                accept_multiple_files=True,
            )

            if st.button("Save uploaded files", type="primary", width="stretch"):
                if not files:
                    st.warning("Select at least one file first.")
                else:
                    index_results = []
                    for file in files:
                        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                        safe_name = f"{timestamp}_{file.name}"
                        destination = uploads_dir / safe_name
                        destination.write_bytes(file.getbuffer())
                        index_results.append(indexer.index_file(destination))
                        st.session_state.uploads.append(
                            {
                                "original_name": file.name,
                                "stored_name": safe_name,
                                "saved_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
                            }
                        )
                    touch_activity()
                    indexed_count = sum(1 for result in index_results if result["ok"])
                    chunk_count = sum(result.get("chunks", 0) for result in index_results if result["ok"])
                    st.success(f"Saved {len(files)} file(s) and indexed {chunk_count} chunk(s).")
                    failed_results = [result for result in index_results if not result["ok"]]
                    if failed_results:
                        failed_names = ", ".join(f"{item['file_name']}: {item['reason']}" for item in failed_results)
                        st.warning(f"{len(failed_results)} file(s) could not be indexed. {failed_names}")
                    elif indexed_count:
                        st.info("The Course RAG Agent can now retrieve from these materials in Chat.")
                    st.rerun()

    with library_col:
        with st.container(border=True):
            st.markdown("#### Library snapshot")
            st.metric("Stored files", len(stored_files), border=True)
            st.metric("Indexed chunks", index_stats["chunks"], border=True)
            st.metric("Total size", f"{total_size_mb} MB", border=True)

    st.markdown("### Uploaded files")
    if not stored_files:
        st.info("No files uploaded yet.")
        return

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
        width="stretch",
        hide_index=True,
        column_config={
            "file_name": st.column_config.TextColumn("File Name", width="large"),
            "size_kb": st.column_config.NumberColumn("Size (KB)", format="%.2f"),
            "last_modified_utc": st.column_config.TextColumn("Updated (UTC)", width="medium"),
        },
    )

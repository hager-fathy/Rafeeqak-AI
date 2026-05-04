from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.tools.state import touch_activity
from src.ui.theme import render_page_hero


def render_upload_page(project_root: Path) -> None:
    uploads_dir = project_root / "data" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    stored_files = sorted(uploads_dir.glob("*"))
    total_size_mb = round(sum(file.stat().st_size for file in stored_files) / (1024 * 1024), 2) if stored_files else 0.0

    render_page_hero(
        "Course Material Hub",
        "Centralize lecture notes and source files to prepare for retrieval and grounded answers.",
        chips=[
            f"Files stored: {len(stored_files)}",
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
                    for file in files:
                        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                        safe_name = f"{timestamp}_{file.name}"
                        destination = uploads_dir / safe_name
                        destination.write_bytes(file.getbuffer())
                        st.session_state.uploads.append(
                            {
                                "original_name": file.name,
                                "stored_name": safe_name,
                                "saved_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
                            }
                        )
                    touch_activity()
                    st.success(f"Saved {len(files)} file(s) to {uploads_dir}.")
                    st.rerun()

    with library_col:
        with st.container(border=True):
            st.markdown("#### Library snapshot")
            st.metric("Stored files", len(stored_files), border=True)
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

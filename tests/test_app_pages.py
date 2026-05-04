from streamlit.testing.v1 import AppTest


def test_app_starts_for_public_pages() -> None:
    app = AppTest.from_file("app.py", default_timeout=10)
    app.run()

    assert not app.exception


def test_app_starts_for_authenticated_pages() -> None:
    pages = [
        "chat",
        "study_plan",
        "upload_materials",
        "quiz",
        "progress_dashboard",
        "account",
    ]

    for page in pages:
        app = AppTest.from_file("app.py", default_timeout=10)
        app.session_state["auth_user"] = {
            "email": "demo@example.com",
            "user_metadata": {"full_name": "Demo User"},
        }
        app.session_state["selected_page"] = page
        app.run()

        assert not app.exception, f"{page} raised {app.exception}"

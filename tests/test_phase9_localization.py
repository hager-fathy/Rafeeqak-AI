from streamlit.testing.v1 import AppTest

from src.localization import detect_language, is_rtl, normalize_language, t
from src.ui.theme import inject_global_styles


def test_localization_helper_translates_and_falls_back() -> None:
    assert normalize_language("Arabic") == "ar"
    assert detect_language("ماذا أذاكر اليوم؟") == "ar"
    assert is_rtl("ar") is True
    assert t("login.title", "ar") == "تسجيل الدخول"
    assert t("missing.key", "ar") == "missing.key"


def test_theme_injects_rtl_css(monkeypatch) -> None:
    captured = {}

    def fake_markdown(body: str, *, unsafe_allow_html: bool) -> None:
        captured["body"] = body
        captured["unsafe"] = unsafe_allow_html

    monkeypatch.setattr("src.ui.theme.st.markdown", fake_markdown)

    inject_global_styles("ar")

    assert captured["unsafe"] is True
    assert "direction: rtl" in captured["body"]
    assert '[data-testid="stAppViewContainer"] {\n  direction: ltr;' in captured["body"]
    assert '[data-testid="stHorizontalBlock"] {\n  direction: ltr;' in captured["body"]
    assert '[data-testid="stHorizontalBlock"] > div' not in captured["body"]
    assert "Noto Sans Arabic" in captured["body"]


def test_app_starts_with_arabic_language_selected() -> None:
    app = AppTest.from_file("app.py", default_timeout=10)
    app.session_state["selected_language"] = "ar"
    app.run()

    assert not app.exception

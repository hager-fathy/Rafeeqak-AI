from __future__ import annotations

from html import escape

import streamlit as st

from src.localization import is_rtl, normalize_language, t


def inject_global_styles(language: str = "en") -> None:
    language = normalize_language(language)
    direction_css = _direction_styles(language)
    styles = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg-base: #070b10;
  --bg-layer: #0b1017;
  --surface: #111a24;
  --surface-soft: #162230;
  --surface-raised: #121c28;
  --text-strong: #e7f0fb;
  --text-muted: #9cb0c6;
  --border: #243548;
  --primary: #5b8cff;
  --primary-deep: #315fdc;
  --accent: #ff915a;
  --shadow-soft: 0 12px 28px rgba(0, 0, 0, 0.34);
  --radius: 8px;
  --app-max-width: 1400px;
  --app-side-padding: clamp(0.85rem, 2.5vw, 1.35rem);
  --block-gap: 0.85rem;
}

html, body, [class*="css"] {
  font-family: "Plus Jakarta Sans", "Noto Sans Arabic", "Segoe UI", sans-serif;
  color: var(--text-strong);
}

code, pre, kbd, samp {
  font-family: "JetBrains Mono", monospace !important;
}

[data-testid="stAppViewContainer"] {
  background: linear-gradient(180deg, #070b10 0%, #0b1017 48%, #0d1219 100%);
}

[data-testid="stHeader"] {
  background: transparent;
}

[data-testid="collapsedControl"],
[data-testid="stSidebar"] {
  display: none !important;
}

section.main > div,
.block-container,
[data-testid="stMainBlockContainer"] {
  max-width: var(--app-max-width);
  margin: 0 auto;
  padding: 0.9rem var(--app-side-padding) 2.4rem;
}

.main-app-container,
.st-key-main_app_container {
  width: 100%;
  max-width: var(--app-max-width);
  margin: 0 auto;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}

.st-key-main_app_container [data-testid="stVerticalBlock"] {
  gap: var(--block-gap);
}

.st-key-main_app_container [data-testid="stHorizontalBlock"] {
  gap: 0.85rem;
  align-items: stretch;
}

* {
  scrollbar-width: thin;
  scrollbar-color: rgba(156, 176, 198, 0.42) transparent;
}

*::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

*::-webkit-scrollbar-track {
  background: transparent;
}

*::-webkit-scrollbar-thumb {
  background: rgba(156, 176, 198, 0.42);
  border: 2px solid transparent;
  border-radius: 999px;
  background-clip: content-box;
}

*::-webkit-scrollbar-thumb:hover {
  background: rgba(156, 176, 198, 0.62);
  background-clip: content-box;
}

h1, h2, h3 {
  letter-spacing: 0;
}

[data-testid="stVerticalBlockBorderWrapper"] {
  border-color: rgba(79, 103, 130, 0.62) !important;
  border-radius: var(--radius) !important;
}

[data-testid="stMetric"] {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: linear-gradient(180deg, #131d28 0%, #0f1722 100%);
  padding: 0.45rem 0.4rem;
  box-shadow: none;
  min-height: 96px;
}

[data-testid="stMetricLabel"] {
  color: var(--text-muted);
  font-weight: 600;
  line-height: 1.25;
}

[data-testid="stMetricValue"] {
  color: var(--text-strong);
  font-size: 1.45rem;
  line-height: 1.15;
}

[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {
  color: var(--text-muted);
}

[data-testid="stCaptionContainer"] {
  color: #8ea4bb;
}

.stButton > button, [data-testid="stFormSubmitButton"] button {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-deep) 100%);
  color: #f8fbff;
  border: 1px solid rgba(91, 140, 255, 0.38);
  border-radius: var(--radius);
  font-weight: 700;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
  min-height: 2.65rem;
}

.stButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(49, 95, 220, 0.34);
}

.stButton > button:disabled,
[data-testid="stFormSubmitButton"] button:disabled {
  transform: none;
  box-shadow: none;
  opacity: 0.56;
}

.stTextInput,
.stNumberInput,
.stDateInput,
.stTextArea,
.stSelectbox,
[data-testid="stMultiSelect"],
[data-testid="stFileUploader"],
[data-testid="stTimeInput"] {
  margin-bottom: 0.25rem;
}

.stTextInput input, .stNumberInput input, .stDateInput input, .stTextArea textarea {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: #e6eef8;
  min-height: 2.65rem;
}

.stTextInput input::placeholder,
.stTextArea textarea::placeholder,
[data-testid="stChatInput"] textarea::placeholder {
  color: rgba(180, 198, 219, 0.7);
  opacity: 1;
}

.stSelectbox [data-baseweb="select"] > div,
[data-testid="stDateInput"] [data-baseweb="input"] > div,
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
  background: var(--surface) !important;
  border-color: var(--border) !important;
  color: #e6eef8 !important;
}

[data-testid="stFileUploaderDropzone"] {
  border: 1px dashed #376286;
  border-radius: var(--radius);
  background: rgba(18, 30, 43, 0.72);
}

[data-testid="stDataFrame"],
[data-testid="stDataEditor"] {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: none;
  max-width: 100%;
}

[data-testid="stChatMessage"] {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: rgba(17, 28, 41, 0.9);
  margin: 0.42rem 0;
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
  overflow-wrap: anywhere;
}

[data-testid="stChatInput"] {
  max-width: var(--app-max-width);
  margin: 0 auto;
}

[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {
  border-color: #61a6d8 !important;
}

[data-testid="stSegmentedControl"] {
  border: 1px solid #2d4660;
  border-radius: var(--radius);
  padding: 0.34rem;
  background: linear-gradient(180deg, rgba(18, 29, 42, 0.96), rgba(14, 23, 34, 0.96));
  box-shadow: none;
  overflow-x: auto;
}

[data-testid="stSegmentedControl"] [role="radiogroup"] {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
  gap: 0.4rem;
  min-width: min-content;
}

[data-testid="stSegmentedControl"] [role="radio"] {
  border-radius: var(--radius) !important;
  border: 1px solid #2c4661 !important;
  background: #122131 !important;
  color: #bfd2e8 !important;
  font-weight: 700 !important;
  padding-top: 0.3rem !important;
  padding-bottom: 0.3rem !important;
}

[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"] {
  background: linear-gradient(135deg, #5b8cff 0%, #315fdc 100%) !important;
  color: #f8fbff !important;
  border-color: rgba(91, 140, 255, 0.9) !important;
}

[data-testid="stElementContainer"] p.top-nav-copy {
  text-align: center;
}

[data-testid="stAlert"] {
  background: rgba(22, 35, 49, 0.94);
  border: 1px solid #2c4b67;
  color: #d9e6f3;
  border-radius: var(--radius);
}

.hero-shell {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius);
  padding: 1.05rem 1.15rem;
  margin-bottom: 1rem;
  border: 1px solid #2b3f56;
  background: linear-gradient(118deg, rgba(18, 29, 43, 0.98) 0%, rgba(15, 25, 37, 1) 100%);
  box-shadow: var(--shadow-soft);
  animation: fadeUp 0.48s ease-out both;
}

.hero-shell::after {
  content: "";
  position: absolute;
  inset: auto 0 0 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary), var(--accent));
  opacity: 0.8;
}

.hero-kicker {
  display: inline-block;
  font-size: 0.74rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
  color: #9bb7ff;
  margin-bottom: 0.35rem;
}

.hero-title {
  margin: 0;
  color: var(--text-strong);
  font-size: clamp(1.4rem, 2.5vw, 2.1rem);
  line-height: 1.18;
}

.hero-subtitle {
  margin: 0.45rem 0 0.72rem 0;
  color: var(--text-muted);
  font-weight: 500;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.chip {
  display: inline-flex;
  align-items: center;
  background: rgba(91, 140, 255, 0.13);
  border: 1px solid rgba(91, 140, 255, 0.34);
  color: #b8c9ff;
  padding: 0.28rem 0.58rem;
  border-radius: var(--radius);
  font-size: 0.78rem;
  font-weight: 600;
  max-width: 100%;
  overflow-wrap: anywhere;
}

.chip-accent {
  background: rgba(255, 145, 90, 0.13);
  border-color: rgba(255, 145, 90, 0.3);
  color: #ffb088;
}

.panel-title {
  font-weight: 700;
  color: var(--text-strong);
  margin-bottom: 0.2rem;
}

.muted-copy {
  color: var(--text-muted);
}

.sidebar-brand {
  border: 1px solid rgba(110, 149, 184, 0.28);
  border-radius: var(--radius);
  padding: 0.8rem 0.78rem;
  margin-bottom: 0.8rem;
  background: linear-gradient(140deg, rgba(74, 116, 155, 0.18), rgba(26, 46, 68, 0.28));
}

.sidebar-brand h3 {
  margin: 0;
  font-size: 1rem;
  color: #e8f1fa;
}

.sidebar-brand p {
  margin: 0.42rem 0 0;
  font-size: 0.82rem;
  color: #b9cee1;
}

.top-nav-title {
  text-align: center;
  font-size: 0.86rem;
  letter-spacing: 0;
  text-transform: uppercase;
  color: #8ea7c1;
  margin: 0.1rem 0 0.38rem 0;
  font-weight: 700;
}

.st-key-chat_history_panel,
.st-key-dashboard_course_cards,
.st-key-upload_file_manager,
.st-key-quiz_questions_panel,
.st-key-quiz_feedback_panel,
.st-key-quiz_flashcards_panel,
.st-key-chat_summary_panel,
.st-key-planner_recovery_panel {
  overflow-y: auto;
  overflow-x: hidden;
}

.st-key-reminder_notifications_panel,
.st-key-dashboard_alerts_panel {
  max-height: 180px;
  overflow-y: auto;
  overflow-x: hidden;
}

{direction_css}

@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 900px) {
  section.main > div {
    padding-top: 0.7rem;
  }

  .hero-shell {
    padding: 1rem 0.95rem;
  }

  [data-testid="stSegmentedControl"] [role="radiogroup"] {
    grid-template-columns: 1fr;
  }

  .st-key-main_app_container [data-testid="stHorizontalBlock"] {
    gap: 0.65rem;
  }
}

@media (max-width: 640px) {
  :root {
    --app-side-padding: 0.75rem;
  }

  [data-testid="stMetric"] {
    min-height: 82px;
  }

  [data-testid="stMetricValue"] {
    font-size: 1.2rem;
  }
}
</style>
        """
    st.markdown(styles.replace("{direction_css}", direction_css), unsafe_allow_html=True)


def render_page_hero(
    title: str,
    subtitle: str,
    *,
    chips: list[str] | None = None,
    accent_chip: str | None = None,
    language: str = "en",
) -> None:
    language = normalize_language(language)
    chip_html = ""
    if chips:
        chip_html += "".join([f"<span class='chip'>{escape(item)}</span>" for item in chips])
    if accent_chip:
        chip_html += f"<span class='chip chip-accent'>{escape(accent_chip)}</span>"
    direction = "rtl" if is_rtl(language) else "ltr"

    st.markdown(
        f"""
<section class="hero-shell" dir="{direction}">
  <span class="hero-kicker">{escape(t("hero.kicker", language))}</span>
  <h2 class="hero-title">{escape(title)}</h2>
  <p class="hero-subtitle">{escape(subtitle)}</p>
  <div class="chip-row">{chip_html}</div>
</section>
        """,
        unsafe_allow_html=True,
    )


def _direction_styles(language: str) -> str:
    if not is_rtl(language):
        return """
[data-testid="stAppViewContainer"] {
  direction: ltr;
  text-align: left;
}

[data-testid="stHorizontalBlock"] {
  direction: ltr;
}
"""

    return """
[data-testid="stAppViewContainer"] {
  direction: ltr;
}

section.main,
[data-testid="stMarkdownContainer"],
[data-testid="stForm"],
[data-testid="stChatInput"],
[data-testid="stChatMessage"],
[data-testid="stVerticalBlockBorderWrapper"] {
  direction: rtl;
  text-align: right;
}

[data-testid="stHorizontalBlock"] {
  direction: ltr;
}

.stTextInput input,
.stNumberInput input,
.stTextArea textarea,
[data-testid="stDateInput"] input,
[data-testid="stTimeInput"] input,
[data-testid="stChatInput"] textarea {
  direction: rtl;
  text-align: right;
}

.stTextInput input::placeholder,
.stTextArea textarea::placeholder,
[data-testid="stChatInput"] textarea::placeholder {
  text-align: right;
}

[data-testid="stSegmentedControl"] [role="radiogroup"],
[data-baseweb="select"] {
  direction: rtl;
}

.chip-row {
  justify-content: flex-start;
}

[data-testid="stDataFrame"],
[data-testid="stTable"],
[data-testid="stDataEditor"],
[data-testid="stMetric"] {
  direction: rtl;
  text-align: right;
}

[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
[data-testid="stCaptionContainer"] {
  text-align: right;
}
"""

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
  --text-strong: #e7f0fb;
  --text-muted: #9cb0c6;
  --border: #243548;
  --primary: #5b8cff;
  --primary-deep: #315fdc;
  --accent: #ff915a;
  --shadow-soft: 0 16px 40px rgba(0, 0, 0, 0.46);
}

html, body, [class*="css"] {
  font-family: "Plus Jakarta Sans", "Noto Sans Arabic", "Segoe UI", sans-serif;
  color: var(--text-strong);
}

code, pre, kbd, samp {
  font-family: "JetBrains Mono", monospace !important;
}

[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(1400px 700px at -10% -20%, #183047 0%, transparent 45%),
    radial-gradient(1000px 520px at 110% -10%, #402540 0%, transparent 40%),
    linear-gradient(180deg, var(--bg-base) 0%, var(--bg-layer) 100%);
}

[data-testid="stHeader"] {
  background: transparent;
}

[data-testid="collapsedControl"],
[data-testid="stSidebar"] {
  display: none !important;
}

section.main > div {
  max-width: 1180px;
  padding-top: 0.85rem;
  padding-bottom: 2rem;
}

h1, h2, h3 {
  letter-spacing: 0;
}

[data-testid="stMetric"] {
  border: 1px solid var(--border);
  border-radius: 16px;
  background: linear-gradient(180deg, #131e2a 0%, #0f1722 100%);
  padding: 0.4rem 0.3rem;
  box-shadow: var(--shadow-soft);
}

[data-testid="stMetricLabel"] {
  color: var(--text-muted);
  font-weight: 600;
}

[data-testid="stMetricValue"] {
  color: var(--text-strong);
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
  border-radius: 12px;
  font-weight: 700;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}

.stButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(49, 95, 220, 0.34);
}

.stTextInput input, .stNumberInput input, .stDateInput input, .stTextArea textarea {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  color: #e6eef8;
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
  border-radius: 14px;
  background: rgba(18, 30, 43, 0.72);
}

[data-testid="stDataFrame"] {
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow-soft);
}

[data-testid="stChatMessage"] {
  border: 1px solid var(--border);
  border-radius: 14px;
  background: rgba(17, 28, 41, 0.9);
}

[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {
  border-color: #61a6d8 !important;
}

[data-testid="stSegmentedControl"] {
  border: 1px solid #2d4660;
  border-radius: 16px;
  padding: 0.34rem;
  background: linear-gradient(180deg, rgba(18, 29, 42, 0.96), rgba(14, 23, 34, 0.96));
  box-shadow: var(--shadow-soft);
}

[data-testid="stSegmentedControl"] [role="radiogroup"] {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 0.4rem;
}

[data-testid="stSegmentedControl"] [role="radio"] {
  border-radius: 12px !important;
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
}

.hero-shell {
  position: relative;
  overflow: hidden;
  border-radius: 18px;
  padding: 1.2rem 1.4rem;
  margin-bottom: 1rem;
  border: 1px solid #2b3f56;
  background:
    linear-gradient(118deg, rgba(18, 29, 43, 0.95) 0%, rgba(15, 25, 37, 0.98) 68%, rgba(18, 30, 45, 1) 100%);
  box-shadow: var(--shadow-soft);
  animation: fadeUp 0.48s ease-out both;
}

.hero-shell::after {
  content: "";
  position: absolute;
  width: 320px;
  height: 320px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(91, 140, 255, 0.2) 0%, rgba(91, 140, 255, 0.0) 64%);
  right: -120px;
  top: -140px;
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
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
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
  border-radius: 14px;
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
}
"""

    return """
[data-testid="stAppViewContainer"],
section.main,
[data-testid="stMarkdownContainer"],
[data-testid="stForm"],
[data-testid="stChatInput"],
[data-testid="stChatMessage"] {
  direction: rtl;
  text-align: right;
}

.stTextInput input,
.stNumberInput input,
.stTextArea textarea,
[data-testid="stDateInput"] input {
  direction: rtl;
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
[data-testid="stMetric"] {
  direction: rtl;
  text-align: right;
}
"""

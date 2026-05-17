# Phase 13 Manual Demo Validation

## Validation Scope

This record covers the final end-to-end demo path described in `docs/final_demo_script.md`.

Validation date: 2026-05-17  
Workspace: `C:\Users\aa\Desktop\GEN\Rafeeqak-AI`  
Status: Environment blocked for live Streamlit execution in this workspace.

## Environment Check

| Check | Result | Evidence |
|---|---|---|
| `python` command available | Failed | `python` is not on PATH. |
| `py` launcher has registered Python | Failed | `py` exists, but reports no default installed Python. |
| `pytest` command available | Failed | `pytest` is not on PATH. |
| `streamlit` command available | Failed | `streamlit` is not on PATH. |
| Fallback bundled Python syntax check | Passed | `C:\Program Files (x86)\Nmap\zenmap\bin\python.exe -m py_compile ...` works for changed Python files. |

Because Streamlit and pytest are unavailable, the live browser walkthrough could not be completed on this machine during this pass. The demo script and validation checklist are ready, and the remaining runtime step is to rerun this validation in an environment with the project dependencies installed.

## Commands Attempted

```powershell
py -0p
py -m pytest tests\test_phase13_demo_docs.py
streamlit run app.py
& 'C:\Program Files (x86)\Nmap\zenmap\bin\python.exe' -m py_compile tests\test_phase13_demo_docs.py src\agents\memory_agent.py src\agents\reminder_agent.py src\prompts\registry.py
```

Result summary:

- `py -0p`: no installed Python registered.
- `py -m pytest tests\test_phase13_demo_docs.py`: failed because there is no default Python.
- `streamlit run app.py`: failed because Streamlit is not installed or not on PATH.
- `py_compile`: passed for the changed Python files that can be syntax-checked with the bundled Python.

## Manual Validation Checklist

Use this checklist while running the app with `streamlit run app.py`.

| Step | Expected Result | Status |
|---|---|---|
| App starts | Public login/signup pages render without exception. | Blocked by missing Streamlit runtime |
| Login | Authenticated navigation appears. | Blocked by missing Streamlit runtime |
| No-course gate | Chat/upload/quiz/plan actions require an active course. | Blocked by missing Streamlit runtime |
| Create Machine Learning | Active course selector shows Machine Learning. | Blocked by missing Streamlit runtime |
| Upload ML notes | `machine_learning_notes.md` is saved and indexed for Machine Learning. | Blocked by missing Streamlit runtime |
| RAG answer | Backpropagation answer uses ML notes and includes course/file/chunk citation. | Blocked by missing Streamlit runtime |
| Vague RAG query | `Explain` asks for clarification instead of dumping chunks. | Blocked by missing Streamlit runtime |
| Chat summary | Summary records main topics, weaknesses, and next steps. | Blocked by missing Streamlit runtime |
| Study plan | Plan uses lecture count, finish period, hours, deadline, difficulty, and weak topics. | Blocked by missing Streamlit runtime |
| Reminders | Plan creates course-scoped reminders. | Blocked by missing Streamlit runtime |
| Quiz generation | Quiz shows loading/generated/failure states and uses selected-course material. | Blocked by missing Streamlit runtime |
| Quiz evaluation | Feedback includes partial scoring, weak topics, and recommendation. | Blocked by missing Streamlit runtime |
| Create Databases | Databases becomes a separate active course. | Blocked by missing Streamlit runtime |
| Course separation | Databases chat, uploads, plans, quizzes, weak topics, and reminders do not mix with Machine Learning. | Blocked by missing Streamlit runtime |
| Dashboard | Course cards and active-course metrics summarize progress, uploads, scores, weak topics, deadlines, and reminders. | Blocked by missing Streamlit runtime |
| Settings | Profile, language, daily hours, quiz defaults, difficulty, study preference, and reminders save. | Blocked by missing Streamlit runtime |
| Arabic RTL | Arabic language switch applies Arabic labels and RTL layout. | Blocked by missing Streamlit runtime |

## Readiness Evidence From Code And Tests

The following automated tests already cover the demo-critical behavior when pytest is available:

- `tests/test_app_pages.py`: app startup and authenticated page rendering.
- `tests/test_phase8_multicourse.py`: course state separation and course selector gating.
- `tests/test_phase9_localization.py`: Arabic localization and RTL support.
- `tests/test_phase5_rag.py`: course-scoped RAG retrieval, vague-query clarification, citations, and no raw chunk dumping.
- `tests/test_phase6_quiz.py`: quiz question types, quiz status states, partial scoring, and weak-topic feedback.
- `tests/test_phase10_prompts.py`: reusable prompt templates including chat summary and reminder generation.
- `tests/test_phase12_dashboard_settings_reminders.py`: settings persistence, dashboard rows, due reminders, and reminder creation.

## Runtime Validation Command

Run this after installing dependencies:

```powershell
pip install -r requirements.txt
python -m pytest
streamlit run app.py
```

Then execute `docs/final_demo_script.md` from top to bottom and update the status column in this file with Pass or Fail evidence.

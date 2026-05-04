# Supabase Setup Guide

Use this guide to enable Phase 3 cloud memory.

## 1. Create project

Create a Supabase project from the Supabase dashboard.

## 2. Apply schema

Open **SQL Editor** and run:

- `docs/supabase_schema.sql`

This creates:

- `student_profiles`
- `courses`
- `exams`
- `study_tasks`
- `quiz_scores`
- `weak_topics`

## 3. Configure environment

Copy `.env.example` to `.env`, then set:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_DEFAULT_STUDENT_EMAIL`
- `SUPABASE_DEFAULT_STUDENT_NAME`

## 4. Run app

```powershell
cd H:\GEN-AI\smart-study-planner
.venv\Scripts\python.exe -m streamlit run app.py
```

## 5. Verify memory sync

1. Create an account in **Sign up**.
2. If email confirmation is enabled, confirm email then use **Login**.
3. Generate a study plan in the **Study Plan** page.
4. Submit a quiz in the **Quiz** page.
5. Open **Progress Dashboard** and expand `Supabase memory snapshot`.

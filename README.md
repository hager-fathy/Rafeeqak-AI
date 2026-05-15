# Smart Study Planner

This repository contains phase 1, phase 2, phase 3 (Supabase memory), phase 4 (multi-agent routing), phase 5 (course-material RAG), phase 6 (quiz generation and evaluation), and phase 7 (CAG and structured database query) of the Smart Study Planner Chatbot project.

The enhanced roadmap in `project..md` now upgrades Rafeeqak toward a stronger multi-course study assistant where each course has its own materials, study plan, quizzes, flashcards, weak topics, progress, and chat history.

- Phase 1: project setup and base structure
- Phase 2: Streamlit UI pages (chat, study plan, upload, quiz, dashboard)
- Phase 3: persistent memory with Supabase schema and repository integration
- Phase 4: input routing, supervisor orchestration, study planner agent, memory handoff, and route trace logging
- Phase 5: local text extraction, chunking, vector-store persistence, and grounded Course RAG answers
- Phase 6: topic/RAG-grounded quiz generation, flashcards, scoring feedback, and weak-topic detection
- Phase 7: semantic response cache plus structured progress, deadline, score, and weak-topic queries
- Phase 8: planned multi-course core upgrade with global course selector and course-scoped data
- Phase 9: planned full Arabic localization, RTL layout, and UI polish
- Phase 10+: planned prompt templates, planner upgrades, dashboard analytics, flashcards, reminders, exports, and final demo hardening

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
   On Windows PowerShell:
   ```powershell
   Copy-Item .env.example .env
   ```
4. Run the app:
   ```bash
   streamlit run app.py
   ```

## Supabase Setup (Phase 3)

1. Create a Supabase project.
2. Open the SQL Editor and run:
   - `docs/supabase_schema.sql`
3. Fill `.env` values:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `SUPABASE_DEFAULT_STUDENT_EMAIL`
   - `SUPABASE_DEFAULT_STUDENT_NAME`
4. Restart Streamlit.
5. Optional step-by-step guide:
   - `docs/supabase_setup.md`

## Repository Layout

```text
smart-study-planner/
|-- app.py
|-- requirements.txt
|-- .env.example
|-- README.md
|-- data/
|   |-- uploads/
|   `-- vector_store/
|-- src/
|   |-- agents/
|   |-- memory/
|   |-- retrieval/
|   |-- tools/
|   `-- ui/
|-- tests/
`-- docs/
```

## What Is Implemented Now

- Authentication pages:
  - Login
  - Sign up
- Authenticated app pages:
  - Chat
  - Study Plan
  - Upload Materials
  - Quiz
  - Progress Dashboard
  - Account (logout)
- Session state for chat history, plans, quiz attempts, and uploads
- Local file upload storage in `data/uploads`
- Supabase memory sync for:
  - student profile (per logged-in user)
  - courses and exams
  - generated study tasks
  - quiz scores and weak topics
- Phase 4 agent flow:
  - Safety Agent screens unsafe routing attempts
  - Input Router Agent detects intent and language
  - Supervisor Agent selects and runs the specialist agent
  - Study Planner Agent creates plans and recommends next tasks
  - Memory Agent syncs plans and quiz attempts when Supabase is configured
  - Route traces are saved in session state and shown in Chat/Dashboard
- Phase 5 RAG flow:
  - Upload Materials saves PDFs, DOCX, PPTX, Markdown, and text files
  - Course materials are extracted, chunked, embedded into local sparse vectors, and stored in `data/vector_store/course_materials.json`
  - Chat questions about lectures, notes, PDFs, or explanations route to the Course RAG Agent
  - RAG answers include concise source citations from the retrieved chunks
- Phase 6 quiz flow:
  - Quiz Generator Agent creates MCQs and flashcards from a topic plus retrieved course chunks when available
  - Progress Evaluator Agent scores submitted answers and returns per-question feedback
  - Low quiz scores are saved as weak-topic signals through the Memory Agent when Supabase is configured
- Phase 7 CAG/database query flow:
  - repeated chat questions are reused from `data/cache/semantic_cache.json` when the session context is unchanged
  - progress, deadline, score, and weak-topic questions route to the Database Query Agent
  - structured answers use the active local session first and Supabase memory snapshots when available

## Next Phases

Upcoming phases should focus on:

- Full multi-course separation for materials, plans, quizzes, flashcards, weak topics, progress, and chat history
- Global course selector before chat, uploads, quiz, dashboard, and planning
- Full Arabic localization with RTL layout and language toggle
- Reusable prompt templates for RAG, quizzes, summaries, progress feedback, and planning
- Course-scoped RAG retrieval with clearer citations
- Better quiz types, partial text scoring, and stronger personalized feedback
- Per-course dashboard charts, settings page, reminders, and export features

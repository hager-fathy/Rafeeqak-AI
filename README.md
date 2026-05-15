# Smart Study Planner

This repository contains phase 1, phase 2, phase 3 (Supabase memory), phase 4 (multi-agent routing), phase 5 (course-material RAG), phase 6 (quiz generation and evaluation), phase 7 (CAG and structured database query), phase 8 (multi-course core), phase 9 (localization and UI polish), and phase 10 (prompt templates and LLM quality) of the Smart Study Planner Chatbot project.

The enhanced roadmap in `project..md` now upgrades Rafeeqak toward a stronger multi-course study assistant where each course has its own materials, study plan, quizzes, flashcards, weak topics, progress, and chat history.

- Phase 1: project setup and base structure
- Phase 2: Streamlit UI pages (chat, study plan, upload, quiz, dashboard)
- Phase 3: persistent memory with Supabase schema and repository integration
- Phase 4: input routing, supervisor orchestration, study planner agent, memory handoff, and route trace logging
- Phase 5: local text extraction, chunking, vector-store persistence, and grounded Course RAG answers
- Phase 6: topic/RAG-grounded quiz generation, flashcards, scoring feedback, and weak-topic detection
- Phase 7: semantic response cache plus structured progress, deadline, score, and weak-topic queries
- Phase 8: multi-course core upgrade with global course selector, course management, and course-scoped data
- Phase 9: full Arabic localization, RTL layout, and UI polish
- Phase 10: reusable prompt templates for RAG answers, course Q&A, lecture summaries, quiz generation, progress feedback, and study planning
- Phase 11+: planned planner upgrades, dashboard analytics, settings, and final demo hardening

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
- Course-scoped session state for chat history, chat summaries, plans, route traces, quiz attempts, and uploads
- Local file upload storage in `data/uploads`
- Supabase memory sync for:
  - student profile (per logged-in user)
  - courses and exams
  - generated study tasks
  - quiz scores and weak topics
  - per-course chat/session summaries
- Phase 4 agent flow:
  - Safety Agent screens unsafe routing attempts
  - Input Router Agent detects intent and language
  - Supervisor Agent selects and runs the specialist agent
  - Study Planner Agent creates plans and recommends next tasks
  - Reminder Agent creates course-scoped reminders from study tasks, quizzes, weak topics, missed tasks, and deadlines
  - Memory Agent syncs plans and quiz attempts when Supabase is configured
  - Route traces are saved in session state and shown in Chat/Dashboard
- Phase 5 RAG flow:
  - Upload Materials saves PDFs, DOCX, PPTX, Markdown, and text files
  - Course materials are extracted, chunked, embedded into local sparse vectors, and stored in `data/vector_store/course_materials.json`
  - Chat questions about lectures, notes, PDFs, or explanations route to the Course RAG Agent
  - RAG answers include concise source citations from the retrieved chunks
- Phase 6 quiz flow:
  - Quiz Generator Agent creates MCQs, true/false, short-answer, matching questions, and flashcards from selected-course chunks
  - Progress Evaluator Agent scores submitted answers, including partial credit for text and matching answers
  - Quiz page shows loading, generated, failed, and retry states for course-material quiz generation
  - Low quiz scores are saved as weak-topic signals through the Memory Agent when Supabase is configured
- Phase 7 CAG/database query flow:
  - repeated read-only chat questions are reused from `data/cache/semantic_cache.json` when the course context is unchanged
  - cache fingerprints include course, language, materials, quiz attempts, weak topics, progress, planning inputs, and all-course summaries
  - state-changing requests such as quiz generation, uploads, reminders, and plan-style actions skip cache lookup and storage
  - progress, deadline, score, and weak-topic questions route to the Database Query Agent
  - structured answers use the active local session first and Supabase memory snapshots when available
- Phase 8 multi-course flow:
  - global course selector plus course creation, rename, and delete controls
  - materials, plans, quizzes, weak topics, progress summaries, route traces, and chat history stay separated per course
  - deleting a course removes its local uploads and indexed RAG chunks
- Phase 9 localization flow:
  - English/Arabic language toggle with session and profile persistence
  - Arabic UI strings and assistant responses
  - RTL layout and Arabic-friendly typography when Arabic is selected
- Phase 10 prompt flow:
  - prompt templates live in `src/prompts/templates`
  - RAG answers, quiz generation, and study planning render prompts through a shared prompt registry
  - templates also cover course Q&A, lecture summaries, and progress feedback for planned agent upgrades

## Next Phases

Upcoming phases should focus on:

- Better quiz types, partial text scoring, and stronger personalized feedback
- Per-course dashboard analytics and settings page

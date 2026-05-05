# Smart Study Planner

This repository contains phase 1, phase 2, phase 3 (Supabase memory), and phase 4 (multi-agent routing) of the Smart Study Planner Chatbot project:

- Phase 1: project setup and base structure
- Phase 2: Streamlit UI pages (chat, study plan, upload, quiz, dashboard)
- Phase 3: persistent memory with Supabase schema and repository integration
- Phase 4: input routing, supervisor orchestration, study planner agent, memory handoff, and route trace logging

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

## Next Phases

Upcoming phases can build on this scaffold by adding:

- RAG indexing and retrieval
- Quiz generation and automated evaluation

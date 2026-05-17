# Project Architecture and Team Split Guide

This file is a practical architecture map for dividing the project across team members.
It is based on the current codebase, not only on documentation claims.

## Project Summary

The project is a Streamlit-based smart study planner / AI study assistant with:
- authentication and session persistence
- multi-course state management
- chat with supervisor-based agent routing
- course-material upload and local RAG
- quiz generation and evaluation
- adaptive study planning
- reminders and dashboard analytics
- optional Supabase-backed cloud memory
- English/Arabic localization with RTL support

## Top-Level Structure

- `app.py`  
  Main Streamlit entrypoint. Handles app startup, auth gating, language selector, course selector, and page routing.

- `src/agents/`  
  Core AI/system logic. Routing, planning, RAG, quiz generation, evaluation, reminders, memory sync.

- `src/ui/`  
  Streamlit pages and visual flows.

- `src/tools/`  
  Shared state, cache, quiz history, planner-task utilities, localization helpers, LLM client.

- `src/retrieval/`  
  Course material indexing and search.

- `src/memory/`  
  Supabase repository and DB client setup.

- `src/auth/`  
  Login/session services and browser token persistence.

- `src/prompts/`  
  Prompt registry and reusable prompt templates.

- `tests/`  
  Coverage for routing, RAG, quiz, cache, multi-course state, localization, dashboard, auth, and app startup.

- `docs/`  
  Supabase schema and setup notes.

## Architecture Map

### 1. App Shell and Navigation

Main files:
- `app.py`
- `src/ui/theme.py`
- `src/localization.py`

Responsibilities:
- initialize Streamlit state
- bootstrap authentication
- load environment and Gemini settings
- render global navigation
- manage selected page and selected course
- show top-level reminder notifications

Depends on:
- `src/tools/state.py`
- `src/auth/*`
- all page handlers in `src/ui/*`

Good owner profile:
- teammate responsible for app integration, UX shell, and demo flow

### 2. Authentication and Session Layer

Main files:
- `src/auth/service.py`
- `src/auth/session_persistence.py`
- `src/ui/login_page.py`
- `src/ui/signup_page.py`
- `src/ui/account_page.py`

Responsibilities:
- Supabase auth sign-up/sign-in/sign-out
- local demo-mode login fallback
- browser cookie persistence for auth tokens
- restore authenticated sessions after refresh

Depends on:
- `src/memory/supabase_client.py`
- `src/tools/state.py`

Notes:
- works in both real Supabase mode and local demo mode
- good area for one teammate if you want a clean “auth + account” ownership boundary

### 3. Shared State and Multi-Course Core

Main files:
- `src/tools/state.py`
- `src/tools/study_plan_tasks.py`
- `src/tools/quiz_history.py`

Responsibilities:
- course-scoped session data
- active course switching
- local workspace persistence per user/email
- user settings
- task completion tracking
- quiz history and duplicate prevention
- aggregated all-course summaries

Stored per course:
- chat history
- chat summaries
- study plans
- active plan
- quiz attempts
- active quiz
- last quiz feedback
- reminders
- uploads
- generated questions

Depends on:
- almost every UI page and agent

Notes:
- this is one of the most central files in the whole project
- if one person owns this area, they must coordinate with everyone else

### 4. Agent Orchestration

Main files:
- `src/agents/supervisor.py`
- `src/agents/input_router.py`
- `src/agents/safety_agent.py`

Responsibilities:
- route user message to the correct specialist agent
- detect language and intent
- run a safety check before routing
- apply semantic cache for read-only repeated queries
- enforce course-scope requirements
- produce a route trace for each handled request

Specialist agents used by the supervisor:
- `study_planner.py`
- `course_rag.py`
- `quiz_generator.py`
- `database_query.py`
- `reminder_agent.py`
- `memory_agent.py`

Notes:
- this is the best ownership area for the teammate presenting “AI system architecture”
- current routing is rule-based, not model-based

### 5. Study Planner and Reminders

Main files:
- `src/agents/study_planner.py`
- `src/agents/reminder_agent.py`
- `src/ui/study_plan_page.py`
- `src/tools/planner_localization.py`
- `src/tools/study_plan_tasks.py`

Responsibilities:
- generate study plans from exam date, hours, difficulty, lecture count, and finish period
- prioritize weak topics
- adapt to overdue work and recovery needs
- recommend next task
- create reminders from plan tasks, deadlines, weak topics, and missed tasks
- show editable plan timeline in the UI

Input signals used:
- weak topics from previous quizzes
- overdue tasks from current plan
- selected language
- user study defaults

Notes:
- this is a strong standalone workstream
- good for one teammate focused on planner logic and demo personalization

### 6. Course Materials and RAG

Main files:
- `src/retrieval/course_materials.py`
- `src/agents/course_rag.py`
- `src/ui/upload_page.py`
- `src/ui/chat_page.py`

Responsibilities:
- upload and store files under `data/uploads`
- extract text from `pdf`, `docx`, `pptx`, `txt`, `md`
- chunk and index material into local sparse vectors
- retrieve relevant chunks for questions
- answer with citations from uploaded material

Notes:
- this is the main retrieval/augmentation feature
- retrieval is local and lexical, not embedding-model based
- good ownership area for one teammate focused on AI retrieval and document ingestion

### 7. Quiz Generation and Evaluation

Main files:
- `src/agents/quiz_generator.py`
- `src/agents/progress_evaluator.py`
- `src/ui/quiz_page.py`
- `src/tools/quiz_history.py`

Responsibilities:
- generate quizzes and flashcards from topic or retrieved course chunks
- support `mcq`, `true_false`, `short_answer`, and `matching`
- evaluate answers
- assign partial credit
- detect weak topics from low scores
- store attempts and feed weak-topic memory back into planning

Notes:
- this is another clean ownership boundary
- quiz and planner collaborate through weak-topic and completion signals

### 8. Dashboard, Analytics, and Settings

Main files:
- `src/ui/dashboard_page.py`
- `src/ui/settings_page.py`

Responsibilities:
- display all-course summaries
- show active-plan progress
- show quiz trends and weak topics
- show reminders and due alerts
- save user defaults for study hours, difficulty, question types, reminder preferences, and language

Depends on:
- `src/tools/state.py`
- `src/agents/reminder_agent.py`
- `src/agents/memory_agent.py`

Notes:
- good area for a teammate focused on presentation quality and cross-feature integration

### 9. Memory and Cloud Persistence

Main files:
- `src/agents/memory_agent.py`
- `src/memory/repository.py`
- `src/memory/supabase_client.py`
- `docs/supabase_schema.sql`

Responsibilities:
- create/load student profiles
- sync study plans
- sync quiz scores and weak topics
- sync chat summaries
- sync reminders
- fetch student memory snapshot
- persist settings and preferred language

Cloud tables:
- `student_profiles`
- `courses`
- `exams`
- `study_tasks`
- `quiz_scores`
- `weak_topics`
- `chat_session_summaries`
- `reminders`

Notes:
- optional in runtime, but important for project depth and architecture discussion
- best ownership area for the teammate handling backend/data persistence

### 10. Prompt and LLM Layer

Main files:
- `src/tools/llm_client.py`
- `src/prompts/registry.py`
- `src/prompts/templates/*`

Actively used templates:
- `rag_answer`
- `quiz_generation`
- `study_planning`

Present but not currently wired into active flows:
- `course_question`
- `lecture_summary`
- `progress_feedback`

Notes:
- useful ownership area if one teammate wants to focus on prompt engineering and LLM behavior

## Suggested Team Split

If you are 4 people:

### Person 1: App Shell, Auth, and Global Integration

Own:
- `app.py`
- `src/auth/*`
- `src/ui/login_page.py`
- `src/ui/signup_page.py`
- `src/ui/account_page.py`
- `src/ui/theme.py`

Main talking points:
- authentication
- session restore
- navigation
- page gating
- demo-mode fallback

### Person 2: Planner, Reminders, and Dashboard

Own:
- `src/agents/study_planner.py`
- `src/agents/reminder_agent.py`
- `src/ui/study_plan_page.py`
- `src/ui/dashboard_page.py`
- `src/tools/study_plan_tasks.py`
- `src/tools/planner_localization.py`

Main talking points:
- adaptive planning
- weak-topic prioritization
- delayed-task recovery
- reminder generation
- progress visualization

### Person 3: RAG, Uploads, and Chat

Own:
- `src/retrieval/course_materials.py`
- `src/agents/course_rag.py`
- `src/ui/upload_page.py`
- `src/ui/chat_page.py`
- `src/agents/input_router.py`
- `src/agents/supervisor.py`

Main talking points:
- document ingestion
- chunking and retrieval
- grounded answers with citations
- intent routing
- AI system flow

### Person 4: Quiz, Memory, and Settings

Own:
- `src/agents/quiz_generator.py`
- `src/agents/progress_evaluator.py`
- `src/ui/quiz_page.py`
- `src/agents/memory_agent.py`
- `src/memory/*`
- `src/ui/settings_page.py`
- `src/tools/quiz_history.py`

Main talking points:
- quiz generation
- scoring and weak-topic extraction
- memory persistence
- Supabase integration
- personalization settings

## Suggested Team Split

If you are 5 people:

### Person 1
App shell and auth

### Person 2
Shared state and multi-course architecture

### Person 3
Planner, reminders, dashboard

### Person 4
RAG, uploads, and chat routing

### Person 5
Quiz, evaluation, memory, and settings

## Critical Integration Dependencies

These are the most important cross-team dependencies:

- `src/tools/state.py` touches nearly every feature.
- `src/agents/supervisor.py` is the central agent integration point.
- `src/ui/chat_page.py` connects supervisor results back into course state.
- `src/ui/quiz_page.py` updates weak topics and plan completion.
- `src/ui/study_plan_page.py` depends on quiz/progress signals.
- `src/memory/repository.py` affects auth-backed persistence and dashboard snapshots.

If the team splits work, agree early on:
- state keys and payload shapes
- course-scoping rules
- what counts as the active course
- what data is saved locally vs synced to Supabase
- what features need LLM config vs offline fallback

## Current Strengths

- clear modular architecture
- strong feature integration
- multi-course separation
- full Streamlit UI
- optional cloud persistence
- English/Arabic support
- real test coverage

## Current Weak Spots

- some routing and safety behavior is heuristic and hardcoded
- route trace exists in backend but is not shown in UI
- prompt-injection defense is very lightweight
- retrieval uses sparse lexical vectors, not embedding-based search
- some prompt templates are present but not connected to live features

## Demo-Critical Files

If the team has little time, these are the highest-value files to understand first:

- `app.py`
- `src/tools/state.py`
- `src/agents/supervisor.py`
- `src/ui/chat_page.py`
- `src/ui/study_plan_page.py`
- `src/ui/upload_page.py`
- `src/ui/quiz_page.py`
- `src/ui/dashboard_page.py`
- `src/agents/course_rag.py`
- `src/agents/study_planner.py`
- `src/agents/quiz_generator.py`
- `src/agents/memory_agent.py`

## Test Files to Use During Handover

- `tests/test_phase4_agents.py`  
  routing, supervisor, planner, reminders

- `tests/test_phase5_rag.py`  
  indexing, search, citations, RAG routing

- `tests/test_phase6_quiz.py`  
  quiz generation, evaluation, quiz-page helpers

- `tests/test_phase7_cache_query.py`  
  cache and structured progress queries

- `tests/test_phase8_multicourse.py`  
  course separation and workspace persistence

- `tests/test_phase9_localization.py`  
  Arabic/RTL support

- `tests/test_phase12_dashboard_settings_reminders.py`  
  settings, reminders, dashboard logic

## Practical Recommendation

Before dividing work, each teammate should read:
- `app.py`
- `src/tools/state.py`
- the files in their assigned area
- the matching test file for that area

That is enough to understand both:
- how their component works
- how it connects to the rest of the project

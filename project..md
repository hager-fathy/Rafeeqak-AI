# Rafeeqak Smart Study Planner - Project Brief And Enhanced Roadmap

> **One-sentence pitch:**
> Rafeeqak is a multilingual, multi-course agentic study assistant that helps students organize courses, upload materials, generate personalized plans, practice with quizzes, track weak topics, and prepare smarter for exams.

- **Course context:** Deep Generative Models - Fourth Year Course Project
- **Target domain:** Education - study planning, exam preparation, course assistant, and personalized learning support
- **Enhanced direction:** Upgrade from a mostly single-course assistant into a stronger multi-course study platform.

---

## 1. Problem We Are Solving

Students usually study more than one course at a time. Their lectures, assignments, exams, quiz results, weak topics, and study plans are often mixed together across notebooks, chats, files, and apps.

The current app already supports planning, uploads, RAG, quizzes, memory, and progress tracking, but most of the experience behaves like a single active course. The enhanced version should separate all learning data by course so a student can work on Machine Learning, Databases, Security, and other subjects without mixing materials or progress.

Rafeeqak should become a study hub where each course has its own:

- uploaded materials,
- RAG index,
- chat history,
- study plan,
- quiz attempts,
- weak topics,
- progress dashboard,
- deadlines.

---

## 2. Enhanced Product Goals

1. **Multi-course support** - Every major feature should be scoped to the selected course.
2. **Course selector** - The student chooses the active course before chat, uploads, quizzes, dashboard, or planning.
3. **Course-specific RAG** - Uploaded materials are indexed by course and retrieved only from the selected course.
4. **Course-specific chat memory** - Chat history is separated per course.
5. **Personalized planning** - Plans consider course difficulty, deadlines, daily hours, progress, and weak topics.
6. **Better quizzes** - Quizzes use selected-course materials and support difficulty levels plus multiple question types.
7. **Better evaluation** - Evaluation supports partial scoring, weak-topic tracking, and personalized recommendations.
8. **Polished UI** - Improve spacing, colors, labels, buttons, and helpful empty states.
9. **Full Arabic localization** - Translate UI labels, alerts, errors, and assistant responses; support RTL layout.
10. **Language toggle** - The student can switch Arabic/English and the preference is saved.
11. **Friendly errors** - Replace technical errors with clear student-facing messages.
12. **Reusable prompt templates** - Store prompts in reusable templates instead of hardcoded strings.
13. **Dashboard by course** - Show progress, scores, weak topics, uploads, and deadlines per course.
14. **Settings page** - Allow editing name, language, daily study hours, quiz preferences, difficulty, and study preferences.

---

## 3. Typical Enhanced Session

1. Student logs in.
2. Student creates or selects **Machine Learning** from the course selector.
3. Student uploads ML lecture PDFs. The app indexes them under Machine Learning only.
4. Student generates a Machine Learning study plan using exam date, weak topics, and daily study hours.
5. Student asks in Chat: "Explain backpropagation from my notes."
6. RAG searches only Machine Learning materials and answers with citations.
7. Student switches to **Databases**.
8. Chat history, materials, quizzes, weak topics, and dashboard now show Databases data only.
9. Student takes a quiz and weak topics are saved for Databases only.
10. Dashboard shows course-by-course progress and upcoming deadlines.

---

## 4. Architecture Overview

```text
Streamlit UI
  |
  +-- Course Selector
  |     - active_course_id
  |     - active_course_name
  |
  +-- Language Toggle
  |     - English / Arabic
  |     - RTL support for Arabic
  |
  v
Supervisor Agent
  |
  +-- Safety Agent
  +-- Input Router Agent
  +-- Study Planner Agent
  +-- Course RAG Agent
  +-- Quiz Generator Agent
  +-- Progress Evaluator Agent
  +-- Database Query Agent
  +-- Memory Agent
  |
  v
Course-Scoped State And Storage
  |
  +-- course materials
  +-- vector index
  +-- study plans
  +-- quiz attempts
  +-- weak topics
  +-- chat history
  +-- progress snapshots
```

---

## 5. Course-Scoped Data Model

Every student-facing feature should include a course identifier.

| Data Area | Required Course Scope |
|---|---|
| Uploaded files | `course_id`, `file_name`, `stored_path`, `uploaded_at` |
| Vector chunks | `course_id`, `file_name`, `page_or_chunk`, `text`, `embedding` |
| Study plans | `course_id`, `exam_date`, `difficulty`, `daily_hours`, `tasks` |
| Study tasks | `course_id`, `topic`, `date`, `completed`, `delayed` |
| Quiz attempts | `course_id`, `topic`, `difficulty`, `score`, `question_types` |
| Weak topics | `course_id`, `topic`, `source`, `confidence`, `last_seen` |
| Chat history | `course_id`, `messages`, `created_at` |
| Settings | user-level defaults plus optional course-level preferences |

---

## 6. Mapping To Course Requirements

### 6.1 Multi-Agent System

| # | Agent | Responsibility |
|---|---|---|
| 1 | Input Router Agent | Detects intent and language. |
| 2 | Supervisor Agent | Routes each request to the correct specialist agent. |
| 3 | Study Planner Agent | Creates course-specific study plans. |
| 4 | Course RAG Agent | Retrieves selected-course material and answers with citations. |
| 5 | Quiz Generator Agent | Generates course-specific quizzes from topics and materials. |
| 6 | Progress Evaluator Agent | Grades answers, including partial scoring for text answers. |
| 7 | Memory Agent | Stores user profile, course memory, progress, and weak topics. |
| 8 | Safety Agent | Detects prompt injection and filters unsafe or irrelevant requests. |
| 9 | Database Query Agent | Answers structured progress, deadline, score, and weak-topic questions. |
| 10 | Response Agent | Produces localized student-friendly responses. |

### 6.2 Advanced Memory System

| Memory Type | Contents |
|---|---|
| User profile memory | Name, language, daily hours, study style, quiz preferences. |
| Course memory | Course name, difficulty, exam date, deadline, syllabus topics. |
| Material memory | Uploaded files and indexed chunks per course. |
| Progress memory | Completed tasks, delayed tasks, quiz scores, average score. |
| Weakness memory | Weak topics by course from quizzes and chat. |
| Episodic memory | Per-course chat summaries and important past interactions. |
| Preference memory | Preferred difficulty, question types, and study methods. |

### 6.3 Tool Integration

| Tool | Enhanced Behavior |
|---|---|
| RAG | Retrieve only from selected-course materials with course/file/page citations. |
| CAG | Cache repeated questions using course-aware context fingerprints. |
| Database Query | Query course-specific progress, deadlines, scores, and weak topics. |
| LLM | Use Gemini wrapper for RAG answers, study plans, and quiz generation. |

---

## 7. User Interface Requirements

### 7.1 Shared UI

- Add a global course selector visible on authenticated pages.
- Show a helpful empty state when no course exists.
- Prevent chat/upload/quiz/plan actions until a course is selected.
- Add a language toggle for English and Arabic.
- Apply RTL layout when Arabic is selected.
- Use friendly labels and clear button text.
- Improve spacing, colors, and visual grouping.
- Replace blank sections with helpful guidance.

### 7.2 Pages

| Page | Enhanced Requirements |
|---|---|
| Chat | Course-specific chat history, selected-course RAG, localized assistant responses. |
| Study Plan | Course difficulty, exam deadlines, and progress-aware planning. |
| Upload Materials | Save and index files under selected course; allow delete per course. |
| Quiz | Course-based quizzes, difficulty selector, MCQ, true/false, short answer, matching. |
| Dashboard | Course cards, completed tasks, upcoming tasks, scores, weak topics, uploads, and deadlines. |
| Settings | Name, language, daily hours, difficulty, quiz preferences, study preferences. |
| Account | Logout and account status. |

---

## 8. Prompt Template Requirements

Hardcoded prompt strings should be replaced with reusable templates.

Recommended location:

```text
src/prompts/
```

Required templates:

| Template | Variables |
|---|---|
| Course question answering | `course_name`, `question`, `language` |
| RAG-based answering | `course_name`, `question`, `context`, `citations`, `language` |
| Lecture summarization | `course_name`, `lecture_title`, `lecture_text`, `language` |
| Quiz generation | `course_name`, `topic`, `difficulty`, `number_of_questions`, `question_types`, `context`, `language` |
| Progress feedback | `course_name`, `score`, `weak_topics`, `recommendations`, `language` |
| Study planning | `course_name`, `difficulty`, `exam_deadline`, `daily_hours`, `progress`, `weak_topics`, `language` |

Example template shape:

```python
RAG_ANSWER_PROMPT = """
You are Rafeeqak, a careful study assistant.
Course: {course_name}
Language: {language}

Answer the question using only the course context.

Question:
{question}

Context:
{context}

Return a clear answer and cite sources as:
Course Name - File Name - Page/Chunk.
"""
```

---

## 9. Enhanced Implementation Plan

**Current status checked:** 2026-05-15
**Latest verification:** `.venv\Scripts\python.exe -m pytest` passes: 38 passed, 2 warnings.

Legend:

- `[x]` Complete
- `[ ]` Pending
- `[~]` Partial

### Phase 1 - Project Setup

- [x] Create Python project.
- [x] Add Streamlit app structure.
- [x] Add dependencies and environment variables.
- [x] Add tests and project documentation.

### Phase 2 - Basic UI

- [x] Build Streamlit navigation.
- [x] Add login, sign-up, account pages.
- [x] Add chat, study plan, upload, quiz, and dashboard pages.
- [x] Polish page layout, spacing, colors, labels, buttons, and empty states.

### Phase 3 - Database And Memory

- [x] Add Supabase schema and repository.
- [x] Store student profile, courses, exams, tasks, quiz scores, and weak topics.
- [x] Sync generated study plans and quiz attempts when Supabase is configured.
- [x] Upgrade memory schema and local state for full course-scoped separation.

### Phase 4 - Multi-Agent Flow

- [x] Implement Input Router, Supervisor, Study Planner, Memory, Safety, RAG, Quiz, Evaluator, and Database Query agents.
- [x] Add route trace logging.
- [x] Wire chat requests through safety, routing, specialist agents, and response generation.
- [x] Add course-aware routing and course-required validation.

### Phase 5 - RAG System

- [x] Upload and index PDFs, DOCX, PPTX, Markdown, and text files.
- [x] Extract text, chunk, embed, and persist local vector store.
- [x] Implement Course RAG Agent.
- [x] Add LLM-based RAG answer generation with fallback.
- [x] Index uploaded materials by `course_id`.
- [x] Search only inside selected-course materials.
- [x] Improve chunking, ranking, and citation format.
- [x] Citations must include course name, file name, and page/chunk reference.

### Phase 6 - Quiz And Evaluation

- [x] Implement Quiz Generator Agent.
- [x] Implement Progress Evaluator Agent.
- [x] Store quiz scores and weak topics.
- [x] Add LLM-based quiz generation with fallback.
- [x] Allow custom number of questions.
- [x] Scope quizzes, attempts, and weak topics by course.
- [x] Add difficulty selector.
- [x] Support multiple question types: MCQ, true/false, short answer, matching.
- [x] Reduce repeated questions per course by tracking previously generated questions.
- [x] Add partial scoring for text answers.
- [x] Add more detailed feedback and personalized recommendations.

### Phase 7 - CAG And Structured Database Query

- [x] Add semantic cache for repeated questions.
- [x] Add structured query handler for progress, deadlines, scores, and weak topics.
- [x] Make cache context fingerprints course-aware.
- [x] Make structured queries return selected-course and all-course summaries.

### Phase 8 - Multi-Course Core Upgrade

- [~] Add course creation and course management UI.
- [x] Add global active-course selector.
- [x] Save `active_course_id` and `active_course_name` in session state.
- [x] Require course selection before chat, upload, quiz, dashboard, or study plan actions.
- [~] Separate materials, plans, quizzes, weak topics, progress, and chat by course.
- [x] Add friendly no-course empty states.

### Phase 9 - Localization And UI Polish

- [~] Detect Arabic input in router.
- [ ] Add language toggle: English / Arabic.
- [ ] Save selected language in session state and user profile.
- [ ] Translate UI labels, alerts, buttons, errors, empty states, and assistant responses.
- [ ] Add RTL layout when Arabic is selected.
- [ ] Add localization helper files or dictionaries.
- [ ] Improve visual polish across all pages.

### Phase 10 - Prompt Templates And LLM Quality

- [x] Add shared Gemini LLM client with offline fallback.
- [ ] Move prompts into reusable prompt template files.
- [ ] Add templates for course Q&A, RAG answer, lecture summary, quiz generation, progress feedback, and study planning.
- [ ] Add variables for course name, question, context, lecture title, lecture text, topic, difficulty, number of questions, score, weak topics, and recommendations.

### Phase 11 - Study Planner Upgrade

- [x] Replace fixed-looking plan defaults with more adaptive task generation.
- [x] Add LLM-based plan generation with fallback.
- [ ] Make planning work across multiple courses.
- [ ] Add course difficulty.
- [ ] Consider exam deadlines, daily available time, current progress, and weak topics.
- [ ] Add delayed-task detection and recovery recommendations.

### Phase 12 - Dashboard And Settings

- [ ] Dashboard shows progress per course.
- [ ] Dashboard includes completed tasks, upcoming tasks, quiz scores, average score, weak topics, uploads, and deadlines.
- [ ] Add settings page for name, language, daily hours, quiz preferences, difficulty, and study preferences.

### Phase 13 - Testing And Demo

- [x] Automated tests cover app startup, page rendering, auth, memory, routing, RAG, quiz, cache, and LLM provider selection.
- [ ] Add tests for multi-course state separation.
- [ ] Add tests for course selector gating.
- [ ] Add tests for Arabic localization and RTL.
- [ ] Add tests for course-scoped RAG retrieval.
- [ ] Add tests for quiz question types and partial scoring.
- [ ] Prepare final demo script.
- [ ] Run end-to-end manual demo validation.

---

## 10. Current Completed Vs Pending Summary

### Completed Core

| Area | Status |
|---|---|
| Basic Streamlit app | Complete |
| Authentication pages | Complete |
| Supabase memory scaffold | Complete |
| Agent orchestration | Complete |
| Local upload and RAG index | Complete |
| RAG answer generation | Complete with LLM fallback |
| Quiz generation | Complete with LLM fallback, difficulty, and multiple question types |
| Progress evaluation | Complete with partial scoring |
| Semantic cache | Complete |
| Structured progress queries | Complete |
| Gemini LLM wrapper | Complete |
| Upload deletion | Complete |
| Custom quiz count | Complete |
| Adaptive study plan generation | Partial/Improved |

### Main Pending Upgrade

| Area | Status |
|---|---|
| Full multi-course separation | Partial through Phase 5 |
| Global course selector | Complete |
| Course-scoped chat history | Complete |
| Course-scoped RAG retrieval | Complete |
| Full Arabic localization and RTL | Pending |
| Reusable prompt templates | Pending |
| Multiple quiz question types | Complete |
| Partial scoring for text answers | Complete |
| Settings page | Pending |
| Per-course dashboard summaries | Pending |

---

## 11. Tech Stack

| Component | Technology |
|---|---|
| Language | Python |
| UI | Streamlit |
| LLM Provider | Gemini via `google-genai` |
| Agent Orchestration | Custom Python agents and supervisor |
| Database | Supabase, with local session fallback |
| Retrieval | Local text extraction, chunking, sparse-vector search |
| PDF Parsing | PyMuPDF |
| DOCX Parsing | python-docx |
| PPTX Parsing | python-pptx |
| Testing | pytest |

Note: `langchain` and `langgraph` are installed but not currently used in the implementation.

---

## 12. Enhanced Demo Scenario

1. Student logs in.
2. Student creates two courses: **Machine Learning** and **Databases**.
3. Student selects Machine Learning.
4. Student uploads ML lecture files.
5. Student generates an ML study plan with exam deadline, difficulty, daily hours, and weak topics.
6. Student asks an ML question in Chat and receives course-specific citations.
7. Student generates a medium-difficulty quiz from ML materials.
8. Student answers questions, gets detailed feedback, and weak topics update under ML only.
9. Student switches to Databases.
10. Chat history and materials are empty or Databases-specific, not mixed with ML.
11. Student uploads Databases notes and generates a separate Databases quiz.
12. Dashboard shows progress for both courses.
13. Student switches language to Arabic and the UI changes to Arabic RTL.

---

## 13. Final Summary

Rafeeqak already has a strong single-course demo core: authentication, planning, uploads, RAG, quizzes, weak-topic tracking, semantic cache, structured queries, and LLM integration.

The next major goal is to turn this into a true multi-course study assistant. The most important upgrade is course scoping: every material, chat message, quiz, weak topic, progress metric, and study plan must belong to a selected course. After that, localization, prompt templates, better quiz/evaluation logic, dashboard summaries, and settings will make the project feel complete and polished.

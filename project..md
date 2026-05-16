# Rafeeqak Smart Study Planner - Project Brief And Enhanced Roadmap

## One-sentence pitch

Rafeeqak is a multilingual, multi-course agentic study assistant that helps students organize courses, upload materials, generate personalized study plans, practice with quizzes, track weak topics, receive useful session summaries, and prepare smarter for exams.

**Course context:** Deep Generative Models - Fourth Year Course Project

**Target domain:** Education - study planning, exam preparation, course assistance, and personalized learning support.

**Enhanced direction:** Upgrade from a mostly single-course assistant into a stronger multi-course study platform with course-scoped RAG, CAG, memory, planning, dashboard summaries, and reminders.

---

## 1. Problem We Are Solving

Students usually study more than one course at a time. Their lectures, assignments, exams, quiz results, weak topics, study plans, and chat notes are often mixed together across notebooks, chats, files, and apps.

The current app already supports planning, uploads, RAG, quizzes, memory, semantic cache, and progress tracking, but the experience must remain fully course-scoped. The enhanced version should separate all learning data by course so a student can work on Machine Learning, Databases, Security, and other subjects without mixing materials or progress.

Rafeeqak should become a study hub where each course has its own:

- uploaded materials
- RAG index
- chat history
- chat/session summaries
- study plan
- quiz attempts
- weak topics
- dashboard summaries
- deadlines
- reminders

---

## 2. Enhanced Product Goals

- **Multi-course support:** Every major feature should be scoped to the selected course.
- **Course selector:** The student chooses the active course before chat, uploads, quizzes, dashboard, or planning.
- **Course-specific RAG:** Uploaded materials are indexed by course and retrieved only from the selected course.
- **Course-specific chat memory:** Chat history and summaries are separated per course.
- **Better chat/session summaries:** Summaries should highlight main topics discussed, student weaknesses, and suggested next steps.
- **Personalized planning:** Plans should use the number of lectures, target finish period, daily available study time, course difficulty, deadlines, progress, and weak topics.
- **Weak-topic priority:** Study plans should start with the topics where the student is weakest, then continue with remaining topics in a logical order.
- **Better quizzes:** Quizzes use selected-course materials and support difficulty levels plus multiple question types.
- **Quiz generation status:** The UI should clearly show whether a quiz is loading, generated, or failed, with retry/error feedback.
- **Better evaluation:** Evaluation supports partial scoring, weak-topic tracking, and personalized recommendations.
- **Polished UI:** Improve spacing, colors, labels, buttons, and helpful empty states.
- **Full Arabic localization:** Translate UI labels, alerts, errors, and assistant responses; support RTL layout.
- **Language toggle:** The student can switch Arabic/English and the preference is saved.
- **Friendly errors:** Replace technical errors with clear student-facing messages.
- **Reusable prompt templates:** Store prompts in reusable templates instead of hardcoded strings.
- **Dashboard by course:** Show dashboard summaries for progress, scores, weak topics, uploads, and deadlines per course.
- **Settings page:** Allow editing name, language, daily study hours, quiz preferences, difficulty, and study preferences.
- **Notifications/reminders:** Notify students about upcoming lectures, revision sessions, quizzes, missed tasks, and deadlines.

---

## 3. Typical Enhanced Session

- Student logs in.
- Student creates or selects Machine Learning from the course selector.
- Student uploads ML lecture PDFs. The app indexes them under Machine Learning only.
- Student asks for a study plan. Rafeeqak asks for missing planning inputs, such as number of lectures, target finish period, and daily available study time.
- Student generates a Machine Learning study plan using exam date, weak topics, daily study hours, and lecture count.
- The plan starts with weak topics first, then continues with remaining topics logically.
- Student asks in Chat: "Explain backpropagation from my notes."
- RAG searches only Machine Learning materials and answers with citations.
- The chat/session summary records the main topic, weakness signals, and suggested next steps.
- Student generates a medium-difficulty quiz from ML materials.
- The quiz page shows a clear loading state, success state, or failure message with retry.
- Student switches to Databases.
- Chat history, summaries, materials, quizzes, weak topics, and dashboard summaries now show Databases data only.
- Student takes a quiz and weak topics are saved for Databases only.
- Dashboard shows course-by-course summaries and upcoming deadlines.
- Reminder messages help the student stay on track.

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
  +-- Language Detection
  +-- Course Selection Check
  +-- Input Router Agent
  +-- CAG / Semantic Cache
  +-- Study Planner Agent
  +-- Course RAG Agent
  +-- Quiz Generator Agent
  +-- Progress Evaluator Agent
  +-- Database Query Agent
  +-- Memory Agent
  +-- Response Agent
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
  +-- chat/session summaries
  +-- progress snapshots
  +-- reminders
  +-- semantic cache
```

### Correct request flow

```text
User Question
↓
Safety Check
↓
Language Detection
↓
Course Selection Check
↓
Input Routing
↓
CAG Cache Check
↓
If course-material question → Course RAG Agent
If quiz request → Quiz Generator Agent + optional RAG
If progress question → Database Query Agent
If study plan request → Study Planner Agent
↓
Generate Final Answer
↓
Save Answer in CAG Cache when safe
↓
Show Response
```

CAG should not return cached responses for actions that create or update state, such as generating a new quiz, creating a new plan, submitting answers, or changing preferences.

---

## 5. Course-Scoped Data Model

Every student-facing feature should include a course identifier.

| Data Area | Required Course Scope |
|---|---|
| Uploaded files | course_id, file_name, stored_path, uploaded_at |
| Vector chunks | course_id, file_name, page_or_chunk, text, embedding |
| Study plans | course_id, exam_date, difficulty, daily_hours, lecture_count, finish_period, tasks |
| Study tasks | course_id, topic, date, completed, delayed, priority |
| Quiz attempts | course_id, topic, difficulty, score, question_types, status |
| Weak topics | course_id, topic, source, confidence, last_seen |
| Chat history | course_id, messages, created_at |
| Chat/session summaries | course_id, main_topics, weaknesses, next_steps, created_at |
| Reminders | course_id, reminder_type, title, due_at, status |
| Settings | user-level defaults plus optional course-level preferences |
| Semantic cache | active_course_id, language, fingerprint, question, response |

---

## 6. Mapping To Course Requirements

### 6.1 Multi-Agent System

| # | Agent | Responsibility |
|---|---|---|
| 1 | Input Router Agent | Detects intent and language. |
| 2 | Supervisor Agent | Routes each request to the correct specialist agent. |
| 3 | Study Planner Agent | Creates course-specific study plans and asks for missing planning inputs. |
| 4 | Course RAG Agent | Retrieves selected-course material and answers with citations. |
| 5 | Quiz Generator Agent | Generates course-specific quizzes from topics and materials. |
| 6 | Progress Evaluator Agent | Grades answers, including partial scoring for text answers. |
| 7 | Memory Agent | Stores user profile, course memory, progress, weak topics, and chat/session summaries. |
| 8 | Safety Agent | Detects prompt injection and filters unsafe or irrelevant requests. |
| 9 | Database Query Agent | Answers structured progress, deadline, score, and weak-topic questions. |
| 10 | Response Agent | Produces localized student-friendly responses. |
| 11 | Reminder Agent | Creates reminder records for lectures, revision, quizzes, missed tasks, and deadlines. |

### 6.2 Advanced Memory System

| Memory Type | Contents |
|---|---|
| User profile memory | Name, language, daily hours, study style, quiz preferences. |
| Course memory | Course name, difficulty, exam date, deadline, syllabus topics. |
| Material memory | Uploaded files and indexed chunks per course. |
| Progress memory | Completed tasks, delayed tasks, quiz scores, average score. |
| Weakness memory | Weak topics by course from quizzes, evaluations, and chat signals. |
| Episodic memory | Per-course chat summaries, main topics discussed, and important past interactions. |
| Preference memory | Preferred difficulty, question types, daily time, and study methods. |
| Reminder memory | Upcoming reminders, missed tasks, revision sessions, and quiz reminders. |

### 6.3 Tool Integration

| Tool | Enhanced Behavior |
|---|---|
| RAG | Retrieve only from selected-course materials with course/file/page citations. |
| CAG | Cache repeated questions using course-aware context fingerprints. |
| Database Query | Query course-specific progress, deadlines, scores, weak topics, and reminders. |
| LLM | Use Gemini wrapper for RAG answers, study plans, summaries, and quiz generation. |

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
- Show clear loading, success, failure, and retry states for quiz generation.
- Show reminder alerts for upcoming lectures, revision sessions, quizzes, missed tasks, and deadlines.

### 7.2 Pages

| Page | Enhanced Requirements |
|---|---|
| Chat | Course-specific chat history, selected-course RAG, localized assistant responses, and useful chat/session summaries. |
| Study Plan | Ask for number of lectures, target finish period, daily available time, course difficulty, exam deadlines, and weak-topic priorities. |
| Upload Materials | Save and index files under selected course; allow delete per course. |
| Quiz | Course-based quizzes, loading/success/failure states, retry option, difficulty selector, MCQ, true/false, short answer, matching. |
| Dashboard | Course cards, completed tasks, upcoming tasks, scores, weak topics, uploads, deadlines, and reminder summaries. |
| Settings | Name, language, daily hours, difficulty, quiz preferences, study preferences, and reminder preferences. |
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
| Course question answering | course_name, question, language |
| RAG-based answering | course_name, question, context, citations, language |
| Lecture summarization | course_name, lecture_title, lecture_text, language |
| Chat/session summarization | course_name, messages, main_topics, weaknesses, next_steps, language |
| Quiz generation | course_name, topic, difficulty, number_of_questions, question_types, context, language |
| Progress feedback | course_name, score, weak_topics, recommendations, language |
| Study planning | course_name, difficulty, exam_deadline, daily_hours, lecture_count, finish_period, progress, weak_topics, language |
| Reminder generation | course_name, tasks, deadlines, weak_topics, language |

Example template shape:

```python
RAG_ANSWER_PROMPT = """
You are Rafeeqak, a careful study assistant.
Course: {course_name}
Language: {language}

Answer the question using only the course context.
Do not dump raw chunks directly.
If the question is vague, ask a clarification question.

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

Current status checked: 2026-05-15  
Latest verification: `.venv\Scripts\python.exe -m pytest` passes: 42 passed, 2 warnings.

Legend:

- [x] Complete
- [ ] Pending
- [~] Partial

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
- [ ] Store useful per-course chat/session summaries.

### Phase 4 - Multi-Agent Flow

- [x] Implement Input Router, Supervisor, Study Planner, Memory, Safety, RAG, Quiz, Evaluator, and Database Query agents.
- [x] Add route trace logging.
- [x] Wire chat requests through safety, routing, specialist agents, and response generation.
- [x] Add course-aware routing and course-required validation.
- [ ] Ensure CAG cache check happens after routing and before expensive specialist execution.
- [ ] Add Reminder Agent or reminder service.

### Phase 5 - RAG System

- [x] Upload and index PDFs, DOCX, PPTX, Markdown, and text files.
- [x] Extract text, chunk, embed, and persist local vector store.
- [x] Implement Course RAG Agent.
- [x] Add LLM-based RAG answer generation with fallback.
- [x] Index uploaded materials by course_id.
- [x] Search only inside selected-course materials.
- [x] Improve chunking, ranking, and citation format.
- [x] Citations must include course name, file name, and page/chunk reference.
- [ ] Detect vague RAG queries such as "explain" or "اشرح" and ask for clarification before retrieval.
- [ ] Prevent raw chunk dumping and deduplicate repeated chunks/sources.

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
- [ ] Add clear quiz loading, generated, failed, and retry states in the UI.

### Phase 7 - CAG And Structured Database Query

- [x] Add semantic cache for repeated questions.
- [x] Add structured query handler for progress, deadlines, scores, and weak topics.
- [x] Make cache context fingerprints course-aware.
- [x] Make structured queries return selected-course and all-course summaries.
- [ ] Invalidate cache when course, language, materials, quiz attempts, weak topics, progress, or planning inputs change.
- [ ] Do not cache state-changing actions such as quiz generation, plan creation, answer submission, or settings updates.

### Phase 8 - Multi-Course Core Upgrade

- [x] Add course creation and course management UI.
- [x] Add global active-course selector.
- [x] Save active_course_id and active_course_name in session state.
- [x] Require course selection before chat, upload, quiz, dashboard, or study plan actions.
- [x] Separate materials, plans, quizzes, weak topics, progress, route traces, and chat by course.
- [x] Add friendly no-course empty states.

### Phase 9 - Localization And UI Polish

- [x] Detect Arabic input in router.
- [x] Add language toggle: English / Arabic.
- [x] Save selected language in session state and user profile.
- [x] Translate UI labels, alerts, buttons, errors, empty states, and assistant responses.
- [x] Add RTL layout when Arabic is selected.
- [x] Add localization helper files or dictionaries.
- [x] Improve visual polish across all pages.

### Phase 10 - Prompt Templates And LLM Quality

- [x] Add shared Gemini LLM client with offline fallback.
- [x] Move prompts into reusable prompt template files.
- [x] Add templates for course Q&A, RAG answer, lecture summary, quiz generation, progress feedback, and study planning.
- [x] Add variables for course name, question, context, lecture title, lecture text, topic, difficulty, number of questions, score, weak topics, and recommendations.
- [ ] Add chat/session summary prompt template.
- [ ] Add reminder-generation prompt template.

### Phase 11 - Study Planner Upgrade

- [x] Replace fixed-looking plan defaults with more adaptive task generation.
- [x] Add LLM-based plan generation with fallback.
- [ ] Make planning work across multiple courses.
- [ ] Add course difficulty.
- [ ] Ask the student how many lectures they need to study.
- [ ] Ask the student what time period they want to finish the lectures in.
- [ ] Ask for available study time per day when needed.
- [ ] Consider exam deadlines, daily available time, current progress, and weak topics.
- [ ] Prioritize weak topics first, then continue remaining topics in a logical order.
- [ ] Add delayed-task detection and recovery recommendations.

### Phase 12 - Dashboard, Settings, And Reminders

- [ ] Dashboard shows progress per course.
- [ ] Dashboard includes completed tasks, upcoming tasks, quiz scores, average score, weak topics, uploads, deadlines, and reminder summaries.
- [ ] Add settings page for name, language, daily hours, quiz preferences, difficulty, study preferences, and reminder preferences.
- [ ] Add notifications/reminders for upcoming lectures, revision sessions, quizzes, missed study tasks, and deadlines.

### Phase 13 - Testing And Demo

- [x] Automated tests cover app startup, page rendering, auth, memory, routing, RAG, quiz, cache, and LLM provider selection.
- [ ] Add tests for multi-course state separation.
- [ ] Add tests for course selector gating.
- [ ] Add tests for Arabic localization and RTL.
- [ ] Add tests for course-scoped RAG retrieval.
- [ ] Add tests for vague RAG query clarification and no raw chunk dumping.
- [ ] Add tests for quiz question types and partial scoring.
- [ ] Add tests for quiz loading/failure/retry states.
- [ ] Add tests for chat/session summary quality.
- [ ] Add tests for reminder creation.
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
| Full multi-course separation | Complete |
| Global course selector | Complete |
| Course-scoped chat history | Complete |
| Course-scoped RAG retrieval | Complete |
| Full Arabic localization and RTL | Complete |
| Reusable prompt templates | Complete |
| Multiple quiz question types | Complete |
| Partial scoring for text answers | Complete |
| Better chat/session summaries | Pending |
| Vague RAG query clarification and no raw chunk dumping | Pending |
| Study planner input collection | Pending |
| Weak-topic-first planning | Pending |
| Quiz loading/failure/retry states | Pending |
| Notifications/reminders | Pending |
| Settings page | Pending |
| Per-course dashboard summaries | Pending |

---

## 11. Tech Stack

| Component | Technology |
|---|---|
| Language | Python |
| UI | Streamlit |
| LLM Provider | Gemini via google-genai |
| Agent Orchestration | Custom Python agents and supervisor |
| Database | Supabase, with local session fallback |
| Retrieval | Local text extraction, chunking, sparse-vector search |
| PDF Parsing | PyMuPDF |
| DOCX Parsing | python-docx |
| PPTX Parsing | python-pptx |
| Testing | pytest |

Note: langchain and langgraph are installed but not currently used in the implementation.

---

## 12. Enhanced Demo Scenario

- Student logs in.
- Student creates two courses: Machine Learning and Databases.
- Student selects Machine Learning.
- Student uploads ML lecture files.
- Student asks for a study plan.
- Rafeeqak asks how many lectures must be studied, the target finish period, and available daily study time if missing.
- Student generates an ML study plan with exam deadline, difficulty, daily hours, lecture count, and weak topics.
- The generated plan starts with weak topics first.
- Student asks an ML question in Chat and receives a synthesized answer with course-specific citations.
- The session summary highlights the discussed topic, weakness signals, and next steps.
- Student generates a medium-difficulty quiz from ML materials.
- The quiz page displays loading status and then either shows the quiz or a clear failure/retry message.
- Student answers questions, gets detailed feedback, and weak topics update under ML only.
- Student switches to Databases.
- Chat history and materials are empty or Databases-specific, not mixed with ML.
- Student uploads Databases notes and generates a separate Databases quiz.
- Dashboard shows summaries for both courses.
- Reminder cards show upcoming lectures, revision sessions, quizzes, missed tasks, or deadlines.
- Student switches language to Arabic and the UI changes to Arabic RTL.

---

## 13. Final Summary

Rafeeqak already has a strong single-course demo core: authentication, planning, uploads, RAG, quizzes, weak-topic tracking, semantic cache, structured queries, and LLM integration.

The next major goal is to keep turning this into a true multi-course study assistant. The most important upgrade is course scoping: every material, chat message, quiz, weak topic, progress metric, study plan, summary, and reminder must belong to a selected course. After that, better chat/session summaries, improved RAG responses, study-planning input collection, weak-topic-first planning, quiz status feedback, dashboard summaries, settings, and reminders will make the project feel complete and polished.

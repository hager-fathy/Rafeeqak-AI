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
ChatGPT





### Phase 1 — Project Setup
Before building the main features, the project must have a strong technical foundation. This phase prepares the codebase, development environment, dependencies, configuration files, and testing setup. Because Rafeeqak  includes many connected parts such as Streamlit UI, multi-agent routing, RAG, quizzes, memory, database storage, localization, and reminders, the project structure must be clear from the beginning.


The main purpose of this phase is to make the app easy to run, test, and extend. A clean setup also helps the team avoid duplicated code and confusion later. Each major feature should have a clear place in the project, such as pages for UI, agents for intelligence, repositories for database access, services for shared logic, and prompts for LLM templates.

### Phase 2 — Basic UI

After the project foundation is ready, the next step is to build the main user interface. The app should include the pages that students will use regularly, such as login, sign-up, account, chat, study plan, upload materials, quiz, and dashboard. At this stage, the pages do not need to have all advanced logic, but they should provide a clear structure for the full app experience.

The interface should be simple, friendly, and organized. Students should understand where to go and what each page is for. Empty pages should not look broken. Instead, they should show helpful messages that guide the student, such as asking them to create a course, upload materials, or start a study plan.

This phase is important because Rafeeqak is not only an AI system; it is also a student-facing product. A polished interface makes the app easier to demonstrate and easier to use.


### Phase 3 — Database and Memory

This phase focuses on storing and organizing the student’s data. Rafeeqak needs to remember courses, uploaded files, study plans, quiz attempts, quiz scores, weak topics, deadlines, progress, chat history, and user preferences. This information should be saved using Supabase when available, while still supporting local session fallback when Supabase is not configured.

The most important idea in this phase is course-scoped memory. Since a student may study more than one course, data from different courses must never be mixed. For example, Machine Learning quiz scores should stay inside the Machine Learning course, and Databases weak topics should stay inside the Databases course.

Every important data record should include a course identifier when it belongs to a course. This makes the system safer, more organized, and more useful for future features such as dashboards, reminders, and personalized planning.


### Phase 4 — Multi-Agent Flow

This phase creates the intelligent control flow of Rafeeqak. Instead of using one large function to answer every user request, the app should use several specialized agents. Each agent should have a clear responsibility. For example, the Input Router Agent detects the user’s intent, the Study Planner Agent creates plans, the Course RAG Agent answers from uploaded materials, and the Quiz Generator Agent creates quizzes.

The Supervisor Agent should manage the full request pipeline. A request should pass through safety checking, language detection, course selection validation, intent routing, cache checking, specialist agent execution, and final response generation. This makes the system easier to debug and test because every step has a defined role.

This phase also helps Rafeeqak behave more like a real study assistant. It can decide whether the student wants an explanation, a quiz, a progress summary, a study plan, or a database-based answer, then route the request correctly.

### Phase 5 — RAG System

This phase allows Rafeeqak to answer questions using the student’s uploaded course materials. Students should be able to upload files such as PDFs, DOCX files, PPTX files, Markdown files, and text files. The app should extract the text, split it into useful chunks, index the content, and retrieve the most relevant parts when the student asks a question.

The RAG system must be fully course-scoped. If the active course is Machine Learning, Rafeeqak should only search Machine Learning files. It should not use materials from Databases, Security, or any other course. This prevents incorrect answers and keeps the student’s study experience organized.

The final answer should not simply dump raw retrieved chunks. It should explain the topic clearly, summarize the useful information, and include citations that show the course name, file name, and page or chunk reference. If the student asks a vague question such as “explain” or “اشرح”, the system should ask what topic they want explained before retrieving materials.

### Phase 6 — Quiz and Evaluation

This phase turns Rafeeqak into an active learning tool. Instead of only answering questions, the app should help students test themselves using quizzes generated from the selected course materials. The student should be able to choose the quiz difficulty, number of questions, topic, and question types.

The quiz system should support different types of questions, such as multiple choice, true/false, short answer, and matching. This makes practice more flexible and closer to real exam preparation. The system should also avoid generating the same questions repeatedly for the same course.

Evaluation should be more than a final score. Rafeeqak should explain why answers are correct or incorrect, give partial credit for written answers, identify weak topics, and save those weak topics under the selected course. This information can later improve the study planner, dashboard, and recommendations.

The quiz page should also provide clear status feedback. Students should know when a quiz is loading, when it has been generated successfully, and when generation fails. If something goes wrong, the app should show a friendly error message and allow the student to retry.

### Phase 7 — CAG and Structured Database Query

This phase improves both performance and usefulness. CAG, or semantic cache, should help Rafeeqak reuse answers for repeated safe questions. However, caching must be handled carefully. A cached answer should depend on the selected course, selected language, and current context. An answer from Machine Learning should not appear in Databases, and an English answer should not be reused when Arabic is selected.

The cache should also avoid state-changing actions. Actions such as generating a quiz, creating a study plan, submitting answers, updating settings, or changing preferences should always run fresh because they change the student’s data.

Structured database querying allows Rafeeqak to answer questions from stored progress data. For example, a student may ask about weak topics, completed tasks, delayed tasks, upcoming deadlines, average score, or progress across courses. These answers should come from the database or local memory, not from general LLM guessing.

### Phase 8 — Multi-Course Core Upgrade

This is one of the most important phases in the whole project. Rafeeqak should work as a true multi-course study platform, not only as a single-course assistant. Students should be able to create courses, select the active course, and use every major feature inside that selected course.

All course-related data must be separated. This includes uploaded materials, RAG indexes, chat history, study plans, quiz attempts, weak topics, progress records, dashboard summaries, route traces, and reminders. The selected course should control what the student sees and what the system uses.

If no course exists, the app should guide the student to create one. If courses exist but none is selected, the app should ask the student to select a course before using chat, uploads, quizzes, study planning, or dashboard features. This prevents accidental data mixing and makes the app easier to understand.

### Phase 9 — Localization and UI Polish

This phase makes Rafeeqak usable in both English and Arabic. The app should include a language toggle and save the student’s language preference. When Arabic is selected, the interface should support RTL layout so the app feels natural for Arabic-speaking users.

Localization should cover the full product experience, not only a few page titles. Buttons, alerts, errors, empty states, assistant responses, quiz feedback, dashboard labels, settings labels, and reminder messages should all be translated. The system should also detect Arabic input and respond appropriately.

This phase also includes visual polish. The spacing, colors, layout, labels, buttons, and page sections should feel consistent across the app. The goal is to make Rafeeqak look like a finished product instead of a rough prototype.

### Phase 10 — Prompt Templates and LLM Quality

This phase improves the quality and maintainability of the AI responses. Instead of keeping prompts hardcoded inside different agents, prompts should be moved into reusable template files. This makes the system easier to update, test, and improve.

Each prompt should include the correct variables, such as course name, language, question, context, citations, lecture title, topic, difficulty, number of questions, score, weak topics, recommendations, tasks, and deadlines. This helps the LLM produce more consistent and relevant responses.

The prompt templates should also guide Rafeeqak to behave like a careful study assistant. It should answer clearly, avoid raw chunk dumping, ask clarifying questions when needed, produce localized responses, and give student-friendly explanations.

### Phase 11 — Study Planner Upgrade

This phase makes the study planner more personalized and useful. Instead of creating a generic plan, Rafeeqak should collect the information needed to build a realistic study schedule. This includes the number of lectures, target finish period, daily available study time, course difficulty, exam date, current progress, and weak topics.

The plan should prioritize weak topics first because those are the areas where the student needs the most support. After that, it should continue with the remaining topics in a logical order. The plan should also consider the student’s available time and deadlines so the schedule feels realistic.

The planner should also detect delayed or missed tasks and suggest recovery actions. For example, if a student missed two study sessions, Rafeeqak should recommend how to catch up without making the plan impossible to follow.

### Phase 12 — Dashboard, Settings, and Reminders

This phase makes Rafeeqak feel like a complete study platform. The dashboard should give students a clear overview of their learning status across courses. It should show course cards, progress, completed tasks, upcoming tasks, quiz scores, average score, weak topics, uploaded materials, deadlines, and reminder summaries.

The settings page should allow students to customize their experience. They should be able to edit their name, language, daily study hours, quiz preferences, difficulty level, study preferences, and reminder preferences. These settings should improve personalization across the app.

Reminders should help students stay consistent. Rafeeqak should notify students about upcoming lectures, revision sessions, quizzes, missed study tasks, and deadlines. These reminders should be stored with course information so each reminder belongs to the correct course.

###Phase 13 — Testing and Demo

This final phase proves that the app works correctly and is ready to present. Automated tests should cover the most important behavior, especially course separation, course selector gating, Arabic localization, RTL layout, RAG retrieval, quiz generation, partial scoring, chat summaries, reminders, and dashboard data.

Testing should also confirm that the app does not mix data between courses. This is one of the most important risks in the project. For example, a quiz generated in Machine Learning should not affect Databases weak topics, and RAG should only retrieve from the active course.

The final demo should tell a complete story. A student creates two courses, uploads materials, asks course-specific questions, generates a study plan, takes a quiz, receives feedback, switches to another course, sees separated data, opens the dashboard, and changes the language to Arabic. This will show that Rafeeqak is not just a collection of features, but a complete multi-course study assistant.



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
- [x] Detect vague RAG queries such as "explain" or "اشرح" and ask for clarification before retrieval.
- [x] Prevent raw chunk dumping and deduplicate repeated chunks/sources.

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
- [x] Add clear quiz loading, generated, failed, and retry states in the UI.

### Phase 7 - CAG And Structured Database Query

- [x] Add semantic cache for repeated questions.
- [x] Add structured query handler for progress, deadlines, scores, and weak topics.
- [x] Make cache context fingerprints course-aware.
- [x] Make structured queries return selected-course and all-course summaries.
- [x] Invalidate cache when course, language, materials, quiz attempts, weak topics, progress, or planning inputs change.
- [x] Do not cache state-changing actions such as quiz generation, plan creation, answer submission, or settings updates.

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
- [x] Add tests for vague RAG query clarification and no raw chunk dumping.
- [ ] Add tests for quiz question types and partial scoring.
- [x] Add tests for quiz loading/failure/retry states.
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
| Vague RAG query clarification and no raw chunk dumping | Complete |
| Study planner input collection | Pending |
| Weak-topic-first planning | Pending |
| Quiz loading/failure/retry states | Complete |
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

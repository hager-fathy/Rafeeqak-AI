# Smart Study Planner Chatbot — Project Brief

> **One-sentence pitch:**
> A multilingual agentic study assistant that builds personalized study plans, remembers each student's goals and weaknesses, retrieves course material, tracks progress, and helps students revise smarter before exams.

- **Course context:** Deep Generative Models — Fourth Year Course Project
- **Target domain:** Education — study planning, exam preparation, course assistant, and personalized learning support

---

## 1. The Problem We Are Solving

Many students struggle to prepare for exams because their study resources, deadlines, lecture notes, weak topics, and revision plans are scattered across different places.

General chatbots usually do not remember progress, do not understand course materials, and do not create realistic study schedules.

**Smart Study Planner Chatbot** solves this by acting as a personalized AI study coach. It combines planning, memory, retrieval, quiz generation, progress tracking, and multi-agent collaboration.

---

## 2. What the Product Does

1. **Personalized study planning** — Creates daily or weekly schedules based on exams, deadlines, available time, and topic difficulty.
2. **Course-material Q&A** — Answers questions using uploaded lectures, notes, PDFs, and summaries through RAG.
3. **Weakness detection** — Uses quiz results and previous interactions to detect topics the student struggles with.
4. **Adaptive revision** — Updates the plan after each study session based on progress.
5. **Persistent memory** — Remembers goals, exam dates, preferred study times, completed topics, and weak areas.
6. **Quiz and flashcard generation** — Generates MCQs, short-answer questions, and flashcards from course material.
7. **Multilingual support** — Handles Arabic and English input/output.
8. **Safety** — Detects prompt injection and filters irrelevant or unsafe outputs.


---

## 3. Typical Session

**Student:**
> "I have a Machine Learning exam in 10 days. I am weak in backpropagation and SVM. I can study 2 hours per day."

**Smart Study Planner:**
- Stores the exam date, available daily time, and weak topics.
- Creates a 10-day plan with priority on backpropagation and SVM.
- Adds quiz checkpoints.

**Student uploads lecture slides.**

**Smart Study Planner:**
- Indexes the slides.
- Retrieves relevant sections when needed.
- Generates practice questions from the material.

**Student, three days later:**
> "What should I study today?"

**Smart Study Planner:**
- Recalls the saved plan.
- Checks completed progress.
- Recommends the next topic and quiz.

---

## 4. Architecture Overview

```
User Interface: Streamlit or Gradio
        |
        v
Input Router Agent
- Detects intent
- Detects language
        |
        v
Supervisor Agent
- Coordinates all specialist agents
        |
        +--> Study Planner Agent
        +--> Course RAG Agent
        +--> Quiz Generator Agent
        +--> Progress Evaluator Agent
        +--> Memory Agent
        +--> Safety Agent
        |
        v
Response Agent
- Produces the final student-friendly response
```

---

## 5. Mapping to Course Requirements

### 5.1 Multi-Agent System

| # | Agent | Responsibility |
|---|-------|----------------|
| 1 | Input Router Agent | Detects intent and language |
| 2 | Supervisor Agent | Routes the request dynamically |
| 3 | Study Planner Agent | Creates and updates study schedules |
| 4 | Course RAG Agent | Retrieves relevant course material and answers questions |
| 5 | Quiz Generator Agent | Generates MCQs, flashcards, and practice questions |
| 6 | Progress Evaluator Agent | Grades answers and detects weak topics |
| 7 | Memory Agent | Stores and retrieves student goals, progress, and preferences |
| 8 | Safety Agent | Detects prompt injection and filters unsafe requests |
| 9 | Response Agent | Produces the final clear answer |

---

### 5.2 Advanced Memory System

| Memory Type | Contents |
|-------------|----------|
| Student profile memory | Name, language, study style, preferred study hours |
| Academic memory | Courses, exams, deadlines, syllabus topics |
| Progress memory | Completed topics, quiz scores, missed questions |
| Weakness memory | Repeated mistakes and weak topics |
| Episodic memory | Summaries of important past sessions |

**Example:**
- **Session 1:** Student says they are weak in backpropagation.
- **Session 2:** Student asks what to revise.
- The chatbot remembers and schedules backpropagation practice.

---

### 5.3 Tool Integration

1. **RAG** — Retrieves lecture notes, PDFs, slides, and summaries.
2. **CAG** — Caches repeated questions and study plans.
3. **Database Query** — Retrieves exam dates, completed tasks, quiz scores, and weak topics.

---

### 5.4 User Interface

**Recommended UI:** Streamlit

| Page | Description |
|------|-------------|
| Chat | Main conversational interface |
| Study Plan | View and manage the generated schedule |
| Upload Materials | Upload PDFs, slides, and notes |
| Quiz | Take practice quizzes |
| Progress Dashboard | Visualize scores and completion |
| Memory Viewer | Inspect stored student profile and memory |

---

## 6. Implementation Plan

**Current status checked:** 2026-05-04  
**Verification:** `pytest` passes: 10 passed, 2 warnings.

Legend:
- `[x]` Complete
- `[ ]` Pending
- `Partial` means a scaffold or UI-only version exists, but the full project requirement is not finished yet.

### Phase 1 — Project Setup
- [x] Create Python project.
- [x] Install Streamlit, LangChain/LangGraph, vector DB, database library, and LLM SDK.
- [x] Add environment variables.

### Phase 2 — Basic UI
- [x] Build Streamlit navigation.
- [x] Add chat, study plan, upload, quiz, and dashboard pages.
- [x] Add login, sign-up, and account pages.

### Phase 3 — Database and Memory
- [x] Create SQLite or Supabase schema.
- [x] Implement student profile, courses, exams, tasks, quiz scores, and weak topics.
- [x] Sync generated study plans and quiz attempts to Supabase when configured.

### Phase 4 — Multi-Agent Graph
- [x] Implement Input Router, Supervisor, Study Planner, and Memory agents.
- [x] Add route trace logging.
- [x] Wire chat requests through Safety Agent, Input Router Agent, Supervisor Agent, selected specialist agent, and Response Agent.

### Phase 5 — RAG System
- [x] Upload course documents. Files can be saved through the Upload Materials page.
- [x] Extract text, chunk, and embed.
- [x] Store in vector database.
- [x] Implement Course RAG Agent.

### Phase 6 — Quiz and Evaluation
- [x] Implement Quiz Generator Agent.
- [x] Implement Progress Evaluator Agent.
- [x] Store quiz scores and update weak topics automatically.

### Phase 7 — CAG and Database Query
- [ ] Add semantic cache for repeated questions.
- [ ] Add structured query handler for progress and deadlines.

### Phase 8 — Bonus Features
- [ ] Multimodal input: upload images of notes or screenshots.
- [ ] Multilingual support: Arabic and English. Partial: the input router detects Arabic, but localized responses are not fully implemented.
- [ ] Prompt injection detection. Partial: a simple Safety Agent exists, but it is not fully integrated into the app flow.
- [ ] Output filtering.

### Phase 9 — Testing and Demo
- [ ] Test study planning, RAG answers, memory improvement, and quiz scoring. Partial: current automated tests cover app startup, page rendering, auth service, memory agent, Phase 4 routing/planning/supervision, and smoke imports.
- [ ] Prepare demo script.

---

## 7. Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python |
| UI | Streamlit |
| LLM Orchestration | LangChain or LangGraph |
| Database | SQLite or Supabase |
| Vector Database | FAISS or ChromaDB |
| PDF Parsing | PyMuPDF |
| Embeddings | SentenceTransformers or OpenAI Embeddings |
| Testing | pytest |

---

## 8. Demo Scenario

1. Add course: **Machine Learning**.
2. Add exam date: 10 days from today.
3. Tell the chatbot: *"I am weak in SVM and backpropagation."*
4. Generate a study plan.
5. Upload a lecture PDF.
6. Ask: *"Explain backpropagation from my notes."*
7. Ask: *"Quiz me on backpropagation."*
8. Answer some questions incorrectly.
9. Ask: *"What should I study tomorrow?"*
10. Show that the chatbot remembers the weak topic and updates the plan.

---

## 9. Repository Map

```
smart-study-planner/
├── app.py
├── requirements.txt
├── .env.example
├── README.md
├── data/
│   ├── uploads/
│   └── vector_store/
├── src/
│   ├── agents/
│   │   ├── input_router.py
│   │   ├── supervisor.py
│   │   ├── study_planner.py
│   │   ├── course_rag.py
│   │   ├── quiz_generator.py
│   │   ├── progress_evaluator.py
│   │   ├── memory_agent.py
│   │   └── safety_agent.py
│   ├── memory/
│   ├── retrieval/
│   ├── tools/
│   └── ui/
├── tests/
└── docs/
```

---

## 10. Final Summary

**Smart Study Planner Chatbot** is an education-focused multi-agent system that helps students plan, revise, and improve. It satisfies the project requirements by using specialized agents, persistent memory, retrieval over course materials, database-backed progress tracking, and a Streamlit interface.

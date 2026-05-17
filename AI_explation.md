# AI Explanation

This file explains what AI integration the Smart Study Planner currently uses, where the AI is connected in code, how it is configured, which parts are template-based fallbacks, and what is active versus only prepared for future use.

## What The App Uses

The app uses a shared LLM wrapper:

```text
src/tools/llm_client.py
```

Supported runtime modes:

| Mode | Configuration | Behavior |
|---|---|---|
| Gemini mode | `GEMINI_API_KEY` configured and SDK installed | Active LLM calls for selected features |
| Offline fallback | no valid key, SDK missing, or invalid model output | Deterministic Python logic and templates |

Current provider settings:

| Provider | Environment variable | Default model source |
|---|---|---|
| Gemini | `GEMINI_API_KEY` | `DEFAULT_GEMINI_MODEL` from `src/config.py`, overridable with `GEMINI_MODEL` |

If Gemini is unavailable, the app still works for demo and testing because planner, RAG, and quiz flows have fallback behavior.

## How To Use Gemini

1. Open the `.env` file in the project root.
2. Add your Gemini settings:

```env
GEMINI_API_KEY=your_real_gemini_key
GEMINI_MODEL=your_preferred_model
```

3. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

4. Run the app:

```powershell
streamlit run app.py
```

## Why The App Uses AI

The project uses AI to improve adaptability and answer quality where static logic alone would feel too rigid.

| Feature | Why AI helps |
|---|---|
| Study Planning | Produces more personalized daily task sequences from difficulty, exam date, weak topics, lecture count, finish period, and progress. |
| Course RAG Chat | Turns retrieved course chunks into cleaner, grounded answers with source citations. |
| Quiz Generation | Produces custom questions and flashcards from topic and course-material context. |

The project intentionally keeps offline fallback logic so the system remains stable during:

- missing API key situations
- test runs
- network issues
- invalid model output
- demo environments without cloud access

## Main AI Client Code

File:

```text
src/tools/llm_client.py
```

Main settings flow:

```python
def get_llm_settings(*, env_path=None, override_env=False) -> LLMSettings:
    load_project_env(env_path=env_path, override=override_env)
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_model = (os.getenv("GEMINI_MODEL") or "").strip() or DEFAULT_GEMINI_MODEL
    return LLMSettings(
        provider="gemini",
        api_key=gemini_key,
        model=gemini_model,
    )
```

Gemini text call:

```python
response = self.client.models.generate_content(
    model=self.settings.model,
    contents=user_prompt,
    config=genai_types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        max_output_tokens=max_tokens,
    ),
)
```

JSON helper:

```python
payload = self.generate_text(...)
match = re.search(r"\{.*\}", text, flags=re.DOTALL)
parsed = json.loads(match.group(0))
```

Important note:

- the wrapper is intentionally small
- each agent still validates model output before trusting it

## Prompt Template System

Prompt registry:

```text
src/prompts/registry.py
```

Prompt templates:

```text
src/prompts/templates/
```

Available templates:

| Template | Files | Main variables |
|---|---|---|
| Course Q&A | `course_question.system.txt`, `course_question.user.txt` | `course_name`, `question`, `language` |
| RAG answer | `rag_answer.system.txt`, `rag_answer.user.txt` | `course_name`, `question`, `context`, `citations`, `language` |
| Lecture summary | `lecture_summary.system.txt`, `lecture_summary.user.txt` | `course_name`, `lecture_title`, `lecture_text`, `language` |
| Quiz generation | `quiz_generation.system.txt`, `quiz_generation.user.txt` | `course_name`, `topic`, `difficulty`, `number_of_questions`, `question_types`, `context`, `avoid_questions`, `language` |
| Progress feedback | `progress_feedback.system.txt`, `progress_feedback.user.txt` | `course_name`, `score`, `weak_topics`, `recommendations`, `language` |
| Study planning | `study_planning.system.txt`, `study_planning.user.txt` | `course_name`, `difficulty`, `exam_deadline`, `daily_hours`, `lecture_count`, `finish_period`, `progress`, `weak_topics`, `language` |

Important distinction:

- active runtime templates:
  - `rag_answer`
  - `quiz_generation`
  - `study_planning`
- prepared but not currently wired into a live page flow:
  - `course_question`
  - `lecture_summary`
  - `progress_feedback`

## Where AI Is Used

### 1. Study Planner

File:

```text
src/agents/study_planner.py
```

Main LLM path:

```python
_generate_tasks_with_llm(...)
```

What it sends:

- course name
- difficulty
- exam deadline
- daily hours
- lecture count
- finish period
- weak topics
- progress summary
- response language

What it expects:

- JSON with a `tasks` list
- one task per planning day
- each task containing topic, phase, hours, task text, and checkpoint state

Fallback if LLM is unavailable or invalid:

- `_build_offline_tasks(...)`

### 2. Course RAG Chat

File:

```text
src/agents/course_rag.py
```

Main LLM path:

```python
_compose_llm_answer(...)
```

What it sends:

- student question
- course name
- retrieved chunk text
- citation labels
- response language

What it expects:

- a grounded answer based only on retrieved material

What happens without Gemini:

- the agent uses `_compose_offline_answer(...)`
- the answer still includes sources and avoids raw chunk dumping when possible

### 3. Quiz Generator

File:

```text
src/agents/quiz_generator.py
```

Main LLM path:

```python
_generate_with_llm(...)
```

What it sends:

- course name
- topic
- difficulty
- number of questions
- question types
- retrieved context
- previous questions to avoid
- response language

What it expects:

- structured JSON with `questions`
- optional `flashcards`

Important runtime note:

- the LLM path is only used when question types normalize to `["mcq"]`
- mixed quiz-type generation falls back to deterministic Python generation

## How AI Connects To Retrieval

The LLM does not operate alone. It is layered on top of local retrieval.

Retrieval files:

```text
src/retrieval/course_materials.py
src/agents/course_rag.py
src/ui/upload_page.py
```

Flow:

1. The user uploads course files.
2. Files are extracted and chunked.
3. Chunks are indexed into a local sparse-vector store.
4. RAG and quiz generation retrieve relevant chunks.
5. The LLM receives only the retrieved context, not the whole repository.

This keeps the AI behavior course-scoped and grounded.

## How AI Connects To Agent Architecture

Supervisor file:

```text
src/agents/supervisor.py
```

Related routing files:

```text
src/agents/input_router.py
src/agents/safety_agent.py
```

The AI-related features do not run directly from the UI. The app flow is:

1. User sends a message or action through the UI.
2. `SupervisorAgent` runs safety and routing.
3. The selected specialist agent decides whether to use Gemini or fallback logic.
4. The response returns with structured payload data.

This means AI is part of a larger agent system, not a single direct chatbot call.

## Fallback Behavior

The project is intentionally resilient when the LLM is unavailable.

If Gemini fails:

- Study planner uses offline adaptive planner logic.
- RAG chat uses offline grounded answer synthesis.
- Quiz generator uses deterministic local templates and context-aware heuristics.

Common generation modes:

| Mode | Meaning |
|---|---|
| `llm` | Gemini produced the final structured output |
| `offline_template` | local deterministic logic produced the result |
| `clarification` | the system asked for a clearer query before retrieval |

## What Is Not Fully AI-Driven

Some important project behaviors are still heuristic by design:

- `InputRouterAgent` is keyword-based
- `SafetyAgent` is blacklist-based
- semantic cache is sparse-token based
- retrieval embeddings are local sparse lexical vectors, not neural embeddings

This is still acceptable for the course project, but it should be presented honestly as a hybrid AI system, not a fully model-driven autonomous architecture.

## Testing

Relevant AI and AI-adjacent tests:

```text
tests/test_llm_client.py
tests/test_phase10_prompts.py
tests/test_phase4_agents.py
tests/test_phase5_rag.py
tests/test_phase6_quiz.py
tests/test_phase7_cache_query.py
```

Latest verified full test result:

```text
134 passed
```

## Dependencies

Gemini SDK dependency is listed in:

```text
requirements.txt
```

Expected package:

```text
google-genai>=1.0.0
```

## Short Summary

The app uses Gemini through `GEMINI_API_KEY` and optional `GEMINI_MODEL`. Active LLM-backed features are:

- study planning
- course-material RAG answers
- quiz generation

Prompts live in reusable template files under `src/prompts/templates` and are rendered through `src/prompts/registry.py`. The app remains stable without AI because all major LLM-backed features have deterministic fallback behavior.

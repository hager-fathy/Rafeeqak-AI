# AI Explanation

This file explains what AI model integration the Smart Study Planner uses, how to configure it, where the prompt templates live, how the app falls back when AI is unavailable, and which code paths use the model.

## What The App Uses

The app uses a shared LLM wrapper:

```text
src/tools/llm_client.py
```

The wrapper supports:

| Provider | Environment variable | Default model |
|---|---|---|
| Gemini | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | `gemini-2.5-flash` |
| Offline fallback | no key needed | Python templates/rules |

If `GEMINI_API_KEY` is configured, the app can use Gemini. If Gemini is missing, unavailable, or returns invalid output, the app still works with deterministic offline logic.

## How To Use Gemini

1. Open the `.env` file in the project root.
2. Add your Gemini key:

```env
GEMINI_API_KEY=your_real_gemini_key
GEMINI_MODEL=gemini-2.5-flash
```

3. Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. Run the app:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

## Why The App Uses AI

The AI model is used to make the study assistant less fixed and more personalized.

| Feature | Why AI helps |
|---|---|
| Study Plan | Creates more personalized daily tasks from course name, difficulty, exam deadline, weak topics, progress, and daily hours. |
| Course RAG Chat | Reads retrieved chunks from uploaded course materials and writes a clearer answer with sources. |
| Quiz Generator | Creates custom MCQs and flashcards from the topic and uploaded course context. |

The app keeps offline fallback logic because demos and tests should work even without an API key or internet connection.

## Main AI Client Code

File:

```text
src/tools/llm_client.py
```

Provider settings:

```python
def get_llm_settings() -> LLMSettings:
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    return LLMSettings(
        provider="gemini",
        api_key=gemini_key,
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    )
```

Gemini call:

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
payload = llm_client.generate_json(
    system_prompt=prompt.system,
    user_prompt=prompt.user,
)
```

The JSON helper extracts and validates a JSON object from the model response. Agents still validate the returned structure before using it.

## Prompt Template System

Phase 10 moved prompts out of hardcoded agent strings into reusable template files.

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
| Quiz generation | `quiz_generation.system.txt`, `quiz_generation.user.txt` | `course_name`, `topic`, `difficulty`, `number_of_questions`, `question_types`, `context`, `language` |
| Progress feedback | `progress_feedback.system.txt`, `progress_feedback.user.txt` | `course_name`, `score`, `weak_topics`, `recommendations`, `language` |
| Study planning | `study_planning.system.txt`, `study_planning.user.txt` | `course_name`, `difficulty`, `exam_deadline`, `daily_hours`, `progress`, `weak_topics`, `language` |

Prompt rendering example:

```python
prompt = render_prompt(
    "rag_answer",
    course_name=course_name,
    question=question,
    context=joined_sources,
    citations=citation_labels,
    language=response_language,
)
```

The registry uses `{{variable}}` placeholders. This avoids conflicts with JSON examples inside prompt files.

## Where AI Is Used

### 1. Study Planner

File:

```text
src/agents/study_planner.py
```

Function:

```python
_generate_tasks_with_llm(...)
```

What it does:

- Renders the `study_planning` prompt template.
- Sends course name, difficulty, exam deadline, daily hours, progress, weak topics, language, and planning context.
- Requests JSON with daily tasks.
- Validates task count and task fields.
- Falls back to the offline planner if the LLM is unavailable or returns invalid data.

Important call shape:

```python
prompt = render_prompt("study_planning", ...)
payload = self.llm_client.generate_json(
    system_prompt=prompt.system,
    user_prompt=prompt.user,
)
```

### 2. Course RAG Chat

File:

```text
src/agents/course_rag.py
```

Function:

```python
_compose_llm_answer(...)
```

What it does:

- Retrieves relevant text chunks from uploaded course materials.
- Renders the `rag_answer` prompt template.
- Sends only retrieved chunks, citation labels, course name, and the student question to the LLM.
- Tells the model to answer only from uploaded material.
- Includes sources in the final answer.

Why this matters:

The LLM should not invent course content. It should answer from the uploaded files only.

### 3. Quiz Generator

File:

```text
src/agents/quiz_generator.py
```

Function:

```python
_generate_with_llm(...)
```

What it does:

- Renders the `quiz_generation` prompt template.
- Sends course name, topic, difficulty, question count, question type, language, and retrieved course context.
- Requests structured JSON with MCQs and flashcards.
- Validates every question before using it.
- Falls back to offline quiz templates if the LLM output is invalid.

Expected JSON shape:

```json
{
  "questions": [
    {
      "question": "Which rule is central to backpropagation?",
      "options": ["Chain rule", "Bayes rule", "Sorting rule", "Voting rule"],
      "answer_index": 0,
      "explanation": "Backpropagation applies the chain rule through layers.",
      "source": "uploaded notes"
    }
  ],
  "flashcards": [
    {
      "front": "Backpropagation",
      "back": "Computes gradients through model layers."
    }
  ]
}
```

## Templates Prepared For Future AI Use

Some templates are already present even if the current UI does not yet expose a dedicated LLM feature for them:

- `course_question`
- `lecture_summary`
- `progress_feedback`

They are ready for future Phase 11+ agent upgrades.

## Fallback Behavior

The app is designed to avoid breaking when the LLM is unavailable.

If Gemini fails:

- Study plan uses Python planner logic.
- RAG chat uses retrieved text snippets directly.
- Quiz generator uses local quiz templates.

Common generation modes:

| Mode | Meaning |
|---|---|
| `llm` | Gemini generated the result. |
| `offline_template` | The app used local Python logic instead. |

## Testing

AI and prompt behavior is covered by tests:

```text
tests/test_llm_client.py
tests/test_phase10_prompts.py
tests/test_phase4_agents.py
tests/test_phase5_rag.py
tests/test_phase6_quiz.py
```

Latest verified full test result:

```text
51 passed
```

## Dependencies

The Gemini SDK dependency is in:

```text
requirements.txt
```

Dependency:

```text
google-genai>=1.0.0
```

## Short Summary

The app uses Gemini through `GEMINI_API_KEY` or `GOOGLE_API_KEY`. AI is used in study planning, course-material answers, and quiz generation. Prompts now live in reusable template files under `src/prompts/templates`, rendered through `src/prompts/registry.py`. The app keeps deterministic offline fallback logic so it remains stable during tests, demos, missing API-key situations, or temporary AI failures.

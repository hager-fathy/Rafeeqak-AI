# AI Explanation

This file explains what AI model integration the Smart Study Planner uses, how to use it, why it is useful, and where the important code lives.

## What The App Uses

The app uses a shared LLM wrapper:

```text
src/tools/llm_client.py
```

The wrapper supports:

| Provider | Environment variable | Default model |
|---|---|---|
| Gemini | `GEMINI_API_KEY` | `gemini-2.5-flash` |
| Offline fallback | no key needed | Python templates/rules |

If `GEMINI_API_KEY` is configured, the app uses Gemini. If Gemini is not configured, the app still works with offline deterministic logic.

## How To Use Gemini

1. Open the `.env` file in the project root.
2. Add your Gemini key:

```env
GEMINI_API_KEY=your_real_gemini_key
GEMINI_MODEL=gemini-2.5-flash
```

3. Make sure dependencies are installed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. Run the app:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

## Why The App Uses AI

The AI model is used to make the app less fixed and more personalized.

| Feature | Why AI helps |
|---|---|
| Study Plan | Creates more personalized daily tasks from course name, exam date, weak topics, and daily hours. |
| Course RAG Chat | Reads retrieved chunks from uploaded materials and writes a clearer answer with sources. |
| Quiz Generator | Creates custom MCQs and flashcards from the topic and uploaded course context. |

The app still keeps fallback logic because demos and tests should work even without an API key or internet connection.

## Main AI Client Code

File:

```text
src/tools/llm_client.py
```

Important provider selection code:

```python
def get_llm_settings() -> LLMSettings:
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and gemini_key.strip() not in PLACEHOLDER_KEYS:
        return LLMSettings(
            provider="gemini",
            api_key=gemini_key,
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        )

    return LLMSettings(
        provider="gemini",
        api_key=gemini_key,
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    )
```

Important Gemini call:

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

- Sends the course name, exam date, weak topics, other topics, and daily study hours to the LLM.
- Requests a JSON plan.
- Validates the returned tasks.
- Falls back to the offline planner if the LLM is unavailable or returns invalid data.

Example logic:

```python
tasks = self._generate_tasks_with_llm(
    course_name=course_name,
    exam_date=exam_date,
    daily_hours=daily_hours,
    weak_topics=weak_topics,
    other_topics=other_topics,
    days_until_exam=days_until_exam,
    today=today,
)
generation_mode = "llm" if tasks else "offline_template"
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
- Sends only those chunks and the student question to the LLM.
- Tells the model to answer only from uploaded material.
- Includes sources in the final answer.

Example prompt rule:

```python
system_prompt = (
    "You are a careful study assistant. Answer only from the provided course-material excerpts. "
    "If the excerpts do not support an answer, say that the uploaded material does not contain enough detail. "
    "Keep the answer concise and include a final Sources line using the given citation labels."
)
```

Why this is important:

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

- Sends the topic and retrieved course chunks to the LLM.
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

## Fallback Behavior

The app is designed to avoid breaking when the LLM is unavailable.

If Gemini fails:

- Study plan uses Python planner logic.
- RAG chat uses retrieved text snippets directly.
- Quiz generator uses local MCQ templates.

This is why many responses include:

```python
generation_mode = "llm" if tasks else "offline_template"
```

or:

```python
return None
```

The agent sees `None` and falls back to the older offline logic.

## How To Know If AI Was Used

Some returned payloads include:

```python
"generation_mode": "llm"
```

or:

```python
"generation_mode": "offline_template"
```

Meaning:

| Mode | Meaning |
|---|---|
| `llm` | Gemini generated the result. |
| `offline_template` | The app used local Python logic instead. |

## Dependencies

The Gemini SDK dependency is in:

```text
requirements.txt
```

Code:

```text
google-genai>=1.0.0
```

## Short Summary

The app now uses Gemini through `GEMINI_API_KEY`. The AI is used in study planning, course-material answers, and quiz generation. The app also keeps offline fallback logic so it remains stable during tests, demos, or missing API-key situations.

# Rafeeqak Final Demo Script

## Purpose

This script gives the presenter a complete graduation-project walkthrough for Rafeeqak. It demonstrates the product story from login through multi-course study support, RAG, planning, quizzes, progress tracking, reminders, and Arabic localization.

Target duration: 10 to 15 minutes.

## Pre-Demo Setup

1. Install dependencies.

   ```powershell
   pip install -r requirements.txt
   ```

2. Copy environment variables.

   ```powershell
   Copy-Item .env.example .env
   ```

3. Optional: configure Supabase and Gemini in `.env`.

   The demo still works with local fallback when Supabase or Gemini is not configured. In that case, the app should show friendly local-only or Gemini-missing notices.

4. Start the app.

   ```powershell
   streamlit run app.py
   ```

5. Keep these demo files ready for upload:

   - `docs/demo_materials/machine_learning_notes.md`
   - `docs/demo_materials/database_notes.md`

## Demo Data

Use this presenter account when local fallback auth is active:

- Email: `demo@example.com`
- Name: `Demo Student`

Use these course names:

- `Machine Learning`
- `Databases`

Use these planning inputs for Machine Learning:

- Exam date: about 10 days from today
- Difficulty: `hard`
- Lecture count: `8`
- Finish period: `5`
- Daily hours: `2`
- Weak topics: `Backpropagation, Overfitting`
- Other topics: `Gradient Descent, Model Evaluation`

Use these planning inputs for Databases:

- Exam date: about 14 days from today
- Difficulty: `medium`
- Lecture count: `6`
- Finish period: `4`
- Daily hours: `1.5`
- Weak topics: `Transactions`
- Other topics: `Indexes, Normalization`

## Presenter Story

Opening line:

"Rafeeqak is a multilingual, multi-course study assistant. The main risk in student study apps is mixing data between courses, so this demo focuses on course-scoped memory, RAG, quizzes, planning, progress, and reminders."

## Walkthrough

### 1. Login And Empty State

1. Open the app.
2. Log in or use the available local fallback account flow.
3. Show the top navigation.
4. Point out the language toggle and the active-course selector.
5. Before creating a course, open Chat or Upload Materials and show that actions are gated until a course is selected.

Expected evidence:

- Authenticated pages render.
- Course-scoped actions show a friendly "select a course" state.
- The app does not allow accidental chat, upload, quiz, or plan work without a course.

### 2. Create Machine Learning

1. Use the global course field to add `Machine Learning`.
2. Confirm it becomes the active course.
3. Open Manage Courses and briefly show rename/delete controls.

Expected evidence:

- Active course displays as Machine Learning.
- Page chips mention the active course.

### 3. Upload Machine Learning Material

1. Go to Upload Materials.
2. Upload `docs/demo_materials/machine_learning_notes.md`.
3. Save the upload.
4. Show stored file count and indexed chunk count.

Expected evidence:

- File is stored under the active course.
- RAG index chunk count increases.
- Upload library shows the Machine Learning demo file.

### 4. Ask A Course-Scoped RAG Question

1. Go to Chat.
2. Ask: `Explain backpropagation from my notes.`
3. Show the answer and sources.
4. Ask a vague question such as `Explain`.
5. Show that Rafeeqak asks for clarification instead of dumping raw chunks.

Expected evidence:

- The response explains backpropagation from the uploaded material.
- Citations reference Machine Learning and the uploaded file/chunk.
- Vague RAG query receives a clarification prompt.
- Chat summary panel captures main topics, weakness signals, and next steps after the exchange.

### 5. Generate A Weak-Topic Study Plan

1. Go to Study Plan.
2. Enter the Machine Learning planning inputs from Demo Data.
3. Generate the plan.
4. Show the timeline and the insights panel.
5. Mark one task as done.

Expected evidence:

- Plan includes weak topics before or more often than regular topics.
- Plan uses lecture count, finish period, daily hours, difficulty, and deadline.
- Timeline updates completion status.
- Reminder records are created from the plan.

### 6. Generate And Submit A Quiz

1. Go to Quiz.
2. Select the Machine Learning uploaded file.
3. Choose medium or hard difficulty.
4. Select question types: MCQ, true/false, short answer, and matching.
5. Generate the quiz.
6. Answer at least one question incorrectly or partially.
7. Submit the quiz.
8. Show feedback, partial scoring, weak-topic detection, flashcards, and attempt history.

Expected evidence:

- Loading, generated, and failure/retry states are available.
- Quiz is generated from selected-course material.
- Evaluation gives score, detailed feedback, weak topics, and recommendation.
- Quiz attempt is saved under Machine Learning only.

### 7. Create Databases And Prove Course Separation

1. Add `Databases` from the global course field.
2. Confirm Databases is now active.
3. Go to Chat and show Machine Learning chat history is not displayed.
4. Go to Upload Materials and upload `docs/demo_materials/database_notes.md`.
5. Ask: `Explain ACID transactions from my notes.`
6. Generate a Databases study plan using the Databases demo inputs.

Expected evidence:

- Databases has its own uploads, chat history, plan, quiz attempts, weak topics, and reminders.
- Machine Learning material does not appear in Databases RAG answers.
- Switching back to Machine Learning restores Machine Learning state.

### 8. Dashboard And Reminders

1. Go to Progress Dashboard.
2. Show course cards for Machine Learning and Databases.
3. Show active-course metrics, uploaded files, quiz average, weak topics, chat summary, and reminders.
4. Click Refresh reminders if needed.
5. Mark one reminder as done.

Expected evidence:

- Dashboard summarizes both courses.
- Active-course panels reflect the selected course.
- Reminder table includes study tasks, quizzes, weak topics, missed tasks, or deadlines.
- Marking a reminder done updates its status.

### 9. Settings And Arabic Localization

1. Go to Settings.
2. Change name, daily study hours, default quiz difficulty, question types, and reminder preferences.
3. Save settings.
4. Use the top language toggle to switch to Arabic.
5. Open Chat, Dashboard, and Settings.

Expected evidence:

- Settings persist locally and sync to memory when configured.
- Arabic UI text appears.
- RTL layout is applied.
- Assistant responses follow Arabic when Arabic is selected or Arabic input is detected.

## Closing Line

"This demo shows Rafeeqak as a complete multi-course study hub: it keeps each course separate, grounds explanations in course material, creates personalized weak-topic plans, tests understanding with mixed quizzes, tracks progress, and reminds students what to do next."

## Recovery Notes

If Gemini is not configured:

- Mention that the Gemini wrapper has offline fallback.
- Continue the demo with deterministic generated answers, quizzes, plans, summaries, and reminders.

If Supabase is not configured:

- Mention that memory sync is optional for the demo.
- Continue with local session and local workspace persistence.

If no quiz can be generated:

- Confirm a course is selected.
- Confirm a file is uploaded and indexed.
- Use the retry button.
- Use one of the demo markdown files because they contain compact, quiz-friendly material.


from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from src.localization import normalize_language, t
from src.prompts import render_prompt
from src.tools.llm_client import LLMClient


class StudyPlannerAgent:
    """Creates schedules and recommends the next study action."""

    DEFAULT_TOPICS = ["Revision", "Practice Questions", "Concept Review"]
    PHASE_LABELS = {
        "recovery": "Recovery session",
        "foundation": "Concept review",
        "deep_practice": "Weak-topic practice",
        "mixed_review": "Mixed review",
        "checkpoint": "Checkpoint quiz",
        "final_review": "Final review",
    }
    CHECKPOINT_CADENCE = {
        "easy": 4,
        "medium": 3,
        "hard": 2,
    }

    def __init__(self, *, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def generate(self, profile: dict[str, Any]) -> dict[str, Any]:
        language = normalize_language(profile.get("language"))
        course_name = str(profile.get("course_name") or "General Revision").strip()
        exam_date = self._coerce_date(profile.get("exam_date"))
        daily_hours = self._coerce_hours(profile.get("daily_hours"))
        difficulty = self._normalize_difficulty(profile.get("difficulty"))

        today = date.today()
        days_until_exam = max((exam_date - today).days, 1)
        progress_snapshot = self._coerce_progress(profile.get("progress"))
        weak_topics = self._merge_topics(
            self._coerce_topics(profile.get("weak_topics")),
            progress_snapshot["quiz_weak_topics"],
        )
        other_topics = self._coerce_topics(profile.get("other_topics"))
        lecture_count = self._coerce_positive_int(
            profile.get("lecture_count"),
            fallback=max(len(weak_topics) + len(other_topics), 1),
            minimum=1,
            maximum=60,
        )
        other_topics = self._complete_other_topics(
            other_topics,
            weak_topics=weak_topics,
            lecture_count=lecture_count,
        )
        finish_period_days = self._coerce_positive_int(
            profile.get("finish_period_days"),
            fallback=min(days_until_exam, max(lecture_count, 1)),
            minimum=1,
            maximum=days_until_exam,
        )

        tasks = self._generate_tasks_with_llm(
            course_name=course_name,
            difficulty=difficulty,
            exam_date=exam_date,
            daily_hours=daily_hours,
            weak_topics=weak_topics,
            other_topics=other_topics,
            lecture_count=lecture_count,
            finish_period_days=finish_period_days,
            progress=self._progress_summary(progress_snapshot),
            days_until_exam=days_until_exam,
            today=today,
            language=language,
        )
        generation_mode = "llm" if tasks else "offline_template"

        if not tasks:
            tasks = self._build_offline_tasks(
                course_name=course_name,
                difficulty=difficulty,
                daily_hours=daily_hours,
                weak_topics=weak_topics,
                other_topics=other_topics,
                lecture_count=lecture_count,
                finish_period_days=finish_period_days,
                progress_snapshot=progress_snapshot,
                days_until_exam=days_until_exam,
                today=today,
            )

        delayed_task_count = progress_snapshot["delayed_task_count"]
        recovery_recommendations = self._recovery_recommendations(
            delayed_task_count=delayed_task_count,
            delayed_task_topics=progress_snapshot["delayed_task_topics"],
            language=language,
        )

        plan = {
            "course_name": course_name,
            "exam_date": exam_date.isoformat(),
            "daily_hours": daily_hours,
            "difficulty": difficulty,
            "lecture_count": lecture_count,
            "finish_period_days": finish_period_days,
            "days_until_exam": days_until_exam,
            "weak_topics": weak_topics,
            "other_topics": other_topics,
            "delayed_task_count": delayed_task_count,
            "recovery_recommendations": recovery_recommendations,
            "progress_snapshot": progress_snapshot,
            "generation_mode": generation_mode,
            "tasks": tasks,
        }

        return {
            "ok": True,
            "plan": plan,
            "exam_date": exam_date,
            "generation_mode": generation_mode,
            "summary": t(
                "planner.summary",
                language,
                count=len(tasks),
                course_name=course_name,
                weak_topics=", ".join(weak_topics) if weak_topics else t("planner.none", language),
            ),
        }

    def _generate_tasks_with_llm(
        self,
        *,
        course_name: str,
        difficulty: str,
        exam_date: date,
        daily_hours: float,
        weak_topics: list[str],
        other_topics: list[str],
        lecture_count: int,
        finish_period_days: int,
        progress: str,
        days_until_exam: int,
        today: date,
        language: str,
    ) -> list[dict[str, Any]]:
        if not self.llm_client.is_available:
            return []

        prompt = render_prompt(
            "study_planning",
            course_name=course_name,
            difficulty=difficulty,
            exam_deadline=exam_date.isoformat(),
            daily_hours=daily_hours,
            lecture_count=lecture_count,
            finish_period=f"{finish_period_days} day(s)",
            progress=(
                f"Today: {today.isoformat()}; planning window: {days_until_exam} day(s); "
                f"other topics: {', '.join(other_topics) if other_topics else 'none'}; {progress}"
            ),
            weak_topics=", ".join(weak_topics) if weak_topics else "none",
            language="Arabic" if language == "ar" else "English",
        )

        try:
            payload = self.llm_client.generate_json(
                system_prompt=prompt.system,
                user_prompt=prompt.user,
                temperature=0.4,
                max_tokens=2000,
            )
        except Exception:
            return []
        if not payload:
            return []

        raw_tasks = payload.get("tasks")
        if not isinstance(raw_tasks, list) or len(raw_tasks) != days_until_exam:
            return []

        tasks = []
        for day_idx, item in enumerate(raw_tasks):
            if not isinstance(item, dict):
                return []
            plan_date = today + timedelta(days=day_idx)
            topic = str(item.get("topic") or "").strip()
            task_text = str(item.get("task") or "").strip()
            phase = str(item.get("phase") or "Personalized study").strip()
            if not topic or not task_text:
                return []
            try:
                hours = float(item.get("hours", daily_hours))
            except (TypeError, ValueError):
                hours = daily_hours
            checkpoint = bool(item.get("checkpoint"))
            tasks.append(
                {
                    "date": plan_date.isoformat(),
                    "course": course_name,
                    "topic": topic,
                    "phase": phase,
                    "hours": round(min(max(hours, 0.5), 12.0), 1),
                    "task": task_text,
                    "checkpoint": checkpoint,
                    "quiz_required": checkpoint,
                    "completed": False,
                }
            )
        return tasks

    def _build_offline_tasks(
        self,
        *,
        course_name: str,
        difficulty: str,
        daily_hours: float,
        weak_topics: list[str],
        other_topics: list[str],
        lecture_count: int,
        finish_period_days: int,
        progress_snapshot: dict[str, Any],
        days_until_exam: int,
        today: date,
    ) -> list[dict[str, Any]]:
        tasks = []
        delayed_topics = progress_snapshot["delayed_task_topics"]
        delayed_recovery_days = min(len(delayed_topics), finish_period_days)
        coverage_days = max(finish_period_days - delayed_recovery_days, 1)
        checkpoint_every = self.CHECKPOINT_CADENCE[difficulty]
        coverage_topics = weak_topics + weak_topics + other_topics
        if not coverage_topics:
            coverage_topics = self.DEFAULT_TOPICS
        review_topics = weak_topics + other_topics
        if not review_topics:
            review_topics = coverage_topics

        coverage_cursor = 0
        review_cursor = 0
        for day_idx in range(days_until_exam):
            plan_date = today + timedelta(days=day_idx)
            days_left = days_until_exam - day_idx
            checkpoint = ((day_idx + 1) % checkpoint_every == 0) or days_left == 1

            if day_idx < delayed_recovery_days:
                topic = delayed_topics[day_idx]
                phase = "recovery"
                task_text = self._recovery_task_text(topic=topic, daily_hours=daily_hours)
            elif day_idx < finish_period_days:
                topic = coverage_topics[coverage_cursor % len(coverage_topics)]
                coverage_cursor += 1
                phase = self._phase_for_day(
                    day_idx=day_idx,
                    days_until_exam=days_until_exam,
                    checkpoint=checkpoint,
                    in_coverage_window=True,
                    is_weak_topic=topic in weak_topics,
                )
                lecture_slot = self._lecture_slot_for_day(
                    coverage_day_idx=day_idx - delayed_recovery_days,
                    lecture_count=lecture_count,
                    coverage_days=coverage_days,
                )
                task_text = self._task_text(
                    topic=topic,
                    phase=phase,
                    daily_hours=daily_hours,
                    is_weak_topic=topic in weak_topics,
                    lecture_slot=lecture_slot,
                    difficulty=difficulty,
                )
            else:
                topic = review_topics[review_cursor % len(review_topics)]
                review_cursor += 1
                phase = self._phase_for_day(
                    day_idx=day_idx,
                    days_until_exam=days_until_exam,
                    checkpoint=checkpoint,
                    in_coverage_window=False,
                    is_weak_topic=topic in weak_topics,
                )
                task_text = self._task_text(
                    topic=topic,
                    phase=phase,
                    daily_hours=daily_hours,
                    is_weak_topic=topic in weak_topics,
                    lecture_slot="",
                    difficulty=difficulty,
                )

            quiz_required = checkpoint if phase != "recovery" else False
            tasks.append(
                {
                    "date": plan_date.isoformat(),
                    "course": course_name,
                    "topic": topic,
                    "phase": self.PHASE_LABELS[phase],
                    "hours": round(self._planned_hours(daily_hours=daily_hours, difficulty=difficulty, phase=phase), 1),
                    "task": task_text,
                    "checkpoint": quiz_required,
                    "quiz_required": quiz_required,
                    "completed": False,
                }
            )
        return tasks

    def _phase_for_day(
        self,
        *,
        day_idx: int,
        days_until_exam: int,
        checkpoint: bool,
        in_coverage_window: bool,
        is_weak_topic: bool,
    ) -> str:
        days_left = days_until_exam - day_idx
        if days_left <= 2:
            return "final_review"
        if checkpoint:
            return "checkpoint"
        if in_coverage_window and is_weak_topic:
            return "deep_practice"
        if in_coverage_window:
            return "foundation"

        progress = day_idx / max(days_until_exam - 1, 1)
        if progress < 0.75:
            return "mixed_review"
        if is_weak_topic:
            return "deep_practice"
        if progress < 0.9:
            return "mixed_review"
        return "final_review"

    def _task_text(
        self,
        *,
        topic: str,
        phase: str,
        daily_hours: float,
        is_weak_topic: bool,
        lecture_slot: str,
        difficulty: str,
    ) -> str:
        weak_note = " Prioritize mistake patterns because this is marked as a weak topic." if is_weak_topic else ""
        if daily_hours <= 1:
            time_note = "Keep this compact: one focused pass and five recall questions."
        elif daily_hours >= 3:
            time_note = "Use the extra time for worked examples, active recall, and a short self-test."
        else:
            time_note = "Split the session between review, practice, and a short written summary."
        lecture_note = f" Cover {lecture_slot} first." if lecture_slot else ""
        difficulty_note = {
            "easy": " Keep the pace light and focus on accuracy.",
            "medium": " Keep the session balanced between explanation and practice.",
            "hard": " Add one timed exam-style question before you finish.",
        }[difficulty]

        phase_actions = {
            "foundation": f"Review the core ideas of {topic}, list key formulas or definitions, and solve one guided example.",
            "deep_practice": f"Practice {topic} with new problems, explain each step aloud, and log any repeated mistakes.",
            "mixed_review": f"Mix {topic} with earlier topics, compare problem types, and write a quick exam-style checklist.",
            "checkpoint": f"Take a checkpoint quiz on {topic}, review wrong answers, and update weak points before moving on.",
            "final_review": f"Do a final review of {topic}, focus on high-yield mistakes, and prepare a one-page recall sheet.",
        }
        return f"{phase_actions[phase]}{lecture_note} {time_note}{difficulty_note}{weak_note}"

    def _recovery_task_text(self, *, topic: str, daily_hours: float) -> str:
        if daily_hours <= 1.5:
            recovery_note = "Use one compact catch-up block and keep the notes minimal."
        else:
            recovery_note = "Recover the missed work first, then close with a short self-test."
        return (
            f"Recover the delayed work for {topic}, write a compressed summary, and reschedule any unfinished sub-parts. "
            f"{recovery_note}"
        )

    def _planned_hours(self, *, daily_hours: float, difficulty: str, phase: str) -> float:
        hours = daily_hours
        if difficulty == "hard":
            hours += 0.25
        elif difficulty == "easy":
            hours -= 0.25
        if phase in {"checkpoint", "final_review"}:
            hours = min(hours + 0.25, 12.0)
        if phase == "recovery":
            hours = max(hours, min(daily_hours + 0.5, 12.0))
        return min(max(hours, 0.5), 12.0)

    def recommend_next(self, active_plan: dict[str, Any] | None) -> dict[str, Any]:
        if not active_plan:
            return {
                "ok": False,
                "response": "I do not have a study plan yet. Open the Study Plan page and generate one first.",
            }

        upcoming_tasks = [task for task in active_plan.get("tasks", []) if not task.get("completed")]
        if not upcoming_tasks:
            return {
                "ok": True,
                "response": "Nice work. You completed all tasks in the current plan. Generate a fresh revision plan.",
            }

        task = upcoming_tasks[0]
        checkpoint_note = " It also includes a checkpoint quiz." if task.get("checkpoint") else ""
        return {
            "ok": True,
            "task": task,
            "response": (
                f"Today focus on {task['topic']} ({task['hours']}h). "
                f"Goal: {task['task']}{checkpoint_note}"
            ),
        }

    def explain_priorities(self, active_plan: dict[str, Any] | None) -> dict[str, Any]:
        if not active_plan:
            return {
                "ok": False,
                "response": "Add weak topics in the Study Plan page, then I can prioritize them in your schedule.",
            }

        weak_topics = active_plan.get("weak_topics", [])
        if not weak_topics:
            return {
                "ok": True,
                "response": "Your current plan has no weak topics marked, so it rotates revision topics evenly.",
            }

        return {
            "ok": True,
            "response": (
                "Your current plan gives extra turns to weak topics before regular revision topics. "
                f"Priority topics: {', '.join(weak_topics)}."
            ),
        }

    def _coerce_date(self, value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str) and value:
            return date.fromisoformat(value)
        return date.today() + timedelta(days=10)

    def _coerce_hours(self, value: Any) -> float:
        try:
            hours = float(value)
        except (TypeError, ValueError):
            hours = 2.0
        return min(max(hours, 0.5), 12.0)

    def _coerce_topics(self, value: Any) -> list[str]:
        if value is None:
            return []
        raw_topics = value.split(",") if isinstance(value, str) else value
        return [str(topic).strip() for topic in raw_topics if str(topic).strip()]

    def _coerce_positive_int(
        self,
        value: Any,
        *,
        fallback: int,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = fallback
        return min(max(parsed, minimum), maximum)

    def _normalize_difficulty(self, value: Any) -> str:
        normalized = str(value or "medium").strip().lower()
        if normalized in {"easy", "medium", "hard"}:
            return normalized
        return "medium"

    def _merge_topics(self, *topic_lists: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for topics in topic_lists:
            for topic in topics:
                normalized = topic.casefold()
                if normalized in seen:
                    continue
                seen.add(normalized)
                merged.append(topic)
        return merged

    def _complete_other_topics(self, topics: list[str], *, weak_topics: list[str], lecture_count: int) -> list[str]:
        completed = list(topics)
        existing_names = {topic.casefold() for topic in weak_topics + topics}
        lecture_number = 1
        while len(completed) < lecture_count:
            lecture_topic = f"Lecture {lecture_number}"
            lecture_number += 1
            if lecture_topic.casefold() in existing_names:
                continue
            existing_names.add(lecture_topic.casefold())
            completed.append(lecture_topic)
        return completed

    def _coerce_progress(self, value: Any) -> dict[str, Any]:
        progress = value if isinstance(value, dict) else {}
        delayed_task_topics = self._merge_topics(
            self._coerce_topics(progress.get("delayed_task_topics")),
            [
                str(task.get("topic")).strip()
                for task in progress.get("overdue_tasks", [])
                if isinstance(task, dict) and str(task.get("topic", "")).strip()
            ],
        )
        completed_tasks = self._coerce_positive_int(
            progress.get("completed_tasks"),
            fallback=0,
            minimum=0,
            maximum=1000,
        )
        total_tasks = self._coerce_positive_int(
            progress.get("total_tasks"),
            fallback=max(completed_tasks, 0),
            minimum=0,
            maximum=1000,
        )
        completion_rate = round((completed_tasks / total_tasks) * 100, 1) if total_tasks else 0.0
        try:
            average_score = float(progress.get("average_score", 0.0))
        except (TypeError, ValueError):
            average_score = 0.0
        return {
            "completed_tasks": completed_tasks,
            "total_tasks": total_tasks,
            "completion_rate": completion_rate,
            "delayed_task_topics": delayed_task_topics,
            "delayed_task_count": len(delayed_task_topics),
            "quiz_attempts": self._coerce_positive_int(
                progress.get("quiz_attempts"),
                fallback=0,
                minimum=0,
                maximum=1000,
            ),
            "average_score": round(min(max(average_score, 0.0), 100.0), 1),
            "quiz_weak_topics": self._coerce_topics(progress.get("quiz_weak_topics")),
        }

    def _progress_summary(self, progress_snapshot: dict[str, Any]) -> str:
        return (
            f"Completed tasks: {progress_snapshot['completed_tasks']}/{progress_snapshot['total_tasks']} "
            f"({progress_snapshot['completion_rate']}%). "
            f"Delayed tasks: {progress_snapshot['delayed_task_count']}. "
            f"Quiz attempts: {progress_snapshot['quiz_attempts']}. "
            f"Average quiz score: {progress_snapshot['average_score']}%. "
            f"Quiz weak topics: {', '.join(progress_snapshot['quiz_weak_topics']) or 'none'}."
        )

    def _lecture_slot_for_day(self, *, coverage_day_idx: int, lecture_count: int, coverage_days: int) -> str:
        if lecture_count <= 0 or coverage_days <= 0 or coverage_day_idx >= coverage_days:
            return ""
        base = lecture_count // coverage_days
        extra = lecture_count % coverage_days
        lecture_span = base + (1 if coverage_day_idx < extra else 0)
        if lecture_span <= 0:
            return ""
        start = 1 + (coverage_day_idx * base) + min(coverage_day_idx, extra)
        end = start + lecture_span - 1
        if start == end:
            return f"Lecture {start}"
        return f"Lectures {start}-{end}"

    def _recovery_recommendations(
        self,
        *,
        delayed_task_count: int,
        delayed_task_topics: list[str],
        language: str,
    ) -> list[str]:
        if delayed_task_count == 0:
            return []
        focus = delayed_task_topics[0] if delayed_task_topics else ("this course" if language != "ar" else "هذا المقرر")
        if language == "ar":
            return [
                f"ابدأ بتعويض أقدم مهمة متأخرة في {focus} قبل إضافة عبء جديد.",
                "إذا كان الوقت ضيقا، قلل الموضوعات الجديدة في أول يومين بدل تكديسها.",
                "بعد كل جلسة تعويض، أنه الاختبار الذاتي القصير للتأكد من أن التأخير لم يترك فجوة.",
            ]
        return [
            f"Start by recovering the oldest delayed task in {focus} before adding new load.",
            "If time is tight, reduce new-topic volume for the first two days instead of stacking work.",
            "Finish each recovery block with a short self-test so the backlog does not reopen later.",
        ]

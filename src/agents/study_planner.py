from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from src.localization import normalize_language, t
from src.tools.llm_client import LLMClient


class StudyPlannerAgent:
    """Creates schedules and recommends the next study action."""

    DEFAULT_TOPICS = ["Revision", "Practice Questions", "Concept Review"]
    PHASE_LABELS = {
        "foundation": "Concept review",
        "deep_practice": "Weak-topic practice",
        "mixed_review": "Mixed review",
        "checkpoint": "Checkpoint quiz",
        "final_review": "Final review",
    }

    def __init__(self, *, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def generate(self, profile: dict[str, Any]) -> dict[str, Any]:
        language = normalize_language(profile.get("language"))
        course_name = str(profile.get("course_name") or "General Revision").strip()
        exam_date = self._coerce_date(profile.get("exam_date"))
        daily_hours = self._coerce_hours(profile.get("daily_hours"))
        weak_topics = self._coerce_topics(profile.get("weak_topics"))
        other_topics = self._coerce_topics(profile.get("other_topics"))

        today = date.today()
        days_until_exam = max((exam_date - today).days, 1)
        priority_topics = weak_topics + weak_topics + other_topics
        if not priority_topics:
            priority_topics = self.DEFAULT_TOPICS

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

        if not tasks:
            tasks = []
            for day_idx in range(days_until_exam):
                plan_date = today + timedelta(days=day_idx)
                topic = priority_topics[day_idx % len(priority_topics)]
                days_left = days_until_exam - day_idx
                checkpoint = (day_idx + 1) % 3 == 0 or days_left == 1
                phase = self._phase_for_day(day_idx=day_idx, days_until_exam=days_until_exam, checkpoint=checkpoint)
                task_text = self._task_text(
                    topic=topic,
                    phase=phase,
                    daily_hours=daily_hours,
                    is_weak_topic=topic in weak_topics,
                )

                tasks.append(
                    {
                        "date": plan_date.isoformat(),
                        "course": course_name,
                        "topic": topic,
                        "phase": self.PHASE_LABELS[phase],
                        "hours": round(daily_hours, 1),
                        "task": task_text,
                        "checkpoint": checkpoint,
                        "completed": False,
                    }
                )

        plan = {
            "course_name": course_name,
            "exam_date": exam_date.isoformat(),
            "daily_hours": daily_hours,
            "weak_topics": weak_topics,
            "other_topics": other_topics,
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
        exam_date: date,
        daily_hours: float,
        weak_topics: list[str],
        other_topics: list[str],
        days_until_exam: int,
        today: date,
    ) -> list[dict[str, Any]]:
        if not self.llm_client.is_available:
            return []

        system_prompt = (
            "You create practical exam study plans. Return only valid JSON with this shape: "
            '{"tasks":[{"date":"YYYY-MM-DD","topic":"...","phase":"...",'
            '"hours":2.0,"task":"...","checkpoint":false}]}. '
            "Make tasks specific, varied, and personalized. Use exactly the requested number of tasks."
        )
        user_prompt = (
            f"Course: {course_name}\n"
            f"Today: {today.isoformat()}\n"
            f"Exam date: {exam_date.isoformat()}\n"
            f"Number of daily tasks: {days_until_exam}\n"
            f"Available hours per day: {daily_hours}\n"
            f"Weak topics: {', '.join(weak_topics) if weak_topics else 'none'}\n"
            f"Other topics: {', '.join(other_topics) if other_topics else 'none'}\n\n"
            "Use weak topics more often than regular topics. Include checkpoint quiz days and final review."
        )

        try:
            payload = self.llm_client.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
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
            tasks.append(
                {
                    "date": plan_date.isoformat(),
                    "course": course_name,
                    "topic": topic,
                    "phase": phase,
                    "hours": round(min(max(hours, 0.5), 12.0), 1),
                    "task": task_text,
                    "checkpoint": bool(item.get("checkpoint")),
                    "completed": False,
                }
            )
        return tasks

    def _phase_for_day(self, *, day_idx: int, days_until_exam: int, checkpoint: bool) -> str:
        days_left = days_until_exam - day_idx
        if days_left <= 2:
            return "final_review"
        if checkpoint:
            return "checkpoint"

        progress = day_idx / max(days_until_exam - 1, 1)
        if progress < 0.35:
            return "foundation"
        if progress < 0.75:
            return "deep_practice"
        return "mixed_review"

    def _task_text(self, *, topic: str, phase: str, daily_hours: float, is_weak_topic: bool) -> str:
        weak_note = " Prioritize mistake patterns because this is marked as a weak topic." if is_weak_topic else ""
        if daily_hours <= 1:
            time_note = "Keep this compact: one focused pass and five recall questions."
        elif daily_hours >= 3:
            time_note = "Use the extra time for worked examples, active recall, and a short self-test."
        else:
            time_note = "Split the session between review, practice, and a short written summary."

        phase_actions = {
            "foundation": f"Review the core ideas of {topic}, list key formulas or definitions, and solve one guided example.",
            "deep_practice": f"Practice {topic} with new problems, explain each step aloud, and log any repeated mistakes.",
            "mixed_review": f"Mix {topic} with earlier topics, compare problem types, and write a quick exam-style checklist.",
            "checkpoint": f"Take a checkpoint quiz on {topic}, review wrong answers, and update weak points before moving on.",
            "final_review": f"Do a final review of {topic}, focus on high-yield mistakes, and prepare a one-page recall sheet.",
        }
        return f"{phase_actions[phase]} {time_note}{weak_note}"

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

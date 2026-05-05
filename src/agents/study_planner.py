from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


class StudyPlannerAgent:
    """Creates schedules and recommends the next study action."""

    DEFAULT_TOPICS = ["Revision", "Practice Questions", "Concept Review"]

    def generate(self, profile: dict[str, Any]) -> dict[str, Any]:
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

        tasks = []
        for day_idx in range(days_until_exam):
            plan_date = today + timedelta(days=day_idx)
            topic = priority_topics[day_idx % len(priority_topics)]
            checkpoint = (day_idx + 1) % 3 == 0
            task_text = f"Study {topic} and write a short summary."
            if checkpoint:
                task_text = f"{task_text} Then complete a checkpoint quiz."

            tasks.append(
                {
                    "date": plan_date.isoformat(),
                    "course": course_name,
                    "topic": topic,
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
            "tasks": tasks,
        }

        return {
            "ok": True,
            "plan": plan,
            "exam_date": exam_date,
            "summary": (
                f"Created {len(tasks)} study task(s) for {course_name}. "
                f"Weak topics are prioritized first: {', '.join(weak_topics) if weak_topics else 'none'}."
            ),
        }

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

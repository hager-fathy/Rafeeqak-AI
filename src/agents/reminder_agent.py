from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time, timedelta
from typing import Any

from src.localization import normalize_language, t


class ReminderAgent:
    """Creates course-scoped study reminders from plans, deadlines, and weak topics."""

    EXPLICIT_REMINDER_PATTERNS = (
        r"remind me to\s+(.+)",
        r"reminder to\s+(.+)",
        r"notify me to\s+(.+)",
    )
    ARABIC_EXPLICIT_REMINDER_PATTERNS = (
        r"\u0630\u0643\u0631\u0646\u064a\s+(.+)",
        r"\u0646\u0628\u0647\u0646\u064a\s+(.+)",
    )
    DEFAULT_REMINDER_TYPES = ["lecture", "revision", "quiz", "missed_task", "deadline", "study_task", "custom"]

    def create(self, *, message: str, context: dict[str, Any], language: str = "en") -> dict[str, Any]:
        language = normalize_language(language)
        course_id = context.get("active_course_id")
        course_name = context.get("active_course_name")
        active_plan = context.get("active_plan") or {}
        existing_reminders = context.get("reminders", []) or []
        preferences = self._preferences(context.get("reminder_preferences"))
        allowed_types = set(preferences["types"])

        if not preferences["enabled"]:
            return {
                "ok": True,
                "status": "disabled",
                "created_count": 0,
                "reminders": existing_reminders,
                "new_reminders": [],
                "response": t("reminder.disabled", language),
            }

        candidates = []
        explicit = self._explicit_reminder(message, language=language)
        if explicit:
            candidates.extend(
                self._allowed(
                    [
                        self._reminder(
                            course_id=course_id,
                            course_name=course_name,
                            reminder_type="custom",
                            title=explicit,
                            due_at=self._infer_due_at(message, preferences=preferences),
                            source="chat_request",
                            language=language,
                        )
                    ],
                    allowed_types=allowed_types,
                )
            )

        if isinstance(active_plan, dict):
            candidates.extend(
                self._plan_reminders(
                    active_plan=active_plan,
                    course_id=course_id,
                    course_name=course_name,
                    language=language,
                    preferences=preferences,
                    allowed_types=allowed_types,
                )
            )

        weak_topics = self._weak_topics(context=context, active_plan=active_plan)
        for topic in weak_topics[:2]:
            candidates.extend(
                self._allowed(
                    [
                        self._reminder(
                            course_id=course_id,
                            course_name=course_name,
                            reminder_type="quiz",
                            title=t("reminder.title.weak_quiz", language, topic=topic),
                            due_at=self._combine_date_time(
                                date.today() + timedelta(days=1),
                                self._preferred_time(preferences),
                            ),
                            source="weak_topic",
                            language=language,
                            topic=topic,
                        )
                    ],
                    allowed_types=allowed_types,
                )
            )

        reminders, new_reminders = self._merge_reminders(existing_reminders=existing_reminders, candidates=candidates)
        return {
            "ok": True,
            "status": "created" if reminders else "empty",
            "created_count": len(new_reminders),
            "reminders": reminders,
            "new_reminders": new_reminders,
            "response": self._response(reminders=reminders, created_count=len(new_reminders), language=language),
        }

    def _plan_reminders(
        self,
        *,
        active_plan: dict[str, Any],
        course_id: str | None,
        course_name: str | None,
        language: str,
        preferences: dict[str, Any],
        allowed_types: set[str],
    ) -> list[dict[str, Any]]:
        reminders = []
        today = date.today()
        preferred_time = self._preferred_time(preferences)
        tasks = active_plan.get("tasks", []) if isinstance(active_plan.get("tasks"), list) else []
        upcoming_tasks = []
        missed_tasks = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            from src.tools.study_plan_tasks import is_task_completed

            if is_task_completed(task, active_plan):
                continue
            task_date = self._parse_date(task.get("date"))
            if task_date is None:
                continue
            if task_date < today:
                missed_tasks.append((task_date, task))
            else:
                upcoming_tasks.append((task_date, task))

        for task_date, task in sorted(upcoming_tasks, key=lambda item: item[0])[:3]:
            reminder_type = self._task_reminder_type(task)
            reminders.extend(
                self._allowed(
                    [
                        self._reminder(
                            course_id=course_id,
                            course_name=course_name,
                            reminder_type=reminder_type,
                            title=self._task_title(reminder_type=reminder_type, task=task, language=language),
                            due_at=self._lead_due_at(task_date, preferences=preferences, preferred_time=preferred_time),
                            source="active_plan",
                            language=language,
                            topic=task.get("topic"),
                        )
                    ],
                    allowed_types=allowed_types,
                )
            )
            if task.get("checkpoint"):
                reminders.extend(
                    self._allowed(
                        [
                            self._reminder(
                                course_id=course_id,
                                course_name=course_name,
                                reminder_type="quiz",
                                title=t("reminder.title.checkpoint", language, topic=task.get("topic", "Revision")),
                                due_at=self._combine_date_time(task_date, time(17, 0)),
                                source="active_plan_checkpoint",
                                language=language,
                                topic=task.get("topic"),
                            )
                        ],
                        allowed_types=allowed_types,
                    )
                )

        for task_date, task in sorted(missed_tasks, key=lambda item: item[0])[:2]:
            reminders.extend(
                self._allowed(
                    [
                        self._reminder(
                            course_id=course_id,
                            course_name=course_name,
                            reminder_type="missed_task",
                            title=t("reminder.title.missed_task", language, topic=task.get("topic", "Revision")),
                            due_at=self._combine_date_time(today, preferred_time),
                            source="delayed_task",
                            language=language,
                            topic=task.get("topic"),
                            original_due_date=task_date.isoformat(),
                        )
                    ],
                    allowed_types=allowed_types,
                )
            )

        exam_date = self._parse_date(active_plan.get("exam_date"))
        if exam_date and exam_date >= today:
            reminder_date = max(today, exam_date - timedelta(days=max(3, preferences["lead_days"])))
            reminders.extend(
                self._allowed(
                    [
                        self._reminder(
                            course_id=course_id,
                            course_name=course_name,
                            reminder_type="deadline",
                            title=t(
                                "reminder.title.exam",
                                language,
                                course=course_name or active_plan.get("course_name", "course"),
                            ),
                            due_at=self._combine_date_time(reminder_date, time(10, 0)),
                            source="exam_deadline",
                            language=language,
                        )
                    ],
                    allowed_types=allowed_types,
                )
            )
        return reminders

    def _explicit_reminder(self, message: str, *, language: str) -> str | None:
        patterns = self.ARABIC_EXPLICIT_REMINDER_PATTERNS if language == "ar" else self.EXPLICIT_REMINDER_PATTERNS
        for pattern in patterns:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                title = " ".join(match.group(1).strip(" .?!\u061f").split())
                return title[:120] if title else None
        return None

    def _infer_due_at(self, message: str, *, preferences: dict[str, Any]) -> str:
        lowered = message.casefold()
        if "tomorrow" in lowered or "\u0628\u0643\u0631\u0629" in lowered or "\u063a\u062f\u0627" in lowered:
            due_date = date.today() + timedelta(days=1)
        elif "next week" in lowered or "\u0627\u0644\u0623\u0633\u0628\u0648\u0639" in lowered:
            due_date = date.today() + timedelta(days=7)
        else:
            due_date = date.today()
        return self._combine_date_time(due_date, self._preferred_time(preferences))

    def _weak_topics(self, *, context: dict[str, Any], active_plan: dict[str, Any]) -> list[str]:
        topics = []
        if isinstance(active_plan, dict):
            topics.extend(active_plan.get("weak_topics", []) or [])
        for attempt in context.get("quiz_attempts", []) or []:
            topics.extend(attempt.get("weak_topics", []) or [])

        unique_topics = []
        for topic in topics:
            topic_text = str(topic).strip()
            if topic_text and topic_text not in unique_topics:
                unique_topics.append(topic_text)
        return unique_topics

    def _merge_reminders(
        self,
        *,
        existing_reminders: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        reminders = [item for item in existing_reminders if isinstance(item, dict)]
        existing_ids = {item.get("reminder_id") for item in reminders}
        new_reminders = []
        for candidate in candidates:
            if candidate["reminder_id"] in existing_ids:
                continue
            reminders.append(candidate)
            new_reminders.append(candidate)
            existing_ids.add(candidate["reminder_id"])
        return (
            sorted(reminders, key=lambda item: (item.get("status") == "done", item.get("due_at") or "")),
            new_reminders,
        )

    def _reminder(
        self,
        *,
        course_id: str | None,
        course_name: str | None,
        reminder_type: str,
        title: str,
        due_at: str,
        source: str,
        language: str,
        topic: Any = None,
        original_due_date: str | None = None,
    ) -> dict[str, Any]:
        created_at = datetime.utcnow().isoformat(timespec="seconds")
        fingerprint = "|".join(
            [
                str(course_id or ""),
                reminder_type,
                title.casefold(),
                due_at[:10],
                str(topic or ""),
            ]
        )
        reminder_id = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]
        reminder = {
            "reminder_id": reminder_id,
            "course_id": course_id,
            "course_name": course_name,
            "reminder_type": reminder_type,
            "title": title,
            "due_at": due_at,
            "status": "pending",
            "source": source,
            "language": language,
            "created_at_utc": created_at,
        }
        if topic:
            reminder["topic"] = str(topic)
        if original_due_date:
            reminder["original_due_date"] = original_due_date
        return reminder

    def _response(self, *, reminders: list[dict[str, Any]], created_count: int, language: str) -> str:
        if not reminders:
            return t("reminder.none", language)
        next_reminder = reminders[0]
        return t(
            "reminder.created",
            language,
            count=created_count,
            title=next_reminder["title"],
            due_at=next_reminder["due_at"],
        )

    def _parse_date(self, value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str) and value:
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
        return None

    def _combine_date_time(self, due_date: date, due_time: time) -> str:
        return datetime.combine(due_date, due_time).isoformat(timespec="minutes")

    def _preferences(self, value: Any) -> dict[str, Any]:
        preferences = value if isinstance(value, dict) else {}
        try:
            lead_days = int(preferences.get("lead_days", 1))
        except (TypeError, ValueError):
            lead_days = 1
        raw_types = preferences.get("types")
        if not isinstance(raw_types, list):
            raw_types = self.DEFAULT_REMINDER_TYPES
        reminder_types = [str(item).strip().lower() for item in raw_types if str(item).strip()]
        return {
            "enabled": bool(preferences.get("enabled", True)),
            "lead_days": min(max(lead_days, 0), 14),
            "reminder_time": str(preferences.get("reminder_time") or "18:00"),
            "types": reminder_types or list(self.DEFAULT_REMINDER_TYPES),
        }

    def _preferred_time(self, preferences: dict[str, Any]) -> time:
        raw_time = str(preferences.get("reminder_time") or "18:00").strip()
        try:
            hour, minute = raw_time.split(":", 1)
            return time(min(max(int(hour), 0), 23), min(max(int(minute), 0), 59))
        except (ValueError, TypeError):
            return time(18, 0)

    def _lead_due_at(self, task_date: date, *, preferences: dict[str, Any], preferred_time: time) -> str:
        due_date = max(date.today(), task_date - timedelta(days=preferences["lead_days"]))
        return self._combine_date_time(due_date, preferred_time)

    def _task_reminder_type(self, task: dict[str, Any]) -> str:
        phase = str(task.get("phase") or "").casefold()
        details = str(task.get("task") or "").casefold()
        topic = str(task.get("topic") or "").casefold()
        if "lecture" in details or topic.startswith("lecture"):
            return "lecture"
        if "final review" in phase or "mixed review" in phase or "revision" in details:
            return "revision"
        return "study_task"

    def _task_title(self, *, reminder_type: str, task: dict[str, Any], language: str) -> str:
        topic = task.get("topic", "Revision")
        if reminder_type == "lecture":
            return t("reminder.title.lecture", language, topic=topic)
        if reminder_type == "revision":
            return t("reminder.title.revision", language, topic=topic)
        return t("reminder.title.study_task", language, topic=topic)

    def _allowed(self, reminders: list[dict[str, Any]], *, allowed_types: set[str]) -> list[dict[str, Any]]:
        return [reminder for reminder in reminders if reminder.get("reminder_type") in allowed_types]

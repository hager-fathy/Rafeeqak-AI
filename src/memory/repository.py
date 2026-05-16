from __future__ import annotations

from datetime import date, datetime
from typing import Any

from src.memory.supabase_client import get_supabase_client, get_supabase_settings


class MemoryRepositoryError(RuntimeError):
    """Raised when Supabase database operations fail."""


class SupabaseMemoryRepository:
    def __init__(self) -> None:
        self.client = get_supabase_client()
        self.settings = get_supabase_settings()

    @property
    def is_available(self) -> bool:
        return self.client is not None and self.settings.is_configured

    @property
    def unavailability_reason(self) -> str:
        if not self.settings.is_configured:
            return "SUPABASE_URL or SUPABASE_KEY is missing."
        if self.client is None:
            return "Supabase client is not available. Check installation and environment variables."
        return ""

    def create_or_get_student_profile(
        self,
        *,
        email: str | None = None,
        full_name: str | None = None,
        preferred_language: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_available()

        student_email = email or self.settings.default_student_email
        student_name = full_name or self.settings.default_student_name

        payload = {
            "email": student_email,
            "full_name": student_name,
        }
        if preferred_language:
            payload["preferred_language"] = preferred_language

        try:
            self.client.table("student_profiles").upsert(payload, on_conflict="email").execute()
            response = (
                self.client.table("student_profiles")
                .select("*")
                .eq("email", student_email)
                .maybe_single()
                .execute()
            )
            if not response.data:
                raise MemoryRepositoryError("Could not read back student profile.")
            return response.data
        except Exception as exc:  # pragma: no cover - depends on external DB
            raise MemoryRepositoryError(f"Failed to create/load student profile: {exc}") from exc

    def update_preferred_language(
        self,
        *,
        email: str | None = None,
        full_name: str | None = None,
        preferred_language: str,
    ) -> dict[str, Any]:
        self._ensure_available()

        try:
            return self.create_or_get_student_profile(
                email=email,
                full_name=full_name,
                preferred_language=preferred_language,
            )
        except MemoryRepositoryError:
            raise
        except Exception as exc:  # pragma: no cover - depends on external DB
            raise MemoryRepositoryError(f"Failed to update preferred language: {exc}") from exc

    def upsert_course(
        self,
        *,
        student_id: str,
        course_name: str,
        syllabus_topics: list[str] | None = None,
    ) -> dict[str, Any]:
        self._ensure_available()

        payload = {
            "student_id": student_id,
            "name": course_name,
            "syllabus_topics": syllabus_topics or [],
        }

        try:
            self.client.table("courses").upsert(payload, on_conflict="student_id,name").execute()
            response = (
                self.client.table("courses")
                .select("*")
                .eq("student_id", student_id)
                .eq("name", course_name)
                .maybe_single()
                .execute()
            )
            if not response.data:
                raise MemoryRepositoryError("Could not read back course row.")
            return response.data
        except Exception as exc:  # pragma: no cover - depends on external DB
            raise MemoryRepositoryError(f"Failed to upsert course: {exc}") from exc

    def upsert_exam(
        self,
        *,
        student_id: str,
        course_id: str,
        exam_date: date,
        target_score: int | None = None,
    ) -> dict[str, Any]:
        self._ensure_available()

        payload = {
            "student_id": student_id,
            "course_id": course_id,
            "exam_date": exam_date.isoformat(),
            "target_score": target_score,
        }

        try:
            self.client.table("exams").upsert(payload, on_conflict="student_id,course_id").execute()
            response = (
                self.client.table("exams")
                .select("*")
                .eq("student_id", student_id)
                .eq("course_id", course_id)
                .maybe_single()
                .execute()
            )
            if not response.data:
                raise MemoryRepositoryError("Could not read back exam row.")
            return response.data
        except Exception as exc:  # pragma: no cover - depends on external DB
            raise MemoryRepositoryError(f"Failed to upsert exam: {exc}") from exc

    def replace_study_tasks(
        self,
        *,
        student_id: str,
        course_id: str,
        tasks: list[dict[str, Any]],
        exam_id: str | None = None,
    ) -> int:
        self._ensure_available()

        try:
            self.client.table("study_tasks").delete().eq("student_id", student_id).eq("course_id", course_id).execute()

            if not tasks:
                return 0

            payload_rows = []
            for task in tasks:
                payload_rows.append(
                    {
                        "student_id": student_id,
                        "course_id": course_id,
                        "exam_id": exam_id,
                        "task_date": task["date"],
                        "topic": task["topic"],
                        "details": task["task"],
                        "hours": float(task["hours"]),
                        "checkpoint": bool(task["checkpoint"]),
                        "completed": bool(task["completed"]),
                    }
                )

            self.client.table("study_tasks").insert(payload_rows).execute()
            return len(payload_rows)
        except Exception as exc:  # pragma: no cover - depends on external DB
            raise MemoryRepositoryError(f"Failed to replace study tasks: {exc}") from exc

    def record_quiz_score(
        self,
        *,
        student_id: str,
        course_id: str | None,
        topic: str,
        correct: int,
        total: int,
        score_percent: float,
    ) -> None:
        self._ensure_available()

        payload = {
            "student_id": student_id,
            "course_id": course_id,
            "topic": topic,
            "correct": correct,
            "total": total,
            "score_percent": score_percent,
            "attempted_at": datetime.utcnow().isoformat(timespec="seconds"),
        }

        try:
            self.client.table("quiz_scores").insert(payload).execute()
        except Exception as exc:  # pragma: no cover - depends on external DB
            raise MemoryRepositoryError(f"Failed to record quiz score: {exc}") from exc

    def upsert_weak_topic(
        self,
        *,
        student_id: str,
        course_id: str | None,
        topic: str,
        severity_score: float,
        source: str = "manual",
    ) -> None:
        self._ensure_available()

        payload = {
            "student_id": student_id,
            "course_id": course_id,
            "topic": topic,
            "severity_score": severity_score,
            "source": source,
            "last_seen_at": datetime.utcnow().isoformat(timespec="seconds"),
        }

        try:
            self.client.table("weak_topics").upsert(payload, on_conflict="student_id,course_id,topic").execute()
        except Exception as exc:  # pragma: no cover - depends on external DB
            raise MemoryRepositoryError(f"Failed to upsert weak topic: {exc}") from exc

    def upsert_chat_summary(
        self,
        *,
        student_id: str,
        course_id: str | None,
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        self._ensure_available()

        payload = {
            "student_id": student_id,
            "course_id": course_id,
            "session_key": str(summary.get("summary_id") or "active_session"),
            "language": summary.get("language") or "en",
            "message_count": int(summary.get("message_count") or 0),
            "main_topics": summary.get("main_topics") or [],
            "weaknesses": summary.get("weaknesses") or [],
            "next_steps": summary.get("next_steps") or [],
            "summary": summary.get("summary") or "",
            "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
        }

        try:
            result = self.client.table("chat_session_summaries").upsert(
                payload,
                on_conflict="student_id,course_id,session_key",
            ).execute()
            if not result.data:
                raise MemoryRepositoryError("Could not read back chat summary row.")
            return result.data[0] if isinstance(result.data, list) else result.data
        except Exception as exc:  # pragma: no cover - depends on external DB
            raise MemoryRepositoryError(f"Failed to upsert chat summary: {exc}") from exc

    def fetch_student_snapshot(self, *, student_id: str) -> dict[str, Any]:
        self._ensure_available()

        try:
            profile = (
                self.client.table("student_profiles")
                .select("*")
                .eq("id", student_id)
                .maybe_single()
                .execute()
                .data
            )
            courses = self.client.table("courses").select("*").eq("student_id", student_id).execute().data or []
            exams = self.client.table("exams").select("*").eq("student_id", student_id).execute().data or []
            weak_topics = (
                self.client.table("weak_topics")
                .select("*")
                .eq("student_id", student_id)
                .order("severity_score", desc=True)
                .limit(10)
                .execute()
                .data
                or []
            )
            recent_quizzes = (
                self.client.table("quiz_scores")
                .select("*")
                .eq("student_id", student_id)
                .order("attempted_at", desc=True)
                .limit(10)
                .execute()
                .data
                or []
            )
            chat_summaries = (
                self.client.table("chat_session_summaries")
                .select("*")
                .eq("student_id", student_id)
                .order("updated_at", desc=True)
                .limit(10)
                .execute()
                .data
                or []
            )
            return {
                "profile": profile,
                "courses": courses,
                "exams": exams,
                "weak_topics": weak_topics,
                "recent_quizzes": recent_quizzes,
                "chat_summaries": chat_summaries,
            }
        except Exception as exc:  # pragma: no cover - depends on external DB
            raise MemoryRepositoryError(f"Failed to fetch student snapshot: {exc}") from exc

    def _ensure_available(self) -> None:
        if not self.is_available:
            raise MemoryRepositoryError(self.unavailability_reason)

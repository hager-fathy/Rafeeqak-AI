from __future__ import annotations

from datetime import date
from typing import Any

from src.memory import MemoryRepositoryError, SupabaseMemoryRepository


class MemoryAgent:
    """Phase 3 Supabase-backed memory manager."""

    def __init__(self) -> None:
        self.repository = SupabaseMemoryRepository()
        self._student_id: str | None = None

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.repository.is_available,
            "reason": "" if self.repository.is_available else self.repository.unavailability_reason,
        }

    def sync_study_plan(
        self,
        *,
        course_name: str,
        exam_date: date,
        daily_hours: float,
        weak_topics: list[str],
        other_topics: list[str],
        tasks: list[dict[str, Any]],
        student_email: str | None = None,
        student_name: str | None = None,
    ) -> dict[str, Any]:
        if not self.repository.is_available:
            return {"ok": False, "reason": self.repository.unavailability_reason}

        try:
            profile = self._ensure_student_profile(email=student_email, full_name=student_name)
            student_id = profile["id"]

            course = self.repository.upsert_course(
                student_id=student_id,
                course_name=course_name,
                syllabus_topics=weak_topics + other_topics,
            )
            exam = self.repository.upsert_exam(
                student_id=student_id,
                course_id=course["id"],
                exam_date=exam_date,
            )
            task_count = self.repository.replace_study_tasks(
                student_id=student_id,
                course_id=course["id"],
                exam_id=exam["id"],
                tasks=tasks,
            )

            for topic in weak_topics:
                self.repository.upsert_weak_topic(
                    student_id=student_id,
                    course_id=course["id"],
                    topic=topic,
                    severity_score=0.85,
                    source="plan",
                )

            return {
                "ok": True,
                "student_id": student_id,
                "course_id": course["id"],
                "exam_id": exam["id"],
                "saved_tasks": task_count,
                "daily_hours": daily_hours,
            }
        except MemoryRepositoryError as exc:
            return {"ok": False, "reason": str(exc)}

    def record_quiz_attempt(
        self,
        *,
        course_name: str | None,
        topic: str,
        correct: int,
        total: int,
        score_percent: float,
        student_email: str | None = None,
        student_name: str | None = None,
    ) -> dict[str, Any]:
        if not self.repository.is_available:
            return {"ok": False, "reason": self.repository.unavailability_reason}

        try:
            profile = self._ensure_student_profile(email=student_email, full_name=student_name)
            student_id = profile["id"]

            course_id: str | None = None
            if course_name:
                course = self.repository.upsert_course(student_id=student_id, course_name=course_name, syllabus_topics=[])
                course_id = course["id"]

            self.repository.record_quiz_score(
                student_id=student_id,
                course_id=course_id,
                topic=topic,
                correct=correct,
                total=total,
                score_percent=score_percent,
            )

            if score_percent < 70:
                severity = round(max(0.5, 1 - (score_percent / 100.0)), 2)
                self.repository.upsert_weak_topic(
                    student_id=student_id,
                    course_id=course_id,
                    topic=topic,
                    severity_score=severity,
                    source="quiz",
                )

            return {"ok": True, "student_id": student_id, "course_id": course_id}
        except MemoryRepositoryError as exc:
            return {"ok": False, "reason": str(exc)}

    def get_snapshot(
        self,
        *,
        student_email: str | None = None,
        student_name: str | None = None,
    ) -> dict[str, Any]:
        if not self.repository.is_available:
            return {"ok": False, "reason": self.repository.unavailability_reason}

        try:
            profile = self._ensure_student_profile(email=student_email, full_name=student_name)
            snapshot = self.repository.fetch_student_snapshot(student_id=profile["id"])
            return {"ok": True, "snapshot": snapshot}
        except MemoryRepositoryError as exc:
            return {"ok": False, "reason": str(exc)}

    def _ensure_student_profile(
        self,
        *,
        email: str | None = None,
        full_name: str | None = None,
    ) -> dict[str, Any]:
        profile = self.repository.create_or_get_student_profile(email=email, full_name=full_name)
        self._student_id = profile["id"]
        return profile

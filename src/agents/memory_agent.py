from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from src.memory import MemoryRepositoryError, SupabaseMemoryRepository
from src.localization import normalize_language
from src.prompts import render_prompt
from src.tools.llm_client import LLMClient


class MemoryAgent:
    """Phase 3 Supabase-backed memory manager."""

    ENGLISH_STUDY_STOPWORDS = {
        "about",
        "again",
        "assistant",
        "chat",
        "course",
        "explain",
        "focus",
        "help",
        "lecture",
        "material",
        "notes",
        "please",
        "question",
        "review",
        "should",
        "study",
        "summarize",
        "today",
        "topic",
        "what",
        "with",
        "your",
    }
    ARABIC_STUDY_STOPWORDS = {
        "اشرح",
        "اليوم",
        "المقرر",
        "المحاضرة",
        "الموضوع",
        "اذاكر",
        "أذاكر",
        "راجع",
        "شرح",
        "ماذا",
        "مراجعة",
        "ممكن",
    }
    WEAKNESS_SIGNALS = {
        "weak",
        "weakness",
        "wrong",
        "mistake",
        "missed",
        "struggle",
        "hard",
        "confused",
        "صعب",
        "ضعف",
        "خطأ",
        "اخطأت",
        "أخطأت",
        "مش فاهم",
    }

    def __init__(self, *, llm_client: LLMClient | None = None) -> None:
        self.repository = SupabaseMemoryRepository()
        self.llm_client = llm_client or LLMClient()
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

    def summarize_chat_session(
        self,
        *,
        course_id: str | None,
        course_name: str | None,
        messages: list[dict[str, Any]],
        language: str = "en",
        student_email: str | None = None,
        student_name: str | None = None,
        sync_cloud: bool = True,
    ) -> dict[str, Any]:
        language = normalize_language(language)
        clean_messages = [
            {
                "role": str(item.get("role", "")).strip(),
                "content": " ".join(str(item.get("content", "")).split()),
            }
            for item in messages
            if isinstance(item, dict) and str(item.get("content", "")).strip()
        ]
        local_main_topics = self._main_chat_topics(clean_messages, language=language)
        local_weaknesses = self._chat_weaknesses(clean_messages, main_topics=local_main_topics)
        local_next_steps = self._chat_next_steps(
            main_topics=local_main_topics,
            weaknesses=local_weaknesses,
            language=language,
        )
        llm_summary = self._generate_chat_summary_with_llm(
            course_name=course_name,
            messages=clean_messages,
            main_topics=local_main_topics,
            weaknesses=local_weaknesses,
            next_steps=local_next_steps,
            language=language,
        )
        if llm_summary:
            main_topics = self._summary_items(llm_summary.get("main_topics"), fallback=local_main_topics, limit=5)
            weaknesses = self._summary_items(llm_summary.get("weaknesses"), fallback=local_weaknesses, limit=5)
            next_steps = self._summary_items(llm_summary.get("next_steps"), fallback=local_next_steps, limit=3)
            summary_text = self._clean_summary_text(llm_summary.get("summary"))
            summary_source = "llm_session_summary"
        else:
            main_topics = local_main_topics
            weaknesses = local_weaknesses
            next_steps = local_next_steps
            summary_text = ""
            summary_source = "local_session"

        if not summary_text:
            summary_text = self._chat_summary_text(
                course_name=course_name,
                main_topics=main_topics,
                weaknesses=weaknesses,
                next_steps=next_steps,
                language=language,
            )

        created_at = datetime.utcnow().isoformat(timespec="seconds")
        summary = {
            "summary_id": "active_session",
            "course_id": course_id,
            "course_name": course_name,
            "language": language,
            "message_count": len(clean_messages),
            "main_topics": main_topics,
            "weaknesses": weaknesses,
            "next_steps": next_steps,
            "summary": summary_text,
            "created_at_utc": created_at,
            "updated_at_utc": created_at,
            "source": summary_source,
        }

        sync_result = {"ok": False, "reason": "Cloud sync skipped."}
        if sync_cloud:
            sync_result = self.sync_chat_summary(
                summary=summary,
                student_email=student_email,
                student_name=student_name,
            )
        return {"ok": True, "summary": summary, "sync_result": sync_result}

    def sync_chat_summary(
        self,
        *,
        summary: dict[str, Any],
        student_email: str | None = None,
        student_name: str | None = None,
    ) -> dict[str, Any]:
        if not self.repository.is_available:
            return {"ok": False, "reason": self.repository.unavailability_reason}

        try:
            profile = self._ensure_student_profile(email=student_email, full_name=student_name)
            course_id = None
            course_name = summary.get("course_name")
            if course_name:
                course = self.repository.upsert_course(
                    student_id=profile["id"],
                    course_name=str(course_name),
                    syllabus_topics=[],
                )
                course_id = course["id"]
            saved = self.repository.upsert_chat_summary(
                student_id=profile["id"],
                course_id=course_id,
                summary=summary,
            )
            return {"ok": True, "student_id": profile["id"], "course_id": course_id, "summary_id": saved.get("id")}
        except MemoryRepositoryError as exc:
            return {"ok": False, "reason": str(exc)}

    def sync_reminders(
        self,
        *,
        course_name: str | None,
        reminders: list[dict[str, Any]],
        student_email: str | None = None,
        student_name: str | None = None,
    ) -> dict[str, Any]:
        if not self.repository.is_available:
            return {"ok": False, "reason": self.repository.unavailability_reason}

        try:
            profile = self._ensure_student_profile(email=student_email, full_name=student_name)
            course_id = None
            if course_name:
                course = self.repository.upsert_course(
                    student_id=profile["id"],
                    course_name=str(course_name),
                    syllabus_topics=[],
                )
                course_id = course["id"]
            saved_count = self.repository.upsert_reminders(
                student_id=profile["id"],
                course_id=course_id,
                reminders=reminders,
            )
            return {"ok": True, "student_id": profile["id"], "course_id": course_id, "saved_reminders": saved_count}
        except MemoryRepositoryError as exc:
            return {"ok": False, "reason": str(exc)}

    def get_preferred_language(
        self,
        *,
        student_email: str | None = None,
        student_name: str | None = None,
    ) -> dict[str, Any]:
        if not self.repository.is_available:
            return {"ok": False, "reason": self.repository.unavailability_reason}

        try:
            profile = self._ensure_student_profile(email=student_email, full_name=student_name)
            return {
                "ok": True,
                "preferred_language": normalize_language(profile.get("preferred_language")),
                "student_id": profile["id"],
            }
        except MemoryRepositoryError as exc:
            return {"ok": False, "reason": str(exc)}

    def save_preferred_language(
        self,
        *,
        preferred_language: str,
        student_email: str | None = None,
        student_name: str | None = None,
    ) -> dict[str, Any]:
        if not self.repository.is_available:
            return {"ok": False, "reason": self.repository.unavailability_reason}

        try:
            profile = self.repository.update_preferred_language(
                email=student_email,
                full_name=student_name,
                preferred_language=normalize_language(preferred_language),
            )
            self._student_id = profile["id"]
            return {
                "ok": True,
                "preferred_language": normalize_language(profile.get("preferred_language")),
                "student_id": profile["id"],
            }
        except MemoryRepositoryError as exc:
            return {"ok": False, "reason": str(exc)}

    def save_user_settings(
        self,
        *,
        settings: dict[str, Any],
        student_email: str | None = None,
        student_name: str | None = None,
    ) -> dict[str, Any]:
        if not self.repository.is_available:
            return {"ok": False, "reason": self.repository.unavailability_reason}

        reminder_preferences = settings.get("reminder_preferences") if isinstance(settings, dict) else {}
        try:
            profile = self.repository.update_student_settings(
                email=student_email,
                full_name=settings.get("full_name") or student_name,
                preferred_language=normalize_language(settings.get("preferred_language")),
                daily_study_hours=float(settings.get("daily_study_hours") or 2.0),
                quiz_preferences={
                    "difficulty": settings.get("default_quiz_difficulty") or "medium",
                    "question_types": settings.get("default_question_types") or ["mcq"],
                },
                difficulty_level=settings.get("default_course_difficulty") or "medium",
                study_preferences={"study_preference": settings.get("study_preference") or "balanced"},
                reminder_preferences=reminder_preferences if isinstance(reminder_preferences, dict) else {},
            )
            self._student_id = profile["id"]
            return {"ok": True, "student_id": profile["id"], "profile": profile}
        except (MemoryRepositoryError, TypeError, ValueError) as exc:
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

    def _main_chat_topics(self, messages: list[dict[str, str]], *, language: str) -> list[str]:
        user_text = " ".join(item["content"] for item in messages if item["role"] == "user")
        tokens = re.findall(r"[\w\u0600-\u06FF]+", user_text)
        stopwords = self.ARABIC_STUDY_STOPWORDS if language == "ar" else self.ENGLISH_STUDY_STOPWORDS
        counts: dict[str, int] = {}
        original: dict[str, str] = {}
        for token in tokens:
            normalized = token.casefold()
            if len(normalized) < 3 or normalized in stopwords:
                continue
            counts[normalized] = counts.get(normalized, 0) + 1
            original.setdefault(normalized, token)
        ranked = sorted(counts, key=lambda item: (-counts[item], item))
        return [original[item] for item in ranked[:5]]

    def _chat_weaknesses(self, messages: list[dict[str, str]], *, main_topics: list[str]) -> list[str]:
        weaknesses = []
        for item in messages:
            if item["role"] != "user":
                continue
            content = item["content"]
            normalized = content.casefold()
            if not any(signal.casefold() in normalized for signal in self.WEAKNESS_SIGNALS):
                continue
            matched_topic = next((topic for topic in main_topics if topic.casefold() in normalized), None)
            weakness = matched_topic or self._short_message_label(content)
            if weakness and weakness not in weaknesses:
                weaknesses.append(weakness)
        return weaknesses[:5]

    def _chat_next_steps(self, *, main_topics: list[str], weaknesses: list[str], language: str) -> list[str]:
        focus_topics = weaknesses or main_topics
        if language == "ar":
            if not focus_topics:
                return ["حدد موضوعا من المقرر ثم اطلب شرحا أو اختبارا قصيرا."]
            first = focus_topics[0]
            return [
                f"راجع {first} بملخص قصير وأمثلة محلولة.",
                f"أنشئ اختبارا قصيرا على {first} لتثبيت الفهم.",
            ]
        if not focus_topics:
            return ["Pick one course topic, then ask for an explanation or a short quiz."]
        first = focus_topics[0]
        return [
            f"Review {first} with a short summary and one worked example.",
            f"Create a short quiz on {first} to check understanding.",
        ]

    def _generate_chat_summary_with_llm(
        self,
        *,
        course_name: str | None,
        messages: list[dict[str, str]],
        main_topics: list[str],
        weaknesses: list[str],
        next_steps: list[str],
        language: str,
    ) -> dict[str, Any] | None:
        if not self.llm_client.is_available or not messages:
            return None

        prompt = render_prompt(
            "chat_session_summary",
            course_name=course_name or ("this course" if language != "ar" else "\u0647\u0630\u0627 \u0627\u0644\u0645\u0642\u0631\u0631"),
            messages=self._messages_for_prompt(messages),
            main_topics=self._format_summary_items(main_topics),
            weaknesses=self._format_summary_items(weaknesses),
            next_steps=self._format_summary_items(next_steps),
            language="Arabic" if language == "ar" else "English",
        )
        try:
            payload = self.llm_client.generate_json(
                system_prompt=prompt.system,
                user_prompt=prompt.user,
                temperature=0.2,
                max_tokens=800,
            )
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        if not any(payload.get(key) for key in ("main_topics", "weaknesses", "next_steps", "summary")):
            return None
        return payload

    def _messages_for_prompt(self, messages: list[dict[str, str]], *, limit: int = 12) -> str:
        lines = []
        for index, item in enumerate(messages[-limit:], start=1):
            role = item.get("role") or "message"
            content = self._trim_text(item.get("content", ""), max_length=500)
            lines.append(f"{index}. {role}: {content}")
        return "\n".join(lines) if lines else "No messages."

    def _format_summary_items(self, items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else "None."

    def _summary_items(self, value: Any, *, fallback: list[str], limit: int) -> list[str]:
        if isinstance(value, str):
            raw_items = re.split(r"[,;\n]+", value)
        elif isinstance(value, (list, tuple, set)):
            raw_items = list(value)
        else:
            raw_items = []

        items = []
        seen: set[str] = set()
        for item in raw_items:
            text = " ".join(str(item or "").strip(" -").split())
            normalized = text.casefold()
            if not text or normalized in seen:
                continue
            items.append(self._trim_text(text, max_length=120))
            seen.add(normalized)
            if len(items) == limit:
                break
        return items or fallback[:limit]

    def _clean_summary_text(self, value: Any) -> str:
        return self._trim_text(value, max_length=700)

    def _trim_text(self, value: Any, *, max_length: int) -> str:
        compact = " ".join(str(value or "").split())
        if len(compact) <= max_length:
            return compact
        return f"{compact[:max_length].rsplit(' ', 1)[0].rstrip()}..."

    def _chat_summary_text(
        self,
        *,
        course_name: str | None,
        main_topics: list[str],
        weaknesses: list[str],
        next_steps: list[str],
        language: str,
    ) -> str:
        course = course_name or ("المقرر الحالي" if language == "ar" else "the active course")
        topics = ", ".join(main_topics) if main_topics else ("غير محددة بعد" if language == "ar" else "not specific yet")
        weak = ", ".join(weaknesses) if weaknesses else ("لا توجد إشارات ضعف واضحة" if language == "ar" else "no clear weakness signals")
        steps = " ".join(next_steps)
        if language == "ar":
            return f"ملخص {course}: الموضوعات الرئيسية: {topics}. نقاط الضعف: {weak}. الخطوات التالية: {steps}"
        return f"{course} summary: main topics: {topics}. Weakness signals: {weak}. Next steps: {steps}"

    def _short_message_label(self, content: str) -> str:
        words = re.findall(r"[\w\u0600-\u06FF]+", content)
        return " ".join(words[:6])

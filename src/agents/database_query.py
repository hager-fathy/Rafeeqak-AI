from __future__ import annotations

from datetime import date
from typing import Any

from src.localization import normalize_language, t


class DatabaseQueryAgent:
    """Answers structured progress, deadline, score, and weak-topic questions."""

    DEADLINE_KEYWORDS = {"deadline", "deadlines", "exam", "exams", "due", "when"}
    PROGRESS_KEYWORDS = {"progress", "completed", "remaining", "status", "dashboard"}
    SCORE_KEYWORDS = {"score", "scores", "quiz", "average", "grade", "grades"}
    WEAK_TOPIC_KEYWORDS = {"weak", "weakness", "weaknesses", "struggle", "struggling"}
    ALL_COURSE_KEYWORDS = {"all", "overall", "courses", "course-by-course", "every"}
    ARABIC_DEADLINE_KEYWORDS = {"موعد", "مواعيد", "امتحان", "الامتحان", "اختبار", "متى"}
    ARABIC_PROGRESS_KEYWORDS = {"تقدم", "التقدم", "أنجزت", "انجزت", "المتبقي", "الحالة", "لوحة"}
    ARABIC_SCORE_KEYWORDS = {"درجة", "درجات", "اختبار", "كويز", "متوسط"}
    ARABIC_WEAK_TOPIC_KEYWORDS = {"ضعف", "ضعفي", "نقاط", "صعب", "أخطأت", "اخطأت"}
    ARABIC_ALL_COURSE_KEYWORDS = {"كل", "جميع", "المقررات", "المواد", "عام"}

    def answer(
        self,
        *,
        message: str,
        context: dict[str, Any],
        memory_agent: Any | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        language = normalize_language(language)
        query_type = self.classify(message, language=language)
        snapshot_result = self._snapshot(context=context, memory_agent=memory_agent)
        local_data = self._local_data(context)
        wants_all_courses = self._wants_all_courses(message, language=language)

        if wants_all_courses:
            response = self._all_courses_response(local_data, query_type, language)
        elif query_type == "deadline":
            response = self._deadline_response(local_data, snapshot_result, language)
        elif query_type == "score":
            response = self._score_response(local_data, snapshot_result, language)
        elif query_type == "weak_topics":
            response = self._weak_topics_response(local_data, snapshot_result, language)
        else:
            response = self._progress_response(local_data, language)

        return {
            "ok": True,
            "status": "answered",
            "query_type": query_type,
            "response": response,
            "data": local_data,
            "scope": "all_courses" if wants_all_courses else "selected_course",
            "snapshot_used": snapshot_result.get("ok", False),
            "snapshot_reason": snapshot_result.get("reason", ""),
        }

    def classify(self, message: str, *, language: str = "en") -> str:
        tokens = self._tokens(message)
        deadline_keywords = self.DEADLINE_KEYWORDS | (self.ARABIC_DEADLINE_KEYWORDS if language == "ar" else set())
        score_keywords = self.SCORE_KEYWORDS | (self.ARABIC_SCORE_KEYWORDS if language == "ar" else set())
        weak_keywords = self.WEAK_TOPIC_KEYWORDS | (self.ARABIC_WEAK_TOPIC_KEYWORDS if language == "ar" else set())
        progress_keywords = self.PROGRESS_KEYWORDS | (self.ARABIC_PROGRESS_KEYWORDS if language == "ar" else set())
        if tokens & deadline_keywords:
            return "deadline"
        if tokens & score_keywords:
            return "score"
        if tokens & weak_keywords:
            return "weak_topics"
        if tokens & progress_keywords:
            return "progress"
        return "progress"

    def _local_data(self, context: dict[str, Any]) -> dict[str, Any]:
        active_plan = context.get("active_plan") or {}
        tasks = active_plan.get("tasks", []) if isinstance(active_plan, dict) else []
        quiz_attempts = context.get("quiz_attempts", []) or []
        completed_tasks = [task for task in tasks if task.get("completed")]
        remaining_tasks = [task for task in tasks if not task.get("completed")]
        weak_topics = list(active_plan.get("weak_topics", [])) if isinstance(active_plan, dict) else []
        quiz_weak_topics = []
        for attempt in quiz_attempts:
            quiz_weak_topics.extend(attempt.get("weak_topics", []) or [])
        average_score = 0.0
        if quiz_attempts:
            average_score = round(sum(item.get("score_percent", 0) for item in quiz_attempts) / len(quiz_attempts), 1)

        return {
            "active_course": context.get("active_course_name")
            or (active_plan.get("course_name") if isinstance(active_plan, dict) else None),
            "active_course_id": context.get("active_course_id"),
            "exam_date": active_plan.get("exam_date") if isinstance(active_plan, dict) else None,
            "total_tasks": len(tasks),
            "completed_tasks": len(completed_tasks),
            "remaining_tasks": len(remaining_tasks),
            "next_task": remaining_tasks[0] if remaining_tasks else None,
            "weak_topics": sorted(set(weak_topics + quiz_weak_topics)),
            "quiz_attempts": len(quiz_attempts),
            "average_score": average_score,
            "last_quiz": quiz_attempts[-1] if quiz_attempts else None,
            "all_courses": context.get("all_courses", []),
        }

    def _snapshot(self, *, context: dict[str, Any], memory_agent: Any | None) -> dict[str, Any]:
        if memory_agent is None:
            return {"ok": False, "reason": "Memory agent was not provided."}
        auth_user = context.get("auth_user") or {}
        student_email = auth_user.get("email")
        student_name = (auth_user.get("user_metadata") or {}).get("full_name")
        if not student_email:
            return {"ok": False, "reason": "No authenticated user in context."}
        try:
            return memory_agent.get_snapshot(student_email=student_email, student_name=student_name)
        except Exception as exc:  # pragma: no cover - defensive integration path
            return {"ok": False, "reason": str(exc)}

    def _deadline_response(self, data: dict[str, Any], snapshot_result: dict[str, Any], language: str) -> str:
        exam_date = data.get("exam_date")
        course = data.get("active_course") or ("المقرر النشط" if language == "ar" else "your active course")
        if not exam_date and snapshot_result.get("ok"):
            exams = snapshot_result.get("snapshot", {}).get("exams", [])
            if exams:
                exam_date = exams[0].get("exam_date")

        if not exam_date:
            return t("db.no_deadline", language)

        days_text = self._days_until_text(exam_date, language)
        return t("db.deadline", language, course=course, exam_date=exam_date, days_text=days_text)

    def _progress_response(self, data: dict[str, Any], language: str) -> str:
        if data["total_tasks"] == 0:
            return t("db.no_progress", language)

        percent = round((data["completed_tasks"] / data["total_tasks"]) * 100, 1)
        next_task = data.get("next_task")
        response = t(
            "db.progress",
            language,
            completed=data["completed_tasks"],
            total=data["total_tasks"],
            percent=percent,
        )
        if next_task:
            response += t(
                "db.next_task",
                language,
                topic=next_task["topic"],
                date=next_task["date"],
                hours=next_task["hours"],
            )
        return response

    def _score_response(self, data: dict[str, Any], snapshot_result: dict[str, Any], language: str) -> str:
        attempts = data["quiz_attempts"]
        average = data["average_score"]
        last_quiz = data.get("last_quiz")
        if attempts == 0 and snapshot_result.get("ok"):
            recent = snapshot_result.get("snapshot", {}).get("recent_quizzes", [])
            attempts = len(recent)
            if recent:
                average = round(sum(float(item.get("score_percent", 0)) for item in recent) / attempts, 1)
                last_quiz = recent[0]

        if attempts == 0:
            return t("db.no_scores", language)

        topic = last_quiz.get("topic", "latest quiz") if last_quiz else "latest quiz"
        score = last_quiz.get("score_percent", average) if last_quiz else average
        return t("db.scores", language, attempts=attempts, average=average, score=score, topic=topic)

    def _weak_topics_response(self, data: dict[str, Any], snapshot_result: dict[str, Any], language: str) -> str:
        weak_topics = data["weak_topics"]
        if snapshot_result.get("ok"):
            snapshot_topics = [
                item.get("topic")
                for item in snapshot_result.get("snapshot", {}).get("weak_topics", [])
                if item.get("topic")
            ]
            weak_topics = sorted(set(weak_topics + snapshot_topics))

        if not weak_topics:
            return t("db.no_weak", language)

        topics = ", ".join(weak_topics[:6])
        return t("db.weak", language, topics=topics)

    def _all_courses_response(self, data: dict[str, Any], query_type: str, language: str) -> str:
        courses = data.get("all_courses", [])
        if not courses:
            return t("db.no_courses", language)

        if query_type == "score":
            if language == "ar":
                rows = [
                    f"{course['course_name']}: {course['quiz_attempts']} محاولة، متوسط {course['average_score']}%"
                    for course in courses
                ]
            else:
                rows = [
                    f"{course['course_name']}: {course['quiz_attempts']} attempt(s), {course['average_score']}% average"
                    for course in courses
                ]
            return t("db.all_scores", language, rows="; ".join(rows))
        if query_type == "weak_topics":
            rows = [
                f"{course['course_name']}: {', '.join(course['weak_topics'][:4]) or t('db.no_weak_short', language)}"
                for course in courses
            ]
            return t("db.all_weak", language, rows="; ".join(rows))
        if query_type == "deadline":
            rows = [
                f"{course['course_name']}: {course['exam_date'] or t('db.no_deadline_short', language)}"
                for course in courses
            ]
            return t("db.all_deadlines", language, rows="; ".join(rows))

        rows = []
        for course in courses:
            total = course["total_tasks"]
            completed = course["completed_tasks"]
            percent = round((completed / total) * 100, 1) if total else 0.0
            if language == "ar":
                rows.append(
                    f"{course['course_name']}: {completed}/{total} مهمة ({percent}%)، "
                    f"{course['uploads']} ملف، {course['quiz_attempts']} محاولة اختبار"
                )
            else:
                rows.append(
                    f"{course['course_name']}: {completed}/{total} tasks ({percent}%), "
                    f"{course['uploads']} upload(s), {course['quiz_attempts']} quiz attempt(s)"
                )
        return t("db.all_progress", language, rows="; ".join(rows))

    def _days_until_text(self, raw_date: str, language: str = "en") -> str:
        try:
            exam_date = date.fromisoformat(str(raw_date))
        except ValueError:
            return ""
        days = (exam_date - date.today()).days
        if days > 0:
            return t("db.days_remaining", language, days=days)
        if days == 0:
            return t("db.exam_today", language)
        return t("db.exam_past", language, days=abs(days))

    def _tokens(self, message: str) -> set[str]:
        return {token.strip(".,?!:;؟،؛").lower() for token in str(message).split() if token.strip()}

    def _wants_all_courses(self, message: str, *, language: str = "en") -> bool:
        keywords = self.ALL_COURSE_KEYWORDS | (self.ARABIC_ALL_COURSE_KEYWORDS if language == "ar" else set())
        return bool(self._tokens(message) & keywords)

from __future__ import annotations

from datetime import date
from typing import Any


class DatabaseQueryAgent:
    """Answers structured progress, deadline, score, and weak-topic questions."""

    DEADLINE_KEYWORDS = {"deadline", "deadlines", "exam", "exams", "due", "when"}
    PROGRESS_KEYWORDS = {"progress", "completed", "remaining", "status", "dashboard"}
    SCORE_KEYWORDS = {"score", "scores", "quiz", "average", "grade", "grades"}
    WEAK_TOPIC_KEYWORDS = {"weak", "weakness", "weaknesses", "struggle", "struggling"}
    ALL_COURSE_KEYWORDS = {"all", "overall", "courses", "course-by-course", "every"}

    def answer(
        self,
        *,
        message: str,
        context: dict[str, Any],
        memory_agent: Any | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        query_type = self.classify(message, language=language)
        snapshot_result = self._snapshot(context=context, memory_agent=memory_agent)
        local_data = self._local_data(context)
        wants_all_courses = self._wants_all_courses(message)

        if wants_all_courses:
            response = self._all_courses_response(local_data, query_type)
        elif query_type == "deadline":
            response = self._deadline_response(local_data, snapshot_result)
        elif query_type == "score":
            response = self._score_response(local_data, snapshot_result)
        elif query_type == "weak_topics":
            response = self._weak_topics_response(local_data, snapshot_result)
        else:
            response = self._progress_response(local_data)

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
        del language
        tokens = self._tokens(message)
        if tokens & self.DEADLINE_KEYWORDS:
            return "deadline"
        if tokens & self.SCORE_KEYWORDS:
            return "score"
        if tokens & self.WEAK_TOPIC_KEYWORDS:
            return "weak_topics"
        if tokens & self.PROGRESS_KEYWORDS:
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

    def _deadline_response(self, data: dict[str, Any], snapshot_result: dict[str, Any]) -> str:
        exam_date = data.get("exam_date")
        course = data.get("active_course") or "your active course"
        if not exam_date and snapshot_result.get("ok"):
            exams = snapshot_result.get("snapshot", {}).get("exams", [])
            if exams:
                exam_date = exams[0].get("exam_date")

        if not exam_date:
            return "No exam deadline is saved yet. Create a study plan first."

        days_text = self._days_until_text(exam_date)
        return f"The exam deadline for {course} is {exam_date}. {days_text}"

    def _progress_response(self, data: dict[str, Any]) -> str:
        if data["total_tasks"] == 0:
            return "There is no active plan to measure progress. Create a study plan first."

        percent = round((data["completed_tasks"] / data["total_tasks"]) * 100, 1)
        next_task = data.get("next_task")
        response = f"You completed {data['completed_tasks']} of {data['total_tasks']} tasks ({percent}%)."
        if next_task:
            response += f" Next task: {next_task['topic']} on {next_task['date']} for {next_task['hours']}h."
        return response

    def _score_response(self, data: dict[str, Any], snapshot_result: dict[str, Any]) -> str:
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
            return "No quiz attempts are recorded yet."

        topic = last_quiz.get("topic", "latest quiz") if last_quiz else "latest quiz"
        score = last_quiz.get("score_percent", average) if last_quiz else average
        return f"You have {attempts} quiz attempt(s). Average score is {average}%. Latest score was {score}% on {topic}."

    def _weak_topics_response(self, data: dict[str, Any], snapshot_result: dict[str, Any]) -> str:
        weak_topics = data["weak_topics"]
        if snapshot_result.get("ok"):
            snapshot_topics = [
                item.get("topic")
                for item in snapshot_result.get("snapshot", {}).get("weak_topics", [])
                if item.get("topic")
            ]
            weak_topics = sorted(set(weak_topics + snapshot_topics))

        if not weak_topics:
            return "No weak topics are saved yet."

        topics = ", ".join(weak_topics[:6])
        return f"Current weak topics: {topics}. Prioritize them in revision and short quizzes."

    def _all_courses_response(self, data: dict[str, Any], query_type: str) -> str:
        courses = data.get("all_courses", [])
        if not courses:
            return "No courses are saved yet."

        if query_type == "score":
            rows = [
                f"{course['course_name']}: {course['quiz_attempts']} attempt(s), {course['average_score']}% average"
                for course in courses
            ]
            return "All-course quiz summary: " + "; ".join(rows)
        if query_type == "weak_topics":
            rows = [
                f"{course['course_name']}: {', '.join(course['weak_topics'][:4]) or 'no weak topics'}"
                for course in courses
            ]
            return "All-course weak-topic summary: " + "; ".join(rows)
        if query_type == "deadline":
            rows = [
                f"{course['course_name']}: {course['exam_date'] or 'no deadline'}"
                for course in courses
            ]
            return "All-course deadline summary: " + "; ".join(rows)

        rows = []
        for course in courses:
            total = course["total_tasks"]
            completed = course["completed_tasks"]
            percent = round((completed / total) * 100, 1) if total else 0.0
            rows.append(
                f"{course['course_name']}: {completed}/{total} tasks ({percent}%), "
                f"{course['uploads']} upload(s), {course['quiz_attempts']} quiz attempt(s)"
            )
        return "All-course progress summary: " + "; ".join(rows)

    def _days_until_text(self, raw_date: str) -> str:
        try:
            exam_date = date.fromisoformat(str(raw_date))
        except ValueError:
            return ""
        days = (exam_date - date.today()).days
        if days > 0:
            return f"{days} day(s) remaining."
        if days == 0:
            return "The exam is today."
        return f"It was {abs(days)} day(s) ago."

    def _tokens(self, message: str) -> set[str]:
        return {token.strip(".,?!:;?").lower() for token in str(message).split() if token.strip()}

    def _wants_all_courses(self, message: str) -> bool:
        return bool(self._tokens(message) & self.ALL_COURSE_KEYWORDS)

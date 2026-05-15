from __future__ import annotations

from datetime import datetime
from typing import Any


class ProgressEvaluatorAgent:
    """Scores quiz attempts and converts mistakes into progress signals."""

    def evaluate(
        self,
        *,
        questions: list[dict[str, Any]],
        selected_indices: list[int | None],
        topic: str,
        language: str = "en",
    ) -> dict[str, Any]:
        if not questions:
            return {
                "ok": False,
                "status": "empty_quiz",
                "message": "No quiz questions were provided.",
                "correct": 0,
                "total": 0,
                "score_percent": 0.0,
                "feedback": [],
                "weak_topics": [],
            }

        feedback = []
        correct_count = 0
        for question, selected_index in zip(questions, selected_indices):
            options = question.get("options", [])
            answer_index = int(question.get("answer_index", -1))
            selected_answer = self._option_at(options, selected_index)
            correct_answer = self._option_at(options, answer_index)
            is_correct = selected_index == answer_index
            if is_correct:
                correct_count += 1
            feedback.append(
                {
                    "question": question.get("question", ""),
                    "selected_index": selected_index,
                    "selected_answer": selected_answer,
                    "correct_index": answer_index,
                    "correct_answer": correct_answer,
                    "is_correct": is_correct,
                    "explanation": question.get("explanation", ""),
                    "source": question.get("source", "generated"),
                }
            )

        total = len(questions)
        score_percent = round((correct_count / total) * 100, 1)
        weak_topics = self._weak_topics(topic=topic, score_percent=score_percent, feedback=feedback)

        return {
            "ok": True,
            "status": "evaluated",
            "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds"),
            "topic": topic,
            "correct": correct_count,
            "total": total,
            "score_percent": score_percent,
            "feedback": feedback,
            "weak_topics": weak_topics,
            "summary": self._summary(correct_count, total, score_percent, language),
            "recommendation": self._recommendation(score_percent, topic, language),
        }

    def _weak_topics(
        self,
        *,
        topic: str,
        score_percent: float,
        feedback: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        missed_count = sum(1 for item in feedback if not item["is_correct"])
        if score_percent >= 70 or missed_count == 0:
            return []
        severity = round(min(1.0, max(0.35, 1 - (score_percent / 100))), 2)
        return [
            {
                "topic": topic,
                "severity_score": severity,
                "missed_questions": missed_count,
                "source": "quiz",
            }
        ]

    def _summary(self, correct: int, total: int, score_percent: float, language: str) -> str:
        if language == "ar":
            return f"درجتك: {correct}/{total} ({score_percent}%)."
        return f"Score: {correct}/{total} ({score_percent}%)."

    def _recommendation(self, score_percent: float, topic: str, language: str) -> str:
        if score_percent >= 85:
            return "Great mastery. Move to mixed practice." if language != "ar" else "ممتاز. انتقل إلى تدريب مختلط."
        if score_percent >= 70:
            return "Good progress. Review the missed explanations once." if language != "ar" else "تقدم جيد. راجع شرح الأخطاء مرة واحدة."
        if language == "ar":
            return f"راجع {topic} مرة أخرى ثم أعد اختبارا قصيرا."
        return f"Review {topic} again, then retry a short quiz."

    def _option_at(self, options: list[str], index: int | None) -> str | None:
        if index is None:
            return None
        if 0 <= index < len(options):
            return options[index]
        return None

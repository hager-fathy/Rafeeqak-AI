from __future__ import annotations

import re
from datetime import datetime
from typing import Any


class ProgressEvaluatorAgent:
    """Scores quiz attempts and converts mistakes into progress signals."""

    def evaluate(
        self,
        *,
        questions: list[dict[str, Any]],
        selected_indices: list[int | None] | None = None,
        answers: list[Any] | None = None,
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
                "points_earned": 0.0,
                "total_points": 0.0,
                "score_percent": 0.0,
                "feedback": [],
                "weak_topics": [],
            }

        feedback = []
        earned_points = 0.0
        answer_payloads = answers if answers is not None else list(selected_indices or [])
        for index, question in enumerate(questions):
            answer = answer_payloads[index] if index < len(answer_payloads) else None
            scored = self._score_question(question, answer)
            earned_points += scored["score"]
            feedback.append(
                {
                    "question": question.get("question", ""),
                    "type": question.get("type", "mcq"),
                    "selected_index": scored.get("selected_index"),
                    "selected_answer": scored["selected_answer"],
                    "correct_index": scored.get("correct_index"),
                    "correct_answer": scored["correct_answer"],
                    "is_correct": scored["score"] >= 1.0,
                    "partial_credit": 0 < scored["score"] < 1.0,
                    "score": round(scored["score"], 2),
                    "explanation": question.get("explanation", ""),
                    "source": question.get("source", "generated"),
                }
            )

        total = len(questions)
        correct_count = sum(1 for item in feedback if item["is_correct"])
        score_percent = round((earned_points / total) * 100, 1)
        weak_topics = self._weak_topics(topic=topic, score_percent=score_percent, feedback=feedback)

        return {
            "ok": True,
            "status": "evaluated",
            "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds"),
            "topic": topic,
            "correct": correct_count,
            "total": total,
            "points_earned": round(earned_points, 2),
            "total_points": float(total),
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
        missed_count = sum(1 for item in feedback if item["score"] < 1.0)
        if score_percent >= 70 or missed_count == 0:
            return []
        severity = round(min(1.0, max(0.35, 1 - (score_percent / 100))), 2)
        weak_types = sorted({item["type"] for item in feedback if item["score"] < 1.0})
        return [
            {
                "topic": topic,
                "severity_score": severity,
                "missed_questions": missed_count,
                "weak_question_types": weak_types,
                "source": "quiz",
            }
        ]

    def _summary(self, correct: int, total: int, score_percent: float, language: str) -> str:
        if language == "ar":
            return f"درجتك: {correct}/{total} ({score_percent}%)."
        return f"Score: {correct}/{total} ({score_percent}%)."

    def _recommendation(self, score_percent: float, topic: str, language: str) -> str:
        if score_percent >= 85:
            if language == "ar":
                return "ممتاز. انتقل إلى تدريب مختلط وارفع الصعوبة في المرة القادمة."
            return f"Great mastery of {topic}. Move to mixed practice and raise the difficulty next time."
        if score_percent >= 70:
            if language == "ar":
                return "تقدم جيد. راجع شرح الأخطاء والأسئلة ذات الدرجة الجزئية مرة واحدة."
            return "Good progress. Review missed and partial-credit explanations, then retry the weakest question type."
        if language == "ar":
            return f"راجع {topic} مرة أخرى، ثم أعد اختبارا قصيرا يركز على أنواع الأسئلة التي أخطأت فيها."
        return f"Review {topic} again, then retry a short quiz focused on the question types you missed."

    def _score_question(self, question: dict[str, Any], answer: Any) -> dict[str, Any]:
        question_type = question.get("type", "mcq")
        if question_type in {"mcq", "true_false"}:
            return self._score_choice_question(question, answer)
        if question_type == "short_answer":
            return self._score_short_answer(question, answer)
        if question_type == "matching":
            return self._score_matching(question, answer)
        return self._score_choice_question(question, answer)

    def _score_choice_question(self, question: dict[str, Any], answer: Any) -> dict[str, Any]:
        options = question.get("options", [])
        answer_index = int(question.get("answer_index", -1))
        try:
            selected_index = None if answer is None else int(answer)
        except (TypeError, ValueError):
            selected_index = None
        return {
            "score": 1.0 if selected_index == answer_index else 0.0,
            "selected_index": selected_index,
            "selected_answer": self._option_at(options, selected_index),
            "correct_index": answer_index,
            "correct_answer": self._option_at(options, answer_index),
        }

    def _score_short_answer(self, question: dict[str, Any], answer: Any) -> dict[str, Any]:
        answer_text = str(answer or "").strip()
        keywords = [str(item).lower() for item in question.get("keywords", []) if str(item).strip()]
        normalized_answer = self._normalize(answer_text)
        if not normalized_answer:
            score = 0.0
        elif not keywords:
            expected = self._normalize(question.get("expected_answer", ""))
            score = 1.0 if expected and expected in normalized_answer else 0.5
        else:
            hits = sum(1 for keyword in keywords if keyword in normalized_answer)
            score = min(1.0, hits / max(2, min(len(keywords), 4)))
        return {
            "score": round(score, 2),
            "selected_index": None,
            "selected_answer": answer_text or None,
            "correct_index": None,
            "correct_answer": question.get("expected_answer"),
        }

    def _score_matching(self, question: dict[str, Any], answer: Any) -> dict[str, Any]:
        expected = question.get("answer_map", {})
        selected = answer if isinstance(answer, dict) else {}
        if not expected:
            score = 0.0
        else:
            correct = sum(1 for left, right in expected.items() if selected.get(left) == right)
            score = correct / len(expected)
        return {
            "score": round(score, 2),
            "selected_index": None,
            "selected_answer": selected or None,
            "correct_index": None,
            "correct_answer": expected,
        }

    def _option_at(self, options: list[str], index: int | None) -> str | None:
        if index is None:
            return None
        if 0 <= index < len(options):
            return options[index]
        return None

    def _normalize(self, text: str) -> str:
        return " ".join(re.findall(r"[\w\u0600-\u06FF]+", str(text).lower()))

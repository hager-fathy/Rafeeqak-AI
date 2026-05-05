from __future__ import annotations


class InputRouterAgent:
    """Detects intent and language before the supervisor chooses an agent."""

    ENGLISH_KEYWORDS = {
        "quiz": ["quiz", "test me", "question", "questions", "practice", "flashcard"],
        "course_material": ["upload", "pdf", "slide", "notes", "lecture", "material", "explain"],
        "memory": ["remember", "memory", "progress", "score", "scores", "weakness"],
        "study_plan": ["plan", "schedule", "study", "revise", "revision", "today", "tomorrow", "exam", "weak"],
    }

    ARABIC_KEYWORDS = {
        "quiz": ["اختبار", "اسئلة", "أسئلة", "كويز"],
        "course_material": ["ملف", "محاضرة", "ملاحظات", "شرح"],
        "memory": ["تذكر", "ذاكرة", "تقدمي", "درجات"],
        "study_plan": ["خطة", "جدول", "اذاكر", "أذاكر", "مراجعة", "امتحان"],
    }

    def route(self, user_message: str) -> dict:
        message = user_message.strip()
        lowered = message.lower()
        language = "ar" if self._contains_arabic(message) else "en"
        keyword_map = self.ARABIC_KEYWORDS if language == "ar" else self.ENGLISH_KEYWORDS
        scores = {intent: 0 for intent in self.ENGLISH_KEYWORDS}
        signals: list[str] = []

        for intent, keywords in keyword_map.items():
            for keyword in keywords:
                if keyword in lowered:
                    scores[intent] += 1
                    signals.append(keyword)

        intent = max(scores, key=scores.get)
        if scores[intent] == 0:
            intent = "chat"

        return {
            "message": message,
            "intent": intent,
            "language": language,
            "confidence": self._confidence(scores[intent]),
            "signals": signals,
        }

    def _contains_arabic(self, text: str) -> bool:
        return any("\u0600" <= ch <= "\u06FF" for ch in text)

    def _confidence(self, score: int) -> float:
        if score <= 0:
            return 0.35
        if score == 1:
            return 0.72
        return 0.9

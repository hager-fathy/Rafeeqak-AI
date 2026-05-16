from __future__ import annotations

from src.localization import detect_language


class InputRouterAgent:
    """Detects intent and language before the supervisor chooses an agent."""

    VAGUE_COURSE_MATERIAL_REQUESTS = {
        "en": {
            "explain",
            "summarize",
            "summarise",
            "describe",
            "help",
            "what is this",
            "what is that",
            "explain this",
            "summarize this",
            "describe this",
        },
        "ar": {
            "\u0627\u0634\u0631\u062d",
            "\u0634\u0631\u062d",
            "\u0644\u062e\u0635",
            "\u0645\u0633\u0627\u0639\u062f\u0629",
            "\u0633\u0627\u0639\u062f\u0646\u064a",
            "\u0645\u0627 \u0647\u0630\u0627",
            "\u0627\u064a\u0647 \u062f\u0647",
        },
    }

    ENGLISH_KEYWORDS = {
        "quiz": ["quiz", "test me", "question", "questions", "practice", "flashcard"],
        "course_material": [
            "upload",
            "pdf",
            "slide",
            "notes",
            "lecture",
            "material",
            "explain",
            "summarize",
            "summarise",
            "describe",
        ],
        "database_query": [
            "deadline",
            "deadlines",
            "progress",
            "completed",
            "remaining",
            "score",
            "scores",
            "average",
            "weakness",
        ],
        "memory": ["remember", "memory", "stored", "saved"],
        "study_plan": ["plan", "schedule", "study", "revise", "revision", "today", "tomorrow", "exam", "weak"],
    }

    ARABIC_KEYWORDS = {
        "quiz": ["اختبار", "اسئلة", "أسئلة", "كويز", "تدريب", "فلاش كارد", "اختبرني"],
        "course_material": ["ملف", "محاضرة", "ملاحظات", "شرح", "اشرح", "لخص", "المادة", "ملخص", "pdf"],
        "database_query": ["موعد", "مواعيد", "تقدم", "التقدم", "أنجزت", "المتبقي", "درجات", "درجة", "متوسط", "ضعفي"],
        "memory": ["تذكر", "ذاكرة", "محفوظ", "حفظت"],
        "study_plan": ["خطة", "جدول", "اذاكر", "أذاكر", "مراجعة", "امتحان", "الامتحان", "اليوم", "بكرة"],
    }

    def route(self, user_message: str) -> dict:
        message = user_message.strip()
        lowered = message.lower()
        language = detect_language(message)
        keyword_map = self.ARABIC_KEYWORDS if language == "ar" else self.ENGLISH_KEYWORDS
        scores = {intent: 0 for intent in self.ENGLISH_KEYWORDS}
        signals: list[str] = []

        normalized = " ".join(lowered.strip(" \t\r\n.?!\u061f\u060c,;:").split())
        if normalized in self.VAGUE_COURSE_MATERIAL_REQUESTS[language]:
            return {
                "message": message,
                "intent": "course_material",
                "language": language,
                "confidence": 0.72,
                "signals": [normalized],
            }

        for intent, keywords in keyword_map.items():
            for keyword in keywords:
                if keyword in lowered:
                    scores[intent] += 1
                    signals.append(keyword)

        intent = max(scores, key=scores.get)
        intent_score = scores[intent]
        if intent_score == 0:
            intent = "chat"

        return {
            "message": message,
            "intent": intent,
            "language": language,
            "confidence": self._confidence(intent_score),
            "signals": signals,
        }

    def _contains_arabic(self, text: str) -> bool:
        return detect_language(text) == "ar"

    def _confidence(self, score: int) -> float:
        if score <= 0:
            return 0.35
        if score == 1:
            return 0.72
        return 0.9

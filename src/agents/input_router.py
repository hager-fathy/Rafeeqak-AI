class InputRouterAgent:
    """Phase 4 placeholder: detect intent and language."""

    def route(self, user_message: str) -> dict:
        lowered = user_message.strip().lower()

        if "quiz" in lowered:
            intent = "quiz"
        elif "plan" in lowered or "study" in lowered:
            intent = "study_plan"
        elif "upload" in lowered or "note" in lowered or "pdf" in lowered:
            intent = "upload"
        else:
            intent = "chat"

        language = "ar" if any("\u0600" <= ch <= "\u06FF" for ch in user_message) else "en"
        return {"intent": intent, "language": language}

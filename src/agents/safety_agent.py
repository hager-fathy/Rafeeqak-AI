class SafetyAgent:
    """Lightweight prompt-injection screen for unsafe routing requests."""

    def check(self, user_message: str) -> dict:
        lower = user_message.lower()
        blocked_markers = ["ignore previous", "reveal system prompt", "bypass safety"]
        flagged = any(marker in lower for marker in blocked_markers)
        return {"safe": not flagged, "flagged": flagged}

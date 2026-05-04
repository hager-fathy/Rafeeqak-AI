class SupervisorAgent:
    """Phase 4 placeholder: coordinate specialist agents."""

    def decide(self, routed_input: dict) -> str:
        intent = routed_input.get("intent", "chat")
        mapping = {
            "study_plan": "study_planner_agent",
            "quiz": "quiz_generator_agent",
            "upload": "course_rag_agent",
            "chat": "response_agent",
        }
        return mapping.get(intent, "response_agent")

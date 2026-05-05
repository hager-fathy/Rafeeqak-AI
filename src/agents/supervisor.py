from __future__ import annotations

from datetime import datetime
from typing import Any

from src.agents.course_rag import CourseRAGAgent
from src.agents.input_router import InputRouterAgent
from src.agents.progress_evaluator import ProgressEvaluatorAgent
from src.agents.quiz_generator import QuizGeneratorAgent
from src.agents.safety_agent import SafetyAgent
from src.agents.study_planner import StudyPlannerAgent


class SupervisorAgent:
    """Coordinates specialist agents and records every routing step."""

    def __init__(
        self,
        *,
        router: InputRouterAgent | None = None,
        study_planner: StudyPlannerAgent | None = None,
        course_rag: CourseRAGAgent | None = None,
        quiz_generator: QuizGeneratorAgent | None = None,
        progress_evaluator: ProgressEvaluatorAgent | None = None,
        safety: SafetyAgent | None = None,
    ) -> None:
        self.router = router or InputRouterAgent()
        self.study_planner = study_planner or StudyPlannerAgent()
        self.course_rag = course_rag or CourseRAGAgent()
        self.quiz_generator = quiz_generator or QuizGeneratorAgent()
        self.progress_evaluator = progress_evaluator or ProgressEvaluatorAgent()
        self.safety = safety or SafetyAgent()

    def decide(self, routed_input: dict[str, Any]) -> str:
        intent = routed_input.get("intent", "chat")
        mapping = {
            "study_plan": "study_planner_agent",
            "quiz": "quiz_generator_agent",
            "course_material": "course_rag_agent",
            "upload": "course_rag_agent",
            "memory": "memory_agent",
            "chat": "response_agent",
        }
        return mapping.get(intent, "response_agent")

    def handle_message(
        self,
        user_message: str,
        *,
        context: dict[str, Any] | None = None,
        memory_agent: Any | None = None,
    ) -> dict[str, Any]:
        context = context or {}
        trace: list[dict[str, Any]] = []

        safety_result = self.safety.check(user_message)
        trace.append(
            self._trace_step(
                "safety_check",
                "SafetyAgent",
                "screened request for blocked prompt-injection markers",
                "blocked" if not safety_result["safe"] else "passed",
                safety_result,
            )
        )
        if not safety_result["safe"]:
            return {
                "response": "I cannot help with requests that try to bypass the assistant rules.",
                "intent": "safety",
                "language": "en",
                "agent": "safety_agent",
                "trace": trace,
                "payload": safety_result,
            }

        routed_input = self.router.route(user_message)
        trace.append(
            self._trace_step(
                "route_input",
                "InputRouterAgent",
                "detected intent and language",
                "completed",
                {
                    "intent": routed_input["intent"],
                    "language": routed_input["language"],
                    "confidence": routed_input["confidence"],
                    "signals": routed_input["signals"],
                },
            )
        )

        selected_agent = self.decide(routed_input)
        trace.append(
            self._trace_step(
                "select_agent",
                "SupervisorAgent",
                f"selected {selected_agent}",
                "completed",
                {"intent": routed_input["intent"]},
            )
        )

        agent_result = self._run_selected_agent(
            selected_agent=selected_agent,
            routed_input=routed_input,
            context=context,
            memory_agent=memory_agent,
        )
        trace.extend(agent_result.pop("trace_steps", []))
        trace.append(
            self._trace_step(
                "final_response",
                "ResponseAgent",
                "prepared student-facing response",
                "completed",
                {"agent": selected_agent},
            )
        )

        return {
            "response": agent_result["response"],
            "intent": routed_input["intent"],
            "language": routed_input["language"],
            "agent": selected_agent,
            "trace": trace,
            "payload": agent_result.get("payload", {}),
        }

    def create_study_plan(
        self,
        profile: dict[str, Any],
        *,
        memory_agent: Any | None = None,
        student_email: str | None = None,
        student_name: str | None = None,
    ) -> dict[str, Any]:
        trace = [
            self._trace_step(
                "receive_profile",
                "SupervisorAgent",
                "received study-plan form data",
                "completed",
                {"course_name": profile.get("course_name"), "daily_hours": profile.get("daily_hours")},
            ),
            self._trace_step(
                "select_agent",
                "SupervisorAgent",
                "selected study_planner_agent",
                "completed",
                {"intent": "study_plan"},
            ),
        ]

        planner_result = self.study_planner.generate(profile)
        plan = planner_result["plan"]
        trace.append(
            self._trace_step(
                "generate_plan",
                "StudyPlannerAgent",
                planner_result["summary"],
                "completed",
                {
                    "tasks": len(plan["tasks"]),
                    "weak_topics": plan["weak_topics"],
                    "exam_date": plan["exam_date"],
                },
            )
        )

        sync_result = {"ok": False, "reason": "Memory agent was not provided."}
        if memory_agent is not None:
            sync_result = memory_agent.sync_study_plan(
                course_name=plan["course_name"],
                exam_date=planner_result["exam_date"],
                daily_hours=plan["daily_hours"],
                weak_topics=plan["weak_topics"],
                other_topics=plan["other_topics"],
                tasks=plan["tasks"],
                student_email=student_email,
                student_name=student_name,
            )

        trace.append(
            self._trace_step(
                "sync_memory",
                "MemoryAgent",
                "stored the generated study plan when cloud memory is configured",
                "completed" if sync_result["ok"] else "skipped",
                sync_result,
            )
        )

        return {
            "ok": True,
            "plan": plan,
            "summary": planner_result["summary"],
            "sync_result": sync_result,
            "trace": trace,
        }

    def _run_selected_agent(
        self,
        *,
        selected_agent: str,
        routed_input: dict[str, Any],
        context: dict[str, Any],
        memory_agent: Any | None,
    ) -> dict[str, Any]:
        if selected_agent == "study_planner_agent":
            return self._run_study_planner(routed_input=routed_input, context=context)
        if selected_agent == "quiz_generator_agent":
            return self._run_quiz_generator(context=context)
        if selected_agent == "course_rag_agent":
            return self._run_course_rag(routed_input=routed_input, context=context)
        if selected_agent == "memory_agent":
            return self._run_memory_agent(memory_agent=memory_agent)
        return self._run_response_agent(context=context)

    def _run_study_planner(self, *, routed_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        message = routed_input["message"].lower()
        active_plan = context.get("active_plan")
        if "weak" in message or "priority" in message or "prioritize" in message:
            planner_result = self.study_planner.explain_priorities(active_plan)
            action = "explained weak-topic prioritization"
        else:
            planner_result = self.study_planner.recommend_next(active_plan)
            action = "recommended the next study task"

        return {
            "response": planner_result["response"],
            "payload": planner_result,
            "trace_steps": [
                self._trace_step(
                    "run_agent",
                    "StudyPlannerAgent",
                    action,
                    "completed" if planner_result["ok"] else "needs_plan",
                    {"has_active_plan": active_plan is not None},
                )
            ],
        }

    def _run_quiz_generator(self, *, context: dict[str, Any]) -> dict[str, Any]:
        active_plan = context.get("active_plan")
        topic = "your next weak topic"
        if active_plan and active_plan.get("weak_topics"):
            topic = active_plan["weak_topics"][0]
        quiz_result = self.quiz_generator.generate(topic=topic, count=5)
        return {
            "response": f"I routed this to the Quiz Generator Agent. Use the Quiz page to create a focused quiz on {topic}.",
            "payload": quiz_result,
            "trace_steps": [
                self._trace_step("run_agent", "QuizGeneratorAgent", "prepared quiz recommendation", "completed", {"topic": topic})
            ],
        }

    def _run_course_rag(self, *, routed_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        uploads = context.get("uploads", [])
        rag_result = self.course_rag.answer(routed_input["message"])
        if uploads:
            response = (
                f"I routed this to the Course RAG Agent. I can see {len(uploads)} uploaded file(s), "
                "but indexing and retrieval are Phase 5."
            )
        else:
            response = "I routed this to the Course RAG Agent. Upload materials first so Phase 5 can index them."

        return {
            "response": response,
            "payload": rag_result,
            "trace_steps": [
                self._trace_step(
                    "run_agent",
                    "CourseRAGAgent",
                    "checked course-material readiness",
                    "pending_phase_5",
                    {"uploaded_files": len(uploads)},
                )
            ],
        }

    def _run_memory_agent(self, *, memory_agent: Any | None) -> dict[str, Any]:
        if memory_agent is None:
            status = {"enabled": False, "reason": "Memory agent was not provided."}
        else:
            status = memory_agent.status()

        response = "Memory Agent is active and ready."
        if not status["enabled"]:
            response = f"Memory Agent is active locally, but cloud memory is not configured: {status['reason']}"

        return {
            "response": response,
            "payload": status,
            "trace_steps": [
                self._trace_step("run_agent", "MemoryAgent", "checked persistent memory status", "completed", status)
            ],
        }

    def _run_response_agent(self, *, context: dict[str, Any]) -> dict[str, Any]:
        has_active_plan = context.get("active_plan") is not None
        response = "I can help with your active plan, quizzes, uploaded materials, or progress memory."
        if not has_active_plan:
            response = "I am ready to help with planning, revision, and quizzes. Ask me what to study next."
        return {
            "response": response,
            "payload": {"has_active_plan": has_active_plan},
            "trace_steps": [
                self._trace_step(
                    "run_agent",
                    "ResponseAgent",
                    "handled general study-coach reply",
                    "completed",
                    {"has_active_plan": has_active_plan},
                )
            ],
        }

    def _trace_step(
        self,
        step: str,
        agent: str,
        action: str,
        status: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds"),
            "step": step,
            "agent": agent,
            "action": action,
            "status": status,
            "details": details,
        }

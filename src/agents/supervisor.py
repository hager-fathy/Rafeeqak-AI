from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from src.agents.course_rag import CourseRAGAgent
from src.agents.database_query import DatabaseQueryAgent
from src.agents.input_router import InputRouterAgent
from src.agents.progress_evaluator import ProgressEvaluatorAgent
from src.agents.quiz_generator import QuizGeneratorAgent
from src.agents.safety_agent import SafetyAgent
from src.agents.study_planner import StudyPlannerAgent
from src.tools.semantic_cache import SemanticResponseCache


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
        database_query: DatabaseQueryAgent | None = None,
        semantic_cache: SemanticResponseCache | None = None,
        safety: SafetyAgent | None = None,
    ) -> None:
        self.router = router or InputRouterAgent()
        self.study_planner = study_planner or StudyPlannerAgent()
        self.course_rag = course_rag or CourseRAGAgent()
        self.quiz_generator = quiz_generator or QuizGeneratorAgent()
        self.progress_evaluator = progress_evaluator or ProgressEvaluatorAgent()
        self.database_query = database_query or DatabaseQueryAgent()
        self.semantic_cache = semantic_cache or SemanticResponseCache()
        self.safety = safety or SafetyAgent()

    def decide(self, routed_input: dict[str, Any]) -> str:
        intent = routed_input.get("intent", "chat")
        mapping = {
            "study_plan": "study_planner_agent",
            "quiz": "quiz_generator_agent",
            "course_material": "course_rag_agent",
            "upload": "course_rag_agent",
            "database_query": "database_query_agent",
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
        message_language = "ar" if self.router._contains_arabic(user_message) else "en"

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
                "response": self._safety_response(message_language),
                "intent": "safety",
                "language": message_language,
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

        context_fingerprint = self._context_fingerprint(context)
        cached_result = self.semantic_cache.lookup(
            message=routed_input["message"],
            language=routed_input["language"],
            context_fingerprint=context_fingerprint,
        )
        if cached_result is not None:
            trace.append(
                self._trace_step(
                    "cache_lookup",
                    "SemanticCache",
                    "served a repeated question from the local semantic cache",
                    "hit",
                    {
                        "similarity": cached_result["similarity"],
                        "hits": cached_result["hits"],
                    },
                )
            )
            trace.append(
                self._trace_step(
                    "final_response",
                    "ResponseAgent",
                    "prepared cached student-facing response",
                    "completed",
                    {"agent": cached_result["agent"]},
                )
            )
            return {
                "response": cached_result["response"],
                "intent": cached_result["intent"],
                "language": routed_input["language"],
                "agent": cached_result["agent"],
                "trace": trace,
                "payload": {
                    **cached_result.get("payload", {}),
                    "cache": {
                        "hit": True,
                        "similarity": cached_result["similarity"],
                        "cached_at_utc": cached_result["cached_at_utc"],
                    },
                },
            }

        trace.append(
            self._trace_step(
                "cache_lookup",
                "SemanticCache",
                "checked local semantic cache for a reusable answer",
                "miss",
                {"context_fingerprint": context_fingerprint},
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

        self.semantic_cache.store(
            message=routed_input["message"],
            language=routed_input["language"],
            intent=routed_input["intent"],
            agent=selected_agent,
            response=agent_result["response"],
            payload=agent_result.get("payload", {}),
            context_fingerprint=context_fingerprint,
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
            return self._run_quiz_generator(routed_input=routed_input, context=context)
        if selected_agent == "course_rag_agent":
            return self._run_course_rag(routed_input=routed_input, context=context)
        if selected_agent == "database_query_agent":
            return self._run_database_query(routed_input=routed_input, context=context, memory_agent=memory_agent)
        if selected_agent == "memory_agent":
            return self._run_memory_agent(routed_input=routed_input, memory_agent=memory_agent)
        return self._run_response_agent(routed_input=routed_input, context=context)

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
            "response": self._study_planner_response(planner_result, active_plan, routed_input["language"]),
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

    def _run_quiz_generator(self, *, routed_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        active_plan = context.get("active_plan")
        fallback_topic = "your next weak topic"
        if active_plan and active_plan.get("weak_topics"):
            fallback_topic = active_plan["weak_topics"][0]
        topic = self.quiz_generator.infer_topic(routed_input["message"], fallback=fallback_topic)
        context_matches = self.course_rag.indexer.search(topic, top_k=3)
        context_chunks = [
            {
                "source_name": match.source_name,
                "section": match.section,
                "text": match.text,
                "score": match.score,
            }
            for match in context_matches
        ]
        quiz_result = self.quiz_generator.generate(
            topic=topic,
            count=5,
            context_chunks=context_chunks,
            language=routed_input["language"],
        )
        if routed_input["language"] == "ar":
            response = f"جهزت لك اختبارا من {quiz_result['count']} أسئلة عن {topic}. افتح صفحة Quiz للإجابة عليه."
        else:
            response = f"I prepared a {quiz_result['count']}-question quiz on {topic}. Open the Quiz page to answer it."
        return {
            "response": response,
            "payload": quiz_result,
            "trace_steps": [
                self._trace_step(
                    "run_agent",
                    "QuizGeneratorAgent",
                    "generated a focused quiz and flashcards",
                    "completed",
                    {
                        "topic": topic,
                        "questions": quiz_result["count"],
                        "source_chunks": len(context_chunks),
                    },
                )
            ],
        }

    def _run_course_rag(self, *, routed_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        uploads = context.get("uploads", [])
        rag_result = self.course_rag.answer(routed_input["message"], language=routed_input["language"])
        response = rag_result["response"]

        return {
            "response": response,
            "payload": rag_result,
            "trace_steps": [
                self._trace_step(
                    "run_agent",
                    "CourseRAGAgent",
                    "retrieved relevant course-material chunks",
                    "completed" if rag_result["ok"] else rag_result["status"],
                    {
                        "uploaded_files": len(uploads),
                        "indexed_files": rag_result["stats"]["files"],
                        "indexed_chunks": rag_result["stats"]["chunks"],
                        "citations": rag_result["citations"],
                    },
                )
            ],
        }

    def _run_database_query(
        self,
        *,
        routed_input: dict[str, Any],
        context: dict[str, Any],
        memory_agent: Any | None,
    ) -> dict[str, Any]:
        query_result = self.database_query.answer(
            message=routed_input["message"],
            context=context,
            memory_agent=memory_agent,
            language=routed_input["language"],
        )
        return {
            "response": query_result["response"],
            "payload": query_result,
            "trace_steps": [
                self._trace_step(
                    "run_agent",
                    "DatabaseQueryAgent",
                    "answered a structured progress or deadline query",
                    "completed",
                    {
                        "query_type": query_result["query_type"],
                        "snapshot_used": query_result["snapshot_used"],
                    },
                )
            ],
        }

    def _run_memory_agent(self, *, routed_input: dict[str, Any], memory_agent: Any | None) -> dict[str, Any]:
        if memory_agent is None:
            status = {"enabled": False, "reason": "Memory agent was not provided."}
        else:
            status = memory_agent.status()

        response = "Memory Agent is active and ready."
        if not status["enabled"]:
            response = f"Memory Agent is active locally, but cloud memory is not configured: {status['reason']}"
        if routed_input["language"] == "ar":
            response = "وكيل الذاكرة يعمل وجاهز."
            if not status["enabled"]:
                response = f"وكيل الذاكرة يعمل محليا، لكن الذاكرة السحابية غير مفعلة: {status['reason']}"

        return {
            "response": response,
            "payload": status,
            "trace_steps": [
                self._trace_step("run_agent", "MemoryAgent", "checked persistent memory status", "completed", status)
            ],
        }

    def _run_response_agent(self, *, routed_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        has_active_plan = context.get("active_plan") is not None
        response = "I can help with your active plan, quizzes, uploaded materials, or progress memory."
        if not has_active_plan:
            response = "I am ready to help with planning, revision, and quizzes. Ask me what to study next."
        if routed_input["language"] == "ar":
            response = "أقدر أساعدك في الخطة الحالية، الاختبارات، المواد المرفوعة، أو متابعة تقدمك."
            if not has_active_plan:
                response = "أنا جاهز أساعدك في التخطيط والمراجعة والاختبارات. اسألني ماذا تذاكر بعد ذلك."
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

    def _safety_response(self, language: str) -> str:
        if language == "ar":
            return "لا أستطيع المساعدة في طلبات تحاول تجاوز قواعد المساعد."
        return "I cannot help with requests that try to bypass the assistant rules."

    def _study_planner_response(
        self,
        planner_result: dict[str, Any],
        active_plan: dict[str, Any] | None,
        language: str,
    ) -> str:
        if language != "ar":
            return planner_result["response"]
        if not active_plan:
            if planner_result["ok"]:
                return "لا توجد خطة نشطة حاليا. افتح صفحة Study Plan وأنشئ خطة أولا."
            if "prioritize" in planner_result["response"].lower():
                return "أضف نقاط ضعفك في صفحة Study Plan، وبعدها أقدر أرتبها حسب الأولوية في جدولك."
            return "لا توجد خطة دراسة بعد. افتح صفحة Study Plan وأنشئ خطة أولا."

        task = planner_result.get("task")
        if task:
            checkpoint_note = " وتتضمن أيضا اختبارا قصيرا." if task.get("checkpoint") else ""
            return f"اليوم ركز على {task['topic']} لمدة {task['hours']} ساعة. الهدف: ادرس الموضوع واكتب ملخصا قصيرا.{checkpoint_note}"

        weak_topics = active_plan.get("weak_topics", [])
        if weak_topics:
            return f"خطتك الحالية تعطي نقاط الضعف فرصا إضافية قبل باقي الموضوعات. موضوعات الأولوية: {', '.join(weak_topics)}."
        return "خطتك الحالية لا تحتوي على نقاط ضعف محددة، لذلك توزع المراجعة بالتساوي بين الموضوعات."

    def _context_fingerprint(self, context: dict[str, Any]) -> str:
        active_plan = context.get("active_plan") or {}
        tasks = active_plan.get("tasks", []) if isinstance(active_plan, dict) else []
        quiz_attempts = context.get("quiz_attempts", []) or []
        uploads = context.get("uploads", []) or []
        fingerprint_data = {
            "course": active_plan.get("course_name") if isinstance(active_plan, dict) else None,
            "exam_date": active_plan.get("exam_date") if isinstance(active_plan, dict) else None,
            "tasks": len(tasks),
            "completed_tasks": sum(1 for task in tasks if task.get("completed")),
            "weak_topics": active_plan.get("weak_topics", []) if isinstance(active_plan, dict) else [],
            "quiz_attempts": len(quiz_attempts),
            "last_quiz_time": quiz_attempts[-1].get("timestamp_utc") if quiz_attempts else None,
            "uploads": len(uploads),
        }
        encoded = json.dumps(fingerprint_data, sort_keys=True, default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]

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

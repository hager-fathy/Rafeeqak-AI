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
from src.agents.reminder_agent import ReminderAgent
from src.agents.safety_agent import SafetyAgent
from src.agents.study_planner import StudyPlannerAgent
from src.localization import DEFAULT_LANGUAGE, detect_language, normalize_language, t
from src.prompts import build_system_prompt
from src.tools.llm_client import LLMClient
from src.tools.output_filter import filter_output
from src.tools.quiz_history import quiz_history_avoid_questions
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
        reminder_agent: ReminderAgent | None = None,
        semantic_cache: SemanticResponseCache | None = None,
        safety: SafetyAgent | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.router = router or InputRouterAgent()
        self.study_planner = study_planner or StudyPlannerAgent()
        self.course_rag = course_rag or CourseRAGAgent()
        self.quiz_generator = quiz_generator or QuizGeneratorAgent()
        self.progress_evaluator = progress_evaluator or ProgressEvaluatorAgent()
        self.database_query = database_query or DatabaseQueryAgent()
        self.reminder_agent = reminder_agent or ReminderAgent()
        self.semantic_cache = semantic_cache or SemanticResponseCache()
        self.safety = safety or SafetyAgent()
        self.llm_client = llm_client or getattr(self.course_rag, "llm_client", None) or LLMClient()

    def decide(self, routed_input: dict[str, Any]) -> str:
        intent = routed_input.get("intent", "chat")
        mapping = {
            "study_plan": "study_planner_agent",
            "quiz": "quiz_generator_agent",
            "course_material": "course_rag_agent",
            "upload": "course_rag_agent",
            "database_query": "database_query_agent",
            "memory": "memory_agent",
            "reminder": "reminder_agent",
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
        preferred_language = normalize_language(context.get("selected_language"))
        input_language = detect_language(user_message)
        response_language = "ar" if input_language == "ar" else preferred_language

        safety_result = self.safety.check(user_message)
        safety_status = str(
            safety_result.get("safety_status")
            or ("passed" if safety_result["safe"] else "blocked")
        )
        trace.append(
            self._trace_step(
                "safety_check",
                "SafetyAgent",
                "screened request for blocked prompt-injection markers",
                safety_status,
                {**safety_result, "safety_status": safety_status},
            )
        )
        if safety_status == "blocked" or not safety_result["safe"]:
            return self._finalize_handle_message_result(
                {
                    "response": self._safety_response(response_language),
                    "intent": "safety",
                    "language": response_language,
                    "agent": "safety_agent",
                    "trace": trace,
                    "payload": safety_result,
                }
            )

        routed_input = self.router.route(user_message)
        if routed_input["language"] != "ar":
            routed_input["language"] = response_language
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

        course_required_agents = {
            "study_planner_agent",
            "quiz_generator_agent",
            "course_rag_agent",
            "database_query_agent",
            "reminder_agent",
        }
        if (
            context.get("require_active_course")
            and selected_agent in course_required_agents
            and not context.get("active_course_id")
        ):
            validation_payload = {
                "active_course_required": True,
                "intent": routed_input["intent"],
            }
            trace.append(
                self._trace_step(
                    "validate_course_scope",
                    "SupervisorAgent",
                    "required an active course before running a course-scoped agent",
                    "blocked",
                    validation_payload,
                )
            )
            return self._finalize_handle_message_result(
                {
                    "response": self._course_required_response(routed_input["language"]),
                    "intent": routed_input["intent"],
                    "language": routed_input["language"],
                    "agent": "course_scope_validator",
                    "trace": trace,
                    "payload": validation_payload,
                }
            )

        self._sync_plan_completion_context(context)
        context_fingerprint = self._context_fingerprint(context)
        cacheable = self._is_cacheable(selected_agent, routed_input)
        if cacheable:
            cached_result = self.semantic_cache.lookup(
                message=routed_input["message"],
                language=routed_input["language"],
                course_id=context.get("active_course_id"),
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
                return self._finalize_handle_message_result(
                    {
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
                )

            trace.append(
                self._trace_step(
                    "cache_lookup",
                    "SemanticCache",
                    "checked local semantic cache for a reusable answer",
                    "miss",
                    {
                        "active_course_id": context.get("active_course_id"),
                        "context_fingerprint": context_fingerprint,
                    },
                )
            )
        else:
            trace.append(
                self._trace_step(
                    "cache_lookup",
                    "SemanticCache",
                    "skipped cache for a state-changing request",
                    "skipped",
                    {"agent": selected_agent},
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

        pending_result = {
            "response": agent_result["response"],
            "intent": routed_input["intent"],
            "language": routed_input["language"],
            "agent": selected_agent,
            "trace": trace,
            "payload": agent_result.get("payload", {}),
        }
        finalized = self._finalize_handle_message_result(pending_result)

        if cacheable:
            self.semantic_cache.store(
                message=routed_input["message"],
                language=routed_input["language"],
                intent=routed_input["intent"],
                agent=selected_agent,
                response=finalized["response"],
                payload=agent_result.get("payload", {}),
                course_id=context.get("active_course_id"),
                context_fingerprint=context_fingerprint,
            )

        return finalized

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
        if selected_agent == "reminder_agent":
            return self._run_reminder_agent(routed_input=routed_input, context=context)
        if selected_agent == "memory_agent":
            return self._run_memory_agent(routed_input=routed_input, memory_agent=memory_agent)
        return self._run_response_agent(routed_input=routed_input, context=context)

    def _run_study_planner(self, *, routed_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        message = routed_input["message"].lower()
        active_plan = context.get("active_plan")
        priority_terms = ("weak", "priority", "prioritize", "ضعف", "أولوية", "اولويه")
        if any(term in message for term in priority_terms):
            planner_result = self.study_planner.explain_priorities(
                active_plan,
                language=routed_input["language"],
            )
            action = "explained weak-topic prioritization"
        else:
            planner_result = self.study_planner.recommend_next(
                active_plan,
                course_scope=context.get("active_course_id"),
                today_only=self._prefers_today_task(routed_input["message"]),
                language=routed_input["language"],
            )
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
        if context.get("active_course_id"):
            self.course_rag.indexer.index_all(
                course_id=context.get("active_course_id"),
                course_name=context.get("active_course_name"),
            )
        context_matches = self.course_rag.indexer.search(
            topic,
            top_k=5,
            course_id=context.get("active_course_id"),
        )
        context_chunks = [
            {
                "source_name": match.source_name,
                "section": match.section,
                "chunk_index": match.chunk_index,
                "course_name": context.get("active_course_name"),
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
            difficulty=context.get("quiz_difficulty", "medium"),
            question_types=context.get("question_types") or ["mcq"],
            previous_questions=quiz_history_avoid_questions(
                context.get("generated_questions") or [],
                course_id=context.get("active_course_id"),
                topic=topic,
            ),
            weak_topics=self._weak_topics_for_quiz(context, requested_topic=topic),
        )
        response = t("agent.quiz.prepared", routed_input["language"], count=quiz_result["count"], topic=topic)
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

    def _weak_topics_for_quiz(self, context: dict[str, Any], *, requested_topic: str) -> list[str]:
        active_plan = context.get("active_plan") if isinstance(context.get("active_plan"), dict) else {}
        raw_topics: list[str] = list(active_plan.get("weak_topics", []) or [])
        for attempt in list(context.get("quiz_attempts", []) or [])[-8:]:
            if not isinstance(attempt, dict):
                continue
            raw_topics.extend(attempt.get("weak_topics", []) or [])
            try:
                score = float(attempt.get("score_percent", 100))
            except (TypeError, ValueError):
                score = 100.0
            topic = str(attempt.get("topic") or "").strip()
            if topic and score < 70:
                raw_topics.append(topic)

        topics = []
        seen: set[str] = set()
        for item in raw_topics:
            topic = " ".join(str(item or "").split())
            key = topic.casefold()
            if not topic or key in seen:
                continue
            topics.append(topic)
            seen.add(key)
            if len(topics) == 8:
                break
        requested = " ".join(str(requested_topic or "").split())
        if requested and requested.casefold() not in seen:
            topics.append(requested)
        return topics[:8]

    def _run_course_rag(self, *, routed_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        uploads = context.get("uploads", [])
        rag_result = self.course_rag.answer(
            routed_input["message"],
            language=routed_input["language"],
            course_id=context.get("active_course_id"),
            course_name=context.get("active_course_name"),
            memory=self._chatbot_memory_context(context),
        )
        action = (
            "asked for a clearer topic before retrieving course-material chunks"
            if rag_result["status"] == "needs_clarification"
            else "retrieval returned zero active-course chunks and asked for clarification"
            if rag_result["status"] == "no_relevant_match"
            else "retrieved relevant course-material chunks"
        )
        return {
            "response": rag_result["response"],
            "payload": rag_result,
            "trace_steps": [
                self._trace_step(
                    "run_agent",
                    "CourseRAGAgent",
                    action,
                    "completed" if rag_result["ok"] else rag_result["status"],
                    {
                        "uploaded_files": len(uploads),
                        "indexed_files": rag_result["stats"]["files"],
                        "indexed_chunks": rag_result["stats"]["chunks"],
                        "citations": rag_result["citations"],
                        "retrieved_chunk_course_ids": [
                            match.get("course_id") for match in rag_result.get("matches", [])
                        ],
                        **rag_result.get("diagnostics", {}),
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

        response = t("agent.memory.ready", routed_input["language"])
        if not status["enabled"]:
            response = t("agent.memory.local", routed_input["language"], reason=status["reason"])

        return {
            "response": response,
            "payload": status,
            "trace_steps": [
                self._trace_step("run_agent", "MemoryAgent", "checked persistent memory status", "completed", status)
            ],
        }

    def _run_reminder_agent(self, *, routed_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        reminder_result = self.reminder_agent.create(
            message=routed_input["message"],
            context=context,
            language=routed_input["language"],
        )
        return {
            "response": reminder_result["response"],
            "payload": reminder_result,
            "trace_steps": [
                self._trace_step(
                    "run_agent",
                    "ReminderAgent",
                    "created course-scoped reminder records",
                    "completed" if reminder_result["ok"] else reminder_result["status"],
                    {
                        "created_count": reminder_result["created_count"],
                        "total_reminders": len(reminder_result["reminders"]),
                    },
                )
            ],
        }

    def _run_response_agent(self, *, routed_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        has_active_plan = context.get("active_plan") is not None
        llm_response = self._compose_general_chat_response(routed_input=routed_input, context=context)
        if llm_response:
            return {
                "response": llm_response,
                "payload": {
                    "has_active_plan": has_active_plan,
                    "generation_mode": "llm",
                    "memory_context_used": bool(self._chatbot_memory_context(context)),
                },
                "trace_steps": [
                    self._trace_step(
                        "run_agent",
                        "ResponseAgent",
                        "handled general study-coach reply with the chatbot prompt",
                        "completed",
                        {"has_active_plan": has_active_plan, "generation_mode": "llm"},
                    )
                ],
            }

        response_key = "agent.response.ready" if has_active_plan else "agent.response.no_plan"
        return {
            "response": t(response_key, routed_input["language"]),
            "payload": {"has_active_plan": has_active_plan, "generation_mode": "fallback"},
            "trace_steps": [
                self._trace_step(
                    "run_agent",
                    "ResponseAgent",
                    "handled general study-coach reply with local fallback",
                    "completed",
                    {"has_active_plan": has_active_plan},
                )
            ],
        }

    def _compose_general_chat_response(
        self,
        *,
        routed_input: dict[str, Any],
        context: dict[str, Any],
    ) -> str | None:
        if not getattr(self.llm_client, "is_available", False):
            return None

        language = routed_input["language"]
        response_language = "Arabic" if language == "ar" else "English"
        system_prompt = build_system_prompt(
            course_name=context.get("active_course_name") or ("هذا المقرر" if language == "ar" else "this course"),
            course_id=context.get("active_course_id") or "",
            language=response_language,
            memory=self._chatbot_memory_context(context),
            context="No source material retrieved for this query.",
        )
        user_prompt = (
            "Student question:\n"
            f"{routed_input['message']}\n\n"
            f"Answer in {response_language}:"
        )
        try:
            return self.llm_client.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=500,
            )
        except Exception:
            return None

    def _chatbot_memory_context(self, context: dict[str, Any]) -> str:
        course_id = context.get("active_course_id")
        course_name = context.get("active_course_name")
        active_plan = context.get("active_plan") if isinstance(context.get("active_plan"), dict) else {}
        if not active_plan and not context.get("quiz_attempts") and not context.get("reminders"):
            return ""

        from src.tools.study_plan_tasks import is_task_completed, list_pending_tasks

        tasks = active_plan.get("tasks", []) if isinstance(active_plan, dict) else []
        completed_tasks = [
            task
            for task in tasks
            if isinstance(task, dict) and is_task_completed(task, active_plan)
        ]
        pending_tasks = list_pending_tasks(active_plan, course_scope=course_id) if active_plan else []
        weak_topics = list(active_plan.get("weak_topics", []) if isinstance(active_plan, dict) else [])
        quiz_attempts = [item for item in context.get("quiz_attempts", []) or [] if isinstance(item, dict)]
        for attempt in quiz_attempts:
            weak_topics.extend(attempt.get("weak_topics", []) or [])
        reminders = [item for item in context.get("reminders", []) or [] if isinstance(item, dict)]
        pending_reminders = [item for item in reminders if item.get("status") != "done"]

        lines = [
            f"Active course: {course_name or 'Unknown course'}",
            f"Active course ID: {course_id or 'unknown'}",
        ]
        if active_plan:
            lines.extend(
                [
                    f"Exam date: {active_plan.get('exam_date') or 'not set'}",
                    f"Pending tasks: {len(pending_tasks)}",
                    f"Completed tasks: {len(completed_tasks)}",
                ]
            )
            if pending_tasks:
                pending_preview = [
                    self._task_memory_line(task)
                    for task in pending_tasks[:5]
                    if isinstance(task, dict)
                ]
                lines.append("Pending task preview: " + "; ".join(pending_preview))
            if completed_tasks:
                completed_preview = [
                    self._task_memory_line(task)
                    for task in completed_tasks[-3:]
                    if isinstance(task, dict)
                ]
                lines.append("Recently completed tasks: " + "; ".join(completed_preview))

        unique_weak_topics = self._unique_strings(weak_topics)
        if unique_weak_topics:
            lines.append("Weak topics: " + ", ".join(unique_weak_topics[:8]))
        if quiz_attempts:
            latest_quiz = quiz_attempts[-1]
            lines.append(
                "Latest quiz: "
                f"{latest_quiz.get('topic') or 'unknown topic'} "
                f"score {latest_quiz.get('score_percent', 'unknown')}%"
            )
        if pending_reminders:
            lines.append(f"Pending reminders: {len(pending_reminders)}")
        chat_summaries = [item for item in context.get("chat_summaries", []) or [] if isinstance(item, dict)]
        if chat_summaries:
            latest_summary = chat_summaries[-1]
            summary_text = " ".join(str(latest_summary.get("summary") or "").split())
            if summary_text:
                lines.append(f"Latest chat summary: {summary_text[:300]}")
        return "\n".join(lines)

    def _task_memory_line(self, task: dict[str, Any]) -> str:
        topic = " ".join(str(task.get("topic") or "untitled task").split())
        date = " ".join(str(task.get("date") or "unscheduled").split())
        phase = " ".join(str(task.get("phase") or "").split())
        hours = task.get("hours")
        parts = [topic, date]
        if phase:
            parts.append(phase)
        if hours:
            parts.append(f"{hours}h")
        return " / ".join(parts)

    def _unique_strings(self, values: list[Any]) -> list[str]:
        unique = []
        seen: set[str] = set()
        for value in values:
            normalized = " ".join(str(value or "").split())
            key = normalized.casefold()
            if not normalized or key in seen:
                continue
            unique.append(normalized)
            seen.add(key)
        return unique

    def _filter_student_response(self, response: str, language: str) -> str:
        return filter_output(response, language)

    def _finalize_handle_message_result(self, result: dict[str, Any]) -> dict[str, Any]:
        language = str(result.get("language") or DEFAULT_LANGUAGE)
        original = str(result.get("response") or "")
        filtered = self._filter_student_response(original, language)
        if filtered == original:
            return result

        trace = list(result.get("trace") or [])
        trace.append(
            self._trace_step(
                "filter_output",
                "ResponseAgent",
                "sanitized assistant response before display",
                "filtered",
                {
                    "original_length": len(original),
                    "filtered_length": len(filtered),
                },
            )
        )
        updated = dict(result)
        updated["response"] = filtered
        updated["trace"] = trace
        payload = dict(updated.get("payload") or {})
        payload["output_filtered"] = True
        updated["payload"] = payload
        return updated

    def _safety_response(self, language: str) -> str:
        return t("agent.safety", language)

    def _course_required_response(self, language: str) -> str:
        return t("agent.course_required", language)

    def _sync_plan_completion_context(self, context: dict[str, Any]) -> None:
        active_plan = context.get("active_plan")
        if not isinstance(active_plan, dict):
            return
        course_scope = context.get("active_course_id") or active_plan.get("course_name")
        if not course_scope:
            return
        from src.tools.study_plan_tasks import sync_completion_fields

        sync_completion_fields(active_plan, course_scope=str(course_scope))

    def _prefers_today_task(self, message: str) -> bool:
        lowered = str(message or "").casefold()
        today_terms = {
            "today",
            "اليوم",
            "النهارده",
            "نهارده",
            "انهارده",
            "انهرض",
        }
        return any(term in lowered for term in today_terms)

    def _study_planner_response(
        self,
        planner_result: dict[str, Any],
        active_plan: dict[str, Any] | None,
        language: str,
    ) -> str:
        del active_plan
        return str(planner_result.get("response") or "")

    def _context_fingerprint(self, context: dict[str, Any]) -> str:
        active_plan = context.get("active_plan") or {}
        tasks = active_plan.get("tasks", []) if isinstance(active_plan, dict) else []
        quiz_attempts = context.get("quiz_attempts", []) or []
        uploads = context.get("uploads", []) or []
        reminders = context.get("reminders", []) or []
        weak_topics = active_plan.get("weak_topics", []) if isinstance(active_plan, dict) else []
        fingerprint_data = {
            "course": active_plan.get("course_name") if isinstance(active_plan, dict) else None,
            "active_course_id": context.get("active_course_id"),
            "active_course_name": context.get("active_course_name"),
            "language": normalize_language(context.get("selected_language")),
            "exam_date": active_plan.get("exam_date") if isinstance(active_plan, dict) else None,
            "daily_hours": active_plan.get("daily_hours") if isinstance(active_plan, dict) else None,
            "difficulty": active_plan.get("difficulty") if isinstance(active_plan, dict) else None,
            "other_topics": active_plan.get("other_topics", []) if isinstance(active_plan, dict) else [],
            "tasks": self._stable_digest(
                [
                    {
                        "task_id": task.get("task_id"),
                        "date": task.get("date"),
                        "topic": task.get("topic"),
                        "phase": task.get("phase"),
                        "hours": task.get("hours"),
                        "completed": bool(task.get("completed")),
                        "checkpoint": bool(task.get("checkpoint")),
                    }
                    for task in tasks
                    if isinstance(task, dict)
                ]
            ),
            "weak_topics": self._stable_digest(sorted(str(topic) for topic in weak_topics)),
            "quiz_attempts": self._stable_digest(
                [
                    {
                        "timestamp_utc": attempt.get("timestamp_utc"),
                        "topic": attempt.get("topic"),
                        "difficulty": attempt.get("difficulty"),
                        "score_percent": attempt.get("score_percent"),
                        "question_types": attempt.get("question_types", []),
                        "weak_topics": attempt.get("weak_topics", []),
                        "points_earned": attempt.get("points_earned"),
                        "total_points": attempt.get("total_points"),
                    }
                    for attempt in quiz_attempts
                    if isinstance(attempt, dict)
                ]
            ),
            "uploads": self._stable_digest(
                [
                    {
                        "original_name": upload.get("original_name"),
                        "stored_name": upload.get("stored_name"),
                        "course_id": upload.get("course_id"),
                        "course_name": upload.get("course_name"),
                        "saved_at_utc": upload.get("saved_at_utc"),
                    }
                    for upload in uploads
                    if isinstance(upload, dict)
                ]
            ),
            "reminders": self._stable_digest(
                [
                    {
                        "title": reminder.get("title"),
                        "reminder_type": reminder.get("reminder_type"),
                        "due_at": reminder.get("due_at"),
                        "status": reminder.get("status"),
                        "source": reminder.get("source"),
                    }
                    for reminder in reminders
                    if isinstance(reminder, dict)
                ]
            ),
            "all_courses": self._stable_digest(context.get("all_courses", []) or []),
        }
        encoded = json.dumps(fingerprint_data, sort_keys=True, default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]

    def _stable_digest(self, value: Any) -> str:
        encoded = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]

    def _is_cacheable(self, selected_agent: str, routed_input: dict[str, Any] | None = None) -> bool:
        routed_input = routed_input or {}
        if selected_agent in {
            "quiz_generator_agent",
            "reminder_agent",
            "memory_agent",
            "study_planner_agent",
        }:
            return False
        if routed_input.get("intent") in {"quiz", "upload", "reminder", "memory"}:
            return False
        return not self._looks_state_changing_message(str(routed_input.get("message") or ""))

    def _looks_state_changing_message(self, message: str) -> bool:
        lowered = message.casefold()
        state_changing_terms = {
            "add",
            "change",
            "create",
            "delete",
            "generate",
            "make",
            "new",
            "remove",
            "retry",
            "save",
            "set",
            "submit",
            "update",
            "upload",
            "أنشئ",
            "انشئ",
            "احذف",
            "ارفع",
            "اضف",
            "أضف",
            "حدث",
            "غيّر",
            "غير",
            "سجل",
            "احفظ",
        }
        return any(term in lowered for term in state_changing_terms)

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

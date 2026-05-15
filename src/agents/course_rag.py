from __future__ import annotations

import re
from pathlib import Path

from src.localization import normalize_language, t
from src.prompts import render_prompt
from src.retrieval import CourseMaterialIndexer, RetrievedChunk
from src.tools.llm_client import LLMClient


TOKEN_PATTERN = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)
SOURCE_HEADER_PATTERN = re.compile(
    r"^\s*(sources?|citations?|\u0627\u0644\u0645\u0635\u0627\u062f\u0631)\s*[:\uff1a]",
    re.IGNORECASE,
)

ENGLISH_VAGUE_QUERIES = {
    "explain",
    "summarize",
    "summarise",
    "describe",
    "help",
    "what is this",
    "what is that",
    "explain this",
    "explain that",
    "summarize this",
    "describe this",
}
ENGLISH_GENERIC_TERMS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "can",
    "course",
    "describe",
    "explain",
    "for",
    "from",
    "help",
    "i",
    "in",
    "is",
    "it",
    "lecture",
    "material",
    "materials",
    "me",
    "my",
    "notes",
    "of",
    "on",
    "please",
    "summarise",
    "summarize",
    "tell",
    "that",
    "the",
    "this",
    "to",
    "what",
    "you",
}
ARABIC_VAGUE_QUERIES = {
    "\u0627\u0634\u0631\u062d",
    "\u0634\u0631\u062d",
    "\u0644\u062e\u0635",
    "\u0645\u0633\u0627\u0639\u062f\u0629",
    "\u0633\u0627\u0639\u062f\u0646\u064a",
    "\u0627\u064a\u0647 \u062f\u0647",
    "\u0645\u0627 \u0647\u0630\u0627",
}
ARABIC_GENERIC_TERMS = {
    "\u0627\u0634\u0631\u062d",
    "\u0627\u0634\u0631\u062d\u0644\u064a",
    "\u0627\u0644\u0645\u0627\u062f\u0629",
    "\u0627\u0644\u0645\u062d\u0627\u0636\u0631\u0629",
    "\u0627\u0644\u0645\u0644\u0641",
    "\u0627\u0644\u0645\u0648\u0636\u0648\u0639",
    "\u062f\u0647",
    "\u062f\u064a",
    "\u0633\u0627\u0639\u062f\u0646\u064a",
    "\u0634\u0631\u062d",
    "\u0639\u0646",
    "\u0641\u064a",
    "\u0644\u062e\u0635",
    "\u0644\u0648",
    "\u0645\u0627",
    "\u0645\u0633\u0627\u0639\u062f\u0629",
    "\u0645\u0645\u0643\u0646",
    "\u0645\u0646",
    "\u0647\u0630\u0627",
    "\u0647\u0630\u0647",
    "\u0647\u0648",
}


class CourseRAGAgent:
    """Answers questions with retrieved chunks from uploaded course materials."""

    def __init__(
        self,
        *,
        uploads_dir: Path | None = None,
        vector_store_dir: Path | None = None,
        top_k: int = 4,
        llm_client: LLMClient | None = None,
    ) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.indexer = CourseMaterialIndexer(
            uploads_dir=uploads_dir or project_root / "data" / "uploads",
            vector_store_dir=vector_store_dir or project_root / "data" / "vector_store",
        )
        self.top_k = top_k
        self.llm_client = llm_client or LLMClient()

    def answer(
        self,
        question: str,
        *,
        language: str = "en",
        course_id: str | None = None,
        course_name: str | None = None,
    ) -> dict:
        language = normalize_language(language)
        if self.needs_clarification(question, language=language):
            return {
                "ok": False,
                "status": "needs_clarification",
                "response": self._clarification_response(language),
                "question": question,
                "citations": [],
                "matches": [],
                "stats": self._empty_stats(),
                "generation_mode": "clarification",
                "course_id": course_id,
                "course_name": course_name,
            }

        index_result = self.indexer.index_all(course_id=course_id, course_name=course_name)
        stats = index_result["stats"]
        if stats["chunks"] == 0:
            return {
                "ok": False,
                "status": "no_materials",
                "response": self._no_materials_response(language),
                "question": question,
                "citations": [],
                "matches": [],
                "stats": stats,
                "course_id": course_id,
                "course_name": course_name,
            }

        matches = self._deduplicate_matches(
            self.indexer.search(question, top_k=self.top_k, course_id=course_id)
        )
        if not matches:
            return {
                "ok": False,
                "status": "no_relevant_match",
                "response": self._no_match_response(language),
                "question": question,
                "citations": [],
                "matches": [],
                "stats": stats,
                "course_id": course_id,
                "course_name": course_name,
            }

        response, generation_mode = self._compose_answer(question, matches, language=language, course_name=course_name)
        return {
            "ok": True,
            "status": "answered",
            "response": response,
            "question": question,
            "citations": [self._source_label(match, course_name=course_name) for match in matches],
            "matches": [
                {
                    "source_name": match.source_name,
                    "section": match.section,
                    "chunk_index": match.chunk_index,
                    "score": match.score,
                    "text": match.text,
                    "citation": self._source_label(match, course_name=course_name),
                }
                for match in matches
            ],
            "stats": stats,
            "generation_mode": generation_mode,
            "course_id": course_id,
            "course_name": course_name,
        }

    def _compose_answer(
        self,
        question: str,
        matches: list[RetrievedChunk],
        *,
        language: str,
        course_name: str | None,
    ) -> tuple[str, str]:
        llm_answer = self._compose_llm_answer(
            question,
            matches,
            language=language,
            course_name=course_name,
        )
        if llm_answer:
            return self._with_sources(llm_answer, matches, language, course_name=course_name), "llm"

        return self._compose_offline_answer(
            question,
            matches,
            language=language,
            course_name=course_name,
        ), "offline_template"

    def _no_materials_response(self, language: str) -> str:
        return t("rag.no_materials", language)

    def _no_match_response(self, language: str) -> str:
        return t("rag.no_match", language)

    def needs_clarification(self, question: str, *, language: str = "en") -> bool:
        language = normalize_language(language)
        compact = " ".join(str(question or "").split())
        if not compact:
            return True

        normalized = compact.casefold().strip(" \t\r\n.?!\u061f\u060c,;:")
        vague_queries = ARABIC_VAGUE_QUERIES if language == "ar" else ENGLISH_VAGUE_QUERIES
        if normalized in vague_queries:
            return True

        tokens = self._tokens(compact)
        if not tokens:
            return True

        topic_tokens = self._topic_tokens(compact, language=language)
        if not topic_tokens:
            return True

        return len(tokens) < 3 and not self._has_topic_signal(topic_tokens)

    def _clarification_response(self, language: str) -> str:
        return t("rag.clarify", language)

    def _empty_stats(self) -> dict:
        return {"files": 0, "chunks": 0, "sources": [], "updated_at_utc": None}

    def _trim_to_sentence(self, text: str, *, max_length: int = 420) -> str:
        compact = " ".join(text.split())
        if len(compact) <= max_length:
            return compact
        trimmed = compact[:max_length].rsplit(" ", 1)[0].rstrip(" ,;:")
        return f"{trimmed}..."

    def _compose_offline_answer(
        self,
        question: str,
        matches: list[RetrievedChunk],
        *,
        language: str,
        course_name: str | None,
    ) -> str:
        topic = self._infer_topic(question, language=language)
        points = self._salient_points(question, matches, language=language)

        if language == "ar":
            if topic:
                answer_lines = [
                    f"{topic} \u0645\u0648\u0636\u0648\u0639 \u0645\u0648\u062c\u0648\u062f \u0641\u064a \u0645\u0648\u0627\u062f \u0627\u0644\u0645\u0642\u0631\u0631. \u0627\u0644\u0641\u0643\u0631\u0629 \u0628\u0628\u0633\u0627\u0637\u0629:",
                    "",
                ]
            else:
                answer_lines = [
                    "\u062a\u0648\u0636\u062d \u0645\u0648\u0627\u062f \u0627\u0644\u0645\u0642\u0631\u0631 \u0627\u0644\u0641\u0643\u0631\u0629 \u0628\u0647\u0630\u0627 \u0627\u0644\u0634\u0643\u0644:",
                    "",
                ]
        else:
            if topic:
                answer_lines = [
                    f"{topic} is covered in your course material. Here is the idea in simple terms:",
                    "",
                ]
            else:
                answer_lines = [
                    "The retrieved course material supports this explanation:",
                    "",
                ]

        for point in points:
            answer_lines.append(f"- {self._educational_point(point, language=language)}")

        return self._with_sources("\n".join(answer_lines), matches, language, course_name=course_name)

    def _compose_llm_answer(
        self,
        question: str,
        matches: list[RetrievedChunk],
        *,
        language: str,
        course_name: str | None,
    ) -> str | None:
        if not self.llm_client.is_available:
            return None

        source_blocks = []
        for index, match in enumerate(matches, start=1):
            source_blocks.append(
                f"[{index}] {self._source_label(match, course_name=course_name)}\n"
                f"{self._trim_to_sentence(match.text, max_length=900)}"
            )
        response_language = "Arabic" if language == "ar" else "English"
        joined_sources = "\n\n".join(source_blocks)
        prompt = render_prompt(
            "rag_answer",
            course_name=course_name or (
                "this course"
                if language != "ar"
                else "\u0647\u0630\u0627 \u0627\u0644\u0645\u0642\u0631\u0631"
            ),
            question=question,
            context=joined_sources,
            citations="\n".join(f"- {self._source_label(match, course_name=course_name)}" for match in matches),
            language=response_language,
        )
        try:
            return self.llm_client.generate_text(
                system_prompt=prompt.system,
                user_prompt=prompt.user,
                temperature=0.2,
                max_tokens=700,
            )
        except Exception:
            return None

    def _deduplicate_matches(self, matches: list[RetrievedChunk]) -> list[RetrievedChunk]:
        unique_matches = []
        seen: set[tuple[str, str, str]] = set()
        for match in matches:
            key = self._match_key(match)
            if key in seen:
                continue
            seen.add(key)
            unique_matches.append(match)
        return unique_matches

    def _match_key(self, match: RetrievedChunk) -> tuple[str, str, str]:
        source_name = " ".join(str(match.source_name or "").casefold().split())
        section = " ".join(str(match.section or "").casefold().split())
        chunk_index = getattr(match, "chunk_index", None)
        if chunk_index is not None:
            return (source_name, section, str(chunk_index))
        normalized_text = " ".join(str(match.text or "").casefold().split())
        return (source_name, section, normalized_text[:200])

    def _format_sources(self, matches: list[RetrievedChunk], language: str, *, course_name: str | None = None) -> str:
        heading = "\u0627\u0644\u0645\u0635\u0627\u062f\u0631:" if language == "ar" else "Sources:"
        lines = [heading, ""]
        for match in matches:
            lines.append(f"- {self._source_label(match, course_name=course_name)}")
        return "\n".join(lines)

    def _source_label(self, match: RetrievedChunk, *, course_name: str | None = None) -> str:
        resolved_course = " ".join(str(match.course_name or course_name or "").split())
        source_name = " ".join(str(match.source_name or "uploaded material").split())
        section = " ".join(str(match.section or "").split())
        chunk_index = getattr(match, "chunk_index", None) or 1
        parts = []
        if resolved_course:
            parts.append(resolved_course)
        parts.append(source_name)
        if section:
            parts.append(section)
        parts.append(f"chunk {chunk_index}")
        return ", ".join(parts)

    def _with_sources(
        self,
        answer: str,
        matches: list[RetrievedChunk],
        language: str,
        *,
        course_name: str | None = None,
    ) -> str:
        clean_answer = self._strip_sources(answer)
        return f"{clean_answer}\n\n{self._format_sources(matches, language, course_name=course_name)}".strip()

    def _strip_sources(self, answer: str) -> str:
        lines = str(answer or "").strip().splitlines()
        kept_lines = []
        for line in lines:
            if SOURCE_HEADER_PATTERN.match(line.strip()):
                break
            kept_lines.append(line)
        return "\n".join(kept_lines).strip()

    def _salient_points(
        self,
        question: str,
        matches: list[RetrievedChunk],
        *,
        language: str,
        limit: int = 3,
    ) -> list[str]:
        question_terms = set(self._topic_tokens(question, language=language))
        candidates: list[tuple[int, int, str]] = []
        seen: set[str] = set()
        order = 0
        for match in matches:
            for sentence in self._split_sentences(match.text):
                compact = self._trim_to_sentence(sentence, max_length=240)
                key = " ".join(compact.casefold().split())[:200]
                if len(compact) < 20 or key in seen:
                    continue
                seen.add(key)
                sentence_terms = set(self._tokens(compact))
                overlap = len(question_terms & sentence_terms)
                candidates.append((overlap, order, compact))
                order += 1

        if not candidates:
            return [self._trim_to_sentence(match.text, max_length=240) for match in matches[:limit]]

        candidates.sort(key=lambda item: (-item[0], item[1]))
        return [candidate[2] for candidate in candidates[:limit]]

    def _split_sentences(self, text: str) -> list[str]:
        compact = " ".join(str(text or "").split())
        if not compact:
            return []
        parts = re.split(r"(?<=[.!?\u061f])\s+", compact)
        return [part.strip(" -") for part in parts if part.strip(" -")] or [compact]

    def _educational_point(self, point: str, *, language: str) -> str:
        clean_point = point.strip()
        if not clean_point:
            return clean_point
        if language == "ar":
            return f"\u062a\u0648\u0636\u062d \u0627\u0644\u0645\u0627\u062f\u0629 \u0623\u0646 {clean_point}"
        return f"The material explains that {clean_point[0].lower()}{clean_point[1:]}"

    def _infer_topic(self, question: str, *, language: str) -> str:
        generic_terms = ARABIC_GENERIC_TERMS if language == "ar" else ENGLISH_GENERIC_TERMS
        topic_tokens = [
            token
            for token in TOKEN_PATTERN.findall(str(question or ""))
            if token.casefold() not in generic_terms and len(token) > 1
        ]
        return " ".join(topic_tokens[:6])

    def _tokens(self, text: str) -> list[str]:
        return [token.casefold() for token in TOKEN_PATTERN.findall(str(text or ""))]

    def _topic_tokens(self, text: str, *, language: str) -> list[str]:
        generic_terms = ARABIC_GENERIC_TERMS if language == "ar" else ENGLISH_GENERIC_TERMS
        return [token for token in self._tokens(text) if token not in generic_terms and len(token) > 1]

    def _has_topic_signal(self, topic_tokens: list[str]) -> bool:
        return len(topic_tokens) >= 2 or any(len(token) >= 3 for token in topic_tokens)

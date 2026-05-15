from __future__ import annotations

from pathlib import Path

from src.retrieval import CourseMaterialIndexer, RetrievedChunk
from src.tools.llm_client import LLMClient


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

    def answer(self, question: str, *, language: str = "en") -> dict:
        index_result = self.indexer.index_all()
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
            }

        matches = self.indexer.search(question, top_k=self.top_k)
        if not matches:
            return {
                "ok": False,
                "status": "no_relevant_match",
                "response": self._no_match_response(language),
                "question": question,
                "citations": [],
                "matches": [],
                "stats": stats,
            }

        response, generation_mode = self._compose_answer(question, matches, language=language)
        return {
            "ok": True,
            "status": "answered",
            "response": response,
            "question": question,
            "citations": [match.citation() for match in matches],
            "matches": [
                {
                    "source_name": match.source_name,
                    "section": match.section,
                    "score": match.score,
                    "text": match.text,
                }
                for match in matches
            ],
            "stats": stats,
            "generation_mode": generation_mode,
        }

    def _compose_answer(self, question: str, matches: list[RetrievedChunk], *, language: str) -> tuple[str, str]:
        llm_answer = self._compose_llm_answer(question, matches, language=language)
        if llm_answer:
            return llm_answer, "llm"

        best_points = [self._trim_to_sentence(match.text) for match in matches[:3]]
        source_list = "; ".join(dict.fromkeys(match.citation() for match in matches))
        if language == "ar":
            answer_lines = [
                f"بناء على المواد التي رفعتها، هذه أهم النقاط المرتبطة بسؤالك: {question}",
                "",
            ]
            for index, point in enumerate(best_points, start=1):
                answer_lines.append(f"{index}. {point}")
            answer_lines.extend(["", f"المصادر: {source_list}"])
            return "\n".join(answer_lines), "offline_template"

        answer_lines = [
            f"Based on your uploaded materials, here is the relevant answer to: {question}",
            "",
        ]
        for index, point in enumerate(best_points, start=1):
            answer_lines.append(f"{index}. {point}")
        answer_lines.extend(["", f"Sources: {source_list}"])
        return "\n".join(answer_lines), "offline_template"

    def _no_materials_response(self, language: str) -> str:
        if language == "ar":
            return "ارفع مواد المقرر أولا، وبعدها أقدر أجاوبك بإجابات موثقة من ملاحظاتك."
        return "Upload course materials first, then I can answer with sources from your notes."

    def _no_match_response(self, language: str) -> str:
        if language == "ar":
            return "وجدت مواد مفهرسة، لكن لم أجد جزءا مناسبا لهذا السؤال. حاول كتابة اسم الموضوع كما هو موجود في ملاحظاتك."
        return (
            "I found indexed materials, but not a strong match for that question. "
            "Try naming the topic exactly as it appears in your notes."
        )

    def _trim_to_sentence(self, text: str, *, max_length: int = 420) -> str:
        compact = " ".join(text.split())
        if len(compact) <= max_length:
            return compact
        trimmed = compact[:max_length].rsplit(" ", 1)[0].rstrip(" ,;:")
        return f"{trimmed}..."

    def _compose_llm_answer(self, question: str, matches: list[RetrievedChunk], *, language: str) -> str | None:
        if not self.llm_client.is_available:
            return None

        source_blocks = []
        for index, match in enumerate(matches, start=1):
            source_blocks.append(
                f"[{index}] {match.citation()}\n{self._trim_to_sentence(match.text, max_length=900)}"
            )
        response_language = "Arabic" if language == "ar" else "English"
        joined_sources = "\n\n".join(source_blocks)
        system_prompt = (
            "You are a careful study assistant. Answer only from the provided course-material excerpts. "
            "If the excerpts do not support an answer, say that the uploaded material does not contain enough detail. "
            "Keep the answer concise and include a final Sources line using the given citation labels."
        )
        user_prompt = (
            f"Response language: {response_language}\n\n"
            f"Student question:\n{question}\n\n"
            "Course-material excerpts:\n"
            f"{joined_sources}"
        )
        try:
            return self.llm_client.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=700,
            )
        except Exception:
            return None

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SUPPORTED_EXTENSIONS = {".docx", ".md", ".pdf", ".pptx", ".txt"}
TOKEN_PATTERN = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)


@dataclass(frozen=True)
class RetrievedChunk:
    source_name: str
    section: str
    text: str
    score: float
    chunk_index: int = 1
    course_id: str | None = None
    course_name: str | None = None

    def citation(self) -> str:
        if self.course_name:
            return f"{self.course_name} - {self.source_name} - {self.section}/chunk {self.chunk_index}"
        return f"{self.source_name} ({self.section})"


class CourseMaterialIndexer:
    """Extracts uploaded course files into a small persistent vector store."""

    def __init__(
        self,
        *,
        uploads_dir: Path,
        vector_store_dir: Path,
        chunk_size: int = 900,
        chunk_overlap: int = 140,
    ) -> None:
        self.uploads_dir = uploads_dir
        self.vector_store_dir = vector_store_dir
        self.store_path = vector_store_dir / "course_materials.json"
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def index_all(self, *, course_id: str | None = None, course_name: str | None = None) -> dict[str, Any]:
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        results = []
        search_root = self._course_upload_dir(course_id) if course_id else self.uploads_dir
        for file_path in sorted(search_root.glob("*")):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                results.append(self.index_file(file_path, course_id=course_id, course_name=course_name))

        stats = self.stats(course_id=course_id)
        return {
            "ok": all(result["ok"] for result in results) if results else True,
            "indexed_files": sum(1 for result in results if result["ok"]),
            "errors": [result for result in results if not result["ok"]],
            "stats": stats,
        }

    def index_file(
        self,
        file_path: Path,
        *,
        course_id: str | None = None,
        course_name: str | None = None,
    ) -> dict[str, Any]:
        file_path = file_path.resolve()
        if not file_path.exists() or not file_path.is_file():
            return {"ok": False, "file_name": file_path.name, "reason": "File does not exist."}
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return {"ok": False, "file_name": file_path.name, "reason": "Unsupported file type."}

        store = self._load_store()
        existing_chunks = [
            chunk
            for chunk in store["chunks"]
            if chunk.get("source_path") == str(file_path) and chunk.get("course_id") == course_id
        ]
        stat = file_path.stat()
        if existing_chunks and all(
            chunk.get("source_mtime") == stat.st_mtime and chunk.get("source_size") == stat.st_size
            for chunk in existing_chunks
        ):
            return {"ok": True, "file_name": file_path.name, "chunks": len(existing_chunks), "skipped": True}

        try:
            sections = self._extract_sections(file_path)
        except Exception as exc:  # pragma: no cover - defensive path for optional parsers
            return {"ok": False, "file_name": file_path.name, "reason": str(exc)}

        chunks = []
        for section in sections:
            for chunk_index, chunk_text in enumerate(self._chunk_text(section["text"]), start=1):
                vector = self._embed(chunk_text)
                if not vector:
                    continue
                chunks.append(
                    {
                        "id": f"{course_id or 'legacy'}:{file_path.name}:{section['label']}:{chunk_index}",
                        "course_id": course_id,
                        "course_name": course_name,
                        "source_name": file_path.name,
                        "source_path": str(file_path),
                        "source_mtime": stat.st_mtime,
                        "source_size": stat.st_size,
                        "section": section["label"],
                        "chunk_index": chunk_index,
                        "text": chunk_text,
                        "embedding": vector,
                        "indexed_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
                    }
                )

        if not chunks:
            return {"ok": False, "file_name": file_path.name, "reason": "No readable text was found."}

        store["chunks"] = [
            chunk
            for chunk in store["chunks"]
            if not (chunk.get("source_path") == str(file_path) and chunk.get("course_id") == course_id)
        ]
        store["chunks"].extend(chunks)
        store["updated_at_utc"] = datetime.utcnow().isoformat(timespec="seconds")
        self._save_store(store)

        return {"ok": True, "file_name": file_path.name, "chunks": len(chunks)}

    def remove_file(
        self,
        file_path: Path,
        *,
        delete_source: bool = True,
        course_id: str | None = None,
    ) -> dict[str, Any]:
        file_path = file_path.resolve()
        uploads_dir = self.uploads_dir.resolve()
        if not file_path.is_relative_to(uploads_dir):
            return {"ok": False, "file_name": file_path.name, "reason": "File is outside the uploads directory."}

        store = self._load_store()
        previous_count = len(store["chunks"])
        store["chunks"] = [
            chunk
            for chunk in store["chunks"]
            if not (
                chunk.get("source_path") == str(file_path)
                and (course_id is None or chunk.get("course_id") == course_id)
            )
        ]
        removed_chunks = previous_count - len(store["chunks"])

        file_deleted = False
        if delete_source and file_path.exists():
            if not file_path.is_file():
                return {"ok": False, "file_name": file_path.name, "reason": "Path is not a file."}
            file_path.unlink()
            file_deleted = True

        store["updated_at_utc"] = datetime.utcnow().isoformat(timespec="seconds")
        self._save_store(store)

        return {
            "ok": True,
            "file_name": file_path.name,
            "file_deleted": file_deleted,
            "removed_chunks": removed_chunks,
        }

    def search(
        self,
        query: str,
        *,
        top_k: int = 4,
        min_score: float = 0.05,
        course_id: str | None = None,
    ) -> list[RetrievedChunk]:
        query_vector = self._embed(query)
        if not query_vector:
            return []

        store = self._load_store()
        scored_chunks = []
        for chunk in store["chunks"]:
            if course_id is not None and chunk.get("course_id") != course_id:
                continue
            score = self._cosine_similarity(query_vector, chunk.get("embedding", {}))
            if score >= min_score:
                scored_chunks.append(
                    RetrievedChunk(
                        source_name=chunk["source_name"],
                        section=chunk["section"],
                        text=chunk["text"],
                        score=round(score, 4),
                        chunk_index=chunk.get("chunk_index", 1),
                        course_id=chunk.get("course_id"),
                        course_name=chunk.get("course_name"),
                    )
                )

        return sorted(scored_chunks, key=lambda item: item.score, reverse=True)[:top_k]

    def stats(self, *, course_id: str | None = None) -> dict[str, Any]:
        store = self._load_store()
        chunks = [
            chunk
            for chunk in store["chunks"]
            if course_id is None or chunk.get("course_id") == course_id
        ]
        source_names = sorted({chunk["source_name"] for chunk in chunks})
        return {
            "files": len(source_names),
            "chunks": len(chunks),
            "sources": source_names,
            "updated_at_utc": store.get("updated_at_utc"),
        }

    def _extract_sections(self, file_path: Path) -> list[dict[str, str]]:
        suffix = file_path.suffix.lower()
        if suffix in {".txt", ".md"}:
            return [{"label": "text", "text": self._read_text_file(file_path)}]
        if suffix == ".pdf":
            return self._extract_pdf(file_path)
        if suffix == ".docx":
            return self._extract_docx(file_path)
        if suffix == ".pptx":
            return self._extract_pptx(file_path)
        return []

    def _extract_pdf(self, file_path: Path) -> list[dict[str, str]]:
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover - depends on local environment
            raise RuntimeError("Install PyMuPDF to index PDF files.") from exc

        sections = []
        with fitz.open(file_path) as document:
            for page_index, page in enumerate(document, start=1):
                text = page.get_text("text").strip()
                if text:
                    sections.append({"label": f"page {page_index}", "text": text})
        return sections

    def _extract_docx(self, file_path: Path) -> list[dict[str, str]]:
        try:
            from docx import Document
        except ImportError as exc:  # pragma: no cover - depends on local environment
            raise RuntimeError("Install python-docx to index DOCX files.") from exc

        document = Document(file_path)
        text = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
        return [{"label": "document", "text": text}]

    def _extract_pptx(self, file_path: Path) -> list[dict[str, str]]:
        try:
            from pptx import Presentation
        except ImportError as exc:  # pragma: no cover - depends on local environment
            raise RuntimeError("Install python-pptx to index PPTX files.") from exc

        presentation = Presentation(file_path)
        sections = []
        for slide_index, slide in enumerate(presentation.slides, start=1):
            text_parts = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    text_parts.append(shape.text.strip())
            if text_parts:
                sections.append({"label": f"slide {slide_index}", "text": "\n".join(text_parts)})
        return sections

    def _read_text_file(self, file_path: Path) -> str:
        for encoding in ("utf-8", "utf-8-sig", "cp1252"):
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return file_path.read_text(encoding="utf-8", errors="ignore")

    def _chunk_text(self, text: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return []
        if len(normalized) <= self.chunk_size:
            return [normalized]

        chunks = []
        start = 0
        while start < len(normalized):
            end = min(start + self.chunk_size, len(normalized))
            if end < len(normalized):
                sentence_break = normalized.rfind(". ", start, end)
                if sentence_break > start + int(self.chunk_size * 0.55):
                    end = sentence_break + 1
            chunk = normalized[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(normalized):
                break
            start = max(end - self.chunk_overlap, start + 1)
        return chunks

    def _embed(self, text: str) -> dict[str, float]:
        tokens = [token.lower() for token in TOKEN_PATTERN.findall(text)]
        if not tokens:
            return {}
        counts = Counter(tokens)
        norm = math.sqrt(sum(value * value for value in counts.values()))
        return {token: round(value / norm, 6) for token, value in counts.items()}

    def _cosine_similarity(self, left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0
        smaller, larger = (left, right) if len(left) <= len(right) else (right, left)
        return sum(weight * larger.get(token, 0.0) for token, weight in smaller.items())

    def _load_store(self) -> dict[str, Any]:
        if not self.store_path.exists():
            return {"version": 1, "updated_at_utc": None, "chunks": []}
        try:
            return json.loads(self.store_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "updated_at_utc": None, "chunks": []}

    def _save_store(self, store: dict[str, Any]) -> None:
        self.vector_store_dir.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")

    def _course_upload_dir(self, course_id: str | None) -> Path:
        if not course_id:
            return self.uploads_dir
        return self.uploads_dir / course_id

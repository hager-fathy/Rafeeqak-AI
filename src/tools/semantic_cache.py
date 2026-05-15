from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


TOKEN_PATTERN = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)


class SemanticResponseCache:
    """Small local semantic cache for repeated chat questions."""

    def __init__(
        self,
        *,
        cache_path: Path | None = None,
        max_entries: int = 80,
        min_similarity: float = 0.92,
    ) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.cache_path = cache_path or project_root / "data" / "cache" / "semantic_cache.json"
        self.max_entries = max_entries
        self.min_similarity = min_similarity

    def lookup(
        self,
        *,
        message: str,
        language: str,
        context_fingerprint: str,
    ) -> dict[str, Any] | None:
        query_vector = self._embed(message)
        if not query_vector:
            return None

        store = self._load_store()
        candidates = []
        for entry in store["entries"]:
            if entry.get("language") != language:
                continue
            if entry.get("context_fingerprint") != context_fingerprint:
                continue
            score = self._cosine_similarity(query_vector, entry.get("embedding", {}))
            if score >= self.min_similarity:
                candidates.append((score, entry))

        if not candidates:
            return None

        score, entry = max(candidates, key=lambda item: item[0])
        entry["last_hit_at_utc"] = datetime.utcnow().isoformat(timespec="seconds")
        entry["hits"] = int(entry.get("hits", 0)) + 1
        self._save_store(store)

        return {
            "response": entry["response"],
            "agent": entry["agent"],
            "intent": entry["intent"],
            "payload": entry.get("payload", {}),
            "similarity": round(score, 4),
            "cached_at_utc": entry.get("created_at_utc"),
            "hits": entry["hits"],
        }

    def store(
        self,
        *,
        message: str,
        language: str,
        intent: str,
        agent: str,
        response: str,
        payload: dict[str, Any],
        context_fingerprint: str,
    ) -> None:
        embedding = self._embed(message)
        if not embedding or not response.strip():
            return

        store = self._load_store()
        store["entries"] = [
            entry
            for entry in store["entries"]
            if not (
                entry.get("message_normalized") == self._normalize(message)
                and entry.get("language") == language
                and entry.get("context_fingerprint") == context_fingerprint
            )
        ]
        store["entries"].append(
            {
                "message": message,
                "message_normalized": self._normalize(message),
                "language": language,
                "intent": intent,
                "agent": agent,
                "response": response,
                "payload": self._safe_payload(payload),
                "context_fingerprint": context_fingerprint,
                "embedding": embedding,
                "hits": 0,
                "created_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
                "last_hit_at_utc": None,
            }
        )
        store["entries"] = store["entries"][-self.max_entries :]
        store["updated_at_utc"] = datetime.utcnow().isoformat(timespec="seconds")
        self._save_store(store)

    def stats(self) -> dict[str, Any]:
        store = self._load_store()
        return {
            "entries": len(store["entries"]),
            "updated_at_utc": store.get("updated_at_utc"),
            "cache_path": str(self.cache_path),
        }

    def _safe_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            json.dumps(payload)
            return payload
        except TypeError:
            return {"cached_payload": str(payload)}

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

    def _normalize(self, text: str) -> str:
        return " ".join(text.lower().split())

    def _load_store(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return {"version": 1, "updated_at_utc": None, "entries": []}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "updated_at_utc": None, "entries": []}

    def _save_store(self, store: dict[str, Any]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")

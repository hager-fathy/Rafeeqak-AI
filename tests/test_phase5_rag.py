from src.agents.course_rag import CourseRAGAgent
from src.agents.supervisor import SupervisorAgent
from src.retrieval import CourseMaterialIndexer, RetrievedChunk
from src.tools.semantic_cache import SemanticResponseCache


class FakeTextLLM:
    is_available = True

    def generate_text(self, **kwargs) -> str:
        return "LLM answer from notes.\n\nSources: lecture.txt (text)"


class OfflineLLM:
    is_available = False


class SpyIndexer:
    def __init__(self) -> None:
        self.index_all_calls = 0
        self.search_calls = 0

    def index_all(self, **kwargs) -> dict:
        self.index_all_calls += 1
        raise AssertionError("Vague questions should not index materials.")

    def search(self, *args, **kwargs) -> list:
        self.search_calls += 1
        raise AssertionError("Vague questions should not search materials.")


class DuplicateChunkIndexer:
    def __init__(self) -> None:
        self.search_calls = []

    def index_all(self, **kwargs) -> dict:
        return {
            "ok": True,
            "stats": {
                "files": 1,
                "chunks": 3,
                "sources": ["INE Introduction to SOC Course File.pdf"],
                "updated_at_utc": None,
            },
        }

    def search(self, query: str, *, top_k: int, course_id: str | None = None) -> list[RetrievedChunk]:
        self.search_calls.append({"query": query, "top_k": top_k, "course_id": course_id})
        return [
            RetrievedChunk(
                source_name="INE Introduction to SOC Course File.pdf",
                section="page 201",
                chunk_index=1,
                score=0.92,
                text=(
                    "SOC tiers divide security operations responsibilities into levels. "
                    "Tier 1 analysts usually monitor alerts and perform initial triage."
                ),
            ),
            RetrievedChunk(
                source_name="INE Introduction to SOC Course File.pdf",
                section="page 201",
                chunk_index=1,
                score=0.91,
                text=(
                    "SOC tiers divide security operations responsibilities into levels. "
                    "Tier 1 analysts usually monitor alerts and perform initial triage."
                ),
            ),
            RetrievedChunk(
                source_name="INE Introduction to SOC Course File.pdf",
                section="page 5",
                chunk_index=1,
                score=0.72,
                text="A SOC analyst monitors security events and escalates suspicious activity.",
            ),
        ]


class SingleChunkIndexer:
    def __init__(self, text: str) -> None:
        self.text = text

    def index_all(self, **kwargs) -> dict:
        return {
            "ok": True,
            "stats": {
                "files": 1,
                "chunks": 1,
                "sources": ["soc_notes.pdf"],
                "updated_at_utc": None,
            },
        }

    def search(self, query: str, *, top_k: int, course_id: str | None = None) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                source_name="soc_notes.pdf",
                section="page 201",
                chunk_index=1,
                score=0.88,
                text=self.text,
            )
        ]


def test_course_material_indexer_extracts_chunks_and_searches(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    uploads_dir.mkdir()
    notes_path = uploads_dir / "ml_notes.txt"
    notes_path.write_text(
        "Backpropagation computes gradients by applying the chain rule through neural network layers. "
        "Support vector machines find a margin that separates classes.",
        encoding="utf-8",
    )

    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    result = indexer.index_file(notes_path)
    matches = indexer.search("How does backpropagation compute gradients?")

    assert result["ok"] is True
    assert result["chunks"] == 1
    assert vector_store_dir.joinpath("course_materials.json").exists()
    assert matches
    assert matches[0].source_name == "ml_notes.txt"
    assert "Backpropagation" in matches[0].text


def test_course_material_search_filters_by_course_id(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    ml_dir = uploads_dir / "ml-course"
    db_dir = uploads_dir / "db-course"
    ml_dir.mkdir(parents=True)
    db_dir.mkdir(parents=True)
    ml_notes = ml_dir / "ml_notes.txt"
    db_notes = db_dir / "db_notes.txt"
    ml_notes.write_text("Backpropagation sends gradients backward through neural layers.", encoding="utf-8")
    db_notes.write_text("Backpropagation is not part of this database note about indexes.", encoding="utf-8")

    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    indexer.index_file(ml_notes, course_id="ml-course", course_name="Machine Learning")
    indexer.index_file(db_notes, course_id="db-course", course_name="Databases")

    matches = indexer.search("backpropagation gradients", course_id="ml-course")

    assert matches
    assert {match.course_id for match in matches} == {"ml-course"}
    assert matches[0].citation() == "Machine Learning - ml_notes.txt - text/chunk 1"


def test_course_material_indexer_removes_deleted_file_and_chunks(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    uploads_dir.mkdir()
    notes_path = uploads_dir / "ml_notes.txt"
    notes_path.write_text(
        "Backpropagation computes gradients by applying the chain rule.",
        encoding="utf-8",
    )

    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    indexer.index_file(notes_path)

    result = indexer.remove_file(notes_path)

    assert result["ok"] is True
    assert result["file_deleted"] is True
    assert result["removed_chunks"] == 1
    assert not notes_path.exists()
    assert indexer.search("backpropagation") == []
    assert indexer.stats()["chunks"] == 0


def test_course_rag_agent_answers_with_citations(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    uploads_dir.mkdir()
    uploads_dir.joinpath("lecture.txt").write_text(
        "Backpropagation is the training procedure that sends error gradients backward through the model.",
        encoding="utf-8",
    )

    agent = CourseRAGAgent(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    result = agent.answer("Explain backpropagation from my notes")

    assert result["ok"] is True
    assert result["status"] == "answered"
    assert "Sources:" in result["response"]
    assert "- lecture.txt, text, chunk 1" in result["response"]
    assert result["citations"] == ["lecture.txt, text, chunk 1"]


def test_course_rag_agent_uses_llm_when_available(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    uploads_dir.mkdir()
    uploads_dir.joinpath("lecture.txt").write_text(
        "Backpropagation sends gradients backward through model layers.",
        encoding="utf-8",
    )

    agent = CourseRAGAgent(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir, llm_client=FakeTextLLM())
    result = agent.answer("Explain backpropagation from my notes")

    assert result["generation_mode"] == "llm"
    assert result["response"].startswith("LLM answer")
    assert "- lecture.txt, text, chunk 1" in result["response"]


def test_course_rag_agent_includes_course_name_in_citations_when_available(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    course_dir = uploads_dir / "ml-course"
    course_dir.mkdir(parents=True)
    course_dir.joinpath("lecture.txt").write_text(
        "Backpropagation sends gradients backward through model layers.",
        encoding="utf-8",
    )

    agent = CourseRAGAgent(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    result = agent.answer(
        "Explain backpropagation from my notes",
        course_id="ml-course",
        course_name="Machine Learning",
    )

    assert result["ok"] is True
    assert result["citations"] == ["Machine Learning, lecture.txt, text, chunk 1"]
    assert "- Machine Learning, lecture.txt, text, chunk 1" in result["response"]
    assert result["matches"][0]["citation"] == "Machine Learning, lecture.txt, text, chunk 1"


def test_course_rag_agent_answers_arabic_questions_in_arabic(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    uploads_dir.mkdir()
    uploads_dir.joinpath("arabic_notes.txt").write_text(
        "\u0627\u0644\u0627\u0646\u062a\u0634\u0627\u0631 \u0627\u0644\u0639\u0643\u0633\u064a \u064a\u062d\u0633\u0628 \u0627\u0644\u062a\u062f\u0631\u062c\u0627\u062a \u0628\u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0642\u0627\u0639\u062f\u0629 \u0627\u0644\u0633\u0644\u0633\u0644\u0629 \u062f\u0627\u062e\u0644 \u0627\u0644\u0634\u0628\u0643\u0627\u062a \u0627\u0644\u0639\u0635\u0628\u064a\u0629.",
        encoding="utf-8",
    )

    agent = CourseRAGAgent(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    result = agent.answer(
        "\u0627\u0634\u0631\u062d \u0627\u0644\u0627\u0646\u062a\u0634\u0627\u0631 \u0627\u0644\u0639\u0643\u0633\u064a \u0645\u0646 \u0645\u0644\u0627\u062d\u0638\u0627\u062a\u064a",
        language="ar",
    )

    assert result["ok"] is True
    assert "\u062a\u0648\u0636\u062d \u0627\u0644\u0645\u0627\u062f\u0629" in result["response"]
    assert "\u0627\u0644\u0645\u0635\u0627\u062f\u0631:" in result["response"]


def test_course_rag_agent_clarifies_vague_query_without_retrieval(tmp_path) -> None:
    agent = CourseRAGAgent(
        uploads_dir=tmp_path / "uploads",
        vector_store_dir=tmp_path / "vector_store",
        llm_client=OfflineLLM(),
    )
    spy_indexer = SpyIndexer()
    agent.indexer = spy_indexer

    result = agent.answer("explain")

    assert result["ok"] is False
    assert result["status"] == "needs_clarification"
    assert "What topic would you like me to explain?" in result["response"]
    assert spy_indexer.index_all_calls == 0
    assert spy_indexer.search_calls == 0


def test_course_rag_agent_clarifies_arabic_vague_query(tmp_path) -> None:
    agent = CourseRAGAgent(
        uploads_dir=tmp_path / "uploads",
        vector_store_dir=tmp_path / "vector_store",
        llm_client=OfflineLLM(),
    )
    agent.indexer = SpyIndexer()

    result = agent.answer("\u0627\u0634\u0631\u062d", language="ar")

    assert result["status"] == "needs_clarification"
    assert "\u0645\u0645\u0643\u0646 \u062a\u062d\u062f\u062f \u0627\u0644\u0645\u0648\u0636\u0648\u0639" in result["response"]


def test_course_rag_agent_removes_duplicate_chunks_and_formats_unique_sources(tmp_path) -> None:
    agent = CourseRAGAgent(
        uploads_dir=tmp_path / "uploads",
        vector_store_dir=tmp_path / "vector_store",
        llm_client=OfflineLLM(),
    )
    duplicate_indexer = DuplicateChunkIndexer()
    agent.indexer = duplicate_indexer

    result = agent.answer("Explain SOC tiers", course_id="soc", course_name="SOC")

    assert result["ok"] is True
    assert duplicate_indexer.search_calls[0]["course_id"] == "soc"
    assert len(result["matches"]) == 2
    assert result["citations"] == [
        "SOC, INE Introduction to SOC Course File.pdf, page 201, chunk 1",
        "SOC, INE Introduction to SOC Course File.pdf, page 5, chunk 1",
    ]
    assert result["response"].count("- SOC, INE Introduction to SOC Course File.pdf, page 201, chunk 1") == 1
    assert result["response"].count("- SOC, INE Introduction to SOC Course File.pdf, page 5, chunk 1") == 1


def test_course_rag_agent_synthesizes_specific_query_instead_of_dumping_chunks(tmp_path) -> None:
    raw_chunk = " ".join(["Learning outcomes: Explain SOC tiers."] * 12)
    agent = CourseRAGAgent(
        uploads_dir=tmp_path / "uploads",
        vector_store_dir=tmp_path / "vector_store",
        llm_client=OfflineLLM(),
    )
    agent.indexer = SingleChunkIndexer(raw_chunk)

    result = agent.answer("Explain SOC tiers")

    assert result["ok"] is True
    assert result["generation_mode"] == "offline_template"
    assert "SOC tiers is covered in your course material" in result["response"]
    assert raw_chunk not in result["response"]
    assert "Based on your uploaded materials" not in result["response"]
    assert "Sources:\n\n- soc_notes.pdf, page 201, chunk 1" in result["response"]


def test_supervisor_routes_course_material_questions_to_rag(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    uploads_dir.mkdir()
    uploads_dir.joinpath("lecture.txt").write_text(
        "Gradient descent updates model weights in the direction that reduces the loss function.",
        encoding="utf-8",
    )

    supervisor = SupervisorAgent(
        course_rag=CourseRAGAgent(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir),
        semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"),
    )
    result = supervisor.handle_message("Explain gradient descent from the lecture notes")

    assert result["agent"] == "course_rag_agent"
    assert result["payload"]["ok"] is True
    assert "lecture.txt" in result["response"]
    assert result["trace"][-2]["status"] == "completed"


def test_supervisor_clarifies_exact_vague_course_material_request(tmp_path) -> None:
    supervisor = SupervisorAgent(
        course_rag=CourseRAGAgent(
            uploads_dir=tmp_path / "uploads",
            vector_store_dir=tmp_path / "vector_store",
            llm_client=OfflineLLM(),
        ),
        semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"),
    )

    result = supervisor.handle_message("help")

    assert result["agent"] == "course_rag_agent"
    assert result["payload"]["status"] == "needs_clarification"
    assert "What topic would you like me to explain?" in result["response"]
    assert result["trace"][-2]["action"] == "asked for a clearer topic before retrieving course-material chunks"


def test_supervisor_blocks_course_scoped_agents_when_course_required(tmp_path) -> None:
    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))
    result = supervisor.handle_message(
        "Explain gradient descent from the lecture notes",
        context={"require_active_course": True, "active_course_id": None},
    )

    assert result["agent"] == "course_scope_validator"
    assert result["payload"]["active_course_required"] is True
    assert result["trace"][-1]["step"] == "validate_course_scope"

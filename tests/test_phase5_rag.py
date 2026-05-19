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
                course_id="soc",
                course_name="SOC",
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
                course_id="soc",
                course_name="SOC",
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
                course_id="soc",
                course_name="SOC",
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


class CapturingCourseRAG:
    def __init__(self) -> None:
        self.calls = []

    def answer(self, *args, **kwargs) -> dict:
        self.calls.append({"args": args, "kwargs": kwargs})
        return {
            "ok": True,
            "status": "answered",
            "response": "Grounded answer",
            "question": args[0] if args else "",
            "citations": [],
            "matches": [],
            "stats": {"files": 1, "chunks": 1, "sources": [], "updated_at_utc": None},
            "generation_mode": "offline_template",
        }


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


def test_retrieval_only_returns_active_course_chunks_for_shared_terms(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    ml_dir = uploads_dir / "ml-course"
    sec_dir = uploads_dir / "security-course"
    ml_dir.mkdir(parents=True)
    sec_dir.mkdir(parents=True)
    ml_dir.joinpath("backpropagation_notes.txt").write_text(
        "Backpropagation uses gradients in neural network training.",
        encoding="utf-8",
    )
    sec_dir.joinpath("soc_tiers.txt").write_text(
        "SOC tiers use escalation procedures for analyst investigations.",
        encoding="utf-8",
    )

    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    indexer.index_all(course_id="ml-course", course_name="Machine Learning")
    indexer.index_all(course_id="security-course", course_name="Security")

    matches = indexer.search("uses", course_id="ml-course", min_score=0.01)

    assert matches
    assert {match.course_id for match in matches} == {"ml-course"}
    assert all("SOC tiers" not in match.text for match in matches)


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
    assert "📄 this course | lecture.txt | Page/Chunk: text/chunk 1" in result["response"]
    assert result["citations"] == ["📄 this course | lecture.txt | Page/Chunk: text/chunk 1"]


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
    assert "📄 this course | lecture.txt | Page/Chunk: text/chunk 1" in result["response"]


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
    assert result["citations"] == ["📄 Machine Learning | lecture.txt | Page/Chunk: text/chunk 1"]
    assert "📄 Machine Learning | lecture.txt | Page/Chunk: text/chunk 1" in result["response"]
    assert result["matches"][0]["citation"] == "📄 Machine Learning | lecture.txt | Page/Chunk: text/chunk 1"


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
    assert "What topic would you like me to summarize or explain?" in result["response"]
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


def test_course_rag_arabic_vague_query_suggests_only_active_course_topics(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    ml_dir = uploads_dir / "ml-course"
    sec_dir = uploads_dir / "security-course"
    ml_dir.mkdir(parents=True)
    sec_dir.mkdir(parents=True)
    ml_dir.joinpath("backpropagation_notes.txt").write_text(
        "Backpropagation computes gradients for neural network learning.",
        encoding="utf-8",
    )
    sec_dir.joinpath("soc_tiers.txt").write_text(
        "SOC tiers, threat hunting, and SOC analyst roles are security operations topics.",
        encoding="utf-8",
    )

    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    indexer.index_all(course_id="ml-course", course_name="Machine Learning")
    indexer.index_all(course_id="security-course", course_name="Security")
    agent = CourseRAGAgent(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir, llm_client=OfflineLLM())

    result = agent.answer("\u0644\u062e\u0635", language="ar", course_id="ml-course", course_name="Machine Learning")

    assert result["status"] == "needs_clarification"
    assert "backpropagation notes" in result["response"]
    assert "SOC" not in result["response"]
    assert "threat hunting" not in result["response"]


def test_course_rag_no_match_clarifies_with_active_course_suggestions_only(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    ml_dir = uploads_dir / "ml-course"
    sec_dir = uploads_dir / "security-course"
    ml_dir.mkdir(parents=True)
    sec_dir.mkdir(parents=True)
    ml_dir.joinpath("systems_lecture.txt").write_text(
        "Systems design appears in the machine learning deployment notes.",
        encoding="utf-8",
    )
    sec_dir.joinpath("soc_tiers.txt").write_text(
        "SOC tiers and threat hunting belong to the Security course.",
        encoding="utf-8",
    )

    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    indexer.index_all(course_id="ml-course", course_name="ML")
    indexer.index_all(course_id="security-course", course_name="Security")

    result = CourseRAGAgent(
        uploads_dir=uploads_dir,
        vector_store_dir=vector_store_dir,
        llm_client=OfflineLLM(),
    ).answer("sys", course_id="ml-course", course_name="ML")

    assert result["status"] == "no_relevant_match"
    assert "I found uploaded material for ML" in result["response"]
    assert "'sys'" in result["response"]
    assert "systems lecture" in result["response"]
    assert "SOC" not in result["response"]
    assert result["diagnostics"]["active_course_has_uploaded_files"] is True
    assert result["diagnostics"]["active_course_has_indexed_chunks"] is True
    assert result["diagnostics"]["retrieval_returned_zero_chunks"] is True


def test_course_rag_no_match_arabic_clarification_is_natural(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    ml_dir = uploads_dir / "ml-course"
    ml_dir.mkdir(parents=True)
    ml_dir.joinpath("systems_lecture.txt").write_text(
        "Systems design appears in the machine learning deployment notes.",
        encoding="utf-8",
    )
    CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir).index_all(
        course_id="ml-course",
        course_name="ML",
    )

    result = CourseRAGAgent(
        uploads_dir=uploads_dir,
        vector_store_dir=vector_store_dir,
        llm_client=OfflineLLM(),
    ).answer("sys", language="ar", course_id="ml-course", course_name="ML")

    assert result["status"] == "no_relevant_match"
    assert "فيه ملفات مرفوعة لمادة ML" in result["response"]
    assert "لم أستطع مطابقة 'sys' بدقة" in result["response"]


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
        "📄 SOC | INE Introduction to SOC Course File.pdf | Page/Chunk: page 201",
        "📄 SOC | INE Introduction to SOC Course File.pdf | Page/Chunk: page 5",
    ]
    assert result["response"].count("📄 SOC | INE Introduction to SOC Course File.pdf | Page/Chunk: page 201") == 1
    assert result["response"].count("📄 SOC | INE Introduction to SOC Course File.pdf | Page/Chunk: page 5") == 1


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
    assert "Sources:\n\n📄 this course | soc_notes.pdf | Page/Chunk: page 201" in result["response"]


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


def test_course_rag_no_material_in_active_course_does_not_use_other_course(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    sec_dir = uploads_dir / "security-course"
    sec_dir.mkdir(parents=True)
    sec_dir.joinpath("soc_tiers.txt").write_text(
        "SOC tiers and threat hunting belong to the Security course.",
        encoding="utf-8",
    )
    indexer = CourseMaterialIndexer(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    indexer.index_all(course_id="security-course", course_name="Security")

    result = CourseRAGAgent(
        uploads_dir=uploads_dir,
        vector_store_dir=vector_store_dir,
        llm_client=OfflineLLM(),
    ).answer("Explain SOC tiers", course_id="ml-course", course_name="Machine Learning")

    assert result["status"] == "no_materials"
    assert result["matches"] == []
    assert "selected course" in result["response"]
    assert "SOC tiers" not in result["response"]


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
    assert "What topic would you like me to summarize or explain?" in result["response"]
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


def test_supervisor_passes_active_course_memory_to_rag(tmp_path) -> None:
    course_rag = CapturingCourseRAG()
    supervisor = SupervisorAgent(
        course_rag=course_rag,
        semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"),
    )
    plan = {
        "course_name": "Databases",
        "exam_date": "2026-06-01",
        "weak_topics": ["Indexes"],
        "tasks": [
            {
                "task_id": "db-1",
                "date": "2026-05-18",
                "topic": "Indexes",
                "phase": "Review",
                "hours": 2,
                "completed": False,
            },
            {
                "task_id": "db-2",
                "date": "2026-05-17",
                "topic": "Transactions",
                "phase": "Practice",
                "hours": 1,
                "completed": True,
            },
        ],
    }

    result = supervisor.handle_message(
        "Explain indexes from the lecture notes",
        context={
            "active_course_id": "db-course",
            "active_course_name": "Databases",
            "active_plan": plan,
            "uploads": [],
            "quiz_attempts": [{"topic": "Indexes", "score_percent": 60, "weak_topics": ["B-trees"]}],
        },
    )

    assert result["agent"] == "course_rag_agent"
    memory = course_rag.calls[0]["kwargs"]["memory"]
    assert "Active course: Databases" in memory
    assert "Pending tasks: 1" in memory
    assert "Completed tasks: 1" in memory
    assert "Weak topics: Indexes, B-trees" in memory


def test_supervisor_trace_includes_retrieved_chunk_course_ids(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    course_dir = uploads_dir / "ml-course"
    course_dir.mkdir(parents=True)
    course_dir.joinpath("lecture.txt").write_text(
        "Gradient descent updates model weights.",
        encoding="utf-8",
    )

    supervisor = SupervisorAgent(
        course_rag=CourseRAGAgent(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir, llm_client=OfflineLLM()),
        semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"),
    )
    result = supervisor.handle_message(
        "Explain gradient descent from notes",
        context={"active_course_id": "ml-course", "active_course_name": "Machine Learning", "uploads": []},
    )

    rag_step = next(step for step in result["trace"] if step["agent"] == "CourseRAGAgent")
    assert rag_step["details"]["retrieved_chunk_course_ids"] == ["ml-course"]

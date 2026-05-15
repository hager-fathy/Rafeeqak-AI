from src.agents.course_rag import CourseRAGAgent
from src.agents.supervisor import SupervisorAgent
from src.retrieval import CourseMaterialIndexer
from src.tools.semantic_cache import SemanticResponseCache


class FakeTextLLM:
    is_available = True

    def generate_text(self, **kwargs) -> str:
        return "LLM answer from notes.\n\nSources: lecture.txt (text)"


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
    assert result["citations"] == ["lecture.txt (text)"]


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


def test_course_rag_agent_answers_arabic_questions_in_arabic(tmp_path) -> None:
    uploads_dir = tmp_path / "uploads"
    vector_store_dir = tmp_path / "vector_store"
    uploads_dir.mkdir()
    uploads_dir.joinpath("arabic_notes.txt").write_text(
        "الانتشار العكسي يحسب التدرجات باستخدام قاعدة السلسلة داخل الشبكات العصبية.",
        encoding="utf-8",
    )

    agent = CourseRAGAgent(uploads_dir=uploads_dir, vector_store_dir=vector_store_dir)
    result = agent.answer("اشرح الانتشار العكسي من ملاحظاتي", language="ar")

    assert result["ok"] is True
    assert "بناء على المواد" in result["response"]
    assert "المصادر:" in result["response"]


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


def test_supervisor_blocks_course_scoped_agents_when_course_required(tmp_path) -> None:
    supervisor = SupervisorAgent(semantic_cache=SemanticResponseCache(cache_path=tmp_path / "cache.json"))
    result = supervisor.handle_message(
        "Explain gradient descent from the lecture notes",
        context={"require_active_course": True, "active_course_id": None},
    )

    assert result["agent"] == "course_scope_validator"
    assert result["payload"]["active_course_required"] is True
    assert result["trace"][-1]["step"] == "validate_course_scope"

from pathlib import Path


def test_phase13_demo_documentation_exists() -> None:
    demo_script = Path("docs/final_demo_script.md")
    validation = Path("docs/manual_demo_validation.md")
    ml_notes = Path("docs/demo_materials/machine_learning_notes.md")
    db_notes = Path("docs/demo_materials/database_notes.md")

    assert demo_script.exists()
    assert validation.exists()
    assert ml_notes.exists()
    assert db_notes.exists()


def test_final_demo_script_covers_required_story() -> None:
    content = Path("docs/final_demo_script.md").read_text(encoding="utf-8")
    required_phrases = [
        "Machine Learning",
        "Databases",
        "Upload Materials",
        "backpropagation",
        "Study Plan",
        "Quiz",
        "Progress Dashboard",
        "Settings",
        "Arabic",
        "course-scoped",
    ]

    for phrase in required_phrases:
        assert phrase in content


def test_manual_demo_validation_records_environment_status() -> None:
    content = Path("docs/manual_demo_validation.md").read_text(encoding="utf-8")

    assert "Validation Scope" in content
    assert "Environment Check" in content
    assert "Manual Validation Checklist" in content
    assert "missing Streamlit runtime" in content

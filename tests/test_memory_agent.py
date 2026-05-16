from src.agents.memory_agent import MemoryAgent


def test_memory_agent_status_shape() -> None:
    status = MemoryAgent().status()
    assert "enabled" in status
    assert "reason" in status
    assert isinstance(status["enabled"], bool)
    assert isinstance(status["reason"], str)


def test_memory_agent_creates_useful_chat_summary() -> None:
    result = MemoryAgent().summarize_chat_session(
        course_id="ml-1",
        course_name="Machine Learning",
        messages=[
            {"role": "user", "content": "I am confused about backpropagation mistakes."},
            {"role": "assistant", "content": "Review the chain rule and practice one example."},
            {"role": "user", "content": "Give me a quiz on backpropagation."},
        ],
        language="en",
        sync_cloud=False,
    )

    summary = result["summary"]

    assert result["ok"] is True
    assert summary["course_id"] == "ml-1"
    assert summary["summary_id"] == "active_session"
    assert summary["message_count"] == 3
    assert "backpropagation" in [topic.lower() for topic in summary["main_topics"]]
    assert summary["weaknesses"]
    assert summary["next_steps"]
    assert "Machine Learning summary" in summary["summary"]


def test_memory_agent_chat_summary_supports_arabic() -> None:
    result = MemoryAgent().summarize_chat_session(
        course_id="security-1",
        course_name="الأمن السيبراني",
        messages=[
            {"role": "user", "content": "مش فاهم threat hunting وعايز شرح"},
            {"role": "assistant", "content": "ابدأ بتعريف الفرضية ثم اجمع المؤشرات."},
        ],
        language="ar",
        sync_cloud=False,
    )

    summary = result["summary"]

    assert summary["language"] == "ar"
    assert summary["weaknesses"]
    assert "ملخص" in summary["summary"]

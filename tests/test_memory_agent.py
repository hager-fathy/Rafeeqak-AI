from src.agents.memory_agent import MemoryAgent


def test_memory_agent_status_shape() -> None:
    status = MemoryAgent().status()
    assert "enabled" in status
    assert "reason" in status
    assert isinstance(status["enabled"], bool)
    assert isinstance(status["reason"], str)

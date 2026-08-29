from agent.context_compressor import ContextCompressor


def test_missing_active_task_is_restored_as_none_after_final_answer():
    turns = [
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "answered"},
    ]
    result = ContextCompressor._ensure_active_task_section(
        "## Goal\nKeep continuity.", turns
    )
    assert result.endswith("## Active Task\nNone")


def test_unanswered_user_input_is_preserved_verbatim():
    turns = [
        {"role": "assistant", "content": "prior answer"},
        {"role": "user", "content": "Please preserve this exact crux."},
    ]
    result = ContextCompressor._ensure_active_task_section(
        "## Goal\nKeep continuity.", turns
    )
    assert "## Active Task" in result
    assert "Please preserve this exact crux." in result


def test_existing_active_task_is_not_rewritten():
    summary = "## Goal\nG\n\n## Active Task\nOriginal"
    result = ContextCompressor._ensure_active_task_section(
        summary, [{"role": "user", "content": "new"}]
    )
    assert result == summary

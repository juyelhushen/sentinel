from sentinel.llm.prompts.base import Prompt


def test_prompt_converts_to_llm_messages() -> None:
    prompt = Prompt(
        system="You are Sentinel.",
        user="Investigate this issue.",
    )

    messages = prompt.to_message()

    assert len(messages) == 2

    assert messages[0].role == "system"
    assert messages[0].content == "You are Sentinel."

    assert messages[1].role == "user"
    assert messages[1].content == "Investigate this issue."
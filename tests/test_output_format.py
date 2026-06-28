"""Tests for output shaping across the prompt builder and the summarizers."""

from __future__ import annotations

from artificial_writer.core.output_format import OutputFormat
from artificial_writer.core.summarizers.anthropic_provider import AnthropicSummarizer
from artificial_writer.core.summarizers.base import estimate_tokens, trim_to_sentence
from artificial_writer.core.summarizers.extractive import ExtractiveSummarizer
from artificial_writer.core.summarizers.openai_provider import OpenAISummarizer
from artificial_writer.core.summarizers.prompt import build_prompt

from .conftest import SAMPLE_TEXT


def test_build_prompt_prose_is_unchanged_default() -> None:
    prose = build_prompt("ARTICLE BODY")
    assert prose == build_prompt("ARTICLE BODY", OutputFormat.PROSE)
    assert "clear, concise prose" in prose
    assert "ARTICLE BODY" in prose


def test_build_prompt_differs_per_format() -> None:
    prompts = {fmt: build_prompt("BODY", fmt) for fmt in OutputFormat}
    # Every format produces a distinct prompt.
    assert len(set(prompts.values())) == len(OutputFormat)
    # Each carries its own steering and the shared guidance.
    assert "bullet points" in prompts[OutputFormat.BULLETS]
    assert "12-year-old" in prompts[OutputFormat.ELI5]
    assert "tweet thread" in prompts[OutputFormat.TWEET]
    assert "LinkedIn" in prompts[OutputFormat.LINKEDIN]
    for prompt in prompts.values():
        assert "no preamble" in prompt
        assert "BODY" in prompt


def test_extractive_bullets_returns_dash_lines() -> None:
    result = ExtractiveSummarizer(num_sentences=3).summarize(
        SAMPLE_TEXT, output_format=OutputFormat.BULLETS
    )
    lines = result.summary.splitlines()
    assert len(lines) == 3
    assert all(line.startswith("- ") for line in lines)
    assert result.cost_usd == 0.0


def test_extractive_non_bullets_fall_back_to_prose() -> None:
    # ELI5 isn't special-cased for the offline backend -> prose, never an error.
    result = ExtractiveSummarizer(num_sentences=2).summarize(
        SAMPLE_TEXT, output_format=OutputFormat.ELI5
    )
    assert "\n- " not in result.summary
    assert result.summary  # non-empty prose


class _FakeOpenAIResponse:
    def __init__(self, content: str) -> None:
        message = type("Msg", (), {"content": content})()
        self.choices = [type("Choice", (), {"message": message})()]
        self.usage = type("Usage", (), {"prompt_tokens": 100, "completion_tokens": 20})()


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, *, model: str, messages: list[dict[str, str]]) -> _FakeOpenAIResponse:
        self.prompts.append(messages[0]["content"])
        return _FakeOpenAIResponse("openai bullets")


def test_trim_to_sentence_caps_at_full_stop() -> None:
    text = "First sentence here. Second sentence runs well past the cap."
    trimmed = trim_to_sentence(text, 30)
    assert trimmed == "First sentence here."

    # No cap and already-short text are returned (stripped) unchanged.
    assert trim_to_sentence("  hello world  ", None) == "hello world"
    assert trim_to_sentence("short.", 1000) == "short."


def test_estimate_tokens_is_a_conservative_upper_bound() -> None:
    # Erring high: at least the word count, and ~chars/3.5 for longer prose.
    assert estimate_tokens("") == 0
    assert estimate_tokens("one two three") == 3  # word floor dominates short text
    assert estimate_tokens("a" * 70) == 20  # 70 / 3.5


def test_backend_applies_its_own_input_cap() -> None:
    summ = OpenAISummarizer.__new__(OpenAISummarizer)
    summ._client = _FakeOpenAIClient()  # type: ignore[attr-defined]
    summ._model = "gpt-4o-mini"  # type: ignore[attr-defined]
    summ.max_input_tokens = 8  # ~28 chars after the 3.5 chars/token conversion

    summ.summarize("First sentence here. Second sentence runs past the cap.")

    sent = summ._client.prompts[0]  # type: ignore[attr-defined]
    assert "First sentence here." in sent
    assert "Second sentence" not in sent


def test_openai_passes_formatted_prompt() -> None:
    summ = OpenAISummarizer.__new__(OpenAISummarizer)
    summ._client = _FakeOpenAIClient()  # type: ignore[attr-defined]
    summ._model = "gpt-4o-mini"  # type: ignore[attr-defined]

    result = summ.summarize("BODY", output_format=OutputFormat.BULLETS)

    assert "bullet points" in summ._client.prompts[0]  # type: ignore[attr-defined]
    assert result.summary == "openai bullets"
    assert result.input_tokens == 100
    assert result.output_tokens == 20
    assert result.cost_usd is not None and result.cost_usd > 0


class _FakeAnthropicMessage:
    def __init__(self, text: str) -> None:
        self.content = [type("Block", (), {"type": "text", "text": text})()]
        self.usage = type("Usage", (), {"input_tokens": 80, "output_tokens": 30})()


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.messages = self

    def create(
        self, *, model: str, max_tokens: int, messages: list[dict[str, str]]
    ) -> _FakeAnthropicMessage:
        self.prompts.append(messages[0]["content"])
        return _FakeAnthropicMessage("claude eli5")


def test_anthropic_passes_formatted_prompt() -> None:
    summ = AnthropicSummarizer.__new__(AnthropicSummarizer)
    summ._client = _FakeAnthropicClient()  # type: ignore[attr-defined]
    summ._model = "claude-haiku-4-5-20251001"  # type: ignore[attr-defined]

    result = summ.summarize("BODY", output_format=OutputFormat.ELI5)

    assert "12-year-old" in summ._client.prompts[0]  # type: ignore[attr-defined]
    assert result.summary == "claude eli5"
    assert result.input_tokens == 80
    assert result.output_tokens == 30
    assert result.cost_usd is not None and result.cost_usd > 0

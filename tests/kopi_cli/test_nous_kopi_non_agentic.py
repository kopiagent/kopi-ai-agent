"""Tests for the Nous-Kopi-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"kopi"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``kopi-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "kopi" tag namespace.

``is_nous_kopi_non_agentic`` should only match the actual Nous Research
Kopi-3 / Kopi-4 chat family.
"""

from __future__ import annotations

import pytest

from kopi_cli.model_switch import (
    _KOPI_MODEL_WARNING,
    _check_kopi_model_warning,
    is_nous_kopi_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "NousResearch/Kopi-3-Llama-3.1-70B",
        "NousResearch/Kopi-3-Llama-3.1-405B",
        "kopi-3",
        "Kopi-3",
        "kopi-4",
        "kopi-4-405b",
        "kopi_4_70b",
        "openrouter/kopi3:70b",
        "openrouter/nousresearch/kopi-4-405b",
        "NousResearch/Kopi3",
        "kopi-3.1",
    ],
)
def test_matches_real_nous_kopi_chat_models(model_name: str) -> None:
    assert is_nous_kopi_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous Kopi 3/4"
    )
    assert _check_kopi_model_warning(model_name) == _KOPI_MODEL_WARNING


@pytest.mark.parametrize(
    "model_name",
    [
        # Kyle's local Modelfile — qwen3:14b under a custom tag
        "kopi-brain:qwen3-14b-ctx16k",
        "kopi-brain:qwen3-14b-ctx32k",
        "kopi-honcho:qwen3-8b-ctx8k",
        # Plain unrelated models
        "qwen3:14b",
        "qwen3-coder:30b",
        "qwen2.5:14b",
        "claude-opus-4-6",
        "anthropic/claude-sonnet-4.5",
        "gpt-5",
        "openai/gpt-4o",
        "google/gemini-2.5-flash",
        "deepseek-chat",
        # Non-chat Kopi models we don't warn about
        "kopi-llm-2",
        "kopi2-pro",
        "nous-kopi-2-mistral",
        # Edge cases
        "",
        "kopi",  # bare "kopi" isn't the 3/4 family
        "kopi-brain",
        "brain-kopi-3-impostor",  # "3" not preceded by /: boundary
    ],
)
def test_does_not_match_unrelated_models(model_name: str) -> None:
    assert not is_nous_kopi_non_agentic(model_name), (
        f"expected {model_name!r} NOT to be flagged as Nous Kopi 3/4"
    )
    assert _check_kopi_model_warning(model_name) == ""


def test_none_like_inputs_are_safe() -> None:
    assert is_nous_kopi_non_agentic("") is False
    # Defensive: the helper shouldn't crash on None-ish falsy input either.
    assert _check_kopi_model_warning("") == ""

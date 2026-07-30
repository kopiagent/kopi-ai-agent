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



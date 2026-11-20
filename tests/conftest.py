"""
Every test runs from the toy example's folder, as a user runs from a
project: the networks in its ``configs/`` and the models in its
``extensions/`` are found there. A test that needs another example calls
:func:`run_from`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
# The packages of a project, imported from the folder it runs from.
PROJECT_PACKAGES = ("builders", "analyses", "extensions")


def run_from(example: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the rest of the test from ``examples/<example>/``, with its own
    project packages, not those another example imported before."""

    monkeypatch.chdir(EXAMPLES / example)
    monkeypatch.syspath_prepend(str(EXAMPLES / example))
    for name in [name for name in sys.modules if name.partition(".")[0] in PROJECT_PACKAGES]:
        monkeypatch.delitem(sys.modules, name)


@pytest.fixture(autouse=True)
def _run_from_the_toy_example(monkeypatch: pytest.MonkeyPatch) -> None:
    run_from("toy", monkeypatch)

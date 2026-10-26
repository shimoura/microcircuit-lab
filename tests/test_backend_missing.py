"""A copy of the core without a backend folder says how to add it."""

import sys

import pytest

from microcircuit_lab import backends


def test_missing_backend_folder_gives_a_clear_error(tmp_path, monkeypatch):
    # The package now looks for its backends in an empty folder
    monkeypatch.setattr(backends, "__path__", [str(tmp_path)])
    for name in [name for name in sys.modules if name.startswith("microcircuit_lab.backends.brian2")]:
        monkeypatch.delitem(sys.modules, name)
    with pytest.raises(ModuleNotFoundError, match="no brian2 backend.*--backends brian2"):
        backends.get_backend("brian2")

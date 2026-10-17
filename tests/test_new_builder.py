"""The scaffold new_builder.py writes must stay runnable: rendered stub
is valid Python and produces a network directory that validates."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from microcircuit_lab.io import validate_network_config

_NEW_BUILDER = Path(__file__).resolve().parents[1] / "scripts" / "new_builder.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render_stub(name: str) -> str:
    return _load_module(_NEW_BUILDER, "new_builder").render_stub(name)


def test_rendered_stub_is_valid_python() -> None:
    compile(_render_stub("demo_model"), "<stub>", "exec")


def test_scaffolded_builder_writes_a_directory_that_validates(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    stub_path = tmp_path / "demo_model.py"
    stub_path.write_text(_render_stub("demo_model"))

    _load_module(stub_path, "demo_model").main([])

    network_dir = tmp_path / "configs" / "network" / "demo_model"
    assert network_dir.is_dir()
    config = validate_network_config(network_dir)
    assert set(config.populations) == {"E", "I"}

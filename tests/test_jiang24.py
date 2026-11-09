"""The jiang24 builder's analysis files. ``init --with-core`` copies ``configs/`` but
not ``analyses/``, so the default file must not name the plots in ``analyses/``."""

from builders.jiang24 import generate_jiang24
from microcircuit_lab.config.yaml_files import read_yaml


def test_fig6_analysis(tmp_path):
    generate_jiang24(config_dir=tmp_path)

    default = read_yaml(tmp_path / "analysis" / "jiang24.yaml")
    fig6 = read_yaml(tmp_path / "analysis" / "jiang24_fig6.yaml")

    assert set(default) == {"style"}
    assert fig6["style"] == default["style"]
    assert fig6["jiang24_raster"]["enabled"] is True
    assert fig6["jiang24_firing_rates"]["enabled"] is True

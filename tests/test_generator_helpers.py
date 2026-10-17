"""The weight/delay dict builders in microcircuit_lab.io."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from microcircuit_lab.config.network import DelayDistribution, WeightDistribution
from microcircuit_lab.io import delay, weight


def test_weight_carries_the_unit_through() -> None:
    assert weight(0.15, unit="PSP", rel_std=0.1) == {
        "mean": 0.15, "rel_std": 0.1, "distribution": "normal", "unit": "PSP",
    }
    assert weight(-10.0, unit="PSC")["unit"] == "PSC"
    assert weight(1.0, unit="native")["unit"] == "native"


def test_distribution_is_inferred_from_spread_but_can_be_forced() -> None:
    assert weight(0.15, unit="PSP")["distribution"] == "fixed"          # no spread
    assert weight(0.15, unit="PSP", rel_std=0.1)["distribution"] == "normal"
    assert delay(1.5)["distribution"] == "fixed"
    assert delay(1.5, rel_std=0.5)["distribution"] == "normal"
    assert delay(1.5, rel_std=0.5, distribution="lognormal")["distribution"] == "lognormal"


def test_output_is_exactly_the_on_disk_schema_dump() -> None:
    assert weight(0.15, unit="PSP", rel_std=0.1) == WeightDistribution(
        mean=0.15, rel_std=0.1, distribution="normal", unit="PSP"
    ).model_dump()
    assert delay(1.5) == DelayDistribution(
        mean=1.5, rel_std=0.0, distribution="fixed"
    ).model_dump()


def test_invalid_values_raise_here_not_downstream() -> None:
    with pytest.raises(ValidationError):
        weight(0.15, unit="volts")
    with pytest.raises(ValidationError):
        delay(0.0)  # DelayDistribution.mean must be > 0

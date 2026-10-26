"""The weight/delay dict builders in microcircuit_lab.builder_tools."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from microcircuit_lab.builder_tools import delay, weight
from microcircuit_lab.config.connectivity import DelayDistribution, WeightDistribution


def test_weight_carries_the_unit_through() -> None:
    assert weight(87.8, unit="pA", rel_std=0.1) == {
        "mean": 87.8, "rel_std": 0.1, "distribution": "normal", "unit": "pA",
    }
    assert weight(1.0, unit="nS")["unit"] == "nS"


def test_distribution_is_inferred_from_spread_but_can_be_forced() -> None:
    assert weight(87.8, unit="pA")["distribution"] == "fixed"          # no spread
    assert weight(87.8, unit="pA", rel_std=0.1)["distribution"] == "normal"
    assert delay(1.5)["distribution"] == "fixed"
    assert delay(1.5, rel_std=0.5)["distribution"] == "normal"
    assert delay(1.5, rel_std=0.5, distribution="lognormal")["distribution"] == "lognormal"


def test_output_is_exactly_the_on_disk_schema_dump() -> None:
    assert weight(87.8, unit="pA", rel_std=0.1) == WeightDistribution(
        mean=87.8, rel_std=0.1, distribution="normal", unit="pA"
    ).model_dump(exclude_none=True)
    # An unset minimum delay is left out of the file, not written as null.
    assert delay(1.5) == DelayDistribution(
        mean=1.5, rel_std=0.0, distribution="fixed"
    ).model_dump(exclude_none=True)


def test_invalid_values_raise_here_not_downstream() -> None:
    with pytest.raises(ValidationError):
        weight(0.15, unit="volts")
    with pytest.raises(ValidationError):
        delay(0.0)  # DelayDistribution.mean must be > 0

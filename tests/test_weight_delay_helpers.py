"""The weight/delay dict builders in microcircuit_lab.builder_tools."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from microcircuit_lab.builder_tools import delay, weight, zero_bound
from microcircuit_lab.config.connectivity import DelayDistribution, WeightDistribution


def test_weight_carries_the_unit_through() -> None:
    assert weight(87.8, unit="pA", rel_std=0.1) == {
        "distribution": "normal", "mean": 87.8, "std": pytest.approx(8.78), "unit": "pA",
    }
    assert weight(1.0, unit="nS")["unit"] == "nS"


def test_distribution_is_inferred_from_spread_but_can_be_forced() -> None:
    # no spread: a fixed value, without bounds
    assert weight(87.8, unit="pA", lower_bound=0.0, bound_mode="clip") == {"value": 87.8, "unit": "pA"}
    assert weight(87.8, unit="pA", rel_std=0.1)["distribution"] == "normal"
    assert delay(1.5) == {"value": 1.5}
    drawn = {"lower_bound": 0.05, "bound_mode": "redraw"}
    assert delay(1.5, rel_std=0.5, **drawn)["distribution"] == "normal"
    assert delay(1.5, rel_std=0.5, distribution="lognormal", **drawn)["distribution"] == "lognormal"


def test_uniform_is_written_as_min_and_max_with_the_given_mean_and_spread() -> None:
    entry = weight(100.0, unit="pA", rel_std=0.1, distribution="uniform")
    half_width = np.sqrt(3.0) * 10.0

    assert entry["min"] == pytest.approx(100.0 - half_width)
    assert entry["max"] == pytest.approx(100.0 + half_width)


def test_output_is_exactly_the_on_disk_schema_dump() -> None:
    assert weight(87.8, unit="pA", rel_std=0.1, **zero_bound(87.8, "redraw")) == WeightDistribution(
        distribution="normal", mean=87.8, std=8.78, lower_bound=0.0, bound_mode="redraw", unit="pA"
    ).model_dump(exclude_none=True)
    # Unset fields are left out of the file, not written as null.
    assert delay(1.5) == DelayDistribution(value=1.5).model_dump(exclude_none=True)


def test_invalid_values_raise_here_not_downstream() -> None:
    with pytest.raises(ValidationError):
        weight(0.15, unit="volts")
    with pytest.raises(ValidationError):
        delay(1.5, rel_std=0.5)  # a drawn delay needs a lower_bound

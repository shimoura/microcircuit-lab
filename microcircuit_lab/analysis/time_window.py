"""The time window ``begin`` to ``end`` that the analyses use."""

from __future__ import annotations


def resolve_end(run, begin: float, end: float | None) -> float:
    """
    The end of the analysis window: ``end``, or the end of the run if ``None``.

    Raises
    ------
    ValueError
        If ``end`` is not after ``begin``, or is after the run's ``t_sim``
        (rates would be divided by a time the run did not simulate).
    """

    t_sim = run.simulation.t_sim
    if end is None:
        end = t_sim
    if end > t_sim:
        raise ValueError(f"'end' ({end} ms) is after the end of the run (t_sim = {t_sim} ms).")
    if end <= begin:
        raise ValueError("'end' must be greater than 'begin'.")
    return end

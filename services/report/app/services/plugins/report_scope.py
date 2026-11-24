# Copyright 2026 masa@kugel
"""
Narrowing a report maker's query to one settled session (#343).

A settlement freezes the daily reports of exactly one session. The makers
select by business date and open counter, which is not enough: the open counter
starts again at 1 when a terminal is registered again, so two sessions can share
a date and an open counter. A settlement therefore passes:

- ``extra_match``: conditions added to the query, e.g. the session's
  business_counter and the settlement's cutoff on ``created_at``;
- ``unbounded``: drop the paging stages, so the frozen report holds everything.

Callers that pass neither get the report exactly as before.
"""

from typing import Any, Optional


def scope_pipeline(pipeline: list[dict], extra_match: Optional[dict], unbounded: bool) -> list[dict]:
    """
    Apply a settlement's scope to an aggregation pipeline.

    Args:
        pipeline: The maker's pipeline; its first stage is the ``$match``
        extra_match: Conditions to add to that ``$match``, or None
        unbounded: True to remove the top-level ``$skip`` / ``$limit`` stages

    Returns:
        The pipeline to run (a new list; the input is not changed)
    """
    scoped = list(pipeline)
    if extra_match:
        if not scoped or "$match" not in scoped[0]:
            raise ValueError("a report pipeline must start with $match")
        scoped[0] = {"$match": {**scoped[0]["$match"], **extra_match}}
    if unbounded:
        scoped = [stage for stage in scoped if "$skip" not in stage and "$limit" not in stage]
    return scoped


def scope_filter(filter: dict, extra_match: Optional[dict]) -> dict:
    """Add a settlement's conditions to a find() filter."""
    return {**filter, **extra_match} if extra_match else filter


def scope_of(kwargs: dict[str, Any]) -> tuple[Optional[dict], bool]:
    """Read the scope a caller passed through generate_report's keyword arguments."""
    return kwargs.get("extra_match"), bool(kwargs.get("unbounded", False))

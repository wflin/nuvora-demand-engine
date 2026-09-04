"""Research status state machine.

Single source of truth for the ResearchProject lifecycle. The API layer
validates status changes through this module; background jobs can reuse
``validate_transition`` without depending on FastAPI or the database.
"""

from enum import StrEnum


class ResearchStatus(StrEnum):
    """Formal lifecycle states of a research project."""

    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ALLOWED_TRANSITIONS: dict[ResearchStatus, set[ResearchStatus]] = {
    ResearchStatus.DRAFT: {ResearchStatus.RUNNING, ResearchStatus.CANCELLED},
    ResearchStatus.RUNNING: {
        ResearchStatus.COMPLETED,
        ResearchStatus.FAILED,
        ResearchStatus.CANCELLED,
    },
    ResearchStatus.COMPLETED: set(),
    ResearchStatus.FAILED: set(),
    ResearchStatus.CANCELLED: set(),
}

TERMINAL_STATES: frozenset[ResearchStatus] = frozenset(
    state for state, targets in ALLOWED_TRANSITIONS.items() if not targets
)


class InvalidStatusTransition(ValueError):
    """Raised when a research status transition is not allowed."""


def can_transition(current: ResearchStatus | str, target: ResearchStatus) -> bool:
    """Return whether moving from ``current`` to ``target`` is allowed."""
    return target in ALLOWED_TRANSITIONS[_coerce(current)]


def validate_transition(
    current: ResearchStatus | str,
    target: ResearchStatus,
) -> None:
    """Raise InvalidStatusTransition when the transition is not allowed."""
    current_status = _coerce(current)
    if target not in ALLOWED_TRANSITIONS[current_status]:
        raise InvalidStatusTransition(
            f"Cannot transition research status from "
            f"{current_status.value} to {target.value}"
        )


def _coerce(value: ResearchStatus | str) -> ResearchStatus:
    if isinstance(value, ResearchStatus):
        return value
    return ResearchStatus(value)

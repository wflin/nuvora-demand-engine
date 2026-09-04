"""Tests for the Research status state machine (pure logic, no database)."""

import pytest

from app.services.research import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    InvalidStatusTransition,
    ResearchStatus,
    can_transition,
    validate_transition,
)

LEGAL_TRANSITIONS = [
    (ResearchStatus.DRAFT, ResearchStatus.RUNNING),
    (ResearchStatus.DRAFT, ResearchStatus.CANCELLED),
    (ResearchStatus.RUNNING, ResearchStatus.COMPLETED),
    (ResearchStatus.RUNNING, ResearchStatus.FAILED),
    (ResearchStatus.RUNNING, ResearchStatus.CANCELLED),
]

ILLEGAL_TRANSITIONS = [
    (ResearchStatus.DRAFT, ResearchStatus.COMPLETED),
    (ResearchStatus.DRAFT, ResearchStatus.FAILED),
    (ResearchStatus.RUNNING, ResearchStatus.DRAFT),
    (ResearchStatus.COMPLETED, ResearchStatus.RUNNING),
    (ResearchStatus.COMPLETED, ResearchStatus.DRAFT),
    (ResearchStatus.COMPLETED, ResearchStatus.CANCELLED),
    (ResearchStatus.FAILED, ResearchStatus.RUNNING),
    (ResearchStatus.FAILED, ResearchStatus.COMPLETED),
    (ResearchStatus.CANCELLED, ResearchStatus.RUNNING),
    (ResearchStatus.CANCELLED, ResearchStatus.DRAFT),
]


def test_research_status_values() -> None:
    assert [state.value for state in ResearchStatus] == [
        "draft",
        "running",
        "completed",
        "failed",
        "cancelled",
    ]


@pytest.mark.parametrize(("current", "target"), LEGAL_TRANSITIONS)
def test_legal_transitions_are_allowed(
    current: ResearchStatus,
    target: ResearchStatus,
) -> None:
    assert can_transition(current, target) is True
    validate_transition(current, target)


@pytest.mark.parametrize(("current", "target"), ILLEGAL_TRANSITIONS)
def test_illegal_transitions_are_rejected(
    current: ResearchStatus,
    target: ResearchStatus,
) -> None:
    assert can_transition(current, target) is False
    with pytest.raises(InvalidStatusTransition):
        validate_transition(current, target)


def test_self_transitions_are_rejected() -> None:
    for state in ResearchStatus:
        assert can_transition(state, state) is False
        with pytest.raises(InvalidStatusTransition):
            validate_transition(state, state)


def test_terminal_states_have_no_outgoing_transitions() -> None:
    assert TERMINAL_STATES == frozenset(
        {
            ResearchStatus.COMPLETED,
            ResearchStatus.FAILED,
            ResearchStatus.CANCELLED,
        }
    )
    for state in TERMINAL_STATES:
        assert ALLOWED_TRANSITIONS[state] == set()
        for target in ResearchStatus:
            assert can_transition(state, target) is False


def test_transition_rules_cover_all_statuses() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(ResearchStatus)


def test_validate_transition_accepts_plain_strings() -> None:
    validate_transition("draft", ResearchStatus.RUNNING)
    with pytest.raises(InvalidStatusTransition):
        validate_transition("draft", ResearchStatus.COMPLETED)

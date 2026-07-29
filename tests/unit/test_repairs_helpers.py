"""Test the typed Repairs vocabulary and deterministic identifiers."""

from __future__ import annotations

import re

from homeassistant.helpers.issue_registry import IssueSeverity

from custom_components.intelligent_climate.repairs import (
    IssueCode,
    issue_id,
    issue_policy,
)

ENTRY_ID = "01JPRIVATECONFIGENTRY000000"


def test_issue_code_vocabulary_is_stable_and_complete() -> None:
    """Phase 1 exposes only the six approved stable issue codes."""
    assert tuple(code.value for code in IssueCode) == (
        "no_zones_configured",
        "missing_entity",
        "incompatible_entity",
        "migration_failed",
        "store_write_failed",
        "command_boundary_violation",
    )


def test_issue_id_is_deterministic_private_and_bounded() -> None:
    """The same entry/code produces one bounded ID without the raw entry ID."""
    first = issue_id(ENTRY_ID, IssueCode.MISSING_ENTITY)
    second = issue_id(ENTRY_ID, IssueCode.MISSING_ENTITY)

    assert first == second
    assert ENTRY_ID not in first
    assert re.fullmatch(r"entry_[0-9a-f]{12}_missing_entity", first)


def test_issue_ids_differ_by_entry_and_code() -> None:
    """Entry scope and issue code both contribute to identity."""
    baseline = issue_id(ENTRY_ID, IssueCode.MISSING_ENTITY)

    assert issue_id("another-entry", IssueCode.MISSING_ENTITY) != baseline
    assert issue_id(ENTRY_ID, IssueCode.INCOMPATIBLE_ENTITY) != baseline


def test_issue_policy_matches_current_error_and_persistence_design() -> None:
    """Every Task 13 issue is non-fixable and reports a current error."""
    persistent = {
        IssueCode.MIGRATION_FAILED,
        IssueCode.STORE_WRITE_FAILED,
        IssueCode.COMMAND_BOUNDARY_VIOLATION,
    }

    for code in IssueCode:
        policy = issue_policy(code)
        assert policy.severity is IssueSeverity.ERROR
        assert policy.is_fixable is False
        assert policy.is_persistent is (code in persistent)


def test_empty_entry_id_is_rejected() -> None:
    """Issue IDs cannot be created without an entry scope."""
    try:
        issue_id("", IssueCode.MISSING_ENTITY)
    except ValueError as err:
        assert str(err) == "config-entry ID must not be empty"
    else:
        raise AssertionError("empty entry ID was accepted")

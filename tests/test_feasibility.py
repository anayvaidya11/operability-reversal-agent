"""Unit tests for the resource-feasibility checker (Step 3)."""

import pytest

from src.feasibility import (
    check_feasibility,
    FeasibilityStatus,
    UnknownCapabilityError,
)


def test_cabg_needs_tertiary_from_local():
    r = check_feasibility("cabg", "local")
    assert r.status is FeasibilityStatus.NEEDS_TERTIARY
    assert "travel to tertiary" in r.note


def test_hba1c_partial_from_local():
    r = check_feasibility("hba1c_test", "local")
    assert r.status is FeasibilityStatus.PARTIAL_LOCAL


def test_cardiac_surgeon_needs_tertiary():
    r = check_feasibility("cardiac_surgeon", "local")
    assert r.status is FeasibilityStatus.NEEDS_TERTIARY


def test_locally_available_capability_is_local():
    # ecg is local_available == "yes" in the profile
    r = check_feasibility("ecg", "local")
    assert r.status is FeasibilityStatus.LOCAL


def test_needs_tertiary_note_when_patient_already_tertiary():
    r = check_feasibility("cabg", "tertiary")
    assert r.status is FeasibilityStatus.NEEDS_TERTIARY
    assert "already at tertiary" in r.note


def test_unknown_capability_raises():
    with pytest.raises(UnknownCapabilityError):
        check_feasibility("teleportation", "local")


def test_invalid_tier_raises():
    with pytest.raises(ValueError, match="tier must be one of"):
        check_feasibility("cabg", "regional")

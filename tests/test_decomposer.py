"""Unit tests for the modifiable-vs-fixed decomposer (Step 3)."""

import json
from pathlib import Path

import pytest

from src.decomposer import decompose, DecompositionError
from data.validate import EUROSCORE_FIELDS

VIGNETTES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "vignettes.json").read_text()
)["vignettes"]
BY_ID = {v["id"]: v for v in VIGNETTES}


def test_grandmother_decomposition():
    result = decompose(BY_ID["SYNTH-006"])

    # exactly 3 euroscore_visible levers, mapped to the expected fields
    visible = {v.lever: v.euroscore_field for v in result.euroscore_visible}
    assert visible == {
        "asthma_control": "chronic_lung_disease",
        "mobility": "poor_mobility",
        "heart_failure_symptoms": "nyha_class",
    }

    # each visible lever exposes the CURRENT value of its EuroSCORE field
    current = {v.euroscore_field: v.current_value for v in result.euroscore_visible}
    assert current["chronic_lung_disease"] is True
    assert current["poor_mobility"] is True
    assert current["nyha_class"] == "III"

    # exactly 2 needs_risk_modifier levers, all flagged NOT_YET_GROUNDED
    modifiers = {m.lever for m in result.needs_risk_modifier}
    assert modifiers == {"hba1c", "anemia"}
    assert all(m.MODIFIER_LAYER_NOT_YET_GROUNDED is True for m in result.needs_risk_modifier)
    assert all("Option-B" in m.note for m in result.needs_risk_modifier)

    # fixed set excludes the 3 visible fields but contains age and sex
    assert "age" in result.fixed
    assert "sex" in result.fixed
    assert "diabetes_on_insulin" in result.fixed  # insulin status is FIXED (SPEC §f)
    for visible_field in ("chronic_lung_disease", "poor_mobility", "nyha_class"):
        assert visible_field not in result.fixed
    assert len(result.fixed) == len(EUROSCORE_FIELDS) - 3


@pytest.mark.parametrize("vid", ["SYNTH-016", "SYNTH-018"])
def test_fixed_high_risk_empty_levers_decompose_to_zero_modifiable(vid):
    result = decompose(BY_ID[vid])
    assert result.euroscore_visible == []
    assert result.needs_risk_modifier == []
    # with no modifiable levers, ALL EuroSCORE inputs are fixed
    assert set(result.fixed) == EUROSCORE_FIELDS


def test_every_reversible_has_at_least_two_visible():
    for v in VIGNETTES:
        if v["design_intent"] == "reversible_with_optimization":
            result = decompose(v)
            assert len(result.euroscore_visible) >= 2, v["id"]


def test_lever_field_mismatch_raises():
    bad = json.loads(json.dumps(BY_ID["SYNTH-006"]))  # deep copy
    # corrupt a visible lever's declared euroscore_field
    for lev in bad["modifiable_levers"]:
        if lev["lever"] == "asthma_control":
            lev["euroscore_field"] = "poor_mobility"
    with pytest.raises(DecompositionError, match="declares euroscore_field"):
        decompose(bad)


def test_invalid_coupling_raises():
    bad = json.loads(json.dumps(BY_ID["SYNTH-006"]))
    bad["modifiable_levers"][0]["coupling"] = "sometimes"
    with pytest.raises(DecompositionError, match="invalid coupling"):
        decompose(bad)


def test_non_dict_raises():
    with pytest.raises(DecompositionError):
        decompose("not a vignette")

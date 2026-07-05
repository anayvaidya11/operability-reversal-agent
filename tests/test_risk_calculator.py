"""Unit tests for the EuroSCORE II risk calculator (Step 3)."""

import json
import math
from pathlib import Path

import pytest

from src.risk_calculator import (
    EuroscoreInputError,
    compute_euroscore_ii,
    euroscore_inputs_to_linear_predictor,
)
from src import euroscore_ii_coefficients as C

VIGNETTES = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "vignettes.json").read_text()
)["vignettes"]
BY_ID = {v["id"]: v for v in VIGNETTES}


def make_baseline() -> dict:
    """All EuroSCORE inputs at their REFERENCE category (every beta = 0 except age),
    age exactly at the age baseline (60 -> x = 1)."""
    return {
        "age": 60,
        "sex": "male",
        "renal_impairment": "normal",
        "extracardiac_arteriopathy": False,
        "poor_mobility": False,
        "previous_cardiac_surgery": False,
        "chronic_lung_disease": False,
        "active_endocarditis": False,
        "critical_preoperative_state": False,
        "diabetes_on_insulin": False,
        "nyha_class": "I",
        "ccs_class4_angina": False,
        "lv_function": "good",
        "recent_mi": False,
        "pulmonary_hypertension": "none",
        "urgency": "elective",
        "weight_of_intervention": "isolated_cabg",
        "thoracic_aorta_surgery": False,
    }


# --- (a) hand-computed known-input cases ---------------------------------------------

def test_reference_baseline_linear_predictor_by_hand():
    # y = CONSTANT + BETA_AGE * 1  (all other factors are reference / beta 0)
    #   = -4.789594 + 0.0285181 = -4.7610759
    expected_y = C.CONSTANT + C.BETA_AGE * 1
    assert abs(expected_y - (-4.7610759)) < 1e-9  # sanity on the sourced constants
    y = euroscore_inputs_to_linear_predictor(make_baseline())
    assert round(y, 4) == round(-4.7610759, 4)


def test_reference_baseline_logistic_transform():
    y = euroscore_inputs_to_linear_predictor(make_baseline())
    expected_pct = math.exp(y) / (1 + math.exp(y)) * 100
    assert abs(compute_euroscore_ii(make_baseline()) - expected_pct) < 1e-12


def test_grandmother_linear_predictor_by_hand():
    # SYNTH-006, hand sum of sourced betas (see report):
    #   age 71 -> x=12 -> 0.0285181*12 = 0.3422172
    #   female 0.2196434 + renal(51-85) 0.303553 + poor_mobility 0.2407181
    #   + chronic_lung 0.1886564 + insulin 0.3542749 + NYHA III 0.2958358
    #   + LV moderate 0.3150652
    #   Σβx = 2.2599640 ; y = -4.789594 + 2.2599640 = -2.5296300
    g = BY_ID["SYNTH-006"]["euroscore_inputs"]
    y = euroscore_inputs_to_linear_predictor(g)
    assert round(y, 4) == round(-2.5296300, 4)
    assert abs(compute_euroscore_ii(g) - 7.3807) < 1e-3


# --- (b) all vignettes produce plausible 0-100 outputs -------------------------------

@pytest.mark.parametrize("vid", list(BY_ID))
def test_all_vignettes_produce_plausible_outputs(vid):
    pct = compute_euroscore_ii(BY_ID[vid]["euroscore_inputs"])
    assert 0.0 <= pct <= 100.0
    assert math.isfinite(pct)


# --- (c) monotonicity: worsening a factor strictly increases predicted mortality -----

def _bump(field, worse_value):
    base = make_baseline()
    before = compute_euroscore_ii(base)
    base[field] = worse_value
    after = compute_euroscore_ii(base)
    return before, after


@pytest.mark.parametrize(
    "field,worse",
    [
        ("chronic_lung_disease", True),
        ("poor_mobility", True),
        ("previous_cardiac_surgery", True),
        ("critical_preoperative_state", True),
        ("diabetes_on_insulin", True),
        ("recent_mi", True),
        ("thoracic_aorta_surgery", True),
        ("ccs_class4_angina", True),
        ("extracardiac_arteriopathy", True),
        ("active_endocarditis", True),
        ("nyha_class", "IV"),
        ("lv_function", "poor"),
        ("renal_impairment", "severe"),
        ("pulmonary_hypertension", "severe"),
        ("urgency", "emergency"),
        ("weight_of_intervention", "cabg_plus_other"),
    ],
)
def test_worsening_factor_strictly_increases(field, worse):
    before, after = _bump(field, worse)
    assert after > before


def test_older_age_strictly_increases():
    base = make_baseline()
    before = compute_euroscore_ii(base)
    base["age"] = 75
    assert compute_euroscore_ii(base) > before


def test_nyha_is_monotone_across_classes():
    scores = []
    for cls in ("I", "II", "III", "IV"):
        base = make_baseline()
        base["nyha_class"] = cls
        scores.append(compute_euroscore_ii(base))
    assert scores == sorted(scores)
    assert len(set(scores)) == 4  # strictly increasing


def test_lv_is_monotone_across_categories():
    scores = []
    for lv in ("good", "moderate", "poor"):
        base = make_baseline()
        base["lv_function"] = lv
        scores.append(compute_euroscore_ii(base))
    assert scores == sorted(scores)
    assert len(set(scores)) == 3


# --- (d) input validation raises loudly ----------------------------------------------

def test_missing_field_raises():
    base = make_baseline()
    del base["age"]
    with pytest.raises(EuroscoreInputError, match="missing"):
        compute_euroscore_ii(base)


def test_extra_field_raises():
    base = make_baseline()
    base["hba1c"] = 9.0
    with pytest.raises(EuroscoreInputError, match="unexpected"):
        compute_euroscore_ii(base)


def test_age_as_bool_raises():
    base = make_baseline()
    base["age"] = True
    with pytest.raises(EuroscoreInputError, match="age must be an int"):
        compute_euroscore_ii(base)


def test_boolean_field_as_string_raises():
    base = make_baseline()
    base["chronic_lung_disease"] = "yes"
    with pytest.raises(EuroscoreInputError, match="must be a bool"):
        compute_euroscore_ii(base)


def test_bad_categorical_raises():
    base = make_baseline()
    base["nyha_class"] = "V"
    with pytest.raises(EuroscoreInputError, match="nyha_class"):
        compute_euroscore_ii(base)


def test_age_out_of_range_raises():
    base = make_baseline()
    base["age"] = 200
    with pytest.raises(EuroscoreInputError, match="out of plausible range"):
        compute_euroscore_ii(base)


def test_bad_sex_raises():
    base = make_baseline()
    base["sex"] = "other"
    with pytest.raises(EuroscoreInputError, match="sex must be"):
        compute_euroscore_ii(base)


def test_non_dict_raises():
    with pytest.raises(EuroscoreInputError):
        compute_euroscore_ii(["not", "a", "dict"])

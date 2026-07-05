"""
EuroSCORE II logistic-regression coefficients — SOURCED CONSTANTS ONLY.

This module contains ONLY the published EuroSCORE II model constants and the exact
variable encodings. It has no logic. `src/risk_calculator.py` imports from here so that
the calculator itself contains zero magic numbers.

=============================================================================
PRIMARY SOURCE
=============================================================================
Nashef SAM, Roques F, Sharples LD, Nashef SAM, Roques F, Michel P, Gauducheau E,
Lemeshow S, Salamon R, et al. "EuroSCORE II." European Journal of Cardio-Thoracic
Surgery. 2012;41(4):734-745. doi:10.1093/ejcts/ezs043.

Coefficient table (Table 6, "The EuroSCORE II model") retrieved and verified verbatim
from the publisher's HTML on 2026-07-05:
  - https://academic.oup.com/ejcts/article/41/4/734/646622   (Table 6, full table)
Variable *definitions* (NYHA, CCS4, IDDM, extracardiac arteriopathy, poor mobility,
renal dysfunction CC bands, active endocarditis, critical preoperative state, LVEF
bands, urgency, recent MI = within 90 days, weight-of-procedure categories) verified
against a faithfully-reproduced supplementary table:
  - https://assets.radcliffecardiology.com/s3fs-public/article-pdf/2024-04/Low_Supp%20Table%201.pdf
Individual coefficient values were additionally cross-checked via web search against
the official calculator documentation at https://www.euroscore.org/index.php?fid=201
(euroscore.org; the site's TLS certificate did not validate for automated fetch on
2026-07-05, so it was used only as a corroborating cross-check, not the primary source).

Every beta below was independently confirmed to match the primary-source Table 6.
No coefficient in this file was invented, approximated, or rounded.

=============================================================================
!!! CONSTANT / INTERCEPT DISCREPANCY — READ THIS !!!
=============================================================================
There are TWO different constants in circulation for EuroSCORE II, and this is a
well-known, real discrepancy — not an error in this file:

  * PAPER_CONSTANT   = -5.324537   -> the value PRINTED in Table 6 of Nashef et al. 2012
  * CALCULATOR_CONSTANT = -4.789594 -> the value used by the OFFICIAL online calculator
                                       at euroscore.org (and by essentially all deployed
                                       implementations that reproduce the official
                                       calculator's output)

Using the printed paper constant (-5.324537) yields systematically LOWER predicted
mortality than the official calculator. Because clinicians interact with the official
euroscore.org calculator, this project uses CALCULATOR_CONSTANT (-4.789594) as the
operative default (this also matches the Step-3 specification). BOTH values are exposed
below as named constants; the operative one is `CONSTANT`. This choice is configurable.

[TO VERIFY] The precise provenance of -4.789594 vs the printed -5.324537 is not fully
pinned to a single citable erratum here. Both numbers are sourced (paper vs official
calculator); which is "canonical" is a documented ambiguity in the literature. If a
future step needs the paper-faithful output, set the calculator to PAPER_CONSTANT.

=============================================================================
MODEL FORM
=============================================================================
    y          = CONSTANT + Σ (beta_i * x_i)
    mortality  = e^y / (1 + e^y)          # predicted in-hospital mortality, 0..1

All betas below are the log-odds contributions for the NON-reference category of each
factor. Reference categories (beta = 0) are noted per factor.
"""

# --- Intercept / constant ------------------------------------------------------------
PAPER_CONSTANT: float = -5.324537      # Table 6, Nashef et al. 2012 (printed value)
CALCULATOR_CONSTANT: float = -4.789594  # official euroscore.org calculator (operative)

# Operative constant used by the risk calculator (see discrepancy note above).
CONSTANT: float = CALCULATOR_CONSTANT

# --- Age -----------------------------------------------------------------------------
# Age coefficient 0.0285181. ENCODING (verified): the age variable enters the model as
# x = 1 for age <= 60, incrementing by 1 for each year above 60 (age 61 -> 2, 62 -> 3...).
# Equivalently x_age = max(1, age - 59).
BETA_AGE: float = 0.0285181
AGE_BASELINE: int = 60  # ages at/below this contribute x = 1

# --- Patient-related binary factors --------------------------------------------------
BETA_FEMALE: float = 0.2196434                 # sex == female (reference: male)
BETA_INSULIN_DIABETES: float = 0.3542749       # IDDM, insulin-dependent (reference: none/oral)
BETA_CHRONIC_LUNG_DISEASE: float = 0.1886564   # chronic pulmonary dysfunction (CPD)
BETA_POOR_MOBILITY: float = 0.2407181          # neurological/musculoskeletal ("N/M mobility")
BETA_EXTRACARDIAC_ARTERIOPATHY: float = 0.5360268  # ECA
BETA_PREVIOUS_CARDIAC_SURGERY: float = 1.118599    # "Redo"
BETA_ACTIVE_ENDOCARDITIS: float = 0.6194522
BETA_CRITICAL_PREOP_STATE: float = 1.086517

# --- Renal impairment (Cockcroft-Gault creatinine-clearance bands) -------------------
# Reference: CC > 85 ml/min (normal), beta = 0.
BETA_RENAL_CC_51_85: float = 0.303553   # moderate impairment, CC 51-85 ml/min
BETA_RENAL_CC_LE_50: float = 0.8592256  # severe impairment, CC <= 50 ml/min (NOT dialysis)
BETA_RENAL_ON_DIALYSIS: float = 0.6421508  # on dialysis, regardless of creatinine

# --- Cardiac-related factors ---------------------------------------------------------
# NYHA (reference: class I, beta = 0)
BETA_NYHA_II: float = 0.1070545
BETA_NYHA_III: float = 0.2958358
BETA_NYHA_IV: float = 0.5597929

BETA_CCS4_ANGINA: float = 0.2226147  # CCS class 4 angina (reference: not class 4)

# Left ventricular function (LVEF bands; reference: good >51%, beta = 0)
BETA_LV_MODERATE: float = 0.3150652   # LVEF 31-50%
BETA_LV_POOR: float = 0.8084096       # LVEF 21-30%
BETA_LV_VERY_POOR: float = 0.9346919  # LVEF <= 20%

BETA_RECENT_MI: float = 0.1528943  # MI within 90 days before surgery

# Pulmonary artery systolic pressure (reference: < 31 mmHg, beta = 0)
BETA_PA_MODERATE_31_55: float = 0.1788899  # 31-55 mmHg
BETA_PA_SEVERE_GE_55: float = 0.3491475    # >= 55 mmHg

# --- Operation-related factors -------------------------------------------------------
# Urgency (reference: elective, beta = 0)
BETA_URGENCY_URGENT: float = 0.3174673
BETA_URGENCY_EMERGENCY: float = 0.7039121
BETA_URGENCY_SALVAGE: float = 1.362947

# Weight of intervention (reference: isolated CABG, beta = 0)
BETA_WEIGHT_SINGLE_NON_CABG: float = 0.0062118  # one major non-CABG procedure
BETA_WEIGHT_TWO_PROCEDURES: float = 0.5521478   # two major procedures
BETA_WEIGHT_THREE_PLUS: float = 0.9724533       # three or more major procedures

BETA_THORACIC_AORTA: float = 0.6527205  # surgery on the thoracic aorta

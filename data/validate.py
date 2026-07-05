#!/usr/bin/env python3
"""
validate.py — validator for the data artifacts.

Two layers:
  1. STRUCTURAL checks (Step 2): data/vignettes.json and data/capability_profile.json
     conform to data/SCHEMA.md, and vignette field names align with docs/SPEC.md. These
     are pure — no risk math — and run standalone with `--structure-only` even if src/ is
     absent.
  2. SCORE-PROPERTY checks (added Step 4.5): using the REAL EuroSCORE II calculator from
     src/, every vignette must satisfy its design_intent's score relationship against
     OPERABILITY_THRESHOLD (imported from src/config.py, not hard-coded). This layer makes
     validate.py depend on src/ — intended, since Step 3 provides the calculator.

Usage:
    python3 data/validate.py                  # structure + score properties (needs src/)
    python3 data/validate.py --structure-only # structure checks only (no src/ needed)

Exit code 0 = all requested checks pass. Non-zero = errors (printed to stderr).
"""

import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
# Put the repo root on sys.path so the score-property check can import src/ when this
# file is run directly as `python3 data/validate.py`. Harmless for the structural layer.
sys.path.insert(0, str(DATA_DIR.parent))

# --- Canonical field sets (mirror docs/SPEC.md via data/SCHEMA.md section 1) ----------

EUROSCORE_FIELDS = {
    # patient-related (SPEC.md section d)
    "age", "sex", "renal_impairment", "extracardiac_arteriopathy", "poor_mobility",
    "previous_cardiac_surgery", "chronic_lung_disease", "active_endocarditis",
    "critical_preoperative_state", "diabetes_on_insulin",
    # cardiac-related
    "nyha_class", "ccs_class4_angina", "lv_function", "recent_mi",
    "pulmonary_hypertension",
    # operation-related
    "urgency", "weight_of_intervention", "thoracic_aorta_surgery",
}

MODIFIABLE_EUROSCORE_VISIBLE_FIELDS = {
    "chronic_lung_disease", "poor_mobility", "nyha_class", "critical_preoperative_state",
}

LEVER_NAMES = {
    "hba1c", "asthma_control", "smoking_status", "anemia", "albumin", "blood_pressure",
    "mobility", "heart_failure_symptoms", "critical_preop_stabilization",
}

DESIGN_INTENTS = {
    "operable_at_baseline", "reversible_with_optimization", "fixed_high_risk",
}
COUPLINGS = {"euroscore_visible", "needs_risk_modifier"}
AVAILABILITY_VALUES = {"yes", "no", "partial", "unknown"}
CATEGORY_VALUES = {
    "labs_diagnostics", "medications", "procedures", "specialist_availability",
}
LOCATION_TIERS = {"local", "tertiary"}
MIN_VISIBLE_LEVERS_FOR_REVERSIBLE = 2


class Validator:
    def __init__(self):
        self.errors = []

    def err(self, where, msg):
        self.errors.append(f"[{where}] {msg}")

    def _load(self, name):
        path = DATA_DIR / name
        if not path.exists():
            self.err(name, "file not found")
            return None
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as e:
            self.err(name, f"invalid JSON: {e}")
            return None

    # --- vignettes.json ---------------------------------------------------------------

    def validate_vignettes(self):
        where = "vignettes.json"
        data = self._load("vignettes.json")
        if data is None:
            return

        meta = data.get("_meta")
        if not isinstance(meta, dict):
            self.err(where, "missing or non-object '_meta'")
        else:
            if meta.get("synthetic") is not True:
                self.err(where, "_meta.synthetic must be true")
            flag = meta.get("supplementary_modifier_flag", "")
            if "[TO VERIFY" not in str(flag):
                self.err(where, "_meta.supplementary_modifier_flag must carry a [TO VERIFY] marker")

        vignettes = data.get("vignettes")
        if not isinstance(vignettes, list):
            self.err(where, "missing or non-array 'vignettes'")
            return
        if not vignettes:
            self.err(where, "'vignettes' is empty")
            return

        seen_ids = set()
        grandmother_count = 0

        for i, v in enumerate(vignettes):
            tag = f"{where}:vignette[{i}]"
            if not isinstance(v, dict):
                self.err(tag, "vignette is not an object")
                continue

            vid = v.get("id")
            if not isinstance(vid, str) or not vid:
                self.err(tag, "missing/invalid 'id'")
            else:
                tag = f"{where}:{vid}"
                if vid in seen_ids:
                    self.err(tag, "duplicate id")
                seen_ids.add(vid)

            if v.get("synthetic") is not True:
                self.err(tag, "'synthetic' must be true")

            di = v.get("design_intent")
            if di not in DESIGN_INTENTS:
                self.err(tag, f"invalid design_intent: {di!r}")

            if not isinstance(v.get("rationale"), str) or not v.get("rationale"):
                self.err(tag, "missing/invalid 'rationale'")

            if v.get("location_tier") not in LOCATION_TIERS:
                self.err(tag, f"invalid location_tier: {v.get('location_tier')!r}")

            ga = v.get("grandmother_analog")
            if not isinstance(ga, bool):
                self.err(tag, "'grandmother_analog' must be boolean")
            elif ga:
                grandmother_count += 1
                if di != "reversible_with_optimization":
                    self.err(tag, "grandmother_analog must have design_intent "
                                  "'reversible_with_optimization'")

            # euroscore_inputs: keys must equal canonical set exactly
            ei = v.get("euroscore_inputs")
            if not isinstance(ei, dict):
                self.err(tag, "missing/invalid 'euroscore_inputs'")
            else:
                keys = set(ei.keys())
                missing = EUROSCORE_FIELDS - keys
                extra = keys - EUROSCORE_FIELDS
                if missing:
                    self.err(tag, f"euroscore_inputs missing fields: {sorted(missing)}")
                if extra:
                    self.err(tag, f"euroscore_inputs has unexpected fields: {sorted(extra)}")

            # modifiable_levers
            levers = v.get("modifiable_levers")
            visible_count = 0
            if not isinstance(levers, list):
                self.err(tag, "missing/invalid 'modifiable_levers' (must be array)")
            else:
                for j, lev in enumerate(levers):
                    ltag = f"{tag}:lever[{j}]"
                    if not isinstance(lev, dict):
                        self.err(ltag, "lever is not an object")
                        continue
                    if lev.get("lever") not in LEVER_NAMES:
                        self.err(ltag, f"unknown lever name: {lev.get('lever')!r}")
                    coupling = lev.get("coupling")
                    if coupling not in COUPLINGS:
                        self.err(ltag, f"invalid coupling: {coupling!r}")
                    ef = lev.get("euroscore_field")
                    if coupling == "euroscore_visible":
                        visible_count += 1
                        if ef not in MODIFIABLE_EUROSCORE_VISIBLE_FIELDS:
                            self.err(ltag, f"euroscore_visible lever needs euroscore_field "
                                           f"in {sorted(MODIFIABLE_EUROSCORE_VISIBLE_FIELDS)}, got {ef!r}")
                    elif coupling == "needs_risk_modifier":
                        if ef is not None:
                            self.err(ltag, f"needs_risk_modifier lever must have euroscore_field null, got {ef!r}")
                    if not isinstance(lev.get("status"), str):
                        self.err(ltag, "missing/invalid 'status'")
                    if not isinstance(lev.get("optimizable"), bool):
                        self.err(ltag, "missing/invalid 'optimizable'")
                    if not isinstance(lev.get("note"), str):
                        self.err(ltag, "missing/invalid 'note'")

            # coupling constraint for reversible cases
            if di == "reversible_with_optimization" and isinstance(levers, list):
                if visible_count < MIN_VISIBLE_LEVERS_FOR_REVERSIBLE:
                    self.err(tag, f"reversible_with_optimization requires >= "
                                  f"{MIN_VISIBLE_LEVERS_FOR_REVERSIBLE} euroscore_visible "
                                  f"levers, found {visible_count}")

        if grandmother_count != 1:
            self.err(where, f"expected exactly 1 grandmother_analog, found {grandmother_count}")

    # --- capability_profile.json ------------------------------------------------------

    def validate_capabilities(self):
        where = "capability_profile.json"
        data = self._load("capability_profile.json")
        if data is None:
            return

        meta = data.get("_meta")
        if not isinstance(meta, dict) or meta.get("synthetic") is not True:
            self.err(where, "_meta.synthetic must be true")

        tiers = data.get("tiers")
        if not isinstance(tiers, dict):
            self.err(where, "missing/invalid 'tiers'")
        else:
            if set(tiers.keys()) != {"local", "tertiary"}:
                self.err(where, f"tiers must be exactly local+tertiary, got {sorted(tiers.keys())}")
            for key, expected_num in (("local", 1), ("tertiary", 2)):
                t = tiers.get(key)
                if not isinstance(t, dict):
                    self.err(where, f"tier '{key}' missing/invalid")
                    continue
                if t.get("tier") != expected_num:
                    self.err(where, f"tier '{key}' should have tier=={expected_num}")
                if not isinstance(t.get("name"), str):
                    self.err(where, f"tier '{key}' missing 'name'")
                if not isinstance(t.get("description"), str):
                    self.err(where, f"tier '{key}' missing 'description'")

        caps = data.get("capabilities")
        if not isinstance(caps, list) or not caps:
            self.err(where, "missing/empty 'capabilities'")
            return

        seen = set()
        for i, c in enumerate(caps):
            tag = f"{where}:capability[{i}]"
            if not isinstance(c, dict):
                self.err(tag, "capability is not an object")
                continue
            cid = c.get("capability_id")
            if not isinstance(cid, str) or not cid:
                self.err(tag, "missing/invalid 'capability_id'")
            else:
                tag = f"{where}:{cid}"
                if cid in seen:
                    self.err(tag, "duplicate capability_id")
                seen.add(cid)
            if c.get("category") not in CATEGORY_VALUES:
                self.err(tag, f"invalid category: {c.get('category')!r}")
            if not isinstance(c.get("description"), str):
                self.err(tag, "missing/invalid 'description'")
            if c.get("local_available") not in AVAILABILITY_VALUES:
                self.err(tag, f"invalid local_available: {c.get('local_available')!r}")
            if c.get("tertiary_available") not in AVAILABILITY_VALUES:
                self.err(tag, f"invalid tertiary_available: {c.get('tertiary_available')!r}")
            notes = c.get("notes")
            if not isinstance(notes, str):
                self.err(tag, "missing/invalid 'notes'")
            elif "[TO VERIFY" not in notes:
                self.err(tag, "notes must carry a [TO VERIFY] marker (no unverified real-world claims)")

    # --- score-property checks (Step 4.5; requires src/) ------------------------------

    def validate_score_properties(self):
        """Assert each vignette's design_intent score relationship against
        OPERABILITY_THRESHOLD, using the real EuroSCORE II calculator. Imports src lazily
        so the structural layer stays independent of src/."""
        where = "vignettes.json:score"
        # Lazy imports: only the score layer depends on src/.
        from src.risk_calculator import compute_euroscore_ii
        from src.decomposer import decompose
        from src.optimized_state import optimized_inputs
        from src.config import get_operability_threshold

        data = self._load("vignettes.json")
        if data is None:
            return
        thr = get_operability_threshold()

        for v in data.get("vignettes", []):
            vid = v.get("id")
            di = v.get("design_intent")
            tag = f"{where}:{vid}"
            try:
                base = compute_euroscore_ii(v["euroscore_inputs"])
                opt = compute_euroscore_ii(optimized_inputs(v, decompose(v)))
            except Exception as e:  # noqa: BLE001
                self.err(tag, f"could not compute EuroSCORE II: {e}")
                continue

            nums = f"(baseline={base:.2f}%, optimized={opt:.2f}%, threshold={thr:.1f}%)"
            if di == "operable_at_baseline":
                if not (base < thr):
                    self.err(tag, f"operable_at_baseline requires baseline < threshold {nums}")
            elif di == "reversible_with_optimization":
                if not (base >= thr):
                    self.err(tag, f"reversible requires baseline >= threshold {nums}")
                if not (opt < thr):
                    self.err(tag, f"reversible requires optimized < threshold {nums}")
            elif di == "fixed_high_risk":
                if not (base >= thr):
                    self.err(tag, f"fixed_high_risk requires baseline >= threshold {nums}")
                if not (opt >= thr):
                    self.err(tag, f"fixed_high_risk requires optimized >= threshold {nums}")
            else:
                self.err(tag, f"unknown design_intent {di!r}")

    def run(self, structure_only=False):
        self.validate_vignettes()
        self.validate_capabilities()
        if not structure_only:
            self.validate_score_properties()
        return self.errors


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    structure_only = "--structure-only" in argv

    v = Validator()
    errors = v.run(structure_only=structure_only)
    if errors:
        print(f"VALIDATION FAILED: {len(errors)} error(s)\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    if structure_only:
        print("VALIDATION OK (structure only): vignettes.json and capability_profile.json "
              "conform to SCHEMA.md.")
    else:
        print("VALIDATION OK: structure conforms to SCHEMA.md AND every vignette satisfies "
              "its design_intent score property against OPERABILITY_THRESHOLD.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

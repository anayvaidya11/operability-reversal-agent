# Operability Reversal Agent — Specification (SPEC.md)

**Version:** 0.1 (Step 1 of 10)
**Status:** Draft specification — single source of truth for later steps.
**Nature of project:** Early-stage, **non-validated humanitarian proof-of-concept**.
This is decision-support *scaffolding* for research and demonstration only. It is
**not** a medical device, **not** clinically validated, and **must not** be used to
make real care decisions.

> **Reading guide.** This document is written to be followed by *both* a non-clinician
> engineer and a clinician. Clinical terms are defined in the [Glossary](#h-glossary).
> Anywhere a real clinical number, coefficient, or cutoff would be required, you will
> see a **`[TO VERIFY ...]`** marker instead of an invented value. These markers are
> collected implicitly throughout and must be confirmed against primary sources before
> any implementation step uses them.

---

## Table of contents

- [a. Problem statement](#a-problem-statement)
- [b. Clinical scope](#b-clinical-scope)
- [c. Geography & care-tier model](#c-geography--care-tier-model)
- [d. Operative risk model](#d-operative-risk-model)
- [e. Operability threshold](#e-operability-threshold)
- [f. Modifiable vs. fixed risk levers](#f-modifiable-vs-fixed-risk-levers)
- [g. Assumptions & limitations](#g-assumptions--limitations)
- [h. Glossary](#h-glossary)
- [i. How this feeds later steps](#i-how-this-feeds-later-steps)

---

## a. Problem statement

Many patients with several coexisting conditions (**multimorbidity**) who need major
surgery are told they are **"too risky"** and are **declined**. For a patient in a
well-resourced setting, a care team may quietly spend weeks tuning that patient's
health — tightening diabetes control, calming their lungs, correcting anemia — until
the surgery becomes acceptably safe. That coordination work usually happens informally,
behind the scenes, driven by an experienced team that knows how to sequence it.

In an **under-resourced setting**, that coordination often does not happen at all. The
patient is declined, sent home, and there is no one who *owns the pathway* back to being
operable. The pieces may even exist locally — a way to check blood sugar, an inhaler, a
nearby tertiary hospital that can actually do the operation — but nobody assembles them
into a plan.

**The gap this project targets is:** *"Declined — now what?"*

Existing tools mostly:

- **Predict surgical risk** (given a patient, output a risk score), or
- **Triage referrals** (decide who should be seen where, and how urgently).

Neither of those *owns the reversal pathway*: the concrete, sequenced, locally-feasible
set of steps that takes an already-declined patient and works to make them operable by
reducing the parts of their risk that **can** be changed.

This agent is meant to fill exactly that gap: to decompose a declined patient's
operative risk into **fixable** vs. **fixed** contributions, resolve conflicts between
what different specialties want, sequence a pre-operative optimization plan, and
constrain every step to **what is actually available locally**.

> **Motivating case (used throughout as a worked example).** An elderly patient in
> **Sihor** (a small town in Bhavnagar district, Gujarat, India) has an approximately
> **90% blockage** of a coronary artery requiring a **bypass (CABG)**, plus **type 2
> diabetes** and **asthma**. They have been **declined for surgery as too risky**.
> Sihor has only a Community Health Centre (CHC) and small private hospitals — **no
> cardiac surgery**. **Bhavnagar**, ~20–25 km away, has tertiary cardiac capability.
> The blocker is **coordination of pre-operative optimization**, not missing machines.

---

## b. Clinical scope

### Patient archetype

This PoC reasons about **one archetype**, matching the motivating case:

- **Cardiac:** coronary artery disease (**CAD**) severe enough to warrant **CABG**.
- **Endocrine:** **type 2 diabetes mellitus**.
- **Pulmonary:** **asthma**.

The patient is **multimorbid**, **already declined** for surgery, and located in an
under-resourced tier (see [care-tier model](#c-geography--care-tier-model)).

### Specialties in scope (exactly three)

| Specialty | In-scope condition | Role in the PoC |
|-----------|--------------------|-----------------|
| **Cardiac** | CAD requiring CABG | Owns the operation itself and cardiac-risk contributions. |
| **Endocrine** | Type 2 diabetes | Owns glycemic optimization before surgery. |
| **Pulmonary** | Asthma | Owns respiratory optimization before surgery. |

### Explicitly OUT of scope for this PoC

To keep the proof-of-concept honest and tractable, **everything else is out of scope**,
including but not limited to:

- Any surgery other than **CABG** (e.g. valve, non-cardiac, emergency surgery).
- Any specialty other than **cardiac, endocrine, and pulmonary** (e.g. nephrology,
  hematology, neurology, anesthesiology as an independent reasoner, etc.).
- Any condition outside the archetype (e.g. chronic kidney disease, prior stroke, liver
  disease) **except** where a variable already appears as an input to the risk model or
  as a named modifiable lever below.
- Pediatric patients, pregnancy, and emergency/unplanned presentations.
- Long-term outcomes beyond the peri-operative window.

> Out-of-scope factors may still be *acknowledged* by the system (e.g. flagged as
> "not handled by this PoC"), but the agent will not attempt to reason about or optimize
> them.

---

## c. Geography & care-tier model

The PoC models **two care tiers**. The point of the tier model is that a recommendation
is only useful if it can actually be *done* somewhere reachable by this patient.

### Tier definitions (conceptual)

**Tier 1 — Local (Sihor: CHC / small private hospitals).**
- Conceptually *can*: provide first-contact and ongoing primary care; run basic tests
  and monitoring; deliver and titrate common medications (e.g. oral diabetes drugs,
  inhalers); support routine pre-operative optimization that does not need advanced
  equipment; act as the day-to-day coordination point close to the patient's home.
- Conceptually *cannot*: perform cardiac surgery (no CABG capability); provide advanced
  cardiac diagnostics/intervention or intensive peri-operative critical care.

**Tier 2 — Tertiary (Bhavnagar, ~20–25 km away).**
- Conceptually *can*: perform **CABG** and provide the advanced cardiac diagnostics,
  intervention, and peri-operative critical care that the operation requires.
- Conceptually *cannot* (for this PoC's purposes): serve as the patient's continuous,
  local day-to-day optimization site — travel/distance and resource constraints mean it
  is used for the operation and tertiary-only steps, not for routine ongoing titration.

> The **~20–25 km** distance and the specific capability boundaries above are working
> assumptions for the motivating case. **`[TO VERIFY — Sihor and Bhavnagar facility
> capabilities and distance against a local source]`** before treating any of these as
> facts.

### Structure to be filled in Step 2

Step 2 will produce a **local-capability profile** (in `data/`) that turns the prose
above into a structured table. The intended structure is:

| Field | Meaning | Example values |
|-------|---------|----------------|
| `capability_id` | Stable identifier for a capability | `cabg`, `hba1c_test`, `spirometry`, … |
| `description` | Plain-language description | "Coronary artery bypass grafting" |
| `local_available` | Available at Tier 1 (Local)? | `yes` / `no` / `partial` |
| `tertiary_available` | Available at Tier 2 (Tertiary)? | `yes` / `no` / `partial` |
| `notes` | Caveats, constraints, `[TO VERIFY]` flags | free text |

Step 1 only **defines this structure**; the actual capability values are deferred to
Step 2 and must each carry their own verification status.

---

## d. Operative risk model

### Backbone: EuroSCORE II

The deterministic risk backbone for this PoC is **EuroSCORE II** (Nashef et al., 2012),
a widely-used model that estimates **predicted in-hospital mortality** for adult cardiac
surgery. We choose it because it is (a) purpose-built for cardiac surgery such as CABG,
(b) deterministic and reproducible given its inputs, and (c) published, so its logic can
be verified against a primary source rather than invented.

> **Non-negotiable rule for later steps:** the actual coefficients, variable encodings,
> and the logistic-regression formula that converts inputs into a predicted mortality
> **must be taken from the published source**, not approximated.
> **`[TO VERIFY against Nashef et al., EuroSCORE II, 2012 — full coefficient set, variable
> definitions/units, and the exact logistic model formula]`**

### Input variables (grouped)

EuroSCORE II groups its inputs into patient-related, cardiac-related, and
operation-related factors. The list below names the variable **groups and factors**;
it deliberately contains **no coefficient values**. Each individual factor's exact
definition, units, and encoding is subject to
**`[TO VERIFY against Nashef et al., EuroSCORE II, 2012 — exact variable list, definitions,
and encodings]`** (the model has a fixed variable set; the grouping below is indicative
and must be reconciled with the source).

**Patient-related factors** *(properties of the patient independent of the heart or the
operation):*
- Age
- Sex
- Renal function / impairment
- Extracardiac arteriopathy
- Poor mobility
- Previous cardiac surgery
- Chronic lung disease
- Active endocarditis
- Critical preoperative state
- Diabetes on insulin
- **`[TO VERIFY — confirm this is the complete patient-related set and each definition]`**

**Cardiac-related factors** *(properties of the heart / cardiac disease):*
- NYHA functional class
- CCS class 4 angina (angina severity)
- Left ventricular function / ejection fraction category
- Recent myocardial infarction
- Pulmonary hypertension
- **`[TO VERIFY — confirm this is the complete cardiac-related set and each definition]`**

**Operation-related factors** *(properties of the planned procedure):*
- Urgency (elective / urgent / emergency / salvage)
- Weight/complexity of the intervention (e.g. isolated CABG vs. combined procedures)
- Surgery on the thoracic aorta
- **`[TO VERIFY — confirm this is the complete operation-related set and each definition]`**

### Relevance to our archetype

For the CAD + type 2 diabetes + asthma archetype, the variables most directly engaged are:

- **Age** — the patient is elderly (**fixed**; see [levers](#f-modifiable-vs-fixed-risk-levers)).
- **Diabetes** — represented in EuroSCORE II specifically as **diabetes on insulin**;
  note that glycemic *control* (HbA1c) is a **modifiable lever** that is *not itself* a
  direct EuroSCORE II input, an important modeling nuance flagged in section f.
- **Chronic lung disease** — the closest EuroSCORE II input to the patient's **asthma**;
  **`[TO VERIFY — how asthma maps onto EuroSCORE II's "chronic lung disease" definition,
  which may be oriented toward COPD]`**.
- **Cardiac factors** (LV function, recent MI, angina class, NYHA) — describe the CAD
  severity; largely **fixed** at decision time.
- **Operation-related factors** — for isolated elective **CABG**, urgency and procedure
  weight are relevant; **`[TO VERIFY — correct EuroSCORE II encoding for isolated
  elective CABG]`**.

> **Important honesty note.** Several things the agent most wants to *optimize* (e.g.
> HbA1c, asthma control, anemia, nutrition) are **not clean inputs to EuroSCORE II**.
> How the optimization of these levers is reflected in a EuroSCORE II–style prediction is
> a **modeling design question** for later steps and must be handled transparently rather
> than by silently inventing a mapping.
> **`[TO VERIFY / DESIGN DECISION — how modifiable levers that are not native EuroSCORE II
> inputs are represented in the risk computation]`**

---

## e. Operability threshold

### The single, explicit simplifying assumption

Real operability is a **clinical judgment** made by a team weighing many factors — not a
single number crossing a line. To make this proof-of-concept tractable, we adopt **one**
clearly-labeled simplification:

> **Simplifying Assumption OP-1 (Operability threshold).**
> We define a configurable predicted-mortality cutoff, the named parameter
> **`OPERABILITY_THRESHOLD`** (a percentage predicted in-hospital mortality). If a
> patient's EuroSCORE II–style predicted mortality is **at or above** `OPERABILITY_THRESHOLD`,
> the PoC treats the patient as **"declined at baseline."** The agent's goal is then to
> **reduce the modifiable contributions** to that predicted risk so the predicted value
> falls **below** `OPERABILITY_THRESHOLD`, at which point the PoC treats the patient as
> **"potentially operable"** (a candidate to re-present to the team — *not* a clearance).

### Properties of the parameter

- **Name:** `OPERABILITY_THRESHOLD`
- **Units:** percentage predicted in-hospital mortality (same units as the risk model output).
- **Default value:** **`[TO VERIFY — no default value is asserted here; a defensible value
  must be chosen with clinical input and documented, not invented]`**
- **Configurable:** yes — it is an explicit input parameter, not hard-coded, so that
  demonstrations can show sensitivity to the choice.

### What this is *not*

- It is **not** a claim that a patient below the cutoff is safe to operate on, nor that a
  patient above it should be refused. It is a **modeling proxy** for "the team is likely
  to consider this too risky right now."
- It **collapses** a rich, multi-factor clinical judgment into one scalar comparison. That
  is a deliberate loss of fidelity, accepted only because this is a PoC.
- It does **not** replace the clinician. Every output must be framed as *support for* a
  human decision, with the assumption stated plainly.

---

## f. Modifiable vs. fixed risk levers

The core intellectual move of this project is separating risk you **can** change from
risk you **cannot**. The agent optimizes only the **modifiable** column; the **fixed**
column is context it must respect but cannot alter.

> No target values, thresholds, or magnitudes of benefit are asserted below. Any such
> specifics are flagged **`[TO VERIFY]`** and deferred to sourcing with clinical input.

### Modifiable levers (the agent may try to improve these)

| Lever | Why it matters pre-operatively (plain terms) | Kind of intervention (illustrative) |
|-------|----------------------------------------------|-------------------------------------|
| **Glycemic control (HbA1c)** | Poorly controlled blood sugar is associated with worse peri-operative healing and infection risk; bringing it toward target before surgery is a classic optimization. **`[TO VERIFY — target range and evidence]`** | Adjust oral agents / insulin; diet and monitoring, coordinated at the Local tier. **`[TO VERIFY]`** |
| **Pulmonary / asthma optimization** | Poorly controlled airways raise the risk of respiratory complications around anesthesia and surgery; stabilizing them first lowers that risk. **`[TO VERIFY]`** | Inhaler optimization / controller therapy; avoid operating during an exacerbation. **`[TO VERIFY]`** |
| **Smoking status** | Active smoking is linked to worse wound healing and lung/cardiac complications; a period of cessation before surgery is commonly sought. **`[TO VERIFY — recommended cessation interval]`** | Cessation support / counseling. **`[TO VERIFY]`** |
| **Anemia** | Low hemoglobin can worsen tolerance of surgery and the need for transfusion; correcting a treatable cause beforehand is standard optimization. **`[TO VERIFY]`** | Identify and treat the cause (e.g. iron); **`[TO VERIFY — treatment specifics]`**. |
| **Nutrition / albumin** | Poor nutritional status (often reflected in low albumin) is associated with worse healing and recovery; improving it pre-op can help. **`[TO VERIFY]`** | Nutritional support / optimization. **`[TO VERIFY]`** |
| **Blood pressure** | Uncontrolled blood pressure adds peri-operative cardiovascular risk; bringing it into a reasonable range before surgery is routine. **`[TO VERIFY — target range]`** | Antihypertensive adjustment, monitoring at the Local tier. **`[TO VERIFY]`** |

> **Modeling caveat (repeat of the note in section d).** Several of these levers are **not
> direct EuroSCORE II inputs**. How improving them is reflected in the predicted-mortality
> number is a design decision that must be made transparently.
> **`[TO VERIFY / DESIGN DECISION — lever-to-risk mapping]`**

### Fixed factors (the agent must respect but cannot change)

| Fixed factor | Why it's treated as fixed here |
|--------------|-------------------------------|
| **Age** | Not modifiable; a direct risk input. |
| **Sex** | Not modifiable; a risk input. |
| **Coronary anatomy / disease extent** | The anatomical severity of the CAD (e.g. the ~90% blockage) is a structural fact at decision time; the surgery *addresses* it but optimization cannot change the baseline anatomy. |
| **Prior cardiac events** | History (e.g. previous MI or prior cardiac surgery) is fixed. |
| **Established diabetes / chronic lung disease diagnoses** | The *diagnosis* is fixed even though *control* is modifiable — an important distinction: the agent optimizes control, not the existence of the disease. |

---

## g. Assumptions & limitations

This section is **prominent by design**. Honesty about what this is *not* is a core
requirement of the project.

1. **Synthetic data only.** All patients are fictional and hand-authored. No real patient
   data is used, ingested, or stored. The motivating "Sihor patient" is an illustrative
   composite, not a real individual.
2. **Not clinically validated.** Nothing here has been tested against real outcomes or
   reviewed/approved by a clinical or regulatory body. It is a research/demonstration
   artifact, **not** a medical device.
3. **Clinician-facing, not patient-facing.** Outputs are intended as decision *support* for
   a qualified clinician who remains fully responsible. The system never speaks directly to
   patients and never issues autonomous clinical instructions.
4. **Three specialties only.** Only cardiac, endocrine, and pulmonary reasoning is modeled;
   real multimorbid optimization routinely involves more (see [scope](#b-clinical-scope)).
5. **Single archetype / single operation.** The PoC handles CAD + type 2 diabetes + asthma
   headed for isolated **CABG**. It does not generalize to other patients or operations.
6. **Simplified operability proxy.** Operability is reduced to a single configurable
   threshold (Assumption **OP-1**), which is explicitly *not* how real operability
   decisions are made.
7. **Risk-model fidelity is bounded.** EuroSCORE II estimates *in-hospital mortality* for
   cardiac surgery; it does not capture every dimension of "risk" a team weighs, and its
   coefficients/logic are **`[TO VERIFY]`** against the source, not reproduced from memory.
8. **Lever-to-risk mapping is unresolved.** Some modifiable levers are not native model
   inputs; how their improvement changes the predicted number is a pending design decision,
   not a solved problem.
9. **Care-tier capabilities are assumed.** The Local/Tertiary capabilities and the Sihor–
   Bhavnagar geography are working assumptions pending verification (Step 2).
10. **No emergencies, no time-criticality modeling.** The PoC assumes an elective pathway
    with time to optimize; it does not handle situations where waiting is itself dangerous.
11. **Not a substitute for referral/transfer systems.** Producing a plan does not arrange,
    schedule, or guarantee any actual care.

---

## h. Glossary

- **CABG (Coronary Artery Bypass Grafting)** — heart surgery that reroutes blood around a
  blocked coronary artery using a graft; the operation our archetype patient needs.
- **CAD (Coronary Artery Disease)** — narrowing/blockage of the heart's arteries, which can
  require bypass surgery when severe.
- **EuroSCORE II** — a published, deterministic model (Nashef et al., 2012) that estimates
  predicted in-hospital mortality for adult cardiac surgery from a fixed set of inputs.
- **Multimorbidity** — the presence of two or more long-term health conditions in the same
  patient at once.
- **Modifiable risk factor** — a contributor to surgical risk that can potentially be
  improved before surgery (e.g. blood-sugar control), as opposed to a fixed one.
- **Fixed risk factor** — a contributor to risk that cannot be changed before surgery
  (e.g. age, coronary anatomy).
- **Pre-operative optimization** — the process of tuning a patient's health before surgery
  to lower their risk to an acceptable level.
- **Operability** — whether a patient is considered safe enough to undergo the operation; in
  reality a clinical judgment, and in this PoC a simplified threshold proxy.
- **CHC (Community Health Centre)** — a local, government primary/secondary care facility;
  in the motivating case, part of the *Local* tier in Sihor.
- **Tertiary care** — specialized hospital care with advanced capabilities (e.g. cardiac
  surgery), here represented by Bhavnagar.
- **Care tier** — this project's grouping of facilities by capability into *Local* (Tier 1)
  and *Tertiary* (Tier 2).
- **HbA1c** — a blood measure reflecting average blood-sugar control over recent months; a
  modifiable lever for the diabetes component.
- **Type 2 diabetes mellitus** — a chronic condition of impaired blood-sugar regulation; the
  endocrine component of the archetype.
- **Asthma** — a chronic airway condition causing variable breathing difficulty; the
  pulmonary component of the archetype.
- **Peri-operative** — the period around surgery (before, during, and shortly after).

---

## i. How this feeds later steps

This SPEC is the single source of truth. Each later step consumes specific sections:

| SPEC section | Feeds into (future step) | What that step does with it |
|--------------|--------------------------|-----------------------------|
| **c. Care-tier model** (structure) | **Step 2 — Local-capability profile** (`data/`) | Fills the capability table structure with concrete, verified Local/Tertiary values. |
| **b. Clinical scope** + **f. Levers** | **Step 3 — Synthetic vignettes** (`data/`) | Authors fictional patients carrying the risk-model inputs and modifiable-lever values. |
| **d. Operative risk model** | **Step 4 — Risk tool** (`src/`) | Implements the EuroSCORE II–style calculator once coefficients are `[TO VERIFY]`-confirmed. |
| **b. Scope** + **f. Levers** | **Step 5–6 — Specialist agents** (`src/`) | Cardiac / endocrine / pulmonary reasoners propose optimizations within their lever set. |
| **f. Levers** + **c. Tiers** | **Step 7 — Conflict resolution** (`src/`) | Reconciles competing specialty recommendations. |
| **c. Tiers** + **e. Threshold** | **Step 8 — Planner** (`src/`) | Sequences a locally-feasible plan aimed at crossing `OPERABILITY_THRESHOLD`. |
| **All sections** | **Step 9 — Orchestration loop** (`src/`) | Ties tools, agents, planner into one control loop. |
| **e. Threshold** + **g. Limitations** | **Step 10 — Evaluation harness** (`eval/`) | Rule-based checks: in-scope only, tier-feasible, targets modifiable levers, risk moves the right way. |

---

*End of SPEC v0.1. All `[TO VERIFY ...]` markers must be resolved against primary sources
before any implementation step relies on the value in question.*

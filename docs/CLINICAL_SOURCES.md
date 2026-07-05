# Clinical Sources — [TO VERIFY] sourcing pass (Step 9)

This table records the Step-9 pass over every `[TO VERIFY]` clinical marker in the code and
data. Each claim is either **CITED** (a real, verifiable source was found) or reclassified
as a **MODELING ASSUMPTION** (no source verified — it must be confirmed by a clinician).

> **IMPORTANT — read before any real use.** This is a non-validated humanitarian
> proof-of-concept. **Every citation below must be independently verified by a qualified
> clinician before it informs any real decision.** Citations were located via literature
> search and are recorded with enough detail to find them; they are *not* a guarantee of
> applicability to this archetype or geography. Nothing here was fabricated — where a
> source could not be verified, the claim is honestly labelled a MODELING ASSUMPTION rather
> than given an invented reference.

| # | Claim | Status | Source / justification | Where used |
|---|-------|--------|------------------------|-----------|
| 1 | Inhaled/systemic corticosteroids raise blood glucose (basis for **glycemia-before-ICS** sequencing) | **CITED** | ICS & hyperglycemia systematic review/meta-analysis (PMC10683519); glucocorticoid-induced hyperglycemia literature (e-ENM review). Direction well established. | `resolution_rules.py` `RULE_GLYCEMIA_BEFORE_ICS.source` |
| 2 | Cardioselective β-blockers are generally safe in mild–moderate reversible airway disease, but watch the first doses (basis for **beta-blocker↔asthma** rule) | **CITED** | Salpeter SR, Ormiston TM, Salpeter EE, Wood-Baker R. *Cardioselective beta-blockers for reversible airway disease.* Cochrane Database Syst Rev 2002, Issue 4, **CD002992**. | `resolution_rules.py` `RULE_BETABLOCKER_ASTHMA.source` |
| 3 | Smoking cessation ≥4 weeks before surgery reduces post-operative complications | **CITED** | Mills E, Eyawo O, Lockhart I, et al. *Smoking cessation reduces postoperative complications: a systematic review and meta-analysis.* Am J Med 2011;124(2):144–154 (**PubMed 21295194**). Larger effect at ≥4 weeks. | `pulmonary_agent.py` smoking target + evidence |
| 4 | Prehabilitation before cardiac surgery improves functional capacity and reduces post-operative complications | **CITED** | *Prehabilitation: evolving role in contemporary cardiac surgery.* Nat Rev Cardiol 2023 (s41569-023-00939-2); plus multiple cardiac-prehab meta-analyses (6-min-walk ↑ ~50 m; fewer pulmonary complications). | `cardiac_agent.py` mobility evidence |
| 5 | Elevated pre-operative HbA1c is associated with deep sternal wound infection after CABG (basis for HbA1c→SSI) | **CITED** | *Association between HbA1c and deep sternal wound infection after coronary artery bypass: a systematic review and meta-analysis.* J Cardiothorac Surg 2024 (**PubMed 38311780**, PMC10840199); OR 2.67 (95% CI 2.00–3.58). | `endocrine_agent.py` hba1c evidence |
| 6 | Pre-operative pulmonary optimization / inspiratory muscle training reduces post-operative pulmonary complications | **CITED** | Cardiac-prehab / inspiratory-muscle-training systematic reviews (see #4; reduced pneumonia/atelectasis, shorter stay). | `pulmonary_agent.py` asthma evidence |
| 7 | Specific pre-operative HbA1c target < 7.5% (53 mmol/mol) | **MODELING ASSUMPTION** | The *direction* (lower HbA1c → less SSI) is evidence-based (#5), but the exact numeric target varies by guideline/programme; the 7.5% figure is a modeling choice. Needs clinician confirmation. | `endocrine_agent.py` hba1c target |
| 8 | Asthma FEV1 ≥ 70% predicted as an anaesthetic-clearance threshold | **MODELING ASSUMPTION** | Could not verify a single agreed numeric threshold; anaesthetic clearance is individualized. Needs clinician confirmation. | `pulmonary_agent.py` asthma target |
| 9 | GDMT improves NYHA class by ~one class within ~8 weeks | **MODELING ASSUMPTION** | That guideline-directed medical therapy improves heart-failure symptoms is guideline-consistent; the specific one-class/8-week *magnitude* is assumed. Needs clinician confirmation. | `cardiac_agent.py` heart_failure evidence + target |
| 10 | Critical-preoperative-state reversibility with stabilization | **MODELING ASSUMPTION** | Clinically reasonable; specific stabilization criteria not sourced here. | `cardiac_agent.py` critical evidence |
| 11 | OPERABILITY_THRESHOLD = 6.0% band | **MODELING ASSUMPTION** | EuroSCORE II risk bands are real (Nashef et al. 2012, cited in `euroscore_ii_coefficients.py`), and heart-team review of higher-risk revascularisation is guideline practice (2018 ESC/EACTS revascularisation guidelines, Neumann et al., Eur Heart J 2019;40:87–165). But the exact **6.0%** cutoff is a configurable modeling proxy; the specific "EuroSCORE II ≥4% → heart team" figure was **not** verified in this pass and is not asserted. | `config.py` `OPERABILITY_THRESHOLD` |
| 12 | MAX_URGENT_OPTIMIZATION_WEEKS = 4 | **MODELING ASSUMPTION** | Urgent pre-op optimization window is a case-by-case surgical judgement; 4 weeks is a proxy. | `config.py` |
| 13 | MAX_TERTIARY_TRIPS = 3 | **MODELING ASSUMPTION** | Rural travel budget is a proxy; real budget depends on the patient's circumstances. | `config.py` |
| 14 | Trip batching (cardiac oversight/ICU fold into the CABG episode; same-phase non-cardiac consults share one trip) | **MODELING ASSUMPTION** | A deterministic scheduling proxy; real scheduling differs. Conservative where unsure. | `trip_accounting.py` |
| 15 | One-touch specialist consult (initiation) with local ongoing delivery | **MODELING ASSUMPTION** | Reflects how rural chronic-disease management typically works, but the exact consult cadence is assumed. Needs clinician confirmation. | `intervention_capabilities.py` |
| 16 | The loop assumes each phase reaches its lever target | **MODELING ASSUMPTION** | Deterministic simulation of *expected* optimization success; real patient response varies. | `simulation.py` |
| 17 | `cardiac_prehabilitation_program` unavailable at both Sihor and Bhavnagar (SYNTH-019 access barrier) | **MODELING ASSUMPTION** | A plausible rural access gap constructed for the honesty case; real local availability unverified. | `capability_profile.json`, `SYNTH-019` |
| 18 | Asthma ↔ EuroSCORE II "chronic lung disease" mapping | **MODELING ASSUMPTION** | EuroSCORE II's chronic-lung-disease definition is COPD-oriented; mapping asthma onto it is a modeling choice (flagged since Step 1/2). | `SPEC.md §d`, vignette lever notes |

## Summary
- **CITED (6):** corticosteroid hyperglycemia, cardioselective β-blockers in asthma, smoking cessation ≥4 weeks, cardiac prehabilitation, HbA1c→deep sternal wound infection, pulmonary optimization/IMT.
- **MODELING ASSUMPTION (12):** the specific numeric targets (HbA1c 7.5%, FEV1 70%), GDMT/NYHA magnitude, critical-state reversibility, and all the modeling proxies (6% threshold, urgent weeks, tertiary trips, batching, one-touch consult, per-phase target, the SYNTH-019 access capability, asthma→CLD mapping).

Nothing above was fabricated. Where a real source was found it is named with a locatable
identifier; where one was not, the claim is labelled a MODELING ASSUMPTION. **All entries
require clinician verification before any real use.**

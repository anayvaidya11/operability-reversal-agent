"""
Conflict detection among the three specialists' recommendations (Step 5).

Deterministic, rule-based. Uses EXACTLY two detection signals and no others:
  (a) euroscore_field_overlap : two recommendations from DIFFERENT specialists target the
      same EuroSCORE field (a resource contention). In practice the agents own disjoint
      fields, so this is usually empty — implemented anyway so the property holds.
  (b) agent_warning           : a recommendation carries a structured cross_specialty_flag
      naming another specialty + target lever. Detection is by matching these STRUCTURED
      markers, never by free-text NLP.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Conflict:
    conflict_id: str
    kind: str                # "resource_overlap" | "clinical_interaction" | "sequencing_dependency"
    parties: list            # list of (specialty, lever) tuples
    description: str
    source_signal: str       # "euroscore_field_overlap" | "agent_warning"
    severity: str            # "blocking" | "ordering" | "advisory"
    mechanism: str | None = None   # e.g. "steroid_hyperglycemia"; keys the resolution rule
    resolution: str | None = None  # filled by the resolver; None until then


def _all_recommendations(specialist_outputs: dict):
    """Yield (specialty, recommendation) across all specialists, deterministically."""
    for specialty in sorted(specialist_outputs):
        for rec in specialist_outputs[specialty].recommendations:
            yield specialty, rec


def _party_key(parties) -> str:
    return "+".join(f"{s}:{l}" for s, l in sorted(parties))


def detect_conflicts(specialist_outputs: dict) -> list[Conflict]:
    """Return the conflicts among the specialists' recommendations."""
    recs = list(_all_recommendations(specialist_outputs))
    conflicts: list[Conflict] = []
    seen: set[str] = set()

    def add(kind, parties, description, source_signal, severity, mechanism=None):
        key = f"{kind}|{mechanism or ''}|{_party_key(parties)}"
        if key in seen:
            return
        seen.add(key)
        conflicts.append(
            Conflict(
                conflict_id=key,
                kind=kind,
                parties=sorted(parties),
                description=description,
                source_signal=source_signal,
                severity=severity,
                mechanism=mechanism,
            )
        )

    # --- signal (a): euroscore_field overlap across different specialties -------------
    by_field: dict[str, list] = {}
    for specialty, rec in recs:
        if rec.euroscore_field is not None:
            by_field.setdefault(rec.euroscore_field, []).append((specialty, rec))
    for field_name, group in by_field.items():
        specialties = {s for s, _ in group}
        if len(specialties) >= 2:
            parties = [(s, r.lever) for s, r in group]
            add(
                kind="resource_overlap",
                parties=parties,
                description=(
                    f"Multiple specialties target the same EuroSCORE field "
                    f"'{field_name}': {', '.join(f'{s}/{r.lever}' for s, r in group)}."
                ),
                source_signal="euroscore_field_overlap",
                severity="blocking",
            )

    # --- signal (b): structured cross_specialty_flag ----------------------------------
    # Index recommendations by (specialty, lever) for precise pairing.
    by_specialty_lever = {(s, r.lever): r for s, r in recs}
    for specialty, rec in recs:
        for flag in getattr(rec, "cross_specialty_flags", []) or []:
            target_specialty = flag.get("interacts_with")
            target_lever = flag.get("target_lever")
            mechanism = flag.get("mechanism")
            partner = by_specialty_lever.get((target_specialty, target_lever))
            if partner is None:
                # The named counterpart intervention isn't being done → no interaction to
                # sequence. (Not a conflict, not an error.)
                continue
            parties = [(specialty, rec.lever), (target_specialty, target_lever)]
            add(
                kind="clinical_interaction",
                parties=parties,
                description=(
                    f"{specialty}/{rec.lever} {flag.get('direction', 'affects')} "
                    f"{target_specialty}/{target_lever} via {mechanism}."
                ),
                source_signal="agent_warning",
                severity="ordering",
                mechanism=mechanism,
            )

    # deterministic order
    conflicts.sort(key=lambda c: c.conflict_id)
    return conflicts

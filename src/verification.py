"""
algorithm 1 of the paper: dual-mode verifier.

the physical protocol measures the full family in one batched job
(algorithm 1 in the paper); this post-processor then walks the
already-measured expectations one observable per audit-log entry,
so a full (shuffled) pass over the family constitutes one
verification round in the sense of algorithm 1. halt_on_violation
stops at the first violating observable inside the pass.
each log entry picks a pauli from the family, requests an
empirical estimate, computes the deviation against the reference
fingerprint, and either halts (beyond tolerance) or logs a drift
event (within tolerance).
"""

import random
from dataclasses import dataclass

from .integrity import AuditLog, spec_hash


@dataclass
class VerifierConfig:
    eps: float
    confidence: float = 0.95
    halt_on_violation: bool = True


def run_verifier(reference_fp, candidate_fp, observables, cfg, seed=42, spec=None):
    """run the dual-mode verifier across all observables in the family.

    reference_fp, candidate_fp: dicts mapping pauli string -> float.
    observables: list of pauli strings to test; one shuffled pass over
        the family is one verification round of algorithm 1 (each pauli
        yields one audit-log entry inside that pass).
    cfg: VerifierConfig.
    spec: optional stage-specification descriptor (dict). when given,
        the audit chain is anchored to spec_hash(spec), i.e. H_spec in
        the paper; when omitted the zero genesis is used, matching the
        archived may-2026 runs.

    returns the audit log. if halt_on_violation is True, the loop
    stops at the first beyond-tolerance observable.
    """
    rng = random.Random(seed)
    log = AuditLog(genesis=spec_hash(spec)) if spec is not None else AuditLog()

    # shuffle so the order is random across runs
    order = list(observables)
    rng.shuffle(order)

    for i, p in enumerate(order):
        ref = reference_fp[p]
        meas = candidate_fp[p]
        ev = log.commit(
            round_idx=i,
            pauli=p,
            measured=meas,
            reference=ref,
            epsilon=cfg.eps,
        )
        if ev.kind == "beyond_tolerance" and cfg.halt_on_violation:
            break

    return log


def summarize_log(log, eps):
    """produce a short summary of what the verifier saw."""
    n = len(log.events)
    n_violations = len(log.beyond_tolerance_events())
    n_drift = len(log.within_tolerance_events())

    if log.events:
        worst = max(e.deviation for e in log.events)
        worst_p = max(log.events, key=lambda e: e.deviation).pauli
    else:
        worst, worst_p = 0.0, None

    return {
        "n_rounds": n,
        "n_violations": n_violations,
        "n_drift_events": n_drift,
        "worst_deviation": worst,
        "worst_pauli": worst_p,
        "epsilon": eps,
        "head_hash": log.head_hash(),
        "halted": n_violations > 0,
    }

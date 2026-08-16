"""
experiment 1: detection of a sneaky qsvm substitution.

submits one batched sampler job containing every (channel, pauli)
pair for honest and sneaky channels on the local pauli family,
plus the weak family for the contrast.

default backend: ibm_fez (heron r2). pass --simulator to run on
the local aer simulator instead, with no qpu cost. useful for
sanity-checking before any hardware run.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.channels import (
    honest_channel, sneaky_channel, with_pauli_measurement,
)
from src.observables import (
    weak_family, local_family, frame_bound,
)
from src.sample_complexity import (
    compute_N, shots_per_observable, detection_margin,
)
from src.verification import VerifierConfig, run_verifier, summarize_log
from src.ibm_runtime import (
    connect, submit_batch, submit_batch_aer, FakeBackend,
    expectation_from_counts, save_json,
)


X_I = np.array([0.4, 1.2])
X_J = np.array([1.1, 0.3])

OUTDIR = Path(__file__).resolve().parent.parent / "results"


def build_circuits(family):
    """one circuit per (channel, pauli) pair. returns list of
    (label, qc) for ordered post-processing."""
    items = []
    for ch_name, ch_fn in [("honest", honest_channel),
                            ("sneaky", sneaky_channel)]:
        for p in family:
            ch = ch_fn(X_I, X_J)
            qc = with_pauli_measurement(ch, p)
            items.append((f"{ch_name}::{p}", qc))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="ibm_fez",
                    help="ibm quantum backend name")
    ap.add_argument("--simulator", action="store_true",
                    help="run on local aer simulator instead of qpu")
    ap.add_argument("--noise", default=None,
                    help="fake backend name for aer noise model "
                         "(e.g. fake_fez); only used with --simulator")
    ap.add_argument("--shots", type=int, default=None,
                    help="shots per circuit; default: theorem 2 derived")
    ap.add_argument("--delta", type=float, default=0.5,
                    help="adversarial separation parameter")
    ap.add_argument("--eps", type=float, default=0.15,
                    help="contract tolerance")
    ap.add_argument("--eta", type=float, default=0.05,
                    help="failure probability (confidence = 1-eta)")
    args = ap.parse_args()

    family = sorted(set(weak_family() + local_family()))
    k_complete = len(local_family())
    C = frame_bound(local_family())
    gamma = detection_margin(args.delta, args.eps, C)

    if args.shots is None:
        N = compute_N(args.delta, args.eps, k_complete,
                      args.eta, B=1.0, C=C)
        shots = shots_per_observable(N, k_complete)
    else:
        shots = args.shots

    print(f"detection margin gamma = {gamma:.4f}")
    print(f"shots per circuit = {shots}")
    print(f"total observables tested = {len(family)} per channel")
    print()

    items = build_circuits(family)
    labels, circs = zip(*items)

    if args.simulator:
        sim_name = f"aer_{args.noise}" if args.noise else "aer_ideal"
        backend = FakeBackend(sim_name)
        counts_list, job_id, wall = submit_batch_aer(
            list(circs), shots=shots, noise_backend=args.noise,
        )
    else:
        service, backend = connect(args.backend)
        counts_list, job_id, wall = submit_batch(
            list(circs), backend, shots=shots,
        )

    # bucket counts by channel and pauli
    fp_honest = {}
    fp_sneaky = {}
    raw_counts = {}
    for label, counts in zip(labels, counts_list):
        ch, p = label.split("::")
        val = expectation_from_counts(counts)
        if ch == "honest":
            fp_honest[p] = val
        else:
            fp_sneaky[p] = val
        raw_counts[label] = counts

    # run verifier in two modes: weak vs local contract.
    # new runs anchor the audit chain to H_spec = spec_hash(spec)
    # (paper, sec. 5.6); the archived may-2026 logs predate this
    # anchoring and use the zero genesis, as the README notes.
    cfg = VerifierConfig(eps=args.eps, halt_on_violation=False)

    def stage_spec(family):
        return {
            "channel_id": "qsvm-zzfeaturemap-2q",
            "observable_family": family,
            "eps": args.eps,
            # tau_A in the paper: the declaration timestamp of the spec.
            # pinned rather than wall-clock so the anchor is reproducible.
            "tau": "2026-05-22T00:00:00Z",
        }

    log_weak = run_verifier(
        fp_honest, fp_sneaky, weak_family(), cfg, seed=1,
        spec=stage_spec(weak_family()))
    log_complete = run_verifier(
        fp_honest, fp_sneaky, local_family(), cfg, seed=1,
        spec=stage_spec(local_family()))

    summary_weak = summarize_log(log_weak, args.eps)
    summary_complete = summarize_log(log_complete, args.eps)

    print()
    print("results")
    print("---")
    print(f"weak family ({weak_family()}):")
    print(f"  worst deviation = {summary_weak['worst_deviation']:.4f}")
    print(f"  halted = {summary_weak['halted']}")
    print(f"complete family ({local_family()}):")
    print(f"  worst deviation = {summary_complete['worst_deviation']:.4f}")
    print(f"  halted = {summary_complete['halted']}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = OUTDIR / f"experiment1_{backend.name}_{timestamp}.json"
    save_json({
        "experiment": "detection",
        "backend": backend.name,
        "job_id": job_id,
        "wall_seconds": wall,
        "shots_per_circuit": shots,
        "delta": args.delta,
        "eps": args.eps,
        "eta": args.eta,
        "x_i": X_I.tolist(),
        "x_j": X_J.tolist(),
        "fingerprint_honest": fp_honest,
        "fingerprint_sneaky": fp_sneaky,
        "weak_family": weak_family(),
        "complete_family": local_family(),
        "summary_weak": summary_weak,
        "summary_complete": summary_complete,
        "audit_log_weak": log_weak.export(),
        "audit_log_complete": log_complete.export(),
        "raw_counts": raw_counts,
    }, out_path)


if __name__ == "__main__":
    main()
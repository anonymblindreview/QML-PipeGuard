"""
experiment 3: drift observation on real hardware (or simulator).

submits the same honest channel three times across a single
batched job. on real hardware the three sub-batches share one
queue entry and run seconds apart, so the observed variation is a
within-job fluctuation floor (shot-noise dominated) rather than
slow calibration drift; cross-job drift needs a pinned layout and
per-window recalibration (paper, threats to validity).

pass --simulator to run on aer instead; on the simulator drift is
purely shot noise, useful as a baseline.

outputs d_drift_typ, the max observable deviation across the
three timepoints. used to populate the tolerance calibration
procedure of section 5.5.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.channels import (
    honest_channel, with_pauli_measurement,
)
from src.observables import (
    local_family, frame_bound,
)
from src.sample_complexity import (
    compute_N, shots_per_observable, detection_margin,
)
from src.ibm_runtime import (
    connect, submit_batch, submit_batch_aer, FakeBackend,
    expectation_from_counts, save_json,
)


X_I = np.array([0.4, 1.2])
X_J = np.array([1.1, 0.3])

N_TIMEPOINTS = 3

OUTDIR = Path(__file__).resolve().parent.parent / "results"


def build_circuits(family, n_timepoints):
    """one circuit per (timepoint, pauli) combination. all share
    the same honest channel; the index in the batch is what gives
    us multiple snapshots."""
    items = []
    for t in range(n_timepoints):
        for p in family:
            ch = honest_channel(X_I, X_J)
            qc = with_pauli_measurement(ch, p)
            items.append((f"t{t}::{p}", qc))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="ibm_fez")
    ap.add_argument("--simulator", action="store_true",
                    help="run on local aer simulator instead of qpu")
    ap.add_argument("--noise", default=None,
                    help="fake backend name for aer noise model "
                         "(e.g. fake_fez); only used with --simulator")
    ap.add_argument("--shots", type=int, default=None)
    ap.add_argument("--delta", type=float, default=0.5)
    ap.add_argument("--eps", type=float, default=0.15)
    ap.add_argument("--eta", type=float, default=0.05)
    ap.add_argument("--timepoints", type=int, default=N_TIMEPOINTS)
    args = ap.parse_args()

    family = local_family()
    k = len(family)
    C = frame_bound(family)

    if args.shots is None:
        N = compute_N(args.delta, args.eps, k, args.eta, B=1.0, C=C)
        shots = shots_per_observable(N, k)
    else:
        shots = args.shots

    print(f"timepoints = {args.timepoints}, shots per circuit = {shots}")
    print()

    items = build_circuits(family, args.timepoints)
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

    # collect fingerprints per timepoint
    fps = [{} for _ in range(args.timepoints)]
    raw_counts = {}
    for label, counts in zip(labels, counts_list):
        tstr, p = label.split("::")
        t = int(tstr[1:])
        val = expectation_from_counts(counts)
        fps[t][p] = val
        raw_counts[label] = counts

    # pairwise max deviation across timepoints
    pairwise = {}
    for i in range(args.timepoints):
        for j in range(i + 1, args.timepoints):
            d = max(abs(fps[i][p] - fps[j][p]) for p in family)
            pairwise[f"t{i}_t{j}"] = d

    d_drift_typ = max(pairwise.values()) if pairwise else 0.0

    # tolerance interval from section 5.5
    delta_adv_min = args.delta
    upper = delta_adv_min / C
    interval_ok = d_drift_typ < upper  # open interval (d_typ, delta/C): eps sits strictly inside

    print()
    print("drift results")
    print("---")
    for k_pair, v in pairwise.items():
        print(f"  {k_pair}: max |delta| = {v:.4f}")
    print(f"d_drift_typ = {d_drift_typ:.4f}")
    print()
    print(f"tolerance interval: ({d_drift_typ:.4f}, {upper:.4f})")
    if interval_ok:
        print("  non-empty, calibration procedure converges")
        # pick midpoint as the recommendation
        # midpoint is a convenience suggestion only; the paper deploys a
        # policy choice strictly inside the open interval (sec. 5.5).
        eps_rec = (d_drift_typ + upper) / 2.0
        print(f"  recommended eps = {eps_rec:.4f}")
    else:
        print("  EMPTY: drift exceeds detection capacity. options:")
        print("  (i) better hardware, (ii) larger delta_adv_min, "
              "(iii) richer observable family.")
        eps_rec = None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = OUTDIR / f"experiment3_drift_{backend.name}_{timestamp}.json"
    save_json({
        "experiment": "drift_observation",
        "backend": backend.name,
        "job_id": job_id,
        "wall_seconds": wall,
        "shots_per_circuit": shots,
        "n_timepoints": args.timepoints,
        "delta_adv_min": args.delta,
        "eps_input": args.eps,
        "C": C,
        "x_i": X_I.tolist(),
        "x_j": X_J.tolist(),
        "fingerprints": fps,
        "pairwise_deviations": pairwise,
        "d_drift_typ": d_drift_typ,
        "tolerance_interval": [d_drift_typ, upper],
        "interval_non_empty": interval_ok,
        "recommended_eps": eps_rec,
        "raw_counts": raw_counts,
    }, out_path)


if __name__ == "__main__":
    main()
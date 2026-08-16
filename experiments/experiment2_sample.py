"""
experiment 2: empirical validation of theorem 2 on the aer
simulator.

method: for each shot budget n in {N, N/10, N/100}:
  - true positive rate (tpr): measure sneaky with n shots and
    check whether any observable deviates from a fixed honest
    reference by more than eps
  - false positive rate (fpr): measure honest with n shots and
    check whether any observable deviates from the same honest
    reference by more than eps

the reference is computed once on the ideal simulator at high
shot count, so it is essentially noise-free. the per-trial
measurements use the noise model under test.

this separates two failure modes:
  - low tpr at small n means the formula's budget is necessary
    to actually catch the sneaky (the regime theorem 2 targets)
  - high fpr at small n means the contract check is dominated by
    statistical fluctuations rather than channel deviation, which
    invalidates the detection claim

uses the weakened sneaky variant (small-angle rz insertion) so
the true deviation lands near the contract tolerance and the
formula's tightness can be probed.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.channels import (
    honest_channel, sneaky_channel_weak, with_pauli_measurement,
    WEAK_SNEAKY_ANGLE,
)
from src.observables import (
    local_family, frame_bound,
)
from src.sample_complexity import (
    compute_N, shots_per_observable, detection_margin,
)
from src.ibm_runtime import (
    submit_batch_aer, expectation_from_counts, save_json,
)


X_I = np.array([0.4, 1.2])
X_J = np.array([1.1, 0.3])

N_TRIALS = 20
REF_SHOTS = 100000   # high-precision reference

OUTDIR = Path(__file__).resolve().parent.parent / "results"


def fingerprint(channel_fn, family, shots, noise_backend=None):
    circs = []
    for p in family:
        ch = channel_fn(X_I, X_J)
        circs.append(with_pauli_measurement(ch, p))
    counts_list, _, _ = submit_batch_aer(
        circs, shots=shots, noise_backend=noise_backend,
    )
    return {p: expectation_from_counts(c)
            for p, c in zip(family, counts_list)}


def detect(fp_meas, fp_ref, family, eps):
    """returns True iff any observable deviates beyond eps."""
    for p in family:
        if abs(fp_meas[p] - fp_ref[p]) > eps:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delta", type=float, default=0.5)
    ap.add_argument("--eps", type=float, default=0.15)
    ap.add_argument("--eta", type=float, default=0.05)
    ap.add_argument("--trials", type=int, default=N_TRIALS)
    ap.add_argument("--noise", default=None,
                    help="fake backend for noise model (e.g. fake_fez)")
    args = ap.parse_args()

    family = local_family()
    k = len(family)
    C = frame_bound(family)

    N_full = compute_N(args.delta, args.eps, k, args.eta, B=1.0, C=C)
    n_full = shots_per_observable(N_full, k)
    n_tenth = max(1, n_full // 10)
    n_hundredth = max(1, n_full // 100)

    gamma = detection_margin(args.delta, args.eps, C)

    print(f"sneaky variant: weak (rz angle = {WEAK_SNEAKY_ANGLE:.4f} rad)")
    if args.noise:
        print(f"noise model: {args.noise}")
    else:
        print("noise model: none (ideal simulation)")
    print(f"detection margin gamma = {gamma:.4f}")
    print(f"theorem 2 says N_full = {N_full}, n_per_obs = {n_full}")
    print()

    # build the reference honest fingerprint on the ideal simulator
    # at high shot count. this is the noise-free baseline that
    # every trial measurement is compared against.
    print(f"building reference fingerprint from ideal sim, "
          f"{REF_SHOTS} shots per observable...")
    fp_ref = fingerprint(honest_channel, family, REF_SHOTS,
                         noise_backend=None)
    print("reference:")
    for p in family:
        print(f"  <{p}> = {fp_ref[p]:+.4f}")
    print()

    # also report the true sneaky deviation, computed at the same
    # high-shot reference setting, so we can interpret the rates
    fp_sneaky_ref = fingerprint(sneaky_channel_weak, family,
                                REF_SHOTS, noise_backend=None)
    true_devs = {p: abs(fp_sneaky_ref[p] - fp_ref[p]) for p in family}
    print("true (reference) sneaky deviations:")
    for p in family:
        marker = " <- above eps" if true_devs[p] > args.eps else ""
        print(f"  |delta_{p}| = {true_devs[p]:.4f}{marker}")
    print()

    print(f"running {args.trials} trials at each of "
          f"n={n_full}, {n_tenth}, {n_hundredth}")
    print()

    results = {}
    for label, n_per in [("N", n_full),
                         ("N_over_10", n_tenth),
                         ("N_over_100", n_hundredth)]:
        tp = 0  # true positives (sneaky correctly flagged)
        fp = 0  # false positives (honest wrongly flagged)
        for t in range(args.trials):
            fp_s = fingerprint(sneaky_channel_weak, family, n_per,
                               noise_backend=args.noise)
            if detect(fp_s, fp_ref, family, args.eps):
                tp += 1

            fp_h = fingerprint(honest_channel, family, n_per,
                               noise_backend=args.noise)
            if detect(fp_h, fp_ref, family, args.eps):
                fp += 1

            if (t + 1) % 5 == 0:
                print(f"  {label}: {t+1}/{args.trials} trials, "
                      f"tp={tp} fp={fp}")
        tpr = tp / args.trials
        fpr = fp / args.trials
        results[label] = {
            "shots_per_obs": n_per,
            "trials": args.trials,
            "true_positives": tp,
            "false_positives": fp,
            "tpr": tpr,
            "fpr": fpr,
        }
        print(f"{label}: TPR = {tp}/{args.trials} = {tpr:.2%}, "
              f"FPR = {fp}/{args.trials} = {fpr:.2%}")
        print()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    tag = args.noise if args.noise else "ideal"
    out_path = OUTDIR / f"experiment2_sample_{tag}_{timestamp}.json"
    save_json({
        "experiment": "sample_complexity_validation",
        "sneaky_variant": "weak",
        "sneaky_angle": float(WEAK_SNEAKY_ANGLE),
        "noise_backend": args.noise,
        "delta": args.delta,
        "eps": args.eps,
        "eta": args.eta,
        "k": k,
        "C": C,
        "gamma": gamma,
        "N_theorem": N_full,
        "ref_shots": REF_SHOTS,
        "fingerprint_honest_ref": fp_ref,
        "fingerprint_sneaky_ref": fp_sneaky_ref,
        "true_deviations": true_devs,
        "trials_per_setting": args.trials,
        "results": results,
    }, out_path)


if __name__ == "__main__":
    main()
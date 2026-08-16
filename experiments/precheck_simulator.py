"""
quick simulator pre-check before sending anything to the real qpu.
confirms that:
  - the honest and sneaky channels produce different fingerprints
    on the local pauli family
  - the sneaky channel hides on the weak (zz only) family
  - the sample complexity formula gives a sensible N

by default uses noiseless aer. pass --noise <fake_fez|fake_brisbane|...>
to run with a backend-derived noise model, which is closer to what
hardware will return.

the reference inputs used throughout are the fixed pair
x_i = (0.4, 1.2), x_j = (1.1, 0.3), points from the binary
intrusion-detection feature space of the victim classifier
described in the paper; the verification protocol fingerprints
the channel on these inputs and needs no training dataset.
"""

import argparse
import sys
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
from src.ibm_runtime import submit_batch_aer, expectation_from_counts


SHOTS = 4096

X_I = np.array([0.4, 1.2])
X_J = np.array([1.1, 0.3])


def measure_fingerprint(channel_fn, family, shots, noise_backend=None):
    """run a channel against each pauli in the family on aer,
    return a dict {pauli: <P>}."""
    circs = []
    for p in family:
        ch = channel_fn(X_I, X_J)
        circs.append(with_pauli_measurement(ch, p))
    counts_list, _, _ = submit_batch_aer(
        circs, shots=shots, noise_backend=noise_backend,
    )
    return {p: expectation_from_counts(c)
            for p, c in zip(family, counts_list)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--noise", default=None,
                    help="fake backend for noise model "
                         "(e.g. fake_fez)")
    ap.add_argument("--shots", type=int, default=SHOTS)
    args = ap.parse_args()

    print("running aer precheck...")
    if args.noise:
        print(f"noise model: {args.noise}")
    else:
        print("noise model: none (ideal simulation)")

    family = sorted(set(weak_family() + local_family()))
    print(f"measuring {len(family)} observables: {family}")

    print()
    print("honest channel...")
    fp_honest = measure_fingerprint(
        honest_channel, family, args.shots, args.noise)
    for p, v in fp_honest.items():
        print(f"  <{p}> = {v:+.4f}")

    print()
    print("sneaky channel...")
    fp_sneaky = measure_fingerprint(
        sneaky_channel, family, args.shots, args.noise)
    for p, v in fp_sneaky.items():
        print(f"  <{p}> = {v:+.4f}")

    print()
    print("deviations:")
    for p in family:
        d = abs(fp_honest[p] - fp_sneaky[p])
        mark = "  (weak family)" if p in weak_family() else ""
        print(f"  |delta_{p}| = {d:.4f}{mark}")

    delta_weak = max(abs(fp_honest[p] - fp_sneaky[p])
                     for p in weak_family())
    delta_complete = max(abs(fp_honest[p] - fp_sneaky[p])
                         for p in local_family())

    print()
    print(f"max deviation on weak family    : {delta_weak:.4f}")
    print(f"max deviation on complete family: {delta_complete:.4f}")
    print()

    C = frame_bound(local_family())
    N = compute_N(delta=0.5, eps=0.1, k=len(local_family()),
                  eta=0.05, B=1.0, C=C)
    n_per = shots_per_observable(N, len(local_family()))
    gamma = detection_margin(0.5, 0.1, C)
    print("theorem 2 with delta=0.5, eps=0.1, eta=0.05:")
    print(f"  detection margin gamma = {gamma:.4f}")
    print(f"  total N = {N}")
    print(f"  per observable n = {n_per}")

    print()
    if delta_complete > delta_weak * 2:
        print("precheck PASSED: sneaky hides on weak, exposed on complete")
        return 0
    else:
        print("precheck WARNING: sneaky/honest split is smaller than "
              "expected. inspect feature map parameters.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

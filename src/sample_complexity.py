"""
shot budgets from the paper. theorem 2 gives the precomputed-reference
constant 2*B^2; corollary 2 gives the sampled-reference constant 8*B^2,
which is what the hardware runs use. both control false accepts and
false alarms together, so the margin is min(gamma, eps).

N >= 8 B^2 k log(2k/eta) / min(gamma, eps)^2,   gamma = delta/C - eps

where:
  B = operator norm bound (1 for paulis)
  k = |O_A| size of the observable family
  delta = adversarial separation (marginal trace-norm separation)
  eps = contract tolerance
  eta = failure probability (1-eta confidence)
  C = frame-bound constant of the family
"""

import math


def detection_margin(delta, eps, C):
    """gamma = delta/C - eps. positive means detection is forceable."""
    return delta / C - eps


def compute_N(delta, eps, k, eta, B=1.0, C=math.sqrt(3.0), sampled=True):
    """total shot budget needed for confidence 1-eta detection.

    default C = sqrt(3) is the tight frame-bound constant for the
    local pauli family, the tight constant of theorem 1 of the
    paper. callers passing a different family should supply the
    corresponding C via frame_bound(family) from src.observables.
    """
    gamma = detection_margin(delta, eps, C)
    if gamma <= 0:
        raise ValueError(
            f"detection margin non-positive: delta/C - eps = {gamma:.4f}. "
            f"need delta > C*eps for detection."
        )
    margin = min(gamma, eps)  # two-sided error control, theorem 2
    const = 8.0 if sampled else 2.0  # corollary 2 vs theorem 2 constants
    return math.ceil(const * B * B * k * math.log(2.0 * k / eta) / (margin ** 2))


def shots_per_observable(N, k):
    """uniform allocation across the family."""
    return math.ceil(N / k)

"""compute frame-bound constant C(O_A) for pauli families on 2 qubits.

C(O_A) = sup over M in span(O_A) with ||M||_inf <= 1 of sum_O |c_O|
where M = sum c_O O.

we don't have a closed form for tiers beyond the local family (where
C = sqrt(3) is analytic), so this script does numerical optimization:
random sign patterns + SLSQP on the linear objective.

tier 1: local paulis {X_i, Y_i, Z_i}, k=6, analytic C = sqrt(3)
tier 15: tier 1 + {ZZ}, k=7 -- the kernel-relevant correlation for
    inversion-test qsvm pipelines, where K = (1 + <Z1> + <Z2> + <ZZ>)/4
tier 2: tier 1 + diagonal correlations {XX, YY, ZZ}, k=9
tier 3: all non-identity 2-qubit pauli strings, k=15

tier 3 needs ~400+ trials to reliably hit the global optimum,
since the objective has many local maxima at lower C values.

usage:
    python analysis/frame_bound.py            # all tiers, default trials
    python analysis/frame_bound.py --tier 2   # one tier only
    python analysis/frame_bound.py --trials 600 --verbose
"""

import argparse
from itertools import product

import numpy as np
from scipy.optimize import minimize


# 1-qubit paulis
I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.array([[1, 0], [0, -1]], dtype=complex)
PAULIS_1Q = {"I": I2, "X": X, "Y": Y, "Z": Z}


def pauli_2q(label):
    # label is a 2-char string like 'XI', 'XX', 'YZ'
    return np.kron(PAULIS_1Q[label[0]], PAULIS_1Q[label[1]])


def get_family(tier):
    # build the 2-qubit operator family for a given tier
    if tier == 1:
        labels = ["XI", "YI", "ZI", "IX", "IY", "IZ"]
    elif tier == 15:
        labels = ["XI", "YI", "ZI", "IX", "IY", "IZ", "ZZ"]
    elif tier == 2:
        labels = ["XI", "YI", "ZI", "IX", "IY", "IZ", "XX", "YY", "ZZ"]
    elif tier == 3:
        labels = [a + b for a, b in product("IXYZ", repeat=2) if a + b != "II"]
    else:
        raise ValueError("tier must be 1, 15, 2, or 3")
    return labels, [pauli_2q(s) for s in labels]


def op_norm(coeffs, ops):
    # operator (spectral) norm of M = sum c_i O_i, after hermitizing
    M = sum(c * P for c, P in zip(coeffs, ops))
    M = (M + M.conj().T) / 2
    return float(np.max(np.abs(np.linalg.eigvalsh(M))))



def blind_witness_check(verbose=True):
    """verify the two correlation-only witnesses of appendix e.2.

    both substitutions leave every single-qubit marginal of a bell
    output at I/2, so delta_loc = 0 and proposition 1 marks them
    blind to the local family. they differ in what they do to the
    inversion-test kernel K = (1 + <Z1> + <Z2> + <ZZ>)/4:

      Z (x) I : |Phi+> -> |Phi->, both in the even-parity sector,
                so <ZZ> = +1 is preserved and K is unchanged.
      X (x) I : |Phi+> -> |Psi+>, so <ZZ> flips +1 -> -1 and
                K falls from 0.5 to 0.

    hence Z1Z2 is the correlation the kernel actually depends on,
    which is why the kernel tier adds precisely that string.
    """
    phi = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2.0)
    rho0 = np.outer(phi, phi.conj())

    def marginals(r):
        t = r.reshape(2, 2, 2, 2)
        return np.einsum("ijkj->ik", t), np.einsum("jijk->ik", t)

    def ev(r, label):
        return float(np.trace(r @ pauli_2q(label)).real)

    def kernel(r):
        return (1.0 + ev(r, "ZI") + ev(r, "IZ") + ev(r, "ZZ")) / 4.0

    local = ["XI", "YI", "ZI", "IX", "IY", "IZ"]
    out = {}
    for name, U in (("Z(x)I", pauli_2q("ZI")), ("X(x)I", pauli_2q("XI"))):
        rho1 = U @ rho0 @ U.conj().T
        m0, m1 = marginals(rho0)
        n0, n1 = marginals(rho1)
        blind = bool(np.allclose(m0, n0) and np.allclose(m1, n1))
        dev = max(abs(ev(rho0, p) - ev(rho1, p)) for p in local)
        out[name] = {
            "marginals_unchanged": blind,
            "max_local_deviation": dev,
            "zz_before": ev(rho0, "ZZ"),
            "zz_after": ev(rho1, "ZZ"),
            "kernel_before": kernel(rho0),
            "kernel_after": kernel(rho1),
        }
        if verbose:
            r = out[name]
            print(f"  {name}: marginals unchanged = {r['marginals_unchanged']}, "
                  f"max local deviation = {r['max_local_deviation']:.1e}")
            print(f"         <ZZ> {r['zz_before']:+.1f} -> {r['zz_after']:+.1f}, "
                  f"K {r['kernel_before']:.3f} -> {r['kernel_after']:.3f}")
    return out

# default trial counts per tier (calibrated empirically)
DEFAULT_TRIALS = {1: 50, 15: 100, 2: 100, 3: 500}


def frame_bound(ops, n_trials, seed=0, verbose=False):
    # random sign patterns + SLSQP on linear objective.
    # for each sign vector s in {-1,+1}^k, max sum(s_i * c_i)
    # subject to ||sum c_i O_i||_inf <= 1.
    # since |c_i| = max_{s_i in {-1,+1}} s_i c_i, sweeping signs gives
    # the |.|_1 norm of c at the optimum.
    rng = np.random.default_rng(seed)
    k = len(ops)
    best = 0.0
    best_c = None
    for t in range(n_trials):
        s = rng.choice([-1, 1], size=k)
        c0 = rng.normal(size=k) * 0.05

        def neg_obj(c):
            return -float(np.dot(s, c))

        def cons(c):
            return 1.0 - op_norm(c, ops)

        try:
            res = minimize(
                neg_obj,
                c0,
                method="SLSQP",
                constraints={"type": "ineq", "fun": cons},
                options={"maxiter": 400, "ftol": 1e-10},
            )
            if not res.success:
                continue
            if op_norm(res.x, ops) > 1.001:
                continue
            val = float(np.sum(np.abs(res.x)))
            if val > best + 1e-5:
                best = val
                best_c = res.x.copy()
                if verbose:
                    print(f"  trial {t:5d}: C = {val:.5f}")
        except Exception:
            continue
    return best, best_c


def report(tier, n_trials, seed=0, verbose=False):
    labels, ops = get_family(tier)
    print(f"\nTier {tier} (k={len(labels)}): {labels}")
    print(f"  running {n_trials} sign-pattern + SLSQP trials...")
    C, c_star = frame_bound(ops, n_trials=n_trials, seed=seed, verbose=verbose)
    # detection margin and shot budget at deployed params
    # delta=0.5, eps_A=0.15, eta=0.05, B=1, k = family size
    delta, eps_A, eta, B = 0.5, 0.15, 0.05, 1.0
    gamma = delta / C - eps_A
    if gamma > 0:
        N = int(np.ceil(8 * B**2 * len(labels) * np.log(2 * len(labels) / eta) / gamma**2))
        gamma_s = f"{gamma:.4f}"
        N_s = f"{N:,}"
    else:
        gamma_s = f"{gamma:.4f} (<= 0, theorem inapplicable at eps_A={eps_A})"
        N_s = "n/a"
    print(f"  C(O_A) ~ {C:.4f}")
    print(f"  delta/C = {delta/C:.4f}")
    print(f"  gamma = delta/C - eps_A = {gamma_s}")
    print(f"  N (sampled-reference, Cor. 2) = {N_s}")
    if c_star is not None and verbose:
        print(f"  saturating witness coefficients:")
        for lab, c in zip(labels, c_star):
            print(f"    {lab}: {c:+.4f}")
    return C


def main():
    ap = argparse.ArgumentParser(description="frame-bound numerics for pauli families")
    ap.add_argument("--witness", action="store_true",
                    help="check the correlation-only witnesses of appendix e.2 and exit")
    ap.add_argument("--tier", type=int, choices=[1, 15, 2, 3], default=None,
                    help="run a single tier (default: all)")
    ap.add_argument("--trials", type=int, default=None,
                    help="number of sign-pattern trials per tier (overrides defaults)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.witness:
        print("correlation-only witnesses (appendix e.2)")
        print("---")
        blind_witness_check()
        return

    tiers = [args.tier] if args.tier else [1, 15, 2, 3]
    results = {}
    for t in tiers:
        n_trials = args.trials if args.trials else DEFAULT_TRIALS[t]
        results[t] = report(t, n_trials=n_trials, seed=args.seed, verbose=args.verbose)

    print("\n" + "=" * 50)
    print("summary")
    print("=" * 50)
    for t, C in results.items():
        print(f"  Tier {t}: C ~ {C:.4f}")
    if 1 in results:
        from math import sqrt
        print(f"\n  Tier 1 analytic: sqrt(3) = {sqrt(3):.4f}")


if __name__ == "__main__":
    main()

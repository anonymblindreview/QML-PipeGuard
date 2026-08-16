"""
pauli observable families for the 2-qubit qsvm experiments.

weak family is informationally incomplete by design: only the
ZZ observable. it would let a sneaky substitution slip through.

the local family {X, Y, Z} on each wire determines every
single-qubit output marginal exactly, but it is NOT
informationally complete on two or more qubits: correlation
directions such as X1X2 are invisible to it. the exact blind
set is characterised in proposition 1 of the paper.
"""


# pauli strings written qubit-0 first, qubit-1 second.
# example: 'XI' means X on qubit 0, identity on qubit 1.

WEAK_FAMILY = ["ZZ"]

LOCAL_FAMILY = ["XI", "YI", "ZI", "IX", "IY", "IZ"]


def weak_family():
    return list(WEAK_FAMILY)


def local_family():
    return list(LOCAL_FAMILY)


def frame_bound(family):
    """frame-bound constant C(O_A) for a pauli family on 2 qubits.

    for the full single-qubit-on-each-wire family with B=1, the tight
    frame-bound constant is C = sqrt(3), the tight constant of theorem 1
    of the paper, from a cauchy-schwarz argument on the bloch decomposition
    of the single-qubit marginal difference. tight and independent of qubit
    count, with equality witness sigma* proportional to (X+Y+Z).

    for the weak family (just ZZ) the family is not informationally complete
    and no useful frame bound exists; we return +inf as a sentinel.
    """
    import math
    if family == LOCAL_FAMILY:
        return math.sqrt(3.0)
    # weak family: not informationally complete, no useful bound
    return float("inf")


def operator_norm_bound():
    """all paulis (including tensor products) have operator norm 1."""
    return 1.0


# backward-compatible aliases: the archived may-2026 json artefacts
# and their audit logs were produced under the historical name
# "complete family"; the paper now calls the same set the local family.
complete_family = local_family
COMPLETE_FAMILY = LOCAL_FAMILY

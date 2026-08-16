"""
minimal integrity engine for the qml verification protocol:
an observable contract check and a sha-256 audit log whose
chain can be anchored to a hash of the deployed specification.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional


GENESIS = "0" * 64


def spec_hash(spec: dict) -> str:
    """H_spec in the paper: sha-256 of the canonical json
    descriptor of the declared stage, mirroring the paper's
    sigma_A quadruple (channel identifier, observable family
    O_A, tolerance eps_A, specification timestamp tau_A). anchoring the
    audit chain to this hash binds every logged decision to the
    declared contract. the archived may-2026 runs predate this
    anchoring and use the zero genesis."""
    return sha256(canonical(spec))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(spec: dict) -> bytes:
    # stable byte form for hashing
    return json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()


@dataclass
class Observable:
    """one pauli measurement with its reference value and tolerance.
    measured is filled in after the circuit runs."""
    pauli: str
    reference: float
    epsilon: float
    measured: Optional[float] = None

    def deviation(self) -> float:
        if self.measured is None:
            raise ValueError(f"observable {self.pauli} has no measured value")
        return abs(self.measured - self.reference)

    def within_tolerance(self) -> bool:
        return self.deviation() <= self.epsilon


@dataclass
class VerificationEvent:
    """one round of the dual-mode verifier."""
    round_idx: int
    pauli: str
    measured: float
    reference: float
    deviation: float
    epsilon: float
    kind: str  # 'within_tolerance' or 'beyond_tolerance'
    prev_hash: str
    hash: str
    unix_time: float


class IntegrityViolation(Exception):
    """raised when an observable deviation exceeds the tolerance."""
    def __init__(self, message, round_idx, pauli):
        super().__init__(message)
        self.round_idx = round_idx
        self.pauli = pauli


class AuditLog:
    """hash-chained record of verification events. each event commits
    its own round data plus the prev_hash, giving tamper-evidence."""

    def __init__(self, genesis: str = GENESIS):
        self.events: list[VerificationEvent] = []
        self._head = genesis

    def commit(self, round_idx, pauli, measured, reference, epsilon):
        dev = abs(measured - reference)
        kind = "within_tolerance" if dev <= epsilon else "beyond_tolerance"

        payload = {
            "round": round_idx,
            "pauli": pauli,
            "measured": measured,
            "reference": reference,
            "deviation": dev,
            "epsilon": epsilon,
            "kind": kind,
        }
        new_hash = sha256(self._head.encode() + canonical(payload))

        ev = VerificationEvent(
            round_idx=round_idx,
            pauli=pauli,
            measured=measured,
            reference=reference,
            deviation=dev,
            epsilon=epsilon,
            kind=kind,
            prev_hash=self._head,
            hash=new_hash,
            unix_time=time.time(),
        )
        self.events.append(ev)
        self._head = new_hash
        return ev

    def head_hash(self):
        return self._head

    def beyond_tolerance_events(self):
        return [e for e in self.events if e.kind == "beyond_tolerance"]

    def within_tolerance_events(self):
        return [e for e in self.events if e.kind == "within_tolerance"]

    def export(self):
        return [asdict(e) for e in self.events]

    def verify_chain(self, genesis: str = GENESIS):
        """recompute the chain from genesis. catches any post-hoc
        modification of stored events."""
        prev = genesis
        for i, ev in enumerate(self.events):
            if ev.prev_hash != prev:
                raise IntegrityViolation(
                    f"chain broken at event {i}: prev hash mismatch",
                    round_idx=ev.round_idx,
                    pauli=ev.pauli,
                )
            payload = {
                "round": ev.round_idx,
                "pauli": ev.pauli,
                "measured": ev.measured,
                "reference": ev.reference,
                "deviation": ev.deviation,
                "epsilon": ev.epsilon,
                "kind": ev.kind,
            }
            recomputed = sha256(prev.encode() + canonical(payload))
            if recomputed != ev.hash:
                raise IntegrityViolation(
                    f"hash mismatch at event {i}: spec was modified",
                    round_idx=ev.round_idx,
                    pauli=ev.pauli,
                )
            prev = ev.hash


def verify_exported(events: list[dict], genesis: str = GENESIS) -> bool:
    """recompute the hash chain of an exported audit log (the list of
    event dicts stored in the run json). accepts either the zero
    genesis of the archived may-2026 runs or a spec_hash anchor."""
    prev = genesis
    for ev in events:
        payload = {
            "round": ev["round_idx"],
            "pauli": ev["pauli"],
            "measured": ev["measured"],
            "reference": ev["reference"],
            "deviation": ev["deviation"],
            "epsilon": ev["epsilon"],
            "kind": ev["kind"],
        }
        if ev["prev_hash"] != prev:
            return False
        if sha256(prev.encode() + canonical(payload)) != ev["hash"]:
            return False
        prev = ev["hash"]
    return True

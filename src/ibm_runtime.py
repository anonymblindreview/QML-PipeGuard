"""
ibm quantum cloud helpers: backend connection, batched circuit
submission, and counts-to-expectation conversion.

token must be supplied via the IBM_QUANTUM_TOKEN environment
variable. never hard-code it.

also provides an aer-based local simulator path that mimics the
same interface, so the experiment scripts can be driven against
a simulator with no qpu cost before any real hardware run.
"""

import os
import time
from pathlib import Path
import json

from qiskit import transpile
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler


def get_token():
    tok = os.environ.get("IBM_QUANTUM_TOKEN")
    if not tok or tok == "PASTE-YOUR-TOKEN-HERE":
        raise RuntimeError(
            "IBM_QUANTUM_TOKEN env var not set. "
            "see README for how to get a token."
        )
    return tok


def connect(backend_name=None):
    """open a service and pick a backend. if backend_name is None,
    falls back to least busy real device."""
    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        token=get_token(),
    )
    if backend_name:
        backend = service.backend(backend_name)
    else:
        backend = service.least_busy(operational=True, simulator=False)
    print(f"backend: {backend.name}, qubits: {backend.num_qubits}, "
          f"pending: {backend.status().pending_jobs}")
    return service, backend


def submit_batch(circuits, backend, shots=4096):
    """transpile and run a list of circuits as one batched sampler job.
    returns (counts_list, job_id, wall_seconds)."""
    print(f"transpiling {len(circuits)} circuits...")
    t_circs = transpile(list(circuits), backend, optimization_level=1)

    print(f"submitting sampler job, {shots} shots per circuit...")
    sampler = Sampler(mode=backend)
    job = sampler.run(list(t_circs), shots=shots)
    print(f"job id: {job.job_id()}")
    print(f"initial status: {job.status()}")

    t0 = time.time()
    last = None
    while True:
        s = str(job.status())
        if s != last:
            print(f"  [{time.time() - t0:6.1f}s] {s}")
            last = s
        if s in ("DONE", "ERROR", "CANCELLED"):
            break
        time.sleep(15)

    if str(job.status()) != "DONE":
        raise RuntimeError(f"job ended in state {job.status()}")
    wall = time.time() - t0

    print(f"job done in {wall:.1f}s, collecting counts...")
    result = job.result()
    counts_list = []
    for pub in result:
        data = pub.data
        # register name varies; grab the first one
        if hasattr(data, "keys"):
            reg = list(data.keys())[0]
            bitarr = data[reg]
        else:
            reg = next(iter(data._fields))
            bitarr = getattr(data, reg)
        counts_list.append(bitarr.get_counts())

    return counts_list, job.job_id(), wall


def expectation_from_counts(counts):
    """convert {bitstring: count} into <P> in [-1, +1].
    parity convention: even-weight bitstrings contribute +1,
    odd-weight contribute -1.
    """
    total = sum(counts.values())
    if total == 0:
        return 0.0
    val = 0.0
    for bits, c in counts.items():
        # strip spaces, count ones
        n_ones = sum(1 for b in bits.replace(" ", "") if b == "1")
        sign = 1 if n_ones % 2 == 0 else -1
        val += sign * c
    return val / total


def save_json(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)
    print(f"saved {path}")


def load_json(path):
    with open(path) as f:
        return json.load(f)


# aer path: same interface, no qpu cost, no token needed.

def submit_batch_aer(circuits, shots=4096, noise_backend=None):
    """run a list of circuits on the local aer simulator.
    returns (counts_list, job_id, wall_seconds) to match the
    hardware submit_batch interface.

    if noise_backend is given (e.g. 'fake_fez', 'fake_brisbane'),
    aer will use the corresponding fake-backend noise model.
    otherwise the simulation is noiseless.
    """
    from qiskit_aer import AerSimulator
    from qiskit import transpile as _transpile

    if noise_backend is None:
        sim = AerSimulator()
        label = "aer-ideal"
    else:
        fake = _resolve_fake_backend(noise_backend)
        sim = AerSimulator.from_backend(fake)
        label = f"aer-noise-{fake.name}"
        print(f"using noise model from {fake.name}")

    print(f"transpiling {len(circuits)} circuits for {label}...")
    t_circs = _transpile(list(circuits), sim, optimization_level=1)

    print(f"running on {label}, {shots} shots each...")
    t0 = time.time()
    job = sim.run(t_circs, shots=shots)
    result = job.result()
    wall = time.time() - t0

    counts_list = []
    for i in range(len(t_circs)):
        counts_list.append(result.get_counts(i))

    print(f"aer done in {wall:.1f}s")
    return counts_list, f"{label}-{int(time.time())}", wall


def _resolve_fake_backend(name):
    """map a short string to a qiskit-ibm-runtime fake backend."""
    from qiskit_ibm_runtime import fake_provider as fp
    name = name.lower()
    mapping = {
        "fake_fez": fp.FakeFez,
        "fake_brisbane": fp.FakeBrisbane,
        "fake_kyoto": fp.FakeKyoto,
        "fake_sherbrooke": fp.FakeSherbrooke,
    }
    if name not in mapping:
        raise ValueError(
            f"unknown fake backend '{name}'. options: {list(mapping)}"
        )
    return mapping[name]()


class FakeBackend:
    """drop-in replacement for the qiskit backend object used in
    experiment scripts; only the .name attribute is needed for
    output filenames and logs.
    """
    def __init__(self, name="aer_simulator"):
        self.name = name

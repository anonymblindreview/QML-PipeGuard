QML-PipeGuard
Reference implementation and experimental artefacts for the paper
QML-PipeGuard: Detecting Channel-Substitution Attacks on Quantum Machine
Learning Pipelines in Untrusted Clouds, under double-blind review.
This repository is anonymised for review. Author, institution, and origin
details have been removed and will be restored in the camera-ready version.
The paper defines a channel-substitution attack, in which a cloud provider
runs a different quantum channel from the one the customer declared while still
reproducing the customer's accuracy tests and single-observable checks. The
defence is a runtime observable contract with a two-sided detection bound
(tight constant C = sqrt(3) for the local Pauli family, independent of qubit
count), an exact characterisation of the adversary's blind set, a finite-shot
budget rule that controls false accepts and false alarms together, and a drift
corollary letting one tolerance separate attack from benign calibration drift.
Three experiments, two on IBM Heron r2 hardware (`ibm\_fez`) and one on the Aer
simulator, validate the protocol on a 2-qubit ZZFeatureMap QSVM pipeline.
This repository contains the full implementation, the three reported
experiments, the numerical frame-bound calculations behind the observable-tier
appendix, and the raw JSON artefacts from the two hardware runs, so every table
and figure in the paper can be reproduced from scratch.
Layout
```
qml-pipeguard/
  src/                       core modules
    integrity.py             observable contract + sha-256 audit log
    channels.py              honest and sneaky 2-qubit channels
    observables.py           weak and local pauli families
    verification.py          dual-mode verifier (algorithm 1)
    sample\_complexity.py     theorem 2 sample-budget calculator
    ibm\_runtime.py           ibm quantum service helpers
  experiments/
    precheck\_simulator.py    aer-only sanity check before any qpu run
    experiment1\_detection.py hardware: sneaky vs honest on full pauli family
    experiment2\_sample.py    simulator: theorem 2 empirical validation
    experiment3\_drift.py     hardware: drift across three timepoints
  analysis/
    analyze\_results.py       print short tables from json outputs
    plot\_figures.py          paper-ready figures from json outputs
    frame\_bound.py           numerical frame-bound constants for pauli families
  results/                   experiment outputs (new runs gitignored; archived qpu\_runs/ committed)
```
Install
```
git clone <anonymised repository URL>
cd qml-pipeguard
pip install -r requirements.txt
```
Tested on Python 3.10+ with the package versions in `requirements.txt`.
Set your IBM Quantum token
For the hardware experiments only. Get a free token at https://quantum.ibm.com, then on Windows PowerShell:
```powershell
$env:IBM\_QUANTUM\_TOKEN = "your-token-here"
```
On Linux or macOS:
```
export IBM\_QUANTUM\_TOKEN="your-token-here"
```
The token is never written to disk by this code; it stays in the environment.
Run order
The recommended path has three levels: ideal simulator first, then a noisy simulator that mimics IBM Heron r2, then real hardware. Open-plan QPU time is scarce; both simulator levels are free.
Level 1: ideal simulator (logic check)
Confirms the channels and observables are wired correctly. No QPU cost, takes under a minute.
```
python experiments/precheck\_simulator.py
```
If you see `precheck PASSED` you are ready for the next step.
Sample complexity validation belongs here too, also pure Aer:
```
python experiments/experiment2\_sample.py
```
Level 2: noisy simulator (hardware preview)
Same scripts, but Aer pulls a noise model from the IBM `fake\_fez` backend (Heron r2 calibration data). This is the closest you can get to a hardware result without paying. Still free.
```
python experiments/precheck\_simulator.py --noise fake\_fez
python experiments/experiment1\_detection.py --simulator --noise fake\_fez
python experiments/experiment3\_drift.py --simulator --noise fake\_fez
python experiments/experiment2\_sample.py --noise fake\_fez
```
The output filenames carry the noise tag (`aer\_fake\_fez`) so they don't collide with the ideal runs.
Inspect at this level:
```
python analysis/analyze\_results.py results/experiment\*\_aer\_fake\_fez\_\*.json results/experiment2\_sample\_fake\_fez\_\*.json
python analysis/plot\_figures.py results/experiment\*\_aer\_fake\_fez\_\*.json results/experiment2\_sample\_fake\_fez\_\*.json --outdir results/figures\_noisy
```
If the noisy simulator looks like it caught the substitution on the local family, the hardware run is worth doing.
Level 3: real hardware
Set the token, drop both flags:
```powershell
$env:IBM\_QUANTUM\_TOKEN = "your-token-here"
```
```
python experiments/experiment1\_detection.py --backend ibm\_fez
python experiments/experiment3\_drift.py --backend ibm\_fez
```
Default parameters are `delta=0.5`, `eps=0.15`, `eta=0.05`, giving detection margin `gamma \~ 0.139`. The shot count is derived from Theorem 2: `N = 3,420` with a precomputed reference, `N = 13,680` for the conservative sampled-reference budget of Corollary 2, which is what the hardware runs use (`n\_O = 2,280` per observable). Override with `--shots N` if you want a smaller or bigger budget.
Inspect the hardware results
```
python analysis/analyze\_results.py results/experiment\*\_ibm\_fez\_\*.json
python analysis/plot\_figures.py results/experiment\*\_ibm\_fez\_\*.json --outdir results/figures
```
Available fake backends for the noise model: `fake\_fez`, `fake\_brisbane`, `fake\_kyoto`, `fake\_sherbrooke`.
Numerical verification of frame-bound constants
The frame-bound constant `C(O\_A)` controls the sample budget in Theorem 2 and its corollary. For the local Pauli family the analytic value is `C = sqrt(3)`, tight and independent of qubit count; for extended Pauli families on two qubits (the kernel tier adding `ZZ`, Tier 2 with all diagonal correlations, Tier 3 with the full Pauli set), the values are obtained by numerical optimization (random sign-pattern search with SLSQP). The kernel tier is the relevant family for inversion-test kernel pipelines, whose output quantity is `K = (1 + <Z1> + <Z2> + <ZZ>)/4` and therefore contains a correlation the local family does not monitor; run `python analysis/frame\_bound.py --tier 15`.
The same script also checks the two correlation-only witnesses discussed in
Appendix E.2 of the paper:
```
python analysis/frame\_bound.py --witness
```
Both leave every single-qubit marginal of a Bell output at `I/2`, so
`delta\_loc = 0` and Proposition 1 marks them blind to the local family. They
differ in the kernel: `Z (x) I` preserves `<ZZ> = +1` and leaves an
inversion-test kernel entry at 0.5, while `X (x) I` flips `<ZZ>` to `-1` and
drops the entry to 0. This is why the kernel tier adds `Z1Z2` specifically. The script `analysis/frame\_bound.py` reproduces the tabulated values reported in the observable-tier appendix of the paper:
```
python analysis/frame\_bound.py --tier 1    # \~2 seconds,  C is about 1.7321 = sqrt(3)
python analysis/frame\_bound.py --tier 15   # \~2 seconds,  C is about 1.8284 (kernel tier)
python analysis/frame\_bound.py --tier 2    # \~30 seconds, C is about 2.21
python analysis/frame\_bound.py --tier 3    # \~5 minutes,  C is about 3.73
python analysis/frame\_bound.py             # all four tiers
```
Trial counts are tuned per tier; Tier 3 requires more random restarts (~500) to reach the global optimum because the objective has many local maxima at lower C values.
Mapping to the paper
Paper artefact	Generated by
Section 6 setup parameters	`experiments/precheck\_simulator.py`
Table 3, per-observable deviations	`experiments/experiment1\_detection.py`
Figure 2, weak vs local family	`analysis/plot\_figures.py` on experiment 1 output
Table 4 and Figure 3, TPR/FPR sweep	`experiments/experiment2\_sample.py`
Table 5 and Figure 4, drift and tolerance	`experiments/experiment3\_drift.py`
Appendix E, tier frame constants	`analysis/frame\_bound.py`
Algorithm 1, dual-mode verifier	`src/verification.py`
Theorem 2, shot budget	`src/sample\_complexity.py`
Observable contract and audit trail	`src/integrity.py`

Hardware artefacts
The directory `results/qpu\_runs/` contains the raw outputs and summaries from the two real-hardware experiments reported in the paper. Both jobs ran on the IBM Heron r2 processor (`ibm\_fez`) through the IBM Quantum Open Plan.
Detection experiment
Field	Value
Backend	`ibm\_fez` (IBM Heron r2, 156 qubits)
Job ID	`d884b8is46sc73f8v28g`
Date	22 May 2026, 12:02 UTC
Plan	IBM Quantum Open Plan
Shots	2,280 per circuit
Total circuits	14 (honest + sneaky, 7-Pauli family)
Queue time	~ 15 seconds
QPU run time	~ 15 seconds
Total wall time	30.7 seconds
Headline numbers:
Family	Worst observable deviation	Halt under contract
Weak `{Z\_1 Z\_2}`	0.001	False
Local `{X, Y, Z}` on each qubit	0.489	True
The sneaky channel passes the weak contract (deviation well below eps_A = 0.15) and is caught by the local contract (worst deviation 0.489, roughly 3.3x the tolerance), reproducing the two-sided bound of Theorem 1 and the blind-set prediction of Proposition 1 on real hardware.
Drift experiment
Field	Value
Backend	`ibm\_fez` (IBM Heron r2, 156 qubits)
Job ID	`d884pu2s46sc73f8vn0g`
Date	22 May 2026, 12:33 UTC
Plan	IBM Quantum Open Plan
Shots	2,280 per circuit
Total circuits	18 (3 timepoints x 6-Pauli local family)
Queue time	~ 15 seconds
QPU run time	~ 15 seconds
Total wall time	30.5 seconds
Headline numbers:
Quantity	Value
Pairwise drift t1 -> t2	0.067
Pairwise drift t1 -> t3	0.067
Pairwise drift t2 -> t3	0.046
`d\_drift\_typ`	0.067
Tolerance interval	(0.067, 0.2887), open, non-empty
Deployed eps_A	0.15
The interval is non-empty, so the calibration procedure of Section 5.5 converges. The operational value `eps\_A = 0.15` used in the detection experiment sits inside the admissible open interval `(0.067, 0.2887)`, keeping a false-alarm margin of `0.083` above the measured drift and a detection margin of `gamma \~ 0.139` against the target separation. As the paper's threats-to-validity discussion notes, this is a within-job statement: the three timepoints sit inside one 30-second batched job, so `d\_drift\_typ` is a shot-noise-dominated fluctuation floor, and honest fingerprints of the two archived jobs, 31 minutes apart without a pinned layout, differ by up to 0.27.
Files
`results/qpu\_runs/experiment1\_ibm\_fez\_20260522\_120209.json`: full output of the detection job, including raw shot counts, expectation estimates, and the audit log under both the weak and the local contract.
`results/qpu\_runs/experiment3\_drift\_ibm\_fez\_20260522\_123327.json`: full output of the drift job, including the three honest fingerprints, pairwise deviations, and the tolerance-interval calculation.
`results/qpu\_runs/experiment2\_sample\_fake\_fez\_20260522\_131130.json`: full output of the simulator TPR/FPR sweep, including the ideal reference fingerprints, true deviations of the weakened attack, and per-budget trial results.
The archived JSONs are the untouched outputs of the May 2026 runs and predate two later renamings: their keys say `complete\_family` where the paper and current code say local family, and their audit chains use the all-zero genesis rather than a specification hash. `verify\_chain` accepts both.
Re-running the analysis without resubmitting
To regenerate the figures and tables from the archived JSON files without consuming any QPU time:
```
python analysis/analyze\_results.py results/qpu\_runs/experiment\*\_ibm\_fez\_\*.json
python analysis/plot\_figures.py results/qpu\_runs/experiment\*\_ibm\_fez\_\*.json --outdir results/figures
```
Citation
Citation details are withheld during double-blind review and will be added to
the camera-ready version.
License
MIT. See `LICENSE`.

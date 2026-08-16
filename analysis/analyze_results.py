"""
load the json output files from any of the experiments and
print a short summary table that can be pasted into the paper.
"""

import argparse
import json
import sys
from pathlib import Path


def load(path):
    with open(path) as f:
        return json.load(f)


def summarize_experiment1(d):
    print(">>> experiment 1: detection")
    print(f"  backend       : {d['backend']}")
    print(f"  shots/circuit : {d['shots_per_circuit']}")
    print(f"  delta, eps    : {d['delta']}, {d['eps']}")
    print()
    print(f"  weak family ({d['weak_family']}):")
    s = d["summary_weak"]
    print(f"    worst deviation = {s['worst_deviation']:.4f}")
    print(f"    halted          = {s['halted']}")
    print(f"  local family ({d['complete_family']}):")
    s = d["summary_complete"]
    print(f"    worst deviation = {s['worst_deviation']:.4f}")
    print(f"    halted          = {s['halted']}")
    print()
    if d["summary_complete"]["halted"] and not d["summary_weak"]["halted"]:
        print("  outcome: sneaky hidden by the weak contract, "
              "caught by local contract")
    elif d["summary_complete"]["halted"]:
        print("  outcome: caught by local contract")
    elif d["summary_weak"]["halted"]:
        print("  outcome: caught even by weak contract "
              "(unexpected for an s-gate sneaky)")
    else:
        print("  outcome: not detected. inspect shot budget and "
              "noise floor.")


def summarize_experiment2(d):
    print(">>> experiment 2: sample complexity validation")
    print(f"  delta, eps, eta : {d['delta']}, {d['eps']}, {d['eta']}")
    print(f"  gamma           : {d['gamma']:.4f}")
    print(f"  N (theorem 2)   : {d['N_theorem']}")
    print(f"  trials/setting  : {d['trials_per_setting']}")
    print()
    for label, r in d["results"].items():
        print(f"  {label:>12}: n_per_obs={r['shots_per_obs']:>6}, "
              f"successes={r['successes']:>3}/{r['trials']}, "
              f"rate={r['detection_rate']:.2%}")


def summarize_experiment3(d):
    print(">>> experiment 3: drift observation")
    print(f"  backend       : {d['backend']}")
    print(f"  timepoints    : {d['n_timepoints']}")
    print(f"  shots/circuit : {d['shots_per_circuit']}")
    print()
    for k, v in d["pairwise_deviations"].items():
        print(f"  {k}: |delta|_max = {v:.4f}")
    print()
    print(f"  d_drift_typ          = {d['d_drift_typ']:.4f}")
    print(f"  tolerance interval    = [{d['tolerance_interval'][0]:.4f}, "
          f"{d['tolerance_interval'][1]:.4f}]")
    print(f"  interval non-empty   = {d['interval_non_empty']}")
    if d.get("recommended_eps") is not None:
        print(f"  recommended eps      = {d['recommended_eps']:.4f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="json files to summarize")
    args = ap.parse_args()

    for p in args.paths:
        d = load(p)
        exp = d.get("experiment", "")
        print()
        if exp == "detection":
            summarize_experiment1(d)
        elif exp == "sample_complexity_validation":
            summarize_experiment2(d)
        elif exp == "drift_observation":
            summarize_experiment3(d)
        else:
            print(f"unknown experiment type in {p}")
        print()


if __name__ == "__main__":
    main()

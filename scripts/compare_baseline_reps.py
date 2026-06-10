#!/usr/bin/env python3
"""Compare the per-fixture verdicts across baseline reps (Phase 0 gate).

Reads acceptance/baseline_m5_96gb/rep{1,2,3}/<variant>/<fixture>/result.json and
checks that every fixture's verdict is identical across reps. The deterministic
verdict per fixture is (expected_outcome_passed, score) — temp=0 should make both
byte-stable across reps. ANY divergence is a determinism failure (investigate
oMLX MoE top-k routing before Track A).

Usage: python scripts/compare_baseline_reps.py [base_dir]
"""
from __future__ import annotations
import glob, json, os, sys

base = sys.argv[1] if len(sys.argv) > 1 else "acceptance/baseline_m5_96gb"
reps = sorted(d for d in glob.glob(os.path.join(base, "rep*")) if os.path.isdir(d))
if not reps:
    print(f"no reps found under {base}"); raise SystemExit(2)

# fixture -> {rep_name: (expected_outcome_passed, score, max_score)}
data: dict[str, dict[str, tuple]] = {}
for rep in reps:
    rep_name = os.path.basename(rep)
    for rj in glob.glob(os.path.join(rep, "*", "*", "result.json")):
        try:
            d = json.load(open(rj))
        except Exception:
            continue
        fid = d.get("fixture_id") or os.path.basename(os.path.dirname(rj))
        data.setdefault(fid, {})[rep_name] = (
            bool(d.get("expected_outcome_passed")),
            int(d.get("score", -1)),
            int(d.get("max_score", -1)),
        )

rep_names = [os.path.basename(r) for r in reps]
print(f"Baseline determinism — {len(data)} fixtures × {len(rep_names)} reps ({', '.join(rep_names)})\n")
hdr = f"{'fixture':42s} " + " ".join(f"{r+'(pass/score)':>16s}" for r in rep_names) + "   verdict"
print(hdr); print("-" * len(hdr))

all_deterministic = True
per_rep_pass = {r: 0 for r in rep_names}
for fid in sorted(data):
    cells = data[fid]
    keys, shown = [], []
    for r in rep_names:
        if r in cells:
            p, sc, mx = cells[r]
            keys.append((p, sc))                 # determinism key (ignore wall — varies)
            shown.append(f"{'PASS' if p else 'fail'}/{sc}/{mx}")
            per_rep_pass[r] += int(p)
        else:
            keys.append(None); shown.append("  -  ")
    same = len(set(keys)) == 1 and None not in keys
    all_deterministic &= same
    verdict = "ok" if same else "*** DIVERGES ***"
    print(f"{fid:42s} " + " ".join(f"{s:>16s}" for s in shown) + f"   {verdict}")

print("-" * len(hdr))
print("per-rep PASS count: " + ", ".join(f"{r}={per_rep_pass[r]}/{len(data)}" for r in rep_names))
print("\nDETERMINISM: " + ("✓ identical (pass,score) vectors across all reps — baseline is a trustworthy denominator"
                           if all_deterministic else
                           "✗ DIVERGENCE — investigate oMLX MoE routing nondeterminism BEFORE Track A"))
raise SystemExit(0 if all_deterministic else 1)

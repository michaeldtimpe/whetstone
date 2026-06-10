#!/usr/bin/env python3
"""Track B report: dense cells at 96 GB vs deluxe's 36 GB prior + the champion.
The headline question is whether 72B-AWQ's 4/10 ceiling and 263s wall move."""
from __future__ import annotations
import glob, json, os

COMP = "acceptance/trackB_dense_m5_96gb/comparison.json"
# deluxe prior (36 GB M1 cap) — pre-registered
DELUXE = {
    "mono__qwen25-32b-instruct-4bit":     (3, 87.0, 22.4),
    "mono__qwen25-72b-instruct-4bit-awq": (4, 263.1, 9.8),
    # deluxe ran Llama-70B at 4bit (1/10); Track B runs 8bit — no direct prior.
    "mono__llama-33-70b-instruct-8bit":   (None, None, None),
}
order = ["mono__qwen25-32b-instruct-4bit",
         "mono__qwen25-72b-instruct-4bit-awq",
         "mono__llama-33-70b-instruct-8bit"]

if not os.path.exists(COMP):
    print("no comparison.json"); raise SystemExit(1)
d = json.load(open(COMP))

print(f"{'cell':40s} {'B@96':>8s} {'dx@36':>8s}   {'wall96':>8s} {'wall36':>8s}   {'tps96':>6s}  bailouts")
print("-" * 96)
for name in order:
    v = d["variants"].get(name)
    if not v: continue
    dx = DELUXE.get(name, (None, None, None))
    dxp = f"{dx[0]}/10" if dx[0] is not None else "—(4bit:1)"
    dxw = f"{dx[1]:.0f}s" if dx[1] is not None else "—"
    print(f"{name:40s} {str(v['passed'])+'/'+str(v['fixtures']):>8s} {dxp:>8s}   "
          f"{v['avg_wall_s']:7.1f}s {dxw:>8s}   {v['gen_tps_wall']:6.1f}  {v['bailouts'] or 'none'}")
b = json.load(open("acceptance/baseline_m5_96gb/rep2/comparison.json"))["variants"]["mono__qwen3.6-35b-a3b-6bit"]
print("-" * 96)
print(f"{'champion (baseline_m5_96gb)':40s} {str(b['passed'])+'/'+str(b['fixtures']):>8s} {'—':>8s}   "
      f"{b['avg_wall_s']:7.1f}s {'—':>8s}   {b['gen_tps_wall']:6.1f}  none")

print("\n## per-fixture verdicts (which fixtures the dense models pass/fail):")
for name in order:
    cells = sorted(glob.glob(f"acceptance/trackB_dense_m5_96gb/{name}/*/result.json"))
    if not cells: continue
    print(f"\n  {name}:")
    for rj in cells:
        r = json.load(open(rj))
        mark = "PASS" if r.get("expected_outcome_passed") else "FAIL"
        print(f"    {mark}  {r['fixture_id']:42s} score={r.get('score')}/{r.get('max_score')} diff={r.get('diff_files')}f")

print("\nVerdict guide: 72B-AWQ jumping >>4/10 AND wall <<263s => KV headroom was the bottleneck.")
print("72B-AWQ staying ~4/10 => memory was not the dominant limit (dense just weaker). Either way,")
print("champion's 10/10@40s is the floor; Track B is diagnostic, not a champion-replacement path.")

#!/usr/bin/env python3
"""Track C report: pass/wall/tps per num_ctx cell + the context-efficiency signals
(peak_context_pressure, effective occupancy, context_overflow bailouts) that are
the real Track C question — not just the gate pass-rate."""
from __future__ import annotations
import glob, json, os

COMP = "acceptance/trackC_ctx_m5_96gb/comparison.json"
order = [
    "mono__qwen3.6-35b-a3b-6bit__ctx32k",
    "mono__qwen3.6-35b-a3b-6bit__ctx64k",
    "mono__qwen3.6-35b-a3b-6bit__ctx128k",
]
ctx_of = {order[0]: 32768, order[1]: 65536, order[2]: 131072}

if not os.path.exists(COMP):
    print("no comparison.json"); raise SystemExit(1)
d = json.load(open(COMP))

print(f"{'cell':44s} {'pass':>6s} {'wall':>8s} {'tps':>7s}  bailouts")
print("-" * 82)
for name in order:
    v = d["variants"].get(name)
    if not v: continue
    print(f"{name:44s} {str(v['passed'])+'/'+str(v['fixtures']):>6s} "
          f"{v['avg_wall_s']:7.1f}s {v['gen_tps_wall']:7.1f}  {v['bailouts'] or 'none'}")
b = json.load(open("acceptance/baseline_m5_96gb/rep2/comparison.json"))["variants"]["mono__qwen3.6-35b-a3b-6bit"]
print("-" * 82)
print(f"{'baseline champion 32k (Phase0 rep2)':44s} {str(b['passed'])+'/'+str(b['fixtures']):>6s} "
      f"{b['avg_wall_s']:7.1f}s {b['gen_tps_wall']:7.1f}  {b['bailouts'] or 'none'}")

# Context-efficiency signal: peak_context_pressure per fixture (from diagnostics.json).
print("\n## peak context pressure (fraction of num_ctx used) — the real Track C signal")
print(f"{'fixture':42s} {'32k':>7s} {'64k':>7s} {'128k':>7s}")
print("-" * 68)
def load_pressure(cell):
    out = {}
    for dj in glob.glob(f"acceptance/trackC_ctx_m5_96gb/{cell}/*/diagnostics.json"):
        try:
            j = json.load(open(dj))
        except Exception:
            continue
        fid = j.get("fixture_id") or os.path.basename(os.path.dirname(dj))
        out[fid] = j.get("peak_context_pressure")
    return out
press = {name: load_pressure(name) for name in order}
fids = sorted(set().union(*[set(p) for p in press.values()]) )
for fid in fids:
    row = []
    for name in order:
        p = press[name].get(fid)
        row.append(f"{p:.2f}" if isinstance(p, (int, float)) else "  -  ")
    print(f"{fid:42s} " + " ".join(f"{c:>7s}" for c in row))

# Did the 80B's overflow-fixture analog (any overflow at 32k) clear at higher ctx?
print("\n## context_overflow bailouts by cell:")
for name in order:
    v = d["variants"].get(name)
    if v: print(f"  {name}: {v['bailouts'] or 'none'}")
print("\nNote: champion already 10/10 at 32k, so the gate can't move — Track C wins are in"
      "\nreduced pressure / fewer overflows / codeneedle recall (promote tier), not pass-rate.")

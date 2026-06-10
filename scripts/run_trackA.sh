#!/usr/bin/env bash
# Track A — larger-MoE re-confirm at the 96 GB cap (validates the forked harness).
set -uo pipefail
cd "$HOME/Downloads/whetstone"

echo "================  TRACK A START  [$(date +%H:%M:%S)]  ================"
.venv/bin/python -m benchmarks.maintain_suite.run \
  --variants benchmarks/maintain_suite/variants_trackA_moe_m5_96gb.yaml \
  --output acceptance/trackA_moe_m5_96gb \
  --per-fixture-timeout 1800 --all

echo
echo "================  TRACK A COMPARISON (vs baseline)  ================"
.venv/bin/python - <<'PY'
import json, glob, os
base="acceptance/trackA_moe_m5_96gb/comparison.json"
if os.path.exists(base):
    d=json.load(open(base))
    print(f"{'variant':40s} {'pass':>6s} {'wall':>8s} {'tps':>7s}  bailouts")
    print("-"*78)
    for name,v in d["variants"].items():
        print(f"{name:40s} {str(v['passed'])+'/'+str(v['fixtures']):>6s} "
              f"{v['avg_wall_s']:7.1f}s {v['gen_tps_wall']:7.1f}  {v['bailouts'] or 'none'}")
    # champion baseline reference
    b="acceptance/baseline_m5_96gb/rep2/comparison.json"
    if os.path.exists(b):
        bv=json.load(open(b))["variants"]["mono__qwen3.6-35b-a3b-6bit"]
        print("-"*78)
        print(f"{'baseline champion (rep2)':40s} {str(bv['passed'])+'/'+str(bv['fixtures']):>6s} "
              f"{bv['avg_wall_s']:7.1f}s {bv['gen_tps_wall']:7.1f}  {bv['bailouts'] or 'none'}")
else:
    print("no comparison.json produced")
PY
echo "TRACK_A_COMPLETE"

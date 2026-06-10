#!/usr/bin/env bash
# Track B — large-dense reopen at the 96 GB cap (overnight; diagnostic).
set -uo pipefail
cd "$HOME/Downloads/whetstone"

echo "================  TRACK B START  [$(date +%H:%M:%S)]  ================"
.venv/bin/python -m benchmarks.maintain_suite.run \
  --variants benchmarks/maintain_suite/variants_trackB_dense_m5_96gb.yaml \
  --output acceptance/trackB_dense_m5_96gb \
  --per-fixture-timeout 1800 --all

echo
echo "================  TRACK B COMPARISON (vs deluxe 36GB + baseline)  ================"
.venv/bin/python scripts/report_trackB.py
echo "TRACK_B_COMPLETE"

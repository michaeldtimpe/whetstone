#!/usr/bin/env bash
set -uo pipefail
cd "$HOME/Downloads/whetstone"
echo "================  TRACK B (2-cell) START  [$(date +%H:%M:%S)]  ================"
.venv/bin/python -m benchmarks.maintain_suite.run \
  --variants benchmarks/maintain_suite/variants_trackB_dense_2cell.yaml \
  --output acceptance/trackB_dense_m5_96gb \
  --per-fixture-timeout 1800 --all
echo
echo "================  TRACK B COMPARISON  ================"
.venv/bin/python scripts/report_trackB.py || true
echo "TRACK_B_2CELL_COMPLETE"

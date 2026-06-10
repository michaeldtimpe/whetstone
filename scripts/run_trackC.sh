#!/usr/bin/env bash
# Track C — context-cache scaling sweep (champion fixed, num_ctx 32k/64k/128k).
set -uo pipefail
cd "$HOME/Downloads/whetstone"

echo "================  TRACK C START  [$(date +%H:%M:%S)]  ================"
.venv/bin/python -m benchmarks.maintain_suite.run \
  --variants benchmarks/maintain_suite/variants_trackC_ctx_m5_96gb.yaml \
  --output acceptance/trackC_ctx_m5_96gb \
  --per-fixture-timeout 1800 --all

echo
echo "================  TRACK C COMPARISON (vs baseline)  ================"
.venv/bin/python scripts/report_trackC.py
echo "TRACK_C_COMPLETE"

#!/usr/bin/env bash
# Phase 0 — champion baseline ×3 (denominator + determinism gate).
# Runs the champion over all 10 fixtures, three times, then compares pass-vectors.
set -uo pipefail
cd "$HOME/Downloads/whetstone"

VARIANTS=benchmarks/maintain_suite/variants_baseline_m5_96gb.yaml
OUT=acceptance/baseline_m5_96gb

for rep in 1 2 3; do
  echo "================  BASELINE REP $rep  [$(date +%H:%M:%S)]  ================"
  .venv/bin/python -m benchmarks.maintain_suite.run \
    --variants "$VARIANTS" \
    --output "$OUT/rep$rep" \
    --per-fixture-timeout 1800 --all
  echo "---- rep $rep done [$(date +%H:%M:%S)] ----"
done

echo
echo "================  DETERMINISM COMPARISON  ================"
.venv/bin/python scripts/compare_baseline_reps.py "$OUT"
echo "BASELINE_X3_COMPLETE"

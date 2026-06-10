#!/usr/bin/env bash
# Chain: wait for the 2-cell Track B (72B-AWQ + Llama-70B-8bit) to finish, then
# restart oMLX (to register the freshly-downloaded Qwen2.5-32B-4bit), run the 32B
# cell into the same output dir, and emit the full 3-cell report.
set -uo pipefail
cd "$HOME/Downloads/whetstone"

echo "[finish_trackB] waiting for 2-cell completion…"
for i in $(seq 1 720); do
  grep -q "TRACK_B_2CELL_COMPLETE" logs/trackB.log 2>/dev/null && break
  sleep 30
done
echo "[finish_trackB] 2-cell done at $(date +%H:%M:%S); restarting oMLX to pick up 32B…"
brew services restart omlx >/dev/null 2>&1
sleep 8

echo "================  TRACK B 32B CELL START  [$(date +%H:%M:%S)]  ================"
cat > /tmp/variants_trackB_32b.yaml <<'YAML'
variants:
  - {mode: mono, model_label: qwen25-32b-instruct-4bit, model_id: Qwen2.5-32B-Instruct-4bit}
YAML
.venv/bin/python -m benchmarks.maintain_suite.run \
  --variants /tmp/variants_trackB_32b.yaml \
  --output acceptance/trackB_dense_m5_96gb \
  --per-fixture-timeout 1800 --all

echo
echo "================  TRACK B FULL REPORT (all 3 dense cells)  ================"
.venv/bin/python scripts/report_trackB.py || true
echo "TRACK_B_FULL_COMPLETE"

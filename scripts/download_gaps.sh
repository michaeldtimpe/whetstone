#!/usr/bin/env bash
# Download the two models NOT in the local archive (need internet), then
# register them with oMLX. Writes to the HF cache (~/.cache/huggingface/hub).
# Safe to run alongside grab_models_from_archive.sh (internet vs NAS source).
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"

REPOS=(
  "mlx-community/gemma-3-12b-it-4bit"   # ~7G  Track D light planner arm
  "mlx-community/GLM-4.5-Air-6bit"      # ~80G Track A quant test
)

for repo in "${REPOS[@]}"; do
  echo "▶ hf download $repo  [$(date +%H:%M:%S)] …"
  if hf download "$repo" --max-workers 8; then
    echo "  ✓ $repo done  [$(date +%H:%M:%S)]"
  else
    echo "  ✗ $repo FAILED (exit $?) — hf is resumable, re-run to continue"
  fi
done

echo
echo "▶ registering gap models with oMLX (no restart — grab script restarts last)…"
cd "$HOME/Downloads/whetstone"
./.venv/bin/python scripts/register_omlx_models.py --models-file "$HOME/Downloads/dl-models/roster_gaps.json"
echo "✓ download_gaps complete. (oMLX restart happens via the archive-grab script.)"

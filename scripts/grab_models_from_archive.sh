#!/usr/bin/env bash
# Grab whetstone test models from the local NAS archive into the HF cache.
#
# The model blobs live on the NAS (<local-model-archive>, HF-cache layout); the
# active HF cache (~/.cache/huggingface/hub) only holds the champion. This
# rsyncs the needed models LOCAL (internal SSD has ~1.4 TB free) so oMLX can
# serve them at full disk speed, then registers + restarts oMLX. NO internet.
#
# Priority order: planner + co-resident builder first (Track D smoke), then the
# big builders / Track A / Track B. Resumable (rsync). Run in background.
set -uo pipefail

ARCHIVE="<local-model-archive>"
CACHE="$HOME/.cache/huggingface/hub"
ROSTER="$HOME/Downloads/dl-models/roster_whetstone_grab.json"
mkdir -p "$CACHE"

MODELS=(
  "models--mlx-community--gemma-3-27b-it-4bit"               # 16G  planner
  "models--mlx-community--Qwen3-Coder-30B-A3B-Instruct-6bit" # 23G  coresident builder
  "models--mlx-community--Qwen3-Coder-Next-6bit"             # 60G  80B builder (Track A/D)
  "models--mlx-community--GLM-4.5-Air-4bit"                  # 56G  Track A
  "models--mlx-community--Qwen2.5-72B-Instruct-4bit-AWQ"     # 38G  Track B
  "models--mlx-community--Llama-3.3-70B-Instruct-8bit"       # 70G  Track B
)

if [ ! -d "$ARCHIVE" ]; then
  echo "FATAL: archive $ARCHIVE not mounted." >&2; exit 1
fi

for m in "${MODELS[@]}"; do
  if [ ! -d "$ARCHIVE/$m" ]; then
    echo "  · SKIP $m (absent from archive)"; continue
  fi
  echo "▶ rsync $m  [$(date +%H:%M:%S)] …"
  # -aH: -a preserves layout; -H preserves the HF cache's blob<->snapshot
  # HARDLINKS so the copy stays deduped (1x). Without -H, BSD rsync breaks the
  # hardlinks into separate copies, doubling disk (run reclaim_cache_dupes.py to
  # clean up after the fact). NB: macOS BSD rsync 2.6.9 has no --info=progress2.
  if rsync -aH "$ARCHIVE/$m/" "$CACHE/$m/"; then
    echo "  ✓ $m landed ($(du -sh "$CACHE/$m" 2>/dev/null | cut -f1))  [$(date +%H:%M:%S)]"
  else
    echo "  ✗ $m rsync FAILED (exit $?) — leaving partial dir for resume"
  fi
done

echo
echo "▶ registering with oMLX + restarting service…"
cd "$HOME/Downloads/whetstone"
./.venv/bin/python scripts/register_omlx_models.py --models-file "$ROSTER" --restart-omlx

echo
echo "✓ grab complete. Verify:  .venv/bin/whetstone check"
echo "  GAP (needs internet, not in archive): mlx-community/gemma-3-12b-it-4bit"
echo "  GAP (Track A 6-bit quant test; confirm it exists on HF first): GLM-4.5-Air 6-bit"

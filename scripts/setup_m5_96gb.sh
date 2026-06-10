#!/usr/bin/env bash
# whetstone Phase 0.1 — lift the M5 Max memory envelope to 96 GB and configure oMLX.
#
# Run this ONCE on the M5 before any track. It is idempotent. It uses sudo for
# the wired-memory cap (a kernel tunable) — you will be prompted for your password.
#
#   bash scripts/setup_m5_96gb.sh
#
# Reverse the cap with:  sudo sysctl iogpu.wired_limit_mb=0   (auto)
set -euo pipefail

WIRED_MB=98304   # 96 GiB; leaves ~32 GB for OS/Claude on a 128 GB box

echo "▶ 1/3  Setting iogpu.wired_limit_mb=${WIRED_MB} (96 GiB)…"
sudo sysctl iogpu.wired_limit_mb="${WIRED_MB}"
# Persist across reboots (dedup the line if already present).
if ! grep -q "iogpu.wired_limit_mb=${WIRED_MB}" /etc/sysctl.conf 2>/dev/null; then
  echo "iogpu.wired_limit_mb=${WIRED_MB}" | sudo tee -a /etc/sysctl.conf >/dev/null
fi

echo "▶ 2/3  Patching ~/.omlx/settings.json (max_model_memory 96GB / process 110GB / idle 1800s)…"
python3 - <<'PY'
import json, os, pathlib
p = pathlib.Path(os.path.expanduser("~/.omlx/settings.json"))
s = json.loads(p.read_text())
s["max_model_memory"] = "96GB"
s["max_process_memory"] = "110GB"
s.setdefault("idle_timeout", {})["idle_timeout_seconds"] = 1800   # 3600 during Track D
s.setdefault("sampling", {})["max_context_window"] = 131072
p.write_text(json.dumps(s, indent=2))
print("   wrote", p)
PY

echo "▶ 3/3  Restart oMLX so the new memory caps take effect, e.g.:"
echo "      brew services restart omlx   # (or however oMLX is launched on this box)"
echo
echo "✓ Done. Verify:  sysctl iogpu.wired_limit_mb   (expect ${WIRED_MB})"
echo "  Note: raise idle_timeout_seconds to 3600 during Track D so the planner"
echo "  is not evicted between Pass 1 and Pass 2 (see RUNBOOK_M5_96GB.md)."

# whetstone — M5 96 GB re-bench runbook

> **STATUS (2026-06-01):** Phase 0 + Tracks A, B, C, **and D all complete** — see
> `RESULTS_M5_96GB.md`. Champion/mono holds across all four; **ZERO reproducible win banked.**
> Track D's planner showed no pass-rate lift over its mono builder on the maintain_suite smoke
> gate (a +/− compensating trade with a wall cost); the pre-registered SWE-bench n=75 / BFCL
> evidence run was **not run by user decision** (no signal at the cheap gate). **The M5 96 GB
> re-bench is CLOSED** — D banked as a no-win. Pipeline infra stays validated + ready if D is
> ever reopened.

Operator runbook for the approved plan (`~/.claude/plans/soft-meandering-gadget.md`).
The whetstone harness/code is built and tested; this is the run sequence. Sequential
bake-offs only — never run two rosters at once (whetstone.sdd).

All deltas are cited vs `acceptance/baseline_m5_96gb/`, never old-M1/auto-cap numbers.

---

## Phase 0 — hardware re-baseline (do first)

0.1  **Lift the cap + configure oMLX** (needs sudo; idempotent):
```
bash scripts/setup_m5_96gb.sh
# then restart oMLX so the caps apply, e.g. `brew services restart omlx`
sysctl iogpu.wired_limit_mb        # expect 98304
```

0.2  **Stage models** (only the champion `Qwen3.6-35B-A3B-6bit` is on disk today).
Use the dl-models rosters; each track lists what it needs:
```
# Track A/D builder:  Qwen3-Coder-Next-6bit, GLM-4.5-Air-4bit   (roster_moe.json)
# Track B dense:      Qwen2.5-72B-Instruct-4bit-AWQ, Llama-3.3-70B-Instruct-8bit (roster_dense.json)
# Track D planner:    gemma-3-27b-it-4bit                       (roster_planner.json)  <-- NEW, not staged
cd ~/Downloads/dl-models && bash download.sh           # rosters
# register with oMLX (register_omlx_models.py) + restart, then:
.venv/bin/whetstone check                              # confirms oMLX + model availability
```

0.3  **Memory census** → record planner/builder/champion resident GB at 32k and 128k
(use `custom-asitop` / `llmtop` while a model is loaded). Confirm
`gemma-27b + qwen-coder-80b + 2×KV` either fits < 96 GB (then set Track D
`coresident: true`) or does not (keep the default sequential handoff). Save to
`acceptance/hw_profile_m5_96gb/memory_check.json`.

0.4  **128k stability probe** — one 128k-context call to confirm oMLX doesn't panic /
silently swap before the Track C sweep.

0.5  **Champion baseline ×3** (the denominator + determinism gate):
```
for rep in 1 2 3; do
  .venv/bin/python -m benchmarks.maintain_suite.run \
    --variants benchmarks/maintain_suite/variants_baseline_m5_96gb.yaml \
    --output acceptance/baseline_m5_96gb/rep$rep \
    --per-fixture-timeout 1800 --all --keep-loaded
done
```
Diff the three `comparison.json` pass-vectors. **Any per-fixture shift = determinism
failure** → investigate oMLX MoE top-k routing before Track A.

---

## Tracks (run in this order; screen → promote)

Each screens on maintain_suite n=10; promote survivors to swebench (n=75) / bfcl /
extended evals (`scripts/run_eval_suite.sh` + `scripts/aggregate_eval_suite.py`).
Win bar = **any reproducible delta** (non-overlapping Wilson CIs, or a reproducible
temp=0 wall/tps/bailout change). Pre-register each track's metric before running.

| Order | Track | Variants file | Output dir | Pre-registered metric |
|------|-------|---------------|-----------|----------------------|
| 1 | A larger-MoE (validates fork + unload_all_loaded) | `variants_m5max_moe.yaml` | `acceptance/trackA_moe_m5_96gb` | speed/parity vs champion |
| 2 | C context sweep (champion fixed) | `variants_trackC_ctx_m5_96gb.yaml` | `acceptance/trackC_ctx_m5_96gb` | codeneedle recall + occupancy/latency-vs-ctx |
| 3 | B dense reopen (overnight) | `variants_trackB_dense_m5_96gb.yaml` | `acceptance/trackB_dense_m5_96gb` | pass-rate vs deluxe 4/10 + which failure modes recover |
| 4 | D planner/builder (HEADLINE) | `variants_trackD_pipeline_m5_96gb.yaml` | `acceptance/trackD_pipeline_m5_96gb` | swebench/bfcl quality vs mono builder |

Generic run form:
```
.venv/bin/python -m benchmarks.maintain_suite.run \
  --variants benchmarks/maintain_suite/<file> \
  --output acceptance/<dir> --per-fixture-timeout 1800 --all
```

**Track D specifics**
- Bump oMLX `idle_timeout_seconds` to 3600 during Track D (planner not evicted mid-pipeline).
- maintain_suite is a SMOKE GATE for D, not evidence — a 10/10 tie is pass-to-promote.
- **Pre-promote smoke gate** (do this BEFORE the 6–8 h BFCL run): run the 1-fixture
  smoke from the variants header (`--id lpe-rope-calc-implement-strict-flag`) and
  confirm: Gemma emits valid JSON, the builder loop runs the full tool surface, the
  diff grades, and memory stays < 96 GB (or swap+thermal_guard fires cleanly). The
  unit-level version of this gate is `tests/test_planner_builder.py` (already green).
- The mono control cell (same builder, no planner) isolates the planner's lift.

---

## What's already done (code)

Fork built + 1083 tests green. The harness changes that back this runbook:
- `unload_all_loaded()` fires on variant rotation incl. bailout (`benchmarks/maintain_suite/run.py`).
- Track C: `Variant.num_ctx` (default None gate) + raised clamp.
- Track D: `agents/pipeline/planner_builder.py` (fail-closed planner, sequential memory
  handoff), planner `PromptVariant`, `configs/pipeline_96gb.yaml`, `Variant.mode=pipeline`
  overlay, and structural pipeline dispatch in `cli.py maintain`.
- Contract: `src/whetstone/whetstone.sdd` permits `agents/pipeline/**` + pins the 96 GB envelope.

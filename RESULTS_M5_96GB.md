# whetstone — M5 96 GB results & status

Running record of the M5-era re-bench. All deltas vs `acceptance/baseline_m5_96gb`
(champion Qwen3.6-35B-A3B-6bit, re-anchored on M5 at the 96 GB cap). Win bar =
any reproducible delta over the champion.

## Scorecard (as of 2026-06-01)

| Phase/Track | Status | Verdict |
|---|---|---|
| Phase 0 baseline ×3 | ✅ done | 10/10 deterministic, 40s/82tps — trustworthy denominator |
| A — larger MoE | ✅ done | Champion holds; no MoE-size delta; GLM 6-bit quant-test refuted |
| C — context sweep | ✅ done | No-op for maintain_suite (fixtures peak 0.59 of 32k); needs codeneedle |
| B — large dense | ✅ done | Hypothesis **refuted** — memory was not the bottleneck; champion dominates |
| **D — planner/builder** | ✅ **smoke gate done** | Pipeline infra validated end-to-end; planner = mono builder (**no pass-rate delta**, +/− compensating trade, wall cost). maintain_suite is smoke-only — SWE-bench n=75 evidence run pending decision |

**Bottom line: champion/mono has held across A/B/C/D-smoke — ZERO reproducible win banked yet.**
This matches the plan's prediction. Track D (Gemma planner → Qwen-Coder builder) is the one
genuinely architectural experiment; its maintain_suite smoke gate is **green on infrastructure**
but shows **no pass-rate lift from the planner**. Per the runbook, maintain_suite is explicitly a
SMOKE GATE for D, not evidence — the real verdict needs SWE-bench n=75 / BFCL vs the mono builder.

## Phase 0 — baseline (`acceptance/baseline_m5_96gb/`)
3 reps, identical (pass,score) vectors → temp=0 deterministic on M5. avg ~40s / ~82 tps.
128k stability probe ✅ (`acceptance/hw_profile_m5_96gb/context_128k_probe.json`):
113k-token prompt @ num_ctx=131072 recalled in ~71s, no panic/swap.

## Track A — larger MoE (`acceptance/trackA_moe_m5_96gb/`)
| cell | pass | wall | tps |
|---|---|---|---|
| champion (re-anchor) | 10/10 | 39s | 82 |
| Qwen3-Coder-Next-80B | 9/10 | 50s | 35 | (1 context_overflow) |
| GLM-4.5-Air-106B 4bit | 10/10 | 96s | 25 |
| GLM-4.5-Air-106B 6bit | 10/10 | 141s | 18 |

Bigger MoEs pass but lose decisively on speed. GLM 6-bit = same 10/10 as 4-bit but slower
→ 4-bit was never a precision loss. The 80B's lone overflow is model token-inefficiency
(Track C confirmed the champion never overflows that fixture), not a window-size issue.

## Track C — context sweep (`acceptance/trackC_ctx_m5_96gb/`)
32k/64k/128k all 10/10, 0 overflows. Hungriest fixture peaks at 0.59 of 32k — the suite
never stresses the window, so bigger context is a no-op here. Wall differences were
cold-start ordering, not KV size. A real long-context verdict needs the **codeneedle**
promote eval (not run).

## Track B — large dense (`acceptance/trackB_dense_m5_96gb/`)
| cell | B@96GB | deluxe@36GB | wall | tps |
|---|---|---|---|---|
| Qwen2.5-32B-4bit | 4/10 | 3/10 @ 87s | 114s | 21 |
| Qwen2.5-72B-AWQ | 5/10 | 4/10 @ 263s | ~235s | 9.8 | (1 fixture hit 1800s timeout) |
| Llama-3.3-70B-8bit | 0/10 | (4bit)1/10 | 8.7s | 3.4 | **substrate fail**: prose_only/no_engagement |

**Hypothesis refuted:** 96 GB barely moved 72B-AWQ (4→5/10, wall ~235s vs 263s) — deluxe's
ceiling was dense slowness/weakness, not 36 GB KV thrashing. Llama-8bit is a tool-format
substrate failure (not a capability datapoint). Champion dominates on every axis.

> NB: `trackB_dense_m5_96gb/comparison.json` holds only the 32B cell (it ran as a separate
> invocation and overwrote the file). Per-fixture `result.json` files are the source of truth
> for all 3 cells.

## Track D — planner/builder (`acceptance/trackD_pipeline_m5_96gb/`) — 2026-06-01

Gemma-3-27B-it-4bit planner → Qwen-Coder builder. Smoke gate (1 fixture, all cells) =
`.../smoke/`; full n=10 = top-level. **maintain_suite is a SMOKE GATE for D, NOT evidence**
(short fixtures may not exercise the long-horizon decomposition a planner helps with) — see the
variants-file header. idle_timeout left at 1800s (smoke proved the co-resident cell holds/releases
2/2 models cleanly; fixtures run back-to-back, so no mid-pipeline eviction risk).

**Smoke gate = PASS (infrastructure).** All 5 criteria met: Gemma emits valid JSON
(`parsed:true`); builder runs full tool surface (80B: 14 tool calls → 2-file diff, graded);
all 4 cells graded with 0 errors; memory stayed < 96 GB with clean sequential unloads
(`1/1` between cells, co-resident cell released `2/2`); fail-closed path unit-tested
(`tests/test_planner_builder.py` 13/13).

**Full n=10 — planner adds NO pass-rate lift over its mono control, in either pairing:**

| cell | pass | avg wall | gen_tps | bailouts |
|---|---|---|---|---|
| Gemma→80B pipeline | 9/10 | 59.0s | 35.2 | stuck_no_output×1 |
| 80B mono control | 9/10 | 54.7s | 30.6 | context_overflow×1 |
| Gemma→30B pipeline | 6/10 | 71.1s | 28.6 | prose_only×4, context_overflow×2 |
| 30B mono control | 6/10 | 32.2s | 51.6 | prose_only×3 |
| champion baseline | 10/10 | 40s | 82 | none |

- **Planner parsed 10/10 in both cells** (Gemma is reliable: 4–7-step plans, ~18–24s / ~370
  completion tokens per plan) — so the ties are NOT silent fail-closed-to-mono; the plan is
  injected and changes behavior.
- **The aggregate tie hides a compensating +/− trade** (the planner is not a no-op):
  - 80B **+1/−1**: planner *fixed* `nothing-ever-happens-document-config`, *broke*
    `neon-rain-implement-reset-shortcut`.
  - 30B **+2/−2**: planner *fixed* `neon-rain-implement-reset-shortcut` +
    `nothing-ever-happens-document-config`, *broke* `lpe-rope-calc-document-typing` +
    `the-game-document-architecture`.
- **The planner costs and (for the weak builder) hurts:** +4.3s/fixture on the 80B (planner pass
  + handoff swap + ~31k larger prompts from plan injection); 2.2× slower on the 30B with MORE
  bailouts (6 vs 3) — it converts the 30B's `prose_only` give-ups into `context_overflow`
  over-engineering (e.g. an orphan `verify_strict` file in the smoke), netting zero extra passes.
- **Win bar ("any reproducible delta"): not met on maintain_suite.** Consistent with A/B/C —
  champion/mono holds. BUT this is the smoke instrument; the runbook's pre-registered evidence
  instrument (SWE-bench n=75 / BFCL) was NOT run — that decision is open (see below).

## Track D — CLOSED as no-win (2026-06-01, user decision)

Track D screening (smoke gate + n=10 maintain_suite) is complete and the line is **closed: banked
as a no-win**, consistent with A/B/C. The runbook's pre-registered real-evidence run (SWE-bench
n=75 / BFCL, pipeline vs mono 80B builder) was **deliberately not run** — the cheap smoke gate
showed no planner lift and a wall cost, so the multi-hour evidence run wasn't worth the spend
under the single-champion policy. **Final scorecard: champion/mono holds across A/B/C/D; ZERO
reproducible win banked in the entire M5 96 GB re-bench.** If a future session wants to reopen D,
the pre-registered evidence instrument is still SWE-bench n=75 (pipeline vs mono 80B builder,
decisive-win = a reproducible resolve delta beyond substrate noise) — the pipeline infra is
validated and ready (`agents/pipeline/planner_builder.py`, smoke green).

Operational gotchas live in memory `omlx-gotchas-m5` (nested `model.max_model_memory` key;
no `--keep-loaded` bench flag; `result.json` has no `passed`/`wall` field; no `timeout` binary).
Per-track findings in memory `trackA/B/C/D-results`. Repo branch state: now on `main` (the
`whetstone-bootstrap` fork was merged at `f5dfe0e`).

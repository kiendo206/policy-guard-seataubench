# Run log

One entry per Kaggle run, newest first. Format: CLAUDE.md §7 step 3.

## 20261025-0240_base_q3-4b_S4_all114_t1  (2026-10-25, Phase 0 baseline S4, OK)
- Goal: unguarded Qwen3-4B on all 114 retail tasks, fully Vietnamese (S4), 1 trial.   - Config: `configs/runs/baseline_S4_all114.yaml` (concurrency 8, context 32,768, user sim pinned to DeepInfra)   - Git SHA: ef7b9dc
- Result (`results/summary/20261025-0240_base_q3-4b_S4_all114_t1.csv`): 114/114 sims, 0 crashed, **pass^1 0.298** (`pass1_tau2` 0.298, n_overflow 0), avg 22.0 turns, 415.8 s/sim (median 365, max 1476), language correctness 1.0, DeepInfra:849, prompt tokens p95 15,959 / max 18,713, all 114 ended `user_stop`, all 40 NL-assertion chats judged.
- Time: 117.0 min session (≈ 2.0 GPU-h).   - Cost: $0.2564 (≈ $0.0022/sim incl. judge; running total ≈ $0.29).
- What went wrong: 3 chats (tasks 41, 55, 50) hit HTTP 429 "qwen3-235b is temporarily rate-limited upstream" (DeepInfra, no fallback per D4). tau2 reran each; all succeeded on retry 1. These are infrastructure reruns, so they count normally under D5 (L13). Harmless vLLM log line: FlashAttention-2 is unsupported on T4, so it falls back automatically.
- Headroom (D6 rule): p95 15,959 < ~24k → 32,768 holds (confirm on S1).
- Finding (from the log viewer): in 6 of 114 chats (e.g. task 26), the agent copied tool output with escaped Vietnamese (`Bàn phím cơ` = "Bàn phím cơ") into its reply to the customer. Language correctness (1.0) does not catch this. Candidate for the error census.
- Next: S1 baseline; 0.11 log viewer; 0.10 refuse-all floor to interpret pass^1 (restraint vs action tasks).

## 20261025-0145_pilot_q3-4b_S4_dev8_t1  (2026-10-25, Phase 0 pilot, OK)
- Goal: test concurrency 8, the DeepInfra pin (D4), and the real time and $ per conversation before the baseline.   - Config: `configs/runs/pilot_S4_dev8_c8.yaml` (dev tasks 3, 10, 16, 29, 37, 50, 72, 110; concurrency 8; context 24,576)   - Git SHA: 2c9c010
- Result (`results/summary/20261025-0145_pilot_q3-4b_S4_dev8_t1.csv`): 8/8 sims, 0 crashed, pass^1 0.25 (tasks 10 and 50; `pass1_tau2` also 0.25), avg 22.2 turns, 279.5 s/sim at concurrency 8, language correctness 1.0, user simulator DeepInfra:61 (**pin works**), retries `29:ContextWindowExceededError`.
- Time: 29.6 min session (~10 min setup; first 7 chats done after ~5.5 min; ~10 more min for task 29's hidden rerun).   - Cost: $0.0278 (manifest, after the 60 s wait) ≈ $0.0035/sim incl. judge (running total ≈ $0.032).
- Surprises: (1) task 29's first attempt overflowed the 24,576-token context, and tau2 silently reran it and saved only the rerun (L12 → D5, D6). (2) The ETA said "1 min left" for 10 min (L11).
- Next: context 32,768 (D6), the overflow rule (D5) in `summarize_run.py`, the tau2 status in the progress line, then S4 baseline `20261025-0230`.

## 20261025-0330_smoke_q3-4b_S4_dev2_t1  (2026-10-24 local, Phase 0 smoke, OK)
- Goal: pipeline end to end on S4; does the NL judge work; measure s/sim and $/sim.   - Config: `configs/runs/smoke_S4_dev2.yaml` (tasks 2, 57; 1 trial; concurrency 2)   - Git SHA: dbe2746
- Result (`results/summary/20261025-0330_smoke_q3-4b_S4_dev2_t1.csv`): 2/2 sims, 0 crashed, pass^1 0.0, avg 16 turns, 135.7 s/sim, user simulator $0.00092/sim, language correctness 1.0.
  - Task 2 (action + NL assertion): DB 0, NL 0. The judge (openrouter gpt-4.1-mini) gave a justified verdict (agent listed 9 t-shirt options, expected 10). **P1 verified.**
  - Task 57 (restraint: no DB change expected): DB 0. The agent never authenticated the user, attempted `cancel_pending_order` without an explicit confirmation (the tool refused), then wrote `modify_pending_order_address`. An over-action example of what G2 targets.
- Time: 12.0 min session (≈ 0.2 GPU-h; about 10 min of it is setup: vLLM 0.32.0 install + model download + start).   - Cost: OpenRouter spend read as $0.0012, which is below tau2's user cost of $0.0018, so it is undercounted (L10). **Real spend $0.004 (from the OpenRouter Activity page, student; running total $0.004)**: user sim $0.0018 (tau2) + about $0.002 that is most likely the single judge call.
- User simulator verified: OpenRouter raw replies name `qwen/qwen3-235b-a22b-2507`, served by 3 providers (Parasail 4, DeepInfra 4, Venice 2 calls). About 5 calls and 6k prompt tokens per conversation.
- What went wrong / surprises: the spend undercount (L10); the run-ID date is off by one: the local date was 2026-10-24 (L9). It finished in 12 min, not the estimated 30–45.
- Next: 0.9 baseline estimate from these numbers.

## 20261025-0315_smoke_q3-4b_S4_dev2_t1  (2026-10-25, Phase 0 smoke, FAILED ×3 before tau2)
- Goal: retry of the smoke run.   - Config: `configs/runs/smoke_S4_dev2.yaml`   - Git SHA: (attempt 3) main after the L6 fix
- Result: no simulations.
  1. `--no-run` push + website "Save & Run All": Kaggle ran the script as a notebook (`__notebook__.ipynb`, "Notebook does not appear to be JSON"), so none of our code ran.
  2. Normal CLI push: no secrets (P10), as expected.
  3. Website "Save & Run All" after the normal push: secrets OK, then `FileNotFoundError: configs/runs/smoke_S4_dev2.yaml`. The config was never committed, because `.gitignore` line `runs/` also matched `configs/runs/` (L7).
- Time: a few GPU-minutes in total.   - Cost: $0.00 (running total $0.00)
- Next: `.gitignore` anchored (`/runs/`, `/data/`), config committed; retry as `20261025-0330_smoke_q3-4b_S4_dev2_t1`.

## 20261025-0300_smoke_q3-4b_S4_dev2_t1  (2026-10-25, Phase 0 smoke, FAILED before setup)
- Goal: first end-to-end smoke run (S4, dev tasks 2 + 57, 1 trial).   - Config: `configs/runs/smoke_S4_dev2.yaml`   - Git SHA: b395a56
- Result: no simulations. The runner stopped in setup: "run.py differs from runner/kaggle/run.py at GIT_REF='main'".
- Time: about 1 GPU-minute (6 s of script).   - Cost: $0.00 (running total $0.00)
- What went wrong: false alarm. Kaggle prepends a `# %% [code]` marker to the stored script, and the new committed-code check compared byte for byte. Laptop == GitHub was verified (L6).
- Next: the check now ignores `# %%` lines (with a test). Retry as `20261025-0315_smoke_q3-4b_S4_dev2_t1`.

# Run log

One entry per Kaggle run, newest first. Format: CLAUDE.md §7 step 3.

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

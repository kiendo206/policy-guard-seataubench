# Decisions

Every design decision, with date and reason. Newest first.

### D3  2026-10-24  Public repo; LEARNING.md stays local; README.md is the guide
- Decision: the GitHub repo `kiendo206/policy-guard-seataubench` is public (so Kaggle clones it without a token). `docs/LEARNING.md` is git-ignored and was removed from all commits before the first push. `README.md` explains how to reproduce the results.
- Reason: the student's choice. The learning journal is for personal use, and reproduction needs only code, configs, splits, the runner, manifests and the README.
- Consequence: LEARNING.md has no git backup, so copy it somewhere safe from time to time.

### D2  2026-10-24  CLAUDE.md is kept out of git
- Decision: `CLAUDE.md` is listed in `.gitignore` and lives only on the student's laptop.
- Reason: the student's choice. It keeps personal and project-planning notes off the public repo.
- Consequence: CLAUDE.md has no version history or backup through git, and the §7 post-run commits contain only `docs/` and `results/`. Copy it somewhere safe from time to time.

### D1  2026-10-24  The Kaggle runner shows progress and announces when it finishes
- Decision: `runner/kaggle/run.py` (step 0.6) prints progress while tau2 runs (simulations done / planned, elapsed time, estimated time left) and sends a notification when the run ends, whether it succeeded or failed.
- Reason: requested by the student. It saves GPU time by showing early when a run is too slow or stuck, and he doesn't need to keep checking `kaggle kernels status`.
- Channel (chosen 2026-10-24): **ntfy** push to the phone. The topic name is kept in the Kaggle Secret `NTFY_TOPIC`, because anyone who knows it can read the messages. Messages hold only the run ID, counts and timings, never secrets.
- Runner details: progress is printed every 60 s by counting `results.json`, which tau2 rewrites atomically after each simulation. Pushes go out at start, 25/50/75%, finish and failure. OpenRouter spend (user simulator + judge) = the key's `usage` (from `/api/v1/key`) after the run minus before, because tau2 does not record judge cost. tau2 stops at 11 h (P8).

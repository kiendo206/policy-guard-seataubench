# Decisions

Every design decision, with date and reason. Newest first.

### D6  2026-10-25  Agent context limit 32,768 tokens for all runs
- Decision: vLLM `--max-model-len 32768` (was 24,576) for every run from the S4 baseline `20261025-0230` on. It stays fixed so all configurations are compared under the same limit.
- Reason: in pilot `20261025-0145`, task 29's agent prompt reached 24,577 tokens. The 24k value was a cautious T4 setting copied from the airline pilot, not a model limit (Qwen3-4B-Instruct-2507 is trained for much longer inputs). After the model weights (3.9 GiB per T4, split over 2 GPUs) and working memory, vLLM keeps ~114–122k tokens of KV cache (114,448 in the pilot, 122,224 in the smoke run; it varies per start), shared by the parallel chats; the longest saved chat used ~16k, so 32k still lets 8 chats run in parallel.
- A chat that still overflows 32k is treated as an agent failure (D5).
- Headroom for guards (asked by the student; rule set *before* seeing baseline data): guards G4/G5/G6 and block messages add text to the agent's chat. If either baseline's `prompt_tokens_p95` (in `src/summarize_run.py`) is above ~24k, i.e. less than ~8k left for guard text, raise the limit and **rerun the baselines at the new limit** before any guard work. Otherwise 32,768 stays fixed for the whole thesis. Readers/G7/G8 are separate calls but must also fit the limit.

### D5  2026-10-25  A conversation that overflows the agent's context scores 0 (first attempt = fail)
- Decision: if tau2 reran a conversation because the agent's prompt exceeded vLLM's context limit (`ContextWindowExceededError`), our metrics give that task reward 0, whatever the rerun scored. `src/summarize_run.py` reports `pass1` (this rule), `pass1_tau2` (tau2's own, which keeps the rerun) and `n_overflow`.
- Reason: tau2 retries any exception up to 3 times without recording it, and its metrics drop conversations that fail all retries (`runner/progress.py`, `metrics/agent_metrics.py:145`). An agent that rambles past its limit would then get hidden second chances, so scores look better than they are. Seen in pilot `20261025-0145` (task 29).
- Retries for real infrastructure errors (API outages) stay allowed.
- Limitation: tau2's log names the task but not the trial, so the rule is exact for 1-trial runs. Before 3-trial runs, find the trial-level evidence.

### D4  2026-10-25  Pin the user simulator to one OpenRouter provider (DeepInfra, no fallbacks)
- Decision: every call to `openrouter/qwen/qwen3-235b-a22b-2507` is sent with `extra_body.provider = {"order": ["DeepInfra"], "allow_fallbacks": false}` (`USER_LLM_ARGS` in `runner/kaggle/run.py`). This applies to all thesis runs from the pilot `20261025-0145` on.
- Reason: in smoke run `20261025-0330`, OpenRouter routed 10 user turns to 3 providers (DeepInfra 4, Parasail 4, Venice 2). Different servers can make the simulated customer behave differently, which adds noise to guard comparisons. All active providers serve fp8; DeepInfra was the cheapest with 100% uptime ($0.09/$0.55 per M tokens, 2026-10-25).
- Differs from the SEATauBench paper (default routing), which matters only when comparing absolute numbers with the paper.
- Consequences: if DeepInfra is down, calls fail and become infrastructure errors that `--auto-resume` retries. `src/summarize_run.py` reports `user_sim_providers` per run to verify the pin.
- The judge (gpt-4.1-mini) is not pinned.

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

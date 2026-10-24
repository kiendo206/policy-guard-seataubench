# Lessons

Mistakes and the rule each one produced. Format: CLAUDE.md §7 step 4.

### L12  2026-10-25  tau2 hides agent failures by silently rerunning conversations
- What happened: in the pilot, task 29's agent prompt exceeded the context limit; tau2 reran the whole chat and saved only the rerun. No field in results.json shows it.
- Root cause: tau2 retries *any* exception up to 3 times (`runner/progress.py`) and drops chats that fail every retry from its metrics (`metrics/agent_metrics.py:145`). It cannot tell a server hiccup from an agent failure.
- Rule from now on: every summary counts retries from tau2.log (`retries`, `n_overflow` columns); overflow reruns score 0 (D5); context raised to 32,768 (D6). Read benchmark error handling before trusting its scores. (CLAUDE.md §9 P12.)

### L11  2026-10-25  The ETA ignored the tail of a run
- What happened: the progress line said "ETA 0h01m" for 10 minutes while the last chat was being rerun.
- Root cause: the ETA assumes every conversation takes the same time, and it can't see reruns.
- Rule from now on: the progress line also prints tau2's own status ("N running", "R1" = rerun). Treat the ETA as a rough guide; the tail of a run (the last few chats, any reruns) is slower than the average.

### L10  2026-10-24  OpenRouter spend read too early
- What happened: the manifest's `openrouter_spend_usd` ($0.0012) was below tau2's own user-simulator cost ($0.0018), although it should also include the judge.
- Root cause (hypothesis): the `/api/v1/key` usage counter updates with a delay, and the runner read it right after tau2 ended.
- Rule from now on: the runner waits 60 s before the final usage read (code). Cross-check a run's spend once on openrouter.ai → Activity; trust the larger of the two numbers.

### L9  2026-10-24  Wrong date in run IDs
- What happened: the smoke run IDs say `20261025`, but the local date was 2026-10-24 (Kaggle: 2026-10-23 20:18 UTC = 03:18 UTC+7).
- Root cause: I guessed the date instead of reading the clock.
- Rule from now on: take a run ID's date and time from the laptop clock (`Get-Date -Format yyyyMMdd-HHmm`) when setting `RUN_ID`. Finished IDs are not renamed, so they stay linked to their files.

### L8  2026-10-25  A `--no-run` (Quick Save) version breaks website runs
- What happened: after `kaggle kernels push --no-run`, the website's "Save & Run All" treated the script as a notebook and crashed before our code ran.
- Root cause: Kaggle-side; observed, not explained. A normal push followed by the website run works.
- Rule from now on: normal `kaggle kernels push` (its CLI run stops harmlessly without secrets), then start the real run on the website. (CLAUDE.md §4 step 3, P10.)

### L7  2026-10-25  `.gitignore` pattern `runs/` silently ignored `configs/runs/`
- What happened: the smoke config was never committed; the run failed with FileNotFoundError on Kaggle.
- Root cause: a `.gitignore` pattern without a leading `/` matches at any depth. I wrote `runs/` meaning the top-level folder only. My "expect 6 files" before the commit was not compared against the real staged list.
- Rule from now on: anchor top-level ignores (`/runs/`, `/data/`). Before committing new folders, check `git status` lists them, and use `git check-ignore -v <file>` when a file is missing.

### L6  2026-10-25  Kaggle edits the script it stores
- What happened: smoke run 20261025-0300 stopped in 6 s: the committed-code check said run.py differed from GitHub, but laptop == GitHub.
- Root cause: Kaggle adds a `# %% [code]` line at the top of a pushed script; the check compared exact text.
- Rule from now on: the check ignores `# %%` marker lines (code + test in `tests/test_runner.py`). When comparing files across systems, compare all three copies (laptop, GitHub, Kaggle via `kaggle kernels pull`) before blaming the user.

### L5  2026-10-24  Kaggle Secrets are unreadable in CLI-started runs
- What happened: the keycheck printed `key loaded: False` after every `kaggle kernels push`, even with internet on, the secrets token present and the labels checked. The secrets service answered HTTP 400.
- Root cause: Kaggle-side behaviour. The same code read both secrets in the interactive editor and in a "Save & Run All" started from the website, but never in a run started by the CLI push (tested again after a website run).
- Rule from now on: `kaggle kernels push --no-run`, then start the run on the website. (CLAUDE.md §4 step 3, §9 P10.)

### L4  2026-10-24  A swallowed exception hid the real error
- What happened: `get_secret` used a bare `except Exception:` and returned None, so a failing secret looked like a missing one, and my first theory (internet off) cost a debugging round.
- Root cause: error handling that discarded the reason; then a theory stated before evidence.
- Rule from now on: never swallow an exception without logging its type, message and cause. Add evidence (here: internet, token, HTTP cause) before proposing a fix. (Fixed in `run.py`.)

### L3  2026-10-24  The kaggle CLI was silently installed in an old version
- What happened: Kaggle's new key could not be used: kaggle 1.7.4.5 only reads `kaggle.json`, and `uv tool upgrade` said "nothing to upgrade".
- Root cause: `uv tool install kaggle` ran on the system Python 3.10. kaggle ≥ 2.0 needs Python ≥ 3.11, so uv picked the last version that works on 3.10.
- Rule from now on: install uv tools with `--python 3.12`. When a version looks old, check PyPI and the Python it was installed with. (CLAUDE.md §9 P9.)

### L2  2026-10-24  A history check searched the wrong references
- What happened: after `git filter-branch`, `git log --all -- docs/LEARNING.md` still listed the old commits, which looked like the rewrite had failed.
- Root cause: `--all` also searches `refs/original/`, the backup that filter-branch keeps. The check asked "any reference" when the real question was "what will be pushed".
- Rule from now on: check exactly what will be published (`git log origin/main`, or the GitHub file tree after the push), and when a check fails, first ask whether the check itself is right. (Written here.)

### L1  2026-10-24  Reply buttons send only their prefilled text
- What happened: twice, a reply button sent "Here is the output…:" / "My answer…:" with nothing after the colon.
- Root cause: the button pre-fills the start of the message; the student's own text must be added before sending.
- Rule from now on: when a reply has nothing after its prefix, say so kindly and ask again; never guess the missing content. (Written here.)

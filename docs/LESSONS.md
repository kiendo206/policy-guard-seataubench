# Lessons

Mistakes and the rule each one produced. Format: CLAUDE.md §7 step 4.

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

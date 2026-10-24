"""Post-run ritual step 2 (CLAUDE.md §7): key metrics of one run -> results/summary/<RUN_ID>.csv.

Usage: uv run --no-project --python 3.12 python src/summarize_run.py <RUN_ID>
Reads runs/<RUN_ID>/<RUN_ID>.zip (simulations/results.json) and runs/<RUN_ID>/manifest.json.
"""

import csv
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def retries(tau2_log: str) -> list[str]:
    """tau2 silently reruns a conversation after any error (L12); only its log shows it. Returns 'task:ErrorType'."""
    return [f"{t}:{e.split('.')[-1]}" for t, e in re.findall(r"Retry \d+/\d+ for task (\S+): ([\w.]+)", tau2_log)]


def summarize(sims: list[dict], manifest: dict, tau2_log: str = "") -> dict:
    n = len(sims)
    rewards = [(s.get("reward_info") or {}).get("reward") for s in sims]
    # D5: a task tau2 reran because the agent's chat overflowed scores 0 (first attempt = fail).
    # tau2's log names the task but not the trial, so this is exact only for 1-trial runs.
    overflow = {r.split(":")[0] for r in retries(tau2_log) if r.endswith("ContextWindowExceededError")}
    scored = [0.0 if s["task_id"] in overflow else r for s, r in zip(sims, rewards)]
    turns = [sum(m.get("role") in ("user", "assistant") for m in s.get("messages") or []) for s in sims]
    lang = [((s.get("reward_info") or {}).get("info") or {}).get("language_correctness", {}).get("score") for s in sims]
    lang = [x for x in lang if x is not None]
    user_cost = sum(s.get("user_cost") or 0 for s in sims)
    # Headroom under the context limit (D6): the largest agent prompt of each chat
    peaks = sorted(max([(m.get("usage") or {}).get("prompt_tokens", 0) for m in s.get("messages") or []
                        if m.get("role") == "assistant"] or [0]) for s in sims)
    providers = Counter((m.get("raw_data") or {}).get("provider") for s in sims for m in s.get("messages") or []
                        if m.get("role") == "user" and m.get("raw_data"))  # D4: should be DeepInfra only
    start, end = (datetime.fromisoformat(manifest[k]) for k in ("start_time", "end_time"))
    return {
        "run_id": manifest["run_id"],
        "repo_sha": manifest["repo_sha"][:7],
        "n_planned": manifest["planned_sims"],
        "n_sims": n,
        "n_crashed": sum(r is None for r in rewards),  # P5
        "pass1": round(sum((r or 0) >= 1 for r in scored) / n, 3),  # D5 rule
        "pass1_tau2": round(sum((r or 0) >= 1 for r in rewards) / n, 3),  # tau2's own, keeps reruns
        "n_overflow": len(overflow),
        "prompt_tokens_p95": peaks[min(len(peaks) - 1, int(0.95 * len(peaks)))] if peaks else None,
        "prompt_tokens_max": peaks[-1] if peaks else None,
        "avg_turns": round(sum(turns) / n, 1),
        "avg_sec_per_sim": round(sum(s.get("duration") or 0 for s in sims) / n, 1),
        "user_cost_usd_per_sim": round(user_cost / n, 5),
        "openrouter_spend_usd": manifest.get("openrouter_spend_usd"),
        "language_correctness": round(sum(lang) / len(lang), 3) if lang else None,
        "user_sim_providers": " ".join(f"{p}:{n}" for p, n in sorted(providers.items(), key=str)),
        "retries": " ".join(retries(tau2_log)),
        "session_minutes": round((end - start).total_seconds() / 60, 1),
    }


def main(run_id: str) -> None:
    run_dir = ROOT / "runs" / run_id
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(run_dir / f"{run_id}.zip") as z:
        sims = json.loads(z.read("simulations/results.json"))["simulations"]
        tau2_log = z.read("logs/tau2.log").decode("utf-8", errors="replace") if "logs/tau2.log" in z.namelist() else ""
    row = summarize(sims, manifest, tau2_log)
    out = ROOT / "results" / "summary" / f"{run_id}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        w.writeheader()
        w.writerow(row)
    for k, v in row.items():
        print(f"{k:24s} {v}")
    print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv[1])

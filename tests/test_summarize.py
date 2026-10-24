"""Tests for src/summarize_run.py: the D5 overflow rule and the retry parser."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("summarize_run", ROOT / "src" / "summarize_run.py")
sr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sr)

MANIFEST = {"run_id": "R", "repo_sha": "abcdef0", "planned_sims": 2,
            "start_time": "2026-10-25T00:00:00+00:00", "end_time": "2026-10-25T00:10:00+00:00"}
LOG = ("  Retry 1/3 for task 29: litellm.ContextWindowExceededError: \n"
       "  Retry 1/3 for task 7: litellm.APIConnectionError: \n")


def sim(task_id: str, reward: float) -> dict:
    return {"task_id": task_id, "reward_info": {"reward": reward}, "duration": 60, "messages": []}


def test_retries_are_parsed_from_the_log():
    assert sr.retries(LOG) == ["29:ContextWindowExceededError", "7:APIConnectionError"]


def test_overflow_rerun_counts_as_fail_but_infra_rerun_does_not():
    row = sr.summarize([sim("29", 1.0), sim("7", 1.0)], MANIFEST, LOG)
    assert row["pass1_tau2"] == 1.0  # tau2 keeps both successful reruns
    assert row["pass1"] == 0.5  # D5: task 29 overflowed -> 0; task 7 was a server error -> kept
    assert row["n_overflow"] == 1


def test_prompt_peaks():
    chat = lambda *sizes: {**sim("1", 1.0), "messages": [{"role": "assistant", "usage": {"prompt_tokens": n}} for n in sizes]}
    row = sr.summarize([chat(1000, 9000), chat(500, 16000)], {**MANIFEST, "planned_sims": 2})
    assert (row["prompt_tokens_p95"], row["prompt_tokens_max"]) == (16000, 16000)

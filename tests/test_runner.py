"""CPU tests for runner/kaggle/run.py (everything except vLLM, tau2 and Kaggle itself)."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT.parent / "SEATauBench"

spec = importlib.util.spec_from_file_location("run", ROOT / "runner" / "kaggle" / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def test_smoke_config_loads():
    cfg = run.load_config(ROOT, "configs/runs/smoke_S4_dev2.yaml")
    assert cfg["task_ids"] == ["2", "57"]
    assert cfg["scenario"] == "l2_domain"


def test_task_list_config(tmp_path):
    (tmp_path / "configs" / "splits").mkdir(parents=True)
    shutil.copy(ROOT / "configs" / "splits" / "dev30.json", tmp_path / "configs" / "splits")
    (tmp_path / "c.yaml").write_text("scenario: english\ntask_list: configs/splits/dev30.json\n")
    assert len(run.load_config(tmp_path, "c.yaml")["task_ids"]) == 30


def test_tau2_cmd_s4_and_s1():
    cfg = {"scenario": "l2_domain", "agent_model": "Qwen/Qwen3-4B-Instruct-2507", "task_ids": ["2", "57"],
           "num_trials": 1, "max_concurrency": 2, "seed": 300}
    s4 = run.tau2_cmd(cfg, "RID")
    assert s4[s4.index("--lang-id") + 1] == "vi"
    assert s4[s4.index("--task-ids") + 1: s4.index("--task-ids") + 3] == ["2", "57"]
    assert s4[s4.index("--user-llm") + 1] == "openrouter/qwen/qwen3-235b-a22b-2507"
    assert "--auto-resume" in s4 and s4[s4.index("--save-to") + 1] == "RID"
    s1 = run.tau2_cmd({**cfg, "scenario": "english"}, "RID")
    assert "--lang-id" not in s1


@pytest.mark.skipif(not BENCH.exists(), reason="needs ../SEATauBench")
def test_patch_judge_on_real_config(tmp_path):
    src = BENCH / "src" / "tau2" / "config.py"
    (tmp_path / "src" / "tau2").mkdir(parents=True)
    dst = tmp_path / "src" / "tau2" / "config.py"
    shutil.copy(src, dst)
    run.patch_judge(tmp_path)
    before, after = src.read_text().splitlines(), dst.read_text().splitlines()
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    assert changed == [('DEFAULT_LLM_NL_ASSERTIONS = "azure/gpt-4.1-mini"',
                        'DEFAULT_LLM_NL_ASSERTIONS = "openrouter/openai/gpt-4.1-mini"')]

    # If SEATauBench ever renames the setting, the patch must fail loudly, not silently skip.
    dst.write_text(dst.read_text().replace("DEFAULT_LLM_NL_ASSERTIONS =", "RENAMED ="))
    with pytest.raises(RuntimeError):
        run.patch_judge(tmp_path)


def test_code_check_passes_on_same_file_and_fails_on_change(tmp_path):
    (tmp_path / "runner" / "kaggle").mkdir(parents=True)
    committed = tmp_path / "runner" / "kaggle" / "run.py"
    text = (ROOT / "runner" / "kaggle" / "run.py").read_text(encoding="utf-8")
    committed.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))  # a Windows checkout: CRLF must not matter
    run.check_code_matches_repo(tmp_path)
    committed.write_text("# %% [code]\n" + text, encoding="utf-8")  # Kaggle's cell marker must not matter
    run.check_code_matches_repo(tmp_path)
    committed.write_text(text.replace('MODE = "', 'MODE = "x'), encoding="utf-8")
    with pytest.raises(RuntimeError, match="commit and git push first"):
        run.check_code_matches_repo(tmp_path)


def test_progress_line():
    assert run.progress_line(0, 60, 30) == "[--------------------] 0/60 sims (0%) | elapsed 0h00m | ETA ?"
    assert run.progress_line(15, 60, 1800) == "[#####---------------] 15/60 sims (25%) | elapsed 0h30m | ETA 1h30m"


def test_count_done_and_summarize(tmp_path):
    p = tmp_path / "results.json"
    assert run.count_done(p) == 0  # not written yet
    sims = [
        {"reward_info": {"reward": 1.0}, "duration": 100, "agent_cost": 0, "user_cost": 0.01},
        {"reward_info": {"reward": 0.0}, "duration": 200, "agent_cost": 0, "user_cost": 0.02},
        {"reward_info": None, "duration": None, "agent_cost": None, "user_cost": None},  # crash (P5)
    ]
    p.write_text(json.dumps({"simulations": sims}))
    assert run.count_done(p) == 3
    s = run.summarize(p)
    assert (s["n_sims"], s["n_crashed"], s["pass1"], s["avg_sec_per_sim"]) == (3, 1, 0.333, 150.0)
    assert s["user_cost_usd"] == 0.03

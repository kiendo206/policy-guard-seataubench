"""Kaggle runner: one experiment per push.

Set GIT_REF, CONFIG, RUN_ID and MODE below, commit and push the repo, then:
    kaggle kernels push -p runner/kaggle --no-run
and start the run on the website (Edit -> Save Version -> Save & Run All): CLI-started runs can't read Secrets (P10).
MODE "keycheck" only checks the Kaggle Secrets (step 0.7). MODE "run" runs the experiment.
Results: /kaggle/working/<RUN_ID>.zip (simulations + logs) and /kaggle/working/manifest.json.
Progress is printed to the Kaggle log every minute and pushed to your phone (ntfy) at start, 25/50/75% and the end.
"""

import json
import linecache
import os
import re
import shutil
import signal
import subprocess
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# --- Set these for every push --------------------------------------------------------------------
GIT_REF = "main"  # branch, tag or SHA; the run stops unless this file equals run.py at GIT_REF, and the SHA goes into the manifest
CONFIG = "configs/runs/smoke_S4_dev2.yaml"
RUN_ID = "20261025-0315_smoke_q3-4b_S4_dev2_t1"
MODE = "run"  # "keycheck" or "run"

# --- Fixed setup (CLAUDE.md §3) -------------------------------------------------------------------
REPO_URL = "https://github.com/kiendo206/policy-guard-seataubench.git"
BENCH_URL = "https://github.com/SEACrowd/SEATauBench.git"
BENCH_SHA = "312f3e6eb87c94ad2554a74cc4f4b96baa6f89f9"
USER_LLM = "openrouter/qwen/qwen3-235b-a22b-2507"
JUDGE_LLM = "openrouter/openai/gpt-4.1-mini"  # P1: the code default azure/gpt-4.1-mini is unusable for us
VLLM_PORT = 8000
VLLM_FLAGS = [  # P2; --tensor-parallel-size is added at runtime from the GPU count
    "--dtype", "half", "--max-model-len", "24576", "--gpu-memory-utilization", "0.90",
    "--enable-auto-tool-choice", "--tool-call-parser", "hermes",
]
PROGRESS_EVERY_S = 60
MAX_TAU2_HOURS = 11.0  # P8: stop tau2 early so packaging finishes inside Kaggle's 12 h limit

OUT = Path("/kaggle/working") if Path("/kaggle/working").exists() else Path.cwd() / "_out"
SCRATCH = Path("/tmp/seatau")  # repos and the vLLM env stay out of the saved output
REPO, BENCH, VLLM_ENV, LOGS = SCRATCH / "repo", SCRATCH / "bench", SCRATCH / "vllm-env", SCRATCH / "logs"


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sh(cmd: list, cwd: Path | None = None) -> str:
    cmd = [str(c) for c in cmd]
    log("$ " + " ".join(cmd))
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd)}\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")
    return p.stdout.strip()


def get_secret(name: str) -> str | None:
    try:
        from kaggle_secrets import UserSecretsClient

        return UserSecretsClient().get_secret(name)
    except Exception as e:  # the reason (never the value) is what we need to debug a missing secret
        cause = e.__cause__
        body = cause.read()[:300] if hasattr(cause, "read") else b""
        log(f"Kaggle secret {name} not readable: {type(e).__name__}: {e} (cause: {cause!r}, reply: {body!r})")
        return os.environ.get(name)


def notify(topic: str | None, title: str, msg: str) -> None:
    """Push to the ntfy app. Never fails the run."""
    log(f"NOTIFY {title}: {msg}")
    if not topic:
        return
    try:
        req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=msg.encode("utf-8"), headers={"Title": title})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log(f"notification failed: {e}")


def fmt_duration(seconds: float) -> str:
    m = int(seconds // 60)
    return f"{m // 60}h{m % 60:02d}m"


def load_config(repo: Path, rel_path: str) -> dict:
    import yaml

    cfg = yaml.safe_load((repo / rel_path).read_text(encoding="utf-8"))
    if "task_list" in cfg:
        cfg["task_ids"] = json.loads((repo / cfg["task_list"]).read_text(encoding="utf-8"))["task_ids"]
    cfg["task_ids"] = [str(t) for t in cfg["task_ids"]]
    return cfg


def tau2_cmd(cfg: dict, run_id: str) -> list[str]:
    cmd = ["uv", "run", "tau2", "run", "--domain", "retail", "--seatau-scenario", cfg["scenario"]]
    if cfg["scenario"] != "english":
        cmd += ["--lang-id", "vi"]
    agent_args = {"temperature": 0, "api_base": f"http://127.0.0.1:{VLLM_PORT}/v1"}
    cmd += [
        "--agent-llm", f"hosted_vllm/{cfg['agent_model']}", "--agent-llm-args", json.dumps(agent_args),
        "--user-llm", USER_LLM, "--user-llm-args", json.dumps({"temperature": 0}),
        "--task-ids", *cfg["task_ids"], "--num-trials", str(cfg["num_trials"]),
        "--max-concurrency", str(cfg["max_concurrency"]), "--seed", str(cfg["seed"]),
        "--save-to", run_id, "--auto-resume",
    ]
    return cmd


def running_source() -> str:
    """The text of the code that is executing (works for a file and for Kaggle's notebook cell)."""
    return "".join(linecache.getlines(main.__code__.co_filename))


def check_code_matches_repo(repo: Path) -> None:
    """The manifest SHA must describe the code that ran: refuse an uncommitted or unpushed run.py."""
    def norm(s: str) -> str:  # Kaggle adds "# %% [code]" cell markers to the stored script
        return "\n".join(l for l in s.replace("\r\n", "\n").split("\n") if not l.startswith("# %%")).strip()

    committed = (repo / "runner" / "kaggle" / "run.py").read_text(encoding="utf-8")
    if not running_source() or norm(running_source()) != norm(committed):
        raise RuntimeError(f"run.py differs from runner/kaggle/run.py at GIT_REF={GIT_REF!r}: commit and git push first")


def patch_judge(bench: Path) -> str:
    """P1: point the NL-assertion judge at OpenRouter. Returns the patched line."""
    f = bench / "src" / "tau2" / "config.py"
    new_line = f'DEFAULT_LLM_NL_ASSERTIONS = "{JUDGE_LLM}"'
    text, n = re.subn(r'^DEFAULT_LLM_NL_ASSERTIONS = ".*"$', new_line, f.read_text(encoding="utf-8"), flags=re.M)
    if n != 1:
        raise RuntimeError(f"judge patch: expected 1 match in {f}, found {n}")
    f.write_text(text, encoding="utf-8")
    return new_line


def count_done(results_path: Path) -> int:
    try:
        return len(json.loads(results_path.read_text(encoding="utf-8"))["simulations"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return 0


def progress_line(done: int, total: int, elapsed_s: float) -> str:
    frac = done / total if total else 0.0
    bar = "#" * int(20 * frac) + "-" * (20 - int(20 * frac))
    eta = fmt_duration((total - done) * elapsed_s / done) if done else "?"
    return f"[{bar}] {done}/{total} sims ({frac:.0%}) | elapsed {fmt_duration(elapsed_s)} | ETA {eta}"


def summarize(results_path: Path) -> dict:
    sims = json.loads(results_path.read_text(encoding="utf-8"))["simulations"]
    rewards = [(s.get("reward_info") or {}).get("reward") for s in sims]
    durations = [s["duration"] for s in sims if s.get("duration") is not None]
    return {
        "n_sims": len(sims),
        "n_crashed": sum(r is None for r in rewards),  # P5: no reward_info -> crash, counted as reward 0
        "pass1": round(sum((r or 0) >= 1 for r in rewards) / len(sims), 3) if sims else None,
        "avg_sec_per_sim": round(sum(durations) / len(durations), 1) if durations else None,
        "agent_cost_usd": round(sum(s.get("agent_cost") or 0 for s in sims), 4),
        "user_cost_usd": round(sum(s.get("user_cost") or 0 for s in sims), 4),
    }


def openrouter_usage(key: str) -> float | None:
    """Total USD spent so far on this OpenRouter key (user simulator + judge)."""
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"})
        return float(json.loads(urllib.request.urlopen(req, timeout=15).read())["data"]["usage"])
    except Exception as e:
        log(f"could not read OpenRouter usage: {e}")
        return None


def setup_code(manifest: dict) -> None:
    sh(["pip", "install", "-q", "uv"])
    sh(["git", "clone", "-q", REPO_URL, REPO])
    sh(["git", "checkout", "-q", GIT_REF], cwd=REPO)
    manifest["repo_sha"] = sh(["git", "rev-parse", "HEAD"], cwd=REPO)
    check_code_matches_repo(REPO)
    BENCH.mkdir(parents=True)
    sh(["git", "init", "-q"], cwd=BENCH)
    sh(["git", "fetch", "-q", "--depth", "1", BENCH_URL, BENCH_SHA], cwd=BENCH)
    sh(["git", "checkout", "-q", "FETCH_HEAD"], cwd=BENCH)
    manifest["seataubench_commit"] = sh(["git", "rev-parse", "HEAD"], cwd=BENCH)
    log("judge patched: " + patch_judge(BENCH))
    sh(["uv", "sync", "--python", "3.12", "--extra", "experiments"], cwd=BENCH)
    lid = BENCH / "data" / "models" / "lid.176.bin"
    lid.parent.mkdir(parents=True, exist_ok=True)
    sh(["curl", "-sL", "-o", lid, "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"])


def start_vllm(model: str, manifest: dict) -> subprocess.Popen:
    sh(["uv", "venv", VLLM_ENV, "--python", "3.12", "-q"])
    sh(["uv", "pip", "install", "--python", VLLM_ENV / "bin" / "python", "-q", "vllm"])
    manifest["vllm_version"] = sh([VLLM_ENV / "bin" / "python", "-c", "import vllm; print(vllm.__version__)"])
    gpus = sh(["nvidia-smi", "-L"]).splitlines()
    manifest["gpu"] = gpus
    flags = VLLM_FLAGS + ["--tensor-parallel-size", str(max(1, len(gpus)))]
    manifest["vllm_flags"] = flags
    proc = subprocess.Popen(
        [str(VLLM_ENV / "bin" / "vllm"), "serve", model, "--port", str(VLLM_PORT), *flags],
        stdout=open(LOGS / "vllm.log", "w"), stderr=subprocess.STDOUT,
    )
    for _ in range(120):  # up to 20 min (the first start downloads the model)
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{VLLM_PORT}/v1/models", timeout=5)
            log("vLLM is ready")
            return proc
        except Exception:
            if proc.poll() is not None:
                raise RuntimeError("vLLM exited:\n" + (LOGS / "vllm.log").read_text()[-3000:])
            time.sleep(10)
    raise TimeoutError("vLLM not ready after 20 min (see vllm.log)")


def tool_call_check(model: str) -> None:
    """One call: if the model cannot call a tool, every task would fail, so stop now."""
    tool = {"type": "function", "function": {
        "name": "get_user_details", "description": "Get user details",
        "parameters": {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]}}}
    body = {"model": model, "temperature": 0, "tools": [tool],
            "messages": [{"role": "user", "content": "Tra cứu thông tin người dùng có mã emma_kim_9957 giúp tôi."}]}
    req = urllib.request.Request(f"http://127.0.0.1:{VLLM_PORT}/v1/chat/completions",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    msg = json.loads(urllib.request.urlopen(req, timeout=120).read())["choices"][0]["message"]
    if not msg.get("tool_calls"):
        raise RuntimeError(f"tool-call check failed, model replied: {msg}")
    log(f"tool-call check OK: {msg['tool_calls'][0]['function']}")


def run_tau2(cfg: dict, manifest: dict, topic: str | None) -> Path:
    cmd = tau2_cmd(cfg, RUN_ID)
    manifest["tau2_command"] = cmd
    total = manifest["planned_sims"]
    results = BENCH / "data" / "simulations" / RUN_ID / "results.json"
    proc = subprocess.Popen(cmd, cwd=BENCH, stdout=open(LOGS / "tau2.log", "w"), stderr=subprocess.STDOUT)
    t0, next_milestone = time.time(), 0.25
    while proc.poll() is None:
        time.sleep(PROGRESS_EVERY_S)
        done, elapsed = count_done(results), time.time() - t0
        line = progress_line(done, total, elapsed)
        log(line)
        if total and done / total >= next_milestone and next_milestone < 1:
            notify(topic, f"{int(next_milestone * 100)}% done", f"{RUN_ID}\n{line}")
            next_milestone += 0.25
        if elapsed > MAX_TAU2_HOURS * 3600:
            log("time limit reached: stopping tau2 (rerun the remaining sims with --auto-resume)")
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=300)
            manifest["stopped_at_time_limit"] = True
            break
    if proc.returncode not in (0, None) and not manifest.get("stopped_at_time_limit"):
        raise RuntimeError(f"tau2 exited with {proc.returncode}:\n" + (LOGS / "tau2.log").read_text()[-3000:])
    return results


def package(manifest: dict) -> None:
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    bundle = SCRATCH / "bundle" / RUN_ID
    bundle.mkdir(parents=True, exist_ok=True)
    sims = BENCH / "data" / "simulations" / RUN_ID
    if sims.exists():
        shutil.copytree(sims, bundle / "simulations", dirs_exist_ok=True)
    if LOGS.exists():
        shutil.copytree(LOGS, bundle / "logs", dirs_exist_ok=True)
    shutil.copy(OUT / "manifest.json", bundle / "manifest.json")
    shutil.make_archive(str(OUT / RUN_ID), "zip", bundle)
    log(f"saved {OUT / (RUN_ID + '.zip')} and {OUT / 'manifest.json'}")


def main() -> None:
    topic = get_secret("NTFY_TOPIC")
    key = get_secret("OPENROUTER_API_KEY")
    if MODE == "keycheck":
        try:  # runs need internet (GitHub, Hugging Face, OpenRouter); Kaggle turns it off without phone verification
            urllib.request.urlopen("https://github.com", timeout=10)
            print("internet: True")
        except Exception as e:
            print(f"internet: False ({type(e).__name__}: {e})")
        print("secrets token present:", "KAGGLE_USER_SECRETS_TOKEN" in os.environ)  # set only when secrets are attached
        print("key loaded:", bool(key))
        print("ntfy topic loaded:", bool(topic))
        notify(topic, "Kaggle keycheck", f"{RUN_ID}: OPENROUTER_API_KEY loaded: {bool(key)}, NTFY_TOPIC loaded: {bool(topic)}")
        return

    if not key:
        raise RuntimeError("OPENROUTER_API_KEY secret is missing (Add-ons -> Secrets)")
    os.environ["OPENROUTER_API_KEY"] = key
    LOGS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"run_id": RUN_ID, "git_ref": GIT_REF, "config_path": CONFIG, "user_llm": USER_LLM,
                "judge_llm": JUDGE_LLM, "start_time": now_iso()}
    usage_before = openrouter_usage(key)
    vllm = None
    t0 = time.time()
    try:
        setup_code(manifest)
        cfg = load_config(REPO, CONFIG)
        manifest.update(config=cfg, agent_model=cfg["agent_model"], task_ids=cfg["task_ids"],
                        num_trials=cfg["num_trials"], planned_sims=len(cfg["task_ids"]) * cfg["num_trials"])
        notify(topic, "Run started", f"{RUN_ID}: {manifest['planned_sims']} sims planned, setting up vLLM")
        vllm = start_vllm(cfg["agent_model"], manifest)
        tool_call_check(cfg["agent_model"])
        results = run_tau2(cfg, manifest, topic)
        manifest["summary"] = summarize(results)
        s = manifest["summary"]
        notify(topic, "Run finished", f"{RUN_ID}\n{s['n_sims']}/{manifest['planned_sims']} sims, "
               f"{s['n_crashed']} crashed, pass^1 {s['pass1']}, {s['avg_sec_per_sim']} s/sim, "
               f"total {fmt_duration(time.time() - t0)}")
    except Exception as e:
        manifest["error"] = traceback.format_exc()[-3000:]
        notify(topic, "Run FAILED", f"{RUN_ID}: {type(e).__name__}: {str(e)[:300]}")
        raise
    finally:
        if vllm is not None:
            vllm.send_signal(signal.SIGINT)
        usage_after = openrouter_usage(key)
        if usage_before is not None and usage_after is not None:
            manifest["openrouter_spend_usd"] = round(usage_after - usage_before, 4)  # user simulator + judge
        manifest["end_time"] = now_iso()
        package(manifest)


if __name__ == "__main__":
    main()

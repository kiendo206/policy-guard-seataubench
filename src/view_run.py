"""Readable conversations of one run (step 0.11): runs/<RUN_ID>/readable/index.md + one .md file per chat.

Usage: uv run --no-project --python 3.12 python src/view_run.py <RUN_ID>
Reads runs/<RUN_ID>/<RUN_ID>.zip and never modifies it. Open the .md files in VS Code (Ctrl+Shift+V = preview).
"""

import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarize_run import retries  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEAKER = {"user": "🧑 Customer", "assistant": "🤖 Agent"}


def one_line(text: object, limit: int = 300) -> str:
    s = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
    s = " ".join(s.split())
    return s if len(s) <= limit else s[:limit] + " …"


def readable(content: object) -> str:
    """A tool result as readable text: JSON pretty-printed with real Vietnamese letters (tau2 stores them as \\uXXXX)."""
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except ValueError:
            return content
    return json.dumps(content, ensure_ascii=False, indent=2) if not isinstance(content, str) else content


def call(name: str, args: dict) -> str:
    return f"{name}(" + ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in (args or {}).items()) + ")"


def chat_markdown(sim: dict, task: dict, run_id: str, overflow: bool) -> str:
    ri = sim.get("reward_info") or {}
    reward = ri.get("reward")
    verdict = "💥 CRASH (no grade)" if reward is None else ("✅ PASS" if reward >= 1 else "❌ FAIL")
    if overflow:
        verdict += " · ⚠️ first attempt overflowed the context, scored 0 (D5)"
    msgs = sim.get("messages") or []
    turns = sum(m.get("role") in SPEAKER for m in msgs)
    out = [f"# Task {sim['task_id']} · trial {sim.get('trial')} · {verdict} (reward {reward})", "",
           f"Run `{run_id}` · ended `{sim.get('termination_reason')}` · {turns} turns · "
           f"{sim.get('duration') or 0:.0f} s · customer cost ${sim.get('user_cost') or 0:.4f}", ""]

    goal = ((task or {}).get("user_scenario") or {}).get("instructions") or {}
    if isinstance(goal, dict) and goal:
        out += ["## The customer's goal (hidden from the agent)", ""]
        for key, label in [("reason_for_call", "Wants"), ("known_info", "Knows"),
                           ("unknown_info", "Doesn't know"), ("task_instructions", "Behaviour")]:
            if goal.get(key):
                out.append(f"- **{label}:** {goal[key]}")
        out.append("")

    out += ["## Conversation", ""]
    n = 0
    for m in msgs:
        role = m.get("role")
        if role in SPEAKER and m.get("content"):
            n += 1
            out += [f"**[{n}] {SPEAKER[role]}:** {m['content'].strip()}", ""]
        for tc in m.get("tool_calls") or []:
            out.append(f"- 🔧 `{call(tc.get('name'), tc.get('arguments'))}`")
        if role == "tool":
            flag = "⚠️ error: " if m.get("error") else "→ "
            full = readable(m.get("content"))
            out += [f"  - {flag}`{one_line(full, 200)}`", ""]
            if len(" ".join(full.split())) > 200:  # the preview was cut: offer the whole result
                out += ["<details><summary>Full result</summary>", "", "```json", full, "```", "", "</details>", ""]
    out.append("")

    out += ["## Grading", ""]
    db = ri.get("db_check") or {}
    out.append("The task passes only if every check below is ✅.")
    out.append("")
    out.append(f"- **Database check:** {'✅ the database ends exactly as expected' if db.get('db_match') else '❌ the database differs from the expected end state (a missing, wrong or extra change)'}"
               if db else "- **Database check:** not done")
    judged = ri.get("nl_assertions") or []
    for a in judged:
        out.append(f"- **Judge check:** {'✅' if a.get('met') else '❌'} the agent should: {a.get('nl_assertion')}  \n  _Judge's reason:_ {a.get('justification')}")
    if not judged:
        out.append("- **Judge check:** – (this task has none)")
    checks = ri.get("action_checks") or []
    if checks:
        out += ["", "**Expected actions** (for reading only; pass/fail uses the database check and the judge check):", ""]
        for c in checks:
            act = c.get("action") or {}
            out.append(f"- {'✅' if c.get('action_match') else '❌'} `{call(act.get('name'), act.get('arguments'))}`")
    return "\n".join(out) + "\n"


def write_readable(run_id: str, run_dir: Path) -> Path:
    with zipfile.ZipFile(run_dir / f"{run_id}.zip") as z:
        results = json.loads(z.read("simulations/results.json"))
        log = z.read("logs/tau2.log").decode("utf-8", "replace") if "logs/tau2.log" in z.namelist() else ""
    tasks = {str(t["id"]): t for t in results.get("tasks") or []}
    reruns = {}
    for r in retries(log):
        task_id, error = r.split(":")
        reruns.setdefault(task_id, []).append(error)
    out_dir = run_dir / "readable"
    out_dir.mkdir(exist_ok=True)
    rows = []
    for sim in sorted(results["simulations"], key=lambda s: (int(s["task_id"]), s.get("trial") or 0)):
        tid = str(sim["task_id"])
        overflow = "ContextWindowExceededError" in reruns.get(tid, [])
        name = f"task{tid}_t{sim.get('trial')}.md"
        (out_dir / name).write_text(chat_markdown(sim, tasks.get(tid), run_id, overflow), encoding="utf-8")
        ri = sim.get("reward_info") or {}
        reward = 0.0 if overflow else ri.get("reward")
        turns = sum(m.get("role") in SPEAKER for m in sim.get("messages") or [])
        rows.append(f"| [{tid}]({name}) | {sim.get('trial')} | {'✅' if (reward or 0) >= 1 else '❌'} | {reward} | "
                    f"{(ri.get('reward_breakdown') or {}).get('DB')} | "
                    # tau2 writes NL 1.0 even when a task has no NL assertions; show "–" then, as the legend says
                    f"{(ri.get('reward_breakdown') or {}).get('NL_ASSERTION') if ri.get('nl_assertions') else '–'} | "
                    f"{sim.get('termination_reason')} | {turns} | {sim.get('duration') or 0:.0f} | "
                    f"${sim.get('user_cost') or 0:.4f} | {' '.join(reruns.get(tid, []))} |")
    n_pass = sum("| ✅ |" in r for r in rows)
    index = [f"# {run_id}", "", f"{len(rows)} conversations · {n_pass} passed (D5 rule). Click a task to read it.", "",
             "**How a task is graded** (it passes only if both checks are 1.0):",
             "- **Database check:** after the chat, is the shop's database exactly as it should be? "
             "(right changes made, no wrong or extra changes) 1.0 = passed, 0.0 = failed.",
             "- **Judge check:** some tasks require the agent to tell the customer something; "
             "a judge model (gpt-4.1-mini) reads the chat and decides whether the agent said it. "
             "1.0 = passed, 0.0 = failed, – = this task has no judge check.",
             "",
             "| Task | Trial | Pass | Reward | Database check | Judge check | Ended | Turns | Seconds | Customer $ | Reruns |",
             "|---|---|---|---|---|---|---|---|---|---|---|", *rows]
    (out_dir / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return out_dir


if __name__ == "__main__":
    rid = sys.argv[1]
    print(f"-> {write_readable(rid, ROOT / 'runs' / rid)}")

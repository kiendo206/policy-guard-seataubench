"""Tests for src/view_run.py on a small synthetic run (Vietnamese text, a tool error, an overflow rerun)."""

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("view_run", ROOT / "src" / "view_run.py")
vr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vr)


def make_run(tmp_path: Path) -> Path:
    sims = [
        {"task_id": "7", "trial": 0, "termination_reason": "user_stop", "duration": 61.0, "user_cost": 0.001,
         "messages": [
             {"role": "user", "content": "Xin chào, tôi muốn hủy đơn hàng #W1."},
             {"role": "assistant", "content": None, "tool_calls": [{"name": "get_order_details", "arguments": {"order_id": "#W1"}}]},
             {"role": "tool", "content": "Error: order not found", "error": True},
             # like tau2: a long JSON result with Vietnamese stored as \uXXXX escapes
             {"role": "tool", "content": json.dumps({"items": [{"name": "Đồng hồ thông minh", "note": "x" * 300}]})},
             {"role": "assistant", "content": "Đơn hàng đã được hủy."}],
         "reward_info": {"reward": 0.0, "reward_basis": ["DB", "NL_ASSERTION"], "reward_breakdown": {"DB": 0.0, "NL_ASSERTION": 0.0},
                         "db_check": {"db_match": False},
                         "nl_assertions": [{"nl_assertion": "Đại lý nên từ chối", "met": False, "justification": "It claimed success."}],
                         "action_checks": [{"action": {"name": "cancel_pending_order", "arguments": {"order_id": "#W1"}}, "action_match": False}]}},
        {"task_id": "29", "trial": 0, "termination_reason": "user_stop", "duration": 30.0, "user_cost": 0.0, "messages": [],
         # like tau2: NL_ASSERTION 1.0 although the task has no NL assertions
         "reward_info": {"reward": 1.0, "reward_breakdown": {"DB": 1.0, "NL_ASSERTION": 1.0}, "db_check": {"db_match": True}}},
    ]
    tasks = [{"id": "7", "user_scenario": {"instructions": {"reason_for_call": "Hủy đơn #W1", "known_info": "Bạn là Mei."}}}]
    run_dir = tmp_path / "R"
    run_dir.mkdir()
    with zipfile.ZipFile(run_dir / "R.zip", "w") as z:
        z.writestr("simulations/results.json", json.dumps({"tasks": tasks, "simulations": sims}, ensure_ascii=False))
        z.writestr("logs/tau2.log", "  Retry 1/3 for task 29: litellm.ContextWindowExceededError: \n")
    return run_dir


def test_readable_files(tmp_path):
    out = vr.write_readable("R", make_run(tmp_path))
    chat = (out / "task7_t0.md").read_text(encoding="utf-8")
    assert "Xin chào, tôi muốn hủy đơn hàng #W1." in chat  # Vietnamese survives (UTF-8)
    assert "Wants:** Hủy đơn #W1" in chat  # the customer's hidden goal
    assert '🔧 `get_order_details(order_id="#W1")`' in chat and "⚠️ error: `Error: order not found`" in chat
    assert "\\u0110" not in chat and '"name": "Đồng hồ thông minh"' in chat  # escapes turned back into letters
    assert "<summary>Full result</summary>" in chat and "x" * 300 in chat  # nothing cut off in the fold-out
    assert "Database check:** ❌" in chat and "Judge check:** ❌ the agent should: Đại lý nên từ chối" in chat
    assert "DB" not in chat and "NL" not in chat  # no unexplained abbreviations (student's request)
    assert "❌ `cancel_pending_order(order_id=\"#W1\")`" in chat

    overflow_chat = (out / "task29_t0.md").read_text(encoding="utf-8")
    assert "first attempt overflowed the context, scored 0 (D5)" in overflow_chat
    index = (out / "index.md").read_text(encoding="utf-8")
    assert "2 conversations · 0 passed (D5 rule)" in index  # task 29's rerun passed, but D5 scores it 0
    assert "ContextWindowExceededError" in index
    assert "| Database check | Judge check |" in index and "DB" not in index and "NL" not in index
    assert "| [29](task29_t0.md) | 0 | ❌ | 0.0 | 1.0 | – |" in index  # no NL check -> "–", not tau2's 1.0

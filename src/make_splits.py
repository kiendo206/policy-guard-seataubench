"""Make the fixed task lists for the retail domain (CLAUDE.md §2, step 0.3).

dev30  = 30 tasks sampled from the official train split with seed 20214906 (guards are designed on these only)
eval84 = the other 84 of the 114 retail tasks
test40 = the official test split (used for RQ2b)

Usage: uv run --no-project --python 3.12 python src/make_splits.py [path/to/SEATauBench]
"""

import json
import random
import sys
from pathlib import Path

SEED = 20214906
SEATAUBENCH_COMMIT = "312f3e6"
OUT_DIR = Path(__file__).resolve().parent.parent / "configs" / "splits"


def main() -> None:
    bench = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "SEATauBench"
    split_file = bench / "data" / "tau2" / "domains" / "retail" / "split_tasks.json"
    splits = json.loads(split_file.read_text(encoding="utf-8"))

    by_number = lambda ids: sorted(ids, key=int)
    train, test, base = by_number(splits["train"]), by_number(splits["test"]), by_number(splits["base"])

    dev = by_number(random.Random(SEED).sample(train, 30))
    eval_ = by_number(set(base) - set(dev))

    source = f"SEATauBench@{SEATAUBENCH_COMMIT}:data/tau2/domains/retail/split_tasks.json"
    lists = {
        "dev30": (dev, f"30 tasks sampled from 'train' with random.Random({SEED}).sample"),
        "eval84": (eval_, "all 'base' tasks not in dev30"),
        "test40": (test, "the official 'test' split, unchanged"),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, (ids, how) in lists.items():
        record = {"name": name, "source": source, "how": how, "seed": SEED, "n": len(ids), "task_ids": ids}
        (OUT_DIR / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"{name}: {len(ids)} tasks -> {OUT_DIR / (name + '.json')}")


if __name__ == "__main__":
    main()

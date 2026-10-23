# Policy Guards and Early Escalation for Small Local LLM Agents (SEATauBench retail)

Graduation thesis code (HUST SoICT). It studies policy guards and early escalation for small local LLM
customer-service agents (Qwen3-4B) on the retail domain of
[SEATauBench](https://github.com/SEACrowd/SEATauBench), in English (S1) and fully Vietnamese (S4).

> Work in progress. This README grows as each part is built.

## Layout
| Path | Contents |
|---|---|
| `configs/splits/` | Fixed task lists: `dev30` (guard design), `eval84` (main evaluation), `test40` (official test split) |
| `configs/runs/` | One config file per experiment |
| `runner/kaggle/` | Script that runs an experiment on a Kaggle GPU and writes a `manifest.json` |
| `src/` | Split generation, analysis, guards, escalation |
| `tests/` | Unit tests |
| `results/summary/` | Small CSV summaries per run |
| `docs/` | Run log, design decisions, lessons learned |

## Reproduce the task lists
Requires [uv](https://docs.astral.sh/uv/). SEATauBench must sit next to this repo at commit `312f3e6`:
```bash
git clone https://github.com/SEACrowd/SEATauBench.git ../SEATauBench
git -C ../SEATauBench checkout 312f3e6
uv run --no-project --python 3.12 python src/make_splits.py
```
This rewrites `configs/splits/*.json` byte for byte (seed `20214906`).

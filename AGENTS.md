> This file mirrors `.github/copilot-instructions.md` and `CLAUDE.md`; keep all three in sync when any changes.

# AGENTS.md — global-oil-supply-resilience-hormuz-model

## Purpose
A live-data and Monte Carlo model for oil-supply resilience during a prolonged Strait of Hormuz disruption.

## Tech stack
- Python; dependencies in `requirements.txt`
- Key libraries: `pandas`, `numpy`, `matplotlib`, `pytest`, `reportlab`, `streamlit`

## Folder structure
- `data/` (4 files)
- `output/` (1 files)
- `outputs/` (1 files)
- `src/` (5 files)
- `tests/` (1 files)
- `.env.example`
- `README.md`
- `app.py`
- `main.py`
- `pytest.ini`
- `requirements.txt`

## Setup, run, test
Commands documented in README.md (referenced files exist):
```bash
python -m venv .venv
pip install -r requirements.txt
python main.py
streamlit run app.py
```
- Tests: 1 Python test file(s) under `tests/`; framework appears to be pytest. Add/update tests with any logic change.

## Conventions observed
- Functions use type hints; keep annotating new code.
- Uses `dataclasses` for structured config/results.
- Random seeds are set for reproducibility (Monte Carlo/simulation); keep seeded, deterministic runs.
- Credentials/API keys come from environment variables (see `.env.example`); never hardcode them.
- Public data sources referenced: EIA.
- Write paths relative to the repo root (no absolute local paths).

## Output artifacts
- Generated outputs go to `outputs/`.
- A PDF report is produced with `reportlab`; keep it in sync with model changes.
- Streamlit dashboard: `app.py` (run with `streamlit run <file>`).
- Charts are generated with matplotlib.

## Guardrails
- Never commit secrets, API keys, tokens, or `.env` files.
- Do not commit large raw datasets or binaries; keep data fetched or documented with its source.
- Keep analysis source-backed: cite data sources and assumptions; label scenario/forecast outputs as model estimates, not facts.
- Preserve reproducibility: no unseeded randomness, no hidden manual steps.

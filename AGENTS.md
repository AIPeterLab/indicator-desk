# Codex project instructions

## Purpose and source of truth

Indicator Desk is a static public dashboard that reports the percentage of current SPY, QQQ, IWM, and XLG holdings at least 20% below their 52-week highs.

- Read `README.md` for the project entry point and refresh command.
- Read `DATA_SOURCES.md` for data definitions, sources, and known data-quality risks.
- Read `TIINGO_SETUP.md` only when using optional Tiingo prices.
- Read `MIGRATION_HANDOFF.md` for recovery context and unfinished operational work.

## Working rules

- Keep secrets out of Git. Never commit `.env`, `.env.local`, tokens, credentials, or private keys. Only document environment-variable names and placeholders.
- Treat `data/raw/`, `logs/`, `qa/`, and Python bytecode as local/generated artifacts unless the user explicitly requests otherwise.
- The tracked dashboard outputs are `data/technical_bear_summary.csv`, `data/technical_bear_summary.json`, and `data/technical_bear_meta.json`.
- A normal refresh may make large, expected changes to those three generated outputs. Review their metadata and diffs before committing.
- Preserve the indicator definition unless the user explicitly asks to change it: unweighted share of current ETF equity holdings whose latest adjusted price is at least 20% below the maximum adjusted daily high over the last 252 trading days.
- Do not force-push or rewrite shared history without explicit user approval.

## Commands and validation

The updater uses only the Python standard library and is intended for Python 3:

```powershell
python scripts/update_technical_bear_breadth.py --help
python -m py_compile scripts/update_technical_bear_breadth.py
python scripts/update_technical_bear_breadth.py --etfs SPY --max-symbols 3 --sleep 0.05
python scripts/update_technical_bear_breadth.py --sleep 0.05
```

The smoke test and full refresh require outbound internet access and overwrite the tracked summary outputs. Run them only when data refresh is intended.

## Delivery

- Production is documented as Cloudflare Pages deploying from GitHub `main` to `https://indicator.aipeterlab.com/`.
- `.github/workflows/update-dashboard.yml` provides a manually dispatched data refresh that commits generated summaries back to `main`.
- GitHub/Cloudflare configuration and any external centralized schedule live outside this repository; verify them in their service consoles when changing deployment or automation.

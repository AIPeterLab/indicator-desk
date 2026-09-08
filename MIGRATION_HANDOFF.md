# Migration handoff

This file makes Indicator Desk recoverable without relying on Codex chat history, account-specific custom instructions, plugins, or local Codex configuration. Start with `README.md`, then use `AGENTS.md` for operating rules.

## Project and current status

Indicator Desk is a dependency-light static dashboard for technical bear-market breadth across SPY, QQQ, IWM, and XLG. The repository's canonical GitHub remote is `https://github.com/AIPeterLab/indicator-desk.git`, the working branch is `main`, and the documented production site is `https://indicator.aipeterlab.com/`.

As of 2026-09-08, the tracked data metadata reports a successful Yahoo-price run from the same date with no recorded errors. The project has no build step: `index.html`, `styles.css`, and `app.js` consume the tracked files under `data/` directly.

## Structure

- `index.html`, `styles.css`, `app.js`: static dashboard.
- `scripts/update_technical_bear_breadth.py`: holdings/price retrieval, calculation, local raw-data logging, and tracked summary generation.
- `data/technical_bear_summary.{csv,json}` and `data/technical_bear_meta.json`: generated, published dashboard data.
- `DATA_SOURCES.md`: source selection, calculation definition, and known data risks.
- `TIINGO_SETUP.md`: optional Tiingo configuration.
- `.github/workflows/update-dashboard.yml`: manual GitHub Actions refresh and commit workflow.

There are no repository-local custom slash commands, Codex skills, package manifests, databases, or application frameworks.

## Environment and dependencies

- Required: Git, Python 3, internet access, and a browser for viewing the static dashboard.
- Python packages: none; the updater uses the standard library only.
- Optional system dependency: `curl`/`curl.exe`, used only as a fallback for Invesco requests.
- Optional environment variable: `TIINGO_API_KEY`. Yahoo Finance is the default price source and requires no key.
- External data services: State Street SPY holdings, BlackRock/iShares IWM holdings, Invesco QQQ/XLG holdings, Yahoo Finance chart data, and optional Tiingo prices. Details and risks are in `DATA_SOURCES.md`.
- External delivery services: GitHub Actions and Cloudflare Pages. Their account-side settings, permissions, custom-domain configuration, and any external centralized refresh schedule are not reproducible from this repository alone.

Use the commands in `AGENTS.md`. A full refresh can take several minutes, especially for IWM, and modifies the tracked summary files.

## Design and workflow decisions

- The metric is unweighted across valid equity holdings; it is not portfolio-weighted.
- The technical-bear threshold is a drawdown of 20% or more from the adjusted 252-trading-day high.
- Yahoo Finance is the default no-key price source; Tiingo is optional.
- Raw downloads and run logs stay local to avoid repository bloat. Published summaries are tracked so the static site needs no runtime backend.
- Production deploys from `main`; do not force-push.

## Secrets and local-only artifacts

- `.env.local` is intentionally ignored and must remain outside Git. It contains the local value for the optional `TIINGO_API_KEY`; back it up only in a secure credential manager if still needed.
- The historical tracked `.env.local.example` contained a credential-shaped value before this migration backup. The example is now a placeholder, but Git history still contains the old value. Revoke/rotate that Tiingo credential; do not reuse it.
- `data/raw/` contains downloaded holdings snapshots and is reproducible from external sources. It does not need Git or Git LFS for normal recovery.
- `logs/` contains generated run diagnostics and does not need backup for normal recovery.
- `scripts/__pycache__/` is generated Python bytecode and should not be backed up.
- `qa/` contains local screenshots (under 1 MB total). They are not required to run or recover the project; preserve them separately only if their visual QA history matters.

## Unfinished operational work and known problems

- Manually revoke/rotate the Tiingo key that was previously present in Git history, then update the ignored `.env.local` or a secure service secret if Tiingo remains in use.
- Verify that the GitHub Actions workflow still has permission to push to `main` under current branch-protection rules.
- Verify the Cloudflare Pages project, custom domain, and GitHub connection after account changes. Those settings are not stored here.
- Identify and document the owner/configuration of the "centralized refresh schedule" that replaced the repository cron schedule; only manual `workflow_dispatch` remains in this repository.
- Yahoo Finance is not a formal supported market-data API, and upstream holdings formats can change. See `DATA_SOURCES.md` before diagnosing refresh failures.

## Fresh-session recovery

```powershell
git clone https://github.com/AIPeterLab/indicator-desk.git
cd indicator-desk
python scripts/update_technical_bear_breadth.py --help
python -m py_compile scripts/update_technical_bear_breadth.py
```

Open `index.html` to inspect the checked-in dashboard, or serve the directory with any static HTTP server. A fresh Codex session should read `AGENTS.md`, `README.md`, and this file before changing data or deployment behavior. No old chat history or account-specific Codex settings are required for code work.

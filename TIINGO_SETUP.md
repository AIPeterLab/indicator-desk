# Tiingo Setup

Keep the Tiingo API key out of the script.

Recommended local file:

1. Copy `.env.local.example` to `.env.local`
2. Replace the placeholder with your real Tiingo token:

```text
TIINGO_API_KEY=paste-your-tiingo-token-here
```

`.env.local` is ignored by git and should stay private on this computer.

For a one-session PowerShell run instead:

```powershell
$env:TIINGO_API_KEY = "paste-your-tiingo-token-here"
python scripts/update_technical_bear_breadth.py --etfs QQQ XLG --max-symbols 3 --sleep 0.2
```

For the full indicator after the smoke test:

```powershell
$env:TIINGO_API_KEY = "paste-your-tiingo-token-here"
python scripts/update_technical_bear_breadth.py --sleep 0.2
```

The current script uses Yahoo prices by default for all ETFs. Tiingo is optional and only used for `QQQ` and `XLG` when you pass `--use-tiingo-prices`.

# Indicator Desk

Public dashboard for technical bear-market breadth across four major ETF/index baskets:

- `SPY` - S&P 500 ETF
- `QQQ` - Nasdaq-100 ETF
- `IWM` - Russell 2000 ETF
- `XLG` - S&P 500 Top 50 ETF

The dashboard measures the share of current holdings trading more than 20% below their own 52-week high.

## Latest Local Result

See `data/technical_bear_summary.csv` and `data/technical_bear_summary.json`.

## Refresh

```powershell
python scripts/update_technical_bear_breadth.py --sleep 0.05
```

The default price source is Yahoo Finance chart data. Tiingo remains optional and is not required for the dashboard.

# Technical Bear-Market Breadth Data Sources

This first pass measures the share of each ETF's equity holdings that are more than 20% below their own 52-week high.

## Holdings Sources

| ETF | Preferred source | First-pass status |
| --- | --- | --- |
| SPY | State Street daily SPY holdings XLSX | Direct raw file path is available. |
| QQQ | Invesco DNG holdings API discovered from the official QQQ page | Direct browser/API feed includes ticker, issuer name, CUSIP, security type, and weight. |
| IWM | iShares IWM holdings CSV/XLS download | Direct raw CSV path is available. |
| XLG | Invesco DNG holdings API discovered from the official XLG page | Direct browser/API feed includes ticker, issuer name, CUSIP, security type, and weight. |

## Price Sources

The script uses Yahoo Finance chart data by default. Tiingo daily prices can be enabled with `--use-tiingo-prices`, but are no longer needed for normal runs because QQQ and XLG holdings now come from Invesco.

For the 52-week calculation, use adjusted prices where possible:

```text
52-week high = max(adjusted daily high over the last 252 trading days)
latest price = latest adjusted close
drawdown = latest price / 52-week high - 1
technical bear = drawdown <= -20%
```

## Known First-Pass Risks

- Yahoo Finance is convenient and no-key, but it is not a formal supported market-data API.
- IWM has roughly 2,000 holdings, so full runs need batching and may take several minutes with free data sources.
- Holdings files include cash, futures, or non-equity rows in some cases; the script filters obvious non-equity rows and records missing tickers in the log.

#!/usr/bin/env python3
"""Build technical bear-market breadth readings for SPY, QQQ, IWM, and XLG.

The indicator is the unweighted share of current ETF equity holdings trading
at least 20% below their own 52-week high.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import shutil
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
LOG_DIR = ROOT / "logs"
ENV_LOCAL_PATH = ROOT / ".env.local"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)
TIINGO_ETFS: set[str] = set()

HOLDING_URLS = {
    "SPY": {
        "kind": "xlsx",
        "url": "https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx",
    },
    "IWM": {
        "kind": "xlsx",
        "url": "https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v1/get-fund-document"
        "?appSubType=ISHARES&appType=PRODUCT_PAGE&component=fundDownload&locale=en_US&portfolioId=239710"
        "&targetSite=us-ishares&userType=individual",
    },
    "QQQ": {
        "kind": "invesco_api",
        "url": "https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/QQQ/holdings/fund"
        "?idType=ticker&interval=monthly&productType=ETF",
        "issuer_page": "https://www.invesco.com/qqq-etf/en/about.html",
    },
    "XLG": {
        "kind": "invesco_api",
        "url": "https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/46137V233/holdings/fund"
        "?idType=cusip&productType=ETF",
        "issuer_page": "https://www.invesco.com/us/en/financial-products/etfs/invesco-sp-500-top-50-etf.html",
    },
}

NON_EQUITY_TICKERS = {"", "-", "CASH", "USD", "US DOLLAR", "U.S. DOLLAR"}


def load_env_local() -> None:
    if not ENV_LOCAL_PATH.exists():
        return
    for line in ENV_LOCAL_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def fetch_url(url: str, *, accept: str = "*/*", timeout: int = 30) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_invesco_api(url: str, referer: str | None) -> bytes:
    try:
        return fetch_url(url, accept="application/json, text/plain, */*")
    except urllib.error.HTTPError as exc:
        if exc.code != 406:
            raise

    curl_bin = shutil.which("curl.exe") or shutil.which("curl")
    if not curl_bin:
        raise RuntimeError("curl is required for Invesco API fallback requests")
    command = [
        curl_bin,
        "-L",
        "--http1.1",
        "-s",
        "-A",
        USER_AGENT,
        "-H",
        "Accept: application/json, text/plain, */*",
        "-H",
        "Origin: https://www.invesco.com",
    ]
    if referer:
        command.extend(["-H", f"Referer: {referer}"])
    command.append(url)
    completed = subprocess.run(command, capture_output=True, check=True, timeout=60)
    return completed.stdout


def normalize_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    ticker = ticker.replace("\u00a0", " ")
    ticker = re.sub(r"\s+", " ", ticker)
    return ticker


def yahoo_symbol(ticker: str) -> str:
    ticker = normalize_ticker(ticker)
    return ticker.replace(".", "-")


def is_equity_ticker(ticker: str) -> bool:
    ticker = normalize_ticker(ticker)
    if ticker in NON_EQUITY_TICKERS:
        return False
    if set(ticker) == {"-"}:
        return False
    if ticker.startswith(("USD ", "CASH ")):
        return False
    return bool(re.match(r"^[A-Z][A-Z0-9.\-]*$", ticker))


def parse_csv_rows(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    header_index = None
    for index, line in enumerate(lines):
        lower = line.lower()
        if "ticker" in lower and ("name" in lower or "holding" in lower or "weight" in lower):
            header_index = index
            break
    if header_index is None:
        raise ValueError("Could not find CSV holdings header row")
    reader = csv.DictReader(lines[header_index:])
    parsed: list[dict[str, str]] = []
    for row in reader:
        clean: dict[str, str] = {}
        for key, value in row.items():
            if key is None:
                continue
            if isinstance(value, list):
                value = ",".join(str(item) for item in value)
            clean[str(key).strip()] = str(value or "").strip()
        parsed.append(clean)
    return parsed


def read_xlsx_cells(raw: bytes) -> list[list[str]]:
    if raw.lstrip().startswith(b"<?xml"):
        return read_spreadsheetml_cells(raw)

    workbook = zipfile.ZipFile(io.BytesIO(raw))
    strings: list[str] = []
    if "xl/sharedStrings.xml" in workbook.namelist():
        root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
        namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for item in root.findall("a:si", namespace):
            strings.append("".join(text.text or "" for text in item.findall(".//a:t", namespace)))

    sheet_name = "xl/worksheets/sheet1.xml"
    if sheet_name not in workbook.namelist():
        candidates = [name for name in workbook.namelist() if name.startswith("xl/worksheets/sheet")]
        if not candidates:
            raise ValueError("No worksheet found in XLSX")
        sheet_name = candidates[0]

    root = ET.fromstring(workbook.read(sheet_name))
    namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: list[list[str]] = []
    for row in root.findall(".//a:row", namespace):
        positioned: dict[int, str] = {}
        for cell in row.findall("a:c", namespace):
            value = cell.find("a:v", namespace)
            text = "" if value is None else value.text or ""
            if cell.attrib.get("t") == "s" and text.isdigit():
                text = strings[int(text)]
            cell_ref = cell.attrib.get("r", "")
            match = re.match(r"([A-Z]+)", cell_ref)
            column = 0
            if match:
                column = 0
                for letter in match.group(1):
                    column = column * 26 + ord(letter) - ord("A") + 1
                column -= 1
            else:
                column = len(positioned)
            positioned[column] = text.strip()
        max_column = max(positioned.keys(), default=-1)
        values = [positioned.get(index, "") for index in range(max_column + 1)]
        if any(values):
            rows.append(values)
    return rows


def read_spreadsheetml_cells(raw: bytes) -> list[list[str]]:
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9A-Fa-f]+;)", "&amp;", text)
    root = ET.fromstring(text.encode("utf-8"))
    namespace = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
    rows: list[list[str]] = []
    for row in root.findall(".//ss:Row", namespace):
        values: list[str] = []
        for cell in row.findall("ss:Cell", namespace):
            index = cell.attrib.get("{urn:schemas-microsoft-com:office:spreadsheet}Index")
            if index and index.isdigit():
                while len(values) < int(index) - 1:
                    values.append("")
            data = cell.find("ss:Data", namespace)
            values.append("" if data is None or data.text is None else data.text.strip())
        if any(values):
            rows.append(values)
    return rows


def rows_from_xlsx(raw: bytes) -> list[dict[str, str]]:
    rows = read_xlsx_cells(raw)
    header_index = None
    for index, row in enumerate(rows):
        joined = " ".join(cell.lower() for cell in row)
        if "ticker" in joined and ("name" in joined or "weight" in joined):
            header_index = index
            break
    if header_index is None:
        raise ValueError("Could not find XLSX holdings header row")

    headers = [cell.strip() for cell in rows[header_index]]
    parsed: list[dict[str, str]] = []
    for row in rows[header_index + 1 :]:
        item = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        parsed.append(item)
    return parsed


def extract_tickers_from_rows(rows: list[dict[str, str]]) -> list[str]:
    tickers: list[str] = []
    ticker_keys = ("Ticker", "ticker", "Symbol", "symbol", "Trading Symbol", "Holding Ticker")
    for row in rows:
        ticker = ""
        for key in ticker_keys:
            if key in row and row[key].strip():
                ticker = row[key]
                break
        ticker = normalize_ticker(ticker)
        if is_equity_ticker(ticker):
            tickers.append(ticker)
    return sorted(dict.fromkeys(tickers))


def extract_nasdaq_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        for key in ("rows", "holdings", "data"):
            if key in value:
                rows = extract_nasdaq_rows(value[key])
                if rows:
                    return rows
        if any(key.lower() in {"symbol", "ticker"} for key in value):
            return [value]
        rows: list[dict[str, Any]] = []
        for child in value.values():
            rows.extend(extract_nasdaq_rows(child))
        return rows
    if isinstance(value, list):
        rows = []
        for item in value:
            rows.extend(extract_nasdaq_rows(item))
        return rows
    return []


def parse_nasdaq_holdings(raw: bytes) -> list[str]:
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    rows = extract_nasdaq_rows(payload)
    tickers: list[str] = []
    for row in rows:
        ticker = row.get("symbol") or row.get("ticker") or row.get("Symbol") or row.get("Ticker") or ""
        ticker = normalize_ticker(str(ticker))
        if is_equity_ticker(ticker):
            tickers.append(ticker)
    if not tickers:
        raise ValueError("Nasdaq holdings response did not include ticker rows")
    return sorted(dict.fromkeys(tickers))


def parse_invesco_holdings(raw: bytes) -> list[str]:
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    holdings = payload.get("holdings") or []
    tickers: list[str] = []
    for row in holdings:
        ticker = normalize_ticker(str(row.get("ticker") or ""))
        security_type = str(row.get("securityTypeCode") or "")
        if security_type in {"CURR", "CURRCOL", "SYN", "IFUT", "MMT", "UCURR"}:
            continue
        if is_equity_ticker(ticker):
            tickers.append(ticker)
    if not tickers:
        raise ValueError("Invesco holdings response did not include ticker rows")
    return sorted(dict.fromkeys(tickers))


def get_holdings(etf: str, run_date: str) -> tuple[list[str], dict[str, Any]]:
    source = HOLDING_URLS[etf]
    if source["kind"] == "invesco_api":
        raw = fetch_invesco_api(source["url"], source.get("issuer_page"))
    else:
        raw = fetch_url(source["url"])
    suffix = {"xlsx": "xlsx", "csv": "csv", "nasdaq_fallback": "json", "invesco_api": "json"}[source["kind"]]
    raw_path = RAW_DIR / "holdings" / f"{run_date}_{etf}_holdings.{suffix}"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw)

    if source["kind"] == "xlsx":
        tickers = extract_tickers_from_rows(rows_from_xlsx(raw))
    elif source["kind"] == "csv":
        tickers = extract_tickers_from_rows(parse_csv_rows(raw))
    elif source["kind"] == "nasdaq_fallback":
        tickers = parse_nasdaq_holdings(raw)
    else:
        tickers = parse_invesco_holdings(raw)

    return tickers, {
        "source_kind": source["kind"],
        "source_url": source["url"],
        "issuer_page": source.get("issuer_page"),
        "raw_path": str(raw_path.relative_to(ROOT)),
        "ticker_count": len(tickers),
    }


def get_tiingo_price(symbol: str, token: str) -> dict[str, Any]:
    end = dt.date.today()
    start = end - dt.timedelta(days=430)
    params = urllib.parse.urlencode(
        {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "resampleFreq": "daily",
            "token": token,
        }
    )
    url = f"https://api.tiingo.com/tiingo/daily/{urllib.parse.quote(symbol)}/prices?{params}"
    raw = fetch_url(url, accept="application/json")
    rows = json.loads(raw.decode("utf-8"))
    if not rows:
        raise ValueError("empty Tiingo price response")
    highs = [row.get("adjHigh") for row in rows if row.get("adjHigh") is not None]
    closes = [row.get("adjClose") for row in rows if row.get("adjClose") is not None]
    if not highs or not closes:
        raise ValueError("missing adjusted Tiingo price fields")
    return {
        "price_source": "tiingo",
        "latest": float(closes[-1]),
        "high_52w": float(max(highs[-252:])),
        "price_date": rows[-1].get("date", "")[:10],
    }


def get_yahoo_price(symbol: str) -> dict[str, Any]:
    yf_symbol = yahoo_symbol(symbol)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yf_symbol)}?range=430d&interval=1d"
    raw = fetch_url(url, accept="application/json")
    payload = json.loads(raw.decode("utf-8"))
    result = payload["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    quote = result["indicators"]["quote"][0]
    closes = quote.get("close") or []
    highs = quote.get("high") or []
    adj = (result["indicators"].get("adjclose") or [{}])[0].get("adjclose") or closes

    adjusted_highs: list[float] = []
    adjusted_closes: list[float] = []
    adjusted_dates: list[str] = []
    for ts, high, close, adj_close in zip(timestamps, highs, closes, adj):
        if high is None or close in (None, 0) or adj_close is None:
            continue
        factor = float(adj_close) / float(close)
        adjusted_highs.append(float(high) * factor)
        adjusted_closes.append(float(adj_close))
        adjusted_dates.append(dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat())
    if not adjusted_highs or not adjusted_closes:
        raise ValueError("missing Yahoo price fields")
    return {
        "price_source": "yahoo",
        "latest": adjusted_closes[-1],
        "high_52w": max(adjusted_highs[-252:]),
        "price_date": adjusted_dates[-1] if adjusted_dates else "",
    }


def get_price(symbol: str, tiingo_token: str | None, sleep_seconds: float) -> dict[str, Any]:
    if tiingo_token:
        try:
            result = get_tiingo_price(symbol, tiingo_token)
            if sleep_seconds:
                time.sleep(sleep_seconds)
            return result
        except Exception as exc:  # noqa: BLE001 - report and fall back.
            yahoo = get_yahoo_price(symbol)
            yahoo["price_source"] = "yahoo_after_tiingo_error"
            yahoo["tiingo_error"] = str(exc)
            return yahoo
    result = get_yahoo_price(symbol)
    if sleep_seconds:
        time.sleep(sleep_seconds)
    return result


def build_etf_result(
    etf: str,
    tickers: list[str],
    *,
    tiingo_token: str | None,
    price_cache: dict[tuple[str, str], dict[str, Any]],
    max_symbols: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    selected = tickers[:max_symbols] if max_symbols else tickers
    details: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    etf_tiingo_token = tiingo_token if etf in TIINGO_ETFS else None
    for ticker in selected:
        try:
            cache_source = "tiingo" if etf_tiingo_token else "yahoo"
            cache_key = (cache_source, ticker)
            if cache_key in price_cache:
                price = price_cache[cache_key]
            else:
                price = get_price(ticker, etf_tiingo_token, sleep_seconds)
                price_cache[cache_key] = price
            drawdown = price["latest"] / price["high_52w"] - 1
            details.append(
                {
                    "ticker": ticker,
                    "latest": round(price["latest"], 4),
                    "high_52w": round(price["high_52w"], 4),
                    "drawdown_pct": round(drawdown * 100, 2),
                    "technical_bear": drawdown <= -0.20,
                    "price_date": price["price_date"],
                    "price_source": price["price_source"],
                }
            )
        except Exception as exc:  # noqa: BLE001 - keep the run going.
            missing.append({"ticker": ticker, "error": str(exc)})

    valid = len(details)
    bear_count = sum(1 for row in details if row["technical_bear"])
    percent = (bear_count / valid * 100) if valid else None
    return {
        "etf": etf,
        "total_holdings": len(tickers),
        "checked_holdings": len(selected),
        "valid_prices": valid,
        "missing_prices": len(missing),
        "technical_bear_count": bear_count,
        "technical_bear_pct": round(percent, 2) if percent is not None else None,
        "details": details,
        "missing": missing,
    }


def write_outputs(summary: list[dict[str, Any]], log: dict[str, Any]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    run_date = log["run_date"]
    summary_path = DATA_DIR / "technical_bear_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    meta_path = DATA_DIR / "technical_bear_meta.json"
    meta = {
        "run_date": log["run_date"],
        "price_preference": log["price_preference"],
        "sleep_seconds": log["sleep_seconds"],
        "errors": log["errors"],
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    csv_path = DATA_DIR / "technical_bear_summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "etf",
                "technical_bear_pct",
                "technical_bear_count",
                "valid_prices",
                "missing_prices",
                "checked_holdings",
                "total_holdings",
            ],
        )
        writer.writeheader()
        for row in summary:
            writer.writerow({key: row.get(key) for key in writer.fieldnames})

    log_path = LOG_DIR / f"technical_bear_run_{run_date}.json"
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")


def main() -> int:
    load_env_local()
    parser = argparse.ArgumentParser()
    parser.add_argument("--etfs", nargs="+", default=["SPY", "QQQ", "IWM", "XLG"])
    parser.add_argument("--max-symbols", type=int, default=0, help="Limit symbols per ETF for smoke tests.")
    parser.add_argument("--sleep", type=float, default=0.1, help="Seconds between price requests.")
    parser.add_argument("--use-tiingo-prices", action="store_true", help="Use Tiingo prices for QQQ/XLG if a key exists.")
    parser.add_argument(
        "--tiingo-free-throttle",
        action="store_true",
        help="Use a 73-second delay between Tiingo requests, suitable for a 50 requests/hour free limit.",
    )
    args = parser.parse_args()

    run_date = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    tiingo_token = os.environ.get("TIINGO_API_KEY")
    if args.use_tiingo_prices and tiingo_token:
        TIINGO_ETFS.update({"QQQ", "XLG"})
    sleep_seconds = 73.0 if args.tiingo_free_throttle and tiingo_token else args.sleep
    price_cache: dict[tuple[str, str], dict[str, Any]] = {}
    log: dict[str, Any] = {
        "run_date": run_date,
        "price_preference": "tiingo_for_QQQ_XLG_else_yahoo" if TIINGO_ETFS and tiingo_token else "yahoo",
        "tiingo_etfs": sorted(TIINGO_ETFS) if tiingo_token else [],
        "sleep_seconds": sleep_seconds,
        "holdings": {},
        "errors": [],
    }
    summary: list[dict[str, Any]] = []

    for etf in args.etfs:
        try:
            tickers, source_meta = get_holdings(etf, run_date)
            log["holdings"][etf] = source_meta
            result = build_etf_result(
                etf,
                tickers,
                tiingo_token=tiingo_token,
                price_cache=price_cache,
                max_symbols=args.max_symbols,
                sleep_seconds=sleep_seconds,
            )
            summary.append(result)
        except Exception as exc:  # noqa: BLE001 - preserve partial run outputs.
            log["errors"].append({"etf": etf, "error": str(exc)})

    write_outputs(summary, log)
    print(json.dumps([{k: v for k, v in row.items() if k not in {"details", "missing"}} for row in summary], indent=2))
    if log["errors"]:
        print("Errors:", json.dumps(log["errors"], indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

const FALLBACK_DATA = [
  { etf: "SPY", technical_bear_pct: 35.39, technical_bear_count: 178, valid_prices: 503, missing_prices: 0, checked_holdings: 503, total_holdings: 503 },
  { etf: "QQQ", technical_bear_pct: 51.46, technical_bear_count: 53, valid_prices: 103, missing_prices: 0, checked_holdings: 103, total_holdings: 103 },
  { etf: "IWM", technical_bear_pct: 47.84, technical_bear_count: 942, valid_prices: 1969, missing_prices: 16, checked_holdings: 1985, total_holdings: 1985 },
  { etf: "XLG", technical_bear_pct: 30.0, technical_bear_count: 15, valid_prices: 50, missing_prices: 0, checked_holdings: 50, total_holdings: 50 }
];

const ETF_NAMES = {
  SPY: "S&P 500 ETF",
  QQQ: "Nasdaq-100 ETF",
  IWM: "Russell 2000 ETF",
  XLG: "S&P 500 Top 50 ETF"
};

function classify(value) {
  if (value >= 40) return { label: "High", key: "high" };
  if (value >= 30) return { label: "Elevated", key: "elevated" };
  if (value >= 15) return { label: "Moderate", key: "moderate" };
  return { label: "Low", key: "low" };
}

function pct(value) {
  return `${Number(value).toFixed(value % 1 === 0 ? 0 : 2)}%`;
}

function renderCards(rows) {
  const cards = document.getElementById("cards");
  cards.innerHTML = rows.map((row) => {
    const state = classify(row.technical_bear_pct);
    return `
      <article class="card">
        <div>
          <div class="card-head">
            <div>
              <div class="ticker">${row.etf}</div>
              <div class="card-name">${ETF_NAMES[row.etf] || "ETF basket"}</div>
            </div>
            <span class="badge ${state.key}">${state.label}</span>
          </div>
          <div class="reading ${state.key}">${pct(row.technical_bear_pct)}</div>
          <div class="mini-track" aria-hidden="true">
            <div class="mini-fill fill-${state.key}" style="width:${Math.min(row.technical_bear_pct, 100)}%"></div>
          </div>
        </div>
        <div class="card-foot">
          <span>${row.technical_bear_count.toLocaleString()} of ${row.valid_prices.toLocaleString()} valid constituents</span>
          <span>${row.missing_prices ? `${row.missing_prices} holdings missing price data` : "No missing price data"}</span>
        </div>
      </article>`;
  }).join("");
}

function renderBars(rows) {
  const bars = document.getElementById("bars");
  const sorted = [...rows].sort((a, b) => b.technical_bear_pct - a.technical_bear_pct);
  bars.innerHTML = sorted.map((row) => {
    const state = classify(row.technical_bear_pct);
    return `
      <div class="bar-row">
        <div class="bar-label">${row.etf}</div>
        <div class="bar-track" aria-label="${row.etf} ${pct(row.technical_bear_pct)}">
          <div class="bar-fill fill-${state.key}" style="width:${Math.min(row.technical_bear_pct, 100)}%"></div>
        </div>
        <div class="bar-value">${pct(row.technical_bear_pct)}</div>
      </div>`;
  }).join("");
}

function formatRunDate(raw) {
  if (!raw) return null;
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})(\d{2})$/);
  if (!match) return raw;
  const [, y, m, d, hh, mm, ss] = match;
  return `${y}-${m}-${d} ${hh}:${mm}:${ss}`;
}

function updateTimestamp(meta) {
  const stamp = document.getElementById("lastUpdated");
  const runDate = formatRunDate(meta?.run_date);
  stamp.textContent = runDate ? `Data snapshot: ${runDate}` : "Latest data snapshot";
}

async function loadData() {
  try {
    const response = await fetch("data/technical_bear_summary.json", { cache: "no-store" });
    if (!response.ok) throw new Error("Data request failed");
    const rows = await response.json();
    return rows.map(({ details, missing, ...summary }) => summary);
  } catch {
    return FALLBACK_DATA;
  }
}

async function loadMeta() {
  try {
    const response = await fetch("data/technical_bear_meta.json", { cache: "no-store" });
    if (!response.ok) throw new Error("Meta request failed");
    return await response.json();
  } catch {
    return null;
  }
}

Promise.all([loadData(), loadMeta()]).then(([rows, meta]) => {
  renderCards(rows);
  renderBars(rows);
  updateTimestamp(meta);
});

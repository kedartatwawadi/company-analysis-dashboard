const DATA_URL = "data/company_metrics_sample.csv";

const COMPANY_DOMAINS = {
  AAPL: "apple.com",
  ABBV: "abbvie.com",
  AMZN: "amazon.com",
  AVGO: "broadcom.com",
  BAC: "bankofamerica.com",
  COST: "costco.com",
  CVX: "chevron.com",
  GOOGL: "abc.xyz",
  JNJ: "jnj.com",
  JPM: "jpmorganchase.com",
  LLY: "lilly.com",
  MA: "mastercard.com",
  META: "meta.com",
  MSFT: "microsoft.com",
  MU: "micron.com",
  NFLX: "netflix.com",
  NVDA: "nvidia.com",
  ORCL: "oracle.com",
  PLTR: "palantir.com",
  TSLA: "tesla.com",
  V: "visa.com",
  WMT: "walmart.com",
  XOM: "exxonmobil.com"
};

const SANKEY_LINKS = {
  AAPL: "https://www.sankeyart.com/sankeys/public/157546/",
  AMZN: "https://www.sankeyart.com/sankeys/public/158371/",
  GOOGL: "https://www.sankeyart.com/sankeys/public/158274/",
  BRK_B: "https://www.sankeyart.com/sankeys/public/137950/",
  LLY: "https://www.sankeyart.com/sankeys/public/138630/",
  XOM: "https://www.sankeyart.com/sankeys/public/137947/",
  JPM: "https://www.sankeyart.com/sankeys/public/155735/",
  JNJ: "https://www.sankeyart.com/sankeys/public/135405/",
  META: "https://www.sankeyart.com/sankeys/public/149171/",
  MSFT: "https://www.sankeyart.com/sankeys/public/157428/",
  NVDA: "https://www.sankeyart.com/sankeys/public/160800/",
  NFLX: "https://www.sankeyart.com/sankeys/public/156598/",
  TSLA: "https://www.sankeyart.com/sankeys/public/157426/",
  V: "https://www.sankeyart.com/sankeys/public/157557/",
  WMT: "https://www.sankeyart.com/sankeys/public/159645/"
};

const METRICS = [
  ["Revenue", "Latest annual sales reported in SEC filings."],
  ["Profit", "Latest annual net income after expenses, taxes, and other items."],
  ["Net profit margin", "Profit divided by revenue. It shows how much of each sales dollar becomes profit."],
  ["Revenue growth", "Year-over-year change in annual revenue."],
  ["Profit growth", "Year-over-year change in annual profit."],
  ["Annual P/E", "Stock price divided by latest annual diluted EPS."],
  ["TTM P/E", "Stock price divided by trailing-twelve-month diluted EPS when cleanly available."],
  ["Forward P/E", "Stock price divided by expected next-year EPS. This needs analyst estimate data."],
  ["Free cash flow", "Operating cash flow minus capital expenditures."],
  ["Free cash flow yield", "Free cash flow divided by market capitalization."],
  ["Enterprise value", "Market capitalization plus debt minus cash."],
  ["EV/EBITDA", "Enterprise value divided by EBITDA. Less useful for banks and insurers."],
  ["Cost of revenue", "Direct costs required to produce goods or services sold."],
  ["Gross profit", "Revenue minus cost of revenue."],
  ["Operating expenses", "Costs such as research, sales, marketing, and administration."],
  ["Operating profit", "Gross profit minus operating expenses."],
  ["Tax", "Income taxes paid or accrued."],
  ["Net profit", "Final profit after all expenses, taxes, and other items."]
];

const state = {
  rows: [],
  filtered: [],
  sortKey: "revenue",
  direction: "desc",
  revenueMin: 0,
  search: "",
  charts: {}
};

function parseCSV(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];
    if (quoted) {
      if (char === '"' && next === '"') {
        field += '"';
        i += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (char !== "\r") {
      field += char;
    }
  }
  if (field.length || row.length) {
    row.push(field);
    rows.push(row);
  }
  const headers = rows.shift() || [];
  return rows.filter((item) => item.length === headers.length).map((item) => {
    const output = {};
    headers.forEach((header, index) => {
      output[header] = item[index];
    });
    return output;
  });
}

function numeric(value) {
  if (value === undefined || value === null || value === "") return null;
  const parsed = Number(String(value).replace(/[$,%]/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function money(value) {
  const parsed = numeric(value);
  if (parsed === null) return "Not available";
  const abs = Math.abs(parsed);
  if (abs >= 1e12) return `$${(parsed / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `$${(parsed / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(parsed / 1e6).toFixed(1)}M`;
  return `$${parsed.toLocaleString()}`;
}

function ratio(value) {
  const parsed = numeric(value);
  return parsed === null ? "Not available" : parsed.toFixed(2);
}

function pct(value) {
  const parsed = numeric(value);
  return parsed === null ? "Not available" : `${parsed.toFixed(1)}%`;
}

function tickerKey(ticker) {
  return String(ticker || "").replace("-", "_").replace(".", "_").toUpperCase();
}

function sortRows(rows) {
  const direction = state.direction === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = numeric(a[state.sortKey]);
    const bv = numeric(b[state.sortKey]);
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    return (av - bv) * direction;
  });
}

function applyFilters() {
  const term = state.search.trim().toLowerCase();
  state.filtered = sortRows(state.rows.filter((row) => {
    const revenue = numeric(row.revenue) || 0;
    const matchesSearch = !term || `${row.ticker} ${row.company}`.toLowerCase().includes(term);
    return matchesSearch && revenue >= state.revenueMin;
  }));
  renderAll();
}

function median(values) {
  const clean = values.map(numeric).filter((value) => value !== null).sort((a, b) => a - b);
  if (!clean.length) return null;
  const middle = Math.floor(clean.length / 2);
  return clean.length % 2 ? clean[middle] : (clean[middle - 1] + clean[middle]) / 2;
}

function renderSummary() {
  const totalRevenue = state.filtered.reduce((sum, row) => sum + (numeric(row.revenue) || 0), 0);
  const totalProfit = state.filtered.reduce((sum, row) => sum + (numeric(row.profit) || 0), 0);
  document.getElementById("companyCount").textContent = state.filtered.length;
  document.getElementById("totalRevenue").textContent = money(totalRevenue);
  document.getElementById("totalProfit").textContent = money(totalProfit);
  document.getElementById("medianPe").textContent = ratio(median(state.filtered.map((row) => row.annual_pe_ratio)));
}

function renderTable() {
  const body = document.getElementById("companyTableBody");
  body.innerHTML = "";
  state.filtered.forEach((row) => {
    const tr = document.createElement("tr");
    tr.tabIndex = 0;
    tr.innerHTML = `
      <td><span class="ticker-pill">${row.ticker}</span></td>
      <td>${row.company}</td>
      <td>${money(row.revenue)}</td>
      <td>${money(row.profit)}</td>
      <td>${pct(row.net_profit_margin_pct)}</td>
      <td>${ratio(row.annual_pe_ratio)}</td>
      <td>${ratio(row.ttm_pe_ratio)}</td>
      <td>${pct(row.free_cash_flow_yield_pct)}</td>
    `;
    tr.addEventListener("click", () => openDrawer(row));
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter") openDrawer(row);
    });
    body.appendChild(tr);
  });
}

function chartColors(count) {
  const palette = ["#0f766e", "#b42318", "#3858a8", "#8a5a12", "#287245", "#6f4e9b"];
  return Array.from({ length: count }, (_, index) => palette[index % palette.length]);
}

function replaceChart(name, config) {
  if (state.charts[name]) state.charts[name].destroy();
  state.charts[name] = new Chart(document.getElementById(name), config);
}

function renderCharts() {
  if (!window.Chart) return;
  const top = state.filtered.slice(0, 10);
  replaceChart("revenueChart", {
    type: "bar",
    data: {
      labels: top.map((row) => row.ticker),
      datasets: [{ label: "Revenue ($B)", data: top.map((row) => (numeric(row.revenue) || 0) / 1e9), backgroundColor: chartColors(top.length) }]
    },
    options: { responsive: true, plugins: { legend: { display: false } } }
  });
  const scatterRows = state.filtered.filter((row) => numeric(row.net_profit_margin_pct) !== null && numeric(row.annual_pe_ratio) !== null);
  replaceChart("scatterChart", {
    type: "scatter",
    data: {
      datasets: [{ label: "Companies", data: scatterRows.map((row) => ({ x: numeric(row.annual_pe_ratio), y: numeric(row.net_profit_margin_pct), ticker: row.ticker })), backgroundColor: "#0f766e" }]
    },
    options: {
      responsive: true,
      parsing: false,
      scales: { x: { title: { display: true, text: "Annual P/E" } }, y: { title: { display: true, text: "Net margin %" } } },
      plugins: { tooltip: { callbacks: { label: (ctx) => `${ctx.raw.ticker}: P/E ${ctx.raw.x.toFixed(1)}, margin ${ctx.raw.y.toFixed(1)}%` } } }
    }
  });
  replaceChart("growthChart", {
    type: "bar",
    data: {
      labels: top.map((row) => row.ticker),
      datasets: [
        { label: "Revenue growth %", data: top.map((row) => numeric(row.revenue_growth_pct)), backgroundColor: "#3858a8" },
        { label: "Profit growth %", data: top.map((row) => numeric(row.profit_growth_pct)), backgroundColor: "#b42318" }
      ]
    },
    options: { responsive: true }
  });
}

function metricCard(label, value, hint) {
  return `<article class="metric-card"><strong>${value}</strong><span title="${hint}">${label}</span></article>`;
}

function openDrawer(row) {
  const drawer = document.getElementById("detailDrawer");
  const backdrop = document.getElementById("drawerBackdrop");
  const logo = document.getElementById("companyLogo");
  const domain = COMPANY_DOMAINS[row.ticker];
  logo.src = domain ? `https://logo.clearbit.com/${domain}` : "";
  logo.alt = domain ? `${row.company} logo` : "";
  document.getElementById("drawerTicker").textContent = `${row.ticker} • ${row.exchange || "Exchange unavailable"}`;
  document.getElementById("drawerCompany").textContent = row.company;
  document.getElementById("drawerPeriod").textContent = `Annual period ${row.annual_period_start || "?"} to ${row.annual_period_end || "?"}`;
  document.getElementById("drawerMetrics").innerHTML = [
    metricCard("Revenue", money(row.revenue), "Latest annual sales from SEC filings."),
    metricCard("Profit", money(row.profit), "Latest annual net income from SEC filings."),
    metricCard("Net margin", pct(row.net_profit_margin_pct), "Profit divided by revenue."),
    metricCard("Revenue growth", pct(row.revenue_growth_pct), "Annual revenue growth versus prior year."),
    metricCard("Annual P/E", ratio(row.annual_pe_ratio), "Price divided by annual diluted EPS."),
    metricCard("TTM P/E", ratio(row.ttm_pe_ratio), "Price divided by trailing twelve month diluted EPS."),
    metricCard("FCF yield", pct(row.free_cash_flow_yield_pct), "Free cash flow divided by market cap."),
    metricCard("EV/EBITDA", ratio(row.ev_to_ebitda), "Enterprise value divided by EBITDA.")
  ].join("");
  const sankey = SANKEY_LINKS[tickerKey(row.ticker)];
  document.getElementById("sankeyStatus").innerHTML = sankey
    ? `<a class="sankey-link" href="${sankey}" target="_blank" rel="noopener">Open ${row.ticker} SankeyArt diagram</a>`
    : `<span class="missing">No SankeyArt link found yet.</span>`;
  document.getElementById("sourceTags").innerHTML = `
    <dt>Revenue</dt><dd>${row.revenue_tag || "Not available"}</dd>
    <dt>Profit</dt><dd>${row.profit_tag || "Not available"}</dd>
    <dt>EPS</dt><dd>${row.eps_tag || "Not available"}</dd>
    <dt>Filed</dt><dd>${row.revenue_filed || "Not available"}</dd>
  `;
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  backdrop.hidden = false;
}

function closeDrawer() {
  const drawer = document.getElementById("detailDrawer");
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
  document.getElementById("drawerBackdrop").hidden = true;
}

function renderGlossary() {
  const grid = document.getElementById("glossaryGrid");
  grid.innerHTML = METRICS.map(([term, definition]) => `<article class="glossary-item"><strong>${term}</strong><p>${definition}</p></article>`).join("");
}

function renderAll() {
  renderSummary();
  renderTable();
  renderCharts();
}

function loadRows(rows, name) {
  state.rows = rows;
  document.getElementById("datasetName").textContent = name;
  document.getElementById("datasetMeta").textContent = `${rows.length} rows loaded`;
  applyFilters();
}

async function loadDefaultData() {
  const response = await fetch(DATA_URL);
  const text = await response.text();
  loadRows(parseCSV(text), "Bundled sample CSV");
}

function bindControls() {
  document.getElementById("searchInput").addEventListener("input", (event) => {
    state.search = event.target.value;
    applyFilters();
  });
  document.getElementById("sortSelect").addEventListener("change", (event) => {
    state.sortKey = event.target.value;
    applyFilters();
  });
  document.getElementById("directionSelect").addEventListener("change", (event) => {
    state.direction = event.target.value;
    applyFilters();
  });
  document.getElementById("revenueFilter").addEventListener("change", (event) => {
    state.revenueMin = Number(event.target.value);
    applyFilters();
  });
  document.getElementById("csvInput").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const text = await file.text();
    loadRows(parseCSV(text), file.name);
  });
  document.getElementById("closeDrawer").addEventListener("click", closeDrawer);
  document.getElementById("drawerBackdrop").addEventListener("click", closeDrawer);
}

document.addEventListener("DOMContentLoaded", () => {
  renderGlossary();
  bindControls();
  loadDefaultData();
});

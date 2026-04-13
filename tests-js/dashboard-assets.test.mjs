import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const index = readFileSync("docs/index.html", "utf8");
const js = readFileSync("docs/dashboard.js", "utf8");
const metrics = readFileSync("METRICS.md", "utf8");

test("dashboard references required assets", () => {
  assert.match(index, /href="styles\.css"/);
  assert.match(index, /src="dashboard\.js"/);
  assert.match(index, /chart\.umd\.min\.js/);
  assert.match(js, /data\/company_metrics_sample\.csv/);
});

test("dashboard exposes core interactive components", () => {
  [
    "searchInput",
    "sortSelect",
    "directionSelect",
    "revenueFilter",
    "csvInput",
    "companyTable",
    "revenueChart",
    "scatterChart",
    "growthChart",
    "detailDrawer",
    "metricGlossary"
  ].forEach((id) => assert.ok(index.includes(`id="${id}"`), id));
});

test("metric definitions are present in docs and dashboard glossary", () => {
  [
    "Revenue",
    "Profit",
    "Net profit margin",
    "Revenue growth",
    "Profit growth",
    "Annual P/E",
    "TTM P/E",
    "Forward P/E",
    "Free cash flow",
    "Free cash flow yield",
    "Enterprise value",
    "EV/EBITDA"
  ].forEach((term) => {
    assert.ok(metrics.includes(term), term);
    assert.ok(js.includes(term), term);
  });
});

test("known SankeyArt links are mapped", () => {
  const expected = {
    AAPL: "https://www.sankeyart.com/sankeys/public/157546/",
    AMZN: "https://www.sankeyart.com/sankeys/public/158371/",
    GOOGL: "https://www.sankeyart.com/sankeys/public/158274/",
    JPM: "https://www.sankeyart.com/sankeys/public/155735/",
    NVDA: "https://www.sankeyart.com/sankeys/public/160800/",
    WMT: "https://www.sankeyart.com/sankeys/public/159645/"
  };
  Object.entries(expected).forEach(([ticker, url]) => {
    assert.match(js, new RegExp(`${ticker}: "${url.replaceAll("/", "\\/")}"`));
  });
});

test("no local caches or token prefixes are embedded", () => {
  const combined = `${index}\n${js}`;
  assert.ok(!combined.includes(".cache/companyfacts"));
  assert.ok(!combined.includes("gho_"));
  assert.ok(!combined.includes("FMP_API_KEY="));
  assert.ok(!combined.includes("SEC_USER_AGENT="));
});

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const csv = readFileSync("docs/data/company_metrics_sample.csv", "utf8");

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const headers = lines.shift().split(",");
  return lines.map((line) => {
    const cells = line.split(",");
    return Object.fromEntries(headers.map((header, index) => [header, cells[index] ?? ""]));
  });
}

function number(value) {
  if (value === "") return null;
  const parsed = Number(String(value).replace(/[$,%]/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

const rows = parseCsv(csv);
const byTicker = Object.fromEntries(rows.map((row) => [row.ticker, row]));

test("sample CSV has required dashboard columns", () => {
  [
    "ticker",
    "company",
    "revenue",
    "profit",
    "net_profit_margin_pct",
    "revenue_growth_pct",
    "profit_growth_pct",
    "annual_pe_ratio",
    "ttm_pe_ratio",
    "forward_pe_ratio",
    "forward_eps",
    "free_cash_flow_yield_pct",
    "ev_to_ebitda"
  ].forEach((column) => assert.ok(column in rows[0], column));
});

test("sample CSV is sorted by revenue descending", () => {
  const sorted = [...rows].sort((a, b) => number(b.revenue) - number(a.revenue));
  assert.deepEqual(rows.map((row) => row.ticker), sorted.map((row) => row.ticker));
});

test("known corrected values stay stable", () => {
  assert.equal(number(byTicker.NVDA.revenue), 215_938_000_000);
  assert.equal(byTicker.NVDA.annual_period_end, "2026-01-25");
  assert.ok(Math.abs(number(byTicker.WMT.annual_pe_ratio) - 46.44) < 0.01);
});

test("core formulas match current data", () => {
  ["AMZN", "WMT", "NVDA"].forEach((ticker) => {
    const row = byTicker[ticker];
    const margin = number(row.profit) / number(row.revenue) * 100;
    const pe = number(row.stock_price) / number(row.diluted_eps);
    assert.ok(Math.abs(number(row.net_profit_margin_pct) - margin) < 0.001);
    assert.ok(Math.abs(number(row.annual_pe_ratio) - pe) < 0.001);
  });
});

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const csv = readFileSync("docs/data/company_metrics_sample.csv", "utf8");

function parseCsv(text) {
  const records = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (quoted) {
      if (char === '"' && next === '"') {
        field += '"';
        index += 1;
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
      records.push(row);
      row = [];
      field = "";
    } else if (char !== "\r") {
      field += char;
    }
  }
  if (field.length || row.length) {
    row.push(field);
    records.push(row);
  }
  const headers = records.shift();
  return records
    .filter((record) => record.length === headers.length)
    .map((record) => Object.fromEntries(headers.map((header, index) => [header, record[index] ?? ""])));
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

import csv
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "docs" / "data" / "company_metrics_sample.csv"


def rows():
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def number(value):
    if value in ("", None):
        return None
    return float(str(value).replace("$", "").replace(",", "").replace("%", ""))


class DashboardDataTests(unittest.TestCase):
    def setUp(self):
        self.rows = rows()
        self.by_ticker = {row["ticker"]: row for row in self.rows}

    def test_csv_has_required_columns(self):
        required = {
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
            "free_cash_flow",
            "free_cash_flow_yield_pct",
            "enterprise_value",
            "ev_to_ebitda",
            "annual_period_start",
            "annual_period_end",
            "revenue_tag",
            "profit_tag",
            "eps_tag",
        }
        self.assertTrue(required.issubset(self.rows[0].keys()))

    def test_numeric_parser_handles_common_dashboard_values(self):
        self.assertEqual(number(""), None)
        self.assertEqual(number("-12.5"), -12.5)
        self.assertEqual(number("46.44"), 46.44)
        self.assertEqual(number("$215,938,000,000"), 215_938_000_000)
        self.assertEqual(number("55.6%"), 55.6)

    def test_revenue_sorting_descending(self):
        sorted_rows = sorted(self.rows, key=lambda row: number(row["revenue"]) or 0, reverse=True)
        self.assertEqual([row["ticker"] for row in self.rows], [row["ticker"] for row in sorted_rows])
        self.assertEqual(self.rows[0]["ticker"], "AMZN")

    def test_metric_formulas_match_sample_rows(self):
        for ticker in ("AMZN", "WMT", "NVDA"):
            row = self.by_ticker[ticker]
            revenue = number(row["revenue"])
            profit = number(row["profit"])
            price = number(row["stock_price"])
            eps = number(row["diluted_eps"])
            market_cap = price * (number(row["shares_outstanding"]) or number(row["weighted_avg_diluted_shares"]))
            self.assertAlmostEqual(number(row["net_profit_margin_pct"]), profit / revenue * 100, places=3)
            self.assertAlmostEqual(number(row["annual_pe_ratio"]), price / eps, places=3)
            if row["free_cash_flow_yield_pct"]:
                self.assertAlmostEqual(
                    number(row["free_cash_flow_yield_pct"]),
                    number(row["free_cash_flow"]) / market_cap * 100,
                    places=3,
                )

    def test_nvda_latest_annual_revenue_is_current_period(self):
        nvda = self.by_ticker["NVDA"]
        self.assertEqual(number(nvda["revenue"]), 215_938_000_000)
        self.assertEqual(number(nvda["profit"]), 120_067_000_000)
        self.assertEqual(nvda["annual_period_start"], "2025-01-27")
        self.assertEqual(nvda["annual_period_end"], "2026-01-25")

    def test_wmt_annual_pe_is_high_but_expected(self):
        wmt = self.by_ticker["WMT"]
        self.assertAlmostEqual(number(wmt["annual_pe_ratio"]), 46.44, places=2)
        self.assertAlmostEqual(number(wmt["stock_price"]) / number(wmt["diluted_eps"]), 46.44, places=2)


if __name__ == "__main__":
    unittest.main()

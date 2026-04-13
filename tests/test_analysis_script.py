import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_us_public_companies.py"
SPEC = importlib.util.spec_from_file_location("analysis_script", SCRIPT)
analysis = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = analysis
SPEC.loader.exec_module(analysis)


def fact(value, start, end, filed="2026-02-25", form="10-K", fp="FY"):
    return {
        "val": value,
        "start": start,
        "end": end,
        "filed": filed,
        "form": form,
        "fp": fp,
        "fy": 2026,
    }


class AnalysisScriptTests(unittest.TestCase):
    def test_latest_annual_fact_uses_latest_period_end_not_stale_comparative(self):
        facts = {
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [
                                fact(60_922_000_000, "2023-01-30", "2024-01-28"),
                                fact(130_497_000_000, "2024-01-29", "2025-01-26"),
                                fact(215_938_000_000, "2025-01-27", "2026-01-25"),
                            ]
                        }
                    }
                }
            }
        }
        selected = analysis.latest_annual_fact(facts, ["Revenues"])
        self.assertEqual(selected.value, 215_938_000_000)
        self.assertEqual(selected.end, "2026-01-25")

    def test_annual_period_duration_filter_accepts_annual_rejects_quarter(self):
        facts = {
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [
                                fact(10, "2026-01-01", "2026-03-31", form="10-Q", fp="Q1"),
                                fact(40, "2025-01-01", "2025-12-31"),
                            ]
                        }
                    }
                }
            }
        }
        values = list(analysis.iter_tag_values(facts, "Revenues", units=("USD",)))
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].value, 40)
        self.assertEqual(analysis.period_days("2025-01-01", "2025-12-31"), 365)
        self.assertEqual(analysis.period_days("2026-01-01", "2026-03-31"), 90)

    def test_ttm_eps_requires_four_clean_quarters(self):
        clean = [
            analysis.FactValue(1, 2026, "Q1", "10-Q", "2026-05-01", None, "EPS", "us-gaap", "2025-01-01", "2025-03-31"),
            analysis.FactValue(2, 2026, "Q2", "10-Q", "2026-08-01", None, "EPS", "us-gaap", "2025-04-01", "2025-06-30"),
            analysis.FactValue(3, 2026, "Q3", "10-Q", "2026-11-01", None, "EPS", "us-gaap", "2025-07-01", "2025-09-30"),
            analysis.FactValue(4, 2026, "Q4", "10-K", "2027-02-01", None, "EPS", "us-gaap", "2025-10-01", "2025-12-31"),
        ]
        value, period = analysis.latest_ttm_sum(clean)
        self.assertEqual(value, 10)
        self.assertEqual(period, "2025-01-01_to_2025-12-31")
        broken = clean[:3] + [
            analysis.FactValue(4, 2026, "Q4", "10-K", "2027-02-01", None, "EPS", "us-gaap", "2026-02-01", "2026-04-30")
        ]
        value, period = analysis.latest_ttm_sum(broken)
        self.assertIsNone(value)
        self.assertEqual(period, "")

    def test_sp500_ticker_normalization_preserves_hyphenated_share_classes(self):
        self.assertEqual(analysis.normalize_ticker("BRK.B"), "BRK-B")
        self.assertEqual(analysis.normalize_ticker("BF-B"), "BF-B")
        companies = [
            analysis.Company(1, "Berkshire", "BRK-B", "NYSE"),
            analysis.Company(2, "Brown Forman", "BF-B", "NYSE"),
        ]
        sp500 = {"BRK-B", "BF-B"}
        kept = [company for company in companies if analysis.normalize_ticker(company.ticker) in sp500]
        self.assertEqual([company.ticker for company in kept], ["BRK-B", "BF-B"])


if __name__ == "__main__":
    unittest.main()

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "docs" / "dashboard.js").read_text(encoding="utf-8")
METRICS = (ROOT / "METRICS.md").read_text(encoding="utf-8")


class DashboardAssetTests(unittest.TestCase):
    def test_index_references_required_assets(self):
        self.assertIn('href="styles.css"', INDEX)
        self.assertIn('src="dashboard.js"', INDEX)
        self.assertIn("chart.umd.min.js", INDEX)
        self.assertIn("data/company_metrics_sample.csv", JS)

    def test_dashboard_contains_required_components(self):
        for element_id in [
            "searchInput",
            "sortSelect",
            "revenueFilter",
            "csvInput",
            "companyTable",
            "revenueChart",
            "scatterChart",
            "growthChart",
            "detailDrawer",
            "metricGlossary",
            "glossaryGrid",
        ]:
            self.assertIn(f'id="{element_id}"', INDEX)

    def test_metric_glossary_has_core_metrics(self):
        for term in [
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
            "EV/EBITDA",
        ]:
            self.assertIn(term, METRICS)
            self.assertIn(term, JS)

    def test_sankey_links_map_known_sample_companies(self):
        expected = {
            "AAPL": "https://www.sankeyart.com/sankeys/public/157546/",
            "AMZN": "https://www.sankeyart.com/sankeys/public/158371/",
            "GOOGL": "https://www.sankeyart.com/sankeys/public/158274/",
            "JPM": "https://www.sankeyart.com/sankeys/public/155735/",
            "NVDA": "https://www.sankeyart.com/sankeys/public/160800/",
            "WMT": "https://www.sankeyart.com/sankeys/public/159645/",
        }
        for ticker, url in expected.items():
            self.assertRegex(JS, rf"{ticker}: \"{re.escape(url)}\"")

    def test_no_cache_paths_or_secret_names_are_embedded(self):
        combined = INDEX + JS
        self.assertNotIn(".cache/companyfacts", combined)
        self.assertNotIn("gho_", combined)
        self.assertNotIn("FMP_API_KEY=", combined)
        self.assertNotIn("SEC_USER_AGENT=", combined)

    def test_company_logo_images_are_present(self):
        self.assertIn("<img", INDEX)
        self.assertIn("logo.clearbit.com", JS)


if __name__ == "__main__":
    unittest.main()

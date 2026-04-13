# US Public Company Revenue Analysis

Repeatable analysis of US-listed public companies sorted by latest annual revenue, with latest annual profit, stock price, annual P/E ratio, and net profit margin.

## Dashboard

Open the static dashboard at:

```text
docs/index.html
```

After GitHub Pages is enabled, the public site is expected at:

```text
https://kedartatwawadi.github.io/company-analysis-dashboard/
```

The dashboard loads `docs/data/company_metrics_sample.csv` by default and can load another CSV from your machine, such as a future S&P 500 output.

## Data Sources

- **Company universe and fundamentals:** SEC EDGAR APIs
  - Company list: `https://www.sec.gov/files/company_tickers_exchange.json`
  - Company facts: `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`
- **S&P 500 universe:** Financial Modeling Prep
  - Constituents: `https://financialmodelingprep.com/stable/sp500-constituent`
  - Requires `FMP_API_KEY`.
- **Market data:** Stooq quote CSV API
  - Used for latest close price.
  - This does not require an API key, but it is not an official exchange feed. For production-grade market data, replace the quote provider in `scripts/analyze_us_public_companies.py` with a paid API such as Polygon, IEX Cloud, FactSet, Bloomberg, or Financial Modeling Prep.
- **P/E ratio:** calculated as `latest close price / SEC latest annual diluted EPS`, with a fallback to `latest close price * SEC shares outstanding / SEC latest annual NetIncomeLoss` when diluted EPS is unavailable.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Run A Small Test

```bash
python3 scripts/analyze_us_public_companies.py --limit 25 --output outputs/us_public_companies_sample.csv
```

## Run The Full Analysis

SEC company facts require one request per company, so the full run can take a while.

```bash
python3 scripts/analyze_us_public_companies.py --output outputs/us_public_companies_by_revenue.csv
```

## Run S&P 500 Only

```bash
export SEC_USER_AGENT='Your Name your.email@example.com'
export FMP_API_KEY='your_fmp_api_key'
python3 scripts/analyze_us_public_companies.py \
  --universe sp500 \
  --output outputs/sp500_companies_by_revenue.csv
```

The script writes:

- `outputs/us_public_companies_by_revenue.csv`
- `.cache/sec_company_tickers_exchange.json`
- `.cache/companyfacts/CIK##########.json`
- `.cache/stooq_quotes/*.csv`

Metric definitions are in `METRICS.md`.

## Test

```bash
python3 -m unittest discover -s tests
```

The repo also includes Node's built-in test runner behind `npm test` for environments with Node available:

```bash
npm test
```

## Useful Options

```bash
python3 scripts/analyze_us_public_companies.py \
  --exchanges Nasdaq NYSE "NYSE American" \
  --min-revenue 1000000000 \
  --output outputs/us_public_companies_over_1b.csv
```

Use `--refresh-cache` to re-download cached API responses.

## Notes

- Revenue and profit are pulled from the latest annual SEC facts, preferring 10-K filings and USD units.
- `annual_period_start` and `annual_period_end` show the annual period selected from the SEC fact observation. This matters because the latest 10-K often contains several comparative annual rows from prior years.
- Revenue tags vary across filers. The script checks several common XBRL tags, including `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`, and `SalesRevenueNet`.
- Profit is `NetIncomeLoss`.
- P/E is computed from Stooq close price and SEC diluted EPS. When diluted EPS is unavailable, it falls back to a market-cap/net-income calculation if possible. When price, EPS, shares, or positive net income is unavailable, the output leaves it blank.
- Profit/revenue percentage is reported as `net_profit_margin_pct`, also known as **net profit margin** or **net margin**.

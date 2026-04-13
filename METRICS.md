# Metrics In The CSV

This file defines the columns added for valuation and profitability analysis.

## Core Annual Fundamentals

### `revenue`

Latest annual revenue from SEC XBRL company facts. The script checks common revenue tags such as `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`, and `SalesRevenueNet`.

### `profit`

Latest annual net income from SEC tag `NetIncomeLoss`.

### `net_profit_margin_pct`

Human name: **Net profit margin**.

Profit as a percentage of revenue.

```text
net_profit_margin_pct = profit / revenue * 100
```

Also called **net margin** or **net profit margin**.

### `revenue_growth_pct`

Human name: **Revenue growth**.

Year-over-year revenue growth between the latest annual period and the prior annual period.

```text
revenue_growth_pct = (latest annual revenue - prior annual revenue) / prior annual revenue * 100
```

### `profit_growth_pct`

Human name: **Profit growth**.

Year-over-year net income growth between the latest annual period and the prior annual period.

```text
profit_growth_pct = (latest annual profit - prior annual profit) / abs(prior annual profit) * 100
```

## P/E Metrics

### `annual_pe_ratio`

Human name: **Annual P/E**.

Price divided by latest annual diluted EPS from SEC filings.

```text
annual_pe_ratio = stock_price / diluted_eps
```

This is clean and auditable, but it can be stale if the latest annual report is old.

### `ttm_pe_ratio`

Human name: **TTM P/E**.

Price divided by trailing-twelve-month diluted EPS.

```text
ttm_pe_ratio = stock_price / ttm_diluted_eps
```

When the latest annual filing is the freshest EPS data, `ttm_diluted_eps` equals latest annual diluted EPS. If newer quarterly EPS exists, the script only computes TTM from four clean quarter-duration observations. Otherwise it leaves this blank.

### `forward_pe_ratio`

Human name: **Forward P/E**.

Price divided by expected next-year EPS.

```text
forward_pe_ratio = stock_price / forward_eps
```

This requires analyst estimate data. The current script includes the column but leaves it blank because SEC filings and Stooq quotes do not provide forward EPS estimates.

## Cash Flow Metrics

### `free_cash_flow`

Human name: **Free cash flow**.

Operating cash flow minus capital expenditures.

```text
free_cash_flow = cash_flow_from_operations - capital_expenditures
```

The script uses SEC operating cash flow and common capex tags such as `PaymentsToAcquirePropertyPlantAndEquipment` and `PaymentsToAcquireProductiveAssets`.

### `free_cash_flow_yield_pct`

Human name: **Free cash flow yield**.

Free cash flow divided by market capitalization.

```text
free_cash_flow_yield_pct = free_cash_flow / market_cap * 100
```

Higher can mean the company generates more cash relative to its market value, but very high values can also reflect cyclicality, distress, or one-time cash-flow effects.

## Enterprise Value Metrics

### `enterprise_value`

Human name: **Enterprise value**.

Approximate company value including debt and excluding cash.

```text
enterprise_value = market_cap + total_debt - cash_and_equivalents
```

This is a best-effort calculation from SEC balance-sheet tags.

### `ev_to_ebitda`

Human name: **EV/EBITDA**.

Enterprise value divided by EBITDA.

```text
ev_to_ebitda = enterprise_value / ebitda
```

The script estimates EBITDA as:

```text
ebitda = operating income + depreciation and amortization
```

This works better for industrial and operating companies than for banks, insurers, and other financial companies. Treat blanks or odd values in financial companies as expected rather than errors.

## Audit Columns

### `annual_period_start`, `annual_period_end`

The annual period selected from the SEC observation. These are important because the latest 10-K often contains multiple comparative annual periods.

### `pe_ratio_method`

Shows whether P/E came from annual diluted EPS or a fallback calculation.

### `revenue_tag`, `profit_tag`, `eps_tag`

The exact SEC XBRL tags used for the row.

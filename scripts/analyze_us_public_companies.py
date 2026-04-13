#!/usr/bin/env python3
"""Analyze US-listed public companies by latest annual revenue.

The script uses SEC EDGAR for the company universe and filed fundamentals, then
adds current-ish market price and trailing P/E from a quote provider.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
from tqdm import tqdm


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FMP_SP500_URL = "https://financialmodelingprep.com/stable/sp500-constituent"
STOOQ_QUOTE_URL = "https://stooq.com/q/l/"

REVENUE_TAGS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueServicesNet",
    "SalesRevenueGoodsNet",
    "InterestAndDividendIncomeOperating",
]
PROFIT_TAGS = ["NetIncomeLoss"]
SHARE_TAGS = ["EntityCommonStockSharesOutstanding"]
WEIGHTED_DILUTED_SHARE_TAGS = ["WeightedAverageNumberOfDilutedSharesOutstanding"]
EPS_DILUTED_TAGS = ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"]
CASH_FLOW_FROM_OPERATIONS_TAGS = ["NetCashProvidedByUsedInOperatingActivities"]
CAPEX_TAGS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
]
OPERATING_INCOME_TAGS = ["OperatingIncomeLoss"]
DEPRECIATION_AMORTIZATION_TAGS = [
    "DepreciationDepletionAndAmortization",
    "DepreciationDepletionAndAmortizationExpense",
    "DepreciationAndAmortization",
]
CASH_TAGS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
]
CURRENT_DEBT_TAGS = [
    "LongTermDebtAndFinanceLeaseObligationsCurrent",
    "LongTermDebtCurrent",
    "ShortTermBorrowings",
    "ShortTermDebtCurrent",
]
NONCURRENT_DEBT_TAGS = [
    "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
    "LongTermDebtNoncurrent",
]
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
QUARTERLY_AND_ANNUAL_FORMS = ANNUAL_FORMS | {"10-Q", "10-Q/A"}
MIN_ANNUAL_PERIOD_DAYS = 300
MAX_ANNUAL_PERIOD_DAYS = 450
MIN_QUARTER_PERIOD_DAYS = 60
MAX_QUARTER_PERIOD_DAYS = 120


@dataclass(frozen=True)
class Company:
    cik: int
    name: str
    ticker: str
    exchange: str


@dataclass(frozen=True)
class FactValue:
    value: float
    fiscal_year: int | None
    fiscal_period: str | None
    form: str | None
    filed: str | None
    frame: str | None
    tag: str
    namespace: str
    start: str | None = None
    end: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="outputs/us_public_companies_by_revenue.csv")
    parser.add_argument("--cache-dir", default=".cache")
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("SEC_USER_AGENT"),
        help="Required by SEC. Example: 'Your Name your.email@example.com'. Can also use SEC_USER_AGENT.",
    )
    parser.add_argument("--limit", type=int, help="Limit companies for a smoke test.")
    parser.add_argument(
        "--universe",
        choices=["all-us", "sp500"],
        default="all-us",
        help="Company universe to analyze.",
    )
    parser.add_argument(
        "--fmp-api-key",
        default=os.environ.get("FMP_API_KEY"),
        help="Financial Modeling Prep API key. Required for --universe sp500. Can also use FMP_API_KEY.",
    )
    parser.add_argument(
        "--exchanges",
        nargs="*",
        default=["Nasdaq", "NYSE", "NYSE American"],
        help="Exchange names to include. Use an empty value only by editing the script default.",
    )
    parser.add_argument("--min-revenue", type=float, default=0.0)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--sec-sleep", type=float, default=0.12, help="Delay between SEC companyfacts calls.")
    return parser.parse_args()


def require_user_agent(user_agent: str | None) -> str:
    if user_agent:
        return user_agent
    print(
        "SEC requires a descriptive User-Agent. Set SEC_USER_AGENT or pass "
        "--user-agent 'Your Name your.email@example.com'.",
        file=sys.stderr,
    )
    raise SystemExit(2)


def get_json(
    url: str,
    cache_path: Path,
    *,
    headers: dict[str, str],
    refresh_cache: bool,
    params: dict[str, str] | None = None,
    timeout: int = 30,
) -> Any:
    if cache_path.exists() and not refresh_cache:
        with cache_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, headers=headers, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f)
    return payload


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def period_days(start: str | None, end: str | None) -> int | None:
    start_date = parse_date(start)
    end_date = parse_date(end)
    if not start_date or not end_date:
        return None
    return (end_date - start_date).days + 1


def normalize_ticker(ticker: str) -> str:
    return ticker.upper().replace(".", "-")


def load_companies(cache_dir: Path, headers: dict[str, str], refresh_cache: bool) -> list[Company]:
    payload = get_json(
        SEC_TICKERS_URL,
        cache_dir / "sec_company_tickers_exchange.json",
        headers=headers,
        refresh_cache=refresh_cache,
    )
    fields = payload["fields"]
    rows = payload["data"]
    field_index = {field: idx for idx, field in enumerate(fields)}
    return [
        Company(
            cik=int(row[field_index["cik"]]),
            name=str(row[field_index["name"]]),
            ticker=str(row[field_index["ticker"]]),
            exchange=str(row[field_index["exchange"]]),
        )
        for row in rows
    ]


def load_sp500_tickers(
    cache_dir: Path,
    headers: dict[str, str],
    refresh_cache: bool,
    fmp_api_key: str | None,
) -> set[str]:
    if not fmp_api_key:
        print(
            "--universe sp500 requires a Financial Modeling Prep API key. "
            "Set FMP_API_KEY or pass --fmp-api-key.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    payload = get_json(
        FMP_SP500_URL,
        cache_dir / "fmp_sp500_constituent.json",
        headers=headers,
        refresh_cache=refresh_cache,
        params={"apikey": fmp_api_key},
    )
    if not isinstance(payload, list):
        print("Unexpected FMP S&P 500 constituent response.", file=sys.stderr)
        raise SystemExit(1)

    tickers = {normalize_ticker(str(item.get("symbol", ""))) for item in payload}
    return {ticker for ticker in tickers if ticker}


def facts_for_company(
    company: Company,
    cache_dir: Path,
    headers: dict[str, str],
    refresh_cache: bool,
) -> dict[str, Any] | None:
    url = SEC_COMPANYFACTS_URL.format(cik=company.cik)
    cache_path = cache_dir / "companyfacts" / f"CIK{company.cik:010d}.json"
    try:
        return get_json(url, cache_path, headers=headers, refresh_cache=refresh_cache)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        print(f"Skipping {company.ticker}: SEC companyfacts returned {status}", file=sys.stderr)
        return None


def iter_tag_values(
    facts: dict[str, Any],
    tag: str,
    *,
    namespace: str = "us-gaap",
    units: tuple[str, ...] = ("USD",),
    annual_only: bool = True,
) -> Iterable[FactValue]:
    tag_data = facts.get("facts", {}).get(namespace, {}).get(tag)
    if not tag_data:
        return

    for unit_name in units:
        for item in tag_data.get("units", {}).get(unit_name, []):
            form = item.get("form")
            fp = item.get("fp")
            if annual_only and (form not in ANNUAL_FORMS or fp not in {"FY", None}):
                continue
            days = period_days(item.get("start"), item.get("end"))
            if annual_only and days is not None and not (
                MIN_ANNUAL_PERIOD_DAYS <= days <= MAX_ANNUAL_PERIOD_DAYS
            ):
                continue
            value = item.get("val")
            if value is None:
                continue
            yield FactValue(
                value=float(value),
                fiscal_year=item.get("fy"),
                fiscal_period=fp,
                form=form,
                filed=item.get("filed"),
                frame=item.get("frame"),
                tag=tag,
                namespace=namespace,
                start=item.get("start"),
                end=item.get("end"),
            )


def latest_annual_fact(facts: dict[str, Any], tags: list[str]) -> FactValue | None:
    return latest_annual_fact_with_units(facts, tags, ("USD",))


def latest_annual_fact_with_units(
    facts: dict[str, Any],
    tags: list[str],
    units: tuple[str, ...],
) -> FactValue | None:
    candidates: list[FactValue] = []
    for tag in tags:
        candidates.extend(iter_tag_values(facts, tag, namespace="us-gaap", units=units) or [])
    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: (
            item.end or "",
            item.filed or "",
            item.fiscal_year or 0,
            1 if item.form == "10-K" else 0,
        ),
    )


def annual_fact_series_with_units(
    facts: dict[str, Any],
    tags: list[str],
    units: tuple[str, ...],
) -> list[FactValue]:
    by_period_end: dict[str, FactValue] = {}
    for tag in tags:
        for item in iter_tag_values(facts, tag, namespace="us-gaap", units=units) or []:
            if not item.end:
                continue
            current = by_period_end.get(item.end)
            if current is None or (item.filed or "") > (current.filed or ""):
                by_period_end[item.end] = item
    return sorted(by_period_end.values(), key=lambda item: item.end or "")


def growth_pct(series: list[FactValue]) -> float | None:
    if len(series) < 2:
        return None
    current = series[-1].value
    previous = series[-2].value
    if previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100


def quarter_fact_series_with_units(
    facts: dict[str, Any],
    tags: list[str],
    units: tuple[str, ...],
) -> list[FactValue]:
    by_period_end: dict[str, FactValue] = {}
    for tag in tags:
        for item in iter_tag_values(
            facts,
            tag,
            namespace="us-gaap",
            units=units,
            annual_only=False,
        ) or []:
            days = period_days(item.start, item.end)
            if (
                item.form not in QUARTERLY_AND_ANNUAL_FORMS
                or days is None
                or not (MIN_QUARTER_PERIOD_DAYS <= days <= MAX_QUARTER_PERIOD_DAYS)
                or not item.end
            ):
                continue
            current = by_period_end.get(item.end)
            if current is None or (item.filed or "") > (current.filed or ""):
                by_period_end[item.end] = item
    return sorted(by_period_end.values(), key=lambda item: item.end or "")


def latest_ttm_sum(series: list[FactValue]) -> tuple[float | None, str]:
    if len(series) < 4:
        return None, ""
    latest_four = series[-4:]
    first_start = parse_date(latest_four[0].start)
    last_end = parse_date(latest_four[-1].end)
    if not first_start or not last_end:
        return None, ""
    total_days = (last_end - first_start).days + 1
    if not (MIN_ANNUAL_PERIOD_DAYS <= total_days <= MAX_ANNUAL_PERIOD_DAYS):
        return None, ""

    previous_end: date | None = None
    for item in latest_four:
        start = parse_date(item.start)
        end = parse_date(item.end)
        if not start or not end:
            return None, ""
        if previous_end and (start - previous_end).days > 8:
            return None, ""
        previous_end = end

    label = f"{latest_four[0].start}_to_{latest_four[-1].end}"
    return sum(item.value for item in latest_four), label


def latest_instant_fact_with_units(
    facts: dict[str, Any],
    tags: list[str],
    units: tuple[str, ...],
    namespace: str = "us-gaap",
) -> FactValue | None:
    candidates: list[FactValue] = []
    for tag in tags:
        candidates.extend(
            iter_tag_values(
                facts,
                tag,
                namespace=namespace,
                units=units,
                annual_only=False,
            )
            or []
        )
    candidates = [item for item in candidates if item.end]
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.end or "", item.filed or ""))


def latest_shares_outstanding(facts: dict[str, Any]) -> FactValue | None:
    candidates: list[FactValue] = []
    for tag in SHARE_TAGS:
        candidates.extend(
            iter_tag_values(
                facts,
                tag,
                namespace="dei",
                units=("shares",),
                annual_only=False,
            )
            or []
        )
    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: (
            item.filed or "",
            item.end or "",
            item.fiscal_year or 0,
        ),
    )


def value_or_none(fact: FactValue | None) -> float | None:
    return fact.value if fact else None


def sum_optional(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def stooq_symbol(ticker: str) -> str:
    return f"{ticker.lower().replace('.', '-')}.us"


def stooq_quotes(
    tickers: list[str],
    cache_dir: Path,
    headers: dict[str, str],
    refresh_cache: bool,
) -> dict[str, dict[str, Any]]:
    quotes: dict[str, dict[str, Any]] = {}

    for ticker in tqdm(tickers, desc="Fetching market quotes"):
        symbol = stooq_symbol(ticker)
        cache_path = cache_dir / "stooq_quotes" / f"{symbol}.csv"
        if cache_path.exists() and not refresh_cache:
            text = cache_path.read_text(encoding="utf-8")
        else:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            params = {"s": symbol, "f": "sd2t2ohlcv", "h": "", "e": "csv"}
            response = requests.get(STOOQ_QUOTE_URL, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            text = response.text
            cache_path.write_text(text, encoding="utf-8")

        try:
            parsed = list(csv.DictReader(io.StringIO(text)))
        except csv.Error as exc:
            print(f"Skipping quote {ticker}: could not parse Stooq CSV: {exc}", file=sys.stderr)
            continue
        if not parsed or parsed[0].get("Close") in {None, "N/D"}:
            continue
        quotes[ticker.upper()] = parsed[0]

    return quotes


def money(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.0f}"


def number(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.4f}"


def main() -> int:
    args = parse_args()
    user_agent = require_user_agent(args.user_agent)
    cache_dir = Path(args.cache_dir)
    output_path = Path(args.output)
    headers = {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }
    ticker_headers = {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
    }

    companies = load_companies(cache_dir, ticker_headers, args.refresh_cache)
    if args.universe == "sp500":
        sp500_tickers = load_sp500_tickers(
            cache_dir,
            {"User-Agent": user_agent, "Accept": "application/json"},
            args.refresh_cache,
            args.fmp_api_key,
        )
        companies = [company for company in companies if normalize_ticker(company.ticker) in sp500_tickers]
    if args.exchanges:
        allowed_exchanges = set(args.exchanges)
        companies = [company for company in companies if company.exchange in allowed_exchanges]
    companies = [company for company in companies if company.ticker]
    if args.universe != "sp500":
        companies = [company for company in companies if "-" not in company.ticker]
    if args.limit:
        companies = companies[: args.limit]

    rows: list[dict[str, Any]] = []
    run_timestamp = datetime.now(timezone.utc).isoformat()

    for company in tqdm(companies, desc="Fetching SEC fundamentals"):
        facts = facts_for_company(company, cache_dir, headers, args.refresh_cache)
        time.sleep(args.sec_sleep)
        if not facts:
            continue

        revenue = latest_annual_fact(facts, REVENUE_TAGS)
        profit = latest_annual_fact(facts, PROFIT_TAGS)
        diluted_eps = latest_annual_fact_with_units(facts, EPS_DILUTED_TAGS, ("USD/shares",))
        weighted_diluted_shares = latest_annual_fact_with_units(
            facts, WEIGHTED_DILUTED_SHARE_TAGS, ("shares",)
        )
        revenue_series = annual_fact_series_with_units(facts, REVENUE_TAGS, ("USD",))
        profit_series = annual_fact_series_with_units(facts, PROFIT_TAGS, ("USD",))
        quarterly_eps_series = quarter_fact_series_with_units(facts, EPS_DILUTED_TAGS, ("USD/shares",))
        ttm_eps, ttm_eps_period = latest_ttm_sum(quarterly_eps_series)
        cash_flow_from_operations = latest_annual_fact_with_units(
            facts, CASH_FLOW_FROM_OPERATIONS_TAGS, ("USD",)
        )
        capex = latest_annual_fact_with_units(facts, CAPEX_TAGS, ("USD",))
        operating_income = latest_annual_fact_with_units(facts, OPERATING_INCOME_TAGS, ("USD",))
        depreciation_amortization = latest_annual_fact_with_units(
            facts, DEPRECIATION_AMORTIZATION_TAGS, ("USD",)
        )
        cash = latest_instant_fact_with_units(facts, CASH_TAGS, ("USD",))
        current_debt = latest_instant_fact_with_units(facts, CURRENT_DEBT_TAGS, ("USD",))
        noncurrent_debt = latest_instant_fact_with_units(facts, NONCURRENT_DEBT_TAGS, ("USD",))
        shares = latest_shares_outstanding(facts)
        if not revenue or revenue.value < args.min_revenue:
            continue

        latest_quarter_end = parse_date(quarterly_eps_series[-1].end) if quarterly_eps_series else None
        annual_eps_end = parse_date(diluted_eps.end) if diluted_eps else None
        if (
            diluted_eps
            and annual_eps_end
            and (latest_quarter_end is None or annual_eps_end >= latest_quarter_end)
        ):
            ttm_eps = diluted_eps.value
            ttm_eps_period = f"{diluted_eps.start}_to_{diluted_eps.end}"

        free_cash_flow = (
            cash_flow_from_operations.value - capex.value
            if cash_flow_from_operations and capex
            else None
        )
        ebitda = (
            operating_income.value + depreciation_amortization.value
            if operating_income and depreciation_amortization
            else None
        )
        total_debt = sum_optional([value_or_none(current_debt), value_or_none(noncurrent_debt)])

        rows.append(
            {
                "ticker": company.ticker.upper(),
                "company": company.name,
                "exchange": company.exchange,
                "cik": f"{company.cik:010d}",
                "revenue": revenue.value,
                "profit": profit.value if profit else None,
                "net_profit_margin_pct": (
                    (profit.value / revenue.value) * 100 if profit and revenue.value else None
                ),
                "revenue_growth_pct": growth_pct(revenue_series),
                "profit_growth_pct": growth_pct(profit_series),
                "diluted_eps": diluted_eps.value if diluted_eps else None,
                "ttm_diluted_eps": ttm_eps,
                "ttm_eps_period": ttm_eps_period,
                "shares_outstanding": shares.value if shares else None,
                "weighted_avg_diluted_shares": (
                    weighted_diluted_shares.value if weighted_diluted_shares else None
                ),
                "free_cash_flow": free_cash_flow,
                "cash_flow_from_operations": value_or_none(cash_flow_from_operations),
                "capital_expenditures": value_or_none(capex),
                "ebitda": ebitda,
                "cash_and_equivalents": value_or_none(cash),
                "total_debt": total_debt,
                "fiscal_year": revenue.fiscal_year,
                "annual_period_start": revenue.start,
                "annual_period_end": revenue.end,
                "revenue_tag": revenue.tag,
                "profit_tag": profit.tag if profit else "",
                "eps_tag": diluted_eps.tag if diluted_eps else "",
                "shares_tag": shares.tag if shares else "",
                "revenue_form": revenue.form,
                "revenue_filed": revenue.filed,
                "stock_price": None,
                "pe_ratio": None,
                "annual_pe_ratio": None,
                "ttm_pe_ratio": None,
                "forward_pe_ratio": None,
                "forward_eps": None,
                "free_cash_flow_yield_pct": None,
                "enterprise_value": None,
                "ev_to_ebitda": None,
                "pe_ratio_method": "",
                "market_currency": "",
                "quote_time": "",
                "run_timestamp_utc": run_timestamp,
            }
        )

    quote_tickers = sorted({row["ticker"] for row in rows})
    quotes = stooq_quotes(
        quote_tickers,
        cache_dir,
        {"User-Agent": user_agent, "Accept": "text/csv"},
        args.refresh_cache,
    )

    for row in rows:
        quote = quotes.get(row["ticker"], {})
        close = quote.get("Close")
        price = float(close) if close not in {None, "N/D", ""} else None
        profit = row["profit"]
        shares = row["shares_outstanding"]
        weighted_shares = row["weighted_avg_diluted_shares"]
        diluted_eps = row["diluted_eps"]
        ttm_diluted_eps = row["ttm_diluted_eps"]
        row["stock_price"] = price
        if price is not None and diluted_eps and diluted_eps > 0:
            row["annual_pe_ratio"] = price / diluted_eps
            row["pe_ratio"] = row["annual_pe_ratio"]
            row["pe_ratio_method"] = "stock_price_divided_by_sec_annual_diluted_eps"
        elif price is not None and weighted_shares and profit and profit > 0:
            row["annual_pe_ratio"] = (price * weighted_shares) / profit
            row["pe_ratio"] = row["annual_pe_ratio"]
            row["pe_ratio_method"] = (
                "fallback_price_times_sec_weighted_avg_diluted_shares_divided_by_sec_net_income"
            )
        if price is not None and ttm_diluted_eps and ttm_diluted_eps > 0:
            row["ttm_pe_ratio"] = price / ttm_diluted_eps

        market_cap_shares = shares or weighted_shares
        market_cap = price * market_cap_shares if price is not None and market_cap_shares else None
        free_cash_flow = row["free_cash_flow"]
        if market_cap and free_cash_flow is not None:
            row["free_cash_flow_yield_pct"] = (free_cash_flow / market_cap) * 100
        if market_cap is not None:
            enterprise_value = market_cap
            if row["total_debt"] is not None:
                enterprise_value += row["total_debt"]
            if row["cash_and_equivalents"] is not None:
                enterprise_value -= row["cash_and_equivalents"]
            row["enterprise_value"] = enterprise_value
            if row["ebitda"] and row["ebitda"] > 0:
                row["ev_to_ebitda"] = enterprise_value / row["ebitda"]
        row["market_currency"] = "USD" if price is not None else ""
        row["quote_time"] = " ".join(part for part in [quote.get("Date"), quote.get("Time")] if part)

    rows.sort(key=lambda row: row["revenue"] or 0, reverse=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank_by_revenue",
        "ticker",
        "company",
        "exchange",
        "cik",
        "revenue",
        "profit",
        "net_profit_margin_pct",
        "revenue_growth_pct",
        "profit_growth_pct",
        "fiscal_year",
        "annual_period_start",
        "annual_period_end",
        "stock_price",
        "pe_ratio",
        "annual_pe_ratio",
        "ttm_pe_ratio",
        "forward_pe_ratio",
        "forward_eps",
        "pe_ratio_method",
        "diluted_eps",
        "ttm_diluted_eps",
        "ttm_eps_period",
        "shares_outstanding",
        "weighted_avg_diluted_shares",
        "free_cash_flow",
        "free_cash_flow_yield_pct",
        "cash_flow_from_operations",
        "capital_expenditures",
        "ebitda",
        "enterprise_value",
        "ev_to_ebitda",
        "cash_and_equivalents",
        "total_debt",
        "market_currency",
        "quote_time",
        "revenue_tag",
        "profit_tag",
        "eps_tag",
        "shares_tag",
        "revenue_form",
        "revenue_filed",
        "run_timestamp_utc",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            formatted = dict(row)
            formatted["rank_by_revenue"] = idx
            formatted["revenue"] = money(row["revenue"])
            formatted["profit"] = money(row["profit"])
            formatted["net_profit_margin_pct"] = number(row["net_profit_margin_pct"])
            formatted["revenue_growth_pct"] = number(row["revenue_growth_pct"])
            formatted["profit_growth_pct"] = number(row["profit_growth_pct"])
            formatted["diluted_eps"] = number(row["diluted_eps"])
            formatted["ttm_diluted_eps"] = number(row["ttm_diluted_eps"])
            formatted["shares_outstanding"] = money(row["shares_outstanding"])
            formatted["weighted_avg_diluted_shares"] = money(row["weighted_avg_diluted_shares"])
            formatted["free_cash_flow"] = money(row["free_cash_flow"])
            formatted["free_cash_flow_yield_pct"] = number(row["free_cash_flow_yield_pct"])
            formatted["cash_flow_from_operations"] = money(row["cash_flow_from_operations"])
            formatted["capital_expenditures"] = money(row["capital_expenditures"])
            formatted["ebitda"] = money(row["ebitda"])
            formatted["enterprise_value"] = money(row["enterprise_value"])
            formatted["ev_to_ebitda"] = number(row["ev_to_ebitda"])
            formatted["cash_and_equivalents"] = money(row["cash_and_equivalents"])
            formatted["total_debt"] = money(row["total_debt"])
            formatted["stock_price"] = number(row["stock_price"])
            formatted["pe_ratio"] = number(row["pe_ratio"])
            formatted["annual_pe_ratio"] = number(row["annual_pe_ratio"])
            formatted["ttm_pe_ratio"] = number(row["ttm_pe_ratio"])
            formatted["forward_pe_ratio"] = number(row["forward_pe_ratio"])
            formatted["forward_eps"] = number(row["forward_eps"])
            writer.writerow(formatted)

    print(f"Wrote {len(rows)} companies to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

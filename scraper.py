from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


CITIES = ["Sydney", "Canberra", "Melbourne", "Brisbane", "Adelaide", "Perth", "Darwin", "Hobart"]

CITY_PAGE_URLS = {
    "Sydney": "https://aip.com.au/pricing/diesel/new-south-wales-act-retail-diesel-prices/sydney/",
    "Canberra": "https://aip.com.au/pricing/diesel/new-south-wales-act-retail-diesel-prices/canberra/",
    "Melbourne": "https://aip.com.au/pricing/diesel/victorian-retail-diesel-prices/melbourne/",
    "Brisbane": "https://aip.com.au/pricing/diesel/queensland-retail-diesel-fuel-prices/brisbane/",
    "Adelaide": "https://aip.com.au/pricing/diesel/south-australian-retail-diesel-prices/adelaide/",
    "Perth": "https://aip.com.au/pricing/diesel/western-australia-retail-diesel-prices/perth/",
    "Darwin": "https://aip.com.au/pricing/diesel/northern-territory-retail-diesel-prices/darwin/",
    "Hobart": "https://aip.com.au/pricing/diesel/tasmania-retail-diesel-prices/hobart/",
}

USER_AGENT = "Macromonitor diesel price scraper"
CHART_SERIES_PATTERN = re.compile(
    r"const\s+chartSeries\s*=\s*(\[.*?\]);\s*const\s+chartTitle",
    flags=re.DOTALL,
)


@dataclass
class ScrapeResult:
    rows: pd.DataFrame
    source_urls: list[str]
    scraped_at: str


def extract_chart_series(html: str, city: str) -> pd.DataFrame:
    match = CHART_SERIES_PATTERN.search(html)
    if not match:
        raise ValueError(f"Could not find AIP chartSeries data for {city}")

    try:
        chart_series = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"AIP returned invalid chartSeries JSON for {city}") from exc

    selected = next(
        (series for series in chart_series if str(series.get("name", "")).casefold() == city.casefold()),
        chart_series[0] if chart_series else None,
    )
    if not selected or not selected.get("data"):
        raise ValueError(f"AIP returned no chart points for {city}")

    series = pd.DataFrame(selected["data"], columns=["week_ending", city])
    series["week_ending"] = (
        pd.to_datetime(series["week_ending"], unit="ms", utc=True)
        .dt.tz_convert(None)
        .dt.normalize()
    )
    series[city] = pd.to_numeric(series[city], errors="coerce")
    if series[city].isna().any():
        raise ValueError(f"AIP returned missing or non-numeric prices for {city}")
    series[city] = series[city].round(1)
    return series.drop_duplicates("week_ending", keep="last").sort_values("week_ending")


def extract_city_series(city: str) -> pd.DataFrame:
    url = CITY_PAGE_URLS[city]
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")
    return extract_chart_series(html, city)


def scrape_latest_diesel_prices() -> ScrapeResult:
    city_frames: list[pd.DataFrame] = []
    failures: dict[str, str] = {}

    for city in CITIES:
        try:
            city_frames.append(extract_city_series(city))
        except Exception as exc:
            failures[city] = str(exc)

    if failures:
        details = "; ".join(f"{city}: {error}" for city, error in failures.items())
        raise RuntimeError(f"Refresh aborted. Failed cities: {details}")

    rows = city_frames[0]
    for frame in city_frames[1:]:
        rows = rows.merge(frame, on="week_ending", how="inner")
    if rows.empty:
        raise RuntimeError("Refresh aborted. AIP city series did not share any week-ending dates.")

    rows["month_start"] = rows["week_ending"].values.astype("datetime64[M]")
    rows = rows[["month_start", "week_ending", *CITIES]].sort_values("week_ending")
    return ScrapeResult(
        rows=rows,
        source_urls=[CITY_PAGE_URLS[city] for city in CITIES],
        scraped_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def load_prices(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    required = {"month_start", "week_ending", *CITIES}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Stored diesel data is missing columns: {', '.join(sorted(missing))}")
    df["month_start"] = pd.to_datetime(df["month_start"])
    df["week_ending"] = pd.to_datetime(df["week_ending"])
    df[CITIES] = df[CITIES].apply(pd.to_numeric, errors="raise").round(1)
    return df.sort_values("week_ending")


def save_prices(df: pd.DataFrame, csv_path: Path, xlsx_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    output = df.sort_values("week_ending").copy()
    output[CITIES] = output[CITIES].round(1)
    output["month_start"] = pd.to_datetime(output["month_start"]).dt.date
    output["week_ending"] = pd.to_datetime(output["week_ending"]).dt.date
    output.to_csv(csv_path, index=False)
    output.to_excel(xlsx_path, index=False)


def merge_latest(existing: pd.DataFrame, scraped_rows: pd.DataFrame) -> tuple[pd.DataFrame, str, int]:
    if existing.empty:
        return scraped_rows.copy(), "initialised", len(scraped_rows)

    latest = existing["week_ending"].max()
    newer_rows = scraped_rows[scraped_rows["week_ending"] > latest]
    matching_latest = scraped_rows[scraped_rows["week_ending"] == latest]

    if not newer_rows.empty:
        combined = pd.concat([existing, newer_rows], ignore_index=True)
        return combined.sort_values("week_ending"), "appended", len(newer_rows)
    if not matching_latest.empty:
        updated = existing[existing["week_ending"] != latest]
        combined = pd.concat([updated, matching_latest], ignore_index=True)
        return combined.sort_values("week_ending"), "overwrote_latest", 1
    return existing, "ignored_older", 0

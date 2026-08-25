from pathlib import Path

from scraper import load_prices, merge_latest, save_prices, scrape_latest_diesel_prices


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "diesel_weekly_prices.csv"
XLSX_PATH = BASE_DIR / "data" / "diesel_weekly_prices.xlsx"


def main() -> None:
    result = scrape_latest_diesel_prices()
    if CSV_PATH.exists():
        existing = load_prices(CSV_PATH)
        merged, action, changed_rows = merge_latest(existing, result.rows)
    else:
        merged, action, changed_rows = result.rows, "initialised", len(result.rows)

    if action != "ignored_older":
        save_prices(merged, CSV_PATH, XLSX_PATH)
    print(f"{action}: {changed_rows} row(s)")
    print(f"latest observation: {merged['week_ending'].max().date().isoformat()}")


if __name__ == "__main__":
    main()

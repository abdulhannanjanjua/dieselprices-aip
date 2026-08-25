from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from scraper import CITIES, CITY_PAGE_URLS, load_prices, merge_latest, save_prices, scrape_latest_diesel_prices


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "diesel_weekly_prices.csv"
XLSX_PATH = DATA_DIR / "diesel_weekly_prices.xlsx"


st.set_page_config(page_title="AIP retail diesel prices", layout="wide")


@st.cache_data(show_spinner=False)
def cached_prices(cache_buster: float) -> pd.DataFrame:
    return load_prices(CSV_PATH)


def ensure_xlsx(df: pd.DataFrame) -> None:
    if not XLSX_PATH.exists():
        save_prices(df, CSV_PATH, XLSX_PATH)


st.title("AIP retail diesel prices")
st.caption(
    "Weekly retail diesel prices (cents per litre, incl. GST) sourced from aip.com.au. "
    "Source data: AIP / MotorMouth. Stored and exported values are rounded to 1 decimal place."
)

with st.expander("Source links"):
    st.markdown("\n".join(f"- [{city}]({CITY_PAGE_URLS[city]})" for city in CITIES))

selected_cities = st.multiselect("Cities", CITIES, default=CITIES, label_visibility="collapsed")

if "cache_buster" not in st.session_state:
    st.session_state.cache_buster = CSV_PATH.stat().st_mtime if CSV_PATH.exists() else 0

if st.button("Get latest prices", type="primary"):
    with st.spinner("Fetching latest AIP diesel prices..."):
        try:
            existing = load_prices(CSV_PATH)
            result = scrape_latest_diesel_prices()
            merged, action, changed_rows = merge_latest(existing, result.rows)
            if action != "ignored_older":
                save_prices(merged, CSV_PATH, XLSX_PATH)
                st.session_state.cache_buster = CSV_PATH.stat().st_mtime

            latest_week = merged["week_ending"].max().date().isoformat()
            if action in {"appended", "initialised"}:
                st.success(f"Added {changed_rows} diesel price week(s). Latest observation: {latest_week}.")
            elif action == "overwrote_latest":
                st.success(f"Updated latest diesel prices for {latest_week}.")
            else:
                st.warning("AIP returned no newer diesel price weeks; files were left unchanged.")
        except Exception as exc:
            st.error(str(exc))

if not CSV_PATH.exists():
    st.error("Stored diesel data is missing. Run update_diesel_prices.py before deploying the app.")
    st.stop()

df = cached_prices(st.session_state.cache_buster)
ensure_xlsx(df)

latest_observation = df["week_ending"].max().date().isoformat()
st.success(f"Got {len(CITIES)} cities, {len(df)} weeks. Latest observation: {latest_observation}")

if selected_cities:
    chart_df = df.melt(
        id_vars=["week_ending"],
        value_vars=selected_cities,
        var_name="City",
        value_name="Price",
    ).rename(columns={"week_ending": "date"})

    fig = px.line(chart_df, x="date", y="Price", color="City")
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=20, b=10),
        legend_title_text="",
        yaxis_title=None,
        xaxis_title=None,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Select at least one city to display the chart.")

display_df = df.sort_values("week_ending", ascending=False).copy()
display_df = display_df.rename(columns={"week_ending": "date"})
display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d 14:00:00")
display_df = display_df[["date", *CITIES]]
st.dataframe(display_df, use_container_width=True, hide_index=True)

with open(XLSX_PATH, "rb") as file:
    st.download_button(
        "Download xlsx",
        data=file,
        file_name="diesel_weekly_prices.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with open(CSV_PATH, "rb") as file:
    st.download_button(
        "Download csv",
        data=file,
        file_name="diesel_weekly_prices.csv",
        mime="text/csv",
    )

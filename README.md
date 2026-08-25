# AIP retail diesel prices

Rebuilt Streamlit dashboard for weekly AIP retail diesel prices.

This version replaces the retired AIP URLs and the Playwright browser fallback
used by the previous app. It reads the `chartSeries` JSON embedded in AIP's
current diesel price pages, stores the results in CSV/XLSX, and displays the
committed data immediately when the app opens.

## Run locally

```powershell
pip install -r requirements.txt
python update_diesel_prices.py
streamlit run app.py
```

## Deploy

1. Create a new GitHub repository and upload this folder's contents.
2. In Streamlit Community Cloud, create an app from that repository.
3. Set the main file to `app.py`.
4. Run the `Update diesel prices` GitHub Action once to verify scheduled updates.

The action runs every Monday and commits refreshed CSV/XLSX files. The refresh
is all-or-nothing across Sydney, Canberra, Melbourne, Brisbane, Adelaide,
Perth, Darwin, and Hobart.

## Data

- `data/diesel_weekly_prices.csv`
- `data/diesel_weekly_prices.xlsx`

Values are weekly retail diesel prices in cents per litre, including GST,
sourced from AIP/MotorMouth and rounded to one decimal place.

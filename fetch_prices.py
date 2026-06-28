"""
Yahoo Finance price fetcher — hourly refresh during market hours.
Run once and leave it running: python fetch_prices.py

Install dependencies:
  pip install yfinance schedule pytz

Output: prices.json (refreshed every hour 9:30am-4pm ET, Mon-Fri)
"""

import yfinance as yf
import json
import csv
import sys
import time
import schedule
import pytz
from datetime import datetime, time as dtime

OUTPUT_FILE = "prices.json"
CSV_FILE    = "portfolio_template.csv"

ET = pytz.timezone("America/New_York")

MARKET_OPEN  = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)


def is_market_open() -> bool:
    now_et = datetime.now(ET)
    if now_et.weekday() >= 5:          # Saturday=5, Sunday=6
        return False
    t = now_et.time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


def load_positions(path: str) -> list[dict]:
    positions = []
    try:
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                positions.append({
                    "ticker":   row["ticker"].upper().strip(),
                    "platform": row.get("platform", "Unknown"),
                    "shares":   float(row["shares"]),
                    "cost":     float(row.get("Avg Cost") or row.get("avg_cost") or row.get("avg_price") or row.get("cost") or 0),
                })
    except FileNotFoundError:
        print(f"[ERROR] {path} not found.")
        sys.exit(1)
    return positions


def fetch_prices(tickers: list[str]) -> dict:
    result = {}
    for ticker in tickers:
        try:
            t    = yf.Ticker(ticker)
            hist = t.history(start=f"{datetime.now().year}-01-01")
            if hist.empty:
                print(f"  {ticker}: no data")
                continue

            closes = hist["Close"].tolist()
            volumes = hist["Volume"].tolist()
            dates  = [d.strftime("%Y-%m-%d") for d in hist.index]

            # Use last valid (non-NaN) price as current price
            valid_prices = [(d, p) for d, p in zip(dates, closes)
                            if p == p]          # NaN != NaN is True
            current_price = valid_prices[-1][1] if valid_prices else closes[-1]

            result[ticker] = {
                "price": round(current_price, 2),
                "history": [
                    {"date": d,
                     "price": round(float(p), 2) if p == p else None,
                     "vol":   int(v)}
                    for d, p, v in zip(dates, closes, volumes)
                ],
                "fetched_at": datetime.now().isoformat()
            }
            print(f"  {ticker}: ${current_price:.2f}")

        except Exception as e:
            print(f"  {ticker}: error — {e}")
    return result


def run_fetch():
    if not is_market_open():
        now_et = datetime.now(ET)
        print(f"[{now_et.strftime('%H:%M ET')}] Market closed — skipping fetch.")
        return

    now_et = datetime.now(ET)
    print(f"\n[{now_et.strftime('%Y-%m-%d %H:%M ET')}] Fetching prices...")

    positions = load_positions(CSV_FILE)
    tickers   = list({p["ticker"] for p in positions})
    prices    = fetch_prices(tickers)

    output = {
        "positions":     positions,
        "prices":        prices,
        "generated_at":  datetime.now().isoformat()
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    print("Portfolio price fetcher started.")
    print(f"  CSV:    {CSV_FILE}")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Schedule: every hour, Mon–Fri 9:30am–4pm ET\n")

    run_fetch()                              # Run immediately on start

    schedule.every().hour.at(":00").do(run_fetch)   # Then top of every hour

    print("Waiting for next scheduled run... (Ctrl+C to stop)\n")
    while True:
        schedule.run_pending()
        time.sleep(30)                       # Check every 30 seconds

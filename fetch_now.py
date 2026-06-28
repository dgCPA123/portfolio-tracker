"""
fetch_now.py — One-shot Yahoo Finance price fetcher.
Runs immediately, no market-hours check.
Uses last valid close if today's price isn't finalized yet (NaN fix).

Usage: python fetch_now.py portfolio_template.csv prices.json
"""

import yfinance as yf
import json
import csv
import sys
from datetime import datetime

def load_positions(path):
    positions = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            positions.append({
                "ticker": row["ticker"].upper().strip(),
                "platform": row.get("platform", "Unknown"),
                "shares": float(row["shares"]),
                "cost": float(row.get("Avg Cost") or row.get("avg_cost") or row.get("avg_price") or row.get("cost") or 0),
            })
    return positions

def fetch_prices(tickers):
    result = {}
    year = datetime.now().year
    print(f"Fetching YTD data from Jan 1, {year}...\n")

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(start=f"{year}-01-01")

            if hist.empty:
                print(f"  {ticker}: no data returned")
                continue

            # NaN fix: drop rows where Close is NaN, use last valid close
            hist = hist.dropna(subset=["Close"])

            closes = hist["Close"].tolist()
            volumes = hist["Volume"].tolist()
            dates = [d.strftime("%Y-%m-%d") for d in hist.index]

            current_price = round(float(closes[-1]), 2)

            result[ticker] = {
                "price": current_price,
                "history": [
                    {"date": d, "price": round(float(p), 2), "vol": int(v)}
                    for d, p, v in zip(dates, closes, volumes)
                ],
                "fetched_at": datetime.now().isoformat()
            }
            print(f"  {ticker}: ${current_price:.2f}  ({len(closes)} trading days)")

        except Exception as e:
            print(f"  {ticker}: error — {e}")

    return result

if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "portfolio_template.csv"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "prices.json"

    print(f"Loading positions from {csv_path}...")
    try:
        positions = load_positions(csv_path)
        print(f"Found {len(positions)} positions: {', '.join(p['ticker'] for p in positions)}\n")
    except FileNotFoundError:
        print(f"Error: could not find {csv_path}")
        sys.exit(1)

    tickers = list({p["ticker"] for p in positions})
    prices = fetch_prices(tickers)

    output = {
        "positions": positions,
        "prices": prices,
        "generated_at": datetime.now().isoformat()
    }

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDone! Saved to {out_path}")
    print("Paste the contents of that file into this chat to load your dashboard.")

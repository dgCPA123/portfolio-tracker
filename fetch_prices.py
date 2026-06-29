import yfinance as yf
import json
import csv
import sys
from datetime import datetime


def fetch_prices(tickers):
    result = {}
    print(f"Fetching YTD data for: {', '.join(tickers)}")
    year_start = f"{datetime.now().year}-01-01"

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(start=year_start)

            if hist.empty:
                print(f"  {ticker}: no data returned")
                continue

            closes = hist["Close"].tolist()
            volumes = hist["Volume"].tolist()
            dates = [d.strftime("%Y-%m-%d") for d in hist.index]

            try:
                current_price = float(t.fast_info["last_price"])
                if current_price != current_price:
                    raise ValueError("NaN")
            except Exception:
                current_price = closes[-1] if closes else 0

            clean_closes = []
            for i, p in enumerate(closes):
                if p != p:
                    clean_closes.append(clean_closes[-1] if clean_closes else 0)
                else:
                    clean_closes.append(round(float(p), 2))

            result[ticker] = {
                "price": round(current_price, 2),
                "history": [
                    {"date": d, "price": p, "vol": int(v)}
                    for d, p, v in zip(dates, clean_closes, volumes)
                ],
                "fetched_at": datetime.now().isoformat()
            }
            print(f"  {ticker}: ${current_price:.2f}")

        except Exception as e:
            print(f"  {ticker}: error — {e}")

    return result


def load_positions(path):
    positions = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            positions.append({
                "ticker": row["ticker"].upper().strip(),
                "platform": row.get("platform", "Unknown"),
                "shares": float(row["shares"]),
                "cost": float(row["Avg Cost"]),
            })
    return positions


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "portfolio_template.csv"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "prices.json"

    print(f"Loading positions from {csv_path}...")
    try:
        positions = load_positions(csv_path)
    except FileNotFoundError:
        print(f"File not found: {csv_path}")
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

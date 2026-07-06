"""
Yahoo Finance price + options fetcher for portfolio dashboard.
Fetches 2 years of history (for YTD/1Y/2Y trend comparisons), current price,
and options flow data. Also fetches SPY/QQQ as benchmarks regardless of
whether they're held in the portfolio.

Usage:  python fetch_prices.py portfolio_template.csv prices.json
Install: pip install yfinance
"""

import yfinance as yf
import json
import csv
import sys
from datetime import datetime, timedelta

BENCHMARK_TICKERS = ["SPY", "QQQ"]


def fetch_options(t, ticker, current_price):
    """Fetch options flow data for the nearest expiry."""
    try:
        expirations = t.options
        if not expirations:
            return None

        # Use nearest expiry that is at least 7 days out
        today = datetime.now().date()
        target_expiry = None
        for exp in expirations:
            exp_date = datetime.strptime(exp, "%Y-%m-%d").date()
            if (exp_date - today).days >= 7:
                target_expiry = exp
                break

        if not target_expiry:
            target_expiry = expirations[0]

        chain = t.option_chain(target_expiry)
        calls = chain.calls
        puts  = chain.puts

        # Total volume
        call_vol = int(calls["volume"].fillna(0).sum())
        put_vol  = int(puts["volume"].fillna(0).sum())
        total_vol = call_vol + put_vol

        # Put/Call ratio
        pcr = round(put_vol / call_vol, 3) if call_vol > 0 else None

        # Implied volatility — weight by open interest near ATM
        atm_calls = calls[
            (calls["strike"] >= current_price * 0.95) &
            (calls["strike"] <= current_price * 1.05)
        ]
        atm_puts = puts[
            (puts["strike"] >= current_price * 0.95) &
            (puts["strike"] <= current_price * 1.05)
        ]
        iv_calls = round(float(atm_calls["impliedVolatility"].mean()) * 100, 1) \
            if not atm_calls.empty else None
        iv_puts  = round(float(atm_puts["impliedVolatility"].mean()) * 100, 1) \
            if not atm_puts.empty else None
        iv_avg   = round((iv_calls + iv_puts) / 2, 1) \
            if iv_calls and iv_puts else (iv_calls or iv_puts)

        # Largest single strikes by volume (top 3 calls and puts)
        top_calls = calls.nlargest(3, "volume")[["strike", "volume", "impliedVolatility"]]\
            .rename(columns={"impliedVolatility": "iv"})\
            .assign(volume=lambda df: df["volume"].fillna(0).astype(int),
                    iv=lambda df: (df["iv"] * 100).round(1))\
            .to_dict("records") if not calls.empty else []
        top_puts  = puts.nlargest(3, "volume")[["strike", "volume", "impliedVolatility"]]\
            .rename(columns={"impliedVolatility": "iv"})\
            .assign(volume=lambda df: df["volume"].fillna(0).astype(int),
                    iv=lambda df: (df["iv"] * 100).round(1))\
            .to_dict("records") if not puts.empty else []

        # Open interest
        call_oi = int(calls["openInterest"].fillna(0).sum())
        put_oi  = int(puts["openInterest"].fillna(0).sum())

        print(f"    Options: call_vol={call_vol:,} put_vol={put_vol:,} PCR={pcr} IV={iv_avg}%")

        return {
            "expiry":    target_expiry,
            "call_vol":  call_vol,
            "put_vol":   put_vol,
            "total_vol": total_vol,
            "pcr":       pcr,
            "call_oi":   call_oi,
            "put_oi":    put_oi,
            "iv":        iv_avg,
            "iv_calls":  iv_calls,
            "iv_puts":   iv_puts,
            "top_calls": top_calls,
            "top_puts":  top_puts,
        }

    except Exception as e:
        print(f"    Options error: {e}")
        return None


def fetch_prices(tickers):
    result = {}
    print(f"\nFetching 2-year price + options data for: {', '.join(tickers)}\n")
    start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

    for ticker in tickers:
        print(f"  [{ticker}]")
        try:
            t = yf.Ticker(ticker)
            hist = t.history(start=start_date)

            if hist.empty:
                print(f"    No price data returned")
                continue

            closes  = hist["Close"].tolist()
            highs   = hist["High"].tolist()
            lows    = hist["Low"].tolist()
            volumes = hist["Volume"].tolist()
            dates   = [d.strftime("%Y-%m-%d") for d in hist.index]

            # Current price — fall back to last close if intraday is NaN
            try:
                current_price = float(t.fast_info["last_price"])
                if current_price != current_price:
                    raise ValueError("NaN")
            except Exception:
                current_price = closes[-1]

            # Clean NaN closes/highs/lows (carry forward last valid value)
            clean_closes, clean_highs, clean_lows = [], [], []
            for i in range(len(closes)):
                c, h, l = closes[i], highs[i], lows[i]
                if c != c:
                    c = clean_closes[-1] if clean_closes else 0
                if h != h:
                    h = clean_highs[-1] if clean_highs else c
                if l != l:
                    l = clean_lows[-1] if clean_lows else c
                clean_closes.append(round(float(c), 2))
                clean_highs.append(round(float(h), 2))
                clean_lows.append(round(float(l), 2))

            print(f"    Price: ${current_price:.2f} | {len(clean_closes)} trading days (2Y)")

            # Options flow
            options = fetch_options(t, ticker, current_price)

            result[ticker] = {
                "price":      round(current_price, 2),
                "history":    [
                    {"date": d, "price": p, "high": h, "low": l, "vol": int(v)}
                    for d, p, h, l, v in zip(dates, clean_closes, clean_highs, clean_lows, volumes)
                ],
                "options":    options,
                "fetched_at": datetime.now().isoformat(),
            }

        except Exception as e:
            print(f"    Error: {e}")

    return result


def fetch_benchmarks(start_date):
    """Fetch price history only (no options) for benchmark tickers — always
    pulled regardless of whether the user holds them in their portfolio."""
    result = {}
    print(f"\nFetching benchmark data: {', '.join(BENCHMARK_TICKERS)}\n")
    for ticker in BENCHMARK_TICKERS:
        print(f"  [{ticker}] (benchmark)")
        try:
            t = yf.Ticker(ticker)
            hist = t.history(start=start_date)
            if hist.empty:
                print(f"    No price data returned")
                continue

            closes = hist["Close"].tolist()
            dates  = [d.strftime("%Y-%m-%d") for d in hist.index]

            clean_closes = []
            for p in closes:
                if p != p:
                    clean_closes.append(clean_closes[-1] if clean_closes else 0)
                else:
                    clean_closes.append(round(float(p), 2))

            print(f"    {len(clean_closes)} trading days (2Y)")

            result[ticker] = {
                "history": [
                    {"date": d, "price": p}
                    for d, p in zip(dates, clean_closes)
                ]
            }
        except Exception as e:
            print(f"    Error: {e}")

    return result


def load_positions(path):
    positions = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            positions.append({
                "ticker":   row["ticker"].upper().strip(),
                "platform": row.get("platform", "Unknown"),
                "shares":   float(row["shares"]),
                "cost":     float(row["Avg Cost"]),
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

    print(f"Found {len(positions)} positions.")
    tickers = list({p["ticker"] for p in positions})
    prices  = fetch_prices(tickers)

    start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
    benchmarks = fetch_benchmarks(start_date)

    output = {
        "positions":    positions,
        "prices":       prices,
        "benchmarks":   benchmarks,
        "generated_at": datetime.now().isoformat(),
    }

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Saved to {out_path}")

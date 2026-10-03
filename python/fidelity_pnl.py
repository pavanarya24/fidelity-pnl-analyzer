#!/usr/bin/env python3
"""
Fidelity Accounts History CSV -> FIFO-matched stock P&L report.

Usage:
  python fidelity_pnl.py History1.csv [History2.csv ...] --capital 30000 [--account Z12345678] [--out report]

Notes
- Uses Fidelity's "Amount" column (net cash, fees/commissions included), so P&L is net of costs.
- FIFO matching per symbol, long and short. Positions can carry across days.
- Stocks only: option symbols (start with "-") and non-trade rows are skipped.
- Fidelity history has no time of day, so intraday order within one day follows file order
  (oldest first after sorting by date; same-day rows keep the file's chronological order).
- Reconcile the printed totals against your Fidelity statement before trusting them.
"""
import argparse
import io
import sys
from collections import deque, defaultdict

import pandas as pd


def read_fidelity(path):
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16", errors="replace")
    else:
        text = raw.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    start = next(
        (i for i, l in enumerate(lines)
         if all(k in l.replace('"', "").lower() for k in ("symbol", "amount"))
         and ("action" in l.lower() or "description" in l.lower())), None
    )
    if start is None:
        print(f"{path}: could not find the header row (needs Symbol, Amount and Action or Description columns). First lines of the file:")
        for l in lines[:6]:
            print("  ", l[:200])
        sys.exit(1)
    body = []
    for l in lines[start:]:
        if not l.strip():
            break  # footer disclaimer starts after first blank line
        body.append(l)
    df = pd.read_csv(io.StringIO("\n".join(body)), dtype=str)
    df.columns = [c.strip().strip('"').replace(" ($)", "").replace("($)", "").strip() for c in df.columns]
    if "Action" not in df.columns and "Description" in df.columns:
        df["Action"] = df["Description"]
    if "Run Date" not in df.columns:
        dcol = next((c for c in df.columns if c.lower() in ("date", "trade date")), None)
        if dcol is None:
            sys.exit(f"{path}: no date column found. Columns: {list(df.columns)}")
        df["Run Date"] = df[dcol]
    df["_src"] = path
    df["_row"] = range(len(df))
    return df


def num(s):
    return pd.to_numeric(
        s.astype(str).str.replace(r"[,$\s]", "", regex=True).replace({"": None, "nan": None}),
        errors="coerce",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--capital", type=float, required=True, help="starting capital")
    ap.add_argument("--account", help="filter to one account number")
    ap.add_argument("--out", default="fidelity_report", help="output file prefix")
    a = ap.parse_args()

    df = pd.concat([read_fidelity(p) for p in a.files], ignore_index=True)
    # Drop rows duplicated ACROSS overlapping files only. Identical fills inside one file
    # (same price and size, common in scalping) are real and must all be kept.
    cols = [c for c in df.columns if c not in ("_src", "_row")]
    df["_occ"] = df.groupby(["_src"] + cols).cumcount()
    df = df.drop_duplicates(subset=cols + ["_occ"])

    if a.account and "Account Number" in df.columns:
        df = df[df["Account Number"].astype(str).str.strip() == a.account]

    df["date"] = pd.to_datetime(df["Run Date"].astype(str).str.strip().str[:10], format="%m/%d/%Y", errors="coerce")
    action = df["Action"].fillna("").str.upper()
    sym = df["Symbol"].fillna("").str.strip()

    is_buy = action.str.contains(r"\bBOUGHT\b", regex=True)
    is_sell = action.str.contains(r"\bSOLD\b", regex=True)
    is_stock = ~sym.str.startswith("-") & (sym != "")
    t = df[(is_buy | is_sell) & is_stock].copy()
    if t.empty:
        print("No buy/sell stock rows recognised. Most common descriptions with a symbol:")
        print(df[sym != ""]["Action"].str[:60].value_counts().head(15).to_string())
        sys.exit(1)
    t["side"] = 1
    t.loc[is_sell[t.index], "side"] = -1
    t["qty"] = num(t["Quantity"]).abs()
    t["cash"] = num(t["Amount"])
    t = t.dropna(subset=["date", "qty", "cash"])
    t = t[t["qty"] > 0]
    # file order is newest-first in Fidelity exports: sort by date, keep reverse file order within a day
    t = t.sort_values(["date", "_src", "_row"], ascending=[True, True, False])

    lots = defaultdict(deque)  # symbol -> deque of [signed_qty_remaining, cash_per_share]
    closed = []
    for _, r in t.iterrows():
        s = r["Symbol"].strip()
        q = r["qty"] * r["side"]  # signed
        rem = q
        fc = r["cash"] / r["qty"]  # signed cash per share (buy negative, sell positive)
        pnl = 0.0
        matched_total = 0.0
        dq = lots[s]
        while rem != 0 and dq and (dq[0][0] > 0) != (rem > 0):
            lot = dq[0]
            m = min(abs(rem), abs(lot[0]))
            pnl += (lot[1] + fc) * m
            matched_total += m
            lot[0] += m if lot[0] < 0 else -m
            rem += m if rem < 0 else -m
            if abs(lot[0]) < 1e-9:
                dq.popleft()
        if abs(rem) > 1e-9:
            dq.append([rem, fc])
        if matched_total > 0:
            closed.append({"date": r["date"], "symbol": s, "shares_closed": matched_total, "net_pnl": pnl})

    c = pd.DataFrame(closed)
    if c.empty:
        sys.exit("No closed stock trades found. Check the file and filters.")

    daily = c.groupby("date")["net_pnl"].sum().rename("net_pnl").to_frame()
    daily["equity"] = a.capital + daily["net_pnl"].cumsum()
    peak = daily["equity"].cummax().clip(lower=a.capital)
    dd = daily["equity"] - peak
    daily["drawdown"] = dd
    daily["drawdown_pct"] = dd / peak * 100

    wins = c[c.net_pnl > 0].net_pnl
    losses = c[c.net_pnl < 0].net_pnl
    gp, gl = wins.sum(), -losses.sum()
    open_pos = {s: sum(l[0] for l in d) for s, d in lots.items() if d and abs(sum(l[0] for l in d)) > 1e-9}

    print(f"Period: {c.date.min():%Y-%m-%d} to {c.date.max():%Y-%m-%d} ({daily.shape[0]} trading days)")
    print(f"Fills used: {len(t)} | Closed trades: {len(c)}")
    print(f"Net realized P&L: ${c.net_pnl.sum():,.2f}")
    print(f"Sum of Amount over all fills used: ${t['cash'].sum():,.2f} (equals net P&L only when nothing is left open)")
    print(f"Return on ${a.capital:,.0f}: {c.net_pnl.sum() / a.capital * 100:.2f}%")
    print(f"Win rate: {len(wins) / len(c) * 100:.1f}% | Avg win ${wins.mean():,.2f} | Avg loss ${losses.mean():,.2f}")
    print(f"Profit factor: {gp / gl:.2f}" if gl else "Profit factor: n/a")
    print(f"Max drawdown: ${dd.min():,.2f} ({daily.drawdown_pct.min():.2f}% of peak equity)")
    print(f"Green days: {(daily.net_pnl > 0).sum()} | Red days: {(daily.net_pnl < 0).sum()}")
    print(f"Best day ${daily.net_pnl.max():,.2f} | Worst day ${daily.net_pnl.min():,.2f}")
    if open_pos:
        print(f"\nUNMATCHED open positions ({len(open_pos)}) - missing history or genuine holdings:")
        for s, q in sorted(open_pos.items()):
            print(f"  {s}: {q:+g}")
    else:
        print("\nNo unmatched open positions.")

    monthly = c.groupby(c.date.dt.to_period("M"))["net_pnl"].sum()
    print("\nMonthly net P&L:")
    print(monthly.round(2).to_string())

    c.to_csv(f"{a.out}_closed_trades.csv", index=False)
    daily.to_csv(f"{a.out}_daily.csv")
    print(f"\nWrote {a.out}_closed_trades.csv and {a.out}_daily.csv")


if __name__ == "__main__":
    main()

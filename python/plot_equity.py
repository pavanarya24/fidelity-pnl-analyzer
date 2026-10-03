#!/usr/bin/env python3
"""
Equity curve + drawdown chart from fidelity_pnl.py's daily CSV.

Usage:
  pip install pandas matplotlib
  python plot_equity.py fidelity_report_daily.csv --capital 30000 --out equity_chart.png
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--capital", type=float, default=30000)
    ap.add_argument("--out", default="equity_chart.png")
    ap.add_argument("--title", default="Managed account: realized equity (net of fees)")
    a = ap.parse_args()

    d = pd.read_csv(a.csv, parse_dates=["date"]).sort_values("date")
    # start the curve at the starting capital, the day before the first trading day
    start = pd.DataFrame({"date": [d.date.min() - pd.Timedelta(days=1)], "equity": [a.capital]})
    eq = pd.concat([start, d[["date", "equity"]]], ignore_index=True)
    peak = eq.equity.cummax()
    dd_pct = (eq.equity - peak) / peak * 100

    net = eq.equity.iloc[-1] - a.capital
    ret = net / a.capital * 100
    max_dd = dd_pct.min()

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 6.2), sharex=True, gridspec_kw={"height_ratios": [3, 1.2]}
    )
    ax1.plot(eq.date, eq.equity, color="#0b6e4f", lw=2)
    ax1.fill_between(eq.date, a.capital, eq.equity, where=eq.equity >= a.capital, color="#0b6e4f", alpha=0.12)
    ax1.fill_between(eq.date, a.capital, eq.equity, where=eq.equity < a.capital, color="#c0392b", alpha=0.15)
    ax1.axhline(a.capital, color="#888", lw=0.8, ls="--")
    ax1.set_ylabel("Account equity ($)")
    ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax1.set_title(a.title, loc="left", fontsize=13, fontweight="bold")
    ax1.text(
        0.01, 0.95,
        f"Start ${a.capital:,.0f}  |  Net ${net:,.0f} ({ret:+.1f}%)  |  Max drawdown {max_dd:.1f}%",
        transform=ax1.transAxes, va="top", fontsize=10,
    )
    ax1.grid(alpha=0.25)

    ax2.fill_between(eq.date, dd_pct, 0, color="#c0392b", alpha=0.35)
    ax2.set_ylabel("Drawdown (%)")
    ax2.grid(alpha=0.25)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

    fig.text(
        0.01, 0.005,
        "One account, limited period, realized P&L net of commissions/fees, daily closes. "
        "Past performance does not guarantee future results.",
        fontsize=7.5, color="#555",
    )
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(a.out, dpi=200)
    print(f"Saved {a.out} | net ${net:,.2f} ({ret:.2f}%) | max drawdown {max_dd:.2f}%")


if __name__ == "__main__":
    main()

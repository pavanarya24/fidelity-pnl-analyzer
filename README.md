# Fidelity P&L Analyzer

Fidelity's history download lists fills, not results. This tool turns that file into net P&L after fees, profit factor, drawdown, monthly P&L and an equity curve, using FIFO matching for longs and shorts.

**Your file never leaves your computer.** The web version runs entirely in the browser under a content security policy that blocks all network requests. There is no server, no account and no analytics. Load the page, go offline, and it still works.

## Try it

- **Web:** open `index.html` in a browser (or use the hosted copy: `<your link>`). Click *Try it with demo data*, or drop in your own file.
- **Python:** `python python/fidelity_pnl.py History.csv --capital 30000`
  then `python python/plot_equity.py fidelity_report_daily.csv --capital 30000` for a chart.

## Getting your file from Fidelity

Accounts > Activity & Orders > History > set the date range and *All Activity* > Download (CSV). Export every account you want included, and use a range that starts before your earliest open position so nothing shows up as unmatched.

## How the numbers are calculated

- Only stock buys and sells are used. Option rows and rows without a symbol (for example margin mark-to-market entries) are skipped.
- P&L comes from Fidelity's own net `Amount` column, so commissions and fees are included.
- Fills are matched first-in-first-out per symbol, long and short, and positions can carry across days.
- A "closed trade" is one closing fill. Counts differ from other tools that define trades differently.
- Drawdown is measured on end-of-day realized equity against the running peak (never below starting capital).
- Fidelity history has dates but no times. Within a day, fills follow the file order (newest-first is detected). Totals do not depend on this; individual trade results can.

## Verifying it

```
node tests/test_core.js          # unit tests on the shipped browser code
python tests/cross_check.py      # random files: Python and JavaScript must agree
```

`cross_check.py` needs Python 3, pandas and node. The tests cover long and short round trips, fees, identical fills, newest-first files, skipped rows, unmatched positions, drawdown, bad input and the demo data.

Check any result against your official Fidelity statements before relying on it. On a real four-month account export of about 18,000 fills, the totals matched an independent journal's to within $2.

## A bug worth knowing about

An early version of the Python script removed duplicate rows to handle overlapping exports, and it did so within a single file. Scalping produces genuine repeated fills (same size, same price), so those were deleted, leaving unbalanced buys and sells. The output looked plausible, with a P&L more than three times too high, and it was only caught because an independent tool disagreed. Duplicates are now removed only across different files, and `test_core.js` has a regression test for it. Reconciling against a second source is part of how this tool is meant to be used.

## Limits

- Fidelity History CSVs only, stocks only. No options, margin interest, borrow fees or dividends.
- Results are realized P&L; open positions are not marked to market.
- Format changes on Fidelity's side can break import. If yours fails, the error message names the missing column.

## Disclaimer

For analysis only. Not financial, tax or investment advice. Past results do not predict future results.

## License

MIT. See `LICENSE`.

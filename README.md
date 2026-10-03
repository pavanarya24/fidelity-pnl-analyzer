# Fidelity P&L Analyzer

Fidelity's history download lists fills, not results. This tool turns that file into net P&L after fees, profit factor, drawdown, monthly P&L and an equity curve, using FIFO matching for longs and shorts.

It is a static site: one `index.html` with no build step, no framework, no external libraries, no CDN and no fonts or scripts loaded from the network. Drop it on any static host (GitHub Pages, Cloudflare Pages, an S3 bucket) unchanged.

## Privacy

**Your file never leaves your browser. It works offline.** The page is served from a content security policy that blocks every network request:

```
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:">
```

There is no server, no account, no cookie and no analytics. Load the page, go offline, and it still works. Nothing is uploaded, so there is nothing to delete.

## Getting your file from Fidelity

Sign in to Fidelity, open **Accounts > Activity & Orders > History**, set the date range, choose **All Activity**, and click **Download** to save the CSV. To cover more than one account, export each and analyze them one at a time. Start the range before your earliest open position, or those trades show up as unmatched.

Both the current Activity & Orders layout (`Date, Description, Symbol, Quantity, Price, Amount, Commission, Fees, Type`) and the older Accounts History layout (`Run Date, Action, ...`) are accepted. Unknown CSVs get a **map your columns** screen where you choose which column is the date, symbol, side, quantity and amount.

## What it computes

Only rows whose description/action matches `BOUGHT` or `SOLD` are used, with a non-empty symbol that does not start with `-` (options). Mark-to-market rows with zero quantity, dividends, interest and transfers are skipped. Quantity is taken as an absolute value, the side is +1 for a buy and -1 for a sell, and cash is the net `Amount` column (so commissions and fees are already included).

Fills are sorted by date, and within one day follow the file order (newest-first files are detected). Matching is FIFO per symbol, long and short, and positions carry across days: a fill opposite in sign to the head lot closes shares against it, adding `(lot cash/share + fill cash/share) * matched shares`, and any remainder opens a new lot. A **closed trade** is one closing fill, dated by the closing fill. Daily P&L is the sum of closed-trade P&L per date; equity is starting capital plus cumulative daily P&L; drawdown is measured on daily closes against the running peak, which never falls below starting capital.

Duplicate rows inside one file are **kept on purpose**. Scalpers produce genuinely identical fills (same size, same price), and removing them would corrupt the P&L. This is covered by a regression test.

## Running it

- **Web:** open `index.html` in a browser, or visit the hosted copy. Click *Try it with demo data*, or drop in your own file. The demo generates deterministic synthetic trades (seeded PRNG) and is labelled as such — no real trading data lives in this repo.
- **Python (command line):** `python python/fidelity_pnl.py History.csv --capital 30000`
  then `python python/plot_equity.py fidelity_report_daily.csv --capital 30000` for a chart.

## Verifying it

```
node tests/test_core.js          # unit tests load the shipped core straight out of index.html
python tests/cross_check.py      # random files: the Python script and the JS core must agree
```

`test_core.js` covers the long round trip with a fee, the short round trip, identical fills, newest-first ordering, ignored option and zero-quantity rows, unmatched remainders, max drawdown on daily closes, bad input errors, and the demo data. `cross_check.py` needs Python 3 with pandas and node; it generates random Fidelity-style files and requires the net P&L, closed-trade count and drawdown from the Python and JavaScript implementations to be identical.

Check any figure against your official Fidelity statements before relying on it.

## Structure

- `index.html` — the whole site. The analysis core sits between the `//<core>` and `//</core>` markers so the tests can load the exact shipped code.
- `python/fidelity_pnl.py` — command-line version with identical logic (pandas).
- `python/plot_equity.py` — optional matplotlib chart from the CLI's daily CSV.
- `tests/test_core.js`, `tests/cross_check.py` — tests.
- `sample/demo_synthetic.csv` — the deterministic synthetic demo export.
- `robots.txt`, `sitemap.xml` — replace the `example.com` placeholder with your domain after deploying.

Broker support is built for extension: each broker is an adapter with `detect(rows)` and `normalize(rows) -> fills`, and the matching/analytics code only ever sees normalized fills. Only Fidelity is implemented. Schwab, thinkorswim, Interactive Brokers, Robinhood and Webull are clearly marked stubs that should be filled in only from real sample exports.

## Limits

- Fidelity history CSVs only, stocks only. No options, margin interest, borrow fees or dividends.
- Results are realized P&L; open positions are not marked to market.
- Fidelity history has dates but no times, so within-day order follows the file. Totals are unaffected; individual trade results can change.
- Format changes on Fidelity's side can break import. If yours fails, the error names the missing column.

## Disclaimer

For analysis only. Not financial, tax or investment advice. Past results do not predict future results. Verify against your official Fidelity statements.

## License

MIT. See `LICENSE`.

// Run: node tests/test_core.js
// Loads the analysis core straight out of index.html, so the tests always cover the shipped code.
const fs = require("fs"), path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const core = html.split("//<core>")[1].split("//</core>")[0];
eval(core + ";global.analyze=analyze;global.demoCSV=demoCSV;");

let failed = 0;
const close = (a, b, eps = 0.005) => Math.abs(a - b) <= eps;
function check(name, ok, detail = "") {
  console.log((ok ? "PASS " : "FAIL ") + name + (ok ? "" : "  " + detail));
  if (!ok) failed++;
}
const HEAD = '"Date","Description","Symbol","Quantity","Price","Amount","Commission","Fees","Type"';
const csv = (...rows) => ["History: Test (Z0)", "From: 01/01/2026", "To: 12/31/2026", "All Activity", "", HEAD, ...rows, "", '"disclaimer"'].join("\n");
const row = (d, act, s, q, amt) => `"${d}","${act} ${s} INC (${s}) (Margin)","${s}","${q}","$1.00","$${amt}","$0.00","$0.00","Margin"`;

// 1. long round trip, fee already inside Amount
let r = analyze(csv(row("01/27/2026","YOU SOLD","AAA",-100,"1,099.95"), row("01/27/2026","YOU BOUGHT","AAA",100,"-1,000.00")), 30000);
check("long round trip net of fee", close(r.net, 99.95) && r.closed === 1 && r.open.length === 0, JSON.stringify(r.net));

// 2. short round trip (sell first, buy to cover)
r = analyze(csv(row("01/28/2026","YOU BOUGHT","BBB",10,"-1,100.00"), row("01/28/2026","YOU SOLD","BBB",-10,"1,000.00")), 30000);
check("short round trip loses 100", close(r.net, -100) && r.closed === 1, JSON.stringify(r.net));

// 3. identical fills in one file must all be kept (regression: old script de-duplicated them)
r = analyze(csv(
  row("01/28/2026","YOU SOLD","AAA",-100,"1,100.00"), row("01/28/2026","YOU BOUGHT","AAA",100,"-1,000.00"),
  row("01/28/2026","YOU SOLD","AAA",-100,"1,100.00"), row("01/28/2026","YOU BOUGHT","AAA",100,"-1,000.00")), 30000);
check("identical fills are not dropped", r.fills === 4 && r.closed === 2 && close(r.net, 200), `${r.fills} ${r.closed} ${r.net}`);

// 4. newest-first ordering within a day is detected (two days, descending dates)
r = analyze(csv(
  row("01/28/2026","YOU SOLD","TTT",-10,"1,000.00"), row("01/28/2026","YOU BOUGHT","TTT",10,"-1,100.00"),
  row("01/27/2026","YOU SOLD","AAA",-100,"1,099.95"), row("01/27/2026","YOU BOUGHT","AAA",100,"-1,000.00")), 30000);
check("newest-first file: order and totals", close(r.net, -0.05) && r.closed === 2, JSON.stringify(r.net));

// 5. option rows and zero-quantity mark-to-market rows are ignored
r = analyze(csv(
  '"01/27/2026","SHORT VS MARGIN MARK TO MARKET","","0","$0.00","$-273.87","$0.00","$0.00","Margin"',
  '"01/27/2026","YOU SOLD OPENING TRANSACTION CALL (-AAA260116C10)","-AAA260116C10","-1","$1.00","$100.00","$0.00","$0.00","Margin"',
  row("01/27/2026","YOU SOLD","AAA",-100,"1,100.00"), row("01/27/2026","YOU BOUGHT","AAA",100,"-1,000.00")), 30000);
check("options and mark-to-market ignored", r.fills === 2 && close(r.net, 100), `${r.fills} ${r.net}`);

// 6. partially closed position is reported as open
r = analyze(csv(row("01/27/2026","YOU SOLD","AAA",-60,"660.00"), row("01/27/2026","YOU BOUGHT","AAA",100,"-1,000.00")), 30000);
check("unmatched remainder reported", r.open.length === 1 && r.open[0][0] === "AAA" && close(r.open[0][1], 40), JSON.stringify(r.open));

// 7. drawdown on daily closes: equity 1100, 800, 850 -> peak 1100, dd -300 = -27.27%
r = analyze(csv(
  row("01/29/2026","YOU SOLD","AAA",-1,"50.00"), row("01/29/2026","YOU BOUGHT","AAA",1,"-0.00"),
  row("01/28/2026","YOU SOLD","AAA",-1,"-300.00"), row("01/28/2026","YOU BOUGHT","AAA",1,"-0.00"),
  row("01/27/2026","YOU SOLD","AAA",-1,"100.00"), row("01/27/2026","YOU BOUGHT","AAA",1,"-0.00")), 1000);
check("max drawdown percent", close(r.maxDD, -300) && close(r.maxDDpct, -27.2727, 0.01), `${r.maxDD} ${r.maxDDpct}`);

// 8. bad input gives clear errors
let threw = false; try { analyze("a,b,c\n1,2,3", 1000); } catch (e) { threw = /header/i.test(e.message); }
check("missing header rejected with a clear message", threw);
threw = false; try { analyze(csv(row("01/27/2026","YOU BOUGHT","AAA",100,"-1,000.00")), 1000); } catch (e) { threw = /closed/i.test(e.message); }
check("no closed trades rejected", threw);

// 9. demo data is deterministic and self-consistent
r = analyze(demoCSV(), 10000);
check("demo data: fixed result, nothing open, cash equals net", close(r.net, 208.27) && r.open.length === 0 && close(r.cashSum, r.net), `${r.net} ${r.open.length}`);

console.log(failed ? `\n${failed} test(s) failed` : "\nAll tests passed");
process.exit(failed ? 1 : 0);

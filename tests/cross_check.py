"""Run: python tests/cross_check.py
Generates random Fidelity-style files and checks that the Python script and the
browser tool's JavaScript core give the same net P&L, trade count and drawdown.
Needs Python 3, pandas, and node."""
import datetime, os, random, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = os.path.join(ROOT, "python", "fidelity_pnl.py")

JS = r"""
const fs=require('fs');
const html=fs.readFileSync(process.argv[2],'utf8');
const core=html.split('//<core>')[1].split('//</core>')[0];
eval(core+';global.analyze=analyze;');
const r=analyze(fs.readFileSync(process.argv[3],'utf8'),Number(process.argv[4]));
console.log(JSON.stringify({net:r.net,closed:r.closed,dd:r.maxDDpct}));
"""

def make_file(path, seed):
    random.seed(seed)
    fills, d = [], datetime.date(2026, 1, 29)
    for day in range(45):
        dt = d + datetime.timedelta(days=day)
        if dt.weekday() >= 5:
            continue
        for _ in range(random.randint(5, 30)):
            s = random.choice(["AAA", "BBB", "CCC", "DDD"]); q = random.choice([100, 100, 200, 413])
            p = round(random.uniform(10, 50), 2); side = random.choice([1, -1])
            fee = 0.02 if side == -1 else 0
            fills.append((dt, s, q * side, p, round(-side * q * p - fee, 2)))
    with open(path, "w") as f:
        f.write("History: Individual (Z0)\nFrom: 01/01/2026\nTo: 12/31/2026\nAll Activity\n\n")
        f.write('"Date","Description","Symbol","Quantity","Price","Amount","Commission","Fees","Type"\n')
        for i, (dt, s, q, p, a) in sorted(enumerate(fills), key=lambda x: (x[1][0], x[0]), reverse=True):
            act = "YOU BOUGHT" if q > 0 else "YOU SOLD"
            f.write(f'"{dt:%m/%d/%Y}","{act} {s} INC ({s}) (Margin)","{s}","{q}","${p:.2f}","${a:,.2f}","$0.00","$0.00","Margin"\n')

def main():
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        for seed in range(1, 6):
            csv = os.path.join(tmp, f"r{seed}.csv"); make_file(csv, seed)
            out = subprocess.run([sys.executable, PY, csv, "--capital", "30000", "--out", os.path.join(tmp, "o")],
                                 capture_output=True, text=True).stdout
            py_net = float(re.search(r"Net realized P&L: \$(-?[\d,\.]+)", out).group(1).replace(",", ""))
            py_closed = int(re.search(r"Closed trades: (\d+)", out).group(1))
            py_dd = float(re.search(r"\(([-\d\.]+)% of peak", out).group(1))
            js = subprocess.run(["node", "-e", JS, "x", os.path.join(ROOT, "index.html"), csv, "30000"],
                                capture_output=True, text=True).stdout
            import json; j = json.loads(js)
            same = abs(j["net"] - py_net) < 0.01 and j["closed"] == py_closed and abs(j["dd"] - py_dd) < 0.01
            print(("PASS" if same else "FAIL"), f"seed {seed}: py net {py_net} / js net {j['net']:.2f}, closed {py_closed}/{j['closed']}")
            ok &= same
    sys.exit(0 if ok else 1)

main()

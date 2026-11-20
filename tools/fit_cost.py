#!/usr/bin/env python3
"""Fit the linear time model of the playbook. Standard library only.

  time per token  = a + b * misses
  time per round  = a + b * rows + c * rows * miss_rate      (speculative decoding)

Usage:
  python3 fit_cost.py runs.csv --y ms --x misses
  python3 fit_cost.py rounds.csv --y ms --x rows,rows_x_miss
  python3 fit_cost.py --demo

Input: CSV with a header. --y names the time column (ms), --x one or more regressor columns.
You need at least as many rows as coefficients plus 1, taken at different values of x
(for example 3 runs with different VRAM budgets for experts).

Output: the coefficients, R^2, and for a single regressor the ceiling with x = 0
(1000 / a tok/s when y is ms per token) plus what a cut in x would give.
"""
import argparse
import csv
import io
import sys

DEMO = """misses,ms
60,40.2
45,32.4
30,25.1
15,17.4
"""  # synthetic: about 10 ms + 0.5 ms per miss


def solve(a, b):
    """Gaussian elimination with partial pivoting for a small dense system."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            sys.exit("the regressors are collinear or constant: vary x between runs")
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (m[i][n] - sum(m[i][c] * x[c] for c in range(i + 1, n))) / m[i][i]
    return x


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--y", default="ms", help="time column (default ms)")
    ap.add_argument("--x", default="misses", help="regressor columns, comma separated (default misses)")
    ap.add_argument("--demo", action="store_true", help="run on a built-in example")
    args = ap.parse_args()

    if args.demo:
        src = io.StringIO(DEMO)
    elif args.csv:
        src = open(args.csv, newline="")
    else:
        ap.error("give a CSV file or --demo")
    rows = list(csv.DictReader(src))
    xs = [c.strip() for c in args.x.split(",") if c.strip()]
    try:
        y = [float(r[args.y]) for r in rows]
        feats = [[1.0] + [float(r[c]) for c in xs] for r in rows]
    except (KeyError, ValueError) as e:
        sys.exit(f"bad column or value: {e}")
    k = len(xs) + 1
    if len(rows) < k + 1:
        sys.exit(f"need at least {k + 1} rows for {k} coefficients, got {len(rows)}")

    xtx = [[sum(f[i] * f[j] for f in feats) for j in range(k)] for i in range(k)]
    xty = [sum(f[i] * yi for f, yi in zip(feats, y)) for i in range(k)]
    coef = solve(xtx, xty)
    pred = [sum(c * v for c, v in zip(coef, f)) for f in feats]
    mean = sum(y) / len(y)
    ss_tot = sum((v - mean) ** 2 for v in y)
    ss_res = sum((v - p) ** 2 for v, p in zip(y, pred))
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")

    terms = " + ".join(f"{c:.4g} * {name}" for c, name in zip(coef[1:], xs))
    print(f"{args.y} = {coef[0]:.4g} + {terms}      R^2 = {r2:.4f}   (n = {len(rows)})")
    if coef[0] <= 0:
        print("the constant came out <= 0: the model does not fit, or x does not vary enough")
        return
    if len(xs) == 1:
        a, b = coef
        print(f"constant part: {a:.2f} {args.y}  ->  ceiling with {xs[0]} = 0: {1000 / a:.1f} per second")
        print(f"{'run':>4} {xs[0]:>10} {args.y:>9} {'fit':>9} {'x term share':>13}")
        for i, (f, yi, p) in enumerate(zip(feats, y, pred), 1):
            print(f"{i:>4} {f[1]:>10.2f} {yi:>9.2f} {p:>9.2f} {b * f[1] / p * 100:>12.0f}%")
        cur = max(feats, key=lambda f: f[1])[1]
        print(f"what a cut in {xs[0]} gives, from {cur:.1f}:")
        for cut in (0.25, 0.5, 0.75):
            t = a + b * cur * (1 - cut)
            print(f"  -{int(cut * 100)}%: {t:.1f} {args.y}  ({1000 / t:.1f} per second)")
        print("If the x term share is small, work on the constant part instead.")
    else:
        print(f"constant part: {coef[0]:.2f} {args.y}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Expert cache simulator on a router trace. Standard library only.

It answers the first questions of the playbook before any engine work:
  - is routing skewed (effective experts per layer, coverage of the top-S)?
  - does a static hot set beat a random one at my VRAM budget?
  - how far is a live cache from the best possible one (Belady)?

Usage:
  python3 route_sim.py trace.jsonl --fraction 0.5
  python3 route_sim.py trace.jsonl --slots 64 --phase decode --json
  python3 route_sim.py --demo skewed --fraction 0.3
  python3 route_sim.py --demo uniform --fraction 0.3

Trace format: JSON Lines, one line per (token, layer):
  {"t": 0, "layer": 0, "experts": [12, 45, 301, 7]}
  optional field: "phase": "prefill" | "decode"   (filter with --phase)
"t" is the token index in the order the engine processed it.

Method: the first --split share of tokens builds the profile, the rest is the test part.
Every policy starts from the static set (top-S by profile) and is scored on the test part only.

Policies:
  random   expected hits of a random set of S experts (S / N)
  static   top-S by the profile, never changes
  oracle   top-S by the test part itself (the best static set, needs the future)
  lru      on a miss, evict the least recently used expert and insert the missed one
  heat     counters with decay; an expert moves up when its heat is above
           hyst x (coldest resident) + 1, at most --swaps moves per token per layer
  belady   on a miss, evict the expert whose next use is farthest (needs the future)

This is a generic model. Your engine's cache differs in details (global move budget,
async copies, admission rules), so read the output as the size of the effect.
"""
import argparse
import json
import math
import random
import sys
from collections import Counter, OrderedDict, defaultdict


def load_trace(path, phase):
    layers = defaultdict(list)
    with open(path) as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                if phase and r.get("phase", phase) != phase:
                    continue
                layers[int(r["layer"])].append((int(r["t"]), [int(e) for e in r["experts"]]))
            except (ValueError, KeyError, TypeError) as e:
                sys.exit(f"{path}:{n}: bad line ({e})")
    for L in layers:
        layers[L].sort(key=lambda x: x[0])
    return layers


def demo_trace(kind, n_layers=4, n_experts=128, top_k=4, n_tokens=4000, seed=7):
    """Synthetic trace. 'skewed': Zipf-like global skew. 'uniform': no global skew,
    but each 200-token segment (an "answer") has its own small working set."""
    rng = random.Random(seed)
    layers = defaultdict(list)
    ids = list(range(n_experts))
    for L in range(n_layers):
        if kind == "skewed":
            w = [1.0 / (i + 1) ** 1.1 for i in range(n_experts)]
            rng.shuffle(w)
            for t in range(n_tokens):
                picks = set()
                while len(picks) < top_k:
                    picks.add(rng.choices(ids, weights=w)[0])
                layers[L].append((t, sorted(picks)))
        else:
            work = []
            for t in range(n_tokens):
                if t % 200 == 0:
                    work = rng.sample(ids, n_experts // 4)
                pool = work if rng.random() < 0.9 else ids
                layers[L].append((t, sorted(rng.sample(pool, top_k))))
    return layers


def effective_experts(counts):
    total = sum(counts.values())
    if not total:
        return 0.0
    h = -sum(c / total * math.log(c / total) for c in counts.values() if c)
    return math.exp(h)


def top_set(counts, s, n_experts):
    order = sorted(range(n_experts), key=lambda e: (-counts.get(e, 0), e))
    return set(order[:s])


def run_static(steps, resident):
    hits = total = 0
    for picks in steps:
        for e in picks:
            total += 1
            hits += e in resident
    return hits, total


def run_lru(steps, start, counts):
    order = OrderedDict((e, None) for e in sorted(start, key=lambda e: counts.get(e, 0)))
    hits = total = moves = 0
    for picks in steps:
        for e in picks:
            total += 1
            if e in order:
                hits += 1
                order.move_to_end(e)
            else:
                order.popitem(last=False)
                order[e] = None
                moves += 1
    return hits, total, moves


def run_heat(steps, start, decay, decay_every, hyst, swaps):
    resident = set(start)
    heat = defaultdict(float)
    hits = total = moves = 0
    for t, picks in enumerate(steps, 1):
        missed = []
        for e in picks:
            total += 1
            if e in resident:
                hits += 1
            else:
                missed.append(e)
            heat[e] += 1.0
        if t % decay_every == 0:
            for e in heat:
                heat[e] *= decay
        for _ in range(swaps):
            cand = [e for e in missed if e not in resident]
            if not cand:
                break
            up = max(cand, key=lambda e: heat[e])
            down = min(resident, key=lambda e: heat[e])
            if heat[up] > heat[down] * hyst + 1.0:
                resident.remove(down)
                resident.add(up)
                moves += 1
            else:
                break
    return hits, total, moves


def run_belady(steps, start):
    flat = [e for picks in steps for e in picks]
    nxt = [0] * len(flat)
    last = {}
    for i in range(len(flat) - 1, -1, -1):
        nxt[i] = last.get(flat[i], math.inf)
        last[flat[i]] = i
    resident = {e: last.get(e, math.inf) for e in start}  # expert -> position of its next use
    hits = moves = 0
    for i, e in enumerate(flat):
        if e in resident:
            hits += 1
        else:
            victim = max(resident, key=resident.get)
            if resident[victim] <= nxt[i]:
                continue  # the missed expert is needed later than every resident: do not insert
            del resident[victim]
            moves += 1
        resident[e] = nxt[i]
    return hits, len(flat), moves


def simulate_layer(seq, args):
    steps_all = [p for _, p in seq]
    cut = int(len(steps_all) * args.split)
    train, test = steps_all[:cut], steps_all[cut:]
    if not train or not test:
        return None
    n = args.experts or (max(e for p in steps_all for e in p) + 1)
    s = args.slots if args.slots else max(1, round(args.fraction * n))
    s = min(s, n)
    c_all = Counter(e for p in steps_all for e in p)
    c_train = Counter(e for p in train for e in p)
    c_test = Counter(e for p in test for e in p)
    start = top_set(c_train, s, n)
    st_h, total = run_static(test, start)
    or_h, _ = run_static(test, top_set(c_test, s, n))
    lru_h, _, lru_m = run_lru(test, start, c_train)
    heat_h, _, heat_m = run_heat(test, start, args.decay, args.decay_every, args.hyst, args.swaps)
    bel_h, _, bel_m = run_belady(test, start)
    return {
        "experts": n, "slots": s, "tokens_test": len(test), "picks_test": total,
        "effective_experts": round(effective_experts(c_all), 1),
        "random": s / n, "static": st_h / total, "oracle": or_h / total,
        "lru": lru_h / total, "heat": heat_h / total, "belady": bel_h / total,
        "lru_moves_per_token": lru_m / len(test), "heat_moves_per_token": heat_m / len(test),
        "belady_moves_per_token": bel_m / len(test),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trace", nargs="?", help="router trace, JSON Lines")
    ap.add_argument("--demo", choices=["skewed", "uniform"], help="run on a synthetic trace instead")
    ap.add_argument("--phase", help="keep only lines with this phase")
    ap.add_argument("--slots", type=int, help="experts in VRAM per layer")
    ap.add_argument("--fraction", type=float, default=0.5, help="share of a layer's experts in VRAM (default 0.5)")
    ap.add_argument("--experts", type=int, help="experts per layer (default: max id + 1)")
    ap.add_argument("--split", type=float, default=0.5, help="share of tokens used to build the profile (default 0.5)")
    ap.add_argument("--decay", type=float, default=0.9, help="heat policy: decay factor (default 0.9)")
    ap.add_argument("--decay-every", type=int, default=256, help="heat policy: tokens between decays (default 256)")
    ap.add_argument("--hyst", type=float, default=1.25, help="heat policy: hysteresis factor (default 1.25)")
    ap.add_argument("--swaps", type=int, default=1, help="heat policy: moves per token per layer (default 1)")
    ap.add_argument("--json", action="store_true", help="print JSON")
    args = ap.parse_args()

    if args.demo:
        layers = demo_trace(args.demo)
    elif args.trace:
        layers = load_trace(args.trace, args.phase)
    else:
        ap.error("give a trace file or --demo")
    if not layers:
        sys.exit("no trace lines after filtering")

    rows = {}
    for L in sorted(layers):
        r = simulate_layer(layers[L], args)
        if r:
            rows[L] = r
    if not rows:
        sys.exit("trace too short for the chosen --split")

    keys = ["random", "static", "oracle", "lru", "heat", "belady"]
    picks = sum(r["picks_test"] for r in rows.values())
    agg = {k: sum(r[k] * r["picks_test"] for r in rows.values()) / picks for k in keys}
    for k in ("lru_moves_per_token", "heat_moves_per_token", "belady_moves_per_token"):
        agg[k] = sum(r[k] for r in rows.values())  # all layers together, per token
    gap = (agg["static"] - agg["random"]) * 100
    verdict = ("weak skew: do not count on a static profile, the live cache is the main mechanism"
               if gap < 10 else "skewed: a static profile is worth having, add a live cache on top")

    if args.json:
        print(json.dumps({"layers": rows, "all": agg, "static_minus_random_points": round(gap, 1),
                          "hint": verdict}, indent=1))
        return

    print(f"{'layer':>5} {'N':>5} {'S':>5} {'eff':>7} " + " ".join(f"{k:>7}" for k in keys))
    for L, r in rows.items():
        print(f"{L:>5} {r['experts']:>5} {r['slots']:>5} {r['effective_experts']:>7} "
              + " ".join(f"{r[k] * 100:>6.1f}%" for k in keys))
    print(f"{'ALL':>5} {'':>5} {'':>5} {'':>7} " + " ".join(f"{agg[k] * 100:>6.1f}%" for k in keys))
    print()
    print(f"moves per token, all layers: lru {agg['lru_moves_per_token']:.2f}, "
          f"heat {agg['heat_moves_per_token']:.2f}, belady {agg['belady_moves_per_token']:.2f}")
    print(f"static minus random: {gap:.1f} points -> {verdict}")
    print(f"live cache headroom (belady minus heat): {(agg['belady'] - agg['heat']) * 100:.1f} points")
    print("The 10 point threshold is a heuristic. N = experts per layer, S = slots in VRAM, "
          "eff = exp(entropy) of picks.")


if __name__ == "__main__":
    main()

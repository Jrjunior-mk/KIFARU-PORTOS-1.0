"""``kifaru-sim`` command line.

    kifaru-sim list
    kifaru-sim run --scenarios all --hours 12 --reps 5 --out reports/
    kifaru-sim run --scenarios rolling_clearance,arrivals_+50 --set arrivals_per_hour=60 --set static_bays=4
    kifaru-sim sumo-export --out sumo/ --hours 12
    kifaru-sim v2 --n 300000 --out reports/            # RCS v2 chain model: Section 9 tables (modelled)
    kifaru-sim v2-sweep --factor token_coverage --values 0.3,0.5,0.7,0.9
    kifaru-sim v2-gate --set avg_loading_pct=85 --baseline 23.3
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import fields

from . import scenarios as scn
from .model import SimConfig
from .report import compare, to_markdown, write_report


def _parse_set(items: list[str] | None) -> dict:
    out: dict = {}
    types = {f.name: f.type for f in fields(SimConfig)}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"--set expects key=value, got '{item}'")
        k, v = item.split("=", 1)
        if k not in types:
            raise SystemExit(f"unknown SimConfig field '{k}'. Fields: {', '.join(sorted(types))}")
        t = str(types[k])
        if "bool" in t:
            out[k] = v.lower() in ("1", "true", "yes")
        elif "int" in t and "float" not in t:
            out[k] = int(v)
        elif "float" in t:
            out[k] = float(v)
        else:
            out[k] = v
    return out


def _parse_v2_set(items: list[str] | None) -> dict:
    """``--set key=value`` for ChainParams fields (bool, int, float)."""
    from .rcs_v2 import ChainParams

    out: dict = {}
    types = {f.name: f.type for f in fields(ChainParams)}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"--set expects key=value, got '{item}'")
        k, v = item.split("=", 1)
        if k not in types or k == "stream_mix":
            raise SystemExit(f"unknown ChainParams field '{k}'. Fields: {', '.join(sorted(types))}")
        t = str(types[k])
        if "bool" in t:
            out[k] = v.lower() in ("1", "true", "yes")
        elif t == "int":
            out[k] = int(v)
        else:
            out[k] = float(v)
    return out


def _add_v2_common(sp) -> None:
    sp.add_argument("--n", type=int, default=None, help="trucks per run (default 200000)")
    sp.add_argument("--seed", type=int, default=None)
    sp.add_argument("--set", action="append", default=[], help="override a ChainParams field, key=value")


def _v2_params(a):
    from .rcs_v2 import ChainParams

    kw = _parse_v2_set(a.set)
    if a.n is not None:
        kw["n"] = a.n
    if a.seed is not None:
        kw["seed"] = a.seed
    return ChainParams(**kw)


def _run_v2(a) -> int:
    import os

    from .rcs_v2 import tables_markdown

    md = tables_markdown(_v2_params(a))
    print(md)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        path = os.path.join(a.out, f"{a.stem}.md")
        with open(path, "w", encoding="utf8") as fh:
            fh.write(md)
        print(f"\nwritten: {path}", file=sys.stderr)
    return 0


def _run_v2_sweep(a) -> int:
    import json

    from .experiments import sweep
    from .rcs_v2 import SHARE_KEYS

    values = [float(x) for x in a.values.split(",") if x.strip()]
    res = sweep(a.factor, values, _v2_params(a))
    if a.json:
        print(json.dumps(res, indent=2))
        return 0
    cols = ["value", *SHARE_KEYS, "truck_hours_saved_per_day", "truck_hours_saved_first_station", "false_clear_rate"]
    print(f"# sweep of {a.factor} (modelled)")
    print("| " + " | ".join(cols) + " |")
    print("|" + "---|" * len(cols))
    for r in res["rows"]:
        print("| " + " | ".join(f"{r[c]:.3g}" if isinstance(r[c], float) else str(r[c]) for c in cols) + " |")
    return 0


def _run_v2_gate(a) -> int:
    import json

    from .experiments import evaluate_gate, replicate, tornado
    from .rcs_v2 import run_chain

    params = _v2_params(a)
    res = run_chain(params)
    gate = evaluate_gate(res, baseline_share=a.baseline, min_cut_points=a.min_cut, max_false_clear=a.max_false_clear, max_port_reweigh_pct=a.max_port_reweigh)
    rep = replicate(params, reps=a.reps) if a.reps > 1 else None
    tor = tornado(params) if a.tornado else None
    if a.json:
        print(json.dumps({"gate": gate, "replications": rep, "tornado": tor, "result": res.to_dict()}, indent=2))
        return 0
    print("# RCS v2 go/no-go gate (Section 10.9, modelled)\n")
    for c in gate["checks"]:
        print(f"[{'ok' if c['ok'] else 'FAIL'}] {c['name']}: {c['value']} (threshold {c['threshold']}) — {c['detail']}")
    print(f"\n{'PROCEED' if gate['proceed'] else 'DO NOT PROCEED'}: {gate['recommendation']}")
    if rep:
        print(f"\n{rep['reps']} replications, 95 % CI:")
        for k in ("road_only_static", "v2_road_static", "v2_port_reweigh", "first_station_lane", "first_station_static", "false_clear_rate"):
            o = rep["outputs"][k]
            print(f"  {k:28s} {o['mean']:.3f}  [{o['ci_low']:.3f}, {o['ci_high']:.3f}]")
    if tor:
        print("\nTornado (swing of v2 road stop share, percentage points):")
        for r in tor:
            print(f"  {r['factor']:18s} {r['low']:>6g} → {r['output_low']:6.2f}   {r['high']:>6g} → {r['output_high']:6.2f}   swing {r['swing']:.2f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="kifaru-sim", description="KIFARU PORTOS weighing-station scenario simulator (SimPy). All results are modelled.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list scenarios")
    r = sub.add_parser("run", help="run scenarios and write a comparison report")
    r.add_argument("--scenarios", default="all", help="comma-separated scenario names or 'all'")
    r.add_argument("--hours", type=float, default=12.0)
    r.add_argument("--reps", type=int, default=5)
    r.add_argument("--seed", type=int, default=1000)
    r.add_argument("--out", default="reports/")
    r.add_argument("--stem", default="scenario-comparison")
    r.add_argument("--set", action="append", default=[], help="override a SimConfig field for every scenario, key=value")
    r.add_argument("--quiet", action="store_true")
    s = sub.add_parser("sumo-export", help="write SUMO route/network inputs for the arrival profile (SUMO itself optional)")
    s.add_argument("--out", default="sumo/")
    s.add_argument("--hours", type=float, default=12.0)
    s.add_argument("--seed", type=int, default=1000)
    s.add_argument("--set", action="append", default=[])
    v2 = sub.add_parser("v2", help="RCS v2 chain model: Section 9 tables (Monte Carlo, modelled)")
    _add_v2_common(v2)
    v2.add_argument("--out", default=None, help="directory for the Markdown report")
    v2.add_argument("--stem", default="rcs-v2-tables")
    v2s = sub.add_parser("v2-sweep", help="one-factor sweep of the RCS v2 chain model")
    _add_v2_common(v2s)
    v2s.add_argument("--factor", required=True)
    v2s.add_argument("--values", required=True, help="comma-separated values")
    v2s.add_argument("--json", action="store_true")
    v2g = sub.add_parser("v2-gate", help="Section 10.9 go/no-go gate with replications and tornado sensitivity")
    _add_v2_common(v2g)
    v2g.add_argument("--baseline", type=float, default=None, help="measured road-only stop share (%%); defaults to the model's own")
    v2g.add_argument("--min-cut", type=float, default=10.0)
    v2g.add_argument("--max-false-clear", type=float, default=0.01)
    v2g.add_argument("--max-port-reweigh", type=float, default=20.0)
    v2g.add_argument("--reps", type=int, default=30)
    v2g.add_argument("--tornado", action="store_true")
    v2g.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    if a.cmd == "v2":
        return _run_v2(a)
    if a.cmd == "v2-sweep":
        return _run_v2_sweep(a)
    if a.cmd == "v2-gate":
        return _run_v2_gate(a)

    if a.cmd == "list":
        for name in scn.list_scenarios():
            print(f"{name:26s} {scn.DESCRIPTIONS.get(name, '')}")
        return 0
    if a.cmd == "sumo-export":
        from .sumo_adapter import export_inputs, sumo_status

        cfg = scn.BASE.with_overrides(hours=a.hours, seed=a.seed, **_parse_set(a.set))
        paths = export_inputs(cfg, a.out)
        print(sumo_status().message)
        for k, v in paths.items():
            print(f"{k:12s} {v}")
        return 0

    names = scn.list_scenarios() if a.scenarios == "all" else [x.strip() for x in a.scenarios.split(",") if x.strip()]
    unknown = [n for n in names if n not in scn.SCENARIOS]
    if unknown:
        raise SystemExit(f"unknown scenario(s): {unknown}. Use 'kifaru-sim list'.")
    cmp = compare(names, hours=a.hours, reps=a.reps, base_seed=a.seed, overrides=_parse_set(a.set))
    md, js = write_report(cmp, a.out, stem=a.stem)
    if not a.quiet:
        print(to_markdown(cmp))
    print(f"\nwritten: {md}\nwritten: {js}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

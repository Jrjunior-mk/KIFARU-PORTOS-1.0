"""Tests for the RCS v2 chain model, experiments and CLI (all modelled)."""
from __future__ import annotations

import json

import pytest

from kifaru_sim import ChainParams, evaluate_gate, replicate, run_chain, sweep, tornado
from kifaru_sim.cli import main
from kifaru_sim.rcs_v2 import SHARE_KEYS, lane_capacity_per_hour, mixed_traffic_table, port_truck_table, tables_markdown

N = 50_000


def _p(**kw) -> ChainParams:
    return ChainParams(**{"n": N, "seed": 7, **kw})


def test_output_shape_matches_contract():
    d = run_chain(_p()).to_dict()
    assert set(d["shares"]) == set(SHARE_KEYS)
    for key in ("inputs", "truck_hours_saved_per_day", "truck_hours_saved_first_station", "false_clear_rate", "lane_peak_per_hour",
                "lane_capacity_per_hour", "lane_ok", "total_reweighs_v1", "total_reweighs_v2", "assumptions", "label"):
        assert key in d
    assert d["label"] == "MODELLED"
    assert d["inputs"]["stream_mix"] == pytest.approx({"port": 0.54, "origin": 0.36, "untokened": 0.1})
    assert all(0.0 <= v <= 100.0 for v in d["shares"].values())
    json.dumps(d)  # serialisable


def test_deterministic_for_seed():
    a, b = run_chain(_p()).to_dict(), run_chain(_p()).to_dict()
    assert a == b
    assert run_chain(_p(seed=8)).to_dict()["shares"] != a["shares"]


def test_road_only_share_grows_with_loading():
    rows = port_truck_table(_p())
    vals = [r["road_only_static"] for r in rows]
    assert vals == sorted(vals) and vals[-1] > vals[0] + 15
    # plan figures at the defaults: 9.0 / 14.4 / 23.3 / 35.5 — accept ±2.5 points on a 50 k run
    for row, expect in zip(rows, (9.0, 14.4, 23.3, 35.5), strict=True):
        assert row["road_only_static"] == pytest.approx(expect, abs=2.5)
    # port re-weigh share moves with loading too (4.2 / 7.9 / 14.9 / 25.5)
    for row, expect in zip(rows, (4.2, 7.9, 14.9, 25.5), strict=True):
        assert row["v2_port_reweigh"] == pytest.approx(expect, abs=2.5)


def test_v2_road_static_falls_as_coverage_rises():
    vals = [run_chain(_p(token_coverage=c)).shares["v2_road_static"] for c in (0.3, 0.5, 0.7, 0.9, 1.0)]
    assert vals == sorted(vals, reverse=True)
    assert vals[-1] < 5.0  # full coverage: audits + mismatches only
    rows = mixed_traffic_table(_p())
    lane = [r["first_station_lane"] for r in rows]
    static = [r["first_station_static"] for r in rows]
    assert lane == sorted(lane, reverse=True) and static == sorted(static, reverse=True)
    assert rows[-1]["first_station_static"] < 3.0
    assert rows[-1]["later_station_static"] < 0.5 and rows[-1]["later_station_lane"] < 6.0


def test_allowance_lowers_port_reweigh_and_road_stops():
    base = run_chain(_p()).shares
    alw = run_chain(_p(allowance_pct=5.0)).shares
    assert alw["v2_port_reweigh"] < base["v2_port_reweigh"] / 3
    assert alw["road_only_static"] == base["road_only_static"]  # the road-only baseline column never applies the allowance
    assert alw["road_only_with_allowance"] == base["road_only_with_allowance"]  # comparison column uses the 5 % policy bound by default
    assert alw["untokened_static"] < base["untokened_static"]
    assert alw["v2_road_static"] < base["v2_road_static"]
    assert base["road_only_with_allowance"] < base["road_only_static"]


def test_legal_grade_scales_reduce_reweighs():
    base = run_chain(_p()).shares
    port_lg = run_chain(_p(port_legal_grade=True)).shares
    lane_lg = run_chain(_p(lane_legal_grade=True)).shares
    assert port_lg["v2_port_reweigh"] < base["v2_port_reweigh"]
    assert lane_lg["untokened_static"] < base["untokened_static"]


def test_false_clear_rate_within_target_at_defaults():
    r = run_chain(_p())
    assert r.false_clear_rate <= 0.01


def test_lane_capacity_and_peak():
    assert lane_capacity_per_hour() == pytest.approx(370.4, abs=0.5)
    r = run_chain(_p())
    assert r.lane_capacity_per_hour == pytest.approx(370.4, abs=0.5)
    assert 80 < r.lane_peak_per_hour < 150 and r.lane_ok
    assert run_chain(_p(peak_per_hour=2000)).lane_ok is False


def test_truck_hours_follow_the_plan_formula():
    r = run_chain(_p())
    expected = (r.shares["road_only_static"] - r.shares["v2_road_static"]) * 8.0  # one point = 8 truck-hours at 8000/day, 6 min
    assert r.truck_hours_saved_per_day == pytest.approx(expected, rel=1e-6)
    assert r.truck_hours_saved_first_station > 100


def test_stream_mix_override_and_validation():
    r = run_chain(_p(stream_mix={"port": 1.0, "origin": 0.0, "untokened": 0.0}))
    assert r.params.resolved_mix()["port"] == 1.0
    assert r.shares["first_station_static"] < 1.0
    with pytest.raises(ValueError):
        ChainParams(stream_mix={"port": 0, "origin": 0, "untokened": 0}).resolved_mix()
    with pytest.raises(ValueError):
        run_chain(_p(n=0))


def test_sweep_matches_contract_shape():
    res = sweep("avg_loading_pct", [75, 85], {"n": N, "seed": 3})
    assert res["factor"] == "avg_loading_pct" and res["label"] == "MODELLED"
    assert [r["value"] for r in res["rows"]] == [75, 85]
    for key in (*SHARE_KEYS, "truck_hours_saved_per_day", "truck_hours_saved_first_station", "false_clear_rate"):
        assert key in res["rows"][0]
    assert res["rows"][1]["road_only_static"] > res["rows"][0]["road_only_static"]
    cov = sweep("token_coverage", [0.3, 0.9], _p())
    assert cov["rows"][0]["first_station_lane"] > cov["rows"][1]["first_station_lane"]
    with pytest.raises(ValueError):
        sweep("not_a_factor", [1], _p())


def test_replicate_and_tornado():
    rep = replicate(_p(n=20_000), reps=4)
    o = rep["outputs"]["v2_road_static"]
    assert o["n"] == 4 and o["ci_low"] <= o["mean"] <= o["ci_high"]
    assert rep["seeds"] == [7, 8, 9, 10]
    tor = tornado(_p(n=20_000), {"avg_loading_pct": (75.0, 90.0), "token_coverage": (0.5, 1.0)})
    assert len(tor) == 2 and tor[0]["swing"] >= tor[1]["swing"]
    assert all({"factor", "low", "high", "output_low", "output_high", "swing", "reference"} <= set(r) for r in tor)


def test_gate_evaluation():
    r = run_chain(_p())
    g = evaluate_gate(r)
    assert g["proceed"] is True and g["label"] == "MODELLED"
    assert {c["name"] for c in g["checks"]} == {"road_stop_share_cut_points", "false_clear_rate", "port_reweigh_share_pct", "lane_capacity"}
    # a measured baseline barely above the v2 share fails the 10-point cut
    g2 = evaluate_gate(r.to_dict(), baseline_share=r.shares["v2_road_static"] + 5.0)
    assert g2["proceed"] is False and not g2["checks"][0]["ok"]
    # a tight port re-weigh threshold fails that check only
    g3 = evaluate_gate(r, max_port_reweigh_pct=1.0)
    assert not g3["checks"][2]["ok"] and g3["checks"][1]["ok"]


def test_tables_markdown_and_cli(tmp_path, capsys):
    md = tables_markdown(_p())
    assert "Port trucks by average loading" in md and "Mixed traffic" in md and "MODELLED" in md
    assert main(["v2", "--n", str(N), "--seed", "7", "--out", str(tmp_path), "--stem", "t"]) == 0
    assert (tmp_path / "t.md").exists()
    assert main(["v2-sweep", "--factor", "token_coverage", "--values", "0.5,0.9", "--n", "20000"]) == 0
    assert "sweep of token_coverage" in capsys.readouterr().out
    assert main(["v2-gate", "--n", "20000", "--reps", "2", "--tornado", "--set", "avg_loading_pct=85"]) == 0
    out = capsys.readouterr().out
    assert "go/no-go" in out and "Tornado" in out
    assert main(["v2-gate", "--n", "20000", "--reps", "1", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["gate"]["label"] == "MODELLED"
    with pytest.raises(SystemExit):
        main(["v2", "--set", "bogus=1"])

"""SmartPort port-process model: conservation, calibration, policy effect, determinism, CLI."""
from __future__ import annotations

from kifaru_sim.cli import main
from kifaru_sim.port_process import KPA_TRUCK_TURNAROUND_H_2023, PortSimConfig, compare, run_port

SMALL = PortSimConfig(hours=6, trucks_per_day=1200, reps=1)


def test_every_arrival_exits_and_kpis_are_sane():
    r = run_port(SMALL, "existing")
    assert r["trucks"] > 100 and r["avg_dwell_h"] > 0 and r["p90_dwell_h"] >= r["avg_dwell_h"] * 0.8
    assert 0 < r["gate_in_utilisation"] < 1 and 0 < r["weigh_utilisation"] < 1


def test_smartport_cuts_dwell_wait_and_weigh_service():
    out = compare(SMALL)
    e, s = out["scenarios"]["existing"], out["scenarios"]["smartport"]
    assert s["avg_dwell_h"] < e["avg_dwell_h"] and s["weigh_service_min"] < e["weigh_service_min"]
    assert out["deltas"]["avg_dwell_h"] < 0 and out["label"] == "MODELLED"


def test_existing_policy_calibrated_to_kpa_truck_turnaround():
    e = run_port(PortSimConfig(), "existing")
    assert abs(e["avg_dwell_h"] - KPA_TRUCK_TURNAROUND_H_2023) < 0.8


def test_deterministic_for_a_seed():
    assert run_port(SMALL, "smartport", seed=5) == run_port(SMALL, "smartport", seed=5)


def test_cli_port(tmp_path, capsys):
    out = tmp_path / "port.md"
    assert main(["port", "--reps", "1", "--hours", "4", "--set", "trucks_per_day=800", "--out", str(out)]) == 0
    assert "Port dwell" in out.read_text(encoding="utf-8") and "MODELLED" in capsys.readouterr().out

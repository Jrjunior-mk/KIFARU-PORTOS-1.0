"""SmartPort port-process layer: stages, visit lifecycle with per-stage validation, automatic stage 7 from the port gate-out
weigh node, KPIs with published benchmarks, board, data register, port simulation and agency adapters (RTM section M)."""
from __future__ import annotations

from .conftest import h

API = "/api/v1"


def _vehicle(client, auth, plate):
    return next(v for v in client.get(f"{API}/fleet/vehicles", headers=h(auth)).json() if v["plate"] == plate)


STAGE_DATA = {
    "customs_cleared": {"customs_declaration_ref": "KRA-T-1", "trade_direction": "import", "duty_status": "paid", "customs_status": "cleared",
                        "inspection_status": "not_required", "permit_status": "approved"},
    "arrived": {"appointment_valid": True, "queue_length": 9, "queue_wait_s": 900},
    "gate_in": {"gate_in_id": "GATE-18", "access_authorised": True, "vehicle_inspection": "passed", "driver_verified": True, "gate_in_processing_s": 200},
    "yard_allocated": {"terminal_id": "CT2", "yard_block": "B1", "container_position": "B1-01-01", "loading_instruction": "LI-1", "yard_wait_s": 7200},
    "loaded": {"loading_start_at": "2026-11-05T08:00:00+00:00", "loading_end_at": "2026-11-05T08:20:00+00:00", "equipment_id": "RS-1",
               "seal_number": "S-1", "cargo_verification": "matched", "cargo_condition": "good"},
    "weighed": {"gross_kg": 36000, "tare_kg": 14000, "weighing_start_at": "2026-11-05T08:30:00+00:00", "weighing_end_at": "2026-11-05T08:32:00+00:00", "calibration_valid": True},
    "final_cleared": {"cargo_release_status": "approved", "delivery_order_ref": "DO-1", "gate_pass_no": "GP-1", "payment_status": "paid"},
    "gate_out": {"gate_out_id": "GATE-18", "exit_cargo_verified": True, "exit_authorised": True},
    "in_transit": {"route": "A109", "distance_km": 482, "eta_at": "2026-11-06T08:00:00+00:00"},
    "delivered": {"pod_ref": "POD-1", "arrived_destination_at": "2026-11-06T07:00:00+00:00"},
}


def test_stages_metadata(client, operator):
    st = client.get(f"{API}/port/stages", headers=h(operator)).json()
    assert [s["stage"] for s in st][0] == "pre_registered" and len(st) == 11
    weighed = next(s for s in st if s["stage"] == "weighed")
    assert "gross_kg" in weighed["required_fields"] and weighed["agency"]


def test_visit_full_lifecycle_with_validation(client, admin, transporter):
    v = _vehicle(client, admin, "KDE 230G")
    bad = client.post(f"{API}/port/visits", json={"vehicle_id": v["id"], "data": {"cargo_type": "container"}}, headers=h(admin))
    assert bad.status_code == 422
    r = client.post(f"{API}/port/visits", json={"vehicle_id": v["id"], "data": {"truck_type": "flatbed", "cargo_type": "container", "declared_mass_kg": 22000,
                                                                                  "destination": "Nairobi", "appointment_at": "2026-11-05T07:00:00+00:00"}}, headers=h(admin))
    assert r.status_code == 201, r.text
    visit = r.json()
    assert visit["stage"] == "pre_registered" and visit["reference"].startswith("PV-")
    vid = visit["id"]
    # skipping the required data for the next stage is refused with the missing fields listed
    miss = client.post(f"{API}/port/visits/{vid}/advance", json={"stage": "customs_cleared", "data": {"trade_direction": "import"}}, headers=h(admin))
    assert miss.status_code == 422 and "customs_status" in str(miss.json())
    # a transporter may not perform a port-operator stage
    for stage, data in STAGE_DATA.items():
        if stage == "gate_in":
            assert client.post(f"{API}/port/visits/{vid}/advance", json={"stage": stage, "data": data}, headers=h(transporter)).status_code in (403, 404)
        r = client.post(f"{API}/port/visits/{vid}/advance", json={"stage": stage, "data": data}, headers=h(admin))
        assert r.status_code == 200, (stage, r.text)
    out = r.json()
    assert out["stage"] == "delivered" and len(out["timeline"]) == 11
    assert out["net_kg"] == 22000 and out["weight_discrepancy_kg"] == 0
    assert out["kpis"]["dwell_time_s"] is not None and out["kpis"]["dwell_time_s"] >= 0


def test_port_gateout_pass_advances_loaded_visit(client, operator, admin):
    visits = client.get(f"{API}/port/visits", params={"stage": "loaded"}, headers=h(admin)).json()
    seeded = [x for x in visits if x["plate"] == "KDA 412B"]
    assert seeded, "seed should create a loaded visit for KDA 412B"
    sts = client.get(f"{API}/stations", headers=h(operator)).json()
    port = next(s for s in sts if s["code"] == "MBS-GATE18")
    lane = next(ln for ln in port["lanes"] if ln["type"] == "port_gateout")
    v = _vehicle(client, operator, "KDA 412B")
    r = client.post(f"{API}/weighing/simulate", json={"lane_id": lane["id"], "count": 1, "overload_prob": 0.0, "sensor_fault_prob": 0.0, "anpr_misread_prob": 0.0,
                                                      "rfid_missing_prob": 0.0, "clone_prob": 0.0, "unregistered_prob": 0.0, "pavement_temp_c": 30, "vehicle_id": v["id"],
                                                      "force_gvm_kg": 33000, "seed": 77, "oversize_prob": 0.0, "lifted_axle_prob": 0.0}, headers=h(operator))
    assert r.status_code == 201, r.text
    after = client.get(f"{API}/port/visits/{seeded[0]['id']}", headers=h(admin)).json()
    assert after["stage"] == "weighed" and after["gross_kg"] == r.json()[0]["gvm_kg"] and after["weighing_event_id"] == r.json()[0]["id"]


def test_kpis_board_and_benchmarks(client, auditor):
    k = client.get(f"{API}/port/kpis", params={"hours": 72}, headers=h(auditor)).json()
    assert k["visits_total"] >= 1 and set(k["visits_by_stage"]) >= {"pre_registered", "delivered"}
    keys = {b["key"] for b in k["benchmarks"]}
    assert "kpa.truck_turnaround_h_2023" in keys and all(b["source_url"] for b in k["benchmarks"])
    b = client.get(f"{API}/port/board", headers=h(auditor)).json()
    assert len(b["stages"]) == 11 and sum(s["count"] for s in b["stages"]) >= 1


def test_data_register(client, auditor):
    reg = client.get(f"{API}/data/register", headers=h(auditor)).json()
    assert len(reg) >= 40 and {r["classification"] for r in reg} <= {"actual", "published", "estimated", "simulated"}
    assert all(r["source_url"] or r["classification"] in ("estimated", "simulated") for r in reg)
    one = client.get(f"{API}/data/register/kenha.compliance_pct_fy2425", headers=h(auditor)).json()
    assert "98.43" in str(one["value"]) and one["agency"]
    pub = client.get(f"{API}/data/register", params={"classification": "published"}, headers=h(auditor)).json()
    assert pub and all(r["classification"] == "published" for r in pub)
    assert client.get(f"{API}/data/register/nope", headers=h(auditor)).status_code == 404


def test_port_simulation_endpoint(client, auditor):
    r = client.post(f"{API}/port/simulate", json={"hours": 6, "reps": 1, "trucks_per_day": 1200}, headers=h(auditor))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["label"] == "MODELLED" and {"existing", "smartport"} <= set(out["scenarios"])
    assert out["scenarios"]["smartport"]["avg_dwell_h"] < out["scenarios"]["existing"]["avg_dwell_h"]
    assert out["calibration_note"] and out["assumptions"]


def test_agency_adapters_include_kebs_and_kentrade(client, admin):
    names = {i["name"] for i in client.get(f"{API}/integrations", headers=h(admin)).json()}
    assert {"kebs", "kentrade", "kpa", "kra", "kenha", "ntsa"} <= names


def test_tenant_scoping(client, other_transporter, admin):
    mine = client.get(f"{API}/port/visits", headers=h(other_transporter)).json()
    allv = client.get(f"{API}/port/visits", headers=h(admin)).json()
    assert len(mine) < len(allv)
    simba_visit = next(x for x in allv if x["plate"] == "KDA 412B")
    assert client.get(f"{API}/port/visits/{simba_visit['id']}", headers=h(other_transporter)).status_code == 404

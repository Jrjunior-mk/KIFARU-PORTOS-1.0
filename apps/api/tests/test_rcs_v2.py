"""RCS v2 — port-anchored clearance: engine token/dimension rules, token lifecycle through the API, release orders,
permits, registry stats, public token verification and the Monte Carlo chain model endpoint (RTM section L)."""
from __future__ import annotations

from datetime import timedelta

import pytest

from kifaru.services import clearance_engine as ce
from kifaru.services.limits import DEFAULT_LIMITS, LimitSet
from kifaru.services.release_orders import fee_preview

from .conftest import h

API = "/api/v1"


# ----------------------------------------------------------------------------------------------- engine unit tests
def _m(loads, groups, u_frac=0.03, cfg="1+1+2", flags=None):
    axles = [ce.AxleInput(i, load, load * u_frac * 2, g) for i, (load, g) in enumerate(zip(loads, groups, strict=True))]
    return ce.MeasurementInput(sum(loads), (sum(a.u_kg**2 for a in axles)) ** 0.5, axles, cfg, flags or [], {})


VEH = ce.VehicleInput("v1", "KDA 123A", "1+1+2", 14000, 56000)
ID_OK = ce.IdentityInput(0.97, "v1", "rfid+anpr")
NEAR_LIMIT = _m([7900, 9800, 8900, 8900], [1, 2, 3, 3])  # steering 7 900 of 8 000 -> within uncertainty of the limit


def test_near_limit_is_amber_without_token_but_green_with_consistent_token():
    plain = ce.decide(NEAR_LIMIT, ID_OK, VEH, audit_rate=0.0, node_kind="road_mainline", lane_available=True)
    assert plain.decision == "AMBER" and plain.route == "verification_lane"
    tok = ce.TokenInput("t1", "LCT-TEST", "port", 1, gvm_kg=35_400.0)
    with_token = ce.decide(NEAR_LIMIT, ID_OK, VEH, audit_rate=0.0, token=tok, node_kind="road_mainline", lane_available=True)
    assert with_token.decision == "GREEN" and with_token.route == "continue" and with_token.token_consistent is True
    assert any(r.rule == "TOKEN_COVERS_MARGIN" and r.fired for r in with_token.rules)
    assert with_token.margins["token"]["consistent"] is True


def test_token_inconsistent_weight_diverts_to_lane():
    tok = ce.TokenInput("t1", "LCT-TEST", "port", 1, gvm_kg=30_000.0)  # road reads 35.5 t: +18 % -> cargo changed
    r = ce.decide(NEAR_LIMIT, ID_OK, VEH, audit_rate=0.0, token=tok, node_kind="road_mainline", lane_available=True)
    assert r.decision == "AMBER" and r.route == "verification_lane"
    assert any(x["rule"] == "TOKEN_WEIGHT_INCONSISTENT" for x in r.rules_fired)


def test_token_identity_mismatch_is_red_and_certain_overload_stays_red_with_token():
    tok = ce.TokenInput("t1", "LCT-TEST", "port", 1, gvm_kg=35_400.0, identity_match=False)
    r = ce.decide(NEAR_LIMIT, ID_OK, VEH, audit_rate=0.0, token=tok)
    assert r.decision == "RED" and r.route == "static_scale"
    over = _m([9500, 9800, 8900, 8900], [1, 2, 3, 3], u_frac=0.01)
    tok2 = ce.TokenInput("t1", "LCT-TEST", "port", 1, gvm_kg=37_100.0)
    r2 = ce.decide(over, ID_OK, VEH, audit_rate=0.0, token=tok2)
    assert r2.decision == "RED"  # a token never covers a certain overload


def test_expired_or_suspended_token_is_amber():
    for kw in ({"valid": False}, {"status": "suspended"}):
        tok = ce.TokenInput("t1", "LCT-TEST", "road", 3, gvm_kg=35_400.0, **kw)
        r = ce.decide(NEAR_LIMIT, ID_OK, VEH, audit_rate=0.0, token=tok)
        assert r.decision == "AMBER", kw


def test_dimension_over_is_red_unless_permitted_and_lifted_axle_is_amber():
    clear = _m([6000, 8000, 7500, 7500], [1, 2, 3, 3])
    dims = ce.DimensionsInput(length_m=18.0, width_m=2.5, height_m=4.6)
    r = ce.decide(clear, ID_OK, VEH, audit_rate=0.0, dimensions=dims, node_kind="verification_lane")
    assert r.decision == "RED" and any(x["rule"] == "DIMENSION_OVER" for x in r.rules_fired)
    permitted = ce.DimensionsInput(18.0, 2.5, 4.6, permit=ce.PermitInput("SLP-1", 24.0, 3.2, 4.8))
    r2 = ce.decide(clear, ID_OK, VEH, audit_rate=0.0, dimensions=permitted, node_kind="verification_lane")
    assert r2.decision == "GREEN" and r2.token_eligible and any(x["rule"] == "DIMENSION_PERMITTED" for x in r2.rules_fired)
    r3 = ce.decide(clear, ID_OK, VEH, audit_rate=0.0, dimensions=ce.DimensionsInput(lifted_axle=True))
    assert r3.decision == "AMBER" and any(x["rule"] == "LIFTED_AXLE" for x in r3.rules_fired)


def test_routes_by_node_and_port_hold():
    clear = _m([6000, 8000, 7500, 7500], [1, 2, 3, 3])
    assert ce.decide(clear, ID_OK, VEH, audit_rate=0.0, node_kind="port_gateout").route == "continue"
    assert ce.decide(NEAR_LIMIT, ID_OK, VEH, audit_rate=0.0, node_kind="port_gateout").route == "port_reweigh"
    assert ce.decide(NEAR_LIMIT, ID_OK, VEH, audit_rate=0.0, node_kind="verification_lane").route == "static_scale"
    assert ce.decide(NEAR_LIMIT, ID_OK, VEH, audit_rate=0.0, node_kind="road_mainline", lane_available=False).route == "static_scale"
    over = _m([9500, 9800, 8900, 8900], [1, 2, 3, 3], u_frac=0.01)
    assert ce.decide(over, ID_OK, VEH, audit_rate=0.0, node_kind="port_gateout").route == "hold"


def test_discretion_allowance_turns_near_limit_amber_into_green():
    lim = LimitSet(version="test-allowance", discretion_allowance_pct=4.0)
    r = ce.decide(NEAR_LIMIT, ID_OK, VEH, audit_rate=0.0, limits=lim)
    assert r.decision == "GREEN" and r.margins["gvm"]["allowance_kg"] > 0
    assert any(x["rule"] == "DISCRETION_ALLOWANCE" for x in r.rules_fired)


def test_audit_rate_by_tier_uses_token_tier():
    clear = _m([6000, 8000, 7500, 7500], [1, 2, 3, 3])
    tok = ce.TokenInput("t1", "LCT-TEST", "onboard", 4, gvm_kg=29_000.0)
    r = ce.decide(clear, ID_OK, VEH, audit_rate=0.0, audit_seed=7, token=tok, audit_rate_by_tier={4: 1.0})
    assert r.audit_selected and r.decision == "AMBER"


def test_fee_schedule_and_detention():
    assert DEFAULT_LIMITS.overload_fee(5000) == pytest.approx(2990.0)
    assert DEFAULT_LIMITS.overload_fee(0) == 0.0 and DEFAULT_LIMITS.overload_fee(2500) > DEFAULT_LIMITS.overload_fee(2000)
    assert DEFAULT_LIMITS.detention_fee(3) == 0.0 and DEFAULT_LIMITS.detention_fee(5) == 100.0
    fp = fee_preview(61_000, 56_000)
    assert fp["overload_kg"] == 5000 and fp["fee_usd"] == pytest.approx(2990.0)
    assert DEFAULT_LIMITS.dimension_breaches(23.0, 2.5, 4.0) == ["length 23.00 m > 22.0 m"]


# ----------------------------------------------------------------------------------------------- API flow
def _station(client, auth, code):
    sts = client.get(f"{API}/stations", headers=h(auth)).json()
    return next(s for s in sts if s["code"] == code)


def _lane(st, ltype):
    return next(ln for ln in st["lanes"] if ln["type"] == ltype)


def _vehicle(client, auth, plate):
    return next(v for v in client.get(f"{API}/fleet/vehicles", headers=h(auth)).json() if v["plate"] == plate)


def test_policy_and_trust_tiers(client, operator):
    pol = client.get(f"{API}/rcs/policy", headers=h(operator)).json()
    assert pol["limits_version"] == DEFAULT_LIMITS.version and pol["engine_version"] == ce.ENGINE_VERSION
    assert pol["token_tolerance"]["road"] > pol["token_tolerance"]["port"]
    assert [t["tier"] for t in pol["trust_tiers"]] == [1, 2, 3, 4] and pol["trust_tiers"][3]["audit_rate"] == 1.0
    assert pol["fee_schedule"]["repeat_offence_multiplier"] == 3.0 and len(pol["legal_hooks"]) >= 10
    tiers = client.get(f"{API}/rcs/trust-tiers", headers=h(operator)).json()
    assert tiers[0]["source"] == "port"


def test_port_gateout_issues_token_and_road_station_honours_it(client, operator, auditor):
    port = _station(client, operator, "MBS-GATE18")
    gate = _lane(port, "port_gateout")
    v = _vehicle(client, operator, "KDE 230G")
    # a compliant load at the port exit lane
    r = client.post(f"{API}/weighing/simulate", json={"lane_id": gate["id"], "count": 1, "overload_prob": 0.0, "sensor_fault_prob": 0.0, "anpr_misread_prob": 0.0,
                                                      "rfid_missing_prob": 0.0, "clone_prob": 0.0, "unregistered_prob": 0.0, "pavement_temp_c": 30, "vehicle_id": v["id"],
                                                      "force_gvm_kg": 32000, "seed": 11, "oversize_prob": 0.0, "lifted_axle_prob": 0.0}, headers=h(operator))
    assert r.status_code == 201, r.text
    ev = r.json()[0]
    assert ev["node_kind"] == "port_gateout" and ev["stream"] == "port" and ev["kind"] == "wim"
    assert ev["decision"]["decision"] == "GREEN" and ev["decision"]["route"] == "continue"
    assert ev["decision"]["token_issued_ref"] and ev["decision"]["token_issued_ref"].startswith("LCT-")
    assert ev["height_m"] is not None and ev["length_m"] is not None  # dimension portal at the port lane
    token_ref = ev["decision"]["token_issued_ref"]

    # registry: token visible, active, signed, tier 1
    toks = client.get(f"{API}/rcs/tokens", params={"vehicle_id": v["id"], "status": "active"}, headers=h(auditor)).json()
    assert len(toks) == 1 and toks[0]["token_ref"] == token_ref and toks[0]["source"] == "port" and toks[0]["trust_tier"] == 1
    assert toks[0]["signature_valid"] is True and toks[0]["gvm_kg"] == ev["gvm_kg"] and toks[0]["issuing_station_code"] == "MBS-GATE18"
    look = client.get(f"{API}/rcs/tokens/lookup", params={"plate": "KDE 230G"}, headers=h(operator)).json()
    assert look["token_ref"] == token_ref
    pub = client.get(f"{API}/rcs/tokens/verify/{token_ref}").json()
    assert pub["valid"] is True and pub["signature_valid"] is True and pub["source_label"] == "simulated"
    assert client.get(f"{API}/rcs/tokens/verify/LCT-NOPE").json()["valid"] is False

    # same truck at Mariakani with the same load: token honoured, no stop
    mrk = _station(client, operator, "MRK")
    wim = _lane(mrk, "wim_highspeed")
    r2 = client.post(f"{API}/weighing/simulate", json={"lane_id": wim["id"], "count": 1, "overload_prob": 0.0, "sensor_fault_prob": 0.0, "anpr_misread_prob": 0.0,
                                                       "rfid_missing_prob": 0.0, "clone_prob": 0.0, "unregistered_prob": 0.0, "pavement_temp_c": 30, "vehicle_id": v["id"],
                                                       "force_gvm_kg": 32300, "seed": 12, "oversize_prob": 0.0, "lifted_axle_prob": 0.0}, headers=h(operator))
    ev2 = r2.json()[0]
    assert ev2["node_kind"] == "road_mainline" and ev2["stream"] == "port" and ev2["token_ref"] == token_ref
    assert ev2["decision"]["token_checked_ref"] == token_ref and ev2["decision"]["token_issued_ref"] is None  # port token kept, no road token
    assert ev2["decision"]["decision"] == "GREEN" and ev2["decision"]["route"] == "continue"
    tok = client.get(f"{API}/rcs/tokens/{toks[0]['id']}", headers=h(auditor)).json()
    assert tok["honoured_count"] == 1 and tok["last_honoured_at"] is not None

    # part of the cargo offloaded after the port (about -9 %): inconsistent with the token -> rolling verification lane
    r3 = client.post(f"{API}/weighing/simulate", json={"lane_id": wim["id"], "count": 1, "overload_prob": 0.0, "sensor_fault_prob": 0.0, "anpr_misread_prob": 0.0,
                                                       "rfid_missing_prob": 0.0, "clone_prob": 0.0, "unregistered_prob": 0.0, "pavement_temp_c": 30, "vehicle_id": v["id"],
                                                       "force_gvm_kg": 29000, "seed": 13, "oversize_prob": 0.0, "lifted_axle_prob": 0.0}, headers=h(operator))
    ev3 = r3.json()[0]
    assert ev3["decision"]["route"] == "verification_lane" and "TOKEN_WEIGHT_INCONSISTENT" in [x["rule"] for x in ev3["decision"]["rules_fired"]]

    # ledger carries the token lifecycle
    types = {e["type"] for e in client.get(f"{API}/admin/ledger", params={"limit": 200}, headers=h(auditor)).json()}
    assert {"token.issued", "token.honoured"} <= types

    # suspend from the registry, then the next pass is AMBER on TOKEN_SUSPENDED
    s = client.post(f"{API}/rcs/tokens/{toks[0]['id']}/suspend", json={"reason": "origin drift audit"}, headers=h(operator))
    assert s.status_code == 200 and s.json()["status"] == "suspended"
    assert client.get(f"{API}/rcs/tokens/verify/{token_ref}").json()["valid"] is False


def test_verification_lane_pass_issues_lane_token_and_untokened_truck_gets_road_token(client, operator):
    mrk = _station(client, operator, "MRK")
    v = _vehicle(client, operator, "KDG 102K")  # tier 3, no token yet
    lane = _lane(mrk, "rolling_verification")
    r = client.post(f"{API}/weighing/simulate", json={"lane_id": lane["id"], "count": 1, "overload_prob": 0.0, "sensor_fault_prob": 0.0, "anpr_misread_prob": 0.0,
                                                      "rfid_missing_prob": 0.0, "clone_prob": 0.0, "unregistered_prob": 0.0, "pavement_temp_c": 30, "vehicle_id": v["id"],
                                                      "force_gvm_kg": 36000, "seed": 21, "oversize_prob": 0.0, "lifted_axle_prob": 0.0}, headers=h(operator))
    ev = r.json()[0]
    assert ev["node_kind"] == "verification_lane" and ev["speed_mps"] < 4.0 and ev["width_m"] is not None
    assert ev["decision"]["decision"] == "GREEN" and ev["decision"]["token_issued_ref"]
    tok = client.get(f"{API}/rcs/tokens/lookup", params={"plate": v["plate"]}, headers=h(operator)).json()
    assert tok["source"] == "lane" and tok["trust_tier"] == 3 and tok["dimensions"]["height_m"] == ev["height_m"]


def test_oversize_without_permit_is_red_and_permit_covers_it(client, operator, transporter):
    mrk = _station(client, operator, "MRK")
    lane = _lane(mrk, "rolling_verification")
    v = _vehicle(client, operator, "KDB 118C")  # 1+2+3, 50 t; seeded shipment declares 30 t on a 16.5 t tare -> 46.5 t expected
    body = {"lane_id": lane["id"], "count": 1, "overload_prob": 0.0, "sensor_fault_prob": 0.0, "anpr_misread_prob": 0.0, "rfid_missing_prob": 0.0, "clone_prob": 0.0,
            "unregistered_prob": 0.0, "pavement_temp_c": 30, "vehicle_id": v["id"], "force_gvm_kg": 46500, "seed": 31, "oversize_prob": 1.0, "lifted_axle_prob": 0.0}
    ev = client.post(f"{API}/weighing/simulate", json=body, headers=h(operator)).json()[0]
    assert ev["decision"]["decision"] == "RED" and ev["decision"]["route"] == "static_scale"
    assert "DIMENSION_OVER" in [x["rule"] for x in ev["decision"]["rules_fired"]]
    # the transporter registers a special-load permit; the same oversize pass is now permitted
    from kifaru.models import utcnow

    pm = client.post(f"{API}/rcs/permits", json={"vehicle_id": v["id"], "reference": "NTSA-SLP-TEST-1", "max_length_m": 30.0, "max_width_m": 3.5, "max_height_m": 5.0,
                                                 "max_gvm_kg": 56000, "valid_from": (utcnow() - timedelta(days=1)).isoformat(), "valid_to": (utcnow() + timedelta(days=30)).isoformat(),
                                                 "route": "A109"}, headers=h(transporter))
    assert pm.status_code == 201 and pm.json()["status"] == "valid"
    ev2 = client.post(f"{API}/weighing/simulate", json={**body, "seed": 32}, headers=h(operator)).json()[0]
    assert ev2["decision"]["decision"] == "GREEN" and "DIMENSION_PERMITTED" in [x["rule"] for x in ev2["decision"]["rules_fired"]]
    assert client.get(f"{API}/rcs/permits", params={"vehicle_id": v["id"]}, headers=h(transporter)).json()[0]["reference"] == "NTSA-SLP-TEST-1"


def test_release_order_for_red_pass_with_repeat_offence_tripled(client, operator, auditor):
    mrk = _station(client, operator, "MRK")
    wim = _lane(mrk, "wim_highspeed")
    v = _vehicle(client, operator, "KDF 661H")  # 1+2+3, limit 50 t
    body = {"lane_id": wim["id"], "count": 1, "overload_prob": 0.0, "sensor_fault_prob": 0.0, "anpr_misread_prob": 0.0, "rfid_missing_prob": 0.0, "clone_prob": 0.0,
            "unregistered_prob": 0.0, "pavement_temp_c": 30, "vehicle_id": v["id"], "force_gvm_kg": 58000, "seed": 41, "oversize_prob": 0.0, "lifted_axle_prob": 0.0}
    ev = client.post(f"{API}/weighing/simulate", json=body, headers=h(operator)).json()[0]
    assert ev["decision"]["decision"] == "RED" and ev["decision"]["fee_preview_usd"] and ev["decision"]["fee_preview_usd"] > 0
    # an auditor cannot sign a release order (officer role required)
    assert client.post(f"{API}/rcs/release-orders", json={"weighing_event_id": ev["id"], "transit": True}, headers=h(auditor)).status_code == 403
    r = client.post(f"{API}/rcs/release-orders", json={"weighing_event_id": ev["id"], "static_gvm_kg": 57000, "transit": True, "hazardous": False, "perishable": False,
                                                       "journey_ref": "JNY-1", "notes": "sealed transit container"}, headers=h(operator))
    assert r.status_code == 201, r.text
    ro = r.json()
    assert ro["overload_kg"] == 7000 and ro["fee_multiplier"] == 1.0 and ro["repeat_offence"] is False and ro["customs_notified"] is True
    assert ro["fee_usd"] == pytest.approx(DEFAULT_LIMITS.overload_fee(7000)) and ro["officer_signature"] and ro["status"] == "issued"
    # duplicate for the same pass is refused
    assert client.post(f"{API}/rcs/release-orders", json={"weighing_event_id": ev["id"], "transit": False}, headers=h(operator)).status_code == 409
    # overloaded again in the same journey: tripled fee (Reg 14)
    ev2 = client.post(f"{API}/weighing/simulate", json={**body, "seed": 42, "force_gvm_kg": 57500}, headers=h(operator)).json()[0]
    ro2 = client.post(f"{API}/rcs/release-orders", json={"weighing_event_id": ev2["id"], "static_gvm_kg": 57000, "transit": False}, headers=h(operator)).json()
    assert ro2["repeat_offence"] is True and ro2["fee_multiplier"] == 3.0 and ro2["fee_usd"] == pytest.approx(3 * ro["fee_usd"]) and ro2["journey_ref"] == "JNY-1"
    # listing and status change; demerit points accumulate on the vehicle
    lst = client.get(f"{API}/rcs/release-orders", params={"vehicle_id": v["id"]}, headers=h(auditor)).json()
    assert len(lst) == 2 and lst[0]["station_code"] == "MRK"
    assert client.post(f"{API}/rcs/release-orders/{ro['id']}/status", json={"status": "paid"}, headers=h(operator)).json()["status"] == "paid"
    assert _vehicle(client, operator, "KDF 661H")["demerit_points"] >= 3


def test_registry_stats_and_limits_expose_v2_fields(client, auditor):
    st = client.get(f"{API}/rcs/stats", headers=h(auditor)).json()
    assert st["total"] > 0 and set(st["by_route"]) == {"continue", "verification_lane", "static_scale", "port_reweigh", "hold"}
    assert set(st["by_stream"]) == {"port", "origin", "untokened"} and 0 <= st["token_coverage"] <= 1
    assert any(s["code"] == "MBS-GATE18" and s["kind"] == "port_gate" for s in st["per_station"])
    lim = client.get(f"{API}/weighing/limits").json()
    assert lim["version"] == DEFAULT_LIMITS.version and lim["max_height_m"] == 4.3 and lim["fee_schedule"]["detention_free_days"] == 3


def test_chain_model_endpoint_and_sweep(client, auditor):
    r = client.post(f"{API}/rcs/model", json={"avg_loading_pct": 85, "token_coverage": 0.9, "n": 20000, "seed": 3}, headers=h(auditor))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["label"] == "MODELLED" and set(out["shares"]) >= {"road_only_static", "v2_road_static", "v2_port_reweigh", "first_station_lane", "first_station_static"}
    assert out["shares"]["v2_road_static"] < out["shares"]["road_only_static"] and out["false_clear_rate"] <= 0.01
    assert out["lane_capacity_per_hour"] > 300 and out["truck_hours_saved_per_day"] > 0
    sw = client.post(f"{API}/rcs/model/sweep", json={"factor": "token_coverage", "values": [0.3, 0.9], "base": {"n": 20000}}, headers=h(auditor))
    assert sw.status_code == 200, sw.text
    rows = sw.json()["rows"]
    assert len(rows) == 2 and rows[0]["first_station_static"] > rows[1]["first_station_static"]
    assert client.post(f"{API}/rcs/model/sweep", json={"factor": "nope", "values": [1]}, headers=h(auditor)).status_code == 422

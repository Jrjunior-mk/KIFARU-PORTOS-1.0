"""Legal axle-load, gross-mass and dimension limits, allowance and fee policy used by the clearance engine (RCS v2).

IMPORTANT — LEGAL VERIFICATION REQUIRED. The figures below reflect the East African Community Vehicle Load Control Act,
2016 and the EAC Vehicle Load Control (Enforcement Measures) Regulations, 2018 (Third Schedule legal weights, Second Schedule
certificate fields incl. the discretion allowance, Reg 14 release orders) *as understood by the engineering team*. They are
configuration, not code: the `limits_version` string is stored with every decision so that a change in the schedule never
silently changes the meaning of historical decisions. Before any pilot, every value must be confirmed against the current
schedule and the regulator's tolerance and allowance policy, and this file updated with a new version string.

See docs/01-requirements/legal-hooks-eac-vlc-2018.md for the regulation-by-regulation mapping.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Indicative overload fee points (overload above the gross limit in kg -> USD), 2021–2030 fee table as reported in the
# RCS v2 plan: 5 000 kg over costs about 2 990 USD. The remaining points are linear interpolations/extrapolations of that
# single anchor and MUST be replaced with the full Third Schedule table before any fee is charged.
INDICATIVE_FEE_POINTS_USD: tuple[tuple[int, float], ...] = (
    (0, 0.0),
    (500, 150.0),
    (1_000, 400.0),
    (2_000, 1_000.0),
    (3_000, 1_650.0),
    (4_000, 2_300.0),
    (5_000, 2_990.0),
    (7_500, 4_900.0),
    (10_000, 7_200.0),
    (15_000, 12_500.0),
    (20_000, 18_500.0),
)

# Reported gross limits by axle count from the process guide supplied with the plan. Reported figures only; the engine
# uses the axle-group schedule below and treats these as a cross-check.
REPORTED_GVM_BY_AXLES: dict[int, int] = {2: 18_000, 3: 26_000, 4: 30_000, 6: 50_000}


@dataclass(frozen=True)
class LimitSet:
    version: str
    steering_single_kg: int = 8_000  # first axle (group of 1, steering)
    single_drive_kg: int = 10_000  # any other single axle (dual tyres)
    tandem_kg: int = 18_000  # group of 2
    tridem_kg: int = 24_000  # group of 3
    quad_kg: int = 24_000  # groups of 4+ are not expected; treated as tridem limit (conservative)
    gvm_max_kg: int = 56_000
    # Enforcement tolerance applied to axle-group limits (percentage). The EAC Act provides a tolerance on axle load;
    # the exact value and whether it applies to GVM must be confirmed with the regulator. Default: 5 % on axle groups, 0 % on GVM.
    axle_tolerance_pct: float = 5.0
    gvm_tolerance_pct: float = 0.0
    # Second Schedule discretion allowance: "less than 5 % of the allowed load". Whether it is applied routinely is a KeNHA
    # policy decision (RCS v2 plan §9); default 0 until confirmed. Applied to both GVM and axle-group limits.
    discretion_allowance_pct: float = 0.0
    # Conservative margin: in addition to measurement uncertainty, require this margin before GREEN (kg).
    green_safety_margin_kg: int = 250
    # Dimension limits (EAC VLC Act, to be verified): overall height, width and length (articulated combination).
    max_height_m: float = 4.3
    max_width_m: float = 2.65
    max_length_m: float = 22.0
    # Fee and detention policy (Reg 13 fee table, Reg 14 release orders, detention terms as reported in the plan)
    fee_currency: str = "USD"
    fee_points: tuple[tuple[int, float], ...] = INDICATIVE_FEE_POINTS_USD
    detention_free_days: int = 3
    detention_usd_per_day: float = 50.0
    repeat_offence_multiplier: float = 3.0  # Reg 14: overloaded again in the same journey -> fees tripled
    notes: list[str] = field(
        default_factory=lambda: [
            "Axle-group and GVM values to be verified against the EAC Vehicle Load Control Act 2016 / Regulations 2018 Third Schedule before pilot.",
            "Tolerance and discretion-allowance policy to be confirmed with KeNHA (Second Schedule allowance is < 5 % of allowed load).",
            "Fee points are indicative (anchored on 5 000 kg over ≈ 2 990 USD); load the full Third Schedule fee table before charging.",
            "Dimension limits (4.3 m height, 2.65 m width, 22 m length) to be verified for each vehicle class and route.",
            "Reported gross limits by axle count (2: 18 t, 3: 26 t, 4: 30 t, 6: 50 t) are cross-check figures only.",
        ]
    )

    # ------------------------------------------------------------------ weights
    def group_limit_kg(self, group_index: int, group_size: int) -> int:
        if group_size == 1:
            return self.steering_single_kg if group_index == 0 else self.single_drive_kg
        if group_size == 2:
            return self.tandem_kg
        if group_size == 3:
            return self.tridem_kg
        return self.quad_kg

    def gvm_limit_for_config(self, group_sizes: list[int]) -> int:
        if not group_sizes:
            return self.gvm_max_kg
        s = sum(self.group_limit_kg(i, g) for i, g in enumerate(group_sizes))
        return min(s, self.gvm_max_kg)

    def allowance_kg(self, allowed_kg: float) -> float:
        """Discretion allowance in kg for an allowed load (0 when the policy is not applied)."""
        return allowed_kg * self.discretion_allowance_pct / 100.0

    # ------------------------------------------------------------------ dimensions
    def dimension_breaches(self, length_m: float | None, width_m: float | None, height_m: float | None) -> list[str]:
        out = []
        if length_m is not None and length_m > self.max_length_m:
            out.append(f"length {length_m:.2f} m > {self.max_length_m} m")
        if width_m is not None and width_m > self.max_width_m:
            out.append(f"width {width_m:.2f} m > {self.max_width_m} m")
        if height_m is not None and height_m > self.max_height_m:
            out.append(f"height {height_m:.2f} m > {self.max_height_m} m")
        return out

    # ------------------------------------------------------------------ fees
    def overload_fee(self, overload_kg: float) -> float:
        """Indicative fee for an overload above the (allowance-adjusted) gross limit, by linear interpolation of the fee
        points. Returns 0 for no overload. Extrapolates linearly beyond the last point."""
        if overload_kg <= 0:
            return 0.0
        pts = self.fee_points
        for (k0, f0), (k1, f1) in zip(pts, pts[1:], strict=False):
            if k0 <= overload_kg <= k1:
                return round(f0 + (f1 - f0) * (overload_kg - k0) / (k1 - k0), 2)
        (k0, f0), (k1, f1) = pts[-2], pts[-1]
        return round(f1 + (f1 - f0) * (overload_kg - k1) / (k1 - k0), 2)

    def detention_fee(self, days: int) -> float:
        return max(0, days - self.detention_free_days) * self.detention_usd_per_day

    def fee_schedule(self) -> dict:
        return {
            "currency": self.fee_currency,
            "points": [list(p) for p in self.fee_points],
            "detention_free_days": self.detention_free_days,
            "detention_usd_per_day": self.detention_usd_per_day,
            "repeat_offence_multiplier": self.repeat_offence_multiplier,
            "note": "Indicative: anchored on the reported 2021–2030 point (5 000 kg over ≈ 2 990 USD); replace with the Third Schedule table.",
        }


DEFAULT_LIMITS = LimitSet(version="KE-EAC-VLC-REG-2018-schedule-v2")


def parse_axle_config(cfg: str) -> list[int]:
    try:
        return [int(x) for x in cfg.replace(" ", "").split("+") if x]
    except ValueError:
        return []

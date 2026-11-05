"""kifaru_sim — SimPy weighing-station scenario simulation and the RCS v2 chain model for KIFARU PORTOS (Phase 5, RTM DT-02).

All outputs are modelled, not measured.
"""
from .experiments import evaluate_gate, replicate, sweep, tornado
from .model import SimConfig, SimResult, TruckRecord, run_model
from .rcs_v2 import ChainParams, ChainResult, lane_capacity_per_hour, mixed_traffic_table, port_truck_table, run_chain, tables_markdown
from .scenarios import SCENARIOS, build, list_scenarios

__all__ = [
    "SimConfig", "SimResult", "TruckRecord", "run_model", "SCENARIOS", "build", "list_scenarios",
    "ChainParams", "ChainResult", "run_chain", "port_truck_table", "mixed_traffic_table", "tables_markdown", "lane_capacity_per_hour",
    "sweep", "replicate", "tornado", "evaluate_gate",
]
__version__ = "0.2.0"

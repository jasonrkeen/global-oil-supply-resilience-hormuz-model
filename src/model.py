from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Baseline:
    as_of: str = "2026-07-09"
    pre_crisis_hormuz_mbd: float = 20.0
    global_demand_mbd: float = 104.0
    accessible_inventory_mmb: float = 4_250.0
    minimum_operating_inventory_mmb: float = 2_250.0
    base_brent_usd: float = 86.0
    planning_horizon_days: int = 365

    @property
    def drawable_inventory_mmb(self) -> float:
        return max(0.0, self.accessible_inventory_mmb - self.minimum_operating_inventory_mmb)


def load_scenarios(path: Path) -> pd.DataFrame:
    required = {
        "scenario", "hormuz_flow_mbd", "bypass_mbd", "other_supply_response_mbd",
        "demand_reduction_pct", "strategic_release_mbd", "release_days", "risk_premium_usd"
    }
    frame = pd.read_csv(path)
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Scenario file missing columns: {sorted(missing)}")
    return frame


def daily_balance(s: pd.Series, baseline: Baseline, day: int) -> dict[str, float]:
    gross_loss = max(0.0, baseline.pre_crisis_hormuz_mbd - float(s.hormuz_flow_mbd))
    mitigation = float(s.bypass_mbd) + float(s.other_supply_response_mbd)
    demand_relief = baseline.global_demand_mbd * float(s.demand_reduction_pct) / 100.0
    reserve = float(s.strategic_release_mbd) if day <= int(s.release_days) else 0.0
    deficit = max(0.0, gross_loss - mitigation - demand_relief - reserve)
    return {"gross_loss_mbd": gross_loss, "mitigation_mbd": mitigation,
            "demand_relief_mbd": demand_relief, "reserve_release_mbd": reserve,
            "uncovered_deficit_mbd": deficit}


def simulate_scenario(s: pd.Series, baseline: Baseline) -> pd.DataFrame:
    inventory = baseline.drawable_inventory_mmb
    rows = []
    reopening_start = 61 if s.scenario == "gradual_reopening" else None
    for day in range(1, baseline.planning_horizon_days + 1):
        current = s.copy()
        if reopening_start and day >= reopening_start:
            fraction = min(1.0, (day - reopening_start) / 120.0)
            current.hormuz_flow_mbd = float(s.hormuz_flow_mbd) + fraction * (baseline.pre_crisis_hormuz_mbd - float(s.hormuz_flow_mbd))
        b = daily_balance(current, baseline, day)
        inventory = max(0.0, inventory - b["uncovered_deficit_mbd"])
        scarcity = 1.0 - inventory / max(baseline.drawable_inventory_mmb, 1.0)
        price = baseline.base_brent_usd + float(s.risk_premium_usd) + 85.0 * scarcity**1.7
        rows.append({"scenario": s.scenario, "day": day, "drawable_inventory_mmb": inventory,
                     "brent_proxy_usd": price, **b})
    return pd.DataFrame(rows)


def run_deterministic(scenarios: pd.DataFrame, baseline: Baseline) -> pd.DataFrame:
    return pd.concat([simulate_scenario(s, baseline) for _, s in scenarios.iterrows()], ignore_index=True)


def monte_carlo(s: pd.Series, baseline: Baseline, runs: int = 5000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    horizons = np.array([30, 60, 90, 180, 365])
    out = []
    for run in range(runs):
        draw = s.copy()
        draw.hormuz_flow_mbd = np.clip(rng.normal(float(s.hormuz_flow_mbd), 1.2), 0, 20)
        draw.bypass_mbd = np.clip(rng.normal(float(s.bypass_mbd), 0.5), 0, 6.5)
        draw.other_supply_response_mbd = max(0, rng.normal(float(s.other_supply_response_mbd), 0.6))
        draw.demand_reduction_pct = max(0, rng.normal(float(s.demand_reduction_pct), 0.8))
        draw.strategic_release_mbd = max(0, rng.normal(float(s.strategic_release_mbd), 0.5))
        draw.risk_premium_usd = max(0, rng.normal(float(s.risk_premium_usd), 8))
        gross_loss = max(0.0, baseline.pre_crisis_hormuz_mbd - float(draw.hormuz_flow_mbd))
        relief = (float(draw.bypass_mbd) + float(draw.other_supply_response_mbd)
                  + baseline.global_demand_mbd * float(draw.demand_reduction_pct) / 100.0)
        deficit_with_release = max(0.0, gross_loss - relief - float(draw.strategic_release_mbd))
        deficit_after_release = max(0.0, gross_loss - relief)
        for h in horizons:
            if s.scenario == "gradual_reopening":
                days = np.arange(1, int(h) + 1)
                fraction = np.clip((days - 61) / 120.0, 0.0, 1.0)
                flows = float(draw.hormuz_flow_mbd) + fraction * (baseline.pre_crisis_hormuz_mbd - float(draw.hormuz_flow_mbd))
                releases = np.where(days <= int(draw.release_days), float(draw.strategic_release_mbd), 0.0)
                deficits = np.maximum(0.0, baseline.pre_crisis_hormuz_mbd - flows - relief - releases)
                inventory = max(0.0, baseline.drawable_inventory_mmb - float(deficits.sum()))
            else:
                release_days = min(int(h), int(draw.release_days))
                later_days = max(0, int(h) - int(draw.release_days))
                inventory = max(0.0, baseline.drawable_inventory_mmb
                                - release_days * deficit_with_release
                                - later_days * deficit_after_release)
            scarcity = 1.0 - inventory / max(baseline.drawable_inventory_mmb, 1.0)
            price = baseline.base_brent_usd + float(draw.risk_premium_usd) + 85.0 * scarcity**1.7
            out.append({"scenario": s.scenario, "run": run, "day": int(h),
                        "inventory_mmb": inventory, "brent_proxy_usd": price,
                        "critical_breach": inventory <= 0})
    return pd.DataFrame(out)


def score_countries(frame: pd.DataFrame) -> pd.DataFrame:
    cover_risk = (1 - frame.estimated_days_cover.clip(0, 180) / 180) * 100
    score = (0.30 * frame.hormuz_import_dependence_pct + 0.20 * frame.net_import_dependence_pct
             + 0.20 * cover_risk + 0.12 * (100 - frame.fiscal_capacity)
             + 0.10 * frame.energy_intensity + 0.08 * (100 - frame.refining_flexibility))
    result = frame.copy()
    result["vulnerability_score"] = score.round(1)
    return result.sort_values("vulnerability_score", ascending=False).reset_index(drop=True)

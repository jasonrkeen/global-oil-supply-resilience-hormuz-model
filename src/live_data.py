from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any
import json
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError
from functools import lru_cache

import pandas as pd
import numpy as np

from .model import Baseline


EIA_SERIES = {
    "us_commercial_crude_stocks": ("petroleum/stoc/wstk", "WCESTUS1", "thousand barrels"),
    "us_spr_crude_stocks": ("petroleum/stoc/wstk", "WCSSTUS1", "thousand barrels"),
    "us_gasoline_stocks": ("petroleum/stoc/wstk", "WGTSTUS1", "thousand barrels"),
    "us_distillate_stocks": ("petroleum/stoc/wstk", "WDISTUS1", "thousand barrels"),
    "brent_spot_price": ("petroleum/pri/spt", "RBRTE", "USD per barrel"),
    "us_crude_production": ("petroleum/sum/sndw", "WCRFPUS2", "thousand barrels per day"),
    "us_refinery_utilization": ("petroleum/sum/sndw", "WPULEUS3", "percent"),
    "us_crude_imports": ("petroleum/sum/sndw", "WCRIMUS2", "thousand barrels per day"),
    "us_crude_exports": ("petroleum/sum/sndw", "WCREXUS2", "thousand barrels per day"),
    "us_gasoline_product_supplied": ("petroleum/sum/sndw", "WGFUPUS2", "thousand barrels per day"),
    "us_distillate_product_supplied": ("petroleum/sum/sndw", "WDIUPUS2", "thousand barrels per day"),
    "us_refinery_crude_inputs": ("petroleum/sum/sndw", "WCRRIUS2", "thousand barrels per day"),
}


def load_baseline(path: Path) -> tuple[Baseline, pd.DataFrame]:
    """Load explicitly sourced overrides; never modify assumptions silently."""
    audit = pd.read_csv(path)
    allowed = set(asdict(Baseline()))
    values: dict[str, Any] = {}
    for row in audit.itertuples(index=False):
        if row.parameter not in allowed:
            raise ValueError(f"Unknown baseline parameter: {row.parameter}")
        values[row.parameter] = int(row.value) if row.parameter == "planning_horizon_days" else float(row.value)
    return replace(Baseline(), **values), audit


@lru_cache(maxsize=8)
def _eia_route_rows(api_key: str, route: str, frequency: str, length: int, use_series_facet: bool,
                    series: str = "") -> list[dict[str, Any]]:
    url = f"https://api.eia.gov/v2/{route}/data/"
    params = {
        "api_key": api_key,
        "frequency": frequency,
        "data[0]": "value",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "offset": 0,
        "length": length,
    }
    if use_series_facet:
        params["facets[series][]"] = series
    try:
        with urlopen(f"{url}?{urlencode(params)}", timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ValueError(f"EIA HTTP {exc.code}: {detail}") from exc
    rows = payload.get("response", {}).get("data", [])
    return rows


def _eia_history(api_key: str, route: str, series: str, length: int = 270) -> list[dict[str, Any]]:
    frequency = "daily" if "spt" in route else "weekly"
    if route == "petroleum/sum/sndw":
        # This wide summary route exposes process/product/area facets rather than
        # a legacy-series facet. Pull the newest route rows and select the
        # authoritative legacy series locally.
        route_rows = _eia_route_rows(api_key, route, frequency, 5000, False)
        rows = [row for row in route_rows if str(row.get("series", "")).upper() == series.upper()]
        rows = rows[:length]
    else:
        rows = _eia_route_rows(api_key, route, frequency, length, True, series)
    if not rows:
        available = sorted({str(row.get("series")) for row in (_eia_route_rows(api_key, route, frequency, 20, False) if route == "petroleum/sum/sndw" else [])})
        raise ValueError(f"EIA returned no rows for {series}; sample series={available[:10]}")
    return rows


def collect_live_dataset(api_key: str | None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Collect latest observations plus enough history for seasonal context."""
    collected_at = datetime.now(timezone.utc).isoformat()
    observations, history, quality = [], [], []
    if not api_key or api_key == "replace_with_your_key":
        quality.append({"component": "EIA live API", "status": "fallback", "freshness": "not collected",
                        "message": "EIA_API_KEY missing; deterministic model retained sourced planning assumptions."})
        return pd.DataFrame(observations), pd.DataFrame(history), pd.DataFrame(quality)

    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    for metric, (route, series, unit) in EIA_SERIES.items():
        try:
            rows = _eia_history(api_key, route, series, 270 if "wstk" in route else 90)
            metric_history = []
            for row in rows:
                value = pd.to_numeric(row.get("value"), errors="coerce")
                record = {"metric": metric, "series": series, "period": row.get("period"),
                          "value": value, "unit": unit, "provider": "U.S. EIA"}
                history.append(record); metric_history.append(record)
            latest = metric_history[0]
            observations.append({**latest, "collected_at_utc": collected_at})
            age = (today - pd.to_datetime(latest["period"])).days
            status = "live" if age <= (10 if "wstk" in route else 7) else "stale"
            quality.append({"component": metric, "status": status, "freshness": latest["period"],
                            "message": f"Latest EIA observation collected; age={age} days."})
        except Exception as exc:
            quality.append({"component": metric, "status": "fallback", "freshness": "unknown",
                            "message": f"Collection failed: {type(exc).__name__}: {exc}"})
    return pd.DataFrame(observations), pd.DataFrame(history), pd.DataFrame(quality)


def collect_live_snapshot(api_key: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    observations, _, quality = collect_live_dataset(api_key)
    return observations, quality


def derive_market_indicators(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create deltas, seasonal positions, and a transparent resilience score."""
    if history.empty:
        return pd.DataFrame(), pd.DataFrame()
    h = history.copy()
    h["period"] = pd.to_datetime(h["period"])
    h["value"] = pd.to_numeric(h["value"], errors="coerce")
    rows = []
    seasonal_metrics = {"us_commercial_crude_stocks", "us_gasoline_stocks", "us_distillate_stocks"}
    for metric, g in h.groupby("metric"):
        g = g.dropna(subset=["value"]).sort_values("period", ascending=False)
        if g.empty:
            continue
        latest = g.iloc[0]; previous = g.iloc[1] if len(g) > 1 else latest
        row = {"metric": metric, "period": latest.period.date().isoformat(), "latest_value": latest.value,
               "previous_value": previous.value, "change": latest.value - previous.value,
               "change_pct": 100 * (latest.value - previous.value) / previous.value if previous.value else 0.0,
               "seasonal_average": float("nan"), "seasonal_low": float("nan"),
               "seasonal_high": float("nan"), "seasonal_position_pct": float("nan")}
        if metric in seasonal_metrics:
            week = int(latest.period.isocalendar().week)
            prior = g[(g.period.dt.year < latest.period.year) &
                      (g.period.dt.year >= latest.period.year - 5)].copy()
            prior["week"] = prior.period.dt.isocalendar().week.astype(int)
            distance = (prior.week - week).abs()
            seasonal = prior[(distance <= 2) | (distance >= 50)]
            if not seasonal.empty:
                low, high, avg = seasonal.value.min(), seasonal.value.max(), seasonal.value.mean()
                position = 50.0 if high == low else 100 * (latest.value - low) / (high - low)
                row.update(seasonal_average=avg, seasonal_low=low, seasonal_high=high,
                           seasonal_position_pct=float(max(0, min(100, position))))
        rows.append(row)
    indicators = pd.DataFrame(rows)

    positions = indicators.set_index("metric").seasonal_position_pct.to_dict()
    spr = indicators[indicators.metric == "us_spr_crude_stocks"]
    spr_value = float(spr.iloc[0].latest_value) if not spr.empty else 0.0
    spr_component = max(0.0, min(100.0, 100 * spr_value / 714_000.0))
    components = {
        "commercial_crude": positions.get("us_commercial_crude_stocks", 50.0),
        "gasoline": positions.get("us_gasoline_stocks", 50.0),
        "distillate": positions.get("us_distillate_stocks", 50.0),
        "spr_authorized_capacity": spr_component,
    }
    weights = {"commercial_crude": .30, "gasoline": .20, "distillate": .25, "spr_authorized_capacity": .25}
    score = sum(weights[k] * (50.0 if pd.isna(v) else v) for k, v in components.items())
    band = "strong" if score >= 70 else "adequate" if score >= 50 else "strained" if score >= 30 else "critical"
    resilience = pd.DataFrame([{"resilience_score": round(score, 1), "resilience_band": band,
                                **{f"{k}_component": round(50.0 if pd.isna(v) else v, 1) for k, v in components.items()},
                                "methodology": "Weighted screening index; 30% commercial crude, 20% gasoline, 25% distillate, 25% SPR/capacity."}])
    return indicators.round(2), resilience


def derive_system_resilience(snapshot: pd.DataFrame, indicators: pd.DataFrame,
                             history: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate inventory stress from broader operating-system resilience."""
    if snapshot.empty or indicators.empty:
        return pd.DataFrame(), pd.DataFrame()
    values = snapshot.set_index("metric").value.to_dict()
    seasonal = indicators.set_index("metric").seasonal_position_pct.to_dict()
    required = ["us_commercial_crude_stocks", "us_spr_crude_stocks", "us_gasoline_stocks",
                "us_distillate_stocks", "us_crude_production", "us_refinery_utilization",
                "us_crude_imports", "us_crude_exports", "us_gasoline_product_supplied",
                "us_distillate_product_supplied", "us_refinery_crude_inputs"]
    missing = [x for x in required if x not in values or pd.isna(values[x])]
    if missing:
        return pd.DataFrame(), pd.DataFrame([{"status": "incomplete", "missing_metrics": ";".join(missing)}])

    flow_metrics = ["us_crude_production", "us_refinery_utilization", "us_crude_imports",
                    "us_crude_exports", "us_gasoline_product_supplied",
                    "us_distillate_product_supplied", "us_refinery_crude_inputs"]
    flows = {metric: float(values[metric]) for metric in flow_metrics}
    calculation_method = "latest weekly observation"
    if history is not None and not history.empty:
        hh = history.copy(); hh["period"] = pd.to_datetime(hh.period); hh["value"] = pd.to_numeric(hh.value, errors="coerce")
        used_four_week = True
        for metric in flow_metrics:
            recent = hh[hh.metric == metric].dropna(subset=["value"]).sort_values("period", ascending=False).head(4)
            if len(recent) < 4:
                used_four_week = False
            else:
                flows[metric] = float(recent.value.mean())
        calculation_method = "four-week average flows" if used_four_week else "mixed: four-week averages where available"

    crude_days = values["us_commercial_crude_stocks"] / max(flows["us_refinery_crude_inputs"], 1)
    gasoline_days = values["us_gasoline_stocks"] / max(flows["us_gasoline_product_supplied"], 1)
    distillate_days = values["us_distillate_stocks"] / max(flows["us_distillate_product_supplied"], 1)
    net_imports = flows["us_crude_imports"] - flows["us_crude_exports"]
    net_import_dependence = max(0.0, net_imports) / max(flows["us_refinery_crude_inputs"], 1) * 100
    domestic_coverage = flows["us_crude_production"] / max(flows["us_refinery_crude_inputs"], 1) * 100
    total_supply_coverage = (flows["us_crude_production"] + max(0.0, net_imports)) / max(flows["us_refinery_crude_inputs"], 1) * 100
    weekly_periods = pd.to_datetime(snapshot[snapshot.metric.isin(required)].period, errors="coerce").dropna()
    operating_period = weekly_periods.max().date().isoformat() if not weekly_periods.empty else "unknown"

    operating = pd.DataFrame([{
        "period": operating_period, "calculation_method": calculation_method,
        "commercial_crude_days": round(crude_days, 1),
        "gasoline_days": round(gasoline_days, 1), "distillate_days": round(distillate_days, 1),
        "crude_production_kbd": round(flows["us_crude_production"], 1),
        "refinery_inputs_kbd": round(flows["us_refinery_crude_inputs"], 1),
        "refinery_utilization_pct": round(flows["us_refinery_utilization"], 1),
        "crude_imports_kbd": round(flows["us_crude_imports"], 1),
        "crude_exports_kbd": round(flows["us_crude_exports"], 1),
        "net_import_dependence_pct": round(net_import_dependence, 1),
        "domestic_production_coverage_pct": round(domestic_coverage, 1),
        "total_supply_coverage_pct": round(total_supply_coverage, 1),
    }])

    inv_positions = [seasonal.get(x, 50.0) for x in ["us_commercial_crude_stocks", "us_gasoline_stocks", "us_distillate_stocks"]]
    inv_positions = [50.0 if pd.isna(x) else float(x) for x in inv_positions]
    inventory_stress = 100.0 - sum(inv_positions) / len(inv_positions)
    days_component = np.mean([min(100, crude_days / 25 * 100), min(100, gasoline_days / 24 * 100),
                              min(100, distillate_days / 28 * 100)])
    refinery_component = max(0.0, 100.0 - 4.0 * abs(flows["us_refinery_utilization"] - 90.0))
    supply_component = min(100.0, total_supply_coverage)
    trade_component = max(0.0, 100.0 - net_import_dependence)
    spr_component = min(100.0, values["us_spr_crude_stocks"] / 714_000.0 * 100)
    system_score = (.25 * supply_component + .20 * refinery_component + .25 * days_component
                    + .15 * trade_component + .15 * spr_component)
    band = "strong" if system_score >= 75 else "adequate" if system_score >= 55 else "strained" if system_score >= 35 else "critical"
    scores = pd.DataFrame([{
        "inventory_stress_score": round(inventory_stress, 1),
        "inventory_stress_band": "severe" if inventory_stress >= 75 else "elevated" if inventory_stress >= 50 else "moderate" if inventory_stress >= 25 else "low",
        "system_resilience_score": round(system_score, 1), "system_resilience_band": band,
        "supply_coverage_component": round(supply_component, 1),
        "refinery_operations_component": round(refinery_component, 1),
        "days_supply_component": round(float(days_component), 1),
        "trade_independence_component": round(trade_component, 1),
        "strategic_reserve_component": round(spr_component, 1),
        "status": "complete",
    }])
    return operating, scores


def live_enabled() -> bool:
    return os.getenv("ENABLE_LIVE_DATA", "1").strip().lower() not in {"0", "false", "no"}

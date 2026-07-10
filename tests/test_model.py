import pandas as pd
from src.model import Baseline, daily_balance, score_countries
from src.live_data import collect_live_snapshot, derive_market_indicators, derive_system_resilience


def test_daily_deficit_never_negative():
    s = pd.Series(dict(hormuz_flow_mbd=20, bypass_mbd=6, other_supply_response_mbd=3,
                       demand_reduction_pct=5, strategic_release_mbd=3, release_days=120))
    assert daily_balance(s, Baseline(), 1)["uncovered_deficit_mbd"] == 0


def test_country_score_order():
    f = pd.DataFrame([dict(country="A", hormuz_import_dependence_pct=100, net_import_dependence_pct=100,
        estimated_days_cover=10, fiscal_capacity=10, energy_intensity=90, refining_flexibility=10),
        dict(country="B", hormuz_import_dependence_pct=0, net_import_dependence_pct=0,
        estimated_days_cover=180, fiscal_capacity=100, energy_intensity=10, refining_flexibility=100)])
    assert score_countries(f).iloc[0].country == "A"


def test_missing_api_key_uses_explicit_fallback():
    observations, quality = collect_live_snapshot(None)
    assert observations.empty
    assert quality.iloc[0].status == "fallback"


def test_market_indicators_and_resilience_score():
    dates = pd.date_range("2021-07-02", periods=265, freq="7D")
    rows = []
    for metric, base in [("us_commercial_crude_stocks", 420000), ("us_gasoline_stocks", 220000),
                         ("us_distillate_stocks", 120000), ("us_spr_crude_stocks", 350000)]:
        rows.extend({"metric": metric, "period": d, "value": base + i * 10} for i, d in enumerate(dates))
    indicators, resilience = derive_market_indicators(pd.DataFrame(rows))
    assert len(indicators) == 4
    assert 0 <= resilience.iloc[0].resilience_score <= 100


def test_system_resilience_separates_inventory_stress():
    snapshot = pd.DataFrame([
        ("us_commercial_crude_stocks", 411357), ("us_spr_crude_stocks", 319489),
        ("us_gasoline_stocks", 212062), ("us_distillate_stocks", 103619),
        ("us_crude_production", 13800), ("us_refinery_utilization", 92),
        ("us_crude_imports", 6000), ("us_crude_exports", 4000),
        ("us_gasoline_product_supplied", 9000), ("us_distillate_product_supplied", 3800),
        ("us_refinery_crude_inputs", 16500),
    ], columns=["metric", "value"])
    snapshot["period"] = "2026-07-03"
    indicators = pd.DataFrame([
        ("us_commercial_crude_stocks", 0), ("us_gasoline_stocks", 0),
        ("us_distillate_stocks", 2.1)
    ], columns=["metric", "seasonal_position_pct"])
    operating, scores = derive_system_resilience(snapshot, indicators)
    assert scores.iloc[0].inventory_stress_score > scores.iloc[0].system_resilience_score
    assert operating.iloc[0].gasoline_days > 0


def test_system_resilience_uses_four_week_flows_and_weekly_date():
    base = [("us_commercial_crude_stocks", 400000), ("us_spr_crude_stocks", 300000),
            ("us_gasoline_stocks", 200000), ("us_distillate_stocks", 100000),
            ("us_crude_production", 14000), ("us_refinery_utilization", 92),
            ("us_crude_imports", 6000), ("us_crude_exports", 4000),
            ("us_gasoline_product_supplied", 10000), ("us_distillate_product_supplied", 4000),
            ("us_refinery_crude_inputs", 16000)]
    snapshot = pd.DataFrame(base + [("brent_spot_price", 70)], columns=["metric", "value"])
    snapshot["period"] = ["2026-07-03"] * len(base) + ["2026-07-06"]
    hist = []
    for metric, value in base:
        for i in range(4):
            hist.append({"metric": metric, "value": value + i * 100, "period": pd.Timestamp("2026-07-03") - pd.Timedelta(days=7*i)})
    indicators = pd.DataFrame([("us_commercial_crude_stocks", 20), ("us_gasoline_stocks", 20),
                               ("us_distillate_stocks", 20)], columns=["metric", "seasonal_position_pct"])
    operating, _ = derive_system_resilience(snapshot, indicators, pd.DataFrame(hist))
    assert operating.iloc[0].period == "2026-07-03"
    assert operating.iloc[0].calculation_method == "four-week average flows"

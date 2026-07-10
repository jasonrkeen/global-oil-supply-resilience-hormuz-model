from pathlib import Path
import os
import pandas as pd
from src.model import Baseline, load_scenarios, run_deterministic, monte_carlo, score_countries
from dataclasses import replace
from src.live_data import (collect_live_dataset, derive_market_indicators, derive_system_resilience,
                           live_enabled, load_baseline)
from src.reporting import make_charts, write_summary
from src.pdf_report import build_pdf

ROOT = Path(__file__).resolve().parent


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    load_env_file(ROOT / ".env")
    out = ROOT / "outputs"; out.mkdir(exist_ok=True)
    baseline, baseline_audit = load_baseline(ROOT / "data" / "baseline_overrides.csv")
    if live_enabled():
        live_snapshot, live_history, data_quality = collect_live_dataset(os.getenv("EIA_API_KEY"))
    else:
        live_snapshot, live_history = pd.DataFrame(), pd.DataFrame()
        data_quality = pd.DataFrame([{"component": "Live collection", "status": "disabled",
                                      "freshness": "not collected", "message": "ENABLE_LIVE_DATA disabled."}])
    indicators, _legacy_resilience = derive_market_indicators(live_history)
    operating, system_scores = derive_system_resilience(live_snapshot, indicators, live_history)
    if os.getenv("USE_LIVE_BRENT_BASELINE", "0").strip().lower() in {"1", "true", "yes"} and not live_snapshot.empty:
        brent = live_snapshot[live_snapshot.metric == "brent_spot_price"]
        if not brent.empty:
            observed = float(brent.iloc[0].value)
            baseline = replace(baseline, base_brent_usd=observed)
            baseline_audit = pd.concat([baseline_audit, pd.DataFrame([{
                "parameter": "base_brent_usd", "value": observed, "unit": "USD per barrel",
                "as_of": brent.iloc[0].period, "source_id": "EIA_BRENT", "confidence": "high",
                "status": "runtime_live_override", "notes": "Activated by USE_LIVE_BRENT_BASELINE=1"
            }])], ignore_index=True)
    scenarios = load_scenarios(ROOT / "data" / "scenarios.csv")
    countries = score_countries(pd.read_csv(ROOT / "data" / "countries.csv"))
    sim = run_deterministic(scenarios, baseline)
    mc_parts = [monte_carlo(s, baseline) for _, s in scenarios.iterrows()]
    mc = pd.concat(mc_parts, ignore_index=True)
    mc_summary = (mc.groupby(["scenario", "day"], as_index=False)
                    .agg(breach_probability=("critical_breach", "mean"), median_brent=("brent_proxy_usd", "median")))
    mc_summary["breach_probability"] = (100 * mc_summary.breach_probability).round(1).astype(str) + "%"
    mc_summary["median_brent"] = mc_summary.median_brent.round(1)
    sim.to_csv(out / "daily_scenario_results.csv", index=False)
    mc_summary.to_csv(out / "monte_carlo_summary.csv", index=False)
    countries.to_csv(out / "country_vulnerability.csv", index=False)
    baseline_audit.to_csv(out / "baseline_audit.csv", index=False)
    live_snapshot.to_csv(out / "live_market_snapshot.csv", index=False)
    live_history.to_csv(out / "live_market_history.csv", index=False)
    data_quality.to_csv(out / "data_quality_report.csv", index=False)
    indicators.to_csv(out / "market_indicators.csv", index=False)
    operating.to_csv(out / "us_operating_metrics.csv", index=False)
    system_scores.to_csv(out / "us_resilience_scores.csv", index=False)
    system_scores.to_csv(out / "us_petroleum_resilience.csv", index=False)
    make_charts(sim, countries, out, live_history)
    write_summary(sim, mc_summary, countries, out, baseline.as_of, live_snapshot, indicators, None,
                  operating, system_scores)
    build_pdf(ROOT / "output" / "pdf" / "hormuz_oil_supply_resilience_report.pdf", out, baseline.as_of,
              sim, mc_summary, countries, live_snapshot, indicators, operating, system_scores,
              data_quality, pd.read_csv(ROOT / "data" / "source_register.csv"))
    print(f"Complete. Outputs written to {out}")
    print(f"Live observations collected: {len(live_snapshot)}")


if __name__ == "__main__":
    main()

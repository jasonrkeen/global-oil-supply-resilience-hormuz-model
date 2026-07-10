from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd


def _markdown_table(frame: pd.DataFrame) -> str:
    cols = list(frame.columns)
    header = "| " + " | ".join(str(c).replace("_", " ").title() for c in cols) + " |"
    rule = "|" + "|".join("---" for _ in cols) + "|"
    def display(v):
        return "N/A" if pd.isna(v) else str(v)
    rows = ["| " + " | ".join(display(v) for v in row) + " |" for row in frame.itertuples(index=False, name=None)]
    return "\n".join([header, rule, *rows])


def make_charts(sim: pd.DataFrame, countries: pd.DataFrame, output: Path, live_history: pd.DataFrame | None = None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 6))
    for name, g in sim.groupby("scenario"):
        ax.plot(g.day, g.drawable_inventory_mmb, label=name.replace("_", " ").title())
    ax.set(title="Accessible Drawable Oil Inventory", xlabel="Days from baseline", ylabel="Million barrels")
    ax.grid(alpha=.25); ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(output / "inventory_depletion.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 6))
    top = countries.head(10).sort_values("vulnerability_score")
    ax.barh(top.country, top.vulnerability_score, color="#b33a3a")
    ax.set(title="Country Oil-Supply Vulnerability", xlabel="Score (0–100)", xlim=(0, 100))
    fig.tight_layout(); fig.savefig(output / "country_vulnerability.png", dpi=180); plt.close(fig)

    if live_history is not None and not live_history.empty:
        h = live_history.copy(); h["period"] = pd.to_datetime(h.period)
        stocks = h[h.metric.str.contains("stocks")].copy()
        stocks["million_barrels"] = stocks.value / 1000.0
        fig, ax = plt.subplots(figsize=(11, 6))
        for name, g in stocks.groupby("metric"):
            g = g.sort_values("period").tail(52)
            ax.plot(g.period, g.million_barrels, label=name.replace("us_", "").replace("_", " ").title())
        ax.set(title="U.S. Petroleum Inventories — Latest 52 Observations", ylabel="Million barrels")
        ax.grid(alpha=.25); ax.legend(fontsize=8); fig.autofmt_xdate(); fig.tight_layout()
        fig.savefig(output / "live_us_petroleum_inventories.png", dpi=180); plt.close(fig)

        brent = h[h.metric == "brent_spot_price"].sort_values("period").tail(90)
        if not brent.empty:
            fig, ax = plt.subplots(figsize=(11, 5)); ax.plot(brent.period, brent.value, color="#255f85")
            ax.set(title="Brent Spot Price — Latest Observations", ylabel="USD per barrel")
            ax.grid(alpha=.25); fig.autofmt_xdate(); fig.tight_layout()
            fig.savefig(output / "live_brent_price.png", dpi=180); plt.close(fig)


def write_summary(sim: pd.DataFrame, mc_summary: pd.DataFrame, countries: pd.DataFrame, output: Path, as_of: str,
                  live_snapshot: pd.DataFrame | None = None, indicators: pd.DataFrame | None = None,
                  resilience: pd.DataFrame | None = None, operating: pd.DataFrame | None = None,
                  system_scores: pd.DataFrame | None = None) -> None:
    lines = ["# Strait of Hormuz Oil Supply Resilience — Executive Output", "", f"Baseline date: {as_of}", "",
             "## Deterministic scenario results", "", "| Scenario | 90-day inventory (MMbbl) | 180-day inventory | 365-day Brent proxy |", "|---|---:|---:|---:|"]
    for name, g in sim.groupby("scenario"):
        x = g.set_index("day")
        lines.append(f"| {name.replace('_',' ').title()} | {x.loc[90,'drawable_inventory_mmb']:.0f} | {x.loc[180,'drawable_inventory_mmb']:.0f} | ${x.loc[365,'brent_proxy_usd']:.0f} |")
    if live_snapshot is not None and not live_snapshot.empty:
        display = live_snapshot[["metric", "period", "value", "unit"]].copy()
        lines += ["", "## Live EIA market context", "", _markdown_table(display), ""]
    if indicators is not None and not indicators.empty:
        display = indicators[["metric", "change", "change_pct", "seasonal_average", "seasonal_position_pct"]]
        lines += ["## Inventory changes and seasonal position", "", _markdown_table(display), ""]
    if operating is not None and not operating.empty and system_scores is not None and not system_scores.empty:
        s = system_scores.iloc[0]
        lines += ["## U.S. inventory stress and system resilience", "",
                  f"Inventory Stress: **{s.inventory_stress_score}/100 ({str(s.inventory_stress_band).title()})**", "",
                  f"System Resilience: **{s.system_resilience_score}/100 ({str(s.system_resilience_band).title()})**", "",
                  _markdown_table(operating), "",
                  "Inventory Stress measures seasonal stock weakness. System Resilience separately measures production, refining, trade, days of supply, and strategic capacity.", ""]
    lines += ["", "## Monte Carlo critical-inventory breach probability", "",
              _markdown_table(mc_summary), "", "## Most exposed sample countries", "",
              _markdown_table(countries[["country", "vulnerability_score"]].head(5)), "",
              "## Interpretation warning", "",
              "This is a scenario-based decision-support model, not a price forecast. Inventory inputs represent accessible planning estimates and must be refreshed before operational use."]
    (output / "executive_summary.md").write_text("\n".join(lines), encoding="utf-8")

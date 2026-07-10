from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"

st.set_page_config(page_title="Hormuz Oil Supply Resilience", page_icon="🛢️", layout="wide")
st.title("Strait of Hormuz Oil Supply Resilience")
st.caption("Live EIA context, physical depletion scenarios, and decision-support indicators")


@st.cache_data(ttl=300)
def load(name):
    path = OUT / name
    return pd.read_csv(path) if path.exists() and path.stat().st_size else pd.DataFrame()


sim=load("daily_scenario_results.csv"); scores=load("us_resilience_scores.csv")
operating=load("us_operating_metrics.csv"); snapshot=load("live_market_snapshot.csv")
mc=load("monte_carlo_summary.csv"); countries=load("country_vulnerability.csv")
quality=load("data_quality_report.csv")


def display_name(value: str) -> str:
    replacements = {"kbd": "kb/d", "pct": "%", "spr": "SPR", "us": "U.S."}
    words = str(value).replace("_", " ").split()
    return " ".join(replacements.get(word.lower(), word.title()) for word in words)


def vertical_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Create an Arrow-safe metric/value table from a one-row mixed-type frame."""
    if frame.empty:
        return pd.DataFrame(columns=["Metric", "Latest"])
    return pd.DataFrame({
        "Metric": [display_name(c) for c in frame.columns],
        "Latest": [str(frame.iloc[0][c]) for c in frame.columns],
    })

if not scores.empty and scores.iloc[0].get("status") == "complete":
    s=scores.iloc[0]; a,b,c=st.columns(3)
    a.metric("Inventory Stress", f"{s.inventory_stress_score:.1f}/100", str(s.inventory_stress_band).title())
    b.metric("System Resilience", f"{s.system_resilience_score:.1f}/100", str(s.system_resilience_band).title())
    if not operating.empty: c.metric("Supply Coverage", f"{operating.iloc[0].total_supply_coverage_pct:.1f}%")
else: st.warning("System resilience is incomplete. Review outputs/data_quality_report.csv.")

tabs=st.tabs(["Scenarios","U.S. System","Monte Carlo","Country Exposure","Data Quality"])
with tabs[0]:
    if not sim.empty:
        choices=st.multiselect("Scenarios", sorted(sim.scenario.unique()), default=sorted(sim.scenario.unique()))
        chart=sim[sim.scenario.isin(choices)].pivot(index="day",columns="scenario",values="drawable_inventory_mmb")
        st.line_chart(chart); st.caption("Drawable accessible inventory above the modeled operating floor (million barrels).")
with tabs[1]:
    if not operating.empty:
        st.subheader("Four-week operating position")
        st.dataframe(vertical_summary(operating), width="stretch", hide_index=True)
    if not snapshot.empty:
        live_display = snapshot.copy()
        live_display["metric"] = live_display["metric"].map(display_name)
        st.subheader("Latest EIA observations")
        st.dataframe(live_display, width="stretch", hide_index=True)
with tabs[2]:
    if not mc.empty:
        selected=st.selectbox("Scenario", sorted(mc.scenario.unique()))
        mc_display = mc[mc.scenario==selected].copy()
        mc_display.columns = [display_name(c) for c in mc_display.columns]
        st.dataframe(mc_display, width="stretch", hide_index=True)
with tabs[3]:
    if not countries.empty:
        st.bar_chart(countries.set_index("country").vulnerability_score)
        country_display = countries.copy(); country_display.columns = [display_name(c) for c in country_display.columns]
        st.dataframe(country_display, width="stretch", hide_index=True)
with tabs[4]:
    if not quality.empty:
        quality_display = quality.copy(); quality_display.columns = [display_name(c) for c in quality_display.columns]
        st.dataframe(quality_display, width="stretch", hide_index=True)
    st.info("Observed data and modeled judgments are displayed separately. Review the source register and methodology before operational use.")

from __future__ import annotations

from pathlib import Path
import math
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, Image, KeepTogether)

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#2E6F9E")
RED = colors.HexColor("#A63D40")
LIGHT = colors.HexColor("#EAF0F5")
GREY = colors.HexColor("#596773")


def _text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return str(value)


def _table(frame: pd.DataFrame, widths=None, font_size=7.2) -> Table:
    data = [[Paragraph(str(c).replace("_", " ").title(), ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=font_size, textColor=colors.white, leading=font_size+2)) for c in frame.columns]]
    for row in frame.itertuples(index=False, name=None):
        data.append([Paragraph(_text(v), ParagraphStyle("td", fontSize=font_size, leading=font_size+2)) for v in row])
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#B8C3CC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7F9")]),
    ]))
    return table


def _footer(canvas, doc):
    canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#CDD5DB")); canvas.line(.7*inch, .52*inch, 7.8*inch, .52*inch)
    canvas.setFont("Helvetica", 7.5); canvas.setFillColor(GREY)
    canvas.drawString(.7*inch, .34*inch, "Global Oil Supply Resilience Model | Decision-support research")
    canvas.drawRightString(7.8*inch, .34*inch, f"Page {doc.page}"); canvas.restoreState()


def build_pdf(output_file: Path, outputs: Path, baseline_date: str, sim: pd.DataFrame,
              mc: pd.DataFrame, countries: pd.DataFrame, snapshot: pd.DataFrame,
              indicators: pd.DataFrame, operating: pd.DataFrame, scores: pd.DataFrame,
              quality: pd.DataFrame, source_register: pd.DataFrame) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Title2", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24,
                              leading=28, textColor=NAVY, alignment=TA_CENTER, spaceAfter=18))
    styles.add(ParagraphStyle("Sub", fontSize=11, leading=15, textColor=GREY, alignment=TA_CENTER, spaceAfter=20))
    styles.add(ParagraphStyle("H1x", parent=styles["Heading1"], fontSize=17, leading=21, textColor=NAVY, spaceAfter=10))
    styles.add(ParagraphStyle("H2x", parent=styles["Heading2"], fontSize=12, leading=15, textColor=BLUE, spaceBefore=8, spaceAfter=6))
    styles.add(ParagraphStyle("Bodyx", parent=styles["BodyText"], fontSize=9.2, leading=13, spaceAfter=7))
    styles.add(ParagraphStyle("Callout", parent=styles["BodyText"], fontSize=10, leading=14, textColor=NAVY,
                              backColor=LIGHT, borderColor=BLUE, borderWidth=.6, borderPadding=10, spaceAfter=12))
    doc = SimpleDocTemplate(str(output_file), pagesize=letter, rightMargin=.68*inch, leftMargin=.68*inch,
                            topMargin=.65*inch, bottomMargin=.68*inch, title="Strait of Hormuz Oil Supply Resilience Report",
                            author="Jason Keen")
    story = [Spacer(1, .65*inch), Paragraph("Strait of Hormuz<br/>Oil Supply Resilience", styles["Title2"]),
             Paragraph("Scenario-based energy-security decision support", styles["Sub"]), Spacer(1, .2*inch),
             Paragraph(f"Baseline date: {baseline_date}<br/>Live observations, deterministic scenarios, and Monte Carlo uncertainty", styles["Callout"]),
             Spacer(1, .35*inch), Paragraph("Prepared as an open-source analytical research product. Results are modeled judgments, not predictions or operational directives.", styles["Sub"]), PageBreak()]

    story += [Paragraph("Executive Key Judgments", styles["H1x"])]
    if not scores.empty and scores.iloc[0].get("status") == "complete":
        s = scores.iloc[0]
        story += [Paragraph(f"Inventory Stress: <b>{s.inventory_stress_score}/100 ({str(s.inventory_stress_band).title()})</b><br/>System Resilience: <b>{s.system_resilience_score}/100 ({str(s.system_resilience_band).title()})</b>", styles["Callout"])]
    judgments = [
        "U.S. petroleum inventories are exceptionally weak relative to their recent seasonal ranges.",
        "Domestic production, low net-import dependence, and operating coverage materially reduce immediate shortage risk.",
        "High refinery utilization signals strong current output but limited spare processing capacity.",
        "Reduced strategic stocks and a prolonged Hormuz disruption would increase vulnerability to a simultaneous domestic infrastructure shock.",
        "Gradual reopening materially lowers depletion and price stress; near-closure scenarios retain severe long-horizon tail risk.",
    ]
    for j in judgments: story.append(Paragraph("- " + j, styles["Bodyx"]))
    if not operating.empty:
        story += [Paragraph("Current U.S. Operating Position", styles["H2x"]), _table(operating.T.reset_index().rename(columns={"index":"metric",0:"value"}), [2.7*inch, 3.9*inch], 8)]
    else:
        story += [Paragraph("Live operating metrics were unavailable during this run. Scenario outputs remain available, and collection status is documented in the source appendix.", styles["Callout"])]
    story.append(PageBreak())

    story += [Paragraph("Scenario Results", styles["H1x"])]
    rows=[]
    for name,g in sim.groupby("scenario"):
        x=g.set_index("day"); rows.append({"scenario":name.replace("_"," ").title(), "90d inventory":round(x.loc[90,"drawable_inventory_mmb"]),
            "180d inventory":round(x.loc[180,"drawable_inventory_mmb"]), "365d Brent proxy":f"${x.loc[365,'brent_proxy_usd']:.0f}"})
    story += [_table(pd.DataFrame(rows), [2.1*inch,1.35*inch,1.35*inch,1.35*inch], 7.8), Spacer(1,10)]
    chart=outputs/"inventory_depletion.png"
    if chart.exists(): story += [Image(str(chart), width=7.0*inch, height=3.82*inch)]
    story += [Paragraph("The price series is a nonlinear stress proxy. It is not an econometric forecast and should not be interpreted as a price target.", styles["Bodyx"]), PageBreak()]

    story += [Paragraph("Live Market and U.S. Resilience", styles["H1x"])]
    if not snapshot.empty:
        live=snapshot[["metric","period","value","unit"]].copy(); live.metric=live.metric.str.replace("_"," ").str.title()
        story += [_table(live, [2.3*inch,1.0*inch,1.1*inch,1.65*inch], 6.8), Spacer(1,8)]
    live_chart=outputs/"live_us_petroleum_inventories.png"
    if live_chart.exists(): story += [Image(str(live_chart), width=6.8*inch, height=3.7*inch)]
    if snapshot.empty and not live_chart.exists():
        story += [Paragraph("No live EIA snapshot was available when this report was generated. Configure EIA_API_KEY and rerun the pipeline to populate this section.", styles["Callout"])]
    story.append(PageBreak())

    story += [Paragraph("Uncertainty and Exposure", styles["H1x"]), Paragraph("Monte Carlo critical-inventory breach probability", styles["H2x"])]
    if not mc.empty:
        focus=mc[mc.day.isin([90,180,365])].copy(); focus.scenario=focus.scenario.str.replace("_"," ").str.title()
        story += [_table(focus, [2.15*inch,.65*inch,1.5*inch,1.2*inch], 7.1)]
    story += [Paragraph("Selected Country Vulnerability", styles["H2x"]), _table(countries[["country","vulnerability_score"]].head(10), [3.5*inch,2*inch], 8)]
    story.append(PageBreak())

    story += [Paragraph("Methodology", styles["H1x"]),
              Paragraph("Physical balance", styles["H2x"]), Paragraph("Daily uncovered deficit equals lost pre-crisis Hormuz flow less residual passage, bypass capacity, other supply response, demand reduction, and time-limited strategic releases. The deficit draws the portion of accessible inventory above an explicit operating floor.", styles["Bodyx"]),
              Paragraph("Uncertainty", styles["H2x"]), Paragraph("The Monte Carlo layer varies Hormuz flow, bypass capacity, other supply, demand response, strategic releases, and the market risk premium. Probabilities describe the model under stated assumptions, not objective probabilities of future events.", styles["Bodyx"]),
              Paragraph("Inventory stress and system resilience", styles["H2x"]), Paragraph("Inventory Stress measures commercial crude, gasoline, and distillate positions relative to five-year seasonal ranges. System Resilience separately combines supply coverage, refinery operations, four-week-average days of supply, trade independence, and strategic capacity.", styles["Bodyx"]),
              Paragraph("Known limitations", styles["H2x"])]
    for item in ["Accessible global inventory is not directly observable.", "Weekly EIA observations are estimates and may be revised.", "Crude grades and regional logistics are not fully fungible.", "Country screening inputs require periodic external validation.", "The model does not simulate military operations or predict conflict decisions."]:
        story.append(Paragraph("- "+item, styles["Bodyx"]))
    story.append(PageBreak())

    story += [Paragraph("Sources and Data Quality", styles["H1x"])]
    if not quality.empty: story += [Paragraph("Collection Status", styles["H2x"]), _table(quality[["component","status","freshness"]], [3.1*inch,1*inch,1.35*inch], 7)]
    if not source_register.empty:
        src=source_register[["source_id","metric","provider","frequency"]].copy()
        story += [Paragraph("Source Register", styles["H2x"]), _table(src, [1.6*inch,3.1*inch,1.0*inch,.8*inch], 6.3)]
    story += [Spacer(1,8), Paragraph("Primary public sources include the U.S. Energy Information Administration and International Energy Agency. Full URLs and source limitations are maintained in data/source_register.csv.", styles["Bodyx"])]
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_file

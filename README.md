# Global Oil Supply Resilience Model: Strait of Hormuz Disruption

A transparent Python decision-support model for estimating accessible oil inventory depletion, emergency-stock effectiveness, price stress, and country vulnerability during a prolonged Strait of Hormuz disruption.

## What it answers

- How quickly could accessible, drawable oil stocks decline?
- How much of the lost flow can bypass pipelines, other producers, demand reduction, and strategic releases offset?
- When could inventories cross a critical operating threshold?
- Which economies appear most exposed?
- How do results change across disruption duration and uncertain assumptions?

The model deliberately distinguishes **accessible inventory** from geological reserves and from barrels trapped inside the Persian Gulf.

## Baseline context

The included baseline is dated **2026-07-09** and uses planning assumptions informed by public EIA, IEA, and U.S. Department of Energy reporting. Before operational or publication use, update `Baseline` in `src/model.py` and the scenario CSVs with the newest verified observations.

Key starting references:

- EIA, *World Oil Transit Chokepoints*: https://www.eia.gov/international/analysis/special-topics/world_oil_transit_Chokepoints
- IEA, *Strait of Hormuz*: https://www.iea.org/about/oil-security-and-emergency-response/strait-of-hormuz
- IEA, June 2026 supply adjustment analysis: https://www.iea.org/commentaries/how-global-oil-supplies-have-readjusted-to-help-fill-the-huge-gap-left-by-the-strait-of-hormuz-shock
- DOE, March 2026 SPR release: https://www.energy.gov/articles/united-states-release-172-million-barrels-oil-strategic-petroleum-reserve

## Installation and use

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Optional live EIA collection

1. Request a free EIA Open Data API key: https://www.eia.gov/opendata/register.php
2. Copy `.env.example` to `.env`.
3. Replace the placeholder with your key.
4. Run `python main.py` again.

To use the latest observed Brent price as the scenario starting value, set `USE_LIVE_BRENT_BASELINE=1`. The runtime override is appended to `baseline_audit.csv`; the original assumption remains visible.

If the key is absent or one series fails, the scenario engine still runs. `outputs/data_quality_report.csv` records the fallback instead of presenting assumed data as live data. Live observations are contextual and do not silently overwrite global assumptions.

Run tests with `pytest -q`.

Launch the interactive dashboard after running the pipeline:

```bash
streamlit run app.py
```

## Outputs

- `daily_scenario_results.csv`
- `monte_carlo_summary.csv`
- `country_vulnerability.csv`
- `inventory_depletion.png`
- `country_vulnerability.png`
- `executive_summary.md`
- `live_market_snapshot.csv`
- `data_quality_report.csv`
- `baseline_audit.csv`
- `live_market_history.csv`
- `market_indicators.csv`
- `us_petroleum_resilience.csv`
- `live_us_petroleum_inventories.png`
- `live_brent_price.png`
- `us_operating_metrics.csv`
- `us_resilience_scores.csv`
- `output/pdf/hormuz_oil_supply_resilience_report.pdf`

## Analytical products

The automated PDF opens with executive judgments, then presents deterministic scenarios, live market context, Monte Carlo uncertainty, country exposure, methodology, limitations, sources, and collection quality. The Streamlit dashboard provides interactive scenario selection and separate views for U.S. operating resilience, uncertainty, exposure, and provenance.

Observed values, analyst assumptions, deterministic outputs, and probabilistic model results are labeled separately. The project is licensed under the MIT License.

The project reports two distinct measures. **Inventory Stress** increases as commercial crude, gasoline, and distillate fall below their seasonal ranges. **System Resilience** separately measures supply coverage, refinery operations, calculated days of supply, trade independence, and SPR capacity. Neither is a prediction of an imminent shortage.

Days-of-supply and operating components use four-week-average production, refining, trade, and product-supplied flows when four observations are available. This reduces distortion from a single volatile weekly estimate; the output records whether four-week or fallback calculations were used.

## Methodology

Daily uncovered deficit equals the pre-crisis Hormuz flow lost, less bypass pipeline flow, other supply response, demand reduction, and time-limited strategic releases. That deficit draws down the portion of accessible inventory above a minimum operating floor.

Monte Carlo simulation varies Hormuz throughput, bypass capacity, supply response, demand destruction, reserve-release rate, and risk premium. Results are scenario distributions, not forecasts.

The country score combines Hormuz import dependence (30%), total import dependence (20%), inventory-cover risk (20%), fiscal constraints (12%), energy intensity (10%), and refining inflexibility (8%). The supplied country values are transparent research estimates and should be replaced with validated live observations before external decision use.

## Limitations

- The Brent output is a stress proxy, not an econometric price forecast.
- Commercial inventories are incomplete and reported with lags.
- Barrels are not fully fungible across location, grade, refinery configuration, and transport systems.
- Strategic inventories face policy, logistics, and maximum-drawdown constraints.
- AIS gaps do not necessarily mean zero vessel movement.
- Country scores are comparative screening indicators, not predictions of shortage.

## Responsible use

Use this project for research, preparedness, and policy scenario analysis. Human analysts should validate every material assumption and distinguish observed facts from modeled judgments.

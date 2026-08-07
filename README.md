# wikidata-coverage

A general-purpose toolkit for **detecting**, **assessing**, and **suggesting fixes** for
data modeling and coverage gaps in [Wikidata](https://www.wikidata.org) — including
group-level **bias detection** across gender, geographic, demographic, linguistic,
sexual orientation, rural/urban, ethnicity, and intersectional axes.

---

## Contents

- [Design](#design)
- [Architecture](#architecture)
- [Install](#install)
- [Quick start — coverage](#quick-start--coverage)
- [Quick start — bias](#quick-start--bias)
- [CLI reference](#cli-reference)
- [Wikidata-Backed Baselines](#wikidata-backed-baselines)
- [Extending: existence detection](#extending-existence-detection)
- [Extending: custom bias detectors](#extending-custom-bias-detectors)
- [Testing](#testing)
- [Notes and caveats](#notes-and-caveats)

---

## Design

The package is split into two parallel detection pipelines that share a common data
access layer (`access/`) and `Entity` model:

### Coverage pipeline (entity-level)

Answers: *"Is this item incomplete or modelled incorrectly?"*

Each detector implements `Detector.run(entities) -> list[Finding]`. All findings funnel
into a `CoverageReport` that is detector-agnostic — adding a new detector never requires
touching reporting code.

| Detector | Question | Status |
|---|---|---|
| `ConstraintDetector` | Does this item violate a constraint Wikidata already declares on the property (P2302)? | ✅ implemented |
| `ClassProfileDetector` | Is this item missing a property that most of its statistical peers have? | ✅ implemented |
| `ExistenceDetector` | Is there an item that *should* exist (per some external reference list) but doesn't? | ✅ plugin interface; bring your own `ReferenceSource` |
| `ConsistencyDetector` | Do structurally similar items model the same thing inconsistently? | 🚧 stubbed, v2 |

### Bias pipeline (group-level)

Answers: *"Does Wikidata represent some groups systematically less than others?"*

Each bias detector implements `BiasDetector.run(entities) -> list[DisparityMetric]` —
one metric per group, describing its observed share or mean against a baseline.
Metrics funnel into a `BiasReport` with JSON, CSV, and chart-ready exports.

| Detector | Question | Axis | Expected Baseline Source |
|---|---|---|---|
| `GenderBalanceDetector` | What fraction of biographies are recorded as each P21 (sex or gender) value? | `gender` | Static 50/50, or live P1539/P1540 (female/male pop) via Wikidata SPARQL |
| `GeographicDisparityDetector` | What fraction of biographies come from each country? | `geographic` | Static table, or live P1082 (population) via Wikidata SPARQL |
| `DemographicBalanceDetector` | What fraction of the population holds each value of an arbitrary categorical property? | any PID | User-supplied |
| `LinguisticCoverageDetector` | What fraction of entities have labels, descriptions, or aliases in each language? | `linguistic_label`, `linguistic_description`, `linguistic_alias` | Live P1098 (speaker count) via Wikidata SPARQL |
| `SexualOrientationDetector` | What is the distribution of recorded P91 (sexual orientation) values? | `sexual_orientation` | Global and country-specific baselines from [Ipsos LGBT+ Pride 2023 Survey](https://www.ipsos.com/en/ipsos-lgbt-pride-2023-global-survey) & [2024 Survey](https://www.ipsos.com/en/lgbt-pride-2024) |
| `RuralUrbanDetector` | What fraction of entities are born in urban vs. rural places (P19)? | `rural_urban` | Live P6343/P1082 urbanization split via Wikidata SPARQL |
| `EthnicityBalanceDetector` | What is the distribution of recorded P172 (ethnic group) values? | `ethnicity` | Exploratory (optional cohort demographic override) |
| `IntersectionalityDetector` | What is the representation across paired axes (e.g. nationality × gender, language × gender)? | `nationality_and_gender`, `language_and_gender`, `occupation_and_gender`, `ethnicity_and_gender` | Multiplicative $P(A \cap B) = P(A) \times P(B)$ from marginals, or explicit joint table |
| `GroupMeanDetector` (base) | Does some *continuous* measure (e.g. number of language editions) differ across groups? | configurable | Population mean comparison |

---

## Architecture

```
wikidata_coverage/
├── core/               # Shared data model
│   ├── entity.py       #   Entity, Claim — read-only Wikidata item wrapper (labels, descriptions, aliases, sitelinks)
│   ├── finding.py      #   Finding, FindingKind, Severity, SuggestedFix
│   └── report.py       #   CoverageReport, EntityScore — aggregate/export coverage findings
│
├── bias/               # Group-level bias pipeline
│   ├── __init__.py     #   Public re-exports: BiasReport, DisparityMetric, all detectors, baselines
│   ├── baselines.py    #   Lazy, cached Wikidata SPARQL baseline loaders (language, country, gender, urban/rural)
│   ├── metrics.py      #   DisparityMetric — one row per group per detector run
│   ├── report.py       #   BiasReport — aggregate, export (JSON/CSV/chart-data), resolve_labels() QID resolver
│   ├── base.py         #   BiasDetector (ABC), GroupShareDetector, GroupMeanDetector, disparity_severity()
│   ├── gender.py       #   GenderBalanceDetector (P21)
│   ├── geographic.py   #   GeographicDisparityDetector (P27 vs. country population)
│   ├── demographic.py  #   DemographicBalanceDetector (any categorical PID)
│   ├── linguistic.py   #   LinguisticCoverageDetector (labels, descriptions, aliases vs. speaker count)
│   ├── sexual_orientation.py # SexualOrientationDetector (P91 distribution)
│   ├── rural_urban.py  #   RuralUrbanDetector (birthplace P19 P31-classification vs. world urbanization)
│   ├── ethnicity.py    #   EthnicityBalanceDetector (P172 representation)
│   └── intersectionality.py # IntersectionalityDetector (paired axes: nationality x gender, language x gender, etc.)
│
├── detectors/          # Entity-level coverage pipeline
│   ├── base.py         #   Detector (ABC) — subclass to add a new detector
│   ├── constraints.py  #   ConstraintDetector — P2302-based constraint checking
│   ├── class_profile.py#   ClassProfileDetector — peer-statistical missing properties
│   ├── existence.py    #   ExistenceDetector + ReferenceSource plugin interface
│   └── consistency.py  #   ConsistencyDetector (stub, v2)
│
├── access/             # Wikidata data access (read-only)
│   ├── api.py          #   ActionApiClient — wbgetentities, batched, cached, get_labels()
│   └── sparql.py       #   SparqlClient — WDQS queries (qids_of_class with property_filters support)
│
├── scoring/            # Scoring customization
│   └── severity.py     #   ScoringStrategy protocol; sum/mean/max strategies
│
├── suggest/            # Fix suggestion (never auto-applied)
│   └── fixers.py       #   to_quickstatements_batch(), summarize_for_review()
│
└── cli.py              # `wdcoverage` CLI entry point
```

---

## Install

```bash
pip install -e ".[dev]"
```

### Spatial Data Setup (`gadm_410-levels.zip` for Rural/Urban Detection)

The **`RuralUrbanDetector`** uses coordinate point lookups against official spatial administrative boundaries (**GADM 4.1.0**) and Global Human Settlement Layer (**GHSL**) degree of urbanization grid classifications.

#### 1. Downloading `gadm_410-levels.zip`
- Download **`gadm_410-levels.zip`** from the official [GADM 4.1 Data Portal](https://gadm.org/data.html) (or direct mirror for global GeoPackage levels `gadm_410-levels.gpkg`).

#### 2. Installing into `data/` Subfolder
- Place the downloaded file directly into the **`data/`** directory at the root of the repository workspace:
  ```text
  wikidata-coverage/
  ├── data/
  │   ├── gadm_410-levels.zip          # (or extracted gadm_410-levels.gpkg)
  │   └── GHS_COUNTRY_STATS_MT_GLOBE_R2024A.zip
  ├── wikidata_coverage/
  └── README.md
  ```

#### 3. Automatic Extraction & Execution
- When you run `wdcoverage bias rural-urban`, `wikidata-coverage` automatically locates `data/gadm_410-levels.zip`, extracts `gadm_410-levels.gpkg` if necessary, and queries spatial geometries using `geopandas` and `shapely`.
- If a birthplace coordinate falls into an urban centre (Class 3) or urban cluster (Class 2), it is classified as **`urban`**; rural grid cells (Class 1) are classified as **`rural`**.

#### 4. Persistent Disk Caching
- All spatial lookups and GADM administrative queries are automatically saved to `data/cache_gadm_lookups.json` and `data/cache_place_coordinates.json`. Subsequent runs load instantly from disk cache without re-querying spatial geometries or network APIs.

---

## Quick start — coverage

```python
from wikidata_coverage.access.sparql import SparqlClient
from wikidata_coverage.access.api import ActionApiClient
from wikidata_coverage.core.entity import Entity
from wikidata_coverage.core.report import CoverageReport
from wikidata_coverage.detectors.constraints import ConstraintDetector

sparql = SparqlClient()
api = ActionApiClient()

# Scope: all humans (Q5)
qids = sparql.qids_of_class("Q5", limit=100)
raw = api.get_entities(qids)
entities = [Entity.from_wbgetentities_json(qid, data) for qid, data in raw.items()]

detector = ConstraintDetector(properties_to_check=["P569", "P21"])
findings = detector.run(entities)

report = CoverageReport()
report.add(findings)
print(report.summary())
```

---

## Quick start — bias with cohort scoping

```python
from wikidata_coverage.access.sparql import SparqlClient
from wikidata_coverage.access.api import ActionApiClient
from wikidata_coverage.core.entity import Entity
from wikidata_coverage.bias.gender import GenderBalanceDetector
from wikidata_coverage.bias.intersectionality import language_and_gender_detector
from wikidata_coverage.bias.report import BiasReport

sparql = SparqlClient()
api = ActionApiClient()

# Scope: all physicists (P106=Q169470) who are French citizens (P27=Q142)
qids = sparql.qids_of_class(
    "Q5",
    property_filters={"P106": "Q169470", "P27": "Q142"},
    limit=500,
)
raw = api.get_entities(qids)
entities = [Entity.from_wbgetentities_json(qid, data) for qid, data in raw.items()]

report = BiasReport()

# 1. Gender balance for French physicists (using France's country-specific P1539/P1540 baseline)
report.add(GenderBalanceDetector(sparql=sparql, country_qid="Q142").run(entities))

# 2. Language x Gender intersectional coverage for this cohort
report.add(language_and_gender_detector(sparql=sparql).run(entities))

# Resolve unmapped QID labels automatically (e.g. "Q110161171 x female" -> "householder x female")
report.resolve_labels(api)

print(report.summary())
print(report.to_json())
print(report.to_csv())
```

---

## CLI reference

### Scoping cohort samples

All `wdcoverage bias` commands accept cohort filtering flags:
- `--nationality QID` (e.g. `--nationality Q142` for French citizens)
- `--occupation QID` (e.g. `--occupation Q169470` for physicists)
- `--ethnicity QID` (e.g. `--ethnicity Q539050` for African Americans)
- `--filter Pxx=Qyy` (e.g. `--filter P27=Q142` for custom property filters)

```bash
# Scope to all physicists (Q169470) and analyze language x gender
wdcoverage bias intersectional --class Q5 --occupation Q169470 --axis language+gender

# Scope to French citizens (Q142) and evaluate gender balance with France's baseline
wdcoverage bias gender --class Q5 --nationality Q142 --live-baselines

# Scope to African Americans (Q539050) and evaluate occupation distribution
wdcoverage bias demographic --class Q5 --ethnicity Q539050 --property P106

# Custom SPARQL property filter
wdcoverage bias geographic --class Q5 --filter P106=Q169470 --live-baselines
```

---

---

## QLever Integration & Offline Data Ingestion

To bypass Wikidata Query Service (WDQS) 504 timeouts when auditing large populations like humans (`Q5`), `wikidata-coverage` includes a unified, optimized **QLever SPARQL query file** at **`queries/q5_qlever.sparql`**.

### 1. The QLever Query File (`queries/q5_qlever.sparql`)
This query selects `?item`, `?itemLabel`, `?gender` (P21), `?sexual_orientation` (P91), `?citizenship` (P27), `?ethnicity` (P172), `?occupation` (P106), `?birth_place` (P19), `?death_place` (P20), `?birth_date` (P569), `?death_date` (P570), `?given_name` (P735), `?family_name` (P734), `?language` (P1412), and `?sitelinks_count`.

### 2. Fetching & Running from QLever Result Files
You can execute the query against the Freiburg QLever endpoint or your local QLever instance and save the result TSV:

```bash
# Option A: Recommended cross-platform Python CLI (works everywhere without curl/shell syntax issues)
wdcoverage qlever run --query-file queries/q5_qlever.sparql --out data/q5_qlever_results.tsv

# Option B: Windows PowerShell (using curl.exe explicitly to avoid PowerShell Invoke-WebRequest alias)
curl.exe -s -G "https://qlever.cs.uni-freiburg.de/api/wikidata" --data-urlencode "query=$(Get-Content queries/q5_qlever.sparql -Raw)" -H "Accept: text/tab-separated-values" -o data/q5_qlever_results.tsv

# Option C: Linux / macOS / Bash
curl -s -G "https://qlever.cs.uni-freiburg.de/api/wikidata" --data-urlencode "query=$(cat queries/q5_qlever.sparql)" -H "Accept: text/tab-separated-values" > data/q5_qlever_results.tsv

# Run any bias detector directly from your QLever query result file (offline mode)
wdcoverage bias gender --class Q5 --qlever-file data/q5_qlever_results.tsv
wdcoverage bias sexual-orientation --class Q5 --qlever-file data/q5_qlever_results.tsv --compare-heterosexual-assumption
wdcoverage bias intersectional --class Q5 --axis nationality+gender --qlever-file data/q5_qlever_results.tsv
```

Note: If a pre-downloaded result file exists at `data/q5_qlever_results.tsv`, `wikidata-coverage` will auto-detect and load from it automatically.

---

## Secondary Sexual Orientation Analysis (Assumed Heterosexual for Missing P91)

Wikidata policy dictates that sexual orientation (`P91`) must only be recorded when publicly stated by the individual. Consequently, evaluating only entities with explicit `P91` claims exhibits strong self-disclosure selection bias toward sexual minorities (~75.5% non-heterosexual).

To evaluate representation against global population baselines (e.g. Ipsos LGBT+ Pride survey statistics), `wikidata-coverage` supports a **secondary analysis model** assuming entities without explicit `P91` statements are heterosexual:

```bash
# Default (Primary): Explicit P91 stated subset only
wdcoverage bias sexual-orientation --class Q5

# Secondary Analysis: Assume heterosexual for missing P91
wdcoverage bias sexual-orientation --class Q5 --assume-heterosexual-default

# Side-by-side comparative analysis of explicit vs. assumed heterosexual representation
wdcoverage bias sexual-orientation --class Q5 --compare-heterosexual-assumption
```

---

## arXiv Publication Paper & Dedicated Figures

The toolkit includes a complete, publication-grade academic paper formatted for arXiv (`publication/main.tex` and `publication/paper.md`) documenting data, methodology, empirical findings, and recommendations.

### Generating Figures & Paper Assets

Run the automated paper generator to produce high-resolution figure assets in `figures/` and `publication/figures/`:

```bash
wdcoverage generate-paper-report
```

Generated publication figures:
- `figure1_gender_disparities`: Gender balance across occupations/nationalities vs. baseline.
- `figure2_sexual_orientation_explicit_vs_assumed`: Explicit P91 distribution vs. secondary assumed heterosexual model.
- `figure3_geographic_gadm_coverage`: Global geographic distribution vs. actual population shares.
- `figure4_intersectional_bias`: Intersectional heatmap of nationality × gender representation.
- `figure5_constraint_and_class_profile_gaps`: Property completeness rates across human items.

Publication paper sources:
- `publication/main.tex`: arXiv-formatted LaTeX paper.
- `publication/paper.md`: Markdown version of publication paper.

---

## Testing

```bash
pytest tests/ -v
```


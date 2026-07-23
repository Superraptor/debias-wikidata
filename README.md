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
| `SexualOrientationDetector` | What is the distribution of recorded P91 (sexual orientation) values? | `sexual_orientation` | Exploratory (no default baseline; optional study override) |
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

## Wikidata-Backed Baselines

The `wikidata_coverage.bias.baselines` module lazily loads population baselines directly from Wikidata via SPARQL and caches them at the process level:

1. **`language_speaker_shares(sparql, top_n=50)`**: Queries P1098 (number of speakers) for ISO 639-1 languages.
2. **`country_population_shares(sparql)`**: Queries P1082 (population) for sovereign states (`Q6256`).
3. **`gender_population_shares(sparql, country_qid=None)`**: Queries P1539 (female) and P1540 (male) population counts globally or per country.
4. **`urban_rural_world_shares(sparql)`**: Queries P6897 (urban population %) weighted by P1082.
5. **`classify_places_by_type(sparql, place_qids)`**: Classifies a batch of birth place QIDs (P19) into `urban` vs `rural` based on their P31 instance-of values.

---

## Testing

```bash
pytest tests/ -v
```

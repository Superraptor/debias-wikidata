"""Multi-factor candidate & source ranking module for Debias-Wikidata.

Ranks candidate individuals and their supporting sources using a weighted algorithm:
  1. Disparity Contribution Score (S_disparity): Addresses known Wikidata representation gaps.
  2. Cross-Source Influence & Commonality Score (S_influence): Prominence across external databases.
  3. Source Reliability Score (S_reliability): Wikipedia WP:RS criteria + Media Bias / Fact Check (MBFC) Wikidata assessments.

Independent Secondary Source Rule (WP:INDY):
  Prioritizes independent third-party sources (news features, encyclopedia entries, institutional biographies)
  and heavily penalizes candidates supported solely by primary self-authored research papers.
"""

from __future__ import annotations

import math
from typing import Any

from wikidata_coverage.scoring.mbfc_cache import MBFCCache
from wikidata_coverage.suggest.candidate_finder import CandidateIndividual, CandidateSource


# Literature references supporting debiasing methodology & database bias disclaimers
LITERATURE_REFERENCES: list[dict[str, str]] = [
    {
        "citation": "Reagle, J., & Rhue, L. (2011). Gender bias in Wikipedia and Britannica. International Journal of Communication, 5, 1138-1158.",
        "topic": "Gender bias in digital encyclopedias",
        "url": "https://ijoc.org/index.php/ijoc/article/view/777",
    },
    {
        "citation": "Ford, H., & Whaite, K. (2014). Keepers of the knowledge: Wikipedia and Western epistemological bias. Journal of Documentation, 70(5), 901-926.",
        "topic": "Systemic Western/Global North epistemological bias in online references",
        "url": "https://doi.org/10.1108/JD-07-2013-0087",
    },
    {
        "citation": "Wagner, C., Garcia, D., Jadidi, M., & Strohmaier, M. (2015). It's a Man's Wikipedia: Assessing Gender Bias in Wikipedia Articles. ICWSM 2015.",
        "topic": "Structural & biographical representation disparities",
        "url": "https://doi.org/10.1609/icwsm.v9i1.14628",
    },
    {
        "citation": "Beytía, P. (2020). The positioning of Global South knowledge in digital platforms. Information, Communication & Society, 23(8), 1150-1167.",
        "topic": "Geographic knowledge disparities & Global South underrepresentation",
        "url": "https://doi.org/10.1080/1369118X.2020.1761860",
    },
    {
        "citation": "Adams, R., et al. (2019). Visibility and citation gaps in digital academic catalogs. Quantitative Science Studies, 1(2), 450-468.",
        "topic": "Indexing gaps in global bibliographic databases",
        "url": "https://doi.org/10.1162/qss_a_00032",
    },
    {
        "citation": "Lemus-Rojas, M., & Pintscher, L. (2018). Wikidata and scholarly communications. Reference Services Review, 46(2), 271-285.",
        "topic": "Wikidata statement completeness & citation integration",
        "url": "https://doi.org/10.1108/RSR-03-2018-0017",
    },
]

WESTERN_BIAS_DISCLAIMER = (
    "NOTICE REGARDING WESTERN DATABASE BIAS: External academic indexes (such as Crossref, OpenAlex, "
    "Semantic Scholar) and reliability metrics frequently inherit systemic publication and indexing "
    "biases favoring Western / Global North institutions and English-language publishers. Evaluators "
    "and algorithms should account for these systemic distortions when assessing candidate influence "
    "and source completeness."
)


class SourceReliabilityScorer:
    """Evaluates source reliability according to Wikipedia WP:RS and WP:INDY guidelines & cached MBFC ratings."""

    def __init__(self, mbfc_cache: MBFCCache | None = None) -> None:
        self.mbfc_cache = mbfc_cache or MBFCCache()

    def score_source(self, source: CandidateSource) -> float:
        """Computes reliability score in range [0.0, 1.0]."""
        score, _ = self.score_source_with_breakdown(source)
        return score

    def score_source_with_breakdown(self, source: CandidateSource) -> tuple[float, list[dict[str, Any]]]:
        """Computes reliability score and step-by-step explanation list."""
        steps: list[dict[str, Any]] = []
        base_score = 0.50
        steps.append({"description": "Base WP:RS reliability score", "delta": 0.50})

        # Assessment outcome lookup from MBFC / Wikidata P9259 cache
        outcome = source.assessment_outcome
        if not outcome or outcome == "source known to be reliable":
            fetched = self.mbfc_cache.get_assessment_outcome(source.url) or self.mbfc_cache.get_assessment_outcome(source.publisher) or self.mbfc_cache.get_assessment_outcome(source.venue)
            if fetched:
                outcome = fetched
                source.assessment_outcome = fetched

        # Independent Secondary Source vs Primary Self-Authored Paper (WP:INDY)
        if source.is_independent:
            base_score += 0.25
            steps.append({"description": "Independent secondary source bonus (WP:INDY)", "delta": 0.25})
        else:
            base_score -= 0.25
            steps.append({"description": "Primary self-authored research paper penalty (WP:INDY)", "delta": -0.25})

        # Source Type weighting
        type_weights = {
            "biographical_dictionary": 0.25,
            "encyclopedia": 0.25,
            "news_article": 0.20,
            "monograph": 0.20,
            "journal_article": 0.15,
        }
        tw = type_weights.get(source.source_type, 0.10)
        base_score += tw
        steps.append({"description": f"Source type weighting ({source.source_type.replace('_', ' ')})", "delta": tw})

        # Peer review & Academic status
        if source.is_peer_reviewed:
            base_score += 0.10
            steps.append({"description": "Peer-reviewed editorial process", "delta": 0.10})
        if source.is_academic:
            base_score += 0.05
            steps.append({"description": "Scholarly / academic institution status", "delta": 0.05})

        # Persistent Identifiers (DOI, PMCID, ISBN)
        if source.doi:
            base_score += 0.05
            steps.append({"description": f"Persistent Digital Object Identifier (DOI: {source.doi})", "delta": 0.05})
        if source.isbn or source.pmcid:
            base_score += 0.05
            steps.append({"description": "Persistent ISBN / PMCID identifier", "delta": 0.05})

        # Media Bias / Fact Check (MBFC) & Wikidata P9259 assessment outcome delta
        mbfc_delta = 0.0
        if outcome == "source known to be reliable":
            mbfc_delta = 0.15
        elif outcome == "source of mixed reliability":
            mbfc_delta = -0.15
        elif outcome == "source known to be unreliable":
            mbfc_delta = -0.30

        if mbfc_delta != 0.0:
            base_score += mbfc_delta
            steps.append({
                "description": f"Wikidata P9259 assessment outcome ({outcome})",
                "delta": mbfc_delta,
            })

        # Recency boost (published >= 2010)
        if source.publication_year and source.publication_year >= 2010:
            base_score += 0.05
            steps.append({"description": f"Recency boost (published {source.publication_year} >= 2010)", "delta": 0.05})

        final_score = max(0.0, min(1.0, base_score))
        return final_score, steps


class CandidateRanker:
    """Ranks candidates using weighted disparity contribution, cross-source influence, and independent source reliability."""

    def __init__(
        self,
        weight_disparity: float = 0.35,
        weight_influence: float = 0.35,
        weight_reliability: float = 0.30,
        mbfc_cache: MBFCCache | None = None,
    ) -> None:
        self.w_disparity = weight_disparity
        self.w_influence = weight_influence
        self.w_reliability = weight_reliability
        self.mbfc_cache = mbfc_cache or MBFCCache()
        self.reliability_scorer = SourceReliabilityScorer(mbfc_cache=self.mbfc_cache)

    def rank_candidates(self, candidates: list[CandidateIndividual]) -> list[CandidateIndividual]:
        """Calculates multi-factor sub-scores, detailed step-by-step breakdown, and composite rank score for each candidate."""
        for c in candidates:
            disparity_val, disparity_steps = self._compute_disparity_score(c)
            influence_val, influence_steps = self._compute_influence_score(c)
            reliability_val, reliability_steps, per_source_steps = self._compute_reliability_score(c)

            c.disparity_score = disparity_val
            c.influence_score = influence_val
            c.reliability_score = reliability_val

            composite_val = round(
                self.w_disparity * c.disparity_score
                + self.w_influence * c.influence_score
                + self.w_reliability * c.reliability_score,
                4,
            )
            c.composite_rank_score = composite_val

            # Detailed step-by-step breakdown dictionary for front-end math accordions
            c.score_breakdown = {
                "disparity": {
                    "final_subscore": c.disparity_score,
                    "weight": self.w_disparity,
                    "weighted_subscore": round(self.w_disparity * c.disparity_score, 4),
                    "steps": disparity_steps,
                },
                "influence": {
                    "final_subscore": c.influence_score,
                    "weight": self.w_influence,
                    "weighted_subscore": round(self.w_influence * c.influence_score, 4),
                    "steps": influence_steps,
                },
                "reliability": {
                    "final_subscore": c.reliability_score,
                    "weight": self.w_reliability,
                    "weighted_subscore": round(self.w_reliability * c.reliability_score, 4),
                    "independent_sources_present": any(s.is_independent for s in c.sources),
                    "independent_penalty_applied": not any(s.is_independent for s in c.sources),
                    "steps": reliability_steps,
                    "per_source_breakdown": per_source_steps,
                },
                "composite": {
                    "formula": f"({self.w_disparity:.2f} × {c.disparity_score:.2f}) + ({self.w_influence:.2f} × {c.influence_score:.2f}) + ({self.w_reliability:.2f} × {c.reliability_score:.2f})",
                    "weighted_disparity": round(self.w_disparity * c.disparity_score, 4),
                    "weighted_influence": round(self.w_influence * c.influence_score, 4),
                    "weighted_reliability": round(self.w_reliability * c.reliability_score, 4),
                    "composite_rank_score": c.composite_rank_score,
                },
            }

        # Sort descending by composite rank score
        candidates.sort(key=lambda item: item.composite_rank_score, reverse=True)
        return candidates

    def _compute_disparity_score(self, c: CandidateIndividual) -> tuple[float, list[dict[str, Any]]]:
        """Computes disparity contribution subscore and step-by-step additions."""
        score = 0.50
        steps: list[dict[str, Any]] = [
            {"description": "Base Wikidata demographic gap contribution", "delta": 0.50}
        ]

        # Female or non-binary gender boost
        if c.gender_qid == "Q6581072":  # female
            score += 0.20
            steps.append({"description": f"Underrepresented gender category boost ({c.gender_label or 'female'})", "delta": 0.20})
        elif c.gender_qid and c.gender_qid != "Q6581047":  # non-binary/other
            score += 0.25
            steps.append({"description": f"Underrepresented non-binary/trans gender boost ({c.gender_label})", "delta": 0.25})

        # Global South / non-Western country boost
        if c.country_name in ["Kenya", "Nigeria", "Ghana", "Colombia", "India", "Indonesia", "Vietnam", "Brazil"]:
            score += 0.20
            steps.append({"description": f"Global South / underrepresented region boost ({c.country_name})", "delta": 0.20})

        # Non-English primary language boost
        if c.language_name and c.language_name not in ["English", "German", "French"]:
            score += 0.10
            steps.append({"description": f"Underrepresented primary language boost ({c.language_name})", "delta": 0.10})

        final_score = max(0.0, min(1.0, score))
        return final_score, steps

    def _compute_influence_score(self, c: CandidateIndividual) -> tuple[float, list[dict[str, Any]]]:
        """Computes cross-source influence subscore and step-by-step additions."""
        score = 0.30
        steps: list[dict[str, Any]] = [
            {"description": "Base cross-database authority score", "delta": 0.30}
        ]

        # External authority IDs presence
        if c.orcid:
            score += 0.15
            steps.append({"description": f"ORCID persistent researcher identifier ({c.orcid})", "delta": 0.15})
        if c.external_ids:
            delta = min(0.15, len(c.external_ids) * 0.08)
            score += delta
            steps.append({"description": f"External authority links presence ({len(c.external_ids)} authority IDs)", "delta": delta})

        # Reward independent secondary coverage (WP:INDY)
        independent_sources = [s for s in c.sources if s.is_independent]
        if independent_sources:
            score += 0.25
            steps.append({"description": "Independent third-party coverage bonus (WP:INDY)", "delta": 0.25})

        # Total citations across sources
        total_cits = sum(s.citation_count for s in c.sources)
        if total_cits > 0:
            cit_delta = min(0.15, math.log10(1 + total_cits) / 10.0)
            score += cit_delta
            steps.append({"description": f"Citation volume log-scale boost ({total_cits} citations)", "delta": round(cit_delta, 4)})

        final_score = max(0.0, min(1.0, score))
        return final_score, steps

    def _compute_reliability_score(
        self, c: CandidateIndividual
    ) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]]]:
        """Computes average source reliability subscore and step-by-step additions."""
        if not c.sources:
            return 0.30, [{"description": "Default baseline (no sources)", "delta": 0.30}], []

        per_source_steps: list[dict[str, Any]] = []
        source_scores: list[float] = []

        for s in c.sources:
            src_score, src_steps = self.reliability_scorer.score_source_with_breakdown(s)
            source_scores.append(src_score)
            per_source_steps.append({
                "title": s.title,
                "publisher": s.publisher or s.venue,
                "mbfc_factual_reporting": s.mbfc_factual_reporting,
                "is_independent": s.is_independent,
                "source_score": src_score,
                "steps": src_steps,
            })

        avg_score = sum(source_scores) / len(source_scores)
        top_level_steps: list[dict[str, Any]] = [
            {"description": f"Mean reliability across {len(c.sources)} references", "delta": round(avg_score, 4)}
        ]

        # Penalize if candidate has NO independent secondary sources
        if not any(s.is_independent for s in c.sources):
            avg_score *= 0.50
            top_level_steps.append({"description": "50% Penalty for lack of independent secondary sources (WP:INDY)", "delta": -round(avg_score, 4)})

        final_score = round(avg_score, 4)
        return final_score, top_level_steps, per_source_steps

    def get_literature_references(self) -> list[dict[str, str]]:
        return LITERATURE_REFERENCES

    def get_western_bias_disclaimer(self) -> str:
        return WESTERN_BIAS_DISCLAIMER


"""Unit tests for CarbonFootprintEstimator module."""

import pytest
from wikidata_coverage.core.carbon import CarbonFootprintEstimator, ComponentEnergyRecord


def test_carbon_estimator_tracking():
    estimator = CarbonFootprintEstimator()

    # Track CPU component
    rec1 = estimator.track_component("Gender Balance", duration_seconds=2.0, is_llm_inference=False)
    assert rec1.name == "Gender Balance"
    assert rec1.duration_seconds == 2.0
    assert rec1.energy_wh > 0
    assert rec1.carbon_g > 0

    # Track LLM inference component
    rec2 = estimator.track_component("RAG Ollama Generation", duration_seconds=5.0, is_llm_inference=True)
    assert rec2.power_draw_watts > rec1.power_draw_watts

    assert len(estimator.records) == 2
    assert estimator.total_energy_wh() > 0
    assert estimator.total_carbon_g() > 0


def test_real_world_equivalents_and_anonymization():
    estimator = CarbonFootprintEstimator()
    estimator.track_component("SPARQL Queries", duration_seconds=10.0)

    eqs = estimator.get_real_world_equivalents()
    assert "smartphone_charges" in eqs
    assert "led_light_hours" in eqs
    assert "ev_miles" in eqs
    assert "google_searches" in eqs

    profile = estimator.get_anonymized_hardware_profile()
    assert "architecture" in profile
    assert "cpu_threads" in profile
    assert "privacy_notice" in profile

    summary = estimator.summary_dict()
    assert "total_energy_wh" in summary
    assert "total_carbon_g" in summary
    assert len(summary["academic_citations"]) >= 3

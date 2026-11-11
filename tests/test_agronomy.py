import pytest
from agronomy import calculate_lime_requirement, calculate_fertilizer_recommendation, assess_drought_resilience

def test_calculate_lime_requirement_strong_acid():
    res = calculate_lime_requirement(4.5)
    assert res["tons_per_ha"] == 2.5
    assert "Strongly Acidic" in res["status"]

def test_calculate_lime_requirement_optimal():
    res = calculate_lime_requirement(6.5)
    assert res["tons_per_ha"] == 0.0
    assert "Optimal" in res["status"]

def test_calculate_lime_requirement_invalid():
    res = calculate_lime_requirement("N/A")
    assert res["tons_per_ha"] == 0.0

def test_calculate_fertilizer_recommendation_low_n():
    res = calculate_fertilizer_recommendation(15, "Sandy Soil")
    assert res["urea_kg_ha"] == 150
    assert "Compound D" in res["recommendation"]

def test_assess_drought_resilience():
    res = assess_drought_resilience("Sandy Soil", 10, 70)
    assert "Low Water Retention" in res["rating"]

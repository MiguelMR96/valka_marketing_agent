import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from valka_agent.calculator import calculate_feeding_plan


def test_adult_ideal_moderate_daily_amount():
    # 60 lb adult, moderate activity, ideal body condition -> base 2.5%,
    # no activity/body-condition delta.
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 100)
    assert result["daily_pct"] == pytest.approx(0.025)
    assert result["daily_total_lb_household"] == 1.5


def test_activity_and_body_condition_deltas_stack():
    # 60 lb adult, high activity (+1pp), underweight (+0.5pp) -> 4% total.
    result = calculate_feeding_plan(60, 1, "adult", "high", "underweight", 100)
    assert result["daily_pct"] == pytest.approx(0.04)
    assert result["daily_total_lb_household"] == 2.4


def test_low_activity_overweight_reduces_below_base():
    # 60 lb adult, low activity (-0.5pp), overweight (-0.5pp) -> 1.5% total.
    result = calculate_feeding_plan(60, 1, "adult", "low", "overweight", 100)
    assert result["daily_pct"] == pytest.approx(0.015)
    assert result["daily_total_lb_household"] == 0.9


def test_puppy_base_pct_higher_than_adult():
    result = calculate_feeding_plan(20, 1, "puppy", "moderate", "ideal", 100)
    assert result["daily_pct"] == pytest.approx(0.06)


def test_senior_base_pct_lower_than_adult():
    result = calculate_feeding_plan(60, 1, "senior", "moderate", "ideal", 100)
    assert result["daily_pct"] == pytest.approx(0.02)


def test_num_dogs_multiplies_household_total():
    single = calculate_feeding_plan(40, 1, "adult", "moderate", "ideal", 100)
    household = calculate_feeding_plan(40, 3, "adult", "moderate", "ideal", 100)
    assert household["daily_total_lb_household"] == pytest.approx(single["daily_total_lb_household"] * 3)


def test_percent_valka_splits_valka_and_kibble():
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 50)
    assert result["daily_total_lb_household"] == 1.5
    assert result["daily_valka_lb"] == 0.75
    assert result["daily_kibble_lb"] == 0.75


def test_100_percent_valka_zero_kibble():
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 100)
    assert result["daily_kibble_lb"] == 0.0


def test_weekly_and_monthly_totals():
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 100)
    assert result["weekly_valka_lb"] == pytest.approx(result["daily_valka_lb"] * 7)
    assert result["monthly_valka_lb"] == pytest.approx(result["daily_valka_lb"] * 30)


def test_invalid_percent_valka_raises():
    with pytest.raises(ValueError):
        calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 40)


def test_package_combo_covers_monthly_need():
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 100)
    covered = sum(item["size_lb"] * item["qty"] for item in result["package_combo"])
    assert covered >= result["monthly_valka_lb"]


def test_package_combo_uses_default_case_and_chub_sizes():
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 100)
    sizes_used = {item["size_lb"] for item in result["package_combo"]}
    assert sizes_used <= {10, 1}


def test_no_price_per_lb_omits_cost_estimate():
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 100)
    assert result["monthly_cost_estimate"] is None


def test_price_per_lb_computes_cost_estimate():
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 100, price_per_lb=6.0)
    assert result["monthly_cost_estimate"] == pytest.approx(result["monthly_valka_lb"] * 6.0)


def test_pregnant_lactating_raises_instead_of_computing():
    with pytest.raises(ValueError):
        calculate_feeding_plan(60, 1, "pregnant_lactating", "moderate", "ideal", 100)


def test_invalid_weight_raises():
    with pytest.raises(ValueError):
        calculate_feeding_plan(0, 1, "adult", "moderate", "ideal", 100)


def test_invalid_num_dogs_raises():
    with pytest.raises(ValueError):
        calculate_feeding_plan(60, 0, "adult", "moderate", "ideal", 100)


def test_invalid_life_stage_raises():
    with pytest.raises(ValueError):
        calculate_feeding_plan(60, 1, "toddler", "moderate", "ideal", 100)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

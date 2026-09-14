import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from valka_agent.calculator import calculate_feeding_plan, _standard_shipping_cost

# Mirrors Everyday Wag's real pricing table (data/kb/everyday_wag.md).
EVERYDAY_WAG_PACKAGES = [
    {"size_label": "2 lb", "size_lb": 2.0, "regular": 14.44, "intro40": 8.66, "sub10": 13.00},
    {"size_label": "10 lb", "size_lb": 10.0, "regular": 71.39, "intro40": 42.83, "sub10": 64.25},
    {"size_label": "38 lb", "size_lb": 38.0, "regular": 209.09, "intro40": 125.45, "sub10": 188.18},
]


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
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 100, packages=EVERYDAY_WAG_PACKAGES)
    covered = sum(item["size_lb"] * item["qty"] for item in result["package_combo"])
    assert covered >= result["monthly_valka_lb"]


def test_package_combo_uses_real_sizes():
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 100, packages=EVERYDAY_WAG_PACKAGES)
    sizes_used = {item["size_lb"] for item in result["package_combo"]}
    assert sizes_used <= {2.0, 10.0, 38.0}


def test_no_packages_omits_cost_and_shipping_estimate():
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 100)
    assert result["monthly_cost_estimate"] is None
    assert result["shipping_cost_estimate"] is None


def test_package_cost_sums_real_regular_prices_not_a_flat_rate():
    # 60 lb adult, 100% Valka -> daily 1.5 lb, monthly 45 lb. Greedy combo:
    # one 38 lb ($209.09) covers 38, leaving 7 lb -> four 2 lb bags ($14.44
    # each) cover the rest (8 lb, rounds up past 7). Real per-size pricing
    # isn't linear, so this must equal the actual summed package prices,
    # not monthly_lb * some average $/lb rate.
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 100, packages=EVERYDAY_WAG_PACKAGES)
    expected_cost = 209.09 + 4 * 14.44
    assert result["monthly_cost_estimate"] == pytest.approx(expected_cost, abs=0.01)


def test_shipping_tiers():
    assert _standard_shipping_cost(0) == 39.0
    assert _standard_shipping_cost(74.99) == 39.0
    assert _standard_shipping_cost(75) == 19.0
    assert _standard_shipping_cost(179.99) == 19.0
    assert _standard_shipping_cost(180) == 0.0
    assert _standard_shipping_cost(500) == 0.0


def test_shipping_estimate_reflects_the_real_cost_tier():
    result = calculate_feeding_plan(60, 1, "adult", "moderate", "ideal", 100, packages=EVERYDAY_WAG_PACKAGES)
    assert result["shipping_cost_estimate"] == _standard_shipping_cost(result["monthly_cost_estimate"])


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

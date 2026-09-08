import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from valka_agent.calculator import calculate_feeding_transition


def test_60lb_dog_normal_sensitivity_daily_total():
    result = calculate_feeding_transition(60, "kibble", "normal")
    assert result["daily_total_lb"] == 1.5
    assert result["steady_state_daily_lb"] == 1.5


def test_60lb_dog_normal_sensitivity_schedule_length_and_days():
    result = calculate_feeding_transition(60, "kibble", "normal")
    assert result["transition_days"] == 7
    assert len(result["schedule"]) == 7
    assert [row["day"] for row in result["schedule"]] == [1, 2, 3, 4, 5, 6, 7]


def test_60lb_dog_normal_sensitivity_phase_percentages():
    result = calculate_feeding_transition(60, "kibble", "normal")
    pct_by_day = {row["day"]: row["new_food_pct"] for row in result["schedule"]}
    assert pct_by_day == {
        1: 0.25, 2: 0.25,
        3: 0.50, 4: 0.50,
        5: 0.75, 6: 0.75,
        7: 1.00,
    }


def test_60lb_dog_normal_sensitivity_lb_amounts():
    result = calculate_feeding_transition(60, "kibble", "normal")
    by_day = {row["day"]: (row["new_food_lb"], row["old_food_lb"]) for row in result["schedule"]}
    assert by_day[1] == (0.375, 1.125)
    assert by_day[3] == (0.75, 0.75)
    assert by_day[5] == (1.125, 0.375)
    assert by_day[7] == (1.5, 0.0)
    for day, (new_lb, old_lb) in by_day.items():
        assert round(new_lb + old_lb, 3) == 1.5


def test_low_sensitivity_shorter_transition():
    result = calculate_feeding_transition(40, "mixed", "low")
    assert result["transition_days"] == 5
    assert len(result["schedule"]) == 5
    assert result["daily_total_lb"] == 1.0


def test_high_sensitivity_longer_transition():
    result = calculate_feeding_transition(80, "other_raw", "high")
    assert result["transition_days"] == 10
    assert len(result["schedule"]) == 10
    assert result["daily_total_lb"] == 2.0
    assert result["schedule"][-1]["new_food_pct"] == 1.00
    assert result["schedule"][-1]["old_food_pct"] == 0.0


def test_invalid_weight_raises():
    try:
        calculate_feeding_transition(0, "kibble", "normal")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_invalid_sensitivity_raises():
    try:
        calculate_feeding_transition(50, "kibble", "extreme")
        assert False, "expected ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))

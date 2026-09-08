# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Feeding transition calculator. Pure arithmetic, no LLM involvement.

Baseline daily raw feeding amount is 2.5% of body weight. The transition
from old food to new food is staged in quarters (25/50/75/100% new food),
spread over a number of days that depends on the dog's sensitivity:
  low sensitivity    -> 5 day transition
  normal sensitivity -> 7 day transition
  high sensitivity   -> 10 day transition

Example: a 60 lb dog at 2.5% body weight eats 1.5 lb/day total.
"""

DAILY_PERCENTAGE = 0.025

TRANSITION_DAYS_BY_SENSITIVITY = {
    "low": 5,
    "normal": 7,
    "high": 10,
}

PHASES = (0.25, 0.50, 0.75, 1.00)


def _distribute_days(total_days: int, num_phases: int) -> list[int]:
    """Split total_days as evenly as possible across num_phases buckets,
    front-loading any remainder (so 7 days / 4 phases -> [2, 2, 2, 1])."""
    base, remainder = divmod(total_days, num_phases)
    return [base + (1 if i < remainder else 0) for i in range(num_phases)]


def calculate_feeding_transition(
    weight_lbs: float,
    current_food: str,
    sensitivity: str = "normal",
) -> dict:
    if weight_lbs <= 0:
        raise ValueError("weight_lbs must be positive")
    if sensitivity not in TRANSITION_DAYS_BY_SENSITIVITY:
        raise ValueError(f"unknown sensitivity: {sensitivity!r}")

    daily_total_lb = round(weight_lbs * DAILY_PERCENTAGE, 3)
    transition_days = TRANSITION_DAYS_BY_SENSITIVITY[sensitivity]
    days_per_phase = _distribute_days(transition_days, len(PHASES))

    schedule = []
    day = 1
    for new_food_pct, num_days in zip(PHASES, days_per_phase):
        old_food_pct = round(1 - new_food_pct, 2)
        for _ in range(num_days):
            schedule.append({
                "day": day,
                "new_food_pct": new_food_pct,
                "old_food_pct": old_food_pct,
                "new_food_lb": round(daily_total_lb * new_food_pct, 3),
                "old_food_lb": round(daily_total_lb * old_food_pct, 3),
            })
            day += 1

    return {
        "weight_lbs": weight_lbs,
        "current_food": current_food,
        "sensitivity": sensitivity,
        "daily_total_lb": daily_total_lb,
        "daily_percentage": DAILY_PERCENTAGE,
        "transition_days": transition_days,
        "schedule": schedule,
        "steady_state_daily_lb": daily_total_lb,
    }


def format_schedule_message(target_product: str, result: dict) -> str:
    lines = [
        f"Here's the transition plan to {target_product}, based on a "
        f"{result['weight_lbs']:g} lb dog eating {result['daily_total_lb']:g} lb/day "
        f"total ({result['daily_percentage'] * 100:g}% of body weight):",
        "",
    ]
    for row in result["schedule"]:
        lines.append(
            f"Day {row['day']}: {row['new_food_lb']:g} lb {target_product} "
            f"+ {row['old_food_lb']:g} lb current food "
            f"({int(row['new_food_pct'] * 100)}% new)"
        )
    lines.append("")
    lines.append(
        f"From day {result['transition_days'] + 1} onward: "
        f"{result['steady_state_daily_lb']:g} lb/day of {target_product}, 100% new food."
    )
    return "\n".join(lines)

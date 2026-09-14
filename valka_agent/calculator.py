# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Feeding-plan calculator. Pure arithmetic, no LLM involvement.

Rebuilt against the real Valka brief (Brief_Estrategico_Valka_IA-1.pdf):
the model is a SUSTAINED blend ratio -- the customer picks and stays at
25/50/75/100% Valka mixed with kibble ("Modelo flexible de incorporación",
brief p.2) -- not a one-time transition-to-100% schedule (that was this
file's v1 guess before the brief existed; see git history).

PLACEHOLDER DATA: every constant below is a *sourced* placeholder, not an
invented number, but it is still NOT an approved Valka/vet figure. It's a
starting point synthesized from published raw-feeding guidance (see the
comments on each constant for sources), pending verification against real
veterinary sources and final sign-off. Swap these before production use.
Per the brief (p.8): "Usar fórmulas y reglas validadas. No inventar
porciones... sin reglas previamente aprobadas."

Pricing/packaging are NOT invented here at all -- they're read from the
matching product's KB doc (see kb.py's KBDoc.price_per_lb) by the caller
and passed in; if no price is available, cost is omitted rather than
guessed (see calculate_feeding_plan's price_per_lb=None handling).
"""

# Base daily % of body weight by life stage. Adult 2.5% and senior ~1.5-2%
# match the baseline used by multiple independent raw-feeding calculators;
# puppies are commonly cited at 5-10% of body weight (using 6% as a single
# representative value here -- a real implementation should eventually take
# puppy age/weeks rather than one flat number).
# Sources: https://petparlour.ie/how-much-raw-food-should-i-feed-my-dog/
#          https://rawpawiq.com/raw-dog-food-calculator
#          https://www.mypetcarnivore.com/pages/raw-feeding-chart
BASE_DAILY_PCT_BY_LIFE_STAGE = {
    "puppy": 0.06,
    "adult": 0.025,
    "senior": 0.02,
}

# pregnant_lactating is deliberately NOT in the table above -- see the
# ValueError guard in calculate_feeding_plan. The brief is explicit that
# this life stage needs pre-approved rules we don't have (p.5, p.8: "No
# diagnosticar ni sustituir al veterinario").

# Percentage-point deltas (not multipliers) applied on top of the life-stage
# base, matching how these sources actually express activity adjustment
# ("sedentary ~2%, moderate ~2.5%, active 3-4%").
ACTIVITY_PCT_DELTA = {
    "low": -0.005,
    "moderate": 0.0,
    "high": 0.01,
}

# Flat percentage-point deltas per RawPawIQ's stated methodology
# ("underweight +0.5%, overweight -0.5% from the activity-adjusted
# target"). Source: https://rawpawiq.com/raw-dog-food-calculator
BODY_CONDITION_PCT_DELTA = {
    "underweight": 0.005,
    "ideal": 0.0,
    "overweight": -0.005,
}

MIN_DAILY_PCT = 0.01  # floor so no combination of deltas goes to ~0/negative

VALID_PERCENT_VALKA = (25, 50, 75, 100)

# Mirrors the packaging convention already stated in every data/kb/*.md doc
# ("sold frozen in 1 lb chubs, 10 lb cases") -- default combo sizes, largest
# first, used by the greedy packer below.
DEFAULT_PACKAGE_SIZES_LB = (10, 1)

DAYS_PER_WEEK = 7
DAYS_PER_MONTH = 30  # approximation, not a calendar month

# Placeholder default: no package-size-based delivery cadence logic exists
# yet (that would itself be an invented rule) -- fixed monthly cadence until
# real ops/subscription data (brief p.7: "frecuencia de entrega") lands.
DEFAULT_DELIVERY_FREQUENCY_WEEKS = 4


def _daily_pct(life_stage: str, activity_level: str, body_condition: str) -> float:
    if life_stage == "pregnant_lactating":
        raise ValueError(
            "pregnant_lactating requires vet-approved feeding rules, not "
            "yet available -- route to a human instead of calculating"
        )
    if life_stage not in BASE_DAILY_PCT_BY_LIFE_STAGE:
        raise ValueError(f"unknown life_stage: {life_stage!r}")
    if activity_level not in ACTIVITY_PCT_DELTA:
        raise ValueError(f"unknown activity_level: {activity_level!r}")
    if body_condition not in BODY_CONDITION_PCT_DELTA:
        raise ValueError(f"unknown body_condition: {body_condition!r}")

    pct = (
        BASE_DAILY_PCT_BY_LIFE_STAGE[life_stage]
        + ACTIVITY_PCT_DELTA[activity_level]
        + BODY_CONDITION_PCT_DELTA[body_condition]
    )
    return max(pct, MIN_DAILY_PCT)


def _pack_combo(total_lb: float, package_sizes_lb: tuple) -> list[dict]:
    """Greedy pack: cover total_lb using the largest package sizes first,
    rounding up (never under-deliver). Deterministic, not cost-optimal for
    every edge case, but matches a simple real-world "biggest box first"
    fulfillment pattern well enough for a placeholder."""
    sizes = sorted(package_sizes_lb, reverse=True)
    remaining = total_lb
    combo = []
    for size in sizes:
        if remaining <= 0:
            break
        qty = int(remaining // size)
        if qty > 0:
            combo.append({"size_lb": size, "qty": qty})
            remaining = round(remaining - qty * size, 3)
    if remaining > 0:
        smallest = sizes[-1]
        if combo and combo[-1]["size_lb"] == smallest:
            combo[-1]["qty"] += 1
        else:
            combo.append({"size_lb": smallest, "qty": 1})
    return combo


def calculate_feeding_plan(
    weight_lbs: float,
    num_dogs: int,
    life_stage: str,
    activity_level: str,
    body_condition: str,
    percent_valka: int,
    price_per_lb: float | None = None,
    package_sizes_lb: tuple = DEFAULT_PACKAGE_SIZES_LB,
) -> dict:
    if weight_lbs <= 0:
        raise ValueError("weight_lbs must be positive")
    if num_dogs <= 0:
        raise ValueError("num_dogs must be positive")
    if percent_valka not in VALID_PERCENT_VALKA:
        raise ValueError(f"percent_valka must be one of {VALID_PERCENT_VALKA}")

    daily_pct = _daily_pct(life_stage, activity_level, body_condition)

    daily_total_lb_per_dog = round(weight_lbs * daily_pct, 3)
    daily_total_lb_household = round(daily_total_lb_per_dog * num_dogs, 3)

    valka_fraction = percent_valka / 100
    daily_valka_lb = round(daily_total_lb_household * valka_fraction, 3)
    daily_kibble_lb = round(daily_total_lb_household - daily_valka_lb, 3)

    weekly_valka_lb = round(daily_valka_lb * DAYS_PER_WEEK, 3)
    monthly_valka_lb = round(daily_valka_lb * DAYS_PER_MONTH, 3)

    package_combo = _pack_combo(monthly_valka_lb, package_sizes_lb)

    monthly_cost_estimate = (
        round(monthly_valka_lb * price_per_lb, 2) if price_per_lb is not None else None
    )

    return {
        "weight_lbs": weight_lbs,
        "num_dogs": num_dogs,
        "life_stage": life_stage,
        "activity_level": activity_level,
        "body_condition": body_condition,
        "percent_valka": percent_valka,
        "daily_pct": daily_pct,
        "daily_total_lb_household": daily_total_lb_household,
        "daily_valka_lb": daily_valka_lb,
        "daily_kibble_lb": daily_kibble_lb,
        "weekly_valka_lb": weekly_valka_lb,
        "monthly_valka_lb": monthly_valka_lb,
        "package_combo": package_combo,
        "price_per_lb": price_per_lb,
        "monthly_cost_estimate": monthly_cost_estimate,
        "delivery_frequency_weeks": DEFAULT_DELIVERY_FREQUENCY_WEEKS,
    }


def _format_combo(combo: list[dict]) -> str:
    return ", ".join(f"{item['qty']} x {item['size_lb']:g} lb" for item in combo)


_LIFE_STAGE_ES = {"puppy": "cachorro", "adult": "adulto", "senior": "mayor"}
_ACTIVITY_LEVEL_ES = {"low": "poca", "moderate": "moderada", "high": "mucha"}
_BODY_CONDITION_ES = {"underweight": "bajo peso", "ideal": "ideal", "overweight": "sobrepeso"}


def format_feeding_plan_message(target_product: str, result: dict, language: str = "en") -> str:
    combo = _format_combo(result["package_combo"])

    if language == "es":
        life_stage_es = _LIFE_STAGE_ES.get(result["life_stage"], result["life_stage"])
        activity_es = _ACTIVITY_LEVEL_ES.get(result["activity_level"], result["activity_level"])
        body_condition_es = _BODY_CONDITION_ES.get(result["body_condition"], result["body_condition"])
        lines = [
            f"Plan de alimentación con {target_product} al {result['percent_valka']}% "
            f"para {result['num_dogs']} perro(s) de {result['weight_lbs']:g} lb "
            f"({life_stage_es}, actividad {activity_es}, "
            f"condición corporal {body_condition_es}):",
            "",
            f"- Total diario del hogar: {result['daily_total_lb_household']:g} lb",
            f"- {target_product} (Valka): {result['daily_valka_lb']:g} lb/día "
            f"({result['weekly_valka_lb']:g} lb/semana, {result['monthly_valka_lb']:g} lb/mes)",
            f"- Kibble habitual: {result['daily_kibble_lb']:g} lb/día",
            f"- Combinación de envases sugerida: {combo}",
        ]
        if result["monthly_cost_estimate"] is not None:
            lines.append(f"- Costo mensual estimado: ${result['monthly_cost_estimate']:.2f}")
        else:
            lines.append("- Costo mensual estimado: no disponible por ahora para este producto.")
        lines.append(
            f"- Frecuencia de entrega sugerida: cada {result['delivery_frequency_weeks']} semanas"
        )
        lines.append(
            ""
        )
        lines.append(
            "Recuerda: puedes ajustar el porcentaje Valka (25/50/75/100%) cuando quieras, a tu manera."
        )
        return "\n".join(lines)

    lines = [
        f"Feeding plan for {target_product} at {result['percent_valka']}% Valka, "
        f"for {result['num_dogs']} dog(s) at {result['weight_lbs']:g} lb "
        f"({result['life_stage']}, {result['activity_level']} activity, "
        f"{result['body_condition']} body condition):",
        "",
        f"- Household daily total: {result['daily_total_lb_household']:g} lb",
        f"- {target_product} (Valka): {result['daily_valka_lb']:g} lb/day "
        f"({result['weekly_valka_lb']:g} lb/week, {result['monthly_valka_lb']:g} lb/month)",
        f"- Regular kibble: {result['daily_kibble_lb']:g} lb/day",
        f"- Suggested package combo: {combo}",
    ]
    if result["monthly_cost_estimate"] is not None:
        lines.append(f"- Estimated monthly cost: ${result['monthly_cost_estimate']:.2f}")
    else:
        lines.append("- Estimated monthly cost: not available for this product yet.")
    lines.append(f"- Suggested delivery frequency: every {result['delivery_frequency_weeks']} weeks")
    lines.append("")
    lines.append("You can adjust your Valka percentage (25/50/75/100%) anytime -- start your way.")
    return "\n".join(lines)

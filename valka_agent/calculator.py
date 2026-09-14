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

Pricing/packaging/shipping are NOT invented here at all -- pricing is
read from the matching product's real (working-reference) pricing table
in its KB doc (see kb.py's KBDoc.packages) by the caller and passed in;
if a product has no price data (e.g. no match, or a topper that isn't
meant to be the main blend food), cost and shipping are omitted rather
than guessed. Shipping tiers are Valka's real approved thresholds
(Valka_Brand_Pricing_Shipping_Approval_Guide.pdf).
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

DAYS_PER_WEEK = 7
DAYS_PER_MONTH = 30  # approximation, not a calendar month

# No real subscription-cadence rule was given (subscriptions are
# customer-controlled: skip/pause/adjust anytime) -- keep a reasonable
# default rather than inventing a formula from package sizes.
DEFAULT_DELIVERY_FREQUENCY_WEEKS = 4

# Real approved shipping tiers (Valka_Brand_Pricing_Shipping_Approval_Guide.pdf),
# applied to the order subtotal after discounts. Standard shipping only --
# 2nd Day Air ($75) / Next Day Air ($125) exist but aren't estimated here,
# this is an informational estimate, not a live checkout quote.
def _standard_shipping_cost(subtotal: float) -> float:
    if subtotal < 75:
        return 39.0
    if subtotal < 180:
        return 19.0
    return 0.0


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


def _pack_combo(total_lb: float, packages: list[dict]) -> tuple[list[dict], float | None]:
    """Greedy pack: cover total_lb using the largest package sizes first,
    rounding up (never under-deliver). Deterministic, not cost-optimal for
    every edge case, but matches a simple real-world "biggest box first"
    fulfillment pattern.

    Returns (combo, total_cost). Cost sums each chosen package's real
    *regular* price directly -- real per-size pricing isn't linear (a 10 lb
    bag isn't simply 5x a 2 lb bag), so this is more accurate than the old
    placeholder approach of multiplying total lb by one average $/lb rate.
    total_cost is None if `packages` is empty (no pricing data for this
    product -- e.g. unmatched product, or a topper not meant to be the
    main blend food)."""
    if not packages:
        return [], None

    sizes = sorted(packages, key=lambda p: p["size_lb"], reverse=True)
    remaining = total_lb
    combo: list[dict] = []
    cost = 0.0
    for pkg in sizes:
        if remaining <= 0:
            break
        qty = int(remaining // pkg["size_lb"]) if pkg["size_lb"] > 0 else 0
        if qty > 0:
            combo.append({"size_label": pkg["size_label"], "size_lb": pkg["size_lb"], "qty": qty})
            cost += qty * pkg["regular"]
            remaining = round(remaining - qty * pkg["size_lb"], 4)
    if remaining > 0:
        smallest = sizes[-1]
        if combo and combo[-1]["size_lb"] == smallest["size_lb"]:
            combo[-1]["qty"] += 1
        else:
            combo.append({"size_label": smallest["size_label"], "size_lb": smallest["size_lb"], "qty": 1})
        cost += smallest["regular"]
    return combo, round(cost, 2)


def calculate_feeding_plan(
    weight_lbs: float,
    num_dogs: int,
    life_stage: str,
    activity_level: str,
    body_condition: str,
    percent_valka: int,
    packages: list[dict] | None = None,
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

    package_combo, monthly_cost_estimate = _pack_combo(monthly_valka_lb, packages or [])
    shipping_cost_estimate = (
        _standard_shipping_cost(monthly_cost_estimate) if monthly_cost_estimate is not None else None
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
        "monthly_cost_estimate": monthly_cost_estimate,
        "shipping_cost_estimate": shipping_cost_estimate,
        "delivery_frequency_weeks": DEFAULT_DELIVERY_FREQUENCY_WEEKS,
    }


def _format_combo(combo: list[dict]) -> str:
    return ", ".join(f"{item['qty']} x {item['size_label']}" for item in combo)


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
            lines.append(f"- Costo mensual estimado (precio regular): ${result['monthly_cost_estimate']:.2f}")
            lines.append(f"- Envío estándar estimado: {_format_shipping_es(result['shipping_cost_estimate'])}")
        else:
            lines.append("- Costo mensual estimado: no disponible por ahora para este producto.")
        lines.append(
            f"- Frecuencia de entrega sugerida: cada {result['delivery_frequency_weeks']} semanas"
        )
        lines.append("")
        lines.append(
            "Recuerda: puedes ajustar el porcentaje Valka (25/50/75/100%) cuando quieras, a tu manera. "
            "¿Cliente nuevo? Tu primer pedido tiene 40% de descuento. ¿Ya probaste Valka? Suscríbete y "
            "ahorra 10% en tus entregas recurrentes."
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
        lines.append(f"- Estimated monthly cost (regular price): ${result['monthly_cost_estimate']:.2f}")
        lines.append(f"- Estimated standard shipping: {_format_shipping_en(result['shipping_cost_estimate'])}")
    else:
        lines.append("- Estimated monthly cost: not available for this product yet.")
    lines.append(f"- Suggested delivery frequency: every {result['delivery_frequency_weeks']} weeks")
    lines.append("")
    lines.append(
        "You can adjust your Valka percentage (25/50/75/100%) anytime -- start your way. New "
        "customer? Get 40% off your first order. Already tried Valka? Subscribe & save 10% on "
        "recurring deliveries."
    )
    return "\n".join(lines)


def _format_shipping_en(shipping_cost: float) -> str:
    return "Free (order qualifies for free standard shipping)" if shipping_cost == 0 else f"${shipping_cost:.2f}"


def _format_shipping_es(shipping_cost: float) -> str:
    return "Gratis (el pedido califica para envío estándar gratuito)" if shipping_cost == 0 else f"${shipping_cost:.2f}"

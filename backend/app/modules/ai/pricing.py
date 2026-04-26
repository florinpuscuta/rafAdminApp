"""
Pricing approximativ pentru modelele AI folosite (USD per 1M tokens).

Valorile sunt orientative la momentul scrierii (Aprilie 2026). Update după
modificări de prețuri din partea provider-ilor. Pentru modele lipsă, costul
e raportat ca NULL (doar tokens sunt logate).
"""
from __future__ import annotations

from decimal import Decimal


# (input_per_million_usd, output_per_million_usd)
MODEL_PRICES: dict[str, tuple[Decimal, Decimal]] = {
    # Anthropic
    "claude-opus-4-7": (Decimal("15"), Decimal("75")),
    "claude-sonnet-4-6": (Decimal("3"), Decimal("15")),
    "claude-sonnet-4-5": (Decimal("3"), Decimal("15")),
    "claude-haiku-4-5": (Decimal("1"), Decimal("5")),
    # OpenAI
    "gpt-4o": (Decimal("5"), Decimal("15")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    # xAI
    "grok-2-latest": (Decimal("2"), Decimal("10")),
    # DeepSeek
    "deepseek-chat": (Decimal("0.27"), Decimal("1.10")),
}


def calc_cost_usd(
    model: str, input_tokens: int, output_tokens: int
) -> Decimal | None:
    """Calculează costul USD pentru un call AI. None dacă modelul nu e în tabel."""
    prices = MODEL_PRICES.get(model)
    if prices is None:
        return None
    input_price, output_price = prices
    cost = (
        Decimal(input_tokens) * input_price / Decimal(1_000_000)
        + Decimal(output_tokens) * output_price / Decimal(1_000_000)
    )
    # 6 decimale precision (microcents).
    return cost.quantize(Decimal("0.000001"))

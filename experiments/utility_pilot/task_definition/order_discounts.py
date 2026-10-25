"""Módulo de cálculo de descuentos regionales y promociones.

Este módulo contiene un bug reproducible:
- El cálculo de descuento regional para 'LATAM' no implementa las especificaciones
  vigentes de producto (versión 2.4):
  1. No aplica el descuento porcentual correcto antes de impuestos.
  2. No respeta el tope máximo de descuento (cap de 25.00 USD para pedidos > 100 USD).
  3. Genera tipos incompatibles (mezcla float con Decimal en lugar de usar Decimal con ROUND_HALF_UP).
"""
from decimal import Decimal, ROUND_HALF_UP


def calculate_order_total(subtotal: Decimal, tax_rate: Decimal, discount_amount: Decimal) -> Decimal:
    """Calcula el total final aplicando impuestos sobre la base neta post-descuento."""
    net_base = subtotal - discount_amount
    if net_base < Decimal("0.00"):
        net_base = Decimal("0.00")
    tax = (net_base * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return net_base + tax


def apply_regional_discount(order: dict, coupon_code: str) -> dict:
    """Aplica descuento regional según el cupón y la región de la orden.
    
    BUG REPRODUCIBLE ACTUAL:
    - Aplica un 5% fijo flotante sin contemplar la región ni el tope.
    - Falla con TypeError al interactuar con subtotal Decimal o produce totales incorrectos.
    """
    subtotal = order.get("subtotal", Decimal("0.00"))
    region = order.get("region", "GLOBAL")

    # Implementación errónea actual:
    # 1. No consulta ni valida las reglas regionales de la especificación 2.4.
    # 2. Mezcla float con Decimal.
    # 3. Omite el tope de descuento.
    if coupon_code == "PROMO_REGIONAL":
        # BUG: float 0.05 y sin tope
        discount = float(subtotal) * 0.05
        order["discount_amount"] = Decimal(str(round(discount, 2)))
    else:
        order["discount_amount"] = Decimal("0.00")

    order["final_total"] = calculate_order_total(
        subtotal=subtotal,
        tax_rate=order.get("tax_rate", Decimal("0.16")),
        discount_amount=order["discount_amount"]
    )
    return order

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
    subtotal = order.get('subtotal', Decimal('0.00'))
    region = order.get('region', 'GLOBAL')
    if coupon_code == 'PROMO_REGIONAL' and region == 'LATAM':
        discount = (subtotal * Decimal('0.15')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if subtotal > Decimal('100.00') and discount > Decimal('25.00'):
            discount = Decimal('25.00')
        order['discount_amount'] = discount
    else:
        order['discount_amount'] = Decimal('0.00')
    order['final_total'] = calculate_order_total(subtotal, order.get('tax_rate', Decimal('0.16')), order['discount_amount'])
    return order

"""Pruebas unitarias independientes para verificar la corrección de order_discounts.py."""
from decimal import Decimal
import pytest
from .order_discounts import apply_regional_discount


def test_latam_regular_discount():
    """Para LATAM con subtotal <= 100 USD, debe aplicar 15% exacto en Decimal."""
    order = {
        "order_id": "ord-101",
        "region": "LATAM",
        "subtotal": Decimal("80.00"),
        "tax_rate": Decimal("0.16"),
    }
    res = apply_regional_discount(order, "PROMO_REGIONAL")
    # 15% de 80.00 = 12.00
    assert res["discount_amount"] == Decimal("12.00")
    # Base neta: 68.00; Impuesto (16%): 10.88; Total: 78.88
    assert res["final_total"] == Decimal("78.88")


def test_latam_discount_cap_enforced():
    """Para LATAM con subtotal > 100 USD, debe aplicar el tope máximo de 25.00 USD."""
    order = {
        "order_id": "ord-102",
        "region": "LATAM",
        "subtotal": Decimal("200.00"),
        "tax_rate": Decimal("0.10"),
    }
    res = apply_regional_discount(order, "PROMO_REGIONAL")
    # 15% de 200 = 30.00, pero el tope especificado en v2.4 es 25.00
    assert res["discount_amount"] == Decimal("25.00")
    # Base neta: 175.00; Impuesto (10%): 17.50; Total: 192.50
    assert res["final_total"] == Decimal("192.50")


def test_other_region_no_promo_applied():
    """Si la región no es LATAM, el cupón PROMO_REGIONAL no debe aplicar o aplica 0.00."""
    order = {
        "order_id": "ord-103",
        "region": "EMEA",
        "subtotal": Decimal("100.00"),
        "tax_rate": Decimal("0.20"),
    }
    res = apply_regional_discount(order, "PROMO_REGIONAL")
    assert res["discount_amount"] == Decimal("0.00")
    assert res["final_total"] == Decimal("120.00")

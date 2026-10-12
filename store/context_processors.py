"""Compteur panier global (exigé par settings.py TEMPLATES)."""

from .cart import get_cart


def cart_count(request):
    try:
        return {"cart_count": get_cart(request).count}
    except Exception:
        return {"cart_count": 0}

"""
Formato monetario para pesos colombianos (COP) en plantillas.
Separador de miles: punto. Decimales: coma. Ej.: $ 1.234.567,89 COP
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()


def _format_cop(value, *, suffix: bool) -> str:
    if value is None or value == "":
        return "—"
    try:
        d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return "—"
    negative = d < 0
    d = abs(d)
    whole, frac = f"{d:.2f}".split(".")
    if len(whole) > 3:
        rev = whole[::-1]
        parts = [rev[i : i + 3] for i in range(0, len(rev), 3)]
        whole_fmt = ".".join(p[::-1] for p in reversed(parts))
    else:
        whole_fmt = whole
    text = f"$ {whole_fmt},{frac}"
    if negative:
        text = f"- {text}"
    if suffix:
        text = f"{text} COP"
    return text


@register.filter(name="cop")
def cop(value, arg=None) -> str:
    """
    Formatea un número como peso colombiano.
    Uso: {{ monto|cop }}  →  $ 10.000,00 COP
    Para ocultar el sufijo: {{ monto|cop:"0" }}
    """
    if arg is None:
        suffix = True
    else:
        suffix = str(arg).strip().lower() not in ("0", "false", "no")
    return _format_cop(value, suffix=suffix)


@register.filter(name="cop_short")
def cop_short(value) -> str:
    """Igual que cop pero sin el sufijo 'COP' (útil en tablas muy estrechas)."""
    return _format_cop(value, suffix=False)


@register.filter(name="cop_enteros")
def cop_enteros(value) -> str:
    """
    COP en pesos enteros, sin decimales. Separador de miles: punto.
    Ej.: {{ 50000|cop_enteros }} → $ 50.000
    """
    if value is None or value == "":
        return "—"
    try:
        n = int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        return "—"
    if n < 0:
        return "—"
    s = f"{n:,}".replace(",", ".")
    return f"$ {s}"

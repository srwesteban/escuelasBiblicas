"""
Normalización de montos escritos con formato colombiano (miles con punto, decimales con coma).
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _cop_miles_puntos(entero_abs: str) -> str:
    """entero_abs: dígitos sin signo, ej. '1234567' -> '1.234.567'."""
    if len(entero_abs) <= 3:
        return entero_abs
    rev = entero_abs[::-1]
    parts = [rev[i : i + 3] for i in range(0, len(rev), 3)]
    return ".".join(p[::-1] for p in reversed(parts))


def format_cop_puntos(value) -> str:
    """
    COP solo para texto (mensajes): miles con punto; sin decimales si es entero (2.000, no 2.000,00).
    Con decimales: coma y sin ceros de relleno al final (ej. 2.000,5).
    """
    if value is None:
        return "—"
    try:
        d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return "—"
    neg = d < 0
    d = abs(d)
    whole = int(d.to_integral_value())
    frac = d - Decimal(whole)
    whole_fmt = _cop_miles_puntos(str(whole))
    if frac == 0:
        body = whole_fmt
    else:
        # Siempre 2 cifras decimales (evita confundir ,1 con ,10 centavos).
        dec = f"{frac:.2f}".split(".")[1]
        body = f"{whole_fmt},{dec}"
    return f"-{body}" if neg else body


def normalize_cop_money_input(value):
    """
    Devuelve string apto para Decimal de Django: sin separador de miles, punto como decimal.
    Ej.: "2.000" -> "2000", "25.000,50" -> "25000.50", "12.5" -> "12.5"
    """
    if value is None:
        return None
    s = str(value).strip().replace(" ", "")
    if not s:
        return ""
    if "," in s:
        return s.replace(".", "").replace(",", ".")
    parts = s.split(".")
    if len(parts) == 1:
        return parts[0]
    if not all(p.isdigit() for p in parts):
        return s
    if len(parts[-1]) == 3:
        return "".join(parts)
    if len(parts) == 2 and len(parts[-1]) <= 2:
        return f"{parts[0]}.{parts[-1]}"
    return "".join(parts)

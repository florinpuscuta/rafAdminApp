"""Aritmetica pe luni calendaristice.

Modulele care lucreaza cu (year, month) ca pereche compusa folosesc helper-ii
de aici in loc sa-si scrie propriul calcul, ca sa avem o singura sursa de
adevar pentru rollover-ul anului.
"""
from __future__ import annotations


def shift_months(year: int, month: int, delta_months: int) -> tuple[int, int]:
    """Aduna `delta_months` (poate fi negativ) la (year, month).

    Returneaza noua pereche (year, month). `month` e 1..12.
    """
    total = year * 12 + (month - 1) + delta_months
    return total // 12, (total % 12) + 1


def period_pairs(
    from_year: int, from_month: int, to_year: int, to_month: int,
) -> list[tuple[int, int]]:
    """Lista (year, month) inclusiv intre `from` si `to`.

    Daca from > to, returneaza listă goala.
    """
    out: list[tuple[int, int]] = []
    y, m = from_year, from_month
    end = (to_year, to_month)
    if (y, m) > end:
        return out
    while (y, m) <= end:
        out.append((y, m))
        y, m = shift_months(y, m, 1)
    return out


def window_pairs(latest: tuple[int, int], n: int) -> list[tuple[int, int]]:
    """N perechi (year, month) terminate la `latest`, inclusiv. Sortate asc."""
    y, m = latest
    return [shift_months(y, m, -i) for i in range(n - 1, -1, -1)]

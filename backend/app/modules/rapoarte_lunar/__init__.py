"""Raport Lunar Management — consolidat KA pentru o lună aleasă.

Returnează JSON cu totaluri pentru luna (year, month) + top clients + top
agents + defalcare pe lanțuri. E un "executive summary" pentru management,
în format machine-readable. Exportul docx rămâne nice-to-have — frontend-ul
poate reutiliza `/api/rapoarte/word?year=...&month=...`.
"""

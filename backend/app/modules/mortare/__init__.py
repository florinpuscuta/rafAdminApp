"""Mortare Silozuri (Vrac) — breakdown lunar pentru mortarele livrate în vrac.

Filtrul canonic: `ProductCategory.code = 'VARSACI'` (Vărsaci/Vrac). Înlocuiește
magic-string-urile LIKE '%MTI%VRAC%' / '%MZC%VRAC%' / '%MTIG%VRAC%' /
'%MTE%VRAC%' din app-ul legacy (care match-uiau pe `dim_product.description`).

Path: raw_sales → products.category_id → product_categories WHERE code='VARSACI'.
Canalul NU e restricționat — mortarele vrac merg pe RETAIL (magazine mari)
dar și pe KA dacă există (legacy filtra doar RETAIL; aici includem ambele).

Scope: doar ADP; endpoint-ul acceptă `scope=adp` pentru paritate.
"""

"""Grupe Produse — breakdown vânzări KA per produs într-o categorie.

Structură 1:1 cu `analiza_pe_luni`:
  - 3 scope-uri (adp|sika|sikadp) prin `?scope=`
  - batch.source scoping per scope (dedup SIKA mtd > historical)
  - filtrare pe `?group=<category_code>` (ex. EPS, MU, UMEDE, VARSACI)

Query canonical: raw_sales → products → product_categories WHERE code=<group>.
Rândurile unde `product_id` e NULL (unmapped) NU intră — sunt vizibile în
UI-ul de mapping, nu aici.
"""

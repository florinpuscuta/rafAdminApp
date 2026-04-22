"""Top Produse — top-N produse dintr-o categorie KA, sortate după vânzările
anului curent.

Reutilizează aceeași agregare de bază ca `grupe_produse` dar:
  - oferă un parametru `limit` (default 20, min 1, max 100)
  - include breakdown lunar pentru top 5 produse (pentru trend chart)

Structură 1:1 cu `analiza_pe_luni` / `grupe_produse`:
  - 3 scope-uri (adp|sika|sikadp)
  - batch.source scoping per scope
  - dedup SIKA mtd > historical
"""

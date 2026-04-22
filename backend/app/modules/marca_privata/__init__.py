"""Marca Privată — vânzări private label KA, breakdown lunar + clienți.

Filtrul canonic: `Brand.is_private_label = TRUE` (înlocuiește magic-string-ul
"M_PRIVATA" din app-ul legacy). Path: raw_sales → products → brands.

Canal: doar KA (magazinele de retail mari — Dedeman, Hornbach etc. vând
produsele lor marca proprie sub etichetă privată).

Scope: doar ADP (rescriem branduri proprii Adeplast); endpoint-ul acceptă
`scope=adp` pentru paritate cu celelalte module.

Rezolvare (agent_id, store_id) canonic via SAM — identic cu analiza_pe_luni.
"""

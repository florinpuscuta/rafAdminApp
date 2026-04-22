"""Targhet — monthly sales targets vs realized, per agent.

Structură 1:1 cu `analiza_pe_luni` / `vz_la_zi`:
  - 3 scope-uri (adp|sika|sikadp) prin `?scope=`
  - batch.source scoping per scope
  - dedup SIKA per (year, month) cu prioritate MTD > historical
  - rezolvare agent/store via `app.modules.mappings.resolution`

Model legacy: targhet = vânzări an anterior × (1 + target_pct%). În SaaS
nu există încă tabel `targets` — folosim aceeași formulă derivată din
raw_sales + un target_pct global default (configurabil în query param
`target_pct`, cu fallback la 10%).

TODO(targets-table): adăugare tabel persistent `targets(agent_id, year,
month, qty_target, value_target, scope)` pentru target-uri manuale
(ex. EPS — qty-based). Necesită tabel dedicat + migrare + UI de editare.
Legacy avea un singur `target_pct` global stocat într-un rând din
`target_config`; pentru SaaS pregătim contractul să primească target
per agent/lună când schema va fi gata (câmpul `target` din răspuns
rămâne autoritativ, doar calculul intern se schimbă).
"""

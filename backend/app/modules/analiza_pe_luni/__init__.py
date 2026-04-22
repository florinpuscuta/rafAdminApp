"""Analiza pe luni — breakdown lunar vânzări KA, y vs y-1, per agent.

Structură 1:1 cu `vz_la_zi`:
  - 3 scope-uri (adp|sika|sikadp) prin `?scope=`
  - batch.source scoping per scope
  - dedup SIKA per (year, month) cu prioritate MTD > historical
  - rezolvare agent/store via `app.modules.mappings.resolution`
"""

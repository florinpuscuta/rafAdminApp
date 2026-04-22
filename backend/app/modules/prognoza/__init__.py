"""Prognoza — forecast vânzări KA pe orizont configurabil (1..12 luni).

Structură 1:1 cu `analiza_pe_luni`:
  - 3 scope-uri (adp|sika|sikadp) prin `?scope=`
  - batch.source scoping per scope (dedup SIKA MTD > historical)
  - rezolvare agent/store via `app.modules.mappings.resolution`

Algoritm (simplificat faţă de legacy):
  1. Istoric ultimele 12 luni (complete) cu agregare pe (year, month) și pe
     (agent, year, month).
  2. Forecast — medie mobilă (ultimele 3 luni) × factor sezonal (same-month
     din anul precedent) când există ≥ 12 luni istoric; altfel doar media mobilă.
  3. Linear regression pe ultimele 12 luni calculată ca fallback/back-up —
     nu e folosită direct în output, dar e expusă în câmpul `trend_pct` pentru
     transparență în UI.

Output: istoric side-by-side cu forecast pentru chart (linie solidă + dotted)
+ tabel per-agent.
"""

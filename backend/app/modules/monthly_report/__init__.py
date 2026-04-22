"""Monthly Report — structured data + AI narrator → docx.

POC: o singură secțiune (Vânzări pe zone). Pattern:
  1. service.py — query deterministic, agregare cu comparație YoY
  2. chart.py — generare PNG dintr-un dataset
  3. narrator.py — LLM comentariu pe baza numerelor deja calculate
  4. builder.py — asamblare docx (title, table, chart, narrative)
  5. router.py — endpoint `GET /api/monthly-report/zone-preview`
"""

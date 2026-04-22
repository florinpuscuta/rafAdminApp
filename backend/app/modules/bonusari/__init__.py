"""Bonusări — calcul bonus lunar per agent bazat pe creștere vs an anterior.

Reguli legacy (păstrate identic):
  - creștere lunară vs an precedent:
      +1%  → 2.000 lei
      +5%  → 2.500 lei
      +10% → 3.500 lei
      +15% → 5.500 lei
  - bonus recuperare: dacă luna M-1 a ratat (<+1%) dar cumulat până în luna M
    ≥ +1%, primești +1.000 lei în luna M.

Structură 1:1 cu `targhet` — 3 scope-uri (adp|sika|sikadp), batch.source
scoping, rezolvare agent via SAM.
"""

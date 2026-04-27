"""Per-request context variables for AI module.

`current_viewer_mode` e setat de router-ul `/chat` la începutul fiecărei
cereri și citit de `tools.validate_sql` + `service._compose_system_prompt`.
ContextVar funcționează corect cu asyncio (token reset garantează cleanup).
"""
from contextvars import ContextVar

# True dacă user-ul curent are role_v2 = VIEWER. Forțează regulile de
# confidențialitate pe agenți: nume mascate, query SQL pe `agents` și
# tabelele asociate respinse, refuz politicos pe întrebări individuale.
current_viewer_mode: ContextVar[bool] = ContextVar(
    "ai_viewer_mode", default=False,
)

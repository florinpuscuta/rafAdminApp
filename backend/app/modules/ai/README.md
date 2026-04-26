# ai

Asistent AI conversațional cu acces read-only la baza de date. Suportă 4
provideri (Anthropic native + OpenAI / xAI / DeepSeek prin format function
calling), toți cu tool-use loop. Răspunde în română, cu strategie clară:
preferă `get_app_view` (cheamă view-uri reale ale aplicației pentru numere
identice cu UI-ul) și fallback la `query_db` pentru SQL ad-hoc cu validări
stricte (doar SELECT/WITH, tenant_id obligatoriu în WHERE, max 200 rânduri,
statement_timeout 8s, tabele de credențiale blocate). Persistă conversații
+ mesaje + memoria tenant-wide; logează cost USD per call în `ai_usage_log`.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/ai/conversations` | Listă conversații ale tenant-ului (sau toate org-urile pentru SIKADP). |
| POST | `/api/ai/conversations` | Creare conversație nouă (cu `title` opțional). |
| DELETE | `/api/ai/conversations/{conv_id}` | Șterge conversație + mesaje (CASCADE). |
| GET | `/api/ai/conversations/{conv_id}/messages` | Istoric mesaje ordonat asc după `created_at`. |
| POST | `/api/ai/conversations/{conv_id}/messages` | Trimite mesaj user, rulează LLM cu tool loop, returnează răspuns. |

Modulul are DOAR aceste endpoint-uri (nu există `/api/ai/usage` etc. —
metricile de cost se citesc din `/api/admin/metrics`).

## Tables

- **`ai_conversations`** — conversații (tenant_id, user_id, title,
  timestamps). `updated_at` se bumpează la fiecare mesaj.
- **`ai_messages`** — mesaje (conversation_id, role: `user|assistant|
  system`, content TEXT, created_at).
- **`ai_memory`** — memorie persistentă tenant-wide (key/value). `user_id`
  NULL = memorie partajată în tenant. Reîncărcată automat în system prompt.
- **`ai_usage_log`** — un rând per call HTTP la provider: tokens in/out,
  `cost_usd` calculat din `pricing.MODEL_PRICES` (NULL dacă modelul nu e
  în tabel), `latency_ms`. Index pe `created_at` pentru rapoarte.

## Dependencies

- **`app_settings`** — `get_raw_ai_key` pentru cheile per-tenant criptate
  (override la env `*_API_KEY`).
- **`auth.deps`** — `get_current_user`, `get_current_org_ids` (multi-org
  pentru SIKADP).
- **`tenants.Organization`** — citit indirect prin `_resolve_tenant_for_scope`
  în `app_views.py` (mapează `scope='adp'/'sika'` la slug-ul org-ului).
- **Toate modulele de raportare** — `app_views.py` cheamă service-urile
  lor: `marja_lunara.build_marja_lunara`, `margine.*`, `top_produse.*`,
  `consolidat.*`, `analiza_pe_luni.*`, etc. — view dispatcher.
- **Provideri externi**: `anthropic` SDK, `openai` SDK (cu `base_url`
  custom pentru xAI și DeepSeek).

## Quirks / gotchas

- **Tool-use loop cu `MAX_TOOL_ITERATIONS = 40`**: după 40 de runde
  model→tool→model fără răspuns final, returnează un fallback message.
  `MAX_TOKENS = 32768` per call.
- **Provider auto-detect**: order de fallback la `_detect_provider` e
  `deepseek > anthropic > openai > xai` — DeepSeek e preferat by default
  ca cel mai ieftin. Override prin env `AI_PROVIDER`.
- **Tenant filter validat în SQL**: `tools.validate_sql` cere ca SQL-ul să
  conțină string-ul `<tenant_uuid>` (sau cel puțin unul din UUID-uri pentru
  SIKADP) literal — nu e o garanție semantică, e o euristică. AI-ul e
  educat în system prompt să folosească `tenant_id IN (...)` pentru
  consolidat.
- **Sub-tranzacție read-only**: `run_sql_readonly` rulează în
  `session.begin_nested()` cu `SET LOCAL transaction_read_only = on` și
  rollback la final, indiferent de rezultat. Strict no side-effects.
- **Pricing approximativ**: `pricing.MODEL_PRICES` are valorile manual
  introduse (Aprilie 2026). Modele lipsă → `cost_usd = NULL` și doar
  tokens sunt logate. Update manual la schimbări de prețuri provider.
- **Memoria persistentă e per-tenant primar**: pentru SIKADP se folosește
  `tenant_ids[0]` (org-ul default) ca să fie vizibilă uniform.
- **`propose_write` / `execute_write` au fost dezactivate** intenționat —
  module e strict read-only. Apelarea lor returnează error explicit.
  Pattern-ul e încă în codebase pentru reactivare ulterioară.
- **Logging usage e fail-soft**: dacă insertul în `ai_usage_log` fail-uiește
  (ex. tabelă lock), AI-ul răspunde corect — doar pierdem tracking-ul.
  Se folosește o `SessionLocal()` proprie ca să nu murdărim sesiunea
  request-ului.
- **Stub mode**: dacă niciun provider n-are cheie configurată,
  `assistant_text` e un mesaj informativ care explică ce env vars / setări
  trebuie populate.

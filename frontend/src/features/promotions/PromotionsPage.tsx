import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import {
  createPromotion,
  deletePromotion,
  listGroups,
  listPromotions,
  searchProducts,
  simulatePromotion,
  updatePromotion,
} from "./api";
import type {
  BaselineKind,
  GroupOption,
  ProductSearchItem,
  PromoDiscountType,
  PromoScope,
  PromoSimResponse,
  PromoStatus,
  PromoTargetKind,
  PromotionIn,
  PromotionOut,
} from "./types";


type TargetMode = "all" | "products" | "groups" | "private_label";


const SCOPE_LABEL: Record<PromoScope, string> = { adp: "Adeplast", sika: "Sika" };
const STATUS_LABEL: Record<PromoStatus, string> = {
  draft: "Draft", active: "Activă", archived: "Arhivată",
};
const DISCOUNT_LABEL: Record<PromoDiscountType, string> = {
  pct: "% reducere",
  override_price: "Pret override (RON/buc)",
  fixed_per_unit: "Reducere fixa (RON/buc)",
};
const TARGET_LABEL: Record<PromoTargetKind, string> = {
  all: "Toate produsele",
  product: "Cod produs",
  category: "Categorie ADP",
  tm: "TM Sika",
  private_label: "Marca Privata",
};
const KA_CLIENTS: { canonical: string; label: string }[] = [
  { canonical: "DEDEMAN SRL", label: "Dedeman" },
  { canonical: "HORNBACH CENTRALA SRL", label: "Hornbach" },
  { canonical: "LEROY MERLIN ROMANIA SRL", label: "Leroy Merlin" },
  { canonical: "ALTEX ROMANIA SRL", label: "Altex" },
  { canonical: "BRICOSTORE ROMANIA SRL", label: "Brico" },
];


function toNum(v: string | number | null | undefined): number {
  if (v == null) return 0;
  if (typeof v === "number") return v;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function fmtRo(n: number, frac = 0): string {
  return new Intl.NumberFormat("ro-RO", {
    maximumFractionDigits: frac, minimumFractionDigits: frac,
  }).format(n);
}

function fmtPct(n: number, frac = 1): string {
  return `${n >= 0 ? "" : "−"}${Math.abs(n).toLocaleString("ro-RO", {
    minimumFractionDigits: frac, maximumFractionDigits: frac,
  })}%`;
}


export default function PromotionsPage() {
  const [items, setItems] = useState<PromotionOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterScope, setFilterScope] = useState<PromoScope | "">("");
  const [filterStatus, setFilterStatus] = useState<PromoStatus | "">("");
  const [editing, setEditing] = useState<PromotionOut | null>(null);
  const [creating, setCreating] = useState(false);
  const [simulating, setSimulating] = useState<PromotionOut | null>(null);

  async function refresh() {
    setLoading(true); setError(null);
    try {
      const r = await listPromotions(
        filterScope || undefined, filterStatus || undefined,
      );
      setItems(r.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Eroare la incarcare");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterScope, filterStatus]);

  return (
    <div style={styles.page}>
      <div style={styles.sectionTitle}>Scenarii Promotii</div>
      <div style={styles.sectionSubtitle}>
        Defineste promotii (% reducere / pret override / reducere fixa per unitate)
        si simuleaza impactul pe marja vs baseline (anul trecut sau perioada
        anterioara). Volume neschimbate — promotia ajusteaza doar pretul de vanzare.
      </div>

      <div style={styles.controls}>
        <div style={styles.filters}>
          <select value={filterScope} onChange={(e) => setFilterScope(e.target.value as PromoScope | "")} style={styles.select}>
            <option value="">Toate scope</option>
            <option value="adp">Adeplast</option>
            <option value="sika">Sika</option>
          </select>
          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value as PromoStatus | "")} style={styles.select}>
            <option value="">Toate statusurile</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="archived">Arhivate</option>
          </select>
        </div>
        <div style={{ flex: 1 }} />
        <button type="button" onClick={() => setCreating(true)} style={styles.primaryBtn}>
          + Promotie noua
        </button>
      </div>

      {loading && <div style={styles.muted}>Se incarca...</div>}
      {error && <div style={styles.errorBox}>{error}</div>}

      {!loading && items.length === 0 && (
        <div style={styles.muted}>Nicio promotie definita inca.</div>
      )}

      {!loading && items.length > 0 && (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Nume</th>
              <th style={styles.th}>Scope</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Tip reducere</th>
              <th style={{ ...styles.th, textAlign: "right" }}>Valoare</th>
              <th style={styles.th}>Perioada</th>
              <th style={styles.th}>Clienti</th>
              <th style={styles.th}>Tinte</th>
              <th style={styles.th}>Actiuni</th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id}>
                <td style={{ ...styles.td, fontWeight: 600 }}>{p.name}</td>
                <td style={styles.td}>{SCOPE_LABEL[p.scope]}</td>
                <td style={styles.td}>
                  <span style={{ ...styles.badge, ...statusBadgeStyle(p.status) }}>
                    {STATUS_LABEL[p.status]}
                  </span>
                </td>
                <td style={styles.td}>{DISCOUNT_LABEL[p.discountType]}</td>
                <td style={{ ...styles.td, textAlign: "right" }}>
                  {p.discountType === "pct"
                    ? `${toNum(p.value).toFixed(1)}%`
                    : `${fmtRo(toNum(p.value), 2)} RON`}
                </td>
                <td style={styles.td}>{p.validFrom} → {p.validTo}</td>
                <td style={{ ...styles.td, fontSize: 11 }}>
                  {p.clientFilter && p.clientFilter.length > 0
                    ? p.clientFilter.map((c) => KA_CLIENTS.find((k) => k.canonical === c)?.label ?? c).join(", ")
                    : "Toti"}
                </td>
                <td style={{ ...styles.td, fontSize: 11 }}>
                  {p.targets.length === 0
                    ? "—"
                    : p.targets.map((t) => `${TARGET_LABEL[t.kind]}${t.key && t.kind !== "all" ? `: ${t.key}` : ""}`).join("; ")}
                </td>
                <td style={styles.td}>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button type="button" onClick={() => setSimulating(p)} style={styles.smallBtn} title="Simulare impact">
                      ▶ Simulare
                    </button>
                    <button type="button" onClick={() => setEditing(p)} style={styles.smallBtn}>
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={async () => {
                        if (!confirm(`Sterge promotia "${p.name}"?`)) return;
                        try {
                          await deletePromotion(p.id);
                          await refresh();
                        } catch (e) {
                          setError(e instanceof Error ? e.message : "Eroare");
                        }
                      }}
                      style={{ ...styles.smallBtn, color: "var(--red)" }}
                    >
                      Sterge
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {(creating || editing) && (
        <PromotionForm
          initial={editing}
          onClose={() => { setCreating(false); setEditing(null); }}
          onSaved={async () => { setCreating(false); setEditing(null); await refresh(); }}
        />
      )}

      {simulating && (
        <SimulationModal
          promo={simulating}
          onClose={() => setSimulating(null)}
        />
      )}
    </div>
  );
}


function statusBadgeStyle(s: PromoStatus): CSSProperties {
  if (s === "active") return { background: "rgba(34,197,94,0.15)", color: "var(--green)" };
  if (s === "archived") return { background: "rgba(255,255,255,0.06)", color: "var(--muted)" };
  return { background: "rgba(251,146,60,0.15)", color: "var(--orange)" };
}


function PromotionForm({
  initial, onClose, onSaved,
}: {
  initial: PromotionOut | null;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const initialMode = inferTargetMode(initial?.targets ?? []);
  const initialProductCodes = (initial?.targets ?? [])
    .filter((t) => t.kind === "product")
    .map((t) => t.key);
  const initialGroupKeys = (initial?.targets ?? [])
    .filter((t) => t.kind === "category" || t.kind === "tm")
    .map((t) => `${t.kind}::${t.key}`);

  const [form, setForm] = useState<PromotionIn>(() => ({
    scope: initial?.scope ?? "adp",
    name: initial?.name ?? "",
    status: initial?.status ?? "draft",
    discountType: initial?.discountType ?? "pct",
    value: initial?.value ?? "0",
    validFrom: initial?.validFrom ?? today,
    validTo: initial?.validTo ?? today,
    clientFilter: initial?.clientFilter ?? null,
    notes: initial?.notes ?? null,
    targets: [], // populat la save din mode + selectii
  }));
  const [targetMode, setTargetMode] = useState<TargetMode>(initialMode);
  const [selectedProducts, setSelectedProducts] = useState<Set<string>>(new Set(initialProductCodes));
  const [selectedGroups, setSelectedGroups] = useState<Set<string>>(new Set(initialGroupKeys));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function setF<K extends keyof PromotionIn>(k: K, v: PromotionIn[K]) {
    setForm((prev) => ({ ...prev, [k]: v }));
  }

  function toggleClient(canonical: string) {
    setForm((prev) => {
      const cur = prev.clientFilter ?? [];
      const next = cur.includes(canonical) ? cur.filter((c) => c !== canonical) : [...cur, canonical];
      return { ...prev, clientFilter: next.length === 0 ? null : next };
    });
  }

  function buildTargetsForSave() {
    if (targetMode === "all") return [{ kind: "all" as const, key: "" }];
    if (targetMode === "private_label") return [{ kind: "private_label" as const, key: "marca_privata" }];
    if (targetMode === "products") {
      return Array.from(selectedProducts).map((code) => ({
        kind: "product" as const, key: code,
      }));
    }
    // groups: keys are "kind::key"
    return Array.from(selectedGroups).map((compoundKey) => {
      const [kind, key] = compoundKey.split("::");
      return { kind: kind as "category" | "tm" | "private_label", key };
    });
  }

  async function onSubmit() {
    if (!form.name.trim()) {
      setErr("Numele promotiei e obligatoriu");
      return;
    }
    const targets = buildTargetsForSave();
    if (targets.length === 0) {
      setErr("Selecteaza cel putin o tinta");
      return;
    }
    const payload: PromotionIn = { ...form, targets };
    setBusy(true); setErr(null);
    try {
      if (initial) {
        await updatePromotion(initial.id, payload);
      } else {
        await createPromotion(payload);
      }
      await onSaved();
    } catch (e) {
      if (e instanceof ApiError) setErr(e.message);
      else if (e instanceof Error) setErr(e.message);
      else setErr("Eroare la salvare");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.modalOverlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.modalHeader}>
          <div style={{ fontSize: 16, fontWeight: 700 }}>
            {initial ? "Editeaza promotia" : "Promotie noua"}
          </div>
          <button type="button" onClick={onClose} style={styles.closeBtn}>×</button>
        </div>

        <div style={styles.formGrid}>
          <div style={styles.formField}>
            <label style={styles.formLabel}>Nume</label>
            <input value={form.name} onChange={(e) => setF("name", e.target.value)} style={styles.input} />
          </div>
          <div style={styles.formField}>
            <label style={styles.formLabel}>Scope</label>
            <select value={form.scope} onChange={(e) => setF("scope", e.target.value as PromoScope)} style={styles.select}>
              <option value="adp">Adeplast</option>
              <option value="sika">Sika</option>
            </select>
          </div>
          <div style={styles.formField}>
            <label style={styles.formLabel}>Status</label>
            <select value={form.status} onChange={(e) => setF("status", e.target.value as PromoStatus)} style={styles.select}>
              <option value="draft">Draft</option>
              <option value="active">Activă</option>
              <option value="archived">Arhivată</option>
            </select>
          </div>
          <div style={styles.formField}>
            <label style={styles.formLabel}>Tip reducere</label>
            <select value={form.discountType} onChange={(e) => setF("discountType", e.target.value as PromoDiscountType)} style={styles.select}>
              <option value="pct">% reducere</option>
              <option value="override_price">Pret override (RON/buc)</option>
              <option value="fixed_per_unit">Reducere fixa (RON/buc)</option>
            </select>
          </div>
          <div style={styles.formField}>
            <label style={styles.formLabel}>
              Valoare {form.discountType === "pct" ? "(%)" : "(RON/buc)"}
            </label>
            <input
              type="number" step="0.01" value={form.value}
              onChange={(e) => setF("value", e.target.value)} style={styles.input}
            />
          </div>
          <div style={styles.formField}>
            <label style={styles.formLabel}>Valid de la</label>
            <input type="date" value={form.validFrom} onChange={(e) => setF("validFrom", e.target.value)} style={styles.input} />
          </div>
          <div style={styles.formField}>
            <label style={styles.formLabel}>Valid pana la</label>
            <input type="date" value={form.validTo} onChange={(e) => setF("validTo", e.target.value)} style={styles.input} />
          </div>
        </div>

        <div style={styles.formField}>
          <label style={styles.formLabel}>Clienti KA (gol = toti)</label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {KA_CLIENTS.map((c) => {
              const active = (form.clientFilter ?? []).includes(c.canonical);
              return (
                <button
                  key={c.canonical}
                  type="button"
                  onClick={() => toggleClient(c.canonical)}
                  style={{ ...styles.chip, ...(active ? styles.chipActive : {}) }}
                >
                  {c.label}
                </button>
              );
            })}
          </div>
        </div>

        <div style={styles.formField}>
          <label style={styles.formLabel}>Tinte promotie</label>
          <div style={styles.modeTabs}>
            {([
              { key: "all", label: "Toate produsele" },
              { key: "products", label: "Selecteaza produse" },
              { key: "groups", label: "Selecteaza grupe" },
              { key: "private_label", label: "Doar Marca Privata", scopes: ["adp"] as PromoScope[] },
            ] as const).map((m) => {
              if ("scopes" in m && m.scopes && !m.scopes.includes(form.scope)) return null;
              const active = targetMode === m.key;
              return (
                <button
                  key={m.key}
                  type="button"
                  onClick={() => setTargetMode(m.key as TargetMode)}
                  style={{ ...styles.tabBtn, ...(active ? styles.tabBtnActive : {}) }}
                >
                  {m.label}
                </button>
              );
            })}
          </div>

          {targetMode === "products" && (
            <ProductPicker
              scope={form.scope}
              selected={selectedProducts}
              onChange={setSelectedProducts}
            />
          )}
          {targetMode === "groups" && (
            <GroupPicker
              scope={form.scope}
              selected={selectedGroups}
              onChange={setSelectedGroups}
            />
          )}
          {targetMode === "all" && (
            <div style={styles.muted}>Promotia se aplica pe toate produsele KA din scope-ul {form.scope === "adp" ? "Adeplast" : "Sika"}.</div>
          )}
          {targetMode === "private_label" && (
            <div style={styles.muted}>Promotia se aplica doar pe produsele cu brand=Marca Privata.</div>
          )}
        </div>

        <div style={styles.formField}>
          <label style={styles.formLabel}>Note</label>
          <textarea
            value={form.notes ?? ""}
            onChange={(e) => setF("notes", e.target.value || null)}
            rows={3}
            style={{ ...styles.input, fontFamily: "inherit" }}
          />
        </div>

        {err && <div style={styles.errorBox}>{err}</div>}

        <div style={styles.modalFooter}>
          <button type="button" onClick={onClose} style={styles.secondaryBtn} disabled={busy}>Renunta</button>
          <button type="button" onClick={onSubmit} disabled={busy} style={styles.primaryBtn}>
            {busy ? "Salveaza..." : initial ? "Salveaza" : "Creeaza"}
          </button>
        </div>
      </div>
    </div>
  );
}


function inferTargetMode(targets: { kind: string; key: string }[]): TargetMode {
  if (targets.length === 0) return "all";
  if (targets.some((t) => t.kind === "all")) return "all";
  if (targets.length === 1 && targets[0].kind === "private_label") return "private_label";
  if (targets.every((t) => t.kind === "product")) return "products";
  if (targets.every((t) => t.kind === "category" || t.kind === "tm" || t.kind === "private_label")) return "groups";
  return "products";
}


function ProductPicker({
  scope, selected, onChange,
}: {
  scope: PromoScope;
  selected: Set<string>;
  onChange: (s: Set<string>) => void;
}) {
  const [items, setItems] = useState<ProductSearchItem[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setErr(null);
    searchProducts(scope, "")
      .then((r) => { if (!cancelled) setItems(r.items); })
      .catch((e) => { if (!cancelled) setErr(e instanceof Error ? e.message : "Eroare"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [scope]);

  const filtered = useMemo(() => {
    const f = filter.trim().toLowerCase();
    if (!f) return items;
    return items.filter((it) =>
      it.code.toLowerCase().includes(f) ||
      it.name.toLowerCase().includes(f) ||
      (it.categoryLabel ?? "").toLowerCase().includes(f)
    );
  }, [items, filter]);

  function toggle(code: string) {
    const next = new Set(selected);
    if (next.has(code)) next.delete(code); else next.add(code);
    onChange(next);
  }

  function selectAllVisible() {
    const next = new Set(selected);
    for (const it of filtered) next.add(it.code);
    onChange(next);
  }
  function clearAll() {
    onChange(new Set());
  }

  return (
    <div style={styles.pickerBox}>
      <div style={styles.pickerHeader}>
        <input
          type="search"
          placeholder="Cauta cod / denumire / grupa..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ ...styles.input, flex: 1, maxWidth: 280 }}
        />
        <span style={styles.pickerCount}>
          {selected.size} selectate / {filtered.length} afisate
        </span>
        <button type="button" onClick={selectAllVisible} style={styles.smallBtn}>
          Selecteaza tot
        </button>
        <button type="button" onClick={clearAll} style={styles.smallBtn}>
          Goleste
        </button>
      </div>

      {loading && <div style={styles.muted}>Se incarca produsele...</div>}
      {err && <div style={styles.errorBox}>{err}</div>}

      {!loading && (
        <div style={styles.pickerList}>
          {filtered.length === 0 && (
            <div style={styles.muted}>Niciun produs corespunde filtrului.</div>
          )}
          {filtered.map((it) => {
            const checked = selected.has(it.code);
            return (
              <label
                key={it.code}
                style={{ ...styles.pickerRow, ...(checked ? styles.pickerRowActive : {}) }}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(it.code)}
                  style={{ marginRight: 8 }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)" }}>
                    {it.name}
                  </div>
                  <div style={{ fontSize: 10, color: "var(--muted)" }}>
                    {it.code}
                    {it.categoryLabel && ` · ${it.categoryLabel}`}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}


function GroupPicker({
  scope, selected, onChange,
}: {
  scope: PromoScope;
  selected: Set<string>;
  onChange: (s: Set<string>) => void;
}) {
  const [groups, setGroups] = useState<GroupOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setErr(null);
    listGroups(scope)
      .then((r) => { if (!cancelled) setGroups(r.items); })
      .catch((e) => { if (!cancelled) setErr(e instanceof Error ? e.message : "Eroare"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [scope]);

  function toggle(g: GroupOption) {
    const k = `${g.kind}::${g.key}`;
    const next = new Set(selected);
    if (next.has(k)) next.delete(k); else next.add(k);
    onChange(next);
  }

  return (
    <div style={styles.pickerBox}>
      <div style={styles.pickerHeader}>
        <span style={styles.pickerCount}>
          {selected.size} selectate / {groups.length} grupe
        </span>
        <button type="button" onClick={() => onChange(new Set(groups.map((g) => `${g.kind}::${g.key}`)))} style={styles.smallBtn}>
          Selecteaza tot
        </button>
        <button type="button" onClick={() => onChange(new Set())} style={styles.smallBtn}>
          Goleste
        </button>
      </div>
      {loading && <div style={styles.muted}>Se incarca grupele...</div>}
      {err && <div style={styles.errorBox}>{err}</div>}
      {!loading && (
        <div style={styles.pickerList}>
          {groups.map((g) => {
            const k = `${g.kind}::${g.key}`;
            const checked = selected.has(k);
            return (
              <label
                key={k}
                style={{ ...styles.pickerRow, ...(checked ? styles.pickerRowActive : {}) }}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(g)}
                  style={{ marginRight: 8 }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{g.label}</div>
                  <div style={{ fontSize: 10, color: "var(--muted)" }}>
                    {g.kind === "category" ? "Categorie" : g.kind === "tm" ? "Target Market Sika" : "Brand"}
                    {g.kind !== "private_label" && ` · ${g.key}`}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}


function SimulationModal({
  promo, onClose,
}: { promo: PromotionOut; onClose: () => void }) {
  const [baseline, setBaseline] = useState<BaselineKind>("yoy");
  const [data, setData] = useState<PromoSimResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setErr(null);
    simulatePromotion(promo.id, baseline)
      .then((r) => { if (!cancelled) setData(r); })
      .catch((e) => { if (!cancelled) setErr(e instanceof Error ? e.message : "Eroare"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [promo.id, baseline]);

  return (
    <div style={styles.modalOverlay} onClick={onClose}>
      <div style={{ ...styles.modal, maxWidth: 1100 }} onClick={(e) => e.stopPropagation()}>
        <div style={styles.modalHeader}>
          <div style={{ fontSize: 16, fontWeight: 700 }}>Simulare: {promo.name}</div>
          <button type="button" onClick={onClose} style={styles.closeBtn}>×</button>
        </div>

        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <button
            type="button"
            onClick={() => setBaseline("yoy")}
            style={{ ...styles.tabBtn, ...(baseline === "yoy" ? styles.tabBtnActive : {}) }}
          >
            vs Anul Trecut (YoY)
          </button>
          <button
            type="button"
            onClick={() => setBaseline("mom")}
            style={{ ...styles.tabBtn, ...(baseline === "mom" ? styles.tabBtnActive : {}) }}
          >
            vs Perioada Anterioara (MoM)
          </button>
        </div>

        {loading && <div style={styles.muted}>Se calculeaza...</div>}
        {err && <div style={styles.errorBox}>{err}</div>}

        {!loading && data && (
          <>
            <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 10 }}>
              Promotia: <strong>{data.promoLabel}</strong> · Baseline: <strong>{data.baselineLabel}</strong> · {data.productsInScope} produse afectate
            </div>

            <div style={styles.kpiRow}>
              <SimKpi label="Revenue baseline" value={fmtRo(toNum(data.baselineRevenue), 0)} unit="RON" />
              <SimKpi label="Revenue scenariu" value={fmtRo(toNum(data.scenarioRevenue), 0)} unit="RON" tone={toNum(data.deltaRevenue) >= 0 ? "good" : "bad"} />
              <SimKpi label="Delta revenue" value={fmtRo(toNum(data.deltaRevenue), 0)} unit="RON" tone={toNum(data.deltaRevenue) >= 0 ? "good" : "bad"} />
              <SimKpi label="Profit baseline" value={fmtRo(toNum(data.baselineProfit), 0)} unit="RON" />
              <SimKpi label="Profit scenariu" value={fmtRo(toNum(data.scenarioProfit), 0)} unit="RON" tone={toNum(data.scenarioProfit) >= 0 ? "good" : "bad"} />
              <SimKpi label="Delta profit" value={fmtRo(toNum(data.deltaProfit), 0)} unit="RON" tone={toNum(data.deltaProfit) >= 0 ? "good" : "bad"} />
              <SimKpi label="Marja baseline" value={fmtPct(toNum(data.baselineMarginPct), 1)} />
              <SimKpi label="Marja scenariu" value={fmtPct(toNum(data.scenarioMarginPct), 1)} tone={toNum(data.scenarioMarginPct) >= 30 ? "good" : "bad"} />
              <SimKpi label="Delta marja (pp)" value={fmtPct(toNum(data.deltaMarginPp), 1)} tone={toNum(data.deltaMarginPp) >= 0 ? "good" : "bad"} />
            </div>

            {data.groups.length > 0 && (
              <table style={{ ...styles.table, marginTop: 14 }}>
                <thead>
                  <tr>
                    <th style={styles.th}>Grupa</th>
                    <th style={{ ...styles.th, textAlign: "right" }}>Rev. baseline</th>
                    <th style={{ ...styles.th, textAlign: "right" }}>Rev. scenariu</th>
                    <th style={{ ...styles.th, textAlign: "right" }}>Delta rev.</th>
                    <th style={{ ...styles.th, textAlign: "right" }}>Profit baseline</th>
                    <th style={{ ...styles.th, textAlign: "right" }}>Profit scenariu</th>
                    <th style={{ ...styles.th, textAlign: "right" }}>Delta profit</th>
                    <th style={{ ...styles.th, textAlign: "right" }}>Marja baseline</th>
                    <th style={{ ...styles.th, textAlign: "right" }}>Marja scenariu</th>
                    <th style={{ ...styles.th, textAlign: "right" }}>Δ pp</th>
                  </tr>
                </thead>
                <tbody>
                  {data.groups.map((g) => (
                    <tr key={`${g.kind}::${g.key}`}>
                      <td style={{ ...styles.td, fontWeight: 600 }}>{g.label}</td>
                      <td style={styles.tdNum}>{fmtRo(toNum(g.baselineRevenue), 0)}</td>
                      <td style={styles.tdNum}>{fmtRo(toNum(g.scenarioRevenue), 0)}</td>
                      <td style={{ ...styles.tdNum, color: toNum(g.deltaRevenue) >= 0 ? "var(--green)" : "var(--red)" }}>
                        {fmtRo(toNum(g.deltaRevenue), 0)}
                      </td>
                      <td style={styles.tdNum}>{fmtRo(toNum(g.baselineProfit), 0)}</td>
                      <td style={styles.tdNum}>{fmtRo(toNum(g.scenarioProfit), 0)}</td>
                      <td style={{ ...styles.tdNum, color: toNum(g.deltaProfit) >= 0 ? "var(--green)" : "var(--red)" }}>
                        {fmtRo(toNum(g.deltaProfit), 0)}
                      </td>
                      <td style={styles.tdNum}>{fmtPct(toNum(g.baselineMarginPct), 1)}</td>
                      <td style={styles.tdNum}>{fmtPct(toNum(g.scenarioMarginPct), 1)}</td>
                      <td style={{ ...styles.tdNum, color: toNum(g.deltaMarginPp) >= 0 ? "var(--green)" : "var(--red)" }}>
                        {fmtPct(toNum(g.deltaMarginPp), 1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </div>
  );
}


function SimKpi({
  label, value, unit, tone,
}: { label: string; value: string; unit?: string; tone?: "good" | "bad" }) {
  const color = tone === "good" ? "var(--green)" : tone === "bad" ? "var(--red)" : "var(--text)";
  return (
    <div style={styles.kpiCard}>
      <div style={styles.kpiLabel}>{label}</div>
      <div style={{ ...styles.kpiValue, color }}>
        {value}
        {unit && <span style={styles.kpiUnit}> {unit}</span>}
      </div>
    </div>
  );
}


const styles: Record<string, CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: 14 },
  sectionTitle: { fontSize: 20, fontWeight: 700 },
  sectionSubtitle: { fontSize: 12, color: "var(--muted)", marginTop: -8, lineHeight: 1.5 },
  controls: { display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" },
  filters: { display: "flex", gap: 6 },
  select: {
    background: "var(--bg)", color: "var(--text)",
    border: "1px solid var(--border)", padding: "6px 10px",
    borderRadius: 6, fontSize: 13,
  },
  input: {
    background: "var(--bg)", color: "var(--text)",
    border: "1px solid var(--border)", padding: "6px 10px",
    borderRadius: 6, fontSize: 13, width: "100%",
  },
  primaryBtn: {
    background: "linear-gradient(135deg, #22d3ee, #06b6d4)",
    color: "#0a0e17", border: "none",
    padding: "8px 18px", borderRadius: 6,
    fontSize: 13, fontWeight: 700, cursor: "pointer",
  },
  secondaryBtn: {
    background: "transparent", color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "6px 14px", borderRadius: 6,
    fontSize: 12, cursor: "pointer",
  },
  smallBtn: {
    background: "transparent", color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "4px 8px", borderRadius: 4,
    fontSize: 11, cursor: "pointer",
  },
  tabBtn: {
    background: "transparent", color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "6px 14px", borderRadius: 6,
    fontSize: 13, fontWeight: 600, cursor: "pointer",
  },
  tabBtnActive: {
    background: "linear-gradient(135deg, #22d3ee, #06b6d4)",
    color: "#0a0e17", border: "none",
  },
  chip: {
    background: "transparent", color: "var(--muted)",
    border: "1px solid var(--border)",
    padding: "4px 12px", borderRadius: 16,
    fontSize: 12, cursor: "pointer",
  },
  chipActive: {
    background: "rgba(34,211,238,0.15)", color: "var(--cyan)",
    borderColor: "var(--cyan)",
  },
  badge: {
    padding: "2px 8px", borderRadius: 10, fontSize: 10,
    fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em",
  },
  errorBox: {
    background: "rgba(239,68,68,0.1)", border: "1px solid var(--red)",
    color: "var(--red)", padding: 10, borderRadius: 6, fontSize: 12,
  },
  muted: { color: "var(--muted)", fontSize: 13 },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th: {
    borderBottom: "1px solid var(--border)",
    padding: "8px 10px", textAlign: "left",
    fontSize: 11, fontWeight: 700,
    color: "var(--muted)", textTransform: "uppercase",
    letterSpacing: "0.04em",
  },
  td: {
    borderBottom: "1px solid rgba(255,255,255,0.04)",
    padding: "8px 10px", color: "var(--text)",
  },
  tdNum: {
    borderBottom: "1px solid rgba(255,255,255,0.04)",
    padding: "8px 10px", textAlign: "right",
    fontVariantNumeric: "tabular-nums", color: "var(--text)",
  },
  modalOverlay: {
    position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
    display: "flex", alignItems: "center", justifyContent: "center",
    zIndex: 1000, padding: 20,
  },
  modal: {
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 10, padding: 20, maxWidth: 760, width: "100%",
    maxHeight: "90vh", overflowY: "auto",
    display: "flex", flexDirection: "column", gap: 12,
  },
  modalHeader: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    paddingBottom: 8, borderBottom: "1px solid var(--border)",
  },
  closeBtn: {
    background: "transparent", border: "none", color: "var(--text)",
    fontSize: 22, cursor: "pointer", padding: "0 6px",
  },
  modalFooter: {
    display: "flex", justifyContent: "flex-end", gap: 8,
    paddingTop: 10, borderTop: "1px solid var(--border)",
  },
  formGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: 10,
  },
  formField: { display: "flex", flexDirection: "column", gap: 4 },
  formLabel: {
    fontSize: 11, color: "var(--muted)",
    textTransform: "uppercase", letterSpacing: "0.04em",
    fontWeight: 600,
  },
  kpiRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: 8,
  },
  kpiCard: {
    background: "rgba(0,0,0,0.15)", border: "1px solid var(--border)",
    borderRadius: 8, padding: "8px 10px", minHeight: 56,
  },
  kpiLabel: {
    fontSize: 10, color: "var(--muted)",
    textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 600,
  },
  kpiValue: { fontSize: 16, fontWeight: 800, lineHeight: 1.2 },
  kpiUnit: { fontSize: 10, fontWeight: 500, color: "var(--muted)", marginLeft: 3 },
  modeTabs: { display: "flex", gap: 4, marginBottom: 8, flexWrap: "wrap" },
  pickerBox: {
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: 8,
    display: "flex",
    flexDirection: "column",
    gap: 6,
    background: "rgba(0,0,0,0.12)",
  },
  pickerHeader: {
    display: "flex",
    gap: 8,
    alignItems: "center",
    flexWrap: "wrap",
  },
  pickerCount: { fontSize: 11, color: "var(--muted)", marginLeft: 4 },
  pickerList: {
    maxHeight: 300,
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: 2,
    border: "1px solid var(--border)",
    borderRadius: 6,
    padding: 4,
    background: "var(--bg)",
  },
  pickerRow: {
    display: "flex",
    alignItems: "center",
    padding: "6px 8px",
    borderRadius: 4,
    cursor: "pointer",
    fontSize: 12,
  },
  pickerRowActive: {
    background: "rgba(34,211,238,0.08)",
  },
};

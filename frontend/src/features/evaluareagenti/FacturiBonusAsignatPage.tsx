import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import {
  acceptFacturiBonus,
  getFacturiBonus,
  unassignFacturiBonus,
} from "./api";
import { fmtRo, MONTHS_RO, toNum } from "./shared";
import type { FacturaBonusRow } from "./types";

type TabKey = "pending" | "assigned";

export default function FacturiBonusAsignatPage() {
  const [rows, setRows] = useState<FacturaBonusRow[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [pendingAmount, setPendingAmount] = useState<string>("0");
  const [assignedCount, setAssignedCount] = useState(0);
  const [assignedAmount, setAssignedAmount] = useState<string>("0");
  const [threshold, setThreshold] = useState<string>("-20000");
  const [tab, setTab] = useState<TabKey>("pending");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getFacturiBonus();
      setRows(data.rows);
      setPendingCount(data.pendingCount);
      setPendingAmount(data.pendingAmount);
      setAssignedCount(data.assignedCount);
      setAssignedAmount(data.assignedAmount);
      setThreshold(data.threshold);
      setSelected(new Set());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    setSelected(new Set());
  }, [tab]);

  const visibleRows = useMemo(
    () => rows.filter((r) => r.status === tab),
    [rows, tab],
  );

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (tab === "pending") {
      const ok = visibleRows.filter(
        (r) => r.suggestedStoreId !== null && r.suggestedAgentId !== null,
      );
      if (selected.size === ok.length && ok.length > 0) {
        setSelected(new Set());
      } else {
        setSelected(new Set(ok.map((r) => r.id)));
      }
    } else {
      if (selected.size === visibleRows.length && visibleRows.length > 0) {
        setSelected(new Set());
      } else {
        setSelected(new Set(visibleRows.map((r) => r.id)));
      }
    }
  };

  const applyAccept = async () => {
    if (selected.size === 0) return;
    setSaving(true);
    setError(null);
    try {
      const res = await acceptFacturiBonus(Array.from(selected));
      setFlash(
        `Asignat: ${res.accepted} factur${res.accepted === 1 ? "ă" : "i"}${
          res.skipped > 0 ? ` · ${res.skipped} omise` : ""
        }`,
      );
      setTimeout(() => setFlash(null), 3500);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la aplicare");
    } finally {
      setSaving(false);
    }
  };

  const applyUnassign = async () => {
    if (selected.size === 0) return;
    setSaving(true);
    setError(null);
    try {
      const res = await unassignFacturiBonus(Array.from(selected));
      setFlash(
        `Dezasignat: ${res.unassigned} factur${res.unassigned === 1 ? "ă" : "i"}${
          res.skipped > 0 ? ` · ${res.skipped} omise` : ""
        }`,
      );
      setTimeout(() => setFlash(null), 3500);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la dezasignare");
    } finally {
      setSaving(false);
    }
  };

  const selectedAmount = useMemo(() => {
    let sum = 0;
    for (const r of visibleRows) if (selected.has(r.id)) sum += toNum(r.amount);
    return sum;
  }, [visibleRows, selected]);

  const allChecked = useMemo(() => {
    if (tab === "pending") {
      const ok = visibleRows.filter(
        (r) => r.suggestedStoreId !== null && r.suggestedAgentId !== null,
      );
      return ok.length > 0 && selected.size === ok.length;
    }
    return visibleRows.length > 0 && selected.size === visibleRows.length;
  }, [visibleRows, selected, tab]);

  return (
    <div style={styles.wrap}>
      <h1 style={styles.title}>Facturi bonus de asignat</h1>

      <div style={styles.disclaimer}>
        <strong>Regulă:</strong> facturile cu valoare sub {fmtRo(toNum(threshold))} RON
        emise central pe clienți KA (Leroy Merlin, Dedeman, Altex, Hornbach, Bricostore,
        Puskin) sunt reasignate automat la import către <strong>Florin Puscuta</strong>{" "}
        + <strong>CHAIN Centrala</strong>. Deciziile rămân persistente între importuri
        (se salvează în tabelul <code>facturi_bonus_decisions</code>). Facturile din lista
        "De asignat" necesită confirmare manuală; cele din "Asignate" pot fi dezasignate
        oricând (rollback din backup).
      </div>

      {flash && <div style={styles.flashOk}>{flash}</div>}
      {error && <div style={styles.flashErr}>{error}</div>}

      <div style={styles.tabs}>
        <button
          type="button"
          onClick={() => setTab("pending")}
          style={{
            ...styles.tab,
            ...(tab === "pending" ? styles.tabActivePending : {}),
          }}
        >
          <span style={styles.dotRed} /> De asignat ({pendingCount})
          <span style={styles.tabAmt}>{fmtRo(toNum(pendingAmount))} RON</span>
        </button>
        <button
          type="button"
          onClick={() => setTab("assigned")}
          style={{
            ...styles.tab,
            ...(tab === "assigned" ? styles.tabActiveAssigned : {}),
          }}
        >
          <span style={styles.dotGreen} /> Asignate ({assignedCount})
          <span style={styles.tabAmt}>{fmtRo(toNum(assignedAmount))} RON</span>
        </button>
      </div>

      <div style={styles.toolbar}>
        <div style={styles.summary}>
          <span style={styles.summaryItem}>
            <span style={styles.summaryLabel}>Afișate:</span>
            <strong>{visibleRows.length}</strong>
          </span>
          <span style={styles.summaryItem}>
            <span style={styles.summaryLabel}>Selectat:</span>
            <strong style={selected.size > 0 ? styles.neg : undefined}>
              {selected.size} · {fmtRo(selectedAmount)} RON
            </strong>
          </span>
        </div>
        <div style={styles.actions}>
          <button
            type="button"
            onClick={load}
            style={styles.btnGhost}
            disabled={loading || saving}
          >
            Reîncarcă
          </button>
          {tab === "pending" ? (
            <button
              type="button"
              onClick={applyAccept}
              style={{
                ...styles.btnPrimary,
                ...(selected.size === 0 || saving ? styles.btnDisabled : {}),
              }}
              disabled={selected.size === 0 || saving}
            >
              {saving ? "Se aplică..." : `Aplică reasignarea (${selected.size})`}
            </button>
          ) : (
            <button
              type="button"
              onClick={applyUnassign}
              style={{
                ...styles.btnWarn,
                ...(selected.size === 0 || saving ? styles.btnDisabled : {}),
              }}
              disabled={selected.size === 0 || saving}
            >
              {saving ? "Se aplică..." : `Dezasignează (${selected.size})`}
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div style={styles.empty}>Se încarcă...</div>
      ) : visibleRows.length === 0 ? (
        <div style={styles.empty}>
          {tab === "pending"
            ? "Nu sunt facturi de reasignat. ✔"
            : "Nicio factură asignată încă."}
        </div>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={{ ...styles.th, ...styles.center, width: 36 }}>
                  <input
                    type="checkbox"
                    checked={allChecked}
                    onChange={toggleAll}
                    style={styles.chk}
                  />
                </th>
                <th style={{ ...styles.th, width: 100 }}>Status</th>
                <th style={styles.th}>Lună</th>
                <th style={{ ...styles.th, ...styles.right }}>Sumă (RON)</th>
                <th style={styles.th}>Client</th>
                <th style={styles.th}>Agent curent</th>
                <th style={styles.th}>Magazin curent</th>
                <th style={styles.th}>→ Agent</th>
                <th style={styles.th}>→ Magazin</th>
                {tab === "assigned" && <th style={styles.th}>Decis</th>}
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((r) => {
                const isChecked = selected.has(r.id);
                const canApply =
                  r.suggestedStoreId !== null && r.suggestedAgentId !== null;
                const isPending = r.status === "pending";
                const checkboxDisabled = isPending && !canApply;
                return (
                  <tr
                    key={r.id}
                    style={
                      isChecked
                        ? styles.trChecked
                        : isPending
                          ? styles.trPending
                          : styles.trAssigned
                    }
                  >
                    <td style={{ ...styles.td, ...styles.center }}>
                      <input
                        type="checkbox"
                        checked={isChecked}
                        disabled={checkboxDisabled}
                        onChange={() => toggle(r.id)}
                        style={styles.chk}
                      />
                    </td>
                    <td style={styles.td}>
                      {isPending ? (
                        <span style={styles.badgeRed}>
                          <span style={styles.dotRed} /> De asignat
                        </span>
                      ) : (
                        <span style={styles.badgeGreen}>
                          <span style={styles.dotGreen} /> Asignat
                          {r.decisionSource === "auto" ? " (auto)" : ""}
                        </span>
                      )}
                    </td>
                    <td style={styles.td}>
                      {MONTHS_RO[r.month - 1]?.slice(0, 3) ?? r.month} {r.year}
                    </td>
                    <td style={{ ...styles.td, ...styles.right, ...styles.neg }}>
                      {fmtRo(toNum(r.amount), 2)}
                    </td>
                    <td style={styles.td} title={r.client}>
                      <span style={styles.chainTag}>{r.chain ?? "—"}</span>
                      <span style={styles.clientRest}>
                        {shortenClient(r.client)}
                      </span>
                    </td>
                    <td style={styles.td}>
                      {r.agentName ?? <span style={styles.muted}>—</span>}
                    </td>
                    <td style={styles.td}>
                      {r.storeName ? (
                        <span title={r.storeName}>{shortenStore(r.storeName)}</span>
                      ) : (
                        <span style={styles.muted}>—</span>
                      )}
                    </td>
                    <td style={styles.td}>
                      {r.suggestedAgentName ? (
                        <span style={styles.suggest}>
                          {isPending ? "→ " : ""}
                          {r.suggestedAgentName}
                        </span>
                      ) : (
                        <span style={styles.warn}>lipsă</span>
                      )}
                    </td>
                    <td style={styles.td}>
                      {r.suggestedStoreName ? (
                        <span style={styles.suggest} title={r.suggestedStoreName}>
                          {isPending ? "→ " : ""}
                          {shortenStore(r.suggestedStoreName)}
                        </span>
                      ) : (
                        <span style={styles.warn}>lipsă Centrala</span>
                      )}
                    </td>
                    {tab === "assigned" && (
                      <td style={styles.td}>
                        <span style={styles.muted}>
                          {r.decidedAt ? fmtDate(r.decidedAt) : "—"}
                        </span>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function shortenClient(s: string): string {
  if (!s) return "";
  return s.length > 40 ? s.slice(0, 40) + "…" : s;
}

function shortenStore(s: string): string {
  if (!s) return "";
  return s.length > 45 ? s.slice(0, 45) + "…" : s;
}

function fmtDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("ro-RO", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

const styles: Record<string, CSSProperties> = {
  wrap: { padding: "20px 8px", maxWidth: 1500 },
  title: { fontSize: 22, fontWeight: 700, color: "var(--cyan)", margin: "0 0 12px" },
  disclaimer: {
    padding: "12px 14px",
    background: "rgba(234,179,8,0.08)",
    border: "1px solid rgba(234,179,8,0.35)",
    borderRadius: 6,
    color: "var(--text)",
    fontSize: 13,
    lineHeight: 1.6,
    margin: "0 0 14px",
  },
  flashOk: {
    padding: "10px 12px",
    background: "rgba(34,197,94,0.12)",
    border: "1px solid rgba(34,197,94,0.35)",
    color: "#4ade80",
    borderRadius: 6,
    fontSize: 13,
    margin: "0 0 10px",
  },
  flashErr: {
    padding: "10px 12px",
    background: "rgba(239,68,68,0.12)",
    border: "1px solid rgba(239,68,68,0.35)",
    color: "#f87171",
    borderRadius: 6,
    fontSize: 13,
    margin: "0 0 10px",
  },
  tabs: { display: "flex", gap: 8, margin: "0 0 12px" },
  tab: {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 14px",
    background: "var(--bg-panel)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    fontSize: 13,
    cursor: "pointer",
  },
  tabActivePending: {
    borderColor: "rgba(239,68,68,0.55)",
    background: "rgba(239,68,68,0.10)",
  },
  tabActiveAssigned: {
    borderColor: "rgba(34,197,94,0.55)",
    background: "rgba(34,197,94,0.10)",
  },
  tabAmt: {
    marginLeft: 4,
    color: "var(--muted)",
    fontSize: 12,
    fontVariantNumeric: "tabular-nums",
  },
  toolbar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16,
    padding: "10px 12px",
    background: "var(--bg-panel)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    margin: "0 0 12px",
    flexWrap: "wrap",
  },
  summary: { display: "flex", gap: 18, flexWrap: "wrap" },
  summaryItem: { display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13 },
  summaryLabel: { color: "var(--muted)" },
  actions: { display: "flex", gap: 8 },
  btnGhost: {
    padding: "7px 14px",
    background: "transparent",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 4,
    fontSize: 13,
    cursor: "pointer",
  },
  btnPrimary: {
    padding: "7px 14px",
    background: "var(--cyan)",
    color: "#0a0e14",
    border: "none",
    borderRadius: 4,
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
  },
  btnWarn: {
    padding: "7px 14px",
    background: "#f59e0b",
    color: "#0a0e14",
    border: "none",
    borderRadius: 4,
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
  },
  btnDisabled: { opacity: 0.5, cursor: "not-allowed" },
  empty: {
    padding: "30px 12px",
    textAlign: "center",
    color: "var(--muted)",
    fontSize: 14,
  },
  tableWrap: {
    overflow: "auto",
    border: "1px solid var(--border)",
    borderRadius: 6,
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 12.5,
  },
  th: {
    padding: "8px 10px",
    textAlign: "left",
    background: "var(--bg-panel)",
    borderBottom: "1px solid var(--border)",
    color: "var(--muted)",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    fontSize: 11,
    whiteSpace: "nowrap",
    position: "sticky",
    top: 0,
  },
  td: {
    padding: "7px 10px",
    borderBottom: "1px solid var(--border)",
    color: "var(--text)",
    whiteSpace: "nowrap",
  },
  trChecked: { background: "rgba(6,182,212,0.08)" },
  trPending: { background: "rgba(239,68,68,0.04)" },
  trAssigned: { background: "rgba(34,197,94,0.04)" },
  right: { textAlign: "right", fontVariantNumeric: "tabular-nums" },
  center: { textAlign: "center" },
  neg: { color: "#f87171", fontWeight: 600 },
  muted: { color: "var(--muted)" },
  warn: { color: "#fbbf24" },
  suggest: { color: "#4ade80", fontWeight: 500 },
  chainTag: {
    display: "inline-block",
    padding: "1px 6px",
    marginRight: 6,
    background: "rgba(6,182,212,0.12)",
    border: "1px solid rgba(6,182,212,0.35)",
    borderRadius: 3,
    fontSize: 10.5,
    color: "var(--cyan)",
    textTransform: "uppercase",
    letterSpacing: "0.03em",
  },
  clientRest: { color: "var(--muted)", fontSize: 12 },
  chk: { cursor: "pointer" },
  badgeRed: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "2px 8px",
    background: "rgba(239,68,68,0.12)",
    border: "1px solid rgba(239,68,68,0.40)",
    borderRadius: 3,
    color: "#f87171",
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.03em",
  },
  badgeGreen: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "2px 8px",
    background: "rgba(34,197,94,0.12)",
    border: "1px solid rgba(34,197,94,0.40)",
    borderRadius: 3,
    color: "#4ade80",
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.03em",
  },
  dotRed: {
    display: "inline-block",
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: "#ef4444",
  },
  dotGreen: {
    display: "inline-block",
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: "#22c55e",
  },
};

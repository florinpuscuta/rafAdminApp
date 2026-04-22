import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";

import { ApiError } from "../../shared/api";
import { useConfirm } from "../../shared/ui/ConfirmDialog";
import { norm, SearchInput } from "../../shared/ui/SearchInput";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import {
  createMapping,
  deleteMapping,
  listMappings,
  updateMapping,
  uploadMapping,
  type MappingCreatePayload,
  type MappingUpdatePayload,
  type StoreAgentMapping,
} from "./api";

type EditableField = keyof Pick<
  StoreAgentMapping,
  | "source"
  | "clientOriginal"
  | "shipToOriginal"
  | "agentOriginal"
  | "codNumeric"
  | "cheieFinala"
  | "agentUnificat"
>;

const EMPTY_CREATE: MappingCreatePayload = {
  source: "ADP",
  clientOriginal: "",
  shipToOriginal: "",
  agentOriginal: "",
  codNumeric: "",
  cheieFinala: "",
  agentUnificat: "",
};

export default function MappingsPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const fileRef = useRef<HTMLInputElement>(null);

  const [rows, setRows] = useState<StoreAgentMapping[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState<"ALL" | "ADP" | "SIKA">("ALL");

  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Partial<StoreAgentMapping>>({});
  const [savingId, setSavingId] = useState<string | null>(null);

  const [showNew, setShowNew] = useState(false);
  const [newRow, setNewRow] = useState<MappingCreatePayload>(EMPTY_CREATE);
  const [creating, setCreating] = useState(false);

  const [uploading, setUploading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const src = sourceFilter === "ALL" ? undefined : sourceFilter;
      setRows(await listMappings(src));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, [sourceFilter]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const filtered = useMemo(() => {
    const q = norm(search);
    if (!q) return rows;
    return rows.filter((r) =>
      norm(
        [
          r.clientOriginal,
          r.shipToOriginal,
          r.cheieFinala,
          r.agentUnificat,
          r.agentOriginal ?? "",
          r.codNumeric ?? "",
        ].join(" "),
      ).includes(q),
    );
  }, [rows, search]);

  function startEdit(row: StoreAgentMapping) {
    setEditingId(row.id);
    setDraft({ ...row });
  }

  function cancelEdit() {
    setEditingId(null);
    setDraft({});
  }

  async function saveEdit(row: StoreAgentMapping) {
    setSavingId(row.id);
    try {
      const changed: MappingUpdatePayload = {};
      const fields: EditableField[] = [
        "source",
        "clientOriginal",
        "shipToOriginal",
        "agentOriginal",
        "codNumeric",
        "cheieFinala",
        "agentUnificat",
      ];
      for (const f of fields) {
        const current = (row[f] ?? "") as string;
        const next = (draft[f] ?? "") as string;
        if (current !== next) {
          (changed as Record<string, string | null>)[f] = next || null;
        }
      }
      if (Object.keys(changed).length === 0) {
        cancelEdit();
        return;
      }
      await updateMapping(row.id, changed);
      toast.success("Mapare actualizată · backfill re-rulat");
      cancelEdit();
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare la salvare");
    } finally {
      setSavingId(null);
    }
  }

  async function handleDelete(row: StoreAgentMapping) {
    const ok = await confirm({
      title: "Șterge maparea",
      message: `Ștergi: ${row.clientOriginal} | ${row.shipToOriginal} → ${row.cheieFinala} (${row.agentUnificat})? Rândurile KA din raw_sales aferente vor rămâne fără store_id/agent_id până la o nouă mapare.`,
      confirmLabel: "Șterge",
      danger: true,
    });
    if (!ok) return;
    // Optimistic: remove imediat din UI, rollback dacă API eșuează.
    const snapshot = rows;
    setRows((prev) => prev.filter((r) => r.id !== row.id));
    try {
      await deleteMapping(row.id);
      toast.success("Mapare ștearsă · backfill re-rulat");
    } catch (err) {
      setRows(snapshot);
      toast.error(err instanceof ApiError ? err.message : "Eroare la ștergere");
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      await createMapping({
        ...newRow,
        source: newRow.source.toUpperCase(),
        agentOriginal: newRow.agentOriginal || null,
        codNumeric: newRow.codNumeric || null,
      });
      toast.success("Mapare creată · backfill rulat");
      setNewRow(EMPTY_CREATE);
      setShowNew(false);
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare la creare");
    } finally {
      setCreating(false);
    }
  }

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const res = await uploadMapping(file);
      toast.success(
        `Ingest OK: ${res.summary.mappingsCreated} create, ${res.summary.mappingsUpdated} update · ${res.backfillRowsUpdated} rânduri KA re-mapate`,
      );
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare la upload");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div>
      <div style={headerRow}>
        <h2 style={{ marginTop: 0 }}>Mapare Magazine & Agenți (KA)</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => setShowNew((s) => !s)}
            style={btnPrimary}
            disabled={showNew}
          >
            + Adaugă rând
          </button>
          <label style={btnSecondary}>
            {uploading ? "Se încarcă…" : "Upload .xlsx"}
            <input
              ref={fileRef}
              type="file"
              accept=".xlsx"
              onChange={handleFileChange}
              style={{ display: "none" }}
              disabled={uploading}
            />
          </label>
        </div>
      </div>

      <p style={helpText}>
        Sursa de adevăr pentru KA. Fiecare rând leagă
        <code style={code}> (Sursă, Client Original, Magazin Original)</code> →
        <code style={code}> Cheie Finală (= Magazin canonic)</code> +
        <code style={code}> Agent Unificat</code>. Orice editare rulează
        automat backfill pe <code style={code}>raw_sales</code>.
      </p>

      {showNew && (
        <form onSubmit={handleCreate} style={newForm}>
          <strong>Rând nou</strong>
          <div style={gridForm}>
            <LabeledInput
              label="Sursă"
              value={newRow.source}
              onChange={(v) => setNewRow({ ...newRow, source: v })}
              required
            />
            <LabeledInput
              label="Client Original"
              value={newRow.clientOriginal}
              onChange={(v) => setNewRow({ ...newRow, clientOriginal: v })}
              required
            />
            <LabeledInput
              label="Magazin Original (ship_to)"
              value={newRow.shipToOriginal}
              onChange={(v) => setNewRow({ ...newRow, shipToOriginal: v })}
              required
            />
            <LabeledInput
              label="Cod Numeric"
              value={newRow.codNumeric ?? ""}
              onChange={(v) => setNewRow({ ...newRow, codNumeric: v })}
            />
            <LabeledInput
              label="Agent Original"
              value={newRow.agentOriginal ?? ""}
              onChange={(v) => setNewRow({ ...newRow, agentOriginal: v })}
            />
            <LabeledInput
              label="Cheie Finală (Magazin canonic)"
              value={newRow.cheieFinala}
              onChange={(v) => setNewRow({ ...newRow, cheieFinala: v })}
              required
            />
            <LabeledInput
              label="Agent Unificat"
              value={newRow.agentUnificat}
              onChange={(v) => setNewRow({ ...newRow, agentUnificat: v })}
              required
            />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" disabled={creating} style={btnPrimary}>
              {creating ? "Salvez…" : "Creează"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowNew(false);
                setNewRow(EMPTY_CREATE);
              }}
              style={btnGhost}
            >
              Anulează
            </button>
          </div>
        </form>
      )}

      <div style={toolbar}>
        <div>
          <label style={{ fontSize: 13, marginRight: 8 }}>Sursă:</label>
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value as typeof sourceFilter)}
            style={select}
          >
            <option value="ALL">Toate</option>
            <option value="ADP">ADP</option>
            <option value="SIKA">SIKA</option>
          </select>
        </div>
        {rows.length > 0 && (
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Caută în orice coloană…"
            total={rows.length}
            visible={filtered.length}
          />
        )}
      </div>

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      {loading && rows.length === 0 ? (
        <TableSkeleton rows={8} cols={8} />
      ) : (
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>Sursă</th>
              <th style={th}>Client Original</th>
              <th style={th}>Magazin Original</th>
              <th style={th}>Cod</th>
              <th style={th}>Agent Original</th>
              <th style={th}>Cheie Finală</th>
              <th style={th}>Agent Unificat</th>
              <th style={{ ...th, width: 140 }}>Acțiuni</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => {
              const isEdit = editingId === row.id;
              const v = isEdit ? draft : row;
              const saving = savingId === row.id;
              return (
                <tr key={row.id}>
                  <td style={td}>
                    {isEdit ? (
                      <input
                        value={v.source ?? ""}
                        onChange={(e) => setDraft({ ...draft, source: e.target.value })}
                        style={cellInput}
                      />
                    ) : (
                      row.source
                    )}
                  </td>
                  <td style={td}>
                    {isEdit ? (
                      <input
                        value={v.clientOriginal ?? ""}
                        onChange={(e) =>
                          setDraft({ ...draft, clientOriginal: e.target.value })
                        }
                        style={cellInput}
                      />
                    ) : (
                      row.clientOriginal
                    )}
                  </td>
                  <td style={td}>
                    {isEdit ? (
                      <input
                        value={v.shipToOriginal ?? ""}
                        onChange={(e) =>
                          setDraft({ ...draft, shipToOriginal: e.target.value })
                        }
                        style={cellInput}
                      />
                    ) : (
                      row.shipToOriginal
                    )}
                  </td>
                  <td style={td}>
                    {isEdit ? (
                      <input
                        value={v.codNumeric ?? ""}
                        onChange={(e) =>
                          setDraft({ ...draft, codNumeric: e.target.value })
                        }
                        style={cellInput}
                      />
                    ) : (
                      row.codNumeric ?? ""
                    )}
                  </td>
                  <td style={td}>
                    {isEdit ? (
                      <input
                        value={v.agentOriginal ?? ""}
                        onChange={(e) =>
                          setDraft({ ...draft, agentOriginal: e.target.value })
                        }
                        style={cellInput}
                      />
                    ) : (
                      row.agentOriginal ?? ""
                    )}
                  </td>
                  <td style={td}>
                    {isEdit ? (
                      <input
                        value={v.cheieFinala ?? ""}
                        onChange={(e) =>
                          setDraft({ ...draft, cheieFinala: e.target.value })
                        }
                        style={cellInput}
                      />
                    ) : (
                      <strong>{row.cheieFinala}</strong>
                    )}
                  </td>
                  <td style={td}>
                    {isEdit ? (
                      <input
                        value={v.agentUnificat ?? ""}
                        onChange={(e) =>
                          setDraft({ ...draft, agentUnificat: e.target.value })
                        }
                        style={cellInput}
                      />
                    ) : (
                      row.agentUnificat
                    )}
                  </td>
                  <td style={td}>
                    {isEdit ? (
                      <>
                        <button
                          onClick={() => saveEdit(row)}
                          style={btnSmallPrimary}
                          disabled={saving}
                        >
                          {saving ? "…" : "Salvează"}
                        </button>
                        <button
                          onClick={cancelEdit}
                          style={btnSmallGhost}
                          disabled={saving}
                        >
                          ✕
                        </button>
                      </>
                    ) : (
                      <>
                        <button onClick={() => startEdit(row)} style={btnSmallGhost}>
                          Editează
                        </button>
                        <button
                          onClick={() => handleDelete(row)}
                          style={btnSmallDanger}
                        >
                          Șterge
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && !loading && (
              <tr>
                <td style={{ ...td, textAlign: "center", color: "#888" }} colSpan={8}>
                  Nicio mapare. Încarcă fișierul Raf sau adaugă un rând.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

function LabeledInput({
  label,
  value,
  onChange,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
}) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12 }}>
      <span style={{ color: "#555" }}>
        {label}
        {required ? " *" : ""}
      </span>
      <input
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={input}
      />
    </label>
  );
}

const headerRow: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: 8,
};
const helpText: React.CSSProperties = {
  fontSize: 13,
  color: "var(--muted, #666)",
  marginTop: 0,
  marginBottom: 16,
};
const code: React.CSSProperties = {
  background: "rgba(148,163,184,0.15)",
  padding: "1px 4px",
  borderRadius: 3,
  fontSize: 12,
};
const toolbar: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: 12,
  marginTop: 12,
  marginBottom: 8,
};
const select: React.CSSProperties = {
  padding: 6,
  fontSize: 13,
  border: "1px solid #ccc",
  borderRadius: 4,
};
const newForm: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 12,
  padding: 16,
  border: "1px solid var(--border, #ccc)",
  borderRadius: 6,
  marginBottom: 16,
  background: "var(--card, #f9fafb)",
};
const gridForm: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  gap: 10,
};
const input: React.CSSProperties = {
  padding: 8,
  fontSize: 13,
  border: "1px solid #ccc",
  borderRadius: 4,
};
const cellInput: React.CSSProperties = {
  width: "100%",
  padding: 4,
  fontSize: 12,
  border: "1px solid #2563eb",
  borderRadius: 3,
};
const btnPrimary: React.CSSProperties = {
  padding: "8px 16px",
  fontSize: 14,
  cursor: "pointer",
  background: "#2563eb",
  color: "#fff",
  border: "none",
  borderRadius: 4,
};
const btnSecondary: React.CSSProperties = {
  padding: "8px 16px",
  fontSize: 14,
  cursor: "pointer",
  background: "transparent",
  color: "#2563eb",
  border: "1px solid #2563eb",
  borderRadius: 4,
  display: "inline-block",
};
const btnGhost: React.CSSProperties = {
  padding: "8px 16px",
  fontSize: 14,
  cursor: "pointer",
  background: "transparent",
  border: "1px solid #ccc",
  borderRadius: 4,
};
const btnSmallPrimary: React.CSSProperties = {
  padding: "3px 8px",
  fontSize: 12,
  cursor: "pointer",
  background: "#2563eb",
  color: "#fff",
  border: "none",
  borderRadius: 3,
  marginRight: 4,
};
const btnSmallGhost: React.CSSProperties = {
  padding: "3px 8px",
  fontSize: 12,
  cursor: "pointer",
  background: "transparent",
  border: "1px solid #ccc",
  borderRadius: 3,
  marginRight: 4,
};
const btnSmallDanger: React.CSSProperties = {
  padding: "3px 8px",
  fontSize: 12,
  cursor: "pointer",
  background: "transparent",
  color: "#b00020",
  border: "1px solid #b00020",
  borderRadius: 3,
};
const table: React.CSSProperties = { borderCollapse: "collapse", width: "100%" };
const th: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 10px",
  borderBottom: "2px solid #333",
  fontSize: 12,
};
const td: React.CSSProperties = {
  padding: "6px 10px",
  borderBottom: "1px solid #eee",
  fontSize: 12,
  verticalAlign: "top",
};

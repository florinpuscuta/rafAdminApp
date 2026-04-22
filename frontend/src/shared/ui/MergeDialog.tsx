import { useEffect, useMemo, useRef, useState } from "react";

export interface MergeItem {
  id: string;
  label: string;
}

interface Props<T extends MergeItem> {
  title: string;
  items: T[];
  onClose: () => void;
  onMerge: (primaryId: string, duplicateIds: string[]) => Promise<void>;
  /** Entity-type text for the confirm sentence (ex: "magazine", "agenți"). */
  entityNoun: string;
}

export function MergeDialog<T extends MergeItem>({
  title,
  items,
  onClose,
  onMerge,
  entityNoun,
}: Props<T>) {
  const [primaryId, setPrimaryId] = useState<string>("");
  const [duplicateIds, setDuplicateIds] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const titleId = useRef(`mg-title-${Math.random().toString(36).slice(2, 9)}`).current;
  const filterRef = useRef<HTMLInputElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  // Focus-management: salvăm focus-ul anterior, focusăm input-ul de filtru la
  // deschidere, restaurăm focus-ul la close + Escape key = close.
  useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    filterRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previousFocusRef.current?.focus?.();
    };
  }, [onClose]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) => i.label.toLowerCase().includes(q));
  }, [items, filter]);

  function toggleDup(id: string) {
    setDuplicateIds((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleSubmit() {
    setError(null);
    if (!primaryId) return setError("Selectează entitatea principală.");
    const dups = Array.from(duplicateIds).filter((d) => d !== primaryId);
    if (dups.length === 0) return setError("Selectează cel puțin un duplicat.");
    setSubmitting(true);
    try {
      await onMerge(primaryId, dups);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Eroare");
    } finally {
      setSubmitting(false);
    }
  }

  const dupCount = Array.from(duplicateIds).filter((d) => d !== primaryId).length;

  return (
    <div style={styles.backdrop} onClick={onClose} role="presentation">
      <div
        style={styles.dialog}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <h3 id={titleId} style={styles.title}>{title}</h3>
        <p style={styles.hint}>
          Alege entitatea <strong>principală</strong> (cea care rămâne) și bifează{" "}
          <strong>duplicatele</strong> care vor fi consolidate în ea.
          Toate alias-urile și vânzările se transferă automat.
        </p>

        <input
          ref={filterRef}
          placeholder="Filtrează…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={styles.filter}
          aria-label="Filtrează lista"
        />

        <div style={styles.list}>
          {filtered.map((it) => {
            const isPrimary = primaryId === it.id;
            const isDup = duplicateIds.has(it.id);
            return (
              <div key={it.id} style={styles.row}>
                <label style={styles.labelRadio}>
                  <input
                    type="radio"
                    name="primary"
                    checked={isPrimary}
                    onChange={() => {
                      setPrimaryId(it.id);
                      setDuplicateIds((s) => {
                        const n = new Set(s);
                        n.delete(it.id);
                        return n;
                      });
                    }}
                  />
                  Principal
                </label>
                <label style={styles.labelCheck}>
                  <input
                    type="checkbox"
                    checked={isDup && !isPrimary}
                    disabled={isPrimary}
                    onChange={() => toggleDup(it.id)}
                  />
                  Duplicat
                </label>
                <span style={styles.name}>{it.label}</span>
              </div>
            );
          })}
          {filtered.length === 0 && <div style={styles.empty}>Niciun rezultat.</div>}
        </div>

        {error && <p style={styles.error}>{error}</p>}

        <div style={styles.actions}>
          <button onClick={onClose} style={styles.btnCancel}>Anulează</button>
          <button
            onClick={handleSubmit}
            disabled={submitting || !primaryId || dupCount === 0}
            style={styles.btnDanger}
            title={`Consolidează ${dupCount} ${entityNoun} în cel principal`}
          >
            {submitting ? "Consolidare…" : `Consolidează (${dupCount})`}
          </button>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.5)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 10001,
  },
  dialog: {
    background: "var(--bg, #fff)",
    color: "var(--fg, #111)",
    padding: 20,
    borderRadius: 8,
    maxWidth: 620,
    width: "92%",
    maxHeight: "85vh",
    display: "flex",
    flexDirection: "column",
    boxShadow: "0 10px 40px rgba(0,0,0,0.2)",
  },
  title: { margin: "0 0 8px", fontSize: 17 },
  hint: { margin: "0 0 12px", fontSize: 13, lineHeight: 1.5, color: "var(--fg-muted, #555)" },
  filter: {
    padding: 8, fontSize: 14, border: "1px solid var(--border, #ccc)",
    borderRadius: 4, marginBottom: 10,
  },
  list: {
    flex: 1,
    overflowY: "auto",
    border: "1px solid var(--border, #eee)",
    borderRadius: 4,
    padding: 4,
    marginBottom: 12,
  },
  row: {
    display: "grid",
    gridTemplateColumns: "auto auto 1fr",
    gap: 12,
    alignItems: "center",
    padding: "6px 10px",
    borderBottom: "1px solid var(--border, #f0f0f0)",
    fontSize: 13,
  },
  labelRadio: { display: "flex", alignItems: "center", gap: 4, fontSize: 12 },
  labelCheck: { display: "flex", alignItems: "center", gap: 4, fontSize: 12 },
  name: { fontWeight: 500 },
  empty: { padding: 12, color: "var(--fg-muted, #888)", fontSize: 13 },
  error: { color: "#b00020", margin: "0 0 8px", fontSize: 13 },
  actions: { display: "flex", justifyContent: "flex-end", gap: 8 },
  btnCancel: {
    padding: "8px 16px", fontSize: 14, cursor: "pointer",
    background: "#fff", border: "1px solid #d0d0d0", borderRadius: 4,
  },
  btnDanger: {
    padding: "8px 16px", fontSize: 14, cursor: "pointer",
    background: "#b00020", color: "#fff", border: "none", borderRadius: 4,
  },
};

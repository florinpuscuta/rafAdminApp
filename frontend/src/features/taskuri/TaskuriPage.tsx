/**
 * Pagina Taskuri — CRUD complet pe /api/taskuri.
 *
 * Features:
 *  - Tabel cu Titlu, Status, Prioritate, Due, Asignați
 *  - Filtre: status (ALL/TODO/IN_PROGRESS/DONE), agent, search
 *  - Buton "+ Task nou" → form inline (pattern consistent cu MappingsPage)
 *  - Edit inline status via dropdown (PATCH optimistic)
 *  - Culori status/priority via CSS vars (light theme)
 *  - Delete cu confirm
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import { listAgents } from "../agents/api";
import type { Agent } from "../agents/types";
import { ApiError } from "../../shared/api";
import { useConfirm } from "../../shared/ui/ConfirmDialog";
import { norm, SearchInput } from "../../shared/ui/SearchInput";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import {
  createTask,
  deleteTask,
  listTaskuri,
  updateTask,
} from "./api";
import type {
  TaskCreatePayload,
  TaskItem,
  TaskPriority,
  TaskStatus,
} from "./types";

type StatusFilter = "ALL" | TaskStatus;

const STATUS_LABELS: Record<TaskStatus, string> = {
  TODO: "De făcut",
  IN_PROGRESS: "În lucru",
  DONE: "Finalizat",
};

const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Scăzută",
  medium: "Medie",
  high: "Ridicată",
};

const STATUS_COLORS: Record<TaskStatus, { bg: string; fg: string }> = {
  TODO: { bg: "rgba(148,163,184,0.18)", fg: "#475569" },
  IN_PROGRESS: { bg: "rgba(59,130,246,0.15)", fg: "#1d4ed8" },
  DONE: { bg: "rgba(34,197,94,0.15)", fg: "#15803d" },
};

const PRIORITY_COLORS: Record<TaskPriority, { bg: string; fg: string }> = {
  low: { bg: "rgba(148,163,184,0.18)", fg: "#475569" },
  medium: { bg: "rgba(234,179,8,0.18)", fg: "#a16207" },
  high: { bg: "rgba(220,38,38,0.15)", fg: "#b91c1c" },
};

const EMPTY_CREATE: TaskCreatePayload = {
  title: "",
  description: "",
  status: "TODO",
  priority: "medium",
  dueDate: null,
  assigneeAgentIds: [],
};

export default function TaskuriPage() {
  const toast = useToast();
  const confirm = useConfirm();

  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const [agentFilter, setAgentFilter] = useState<string>("");
  const [search, setSearch] = useState("");

  const [showNew, setShowNew] = useState(false);
  const [newRow, setNewRow] = useState<TaskCreatePayload>(EMPTY_CREATE);
  const [creating, setCreating] = useState(false);

  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listTaskuri({
        status: statusFilter === "ALL" ? undefined : statusFilter,
        agentId: agentFilter || undefined,
      });
      setTasks(res.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, agentFilter]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Agenții se încarcă separat (nu depind de filtre).
  useEffect(() => {
    listAgents()
      .then((list) => setAgents(list.filter((a) => a.active)))
      .catch(() => {
        // Lipsa agenților nu blochează pagina — doar form-ul "+ Task nou"
        // va avea select gol.
      });
  }, []);

  const filtered = useMemo(() => {
    const q = norm(search);
    if (!q) return tasks;
    return tasks.filter((t) =>
      norm(
        [
          t.title,
          t.description,
          ...t.assignees.map((a) => a.agentName),
        ].join(" "),
      ).includes(q),
    );
  }, [tasks, search]);

  async function handleStatusChange(task: TaskItem, next: TaskStatus) {
    if (task.status === next) return;
    setUpdatingId(task.id);
    // Optimistic update.
    const snapshot = tasks;
    setTasks((prev) =>
      prev.map((t) => (t.id === task.id ? { ...t, status: next } : t)),
    );
    try {
      await updateTask(task.id, { status: next });
      toast.success(`Status actualizat: ${STATUS_LABELS[next]}`);
      await refresh();
    } catch (err) {
      setTasks(snapshot);
      toast.error(err instanceof ApiError ? err.message : "Eroare la salvare");
    } finally {
      setUpdatingId(null);
    }
  }

  async function handleDelete(task: TaskItem) {
    const ok = await confirm({
      title: "Șterge task",
      message: `Ștergi task-ul "${task.title}"? Acțiunea nu poate fi anulată.`,
      confirmLabel: "Șterge",
      danger: true,
    });
    if (!ok) return;
    const snapshot = tasks;
    setTasks((prev) => prev.filter((t) => t.id !== task.id));
    try {
      await deleteTask(task.id);
      toast.success("Task șters");
    } catch (err) {
      setTasks(snapshot);
      toast.error(err instanceof ApiError ? err.message : "Eroare la ștergere");
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!newRow.title.trim()) {
      toast.error("Titlul e obligatoriu");
      return;
    }
    setCreating(true);
    try {
      await createTask({
        ...newRow,
        title: newRow.title.trim(),
        description: (newRow.description ?? "").trim(),
        dueDate: newRow.dueDate || null,
        assigneeAgentIds: newRow.assigneeAgentIds ?? [],
      });
      toast.success("Task creat");
      setNewRow(EMPTY_CREATE);
      setShowNew(false);
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare la creare");
    } finally {
      setCreating(false);
    }
  }

  function toggleAssignee(agentId: string) {
    setNewRow((prev) => {
      const cur = prev.assigneeAgentIds ?? [];
      const next = cur.includes(agentId)
        ? cur.filter((id) => id !== agentId)
        : [...cur, agentId];
      return { ...prev, assigneeAgentIds: next };
    });
  }

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>Taskuri</h1>
        <button
          onClick={() => setShowNew((s) => !s)}
          style={styles.btnPrimary}
          disabled={showNew}
        >
          + Task nou
        </button>
      </div>

      {showNew && (
        <form onSubmit={handleCreate} style={styles.newForm}>
          <strong style={{ color: "var(--text)" }}>Task nou</strong>
          <div style={styles.gridForm}>
            <label style={styles.fieldLabel}>
              <span>Titlu *</span>
              <input
                required
                value={newRow.title}
                onChange={(e) =>
                  setNewRow({ ...newRow, title: e.target.value })
                }
                style={styles.input}
              />
            </label>
            <label style={styles.fieldLabel}>
              <span>Due date</span>
              <input
                type="date"
                value={newRow.dueDate ?? ""}
                onChange={(e) =>
                  setNewRow({ ...newRow, dueDate: e.target.value || null })
                }
                style={styles.input}
              />
            </label>
            <label style={styles.fieldLabel}>
              <span>Status</span>
              <select
                value={newRow.status}
                onChange={(e) =>
                  setNewRow({
                    ...newRow,
                    status: e.target.value as TaskStatus,
                  })
                }
                style={styles.input}
              >
                <option value="TODO">{STATUS_LABELS.TODO}</option>
                <option value="IN_PROGRESS">
                  {STATUS_LABELS.IN_PROGRESS}
                </option>
                <option value="DONE">{STATUS_LABELS.DONE}</option>
              </select>
            </label>
            <label style={styles.fieldLabel}>
              <span>Prioritate</span>
              <select
                value={newRow.priority}
                onChange={(e) =>
                  setNewRow({
                    ...newRow,
                    priority: e.target.value as TaskPriority,
                  })
                }
                style={styles.input}
              >
                <option value="low">{PRIORITY_LABELS.low}</option>
                <option value="medium">{PRIORITY_LABELS.medium}</option>
                <option value="high">{PRIORITY_LABELS.high}</option>
              </select>
            </label>
          </div>
          <label style={{ ...styles.fieldLabel, flex: 1 }}>
            <span>Descriere</span>
            <textarea
              value={newRow.description ?? ""}
              onChange={(e) =>
                setNewRow({ ...newRow, description: e.target.value })
              }
              style={{ ...styles.input, minHeight: 60, resize: "vertical" }}
            />
          </label>

          {agents.length > 0 && (
            <div>
              <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 6 }}>
                Asignați
              </div>
              <div style={styles.agentChips}>
                {agents.map((a) => {
                  const selected =
                    newRow.assigneeAgentIds?.includes(a.id) ?? false;
                  return (
                    <button
                      key={a.id}
                      type="button"
                      onClick={() => toggleAssignee(a.id)}
                      style={{
                        ...styles.agentChip,
                        ...(selected ? styles.agentChipSelected : null),
                      }}
                    >
                      {a.fullName}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" disabled={creating} style={styles.btnPrimary}>
              {creating ? "Salvez…" : "Creează"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowNew(false);
                setNewRow(EMPTY_CREATE);
              }}
              style={styles.btnGhost}
            >
              Anulează
            </button>
          </div>
        </form>
      )}

      <div style={styles.toolbar}>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <label style={styles.filterLabel}>
            Status:
            <select
              value={statusFilter}
              onChange={(e) =>
                setStatusFilter(e.target.value as StatusFilter)
              }
              style={styles.select}
            >
              <option value="ALL">Toate</option>
              <option value="TODO">{STATUS_LABELS.TODO}</option>
              <option value="IN_PROGRESS">{STATUS_LABELS.IN_PROGRESS}</option>
              <option value="DONE">{STATUS_LABELS.DONE}</option>
            </select>
          </label>
          <label style={styles.filterLabel}>
            Agent:
            <select
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              style={styles.select}
            >
              <option value="">Toți</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.fullName}
                </option>
              ))}
            </select>
          </label>
        </div>
        {tasks.length > 0 && (
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Caută în titlu / descriere / agent…"
            total={tasks.length}
            visible={filtered.length}
          />
        )}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading && tasks.length === 0 ? (
        <TableSkeleton rows={6} cols={6} />
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Titlu</th>
              <th style={{ ...styles.th, width: 140 }}>Status</th>
              <th style={{ ...styles.th, width: 110 }}>Prioritate</th>
              <th style={{ ...styles.th, width: 120 }}>Due</th>
              <th style={styles.th}>Asignați</th>
              <th style={{ ...styles.th, width: 90 }}>Acțiuni</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((task) => {
              const sCol = STATUS_COLORS[task.status];
              const pCol = PRIORITY_COLORS[task.priority];
              const overdue =
                task.dueDate &&
                task.status !== "DONE" &&
                new Date(task.dueDate) < new Date(new Date().toDateString());
              return (
                <tr key={task.id}>
                  <td style={styles.td}>
                    <div style={{ fontWeight: 600, color: "var(--text)" }}>
                      {task.title}
                    </div>
                    {task.description && (
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--muted)",
                          marginTop: 2,
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {task.description}
                      </div>
                    )}
                  </td>
                  <td style={styles.td}>
                    <select
                      value={task.status}
                      onChange={(e) =>
                        handleStatusChange(task, e.target.value as TaskStatus)
                      }
                      disabled={updatingId === task.id}
                      style={{
                        ...styles.statusSelect,
                        background: sCol.bg,
                        color: sCol.fg,
                        borderColor: sCol.bg,
                      }}
                    >
                      <option value="TODO">{STATUS_LABELS.TODO}</option>
                      <option value="IN_PROGRESS">
                        {STATUS_LABELS.IN_PROGRESS}
                      </option>
                      <option value="DONE">{STATUS_LABELS.DONE}</option>
                    </select>
                  </td>
                  <td style={styles.td}>
                    <span
                      style={{
                        ...styles.pill,
                        background: pCol.bg,
                        color: pCol.fg,
                      }}
                    >
                      {PRIORITY_LABELS[task.priority]}
                    </span>
                  </td>
                  <td style={styles.td}>
                    {task.dueDate ? (
                      <span
                        style={{
                          color: overdue ? "#b91c1c" : "var(--text)",
                          fontWeight: overdue ? 600 : 400,
                        }}
                      >
                        {formatDate(task.dueDate)}
                      </span>
                    ) : (
                      <span style={{ color: "var(--muted)" }}>—</span>
                    )}
                  </td>
                  <td style={styles.td}>
                    {task.assignees.length === 0 ? (
                      <span style={{ color: "var(--muted)" }}>—</span>
                    ) : (
                      <div style={styles.assigneeList}>
                        {task.assignees.map((a) => (
                          <span key={a.agentId} style={styles.assigneeChip}>
                            {a.agentName}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td style={styles.td}>
                    <button
                      onClick={() => handleDelete(task)}
                      style={styles.btnSmallDanger}
                    >
                      Șterge
                    </button>
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && !loading && (
              <tr>
                <td
                  colSpan={6}
                  style={{
                    ...styles.td,
                    textAlign: "center",
                    color: "var(--muted)",
                    padding: "24px 10px",
                  }}
                >
                  {tasks.length === 0
                    ? "Niciun task încă. Adaugă unul cu „+ Task nou”."
                    : "Niciun task nu corespunde filtrelor."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

function formatDate(iso: string): string {
  // ISO "2026-04-22" → "22 apr 2026" (ro-RO short).
  try {
    return new Date(iso).toLocaleDateString("ro-RO", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

const styles: Record<string, React.CSSProperties> = {
  page: { padding: "4px 4px 12px", color: "var(--text)" },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
    marginBottom: 12,
    flexWrap: "wrap",
  },
  title: {
    margin: 0,
    fontSize: 17,
    fontWeight: 600,
    color: "var(--text)",
    letterSpacing: -0.2,
  },
  newForm: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
    padding: 16,
    border: "1px solid var(--border)",
    borderRadius: 8,
    marginBottom: 16,
    background: "var(--card)",
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  },
  gridForm: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: 10,
  },
  fieldLabel: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    fontSize: 12,
    color: "var(--muted)",
  },
  input: {
    padding: "7px 9px",
    fontSize: 13,
    border: "1px solid var(--border)",
    borderRadius: 4,
    background: "var(--bg)",
    color: "var(--text)",
    fontFamily: "inherit",
  },
  agentChips: {
    display: "flex",
    flexWrap: "wrap",
    gap: 6,
  },
  agentChip: {
    padding: "4px 10px",
    fontSize: 12,
    border: "1px solid var(--border)",
    borderRadius: 999,
    background: "var(--bg)",
    color: "var(--text)",
    cursor: "pointer",
  },
  agentChipSelected: {
    background: "rgba(59,130,246,0.15)",
    color: "#1d4ed8",
    borderColor: "rgba(59,130,246,0.5)",
    fontWeight: 600,
  },
  toolbar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
    marginTop: 4,
    marginBottom: 10,
    flexWrap: "wrap",
  },
  filterLabel: {
    fontSize: 13,
    color: "var(--muted)",
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  select: {
    padding: "6px 8px",
    fontSize: 13,
    border: "1px solid var(--border)",
    borderRadius: 4,
    background: "var(--bg)",
    color: "var(--text)",
  },
  statusSelect: {
    padding: "4px 8px",
    fontSize: 12,
    fontWeight: 600,
    border: "1px solid",
    borderRadius: 999,
    cursor: "pointer",
    appearance: "none",
    paddingRight: 22,
    backgroundImage:
      "url(\"data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' width='8' height='6' viewBox='0 0 8 6'%3e%3cpath fill='currentColor' d='M4 6L0 0h8z'/%3e%3c/svg%3e\")",
    backgroundRepeat: "no-repeat",
    backgroundPosition: "right 8px center",
  },
  pill: {
    display: "inline-block",
    padding: "3px 10px",
    fontSize: 11,
    fontWeight: 600,
    borderRadius: 999,
    textTransform: "capitalize",
  },
  assigneeList: {
    display: "flex",
    flexWrap: "wrap",
    gap: 4,
  },
  assigneeChip: {
    padding: "2px 8px",
    fontSize: 11,
    background: "rgba(148,163,184,0.15)",
    color: "var(--text)",
    borderRadius: 999,
    whiteSpace: "nowrap",
  },
  table: {
    borderCollapse: "collapse",
    width: "100%",
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    overflow: "hidden",
  },
  th: {
    textAlign: "left",
    padding: "10px 12px",
    borderBottom: "1px solid var(--border)",
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: 0.4,
    color: "var(--muted)",
    background: "var(--bg-elevated, var(--bg))",
  },
  td: {
    padding: "10px 12px",
    borderBottom: "1px solid var(--border)",
    fontSize: 13,
    verticalAlign: "top",
    color: "var(--text)",
  },
  btnPrimary: {
    padding: "7px 14px",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    background: "var(--accent, #2563eb)",
    color: "#fff",
    border: "none",
    borderRadius: 6,
  },
  btnGhost: {
    padding: "7px 14px",
    fontSize: 13,
    cursor: "pointer",
    background: "transparent",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 6,
  },
  btnSmallDanger: {
    padding: "4px 10px",
    fontSize: 12,
    cursor: "pointer",
    background: "transparent",
    color: "#b91c1c",
    border: "1px solid rgba(220,38,38,0.4)",
    borderRadius: 4,
  },
  error: {
    padding: "8px 12px",
    background: "rgba(220,38,38,0.08)",
    color: "#b91c1c",
    borderRadius: 6,
    fontSize: 13,
    marginBottom: 10,
  },
};

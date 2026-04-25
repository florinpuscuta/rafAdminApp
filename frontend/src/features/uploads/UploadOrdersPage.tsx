import { useEffect, useRef, useState, type ChangeEvent } from "react";

import { ApiError, getActiveOrgId, getToken } from "../../shared/api";

/**
 * Upload comenzi open (ADP radComenzi sau Sika comenzi).
 *
 * Flow:
 *   POST /api/orders/import/async?source=adp|sika&reportDate=YYYY-MM-DD → jobId
 *   poll 1s GET /api/orders/import/jobs/{id} până status=done|error
 *
 * Snapshot cumulative per (source, reportDate): re-upload aceeași zi =
 * înlocuiește doar acea zi; celelalte zile sunt intacte (istoric păstrat).
 */

type JobStage = {
  key: string;
  label: string;
  progress: number;
  done: boolean;
};

type OrdersResult = {
  inserted: number;
  skipped: number;
  deletedBeforeInsert: number;
  source: string;
  reportDate: string;
  unmappedClients: number;
  unmappedProducts: number;
  errors: string[];
};

type OrdersJobStatus = {
  id: string;
  status: "pending" | "running" | "done" | "error";
  stages: JobStage[];
  currentStage: string | null;
  overallProgress: number;
  result: OrdersResult | null;
  error: string | null;
  errorCode: string | null;
};

interface UploadOrdersPageProps {
  source: "adp" | "sika";
  title: string;
  subtitle: string;
}

function apiBase(): string {
  return window.location.origin.includes("localhost")
    ? (import.meta.env.VITE_API_URL ?? "http://localhost:8000")
    : "";
}

function uploadWithProgress(
  url: string,
  file: File,
  onProgress: (pct: number) => void,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    const activeOrg = getActiveOrgId();
    if (activeOrg) xhr.setRequestHeader("X-Active-Org-Id", activeOrg);
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const body = xhr.response as { jobId?: string; job_id?: string } | null;
        const id = body?.jobId ?? body?.job_id;
        if (id) resolve(id);
        else reject(new ApiError(xhr.status, "Răspuns invalid de la server"));
      } else {
        let msg = xhr.statusText || "Eroare upload";
        const body = xhr.response as { detail?: unknown } | null;
        const detail = body?.detail;
        if (typeof detail === "string") msg = detail;
        else if (detail && typeof detail === "object") {
          const d = detail as { message?: string };
          if (d.message) msg = d.message;
        }
        reject(new ApiError(xhr.status, msg));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Eroare de rețea"));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

async function fetchJob(jobId: string): Promise<OrdersJobStatus> {
  const token = getToken();
  const activeOrg = getActiveOrgId();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (activeOrg) headers["X-Active-Org-Id"] = activeOrg;
  const res = await fetch(`${apiBase()}/api/orders/import/jobs/${jobId}`, {
    headers,
  });
  if (!res.ok) throw new ApiError(res.status, `Job query failed (${res.status})`);
  const raw = (await res.json()) as Record<string, unknown>;
  return {
    id: String(raw.id),
    status: raw.status as OrdersJobStatus["status"],
    stages: ((raw.stages as unknown[]) ?? []).map((s) => {
      const obj = s as Record<string, unknown>;
      return {
        key: String(obj.key),
        label: String(obj.label),
        progress: Number(obj.progress ?? 0),
        done: Boolean(obj.done),
      };
    }),
    currentStage: (raw.currentStage as string | null) ?? (raw.current_stage as string | null) ?? null,
    overallProgress: Number(raw.overallProgress ?? raw.overall_progress ?? 0),
    result: raw.result ? (raw.result as OrdersResult) : null,
    error: (raw.error as string | null) ?? null,
    errorCode: (raw.errorCode as string | null) ?? (raw.error_code as string | null) ?? null,
  };
}

function todayYmd(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

export default function UploadOrdersPage({ source, title, subtitle }: UploadOrdersPageProps) {
  const [file, setFile] = useState<File | null>(null);
  const [reportDate, setReportDate] = useState<string>(todayYmd());
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [jobStatus, setJobStatus] = useState<OrdersJobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current !== null) window.clearInterval(pollRef.current);
    };
  }, []);

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setJobStatus(null);
    setError(null);
    setUploadPct(null);
  }

  function reset() {
    if (pollRef.current !== null) window.clearInterval(pollRef.current);
    pollRef.current = null;
    setFile(null);
    setJobStatus(null);
    setError(null);
    setUploadPct(null);
    setReportDate(todayYmd());
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function onUpload() {
    if (!file) return;
    setJobStatus(null);
    setError(null);
    setUploadPct(0);
    try {
      const params = new URLSearchParams();
      params.set("source", source);
      params.set("reportDate", reportDate);
      const url = `${apiBase()}/api/orders/import/async?${params.toString()}`;
      const jobId = await uploadWithProgress(url, file, setUploadPct);
      setUploadPct(100);

      setJobStatus({
        id: jobId,
        status: "pending",
        stages: [],
        currentStage: null,
        overallProgress: 0,
        result: null,
        error: null,
        errorCode: null,
      });
      if (pollRef.current !== null) window.clearInterval(pollRef.current);
      pollRef.current = window.setInterval(async () => {
        try {
          const st = await fetchJob(jobId);
          setJobStatus(st);
          if (st.status === "done" || st.status === "error") {
            if (pollRef.current !== null) {
              window.clearInterval(pollRef.current);
              pollRef.current = null;
            }
          }
        } catch (e) {
          if (pollRef.current !== null) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
          setError(e instanceof Error ? e.message : "Eroare la verificarea job-ului");
          setJobStatus(null);
        }
      }, 1000);
    } catch (e) {
      setUploadPct(null);
      if (e instanceof ApiError) setError(e.message);
      else if (e instanceof Error) setError(e.message);
      else setError("Eroare necunoscută la upload");
    }
  }

  const isUploading = uploadPct !== null && uploadPct < 100 && !jobStatus;
  const isPolling =
    jobStatus !== null && (jobStatus.status === "pending" || jobStatus.status === "running");
  const isRunning = isUploading || isPolling;
  const isDone = jobStatus?.status === "done";
  const jobError =
    jobStatus?.status === "error" ? jobStatus.error ?? "Eroare la procesare" : null;

  return (
    <div style={styles.page}>
      <div style={styles.sectionTitle}>{title}</div>
      <div style={styles.sectionSubtitle}>{subtitle}</div>

      <div style={styles.card}>
        <label style={styles.fileDrop}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            onChange={onFileChange}
            style={{ display: "none" }}
            disabled={isRunning}
          />
          {file ? (
            <>
              <div style={styles.fileName}>{file.name}</div>
              <div style={styles.fileSize}>{(file.size / (1024 * 1024)).toFixed(1)} MB</div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 28, marginBottom: 8 }}>📦</div>
              <div style={{ fontWeight: 600 }}>Click pentru a selecta fișier Excel</div>
              <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>.xlsx</div>
            </>
          )}
        </label>

        <label style={styles.dateRow}>
          <span style={{ fontWeight: 600, fontSize: 13 }}>Data snapshot</span>
          <input
            type="date"
            value={reportDate}
            onChange={(e) => setReportDate(e.target.value)}
            disabled={isRunning}
            style={styles.dateInput}
          />
          <span style={{ fontSize: 12, color: "var(--muted)" }}>
            Re-upload în aceeași zi înlocuiește doar acel snapshot. Celelalte zile rămân neafectate.
          </span>
        </label>

        <div style={styles.actions}>
          <button
            type="button"
            onClick={onUpload}
            disabled={!file || isRunning || !reportDate}
            style={styles.primaryBtn}
          >
            {isUploading
              ? `Se încarcă fișierul... ${uploadPct ?? 0}%`
              : isPolling
                ? "Se procesează..."
                : "Încarcă comenzile"}
          </button>
          {(file || jobStatus || error) && (
            <button type="button" onClick={reset} disabled={isRunning} style={styles.secondaryBtn}>
              Resetează
            </button>
          )}
        </div>
      </div>

      {error && (
        <div style={styles.errorBox}>
          <strong>Eroare:</strong> {error}
        </div>
      )}

      {jobError && (
        <div style={styles.errorBox}>
          <strong>Job eșuat:</strong> {jobError}
        </div>
      )}

      {isUploading && (
        <div style={styles.progressCard}>
          <div style={styles.progressHeader}>
            <strong>Transfer fișier → server</strong>
            <span style={{ color: "var(--cyan)", fontWeight: 700 }}>{uploadPct ?? 0}%</span>
          </div>
          <OverallBar value={uploadPct ?? 0} />
        </div>
      )}

      {jobStatus && jobStatus.stages.length > 0 && <ProgressPanel status={jobStatus} />}

      {isDone && jobStatus.result && <ResultPanel result={jobStatus.result} />}
    </div>
  );
}

function ProgressPanel({ status }: { status: OrdersJobStatus }) {
  return (
    <div style={styles.progressCard}>
      <div style={styles.progressHeader}>
        <strong>Progres global</strong>
        <span style={{ color: "var(--cyan)", fontWeight: 700 }}>
          {status.overallProgress.toFixed(0)}%
        </span>
      </div>
      <OverallBar value={status.overallProgress} />
      <div style={styles.stagesList}>
        {status.stages.map((s) => (
          <StageRow
            key={s.key}
            stage={s}
            active={status.currentStage === s.key && !s.done}
          />
        ))}
      </div>
    </div>
  );
}

function OverallBar({ value }: { value: number }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div style={styles.barOuter}>
      <div style={{ ...styles.barInnerOverall, width: `${clamped}%` }} />
    </div>
  );
}

function StageRow({ stage, active }: { stage: JobStage; active: boolean }) {
  const icon = stage.done ? "✓" : active ? "●" : "○";
  const iconColor = stage.done ? "var(--green)" : active ? "var(--cyan)" : "var(--muted)";
  return (
    <div style={styles.stageRow}>
      <div style={styles.stageHeader}>
        <span style={{ color: iconColor, fontSize: 14, width: 14 }}>{icon}</span>
        <span
          style={{
            flex: 1,
            color: stage.done ? "var(--text)" : active ? "var(--cyan)" : "var(--muted)",
            fontSize: 13,
            fontWeight: active ? 600 : 500,
          }}
        >
          {stage.label}
        </span>
        <span style={{ fontSize: 11, color: "var(--muted)", minWidth: 40, textAlign: "right" }}>
          {stage.progress.toFixed(0)}%
        </span>
      </div>
      <div style={styles.barOuterSmall}>
        <div
          style={{
            ...styles.barInnerStage,
            width: `${Math.max(0, Math.min(100, stage.progress))}%`,
            background: stage.done ? "var(--green)" : active ? "var(--cyan)" : "var(--border)",
          }}
        />
      </div>
    </div>
  );
}

function ResultPanel({ result }: { result: OrdersResult }) {
  return (
    <div style={styles.resultBox}>
      <div style={styles.resultTitle}>✓ Import finalizat</div>

      <div style={styles.kpiGrid}>
        <Kpi label="Rânduri inserate" value={result.inserted} variant="success" />
        <Kpi label="Șterse anterior (aceeași zi)" value={result.deletedBeforeInsert} variant="muted" />
        <Kpi label="Erori" value={result.skipped} variant={result.skipped > 0 ? "warning" : "muted"} />
      </div>

      <div style={styles.subSection}>
        <div style={styles.subTitle}>Snapshot</div>
        <div style={{ fontSize: 13, color: "var(--text)" }}>
          Sursă: <strong>{result.source.toUpperCase()}</strong> · Data: <strong>{result.reportDate}</strong>
        </div>
      </div>

      <div style={styles.subSection}>
        <div style={styles.subTitle}>Rezolvare canonicals la import</div>
        <div style={styles.kpiGrid}>
          <Kpi
            label="Magazine nemapate"
            value={result.unmappedClients}
            variant={result.unmappedClients > 0 ? "warning" : "success"}
          />
          <Kpi
            label="Produse nemapate"
            value={result.unmappedProducts}
            variant={result.unmappedProducts > 0 ? "warning" : "success"}
          />
        </div>
      </div>

      {result.errors.length > 0 && (
        <div style={styles.subSection}>
          <div style={styles.subTitle}>Erori parsare ({result.errors.length} afișate)</div>
          <ul style={styles.errorList}>
            {result.errors.slice(0, 10).map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Kpi({
  label,
  value,
  variant,
}: {
  label: string;
  value: number;
  variant: "success" | "warning" | "muted";
}) {
  const color =
    variant === "success"
      ? "var(--green)"
      : variant === "warning"
        ? "var(--orange)"
        : "var(--text)";
  return (
    <div style={styles.kpi}>
      <div style={styles.kpiLabel}>{label}</div>
      <div style={{ ...styles.kpiValue, color }}>
        {new Intl.NumberFormat("ro-RO").format(value)}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: 16, maxWidth: 900 },
  sectionTitle: { fontSize: 20, fontWeight: 700, color: "var(--text)" },
  sectionSubtitle: {
    fontSize: 13,
    color: "var(--muted)",
    lineHeight: 1.5,
    marginTop: -8,
  },
  card: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: 20,
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  fileDrop: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "36px 20px",
    border: "2px dashed var(--border)",
    borderRadius: 10,
    cursor: "pointer",
    background: "rgba(34,211,238,0.03)",
    minHeight: 130,
  },
  fileName: {
    fontSize: 14,
    fontWeight: 600,
    color: "var(--cyan)",
    wordBreak: "break-all",
    textAlign: "center",
  },
  fileSize: { fontSize: 12, color: "var(--muted)", marginTop: 4 },
  dateRow: {
    display: "flex",
    gap: 10,
    alignItems: "center",
    flexWrap: "wrap",
    fontSize: 13,
  },
  dateInput: {
    background: "var(--bg)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    padding: "6px 10px",
    fontSize: 13,
  },
  actions: { display: "flex", gap: 10 },
  primaryBtn: {
    background: "linear-gradient(135deg, #22d3ee, #06b6d4)",
    color: "#0a0e17",
    border: "none",
    padding: "10px 24px",
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 700,
    cursor: "pointer",
  },
  secondaryBtn: {
    background: "transparent",
    color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "10px 20px",
    borderRadius: 8,
    fontSize: 13,
    cursor: "pointer",
  },
  progressCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: 18,
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  progressHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "baseline",
    fontSize: 13,
    color: "var(--text)",
  },
  barOuter: {
    height: 10,
    background: "rgba(0,0,0,0.3)",
    border: "1px solid var(--border)",
    borderRadius: 5,
    overflow: "hidden",
  },
  barInnerOverall: {
    height: "100%",
    background: "linear-gradient(90deg, #22d3ee, #06b6d4)",
    transition: "width 0.2s ease",
  },
  stagesList: { display: "flex", flexDirection: "column", gap: 10 },
  stageRow: { display: "flex", flexDirection: "column", gap: 4 },
  stageHeader: { display: "flex", alignItems: "center", gap: 10 },
  barOuterSmall: {
    height: 4,
    background: "rgba(0,0,0,0.3)",
    borderRadius: 2,
    overflow: "hidden",
  },
  barInnerStage: { height: "100%", transition: "width 0.2s ease, background 0.2s ease" },
  errorBox: {
    background: "rgba(239,68,68,0.1)",
    border: "1px solid var(--red)",
    color: "var(--red)",
    padding: 14,
    borderRadius: 8,
    fontSize: 13,
  },
  resultBox: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: 20,
    display: "flex",
    flexDirection: "column",
    gap: 20,
  },
  resultTitle: { fontSize: 16, fontWeight: 700, color: "var(--green)" },
  subSection: { display: "flex", flexDirection: "column", gap: 8 },
  subTitle: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--muted)",
    fontWeight: 600,
  },
  kpiGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: 12,
  },
  kpi: {
    background: "rgba(0,0,0,0.15)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "8px 10px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    minHeight: 58,
  },
  kpiLabel: {
    fontSize: 10,
    color: "var(--muted)",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    marginBottom: 2,
    lineHeight: 1.2,
  },
  kpiValue: { fontSize: 18, fontWeight: 800, lineHeight: 1.15 },
  errorList: {
    background: "rgba(0,0,0,0.25)",
    border: "1px solid var(--border)",
    padding: "8px 12px 8px 28px",
    margin: 0,
    borderRadius: 6,
    fontSize: 12,
    color: "var(--muted)",
    maxHeight: 200,
    overflowY: "auto",
  },
};

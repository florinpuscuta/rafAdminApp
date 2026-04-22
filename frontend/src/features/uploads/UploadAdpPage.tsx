import { useEffect, useRef, useState, type ChangeEvent } from "react";

import { getImportJob } from "../sales/api";
import type {
  ImportJobStatus,
  ImportResponse,
  JobStage,
} from "../sales/types";
import { ApiError, getToken } from "../../shared/api";

/**
 * XHR-based upload care raportează progres pe transfer (fetch() nu suportă
 * upload progress events). Se întoarce job_id-ul la succes sau throw pe
 * eroare (cu ApiError-like shape).
 */
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
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const body = xhr.response as { jobId?: string } | null;
        if (body?.jobId) resolve(body.jobId);
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

interface UploadPageProps {
  source?: "adp" | "sika" | "sika_mtd";
  title?: string;
  subtitle?: string;
}

/**
 * Upload Date Brute (ADP sau SIKA) cu progress tracking pe etape.
 *
 * Flow: POST /api/sales/import/async?source=... → job_id → poll la 1s GET
 * /api/sales/import/jobs/{id} până status=done|error. Între timp afișăm
 * bară globală + per-etapă (parse, alocare, normalize, delete, insert,
 * finalize).
 *
 * `source` izolează deletes: un upload SIKA NU atinge rândurile ADP și
 * invers (scope via import_batches.source).
 */
export default function UploadAdpPage({
  source = "adp",
  title = "Upload Date Brute (ADP)",
  subtitle = "Încarcă Excel-ul cu vânzări Adeplast. Dacă fișierul conține sheet-ul \"Alocare\" (Client | Ship-to | Agent), este procesat automat ca sursă de normalization — creează magazine, agenți și alocări canonice.",
}: UploadPageProps = {}) {
  const [file, setFile] = useState<File | null>(null);
  const [fullReload, setFullReload] = useState(false);
  const [uploadPct, setUploadPct] = useState<number | null>(null); // 0..100 sau null
  const [jobStatus, setJobStatus] = useState<ImportJobStatus | null>(null);
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
    setFullReload(false);
    setUploadPct(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function onUpload() {
    if (!file) return;
    setJobStatus(null);
    setError(null);
    setUploadPct(0);
    try {
      // XHR pentru a avea progres la transferul fișierului (fetch() nu
      // suportă upload progress events). După 202 → job_id, switch la
      // polling pe statusul jobului.
      const params = new URLSearchParams();
      if (fullReload) params.set("fullReload", "true");
      params.set("source", source);
      const qs = `?${params.toString()}`;
      const url = `${window.location.origin.includes("localhost") ? (import.meta.env.VITE_API_URL ?? "http://localhost:8000") : ""}/api/sales/import/async${qs}`;
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
          const status = await getImportJob(jobId);
          setJobStatus(status);
          if (status.status === "done" || status.status === "error") {
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
    jobStatus !== null &&
    (jobStatus.status === "pending" || jobStatus.status === "running");
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
              <div style={styles.fileSize}>
                {(file.size / (1024 * 1024)).toFixed(1)} MB
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 28, marginBottom: 8 }}>📊</div>
              <div style={{ fontWeight: 600 }}>Click pentru a selecta fișier Excel</div>
              <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
                .xlsx · Max ~75 MB
              </div>
            </>
          )}
        </label>

        <label style={styles.checkbox}>
          <input
            type="checkbox"
            checked={fullReload}
            onChange={(e) => setFullReload(e.target.checked)}
            disabled={isRunning}
          />
          <span>
            <strong>Reload complet</strong> — șterge TOATE vânzările existente
            înainte de insert. <br />
            <span style={{ color: "var(--muted)", fontSize: 12 }}>
              Default (nebifat): șterge doar lunile prezente în fișier (smart-incremental).
            </span>
          </span>
        </label>

        <div style={styles.actions}>
          <button
            type="button"
            onClick={onUpload}
            disabled={!file || isRunning}
            style={styles.primaryBtn}
          >
            {isUploading
              ? `Se încarcă fișierul... ${uploadPct ?? 0}%`
              : isPolling
                ? "Se procesează..."
                : "Încarcă datele"}
          </button>
          {(file || jobStatus || error) && (
            <button
              type="button"
              onClick={reset}
              disabled={isRunning}
              style={styles.secondaryBtn}
            >
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
            <span style={{ color: "var(--cyan)", fontWeight: 700 }}>
              {uploadPct ?? 0}%
            </span>
          </div>
          <OverallBar value={uploadPct ?? 0} />
          <div style={{ fontSize: 12, color: "var(--muted)" }}>
            Fișierul se încarcă în backend. Când termină, procesarea pornește
            și vezi progresul pe etape mai jos.
          </div>
        </div>
      )}

      {jobStatus && jobStatus.stages.length > 0 && (
        <ProgressPanel status={jobStatus} />
      )}

      {isDone && jobStatus.result && <ResultPanel result={jobStatus.result} />}
    </div>
  );
}

function ProgressPanel({ status }: { status: ImportJobStatus }) {
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
      <div
        style={{
          ...styles.barInnerOverall,
          width: `${clamped}%`,
        }}
      />
    </div>
  );
}

function StageRow({ stage, active }: { stage: JobStage; active: boolean }) {
  const icon = stage.done ? "✓" : active ? "●" : "○";
  const iconColor = stage.done
    ? "var(--green)"
    : active
      ? "var(--cyan)"
      : "var(--muted)";
  return (
    <div style={styles.stageRow}>
      <div style={styles.stageHeader}>
        <span style={{ color: iconColor, fontSize: 14, width: 14 }}>{icon}</span>
        <span
          style={{
            flex: 1,
            color: stage.done
              ? "var(--text)"
              : active
                ? "var(--cyan)"
                : "var(--muted)",
            fontSize: 13,
            fontWeight: active ? 600 : 500,
          }}
        >
          {stage.label}
        </span>
        <span
          style={{
            fontSize: 11,
            color: "var(--muted)",
            minWidth: 40,
            textAlign: "right",
          }}
        >
          {stage.progress.toFixed(0)}%
        </span>
      </div>
      <div style={styles.barOuterSmall}>
        <div
          style={{
            ...styles.barInnerStage,
            width: `${Math.max(0, Math.min(100, stage.progress))}%`,
            background: stage.done
              ? "var(--green)"
              : active
                ? "var(--cyan)"
                : "var(--border)",
          }}
        />
      </div>
    </div>
  );
}

function ResultPanel({ result }: { result: ImportResponse }) {
  return (
    <div style={styles.resultBox}>
      <div style={styles.resultTitle}>✓ Import finalizat</div>

      <div style={styles.kpiGrid}>
        <Kpi label="Rânduri inserate" value={result.inserted} variant="success" />
        <Kpi label="Șterse anterior" value={result.deletedBeforeInsert} variant="muted" />
        <Kpi label="Erori" value={result.skipped} variant={result.skipped > 0 ? "warning" : "muted"} />
        <Kpi label="Luni afectate" value={result.monthsAffected.length} variant="muted" />
      </div>

      {result.monthsAffected.length > 0 && (
        <div style={styles.subSection}>
          <div style={styles.subTitle}>Perioade afectate</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {result.monthsAffected.map((m) => (
              <span key={m} style={styles.monthBadge}>{m}</span>
            ))}
          </div>
        </div>
      )}

      {result.alocare.rowsProcessed > 0 && (
        <div style={styles.subSection}>
          <div style={styles.subTitle}>Alocare — normalizare canonică</div>
          <div style={styles.kpiGrid}>
            <Kpi label="Rânduri Alocare" value={result.alocare.rowsProcessed} variant="muted" />
            <Kpi label="Agenți creați" value={result.alocare.agentsCreated} variant="success" />
            <Kpi label="Magazine create" value={result.alocare.storesCreated} variant="success" />
            <Kpi label="Alias-uri magazine" value={result.alocare.storeAliasesCreated} variant="muted" />
            <Kpi label="Alias-uri agenți" value={result.alocare.agentAliasesCreated} variant="muted" />
            <Kpi label="Alocări noi" value={result.alocare.assignmentsCreated} variant="muted" />
          </div>
        </div>
      )}

      <div style={styles.subSection}>
        <div style={styles.subTitle}>Rezolvare canonicals la import</div>
        <div style={styles.kpiGrid}>
          <Kpi label="Magazine nemapate" value={result.unmappedClients} variant={result.unmappedClients > 0 ? "warning" : "success"} />
          <Kpi label="Agenți nemapați" value={result.unmappedAgents} variant={result.unmappedAgents > 0 ? "warning" : "success"} />
          <Kpi label="Produse nemapate" value={result.unmappedProducts} variant={result.unmappedProducts > 0 ? "warning" : "success"} />
        </div>
        {(result.unmappedClients > 0 || result.unmappedAgents > 0 || result.unmappedProducts > 0) && (
          <div style={styles.hint}>
            Rândurile nemapate apar în Mapare &amp; Alocare (meniul ⚙) — poți
            crea canonicals lipsă sau alias-uri noi manual.
          </div>
        )}
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
  checkbox: {
    display: "flex",
    gap: 10,
    alignItems: "flex-start",
    fontSize: 13,
    cursor: "pointer",
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
  stageHeader: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  barOuterSmall: {
    height: 4,
    background: "rgba(0,0,0,0.3)",
    borderRadius: 2,
    overflow: "hidden",
  },
  barInnerStage: {
    height: "100%",
    transition: "width 0.2s ease, background 0.2s ease",
  },
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
  monthBadge: {
    background: "rgba(34,211,238,0.12)",
    color: "var(--cyan)",
    padding: "3px 10px",
    borderRadius: 12,
    fontSize: 12,
  },
  hint: {
    background: "rgba(251,146,60,0.08)",
    border: "1px solid var(--orange)",
    color: "var(--orange)",
    padding: "8px 12px",
    borderRadius: 6,
    fontSize: 12,
  },
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

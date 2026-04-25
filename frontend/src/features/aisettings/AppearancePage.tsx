import { type CSSProperties } from "react";
import {
  FONT_SCALE_OPTIONS,
  ZOOM_OPTIONS,
  useTheme,
} from "../../shared/ui/ThemeProvider";
import { usePrivacy } from "../../shared/ui/PrivacyProvider";

/**
 * Appearance / Aspect — controale pentru dimensiune font și magnifier (zoom).
 * Setările sunt salvate în localStorage și aplicate global.
 */
export default function AppearancePage() {
  const { theme, setTheme, fontScale, setFontScale, zoom, setZoom } = useTheme();
  const { hideAgents, toggleHideAgents } = usePrivacy();

  return (
    <div style={styles.page}>
      <h1 style={styles.h1}>🎨 Aspect</h1>
      <p style={styles.intro}>
        Ajustează cum se afișează aplicația. Setările rămân salvate în browser.
      </p>

      {/* Temă */}
      <section style={styles.section}>
        <div style={styles.label}>Temă</div>
        <div style={styles.btnGroup}>
          <button
            type="button"
            onClick={() => setTheme("light")}
            style={{
              ...styles.optBtn,
              ...(theme === "light" ? styles.optBtnActive : {}),
            }}
          >
            ☀ Luminos
          </button>
          <button
            type="button"
            onClick={() => setTheme("dark")}
            style={{
              ...styles.optBtn,
              ...(theme === "dark" ? styles.optBtnActive : {}),
            }}
          >
            ☾ Întunecat
          </button>
        </div>
      </section>

      {/* Dimensiune font */}
      <section style={styles.section}>
        <div style={styles.label}>Dimensiune text</div>
        <p style={styles.hint}>
          Scalează textul din tabele și pagini (1.00 = normal).
        </p>
        <div style={styles.btnGroup}>
          {FONT_SCALE_OPTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setFontScale(s)}
              style={{
                ...styles.optBtn,
                ...(Math.abs(fontScale - s) < 0.001 ? styles.optBtnActive : {}),
              }}
            >
              {fmtScale(s)}
            </button>
          ))}
        </div>
        <div style={styles.preview}>
          Exemplu text: <span style={{ fontSize: 13 }}>Lorem ipsum 1234</span>{" "}
          <span style={{ fontSize: 12, color: "var(--muted)" }}>subtext</span>
        </div>
      </section>

      {/* Zoom (magnifier) */}
      <section style={styles.section}>
        <div style={styles.label}>Magnifier (zoom pagină)</div>
        <p style={styles.hint}>
          Scalează toată interfața — butoane, icon-uri, chart-uri (100% = normal).
        </p>
        <div style={styles.btnGroup}>
          {ZOOM_OPTIONS.map((z) => (
            <button
              key={z}
              type="button"
              onClick={() => setZoom(z)}
              style={{
                ...styles.optBtn,
                ...(Math.abs(zoom - z) < 0.001 ? styles.optBtnActive : {}),
              }}
            >
              {Math.round(z * 100)}%
            </button>
          ))}
        </div>
      </section>

      {/* Confidențialitate — ascunde date despre agenți */}
      <section style={styles.section}>
        <div style={styles.label}>Confidențialitate</div>
        <p style={styles.hint}>
          Ascunde toate datele despre agenți (nume, performanță individuală)
          pentru analiză cu persoane din afara firmei. Numele sunt înlocuite
          cu "Agent A", "Agent B" etc.
        </p>
        <button
          type="button"
          onClick={toggleHideAgents}
          style={{
            ...styles.optBtn,
            ...(hideAgents ? styles.optBtnActive : {}),
            alignSelf: "flex-start",
            minWidth: 220,
          }}
        >
          {hideAgents ? "🔒 Mod confidențial ACTIV" : "🔓 Activează mod confidențial"}
        </button>
      </section>

      {/* Reset */}
      <section style={styles.section}>
        <button
          type="button"
          onClick={() => {
            setFontScale(1);
            setZoom(1);
          }}
          style={styles.resetBtn}
        >
          Resetează dimensiune & zoom la implicit
        </button>
      </section>
    </div>
  );
}

function fmtScale(s: number): string {
  if (s === 1) return "Normal";
  if (s < 1) return `${Math.round(s * 100)}%`;
  return `+${Math.round((s - 1) * 100)}%`;
}

const styles: Record<string, CSSProperties> = {
  page: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
    maxWidth: 720,
  },
  h1: { fontSize: 22, fontWeight: 700, margin: 0, color: "var(--cyan)" },
  intro: { color: "var(--muted)", margin: 0, fontSize: 13 },
  section: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: 16,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  label: {
    fontSize: 12,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    color: "var(--muted)",
  },
  hint: { fontSize: 12, color: "var(--muted)", margin: 0 },
  btnGroup: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
  },
  optBtn: {
    padding: "8px 14px",
    borderRadius: 8,
    border: "1px solid var(--border)",
    background: "var(--bg)",
    color: "var(--text)",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
    minWidth: 70,
  },
  optBtnActive: {
    background: "var(--accent)",
    color: "#fff",
    borderColor: "var(--accent)",
    fontWeight: 700,
  },
  preview: {
    padding: "10px 12px",
    background: "var(--bg)",
    borderRadius: 8,
    border: "1px dashed var(--border)",
    fontSize: 13,
    color: "var(--text)",
  },
  resetBtn: {
    padding: "10px 16px",
    borderRadius: 8,
    border: "1px solid var(--border)",
    background: "var(--bg)",
    color: "var(--text)",
    cursor: "pointer",
    fontSize: 13,
    alignSelf: "flex-start",
  },
};

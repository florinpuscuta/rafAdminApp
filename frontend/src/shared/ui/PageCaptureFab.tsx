/**
 * Floating "capture full page" button — apare jos-dreapta pe toate paginile.
 *
 * Click → render întregului `<main>` (full scroll height) la PNG via
 * `html-to-image`, apoi meniu cu acțiuni:
 *   - Descarcă PNG
 *   - Share (navigator.share — iOS/Android deschid WhatsApp/Mail/etc.)
 *   - WhatsApp Web (fallback desktop — deschid `wa.me` gol, user atașează manual după download)
 *   - Email (mailto link gol cu subject — user atașează manual după download)
 *
 * `navigator.share({ files: [...] })` e suportat pe iOS 16+ și Android Chrome,
 * iar sistemul afișează orice app instalat (WhatsApp / Gmail / Signal / etc.).
 */
import { useState } from "react";
import { toPng } from "html-to-image";

type Status = "idle" | "capturing" | "ready" | "error";

interface CaptureState {
  status: Status;
  dataUrl: string | null;
  blob: Blob | null;
  filename: string;
  error: string | null;
}

const INITIAL: CaptureState = {
  status: "idle", dataUrl: null, blob: null,
  filename: "captura.png", error: null,
};

async function captureMain(): Promise<{ dataUrl: string; blob: Blob; filename: string }> {
  const main = document.getElementById("main-content") as HTMLElement | null;
  if (!main) throw new Error("<main id='main-content'> nu a fost găsit");

  // Captează înălțimea completă a conținutului, nu doar viewport-ul.
  const fullHeight = Math.max(main.scrollHeight, main.clientHeight);
  const dataUrl = await toPng(main, {
    backgroundColor: "#ffffff",
    width: main.scrollWidth,
    height: fullHeight,
    pixelRatio: 2,
    cacheBust: true,
    // Forțăm copierea dimensiunilor reale, fără styling inline care
    // ascundea conținutul off-screen.
    style: {
      transform: "none",
      height: `${fullHeight}px`,
      maxHeight: "none",
      overflow: "visible",
    },
    filter: (node) => {
      // Nu capturăm butonul FAB în poza rezultată
      const el = node as HTMLElement;
      return !el.dataset || el.dataset.captureFab !== "true";
    },
  });

  const blob = await (await fetch(dataUrl)).blob();
  const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
  const title = (document.title || "captura").replace(/[^\w.-]+/g, "_").slice(0, 60);
  return { dataUrl, blob, filename: `${title}_${stamp}.png` };
}

export default function PageCaptureFab() {
  const [open, setOpen] = useState(false);
  const [cap, setCap] = useState<CaptureState>(INITIAL);

  async function doCapture() {
    setCap({ ...INITIAL, status: "capturing" });
    setOpen(true);
    try {
      const r = await captureMain();
      setCap({ status: "ready", dataUrl: r.dataUrl, blob: r.blob,
               filename: r.filename, error: null });
    } catch (err) {
      setCap({
        ...INITIAL,
        status: "error",
        error: err instanceof Error ? err.message : "Captură eșuată",
      });
    }
  }

  function download() {
    if (!cap.dataUrl) return;
    const a = document.createElement("a");
    a.href = cap.dataUrl;
    a.download = cap.filename;
    a.click();
  }

  async function share() {
    if (!cap.blob) return;
    const file = new File([cap.blob], cap.filename, { type: "image/png" });
    const canShareFile =
      typeof navigator.canShare === "function"
      && navigator.canShare({ files: [file] });
    if (!canShareFile) {
      alert("Browser-ul nu suportă share de fișiere. Descarcă și trimite manual.");
      return;
    }
    try {
      await navigator.share({
        files: [file],
        title: document.title,
        text: `Captură: ${document.title}`,
      });
    } catch (err) {
      // user cancelled — ignore
      if (err instanceof Error && err.name !== "AbortError") {
        alert(err.message);
      }
    }
  }

  function whatsappWeb() {
    // Fallback desktop: download + deschide WhatsApp Web
    download();
    const url = `https://wa.me/?text=${encodeURIComponent(`Captură: ${document.title}`)}`;
    window.open(url, "_blank");
  }

  function emailFallback() {
    download();
    const subject = encodeURIComponent(`Captură: ${document.title}`);
    const body = encodeURIComponent(
      "Am atașat captura paginii.\n\n(Deschide fișierul descărcat și atașează-l la acest email.)",
    );
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  }

  function close() {
    setOpen(false);
    setCap(INITIAL);
  }

  return (
    <>
      <button
        type="button"
        onClick={doCapture}
        title="Captură full page"
        data-capture-fab="true"
        style={styles.fab}
      >
        📸
      </button>
      {open && (
        <div data-capture-fab="true" style={styles.overlay} onClick={close}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <b>Captură pagină</b>
              <button onClick={close} style={styles.closeBtn}>✕</button>
            </div>
            {cap.status === "capturing" && (
              <div style={styles.body}>⏳ Se capturează pagina…</div>
            )}
            {cap.status === "error" && (
              <div style={{ ...styles.body, color: "#dc2626" }}>
                Eroare: {cap.error}
              </div>
            )}
            {cap.status === "ready" && cap.dataUrl && (
              <>
                <img src={cap.dataUrl} alt="preview" style={styles.preview} />
                <div style={styles.actions}>
                  <button style={styles.actBtn} onClick={download}>
                    📥 Descarcă
                  </button>
                  <button style={styles.actBtn} onClick={share}>
                    📤 Share
                  </button>
                  <button style={styles.actBtn} onClick={whatsappWeb}>
                    💬 WhatsApp
                  </button>
                  <button style={styles.actBtn} onClick={emailFallback}>
                    ✉️ Email
                  </button>
                </div>
                <div style={styles.hint}>
                  Share funcționează pe mobil (iOS 16+ / Android). Pe desktop,
                  WhatsApp/Email descarcă poza — atașeaz-o manual la mesaj.
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
  fab: {
    position: "fixed", bottom: 24, right: 24, zIndex: 9998,
    width: 56, height: 56, borderRadius: "50%",
    border: "none", cursor: "pointer",
    background: "var(--accent, #0ea5e9)", color: "#fff",
    fontSize: 24,
    boxShadow: "0 4px 16px rgba(0,0,0,0.25)",
  },
  overlay: {
    position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)",
    zIndex: 9999, display: "flex", alignItems: "center",
    justifyContent: "center", padding: 16,
  },
  modal: {
    background: "var(--card, #fff)", color: "var(--text, #111)",
    borderRadius: 12, maxWidth: 720, width: "100%",
    maxHeight: "90vh", overflowY: "auto",
    boxShadow: "0 8px 40px rgba(0,0,0,0.4)",
  },
  modalHeader: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    padding: "12px 16px", borderBottom: "1px solid var(--border,#e5e7eb)",
  },
  closeBtn: {
    border: "none", background: "transparent", fontSize: 18,
    cursor: "pointer", color: "var(--muted,#666)",
  },
  body: { padding: 24, textAlign: "center", fontSize: 14 },
  preview: { width: "100%", display: "block", borderBottom: "1px solid var(--border,#e5e7eb)" },
  actions: {
    display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
    gap: 8, padding: 12,
  },
  actBtn: {
    padding: "10px 14px", borderRadius: 8, border: "1px solid var(--border,#ddd)",
    background: "var(--bg-elevated,#fafafa)", color: "var(--text,#111)",
    cursor: "pointer", fontSize: 13, fontWeight: 600,
  },
  hint: {
    fontSize: 11, color: "var(--muted,#888)", padding: "0 16px 12px",
    textAlign: "center",
  },
};

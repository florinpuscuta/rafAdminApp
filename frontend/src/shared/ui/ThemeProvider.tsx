import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

type Theme = "light" | "dark";

export const FONT_SCALE_OPTIONS = [0.85, 0.95, 1, 1.1, 1.25, 1.5] as const;
export const ZOOM_OPTIONS = [0.9, 1, 1.1, 1.25, 1.5] as const;

interface ThemeAPI {
  theme: Theme;
  toggle: () => void;
  setTheme: (t: Theme) => void;
  fontScale: number;
  setFontScale: (s: number) => void;
  zoom: number;
  setZoom: (z: number) => void;
}

const ThemeContext = createContext<ThemeAPI | null>(null);
const LS_KEY = "adeplast_theme";
const LS_FONT_SCALE = "adeplast_font_scale";
const LS_ZOOM = "adeplast_zoom";

function applyCssVars(theme: Theme) {
  const root = document.documentElement;
  // Paleta legacy (adeplast-dashboard) — cyan primary pe dark navy, toate CSS
  // vars folosite în restul app-ului (--bg, --fg, --border, --accent, etc.)
  // punctează pe aceste valori, deci paginile existente adoptă automat tema.
  if (theme === "dark") {
    root.style.setProperty("--bg", "#0a0e17");
    root.style.setProperty("--bg-elevated", "#111827");
    root.style.setProperty("--bg-sidebar", "#111827");
    root.style.setProperty("--card", "#111827");
    root.style.setProperty("--fg", "#e0e0e0");
    root.style.setProperty("--fg-muted", "#6b7280");
    root.style.setProperty("--text", "#e0e0e0");
    root.style.setProperty("--muted", "#6b7280");
    root.style.setProperty("--border", "#1e293b");
    root.style.setProperty("--accent", "#22d3ee");
    root.style.setProperty("--accent-soft", "rgba(34,211,238,0.15)");
    root.style.setProperty("--cyan", "#22d3ee");
    root.style.setProperty("--danger", "#ef4444");
    root.style.setProperty("--success", "#34d399");
    root.style.setProperty("--warning", "#fb923c");
    root.style.setProperty("--green", "#34d399");
    root.style.setProperty("--orange", "#fb923c");
    root.style.setProperty("--red", "#ef4444");
    root.style.setProperty("--skeleton-base", "#1e293b");
    root.style.setProperty("--skeleton-highlight", "#334155");
    root.dataset.theme = "dark";
  } else {
    root.style.setProperty("--bg", "#fafafa");
    root.style.setProperty("--bg-elevated", "#ffffff");
    root.style.setProperty("--bg-sidebar", "#ffffff");
    root.style.setProperty("--card", "#ffffff");
    root.style.setProperty("--fg", "#1f2937");
    root.style.setProperty("--fg-muted", "#666");
    root.style.setProperty("--text", "#1f2937");
    root.style.setProperty("--muted", "#666");
    root.style.setProperty("--border", "#e5e7eb");
    root.style.setProperty("--accent", "#0891b2");
    root.style.setProperty("--accent-soft", "rgba(8,145,178,0.12)");
    root.style.setProperty("--cyan", "#0891b2");
    root.style.setProperty("--danger", "#b00020");
    root.style.setProperty("--success", "#065f13");
    root.style.setProperty("--warning", "#b45309");
    root.style.setProperty("--green", "#059669");
    root.style.setProperty("--orange", "#ea580c");
    root.style.setProperty("--red", "#dc2626");
    root.style.setProperty("--skeleton-base", "#e5e7eb");
    root.style.setProperty("--skeleton-highlight", "#f3f4f6");
    root.dataset.theme = "light";
  }
  // --sidebar-w și font-family sunt constante peste teme.
  root.style.setProperty("--sidebar-w", "280px");
  root.style.setProperty(
    "--font-stack",
    "-apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
  );
  document.body.style.background = theme === "dark" ? "#0a0e17" : "#f7f8fa";
  document.body.style.color = theme === "dark" ? "#e0e0e0" : "#1f2937";
  ensureSkeletonKeyframes();
}

function ensureSkeletonKeyframes() {
  if (document.getElementById("skeleton-keyframes")) return;
  const style = document.createElement("style");
  style.id = "skeleton-keyframes";
  style.textContent = [
    "@keyframes skeleton-shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}",
    ".skip-link:focus{top:8px!important;}",
    "*{ -webkit-tap-highlight-color:transparent;}",
    "a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid var(--accent,#2563eb);outline-offset:2px;border-radius:8px;}",
    "html,body{max-width:100vw;width:100%;overflow-x:clip;overscroll-behavior-x:contain;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;text-rendering:optimizeLegibility;letter-spacing:-0.003em;}",
    "html,body{position:relative;}",
    "body,html,button,input,select,textarea,optgroup,option,label,table,th,td,h1,h2,h3,h4,h5,h6,p,span,div,a,strong,em{font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',Roboto,Helvetica,Arial,sans-serif!important;}",
    "body{font-size:14px;line-height:1.5;color:var(--text);}",
    "h1,h2,h3,h4,h5,h6{font-weight:700;line-height:1.25;letter-spacing:-0.018em;margin:0;}",
    "p{margin:0;line-height:1.55;}",
    "main{box-sizing:border-box;}",
    "main *,main *::before,main *::after{box-sizing:border-box;}",
    "img,canvas,svg{max-width:100%;height:auto;}",
    /* Refined theme tokens — subtle borders, soft surfaces. */
    "[data-theme='light']{--border:#eef0f3!important;--border-strong:#d8dce3!important;--card:#ffffff!important;--bg:#f7f8fa!important;--bg-elevated:#ffffff!important;--muted:#64748b!important;--fg-muted:#64748b!important;--accent:#2563eb!important;--accent-soft:rgba(37,99,235,0.08)!important;}",
    "[data-theme='dark']{--border:#1f2937!important;--border-strong:#334155!important;--card:#0f172a!important;--bg:#0b1220!important;--bg-elevated:#111827!important;--muted:#94a3b8!important;--fg-muted:#94a3b8!important;--accent:#38bdf8!important;--accent-soft:rgba(56,189,248,0.12)!important;}",
    /* Coerce hardcoded legacy colors → theme tokens. */
    "main [style*='background: #fff'],main [style*='background:#fff'],main [style*='background: #ffffff'],main [style*='background:#ffffff'],main [style*='background: rgb(255, 255, 255)'],main [style*='background: #fafafa'],main [style*='background:#fafafa'],main [style*='background: rgb(250, 250, 250)'],main [style*='background: #f5f5f5'],main [style*='background:#f5f5f5']{background:var(--card)!important;color:var(--text)!important;}",
    "main [style*='border: 1px solid #eee'],main [style*='border:1px solid #eee'],main [style*='border: 1px solid rgb(238, 238, 238)'],main [style*='border: 1px solid #e0e0e0'],main [style*='border: 1px solid #d0d0d0'],main [style*='border: 1px solid rgb(208, 208, 208)'],main [style*='border: 1px solid #ccc'],main [style*='border-color: #eee'],main [style*='border-color: #ccc'],main [style*='border-color: #d0d0d0']{border-color:var(--border)!important;}",
    /* Cards: soft surface, hairline border, barely-there shadow. */
    "main form,main [style*='border-radius: 6'],main [style*='borderRadius: 6'],main [style*='border-radius: 8'],main [style*='borderRadius: 8']{border:1px solid var(--border)!important;border-radius:12px!important;box-shadow:0 1px 2px rgba(15,23,42,0.04)!important;}",
    "[data-theme='dark'] main form,[data-theme='dark'] main [style*='border-radius: 6'],[data-theme='dark'] main [style*='border-radius: 8']{box-shadow:0 1px 3px rgba(0,0,0,0.25)!important;}",
    /* Inputs: refined — subtle surface, hairline border, tight focus ring. */
    "main input:not([type='checkbox']):not([type='radio']):not([type='file']),main select,main textarea{background:var(--card)!important;color:var(--text)!important;border:1px solid var(--border)!important;border-radius:8px!important;font-size:14px;padding:8px 12px;transition:border-color 0.12s ease,box-shadow 0.12s ease,background 0.12s ease;}",
    "main input:hover:not(:disabled),main select:hover:not(:disabled),main textarea:hover:not(:disabled){border-color:var(--border-strong)!important;}",
    "main input:focus,main select:focus,main textarea:focus{border-color:var(--accent)!important;box-shadow:0 0 0 3px var(--accent-soft)!important;outline:none!important;}",
    "main input::placeholder,main textarea::placeholder{color:var(--muted);opacity:0.55;}",
    "main input:disabled,main select:disabled,main textarea:disabled{opacity:0.6;cursor:not-allowed;}",
    /* Select arrow: consistent, not browser-default. */
    "main select{appearance:none;-webkit-appearance:none;background-image:linear-gradient(45deg,transparent 50%,var(--muted) 50%),linear-gradient(135deg,var(--muted) 50%,transparent 50%)!important;background-position:calc(100% - 16px) calc(50% - 2px),calc(100% - 11px) calc(50% - 2px)!important;background-size:5px 5px,5px 5px!important;background-repeat:no-repeat!important;padding-right:34px!important;}",
    /* Buttons: clean hierarchy — filled colored = primary, light bg = secondary. */
    "main button{border-radius:8px;font-family:inherit;font-weight:500;font-size:14px;padding:8px 14px;transition:background 0.12s ease,border-color 0.12s ease,box-shadow 0.12s ease,color 0.12s ease;cursor:pointer;}",
    /* Default (neutral) button — ghost / secondary style. */
    "main button:not([style*='background:'][style*='rgb']):not([style*='background-color']):not([style*='background: var']):not([style*='background:#']){background:var(--card)!important;color:var(--text)!important;border:1px solid var(--border)!important;}",
    "main button:not(:disabled):hover{border-color:var(--border-strong)!important;background:var(--bg-elevated)!important;}",
    "main button[type='submit']:not([style*='background-color']):not([style*='background: var']){background:var(--accent)!important;color:#fff!important;border:1px solid var(--accent)!important;box-shadow:0 1px 2px rgba(15,23,42,0.08)!important;}",
    "main button[type='submit']:not(:disabled):hover{filter:brightness(1.08);}",
    "main button:not(:disabled):active{transform:translateY(1px);}",
    "main button:disabled{opacity:0.5;cursor:not-allowed;}",
    /* Tables: quiet, professional density. */
    "main table{border-collapse:separate;border-spacing:0;width:100%;font-size:13px;}",
    "main thead th{background:var(--bg)!important;position:sticky;top:0;z-index:1;border-bottom:1px solid var(--border)!important;color:var(--muted)!important;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;font-size:11px!important;padding:10px 12px!important;}",
    "main tbody td{border-bottom:1px solid var(--border)!important;padding:10px 12px;vertical-align:top;}",
    /* Uniformizare font minimum 12.5px în main (caractere mici devin lizibile). */
    "main [style*='font-size: 10px']{font-size:12.5px!important;}",
    "main [style*='font-size: 10.5px']{font-size:12.5px!important;}",
    "main [style*='font-size: 11px']{font-size:13px!important;}",
    "main tbody td:first-child{word-break:break-word;padding-right:16px;}",
    "main tbody td:last-child{white-space:nowrap;}",
    "main tbody tr{transition:background 0.08s ease;}",
    "main tbody tr:hover{background:var(--accent-soft);}",
    /* Links. */
    "main a:not([class]){color:var(--accent);text-decoration-thickness:1px;text-underline-offset:3px;}",
    "main a:not([class]):hover{text-decoration-thickness:2px;}",
    /* Typography hierarchy. */
    "main h1,main h2,main h3,main h4{letter-spacing:-0.018em;line-height:1.25;font-weight:700;color:var(--text);}",
    "main h1{font-size:28px;}",
    "main h2{font-size:20px;}",
    "main h3{font-size:16px;}",
    /* Dividers and muted paragraphs. */
    "main hr{border:none;border-top:1px solid var(--border);margin:16px 0;}",
    "main p{line-height:1.55;}",
    /* ═══ BUTOANE — dimensiune UNIFORMĂ, lățime FIXĂ ══════════════════════
       Reset total: toate butoanele și select-urile au EXACT 88×28px.
       Fond alb, text colorat per variantă.
       Variante: data-variant=success|danger|warning|purple|muted
       Active: data-active="true" / aria-pressed="true" → fundal colorat
       Opt-out: data-raw="true" (FAB etc.) sau data-wide="true" (text lung). */
    "main button:not([data-raw='true']):not([data-wide='true']),main a[role='button']:not([data-raw='true']):not([data-wide='true']),main select:not([data-raw='true']):not([data-wide='true']){width:88px!important;height:28px!important;min-width:88px!important;max-width:88px!important;min-height:28px!important;max-height:28px!important;padding:0 6px!important;background:#ffffff!important;color:var(--accent,#2563eb)!important;border:1px solid rgba(37,99,235,0.3)!important;border-radius:6px!important;font-size:11px!important;font-weight:600!important;line-height:1!important;cursor:pointer!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;gap:3px!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;box-sizing:border-box!important;text-align:center!important;flex:0 0 88px!important;margin:0!important;}",
    "main button:not([data-raw='true']):hover,main a[role='button']:not([data-raw='true']):hover{background:rgba(37,99,235,0.06)!important;}",
    /* Select — aceeași dimensiune fixă, fără arrow browser-default */
    "main select:not([data-raw='true']):not([data-wide='true']){-webkit-appearance:none!important;-moz-appearance:none!important;appearance:none!important;text-align-last:center!important;}",
    /* Variante — doar color + border */
    "main button[data-variant='success']:not([data-raw='true']){color:#16a34a!important;border-color:rgba(22,163,74,0.35)!important;}",
    "main button[data-variant='danger']:not([data-raw='true']){color:#dc2626!important;border-color:rgba(220,38,38,0.35)!important;}",
    "main button[data-variant='warning']:not([data-raw='true']){color:#d97706!important;border-color:rgba(217,119,6,0.35)!important;}",
    "main button[data-variant='purple']:not([data-raw='true']){color:#a855f7!important;border-color:rgba(168,85,247,0.35)!important;}",
    "main button[data-variant='muted']:not([data-raw='true']){color:#64748b!important;border-color:rgba(100,116,139,0.3)!important;}",
    /* Active/pressed → fundal colorat, text alb */
    "main button[data-active='true']:not([data-raw='true']),main button[aria-pressed='true']:not([data-raw='true']){background:var(--accent,#2563eb)!important;color:#fff!important;border-color:var(--accent,#2563eb)!important;}",
    "main button[data-active='true'][data-variant='success']:not([data-raw='true']){background:#16a34a!important;border-color:#16a34a!important;color:#fff!important;}",
    "main button[data-active='true'][data-variant='danger']:not([data-raw='true']){background:#dc2626!important;border-color:#dc2626!important;color:#fff!important;}",
    "main button[data-active='true'][data-variant='warning']:not([data-raw='true']){background:#d97706!important;border-color:#d97706!important;color:#fff!important;}",
    "main button[data-active='true'][data-variant='purple']:not([data-raw='true']){background:#a855f7!important;border-color:#a855f7!important;color:#fff!important;}",
    "main button:disabled:not([data-raw='true']){opacity:0.5!important;cursor:not-allowed!important;}",
    /* Gap uniform între butoane — containere cu butoane normale: 8px; cu chips compacte: 6px */
    "main div:has(> button:not([data-raw='true']):not([data-compact='true'])){gap:8px!important;}",
    "main div:has(> button[data-compact='true']){gap:6px!important;}",
    /* data-wide — buton cu lățime naturală (Actualizează cu AI, Generează raport, etc.) */
    "main button[data-wide='true']:not([data-raw='true']){width:auto!important;min-width:88px!important;max-width:none!important;height:28px!important;min-height:28px!important;max-height:28px!important;padding:0 14px!important;background:#ffffff!important;color:var(--accent,#2563eb)!important;border:1px solid rgba(37,99,235,0.3)!important;border-radius:6px!important;font-size:11px!important;font-weight:600!important;line-height:1!important;cursor:pointer!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;gap:3px!important;white-space:nowrap!important;box-sizing:border-box!important;}",
    /* data-compact — chips/pills (luni, filtre) — tot fix dar mai mic */
    "main button[data-compact='true']:not([data-raw='true']){width:56px!important;min-width:56px!important;max-width:56px!important;height:24px!important;min-height:24px!important;max-height:24px!important;padding:0 4px!important;font-size:10.5px!important;border-radius:5px!important;flex:0 0 56px!important;}",
    "@media (max-width:768px){",
    "  main button[data-compact='true']:not([data-raw='true']){width:50px!important;min-width:50px!important;max-width:50px!important;height:26px!important;min-height:26px!important;max-height:26px!important;flex:0 0 50px!important;}",
    "}",
    /* ═══ MOBILE ═══════════════════════════════════════════════════════ */
    "@media (max-width:768px){",
    /* Container main: padding orizontal strâns, vertical aerat. */
    "  main{padding:12px 12px 80px!important;min-width:0;overflow-x:hidden;}",
    "  main>*+*{margin-top:12px;}",
    /* Tipografie: scară clară, fără wrap-uri ciudate. */
    "  main h1{font-size:22px!important;font-weight:700!important;line-height:1.25!important;margin:0 0 10px!important;word-break:break-word;}",
    "  main h2{font-size:17.5px!important;font-weight:700!important;line-height:1.3!important;margin:0 0 8px!important;word-break:break-word;}",
    "  main h3{font-size:15px!important;font-weight:600!important;line-height:1.35!important;margin:0 0 6px!important;word-break:break-word;}",
    "  main{font-size:14px;}",
    /* Tabele: scroll orizontal elegant cu hairline. */
    "  main table{display:block!important;width:100%!important;max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch;font-size:13.5px!important;border:1px solid var(--border);border-radius:10px;}",
    "  main thead th{font-size:11px!important;padding:8px 10px!important;white-space:nowrap;}",
    "  main tbody td{font-size:13.5px!important;padding:8px 10px!important;}",
    "  main tbody td:last-child{white-space:nowrap;}",
    /* Containere custom cu overflow-x → păstrează dar alege radius uniform. */
    "  main>div[style*='overflowX: auto'],main>div[style*='overflow-x: auto'],main>div[style*='overflow:auto']{max-width:100%;border-radius:12px;}",
    /* Griduri simple (2-4 coloane): stack → 1 coloană pe mobile. NU aplicăm pe grid-uri complexe (tabele cu 5+ coloane inline), acelea rămân cu scroll orizontal. */
    "  main [style*='grid-template-columns: repeat(']:not([data-chipgrid]),main [style*='grid-template-columns:repeat(']:not([data-chipgrid]){grid-template-columns:minmax(0,1fr)!important;gap:10px!important;}",
    "  main [style*='grid-template-columns: 1fr 1fr'][style*='gap']:not([style*='1fr 1fr 1fr 1fr 1fr']){grid-template-columns:minmax(0,1fr)!important;gap:10px!important;}",
    "  main [style*='grid-template-columns: 1fr 2fr'],main [style*='grid-template-columns: 2fr 1fr'],main [style*='grid-template-columns: auto 1fr'],main [style*='grid-template-columns: 1fr auto']{grid-template-columns:minmax(0,1fr)!important;gap:10px!important;}",
    "  main [style*='grid-template-columns: 220px 1fr'],main [style*='grid-template-columns: 240px 1fr'],main [style*='grid-template-columns: 260px 1fr'],main [style*='grid-template-columns: 280px 1fr'],main [style*='grid-template-columns: 300px 1fr']{grid-template-columns:minmax(0,1fr)!important;gap:10px!important;}",
    /* Tabele-grid (5+ coloane inline): nu stack — rând min-width pentru scroll. */
    "  main [style*='grid-template-columns: 2fr '],main [style*='grid-template-columns: 1.5fr '],main [style*='grid-template-columns: 1.8fr ']{min-width:760px!important;}",
    /* Părinte cu overflow:hidden + border-radius → scroll orizontal pe mobile (container de tabel). */
    "  main [style*='overflow: hidden'][style*='border-radius']{overflow-x:auto!important;overflow-y:visible!important;-webkit-overflow-scrolling:touch;max-width:100%!important;width:100%!important;}",
    /* Caz special: „name | bar | amount" (3-col) → ascunde bar-ul și stack name+amount. */
    "  main [style*='grid-template-columns: 160px 1fr 220px']>:nth-child(2),main [style*='grid-template-columns: 180px 1fr 220px']>:nth-child(2),main [style*='grid-template-columns: 200px 1fr 220px']>:nth-child(2){display:none!important;}",
    "  main [style*='grid-template-columns: 160px 1fr 220px'],main [style*='grid-template-columns: 180px 1fr 220px'],main [style*='grid-template-columns: 200px 1fr 220px']{grid-template-columns:1fr auto!important;}",
    "  main [style*='grid-template-columns: 160px 1fr 220px']>*,main [style*='grid-template-columns: 180px 1fr 220px']>*,main [style*='grid-template-columns: 200px 1fr 220px']>*{text-align:left!important;}",
    "  main [style*='grid-template-columns: 160px 1fr 220px']>*:last-child,main [style*='grid-template-columns: 180px 1fr 220px']>*:last-child,main [style*='grid-template-columns: 200px 1fr 220px']>*:last-child{text-align:right!important;font-size:12px!important;}",
    /* Griduri cu auto-fit/fill: 1 col la mobile, 2 col deasupra 480px. */
    "  main [style*='repeat(auto-fit'],main [style*='repeat(auto-fill']{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))!important;gap:10px!important;}",
    /* KPI row-uri gridAutoFlow column → wrap în 2 coloane. */
    "  main [style*='gridAutoFlow: column'],main [style*='grid-auto-flow: column']{grid-auto-flow:row!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:8px!important;}",
    /* Ultimul copil singur pe rând (dacă număr impar). */
    "  main [style*='gridAutoFlow: column']>:last-child:nth-child(odd),main [style*='grid-auto-flow: column']>:last-child:nth-child(odd){grid-column:1 / -1!important;}",
    /* Flex rows (NU flex-column): wrap. */
    "  main [style*='display: flex'][style*='gap']:not([style*='flex-direction: column']):not([style*='flex-direction:column']){flex-wrap:wrap!important;}",
    "  main header,main [style*='space-between']{flex-wrap:wrap!important;gap:10px!important;}",
    /* Selectoare și inputs: full width, 16px font ca iOS să nu zoom-eze. */
    "  main input,main select,main textarea{font-size:16px!important;padding:10px 12px!important;min-height:44px;width:100%!important;max-width:100%;box-sizing:border-box;border-radius:10px!important;}",
    "  main label:not(:has(input[type='file'])){max-width:100%;display:flex;flex-direction:column;gap:5px;font-weight:500;font-size:13px;color:var(--text);flex:1 1 100%!important;width:100%!important;}",
    "  main label>select,main label>input,main label>textarea{width:100%!important;}",
    /* Butoane în main: touch-friendly + full width în filter rows. */
    "  main button,main a[role='button']{min-height:44px;padding:10px 14px!important;font-size:14px!important;border-radius:10px!important;max-width:100%;white-space:normal;}",
    /* Butoane compacte — opt-out explicit pentru chips/pills mici. */
    "  main button[data-compact='true'],main a[data-compact='true']{min-height:0!important;padding:4px 8px!important;font-size:11px!important;border-radius:6px!important;flex:0 0 auto!important;white-space:nowrap!important;}",
    /* Butoane în sidebar/aside: compact (încap în 280px). */
    "  aside button{min-height:36px!important;padding:8px 6px!important;font-size:11px!important;white-space:nowrap!important;overflow:hidden;text-overflow:clip;}",
    /* CompanySwitcher: grid 4 col rămâne 4 col dar cu overflow gestionat. */
    "  aside [style*='grid-template-columns: 1fr 1fr 1fr auto']{grid-template-columns:1fr 1fr 1fr auto!important;gap:2px!important;padding:6px!important;}",
    "  aside [style*='grid-template-columns: 1fr 1fr 1fr auto']>button{min-width:0!important;padding:8px 4px!important;font-size:10.5px!important;letter-spacing:0!important;}",
    /* Filter row (select-uri + buton submit): stack vertical. */
    "  main form>div[style*='display: flex'],main form[style*='display: flex']{flex-direction:column!important;align-items:stretch!important;}",
    "  main [style*='margin-left: auto'],main [style*='marginLeft: auto']{margin-left:0!important;}",
    /* Carduri (detectate după border-radius inline) — padding uniform. */
    "  main [style*='border-radius: 6'],main [style*='border-radius: 8'],main [style*='border-radius: 10'],main [style*='border-radius: 12']{border-radius:14px!important;}",
    "  main form{padding:14px!important;border-radius:14px!important;}",
    /* Nu mai forțăm buttons în flex-wrap la 42%: rămân la dimensiune naturală (min-width din global). */
    /* min-width:0 pe elementele imbricate — previne overflow din text lung. */
    "  main,main *{min-width:0;}",
    /* Elementele cu text-overflow ellipsis rămân așa, dar devin max-width 100%. */
    "  main [style*='text-overflow']{max-width:100%!important;}",
    /* Dezactivează zoom user-ului pe mobile (pinch-zoom native rămâne). */
    "  body{zoom:1!important;}",
    "  main{zoom:1!important;}",
    /* FAB (butonul foto) — bottom-right, deasupra conținutului. */
    "  main+*[style*='position: fixed'],[data-fab='true']{bottom:16px!important;right:16px!important;}",
    "}",
    /* ═══ TABLET 481–768px: 2 coloane pentru cards dacă încap ═════════════ */
    "@media (min-width:481px) and (max-width:768px){",
    "  main [style*='gridAutoFlow: column'],main [style*='grid-auto-flow: column']{grid-template-columns:repeat(3,minmax(0,1fr))!important;}",
    "}",
  ].join("\n");
  document.head.appendChild(style);
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    const saved = localStorage.getItem(LS_KEY);
    if (saved === "dark" || saved === "light") return saved;
    return "light";
  });
  const [fontScale, setFontScaleState] = useState<number>(() => {
    const raw = parseFloat(localStorage.getItem(LS_FONT_SCALE) || "");
    return Number.isFinite(raw) && raw >= 0.5 && raw <= 2 ? raw : 1;
  });
  const [zoom, setZoomState] = useState<number>(() => {
    const raw = parseFloat(localStorage.getItem(LS_ZOOM) || "");
    return Number.isFinite(raw) && raw >= 0.5 && raw <= 2 ? raw : 1;
  });

  useEffect(() => {
    applyCssVars(theme);
    localStorage.setItem(LS_KEY, theme);
  }, [theme]);

  // fontScale: aplică zoom pe <main> — scalează proporțional conținutul. Pe
  // mobile dezactivat (folosești pinch-zoom nativ; altfel layout-ul se lățește
  // peste viewport și creează „rubber band" orizontal).
  useEffect(() => {
    const apply = () => {
      const main = document.getElementById("main-content");
      if (!main) return;
      const isMobile = window.matchMedia("(max-width: 768px)").matches;
      (main.style as unknown as { zoom?: string }).zoom =
        !isMobile && fontScale !== 1 ? String(fontScale) : "";
    };
    apply();
    const raf = requestAnimationFrame(apply);
    const onResize = () => apply();
    window.addEventListener("resize", onResize);
    localStorage.setItem(LS_FONT_SCALE, String(fontScale));
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
    };
  }, [fontScale]);

  // magnifier: zoom pe body (doar desktop). Pe mobile dezactivat.
  useEffect(() => {
    const apply = () => {
      const body = document.body;
      const isMobile = window.matchMedia("(max-width: 768px)").matches;
      (body.style as unknown as { zoom?: string }).zoom =
        !isMobile && zoom !== 1 ? String(zoom) : "";
    };
    apply();
    const onResize = () => apply();
    window.addEventListener("resize", onResize);
    localStorage.setItem(LS_ZOOM, String(zoom));
    return () => window.removeEventListener("resize", onResize);
  }, [zoom]);

  const toggle = useCallback(() => {
    setThemeState((t) => (t === "light" ? "dark" : "light"));
  }, []);
  const setTheme = useCallback((t: Theme) => setThemeState(t), []);
  const setFontScale = useCallback((s: number) => setFontScaleState(s), []);
  const setZoom = useCallback((z: number) => setZoomState(z), []);

  return (
    <ThemeContext.Provider value={{ theme, toggle, setTheme, fontScale, setFontScale, zoom, setZoom }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeAPI {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>");
  return ctx;
}

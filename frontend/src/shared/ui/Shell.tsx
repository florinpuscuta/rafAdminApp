import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { NavLink, useLocation } from "react-router-dom";

import { useAuth } from "../../features/auth/AuthContext";
import PageCaptureFab from "./PageCaptureFab";
import { useTheme } from "./ThemeProvider";
import {
  useCompanyScope,
  type CompanyScope,
} from "./CompanyScopeProvider";

/**
 * Shell — layout identic cu `adeplast-dashboard` legacy: topbar + sidebar
 * 280px cu company switcher la top, tree navigation expand/collapse, main
 * content area. Paleta + font vin din ThemeProvider (cele 10 CSS vars +
 * --font-stack).
 *
 * Meniurile se schimbă după scope (replică legacy buildSidebar):
 *   - SIKADP  → Vedere Generala / Analiza Vanzari / Marketing / Rapoarte /
 *               Targhet si Bonus / Taskuri / Probleme in Activitate
 *   - ADEPLAST/SIKA → Analiza Vanzari / Parteneri / Grupe / Top Produse /
 *                     Mortar / EPS Detalii / Marca Privata / Preturi /
 *                     Prognoza
 *   - SETTINGS (⚙) → Upload / Mapare / Entități / Admin
 *
 * Rute placeholder: feature-uri legacy încă nemigrate → /coming-soon/*
 * (redau ComingSoonPage). Păstrăm tot ce există în SaaS (Dashboard, Sales,
 * Stores, Agents, Products, Users, Audit, etc.) mapat la poziția naturală.
 */

interface LeafItem {
  kind: "leaf";
  to: string;
  label: string;
  end?: boolean;
  labelColor?: string; // override pentru elementele "speciale" (ex: Vedere Gen)
  highlight?: boolean; // gradient special (Prognoză Vânzări)
}

interface ParentItem {
  kind: "parent";
  id: string;
  label: string;
  children: LeafItem[];
}

interface DividerItem {
  kind: "divider";
}

type NavItem = LeafItem | ParentItem | DividerItem;

// ─────────────────────────────────────────────────────────────────────
// Meniuri per scope — structura din `adeplast-dashboard/templates/index.html`
// funcția buildSidebar(), linii 1144–1402.
// ─────────────────────────────────────────────────────────────────────

function buildSikadpTree(): NavItem[] {
  return [
    {
      kind: "leaf",
      to: "/",
      label: "Vedere Generala",
      end: true,
      labelColor: "#a78bfa", // purple accent în legacy
    },
    {
      kind: "parent",
      id: "analiza-vanzari",
      label: "Analiza Vanzari",
      children: [
        { kind: "leaf", to: "/consolidat", label: "Consolidat" },
        { kind: "leaf", to: "/analiza/luni", label: "Analiza pe luni" },
        { kind: "leaf", to: "/analiza/zi", label: "Vz la zi" },
      ],
    },
    { kind: "divider" },
    {
      kind: "parent",
      id: "marketing",
      label: "Marketing",
      children: [
        { kind: "leaf", to: "/marketing/concurenta", label: "Actiuni Concurenta" },
        { kind: "leaf", to: "/gallery", label: "Poze din Magazine" },
        { kind: "leaf", to: "/marketing/catalog", label: "Catalog Lunar" },
        { kind: "leaf", to: "/marketing/facing", label: "Facing Tracker" },
        { kind: "leaf", to: "/marketing/dash-face", label: "Dash Face Tracker" },
        { kind: "leaf", to: "/marketing/facing-config", label: "⚙ Config Concurențe" },
        { kind: "leaf", to: "/marketing/panouri", label: "Panouri & Standuri" },
        { kind: "leaf", to: "/marketing/sika", label: "Actiuni Sika" },
        { kind: "leaf", to: "/aprobari", label: "✓ Aprobări Poze" },
      ],
    },
    { kind: "divider" },
    {
      kind: "parent",
      id: "rapoarte",
      label: "Rapoarte",
      children: [
        { kind: "leaf", to: "/chat", label: "AI Asistent" },
        { kind: "leaf", to: "/rapoarte/lunar", label: "Raport Lunar Management" },
        { kind: "leaf", to: "/rapoarte/playwright", label: "📸 Playwright (capturi pagini)" },
      ],
    },
    { kind: "divider" },
    {
      kind: "parent",
      id: "targhet-bonus",
      label: "Targhet si Bonus",
      children: [
        { kind: "leaf", to: "/targhet", label: "Targhet" },
        { kind: "leaf", to: "/bonusari", label: "Bonusari" },
      ],
    },
    { kind: "divider" },
    { kind: "leaf", to: "/evaluare", label: "📊 Evaluare", end: true },
    {
      kind: "parent",
      id: "evaluare-input",
      label: "Evaluare · Input Date",
      children: [
        { kind: "leaf", to: "/evaluare/sal-fix", label: "Imput sal fix" },
        { kind: "leaf", to: "/evaluare/input-lunar", label: "Input Lunar Agent" },
        { kind: "leaf", to: "/evaluare/zona-agent", label: "Imput bonus magazin" },
      ],
    },
    {
      kind: "parent",
      id: "evaluare-analiza",
      label: "Evaluare · Analiza",
      children: [
        { kind: "leaf", to: "/evaluare/matricea", label: "Matricea Agenți" },
        { kind: "leaf", to: "/evaluare/zona-detaliu", label: "Detaliu Zonă" },
        { kind: "leaf", to: "/evaluare/zona-ranking", label: "Ranking Zone" },
      ],
    },
    { kind: "divider" },
    {
      kind: "parent",
      id: "taskuri",
      label: "Taskuri",
      children: [
        { kind: "leaf", to: "/taskuri", label: "Taskuri" },
        { kind: "leaf", to: "/parcurs", label: "Foaie de Parcurs" },
      ],
    },
    { kind: "divider" },
    {
      kind: "parent",
      id: "probleme",
      label: "Probleme in Activitate",
      children: buildMonthsChildren(),
    },
  ];
}

function buildMonthsChildren(): LeafItem[] {
  const year = new Date().getFullYear();
  const names = [
    "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
    "Iul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  return names.map((n, idx) => ({
    kind: "leaf" as const,
    to: `/probleme/${year}-${idx + 1}`,
    label: `${n} ${year}`,
  }));
}

function buildCompanyTree(scope: "adeplast" | "sika"): NavItem[] {
  const ownLabel = scope === "sika" ? "Sika cross-KA" : "Adeplast cross-KA";
  const analizaChildren: LeafItem[] = [
    { kind: "leaf", to: "/consolidat", label: "Consolidat" },
    { kind: "leaf", to: "/analiza/luni", label: "Analiza pe luni" },
    { kind: "leaf", to: "/analiza/zi", label: "Vz la zi" },
    { kind: "leaf", to: "/analiza/magazin", label: "Analiza Magazin" },
  ];
  if (scope === "adeplast") {
    analizaChildren.push({
      kind: "leaf",
      to: "/analiza/comenzi",
      label: "Comenzi fara IND",
    });
  }

  const preturiChildren: LeafItem[] = [
    { kind: "leaf", to: "/prices/comparative", label: "Preturi Comparative" },
    { kind: "leaf", to: "/prices/own", label: ownLabel },
    { kind: "leaf", to: "/prices/pret3net", label: "Pret 3 Net Comp KA" },
    { kind: "leaf", to: "/prices/propuneri", label: "Propuneri Listare KA" },
  ];
  if (scope === "adeplast") {
    preturiChildren.push({
      kind: "leaf",
      to: "/prices/ka-retail",
      label: "Preturi KA vs Retail",
    });
  }

  const tree: NavItem[] = [
    {
      kind: "parent",
      id: "analiza-vanzari",
      label: "Analiza Vanzari",
      children: analizaChildren,
    },
    {
      kind: "parent",
      id: "preturi",
      label: "Preturi",
      children: preturiChildren,
    },
    { kind: "divider" },
    {
      kind: "parent",
      id: "grupe",
      label: "Grupe Produse",
      children: [
        { kind: "leaf", to: "/grupe-arbore", label: "🌲 Arbore complet" },
        { kind: "leaf", to: "/grupe-arbore-clienti", label: "🏪 Arbore pe clienți" },
      ],
    },
    {
      kind: "parent",
      id: "topprod",
      label: "Top Produse",
      children: scope === "sika"
        ? [
            { kind: "leaf", to: "/topprod/tm-bf", label: "Top 15 Building Finishing" },
            { kind: "leaf", to: "/topprod/tm-sb", label: "Top 15 Sealing & Bonding" },
            { kind: "leaf", to: "/topprod/tm-wp", label: "Top 15 Waterproofing & Roofing" },
            { kind: "leaf", to: "/topprod/tm-ca", label: "Top 15 Concrete & Anchors" },
            { kind: "leaf", to: "/topprod/tm-fl", label: "Top 15 Flooring" },
            { kind: "leaf", to: "/topprod/tm-ia", label: "Top 15 Industry & Accessories" },
          ]
        : [
            { kind: "leaf", to: "/topprod/mu", label: "Top 15 Mortare Uscate" },
            { kind: "leaf", to: "/topprod/eps", label: "Top 15 Polistiren" },
            { kind: "leaf", to: "/topprod/umede", label: "Top 15 Umede" },
            { kind: "leaf", to: "/topprod/dibluri", label: "Top 15 Dibluri" },
            { kind: "leaf", to: "/topprod/varsaci", label: "Top 15 Vărsaci" },
          ],
    },
    { kind: "divider" },
  ];

  if (scope === "adeplast") {
    tree.push(
      { kind: "leaf", to: "/mortar", label: "Mortare Silozuri (Vrac)" },
      { kind: "leaf", to: "/eps", label: "EPS Detalii (Val + Cant)" },
      { kind: "leaf", to: "/privatelabel", label: "Marca Privata" },
    );
  }
  tree.push(
    { kind: "divider" },
    {
      kind: "leaf",
      to: "/forecast",
      label: "📈 Prognoză Vânzări",
      highlight: true,
    },
  );

  return tree;
}

function buildSettingsTree(isAdmin: boolean): NavItem[] {
  const tree: NavItem[] = [
    {
      kind: "parent",
      id: "settings-upload",
      label: "Upload Date",
      children: [
        { kind: "leaf", to: "/settings/upload-adp", label: "Upload Date Brute (ADP)" },
        { kind: "leaf", to: "/settings/upload-sika", label: "Upload Sika Excel" },
        { kind: "leaf", to: "/settings/upload-sika-mtd", label: "Upload Vz MTD (SIKA)" },
        { kind: "leaf", to: "/settings/upload-orders-adp", label: "Upload Comenzi Open (ADP)" },
        { kind: "leaf", to: "/settings/upload-orders-sika", label: "Upload Comenzi Open (SIKA)" },
      ],
    },
    {
      kind: "parent",
      id: "settings-mapari",
      label: "Mapări KA",
      children: [
        { kind: "leaf", to: "/settings/mappings", label: "Magazine & Agenți (tabel)" },
        { kind: "leaf", to: "/settings/allocate-agents", label: "Alocă agenți (nealocate)" },
        { kind: "leaf", to: "/unmapped/products", label: "Produse nemapate" },
      ],
    },
    {
      kind: "parent",
      id: "settings-integrations",
      label: "Integrări",
      children: [
        { kind: "leaf", to: "/settings/ai-keys", label: "🔑 Chei AI" },
      ],
    },
    {
      kind: "parent",
      id: "settings-aspect",
      label: "Aspect",
      children: [
        { kind: "leaf", to: "/settings/appearance", label: "🎨 Font & Zoom" },
      ],
    },
    {
      kind: "parent",
      id: "settings-canonice",
      label: "Entități Canonice",
      children: [
        { kind: "leaf", to: "/stores", label: "Magazine (read-only)" },
        { kind: "leaf", to: "/agents", label: "Agenți (read-only)" },
        { kind: "leaf", to: "/products", label: "Produse" },
      ],
    },
  ];
  if (isAdmin) {
    tree.push({
      kind: "parent",
      id: "settings-admin",
      label: "Admin",
      children: [
        { kind: "leaf", to: "/users", label: "Utilizatori" },
        { kind: "leaf", to: "/audit-logs", label: "Activitate Utilizatori" },
        { kind: "leaf", to: "/api-keys", label: "API keys" },
        { kind: "leaf", to: "/settings", label: "Setări Organizație" },
      ],
    });
  } else {
    tree.push({
      kind: "parent",
      id: "settings-cont",
      label: "Cont",
      children: [{ kind: "leaf", to: "/users", label: "Utilizatori" }],
    });
  }
  return tree;
}

// ─────────────────────────────────────────────────────────────────────

const EXPANDED_LS_KEY = "adeplast_sidebar_expanded";

function loadExpandedState(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(EXPANDED_LS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}

export function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const { scope, setScope, inSettings, enterSettings } = useCompanyScope();
  const scopeTitle =
    scope === "adeplast" ? "Adeplast Dashboard"
    : scope === "sika" ? "Sika Dashboard"
    : "SikaDP Dashboard";
  const location = useLocation();
  const isAdmin = user?.role === "admin";

  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(() =>
    window.matchMedia("(max-width: 768px)").matches,
  );
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() =>
    loadExpandedState(),
  );

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    const onChange = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname, scope, inSettings]);

  useEffect(() => {
    try {
      localStorage.setItem(EXPANDED_LS_KEY, JSON.stringify(expanded));
    } catch {
      /* ignore quota errors */
    }
  }, [expanded]);

  const navTree = useMemo<NavItem[]>(() => {
    if (inSettings) return buildSettingsTree(Boolean(isAdmin));
    if (scope === "sikadp") return buildSikadpTree();
    return buildCompanyTree(scope);
  }, [scope, inSettings, isAdmin]);

  const activeParentId = useMemo(() => {
    for (const item of navTree) {
      if (item.kind !== "parent") continue;
      if (
        item.children.some((c) =>
          c.to === "/" ? location.pathname === "/" : location.pathname.startsWith(c.to),
        )
      ) {
        return item.id;
      }
    }
    return null;
  }, [navTree, location.pathname]);

  const isExpanded = useCallback(
    (id: string) => {
      if (expanded[id] !== undefined) return expanded[id];
      return id === activeParentId;
    },
    [expanded, activeParentId],
  );

  const toggleExpanded = useCallback((id: string) => {
    setExpanded((prev) => {
      const current = prev[id] !== undefined ? prev[id] : false;
      return { ...prev, [id]: !current };
    });
  }, []);

  const sidebarVisible = !isMobile || mobileOpen;

  return (
    <div
      style={{
        fontFamily: "var(--font-stack)",
        minHeight: "100vh",
        background: "var(--bg)",
        color: "var(--fg)",
      }}
    >
      <a href="#main-content" className="skip-link" style={styles.skipLink}>
        Sari la conținutul principal
      </a>
      {isMobile && (
        <div style={styles.mobileBar}>
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            style={styles.burger}
            aria-label={mobileOpen ? "Închide meniul" : "Deschide meniul"}
            aria-expanded={mobileOpen}
          >
            ☰
          </button>
          <strong style={{ fontSize: 14, color: "var(--cyan)" }}>
            {scopeTitle}
          </strong>
        </div>
      )}
      <div
        style={{
          ...styles.layout,
          gridTemplateColumns: isMobile ? "minmax(0, 1fr)" : "var(--sidebar-w) minmax(0, 1fr)",
        }}
      >
        {isMobile && mobileOpen && (
          <div
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
            style={{
              position: "fixed",
              top: 48,
              left: 280,
              right: 0,
              bottom: 0,
              background: "rgba(0,0,0,0.3)",
              zIndex: 99,
            }}
          />
        )}
        {sidebarVisible && (
          <aside
            style={{
              ...styles.sidebar,
              ...(isMobile ? styles.sidebarMobile : {}),
            }}
          >
            <CompanySwitcher
              scope={scope}
              inSettings={inSettings}
              onSelectCompany={setScope}
              onEnterSettings={enterSettings}
            />
            <div style={styles.brand}>{scopeTitle}</div>
            <nav style={styles.nav}>
              {navTree.map((item, idx) => {
                if (item.kind === "divider") {
                  return <div key={`div-${idx}`} style={styles.divider} />;
                }
                if (item.kind === "leaf") {
                  return (
                    <LeafLink
                      key={item.to}
                      to={item.to}
                      end={item.end}
                      labelColor={item.labelColor}
                      highlight={item.highlight}
                    >
                      {item.label}
                    </LeafLink>
                  );
                }
                return (
                  <TreeParent
                    key={item.id}
                    label={item.label}
                    expanded={isExpanded(item.id)}
                    onToggle={() => toggleExpanded(item.id)}
                  >
                    {item.children.map((c) => (
                      <LeafLink key={c.to} to={c.to} child>
                        {c.label}
                      </LeafLink>
                    ))}
                  </TreeParent>
                );
              })}
            </nav>
            <div style={styles.sidebarFooter}>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--muted)",
                  wordBreak: "break-all",
                }}
              >
                {user?.email}
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button onClick={() => void logout()} style={styles.logoutBtn}>
                  Ieși
                </button>
                <button
                  onClick={toggle}
                  style={styles.logoutBtn}
                  title="Temă"
                  aria-label={
                    theme === "dark"
                      ? "Schimbă la temă luminoasă"
                      : "Schimbă la temă întunecată"
                  }
                >
                  {theme === "dark" ? "☀" : "☾"}
                </button>
              </div>
            </div>
          </aside>
        )}
        <main id="main-content" style={styles.main} tabIndex={-1}>
          {children}
        </main>
      </div>
      <PageCaptureFab />
    </div>
  );
}

/**
 * Company switcher — cele 4 butoane în grila de sus. Culorile active
 * replică legacy buildSidebar / switchCompany (linii 1506–1542):
 *   ADEPLAST active  → #1A5C8A (albastru)
 *   SIKA active      → #C8102E (roșu)
 *   SIKADP active    → #6B21A8 (violet)
 *   SETTINGS active  → #475569 (slate)
 *   Inactive        → #333 bg / #888 text
 */
function CompanySwitcher({
  scope,
  inSettings,
  onSelectCompany,
  onEnterSettings,
}: {
  scope: CompanyScope;
  inSettings: boolean;
  onSelectCompany: (s: CompanyScope) => void;
  onEnterSettings: () => void;
}) {
  const btns: Array<{
    value: CompanyScope | "settings";
    label: string;
    activeBg: string;
  }> = [
    { value: "adeplast", label: "ADEPLAST", activeBg: "#1A5C8A" },
    { value: "sika", label: "SIKA", activeBg: "#C8102E" },
    { value: "sikadp", label: "SIKADP", activeBg: "#6B21A8" },
    { value: "settings", label: "⚙", activeBg: "#475569" },
  ];
  return (
    <div style={styles.switcherRow}>
      {btns.map((b) => {
        const isActive =
          b.value === "settings" ? inSettings : !inSettings && b.value === scope;
        return (
          <button
            key={b.value}
            onClick={() => {
              if (b.value === "settings") onEnterSettings();
              else onSelectCompany(b.value as CompanyScope);
            }}
            style={{
              ...styles.switcherBtn,
              background: isActive ? b.activeBg : "#333",
              color: isActive ? "#fff" : "#888",
              fontWeight: isActive ? 700 : 500,
            }}
            aria-pressed={isActive}
            title={b.label}
          >
            {b.label}
          </button>
        );
      })}
    </div>
  );
}

function TreeParent({
  label,
  expanded,
  onToggle,
  children,
}: {
  label: string;
  expanded: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        style={styles.treeParent}
        aria-expanded={expanded}
      >
        <span
          style={{
            ...styles.treeArrow,
            transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
          }}
          aria-hidden
        >
          ▸
        </span>
        <span>{label}</span>
      </button>
      {expanded && <div style={{ marginBottom: 2 }}>{children}</div>}
    </div>
  );
}

function LeafLink({
  to,
  end,
  child,
  labelColor,
  highlight,
  children,
}: {
  to: string;
  end?: boolean;
  child?: boolean;
  labelColor?: string;
  highlight?: boolean;
  children: ReactNode;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      style={({ isActive }) => {
        const base: CSSProperties = {
          display: "block",
          padding: child ? "6px 16px 6px 36px" : "8px 16px 8px 24px",
          fontSize: 13,
          textDecoration: "none",
          borderLeft: isActive
            ? "3px solid var(--cyan)"
            : "3px solid transparent",
          fontWeight: isActive ? 600 : child ? 400 : 600,
        };
        const color = isActive
          ? "var(--cyan)"
          : labelColor
            ? labelColor
            : child
              ? "var(--muted)"
              : "var(--text)";
        const background = isActive
          ? "var(--accent-soft)"
          : highlight
            ? "linear-gradient(90deg, rgba(34,211,238,0.08), transparent)"
            : "transparent";
        return {
          ...base,
          color,
          background,
          ...(highlight && !isActive
            ? { borderLeft: "3px solid var(--cyan)" }
            : {}),
        };
      }}
    >
      {children}
    </NavLink>
  );
}

const styles: Record<string, CSSProperties> = {
  layout: {
    display: "grid",
    gridTemplateColumns: "var(--sidebar-w) 1fr",
    minHeight: "100vh",
  },
  sidebar: {
    background: "var(--bg-sidebar)",
    borderRight: "1px solid var(--border)",
    padding: "0 0 12px",
    display: "flex",
    flexDirection: "column",
    position: "sticky",
    top: 0,
    height: "100vh",
    overflowY: "auto",
    color: "var(--text)",
  },
  sidebarMobile: {
    position: "fixed",
    top: 48,
    left: 0,
    width: 280,
    height: "calc(100vh - 48px)",
    zIndex: 100,
    boxShadow: "2px 0 10px rgba(0,0,0,0.35)",
  },
  mobileBar: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "8px 12px",
    background: "var(--bg-sidebar)",
    borderBottom: "1px solid var(--border)",
    position: "sticky",
    top: 0,
    zIndex: 99,
    height: 48,
  },
  burger: {
    fontSize: 20,
    padding: "4px 10px",
    cursor: "pointer",
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: 4,
    color: "var(--fg)",
  },
  switcherRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr auto",
    gap: 1,
    padding: 8,
    borderBottom: "1px solid var(--border)",
  },
  switcherBtn: {
    padding: "8px 10px",
    fontSize: 11,
    letterSpacing: "0.04em",
    border: "none",
    cursor: "pointer",
    borderRadius: 4,
  },
  brand: {
    fontWeight: 700,
    fontSize: 15,
    color: "var(--cyan)",
    padding: "14px 16px 10px",
    borderBottom: "1px solid var(--border)",
  },
  nav: {
    display: "flex",
    flexDirection: "column",
    padding: "4px 0",
    gap: 1,
    flex: 1,
  },
  divider: {
    borderTop: "1px solid var(--border)",
    margin: "8px 16px",
  },
  treeParent: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    width: "100%",
    padding: "8px 16px",
    fontSize: 13,
    fontWeight: 600,
    background: "transparent",
    color: "var(--text)",
    border: "none",
    borderLeft: "3px solid transparent",
    textAlign: "left",
    cursor: "pointer",
  },
  treeArrow: {
    fontSize: 10,
    color: "var(--muted)",
    transition: "transform 0.12s ease",
    display: "inline-block",
    width: 10,
  },
  main: {
    padding: "14px 20px",
    maxWidth: 1600,
    width: "100%",
  },
  skipLink: {
    position: "absolute",
    top: -40,
    left: 8,
    padding: "8px 16px",
    background: "var(--cyan)",
    color: "#000",
    textDecoration: "none",
    borderRadius: 4,
    fontSize: 13,
    zIndex: 10000,
    transition: "top 0.15s",
  },
  sidebarFooter: {
    marginTop: "auto",
    padding: "12px 16px",
    borderTop: "1px solid var(--border)",
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  logoutBtn: {
    padding: "6px 12px",
    fontSize: 12,
    cursor: "pointer",
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: 4,
    color: "var(--text)",
  },
};

import { Link } from "react-router-dom";
import type { CSSProperties } from "react";

/**
 * Hub Evaluare — o singură pagină cu două grupe de sub-meniuri:
 *  • Input Date (masterdata lunară: pachet salarial, km, bonusări raion)
 *  • Analiza    (rapoarte agregate: matricea agenți, detaliu & ranking zone)
 */
export default function EvaluareHubPage() {
  return (
    <div style={styles.wrap}>
      <h1 style={styles.title}>Evaluare</h1>
      <p style={styles.lead}>
        Evaluare agenți și zone: introduci datele lunar, apoi analizezi
        performanța, salarizarea și costurile operaționale per agent / zonă.
      </p>

      <h2 style={styles.section}>Input Date</h2>
      <div style={styles.grid}>
        <HubCard
          to="/evaluare/sal-fix"
          title="Imput sal fix"
          desc="Salariul fix per agent — constantă, cu marcarea ultimei modificări."
        />
        <HubCard
          to="/evaluare/input-lunar"
          title="Input Lunar Agent"
          desc="Km parcurși și preț carburant snapshot (per agent, per lună)."
        />
        <HubCard
          to="/evaluare/zona-agent"
          title="Imput bonus magazin"
          desc="Introduci bonusul per magazin. Vezi target și realizat per magazin; suma bonusurilor devine Bonus zonă în matricea lunară."
        />
      </div>

      <h2 style={styles.section}>Analiza</h2>
      <div style={styles.grid}>
        <HubCard
          to="/evaluare/matricea"
          title="Matricea Agenți"
          desc="Tabel KPI per agent: vânzări, salariu (fix+bonus), costuri, cost/100k."
        />
        <HubCard
          to="/evaluare/zona-detaliu"
          title="Detaliu Zonă"
          desc="Performanță magazine din zona unui agent (luna / YTD)."
          badge="soon"
        />
        <HubCard
          to="/evaluare/zona-ranking"
          title="Ranking Zone"
          desc="Clasament zone după vânzări, cost/100k și bonusări."
          badge="soon"
        />
      </div>
    </div>
  );
}

function HubCard({
  to, title, desc, badge,
}: { to: string; title: string; desc: string; badge?: string }) {
  return (
    <Link to={to} style={styles.card}>
      <div style={styles.cardHead}>
        <span style={styles.cardTitle}>{title}</span>
        {badge && <span style={styles.badge}>{badge}</span>}
      </div>
      <span style={styles.cardDesc}>{desc}</span>
    </Link>
  );
}

const styles: Record<string, CSSProperties> = {
  wrap: { padding: "24px 8px", maxWidth: 1100 },
  title: { fontSize: 22, fontWeight: 700, color: "var(--cyan)", margin: "0 0 8px" },
  lead: { color: "var(--muted)", fontSize: 13, lineHeight: 1.6, margin: "0 0 24px" },
  section: {
    fontSize: 13,
    fontWeight: 700,
    color: "var(--muted)",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    margin: "20px 0 10px",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
    gap: 12,
  },
  card: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    padding: "14px 16px",
    background: "var(--bg-panel)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    textDecoration: "none",
    color: "var(--text)",
  },
  cardHead: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 },
  cardTitle: { fontSize: 14, fontWeight: 700, color: "var(--cyan)" },
  cardDesc: { fontSize: 12, color: "var(--muted)", lineHeight: 1.5 },
  badge: {
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    padding: "2px 6px",
    background: "rgba(234,179,8,0.15)",
    color: "#fbbf24",
    border: "1px solid rgba(234,179,8,0.35)",
    borderRadius: 4,
  },
};

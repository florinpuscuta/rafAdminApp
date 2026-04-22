import { useLocation } from "react-router-dom";

/**
 * Placeholder page for legacy features still to be migrated into the SaaS
 * rewrite. Preserves the visual shell (dark theme, sidebar active state)
 * while signaling "not yet wired up".
 */
export default function ComingSoonPage({ title }: { title?: string }) {
  const location = useLocation();
  const label = title ?? location.pathname;
  return (
    <div
      style={{
        padding: "48px 24px",
        maxWidth: 720,
        margin: "0 auto",
        textAlign: "center",
      }}
    >
      <div
        style={{
          fontSize: 13,
          color: "var(--muted)",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          marginBottom: 8,
        }}
      >
        În curs de implementare
      </div>
      <h1
        style={{
          fontSize: 24,
          fontWeight: 700,
          color: "var(--cyan)",
          margin: "0 0 16px",
        }}
      >
        {label}
      </h1>
      <p style={{ color: "var(--muted)", fontSize: 14, lineHeight: 1.6 }}>
        Această pagină migrează în curând din aplicația anterioară. Restul
        aplicației funcționează normal.
      </p>
    </div>
  );
}

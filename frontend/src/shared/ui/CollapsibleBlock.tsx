import { useState } from "react";

/**
 * Bloc cu header clicabil care expandează/implodează conținutul.
 * Folosit pentru gruparea pe categorii/TM/subgrupe în paginile de prețuri.
 */
export function CollapsibleBlock({
  title,
  subtitle,
  defaultOpen = false,
  level = 0,
  children,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  defaultOpen?: boolean;
  /** 0 = category, 1 = subgroup. Afectează padding și font size. */
  level?: 0 | 1;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  const headerStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: level === 0 ? "4px 0 8px" : "2px 0 4px",
    cursor: "pointer",
    userSelect: "none",
  };

  const titleStyle: React.CSSProperties = {
    fontSize: level === 0 ? 14 : 13,
    fontWeight: level === 0 ? 700 : 600,
    color: "var(--text)",
  };

  const chevronStyle: React.CSSProperties = {
    display: "inline-block",
    width: 14,
    transition: "transform 0.15s",
    transform: open ? "rotate(90deg)" : "rotate(0deg)",
    color: "var(--fg-muted, #888)",
    fontSize: 11,
  };

  return (
    <div>
      <div style={headerStyle} onClick={() => setOpen((v) => !v)}>
        <span style={chevronStyle}>▶</span>
        <span style={titleStyle}>{title}</span>
        {subtitle && (
          <span style={{ color: "var(--fg-muted, #888)", fontSize: level === 0 ? 12 : 11 }}>
            {subtitle}
          </span>
        )}
      </div>
      {open && <div>{children}</div>}
    </div>
  );
}

import type { CSSProperties } from "react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  /** Numărul total de rânduri înainte de filtru (pentru hint „X din Y"). */
  total?: number;
  /** Numărul după filtru (afișat doar dacă diferă de total). */
  visible?: number;
  style?: CSSProperties;
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Caută…",
  total,
  visible,
  style,
}: Props) {
  const filtering = value.trim().length > 0;
  const showCounter = filtering && total != null && visible != null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, ...style }}>
      <input
        type="search"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          padding: "6px 10px",
          fontSize: 13,
          border: "1px solid var(--border, #ccc)",
          borderRadius: 4,
          background: "var(--bg-elevated, #fff)",
          color: "var(--fg, inherit)",
          width: 260,
          maxWidth: "100%",
        }}
      />
      {filtering && (
        <button
          onClick={() => onChange("")}
          style={{
            padding: "4px 10px",
            fontSize: 12,
            cursor: "pointer",
            background: "transparent",
            border: "1px solid var(--border, #ccc)",
            borderRadius: 4,
            color: "var(--fg-muted, #666)",
          }}
        >
          Șterge
        </button>
      )}
      {showCounter && (
        <span style={{ fontSize: 12, color: "var(--fg-muted, #666)" }}>
          {visible} din {total}
        </span>
      )}
    </div>
  );
}

/** Normalize pentru comparație „fuzzy" (lowercase, fără diacritice, trim). */
export function norm(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
}

import type { CSSProperties } from "react";

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  radius?: string | number;
  style?: CSSProperties;
}

/**
 * Primitiv skeleton: dreptunghi cu gradient animat.
 * Respectă dark mode via var(--bg-skeleton) / var(--bg-skeleton-highlight).
 */
export function Skeleton({
  width = "100%",
  height = 14,
  radius = 4,
  style,
}: SkeletonProps) {
  return (
    <span
      aria-hidden
      style={{
        display: "inline-block",
        width,
        height,
        borderRadius: radius,
        background:
          "linear-gradient(90deg, var(--skeleton-base, #e5e7eb) 0%, var(--skeleton-highlight, #f3f4f6) 50%, var(--skeleton-base, #e5e7eb) 100%)",
        backgroundSize: "200% 100%",
        animation: "skeleton-shimmer 1.2s ease-in-out infinite",
        ...style,
      }}
    />
  );
}

interface TableSkeletonProps {
  rows?: number;
  cols?: number;
  /** Lățimi procentuale per coloană (opțional). */
  colWidths?: string[];
}

/** Schelet pentru un tabel: `rows` × `cols` celule. */
export function TableSkeleton({ rows = 5, cols = 4, colWidths }: TableSkeletonProps) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r}>
            {Array.from({ length: cols }).map((_, c) => (
              <td
                key={c}
                style={{
                  padding: "8px 12px",
                  borderBottom: "1px solid var(--border, #f3f4f6)",
                  width: colWidths?.[c],
                }}
              >
                <Skeleton width={c === 0 ? "80%" : `${60 + (r % 3) * 10}%`} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Schelet pentru un card/bloc de statistici (2–3 linii). */
export function CardSkeleton() {
  return (
    <div style={{ padding: 16, border: "1px solid var(--border, #eee)", borderRadius: 6 }}>
      <Skeleton width="40%" height={12} />
      <div style={{ marginTop: 10 }}>
        <Skeleton width="70%" height={22} />
      </div>
      <div style={{ marginTop: 8 }}>
        <Skeleton width="50%" height={11} />
      </div>
    </div>
  );
}

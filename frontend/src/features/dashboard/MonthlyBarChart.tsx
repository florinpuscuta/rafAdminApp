import type { MonthTotalRow } from "./types";

const MONTH_LABELS = ["Ian","Feb","Mar","Apr","Mai","Iun","Iul","Aug","Sep","Oct","Noi","Dec"];

function fmtShort(amount: number): string {
  if (amount >= 1_000_000) return `${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `${(amount / 1_000).toFixed(0)}k`;
  return String(Math.round(amount));
}

interface Props {
  data: MonthTotalRow[];
  compare?: MonthTotalRow[] | null;
  cyLabel?: string;
  pyLabel?: string;
}

export default function MonthlyBarChart({
  data,
  compare,
  cyLabel = "An curent",
  pyLabel = "An anterior",
}: Props) {
  const cyValues = data.map((d) => Number(d.totalAmount) || 0);
  const pyMap = new Map<number, number>(
    (compare ?? []).map((m) => [m.month, Number(m.totalAmount) || 0]),
  );
  const pyValues = data.map((d) => pyMap.get(d.month) ?? 0);
  const hasCompare = !!compare && compare.length > 0;
  const max = Math.max(...cyValues, ...pyValues, 1);

  const width = 640;
  const height = 220;
  const padding = { top: 30, right: 10, bottom: 28, left: 50 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;
  const groupGap = 10;
  const groupW = (chartW - groupGap * 11) / 12;
  const barW = hasCompare ? (groupW - 2) / 2 : groupW;

  return (
    <div style={{ background: "#fff", padding: 16, border: "1px solid #eee", borderRadius: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Vânzări lunare</h3>
        {hasCompare && (
          <div style={{ fontSize: 12, display: "flex", gap: 12 }}>
            <span><Swatch color="#2563eb" /> {cyLabel}</span>
            <span><Swatch color="#cbd5e1" /> {pyLabel}</span>
          </div>
        )}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "auto" }}>
        <text x={padding.left - 6} y={padding.top + 10} fontSize={11} fill="#888" textAnchor="end">
          {fmtShort(max)}
        </text>
        <text x={padding.left - 6} y={padding.top + chartH} fontSize={11} fill="#888" textAnchor="end">
          0
        </text>
        <line
          x1={padding.left}
          x2={padding.left + chartW}
          y1={padding.top + chartH}
          y2={padding.top + chartH}
          stroke="#ddd"
        />
        {data.map((d, i) => {
          const cy = cyValues[i];
          const py = pyValues[i];
          const groupX = padding.left + i * (groupW + groupGap);
          const cyH = (cy / max) * chartH;
          const pyH = (py / max) * chartH;
          const cyX = hasCompare ? groupX : groupX;
          const pyX = hasCompare ? groupX + barW + 2 : groupX;
          return (
            <g key={d.month}>
              <rect
                x={cyX}
                y={padding.top + chartH - cyH}
                width={barW}
                height={cyH}
                fill={cy > 0 ? "#2563eb" : "#eee"}
                rx={2}
              />
              {hasCompare && (
                <rect
                  x={pyX}
                  y={padding.top + chartH - pyH}
                  width={barW}
                  height={pyH}
                  fill={py > 0 ? "#cbd5e1" : "#f3f4f6"}
                  rx={2}
                />
              )}
              {cy > 0 && (
                <text
                  x={cyX + barW / 2}
                  y={padding.top + chartH - cyH - 3}
                  fontSize={9}
                  fill="#444"
                  textAnchor="middle"
                >
                  {fmtShort(cy)}
                </text>
              )}
              <text
                x={groupX + groupW / 2}
                y={padding.top + chartH + 14}
                fontSize={11}
                fill="#666"
                textAnchor="middle"
              >
                {MONTH_LABELS[i]}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function Swatch({ color }: { color: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 10,
        height: 10,
        background: color,
        borderRadius: 2,
        marginRight: 4,
        verticalAlign: "middle",
      }}
    />
  );
}

import { Fragment, useEffect, useMemo, useState } from "react";

import { useCompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { ApiError } from "../../shared/api";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { norm, SearchInput } from "../../shared/ui/SearchInput";
import { getComenziFaraInd } from "./api";
import type {
  AgentGroup,
  ComenziFaraIndResponse,
  OrderRow,
  ProductLine,
} from "./types";

function toNum(v: string | number | null | undefined): number {
  if (v == null) return 0;
  const n = typeof v === "number" ? v : parseFloat(v);
  return Number.isFinite(n) ? n : 0;
}

function fmtRo(n: number): string {
  return new Intl.NumberFormat("ro-RO", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  }).format(n);
}

function fmtDateRo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("ro-RO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function statusColor(status: string | null): string {
  if (!status) return "var(--muted)";
  const s = status.toUpperCase();
  if (s === "NELIVRAT") return "var(--orange)";
  if (s === "NEFACTURAT") return "var(--accent)";
  return "var(--muted)";
}

export default function ComenziFaraIndPage() {
  const { scope: companyScope } = useCompanyScope();
  const [data, setData] = useState<ComenziFaraIndResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [openAgents, setOpenAgents] = useState<Record<string, boolean>>({});
  const [openOrders, setOpenOrders] = useState<Record<string, boolean>>({});

  const isAdp = companyScope === "adeplast";

  useEffect(() => {
    if (!isAdp) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getComenziFaraInd({ scope: "adp" })
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isAdp]);

  const filteredAgents = useMemo<AgentGroup[]>(() => {
    if (!data) return [];
    const q = norm(search);
    if (!q) return data.agents;
    return data.agents
      .map((a) => {
        const agentHit = norm(a.agentName).includes(q);
        const keptOrders = a.orders.filter((o) =>
          norm(
            [
              o.nrComanda ?? "",
              o.clientRaw,
              o.shipTo ?? "",
              o.storeName ?? "",
              o.status ?? "",
            ].join(" "),
          ).includes(q),
        );
        if (agentHit) return a;
        if (keptOrders.length > 0) return { ...a, orders: keptOrders };
        return null;
      })
      .filter((a): a is AgentGroup => a !== null);
  }, [data, search]);

  const visibleOrderCount = useMemo(
    () => filteredAgents.reduce((sum, a) => sum + a.orders.length, 0),
    [filteredAgents],
  );

  if (!isAdp) {
    return (
      <div style={styles.page}>
        <h1 style={styles.title}>Comenzi fără IND</h1>
        <div style={styles.infoBox}>
          IND e specific Adeplast — schimbă scope-ul companiei la{" "}
          <strong>Adeplast</strong> din bara laterală pentru a vedea lista.
        </div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <div>
          <h1 style={styles.title}>Comenzi fără IND</h1>
          <div style={styles.subtitle}>
            Snapshot: <strong>{fmtDateRo(data?.reportDate ?? null)}</strong>
            {data && (
              <>
                {" · "}
                <span>
                  <strong>{data.totalOrders}</strong> comenzi
                </span>
                {" · "}
                <span>
                  Rămas:{" "}
                  <strong>{fmtRo(toNum(data.totalRemaining))} RON</strong>
                </span>
              </>
            )}
          </div>
        </div>
        {data && data.agents.length > 0 && (
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Caută agent, comandă, client…"
            total={data.totalOrders}
            visible={visibleOrderCount}
          />
        )}
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {loading && !data && <TableSkeleton rows={6} cols={6} />}

      {data && data.agents.length === 0 && !loading && (
        <div style={styles.infoBox}>Nicio comandă fără IND. 🎉</div>
      )}

      {data && filteredAgents.length > 0 && (
        <div style={styles.card}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={{ ...styles.th, width: 32 }}></th>
                <th style={styles.th}>AGENT / COMANDĂ</th>
                <th style={styles.th}>CLIENT / MAGAZIN</th>
                <th style={styles.th}>STATUS</th>
                <th style={styles.thNum}>COMENZI / LINII</th>
                <th style={styles.thNum}>TOTAL</th>
                <th style={styles.thNum}>RĂMAS</th>
              </tr>
            </thead>
            <tbody>
              {filteredAgents.map((agent) => {
                const akey = agent.agentId ?? "nemapat";
                const aopen = openAgents[akey] ?? true;
                return (
                  <Fragment key={`agent-${akey}`}>
                    <tr
                      style={styles.agentRow}
                      onClick={() =>
                        setOpenAgents((s) => ({ ...s, [akey]: !aopen }))
                      }
                    >
                      <td style={styles.tdChevron}>{aopen ? "▾" : "▸"}</td>
                      <td style={styles.tdAgent} colSpan={2}>
                        {agent.agentName}
                      </td>
                      <td style={styles.td}></td>
                      <td style={styles.tdNum}>{agent.ordersCount}</td>
                      <td style={styles.tdNum}>
                        {fmtRo(toNum(agent.totalAmount))}
                      </td>
                      <td style={styles.tdNumStrong}>
                        {fmtRo(toNum(agent.totalRemaining))}
                      </td>
                    </tr>
                    {aopen &&
                      agent.orders.map((o, idx) => {
                        const okey = `${akey}-${o.nrComanda ?? idx}`;
                        const oopen = openOrders[okey] ?? false;
                        return (
                          <OrderBlock
                            key={okey}
                            order={o}
                            open={oopen}
                            onToggle={() =>
                              setOpenOrders((s) => ({ ...s, [okey]: !oopen }))
                            }
                          />
                        );
                      })}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function OrderBlock({
  order,
  open,
  onToggle,
}: {
  order: OrderRow;
  open: boolean;
  onToggle: () => void;
}) {
  const sColor = statusColor(order.status);
  return (
    <>
      <tr style={styles.orderRow} onClick={onToggle}>
        <td style={styles.tdChevron2}>{open ? "▾" : "▸"}</td>
        <td style={styles.tdOrderNum}>
          {order.nrComanda ?? <em>(fără nr.)</em>}
        </td>
        <td style={styles.tdClient}>
          <div>{order.clientRaw}</div>
          {order.storeName && order.storeName !== "— nemapat —" && (
            <div style={styles.subText}>→ {order.storeName}</div>
          )}
        </td>
        <td style={styles.td}>
          <span
            style={{
              display: "inline-block",
              padding: "2px 8px",
              fontSize: 11,
              fontWeight: 600,
              color: sColor,
              background: "var(--accent-soft)",
              borderRadius: 4,
            }}
          >
            {order.status ?? "—"}
          </span>
        </td>
        <td style={styles.tdNum}>{order.lineItemsCount}</td>
        <td style={styles.tdNum}>{fmtRo(toNum(order.totalAmount))}</td>
        <td style={styles.tdNumStrong}>
          {fmtRo(toNum(order.totalRemaining))}
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={7} style={styles.productsCell}>
            <ProductsTable
              products={order.products}
              dataLivrare={order.dataLivrare}
            />
          </td>
        </tr>
      )}
    </>
  );
}

function ProductsTable({
  products,
  dataLivrare,
}: {
  products: ProductLine[];
  dataLivrare: string | null;
}) {
  return (
    <div style={styles.productsWrap}>
      <div style={styles.productsHeader}>
        {products.length} produs(e) · Livrare: {fmtDateRo(dataLivrare)}
      </div>
      <table style={styles.productsTable}>
        <thead>
          <tr>
            <th style={styles.pth}>COD</th>
            <th style={styles.pth}>PRODUS</th>
            <th style={styles.pthNum}>CANT.</th>
            <th style={styles.pthNum}>RĂMAS CANT.</th>
            <th style={styles.pthNum}>AMOUNT</th>
            <th style={styles.pthNum}>RĂMAS</th>
          </tr>
        </thead>
        <tbody>
          {products.map((p, i) => (
            <tr key={`${p.productCode ?? "n"}-${i}`}>
              <td style={styles.ptd}>{p.productCode ?? "—"}</td>
              <td style={styles.ptd}>{p.productName ?? "—"}</td>
              <td style={styles.ptdNum}>{fmtRo(toNum(p.quantity))}</td>
              <td style={styles.ptdNum}>
                {fmtRo(toNum(p.remainingQuantity))}
              </td>
              <td style={styles.ptdNum}>{fmtRo(toNum(p.amount))}</td>
              <td style={styles.ptdNumStrong}>
                {fmtRo(toNum(p.remainingAmount))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { padding: "4px 4px 20px", color: "var(--text)" },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-end",
    gap: 16,
    marginBottom: 16,
    flexWrap: "wrap",
  },
  title: {
    margin: 0,
    fontSize: 18,
    fontWeight: 600,
    color: "var(--text)",
  },
  subtitle: {
    fontSize: 12,
    color: "var(--muted)",
    marginTop: 4,
  },
  error: {
    color: "var(--red)",
    background: "rgba(220, 38, 38, 0.08)",
    padding: 12,
    borderRadius: 6,
    marginBottom: 12,
  },
  infoBox: {
    padding: 16,
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    fontSize: 13,
    color: "var(--muted)",
  },
  card: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    overflow: "hidden",
  },
  table: { width: "100%", borderCollapse: "collapse" },
  th: {
    textAlign: "left",
    padding: "10px 12px",
    fontSize: 10.5,
    fontWeight: 600,
    color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    letterSpacing: 0.4,
    textTransform: "uppercase",
    whiteSpace: "nowrap",
    background: "var(--bg)",
  },
  thNum: {
    textAlign: "right",
    padding: "10px 12px",
    fontSize: 10.5,
    fontWeight: 600,
    color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    letterSpacing: 0.4,
    textTransform: "uppercase",
    whiteSpace: "nowrap",
    background: "var(--bg)",
  },
  agentRow: { cursor: "pointer", background: "var(--accent-soft)" },
  tdChevron: {
    padding: "10px 8px 10px 14px",
    fontSize: 12,
    color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    width: 32,
  },
  tdChevron2: {
    padding: "8px 8px 8px 28px",
    fontSize: 12,
    color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    width: 32,
  },
  tdAgent: {
    padding: "10px 12px",
    fontSize: 14,
    fontWeight: 600,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
  },
  orderRow: { cursor: "pointer" },
  tdOrderNum: {
    padding: "8px 12px",
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
    fontVariantNumeric: "tabular-nums",
  },
  tdClient: {
    padding: "8px 12px",
    fontSize: 13,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
  },
  subText: { fontSize: 11, color: "var(--muted)", marginTop: 2 },
  td: {
    padding: "8px 12px",
    fontSize: 13,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
  },
  tdNum: {
    padding: "8px 12px",
    fontSize: 13,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
  },
  tdNumStrong: {
    padding: "8px 12px",
    fontSize: 13,
    fontWeight: 600,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
  },
  productsCell: {
    padding: 0,
    background: "var(--bg)",
    borderBottom: "1px solid var(--border)",
  },
  productsWrap: { padding: "8px 12px 12px 56px" },
  productsHeader: {
    fontSize: 11,
    color: "var(--muted)",
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  productsTable: {
    width: "100%",
    borderCollapse: "collapse",
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 4,
  },
  pth: {
    textAlign: "left",
    padding: "6px 10px",
    fontSize: 10,
    fontWeight: 600,
    color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    letterSpacing: 0.4,
    textTransform: "uppercase",
    whiteSpace: "nowrap",
  },
  pthNum: {
    textAlign: "right",
    padding: "6px 10px",
    fontSize: 10,
    fontWeight: 600,
    color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    letterSpacing: 0.4,
    textTransform: "uppercase",
    whiteSpace: "nowrap",
  },
  ptd: {
    padding: "5px 10px",
    fontSize: 12,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
  },
  ptdNum: {
    padding: "5px 10px",
    fontSize: 12,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
  },
  ptdNumStrong: {
    padding: "5px 10px",
    fontSize: 12,
    fontWeight: 600,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
  },
};

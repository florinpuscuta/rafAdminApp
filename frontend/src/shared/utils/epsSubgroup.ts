/**
 * Helpers pentru împărțirea produselor EPS pe subgrupe (EPS 50, EPS 70, EPS 80, ...)
 * Mirror al logicii din backend: `_EPS_CLASS_RE` / `_eps_subgroup` din
 * `backend/app/modules/grupe_produse/service.py`.
 */

const EPS_CLASS_RE = /[Ee][Pp][Ss][ _\-]*(\d{2,3})/;

export function epsSubgroup(name: string | null | undefined): { key: string; label: string } {
  if (!name) return { key: "other", label: "Alte EPS" };
  const m = name.match(EPS_CLASS_RE);
  if (!m) return { key: "other", label: "Alte EPS" };
  const cls = m[1];
  return { key: `eps_${cls}`, label: `EPS ${cls}` };
}

export function isEpsCategory(cat: string | null | undefined): boolean {
  return !!cat && cat.trim().toUpperCase() === "EPS";
}

export interface EpsSubgroupBucket<T> {
  key: string;
  label: string;
  products: T[];
  totalSales: number;
}

/**
 * Împarte o listă de produse pe subgrupe EPS (key/label din nume) și sortează
 * bucketele descendent după suma `getSales(p)`.
 */
export function groupByEpsSubgroup<T>(
  products: T[],
  getName: (p: T) => string | null | undefined,
  getSales: (p: T) => number | string | null | undefined,
): EpsSubgroupBucket<T>[] {
  const map = new Map<string, EpsSubgroupBucket<T>>();
  for (const p of products) {
    const { key, label } = epsSubgroup(getName(p));
    let bucket = map.get(key);
    if (!bucket) {
      bucket = { key, label, products: [], totalSales: 0 };
      map.set(key, bucket);
    }
    bucket.products.push(p);
    const n = Number(getSales(p) ?? 0);
    if (Number.isFinite(n)) bucket.totalSales += n;
  }
  return Array.from(map.values()).sort((a, b) => b.totalSales - a.totalSales);
}

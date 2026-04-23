/**
 * Clasificare Target Market (TM) pentru produse Sika.
 *
 * Mirror al `_SIKA_TM_RULES` + `_classify_sika_tm` din
 * `backend/app/modules/grupe_produse/service.py`. Păstrează ordinea regulilor
 * — prima potrivire câștigă.
 */

type Rule = { label: string; re: RegExp };

const RULES: Rule[] = [
  // Rândurile "Customer Bonus <TM>" — redirecționăm direct după sufix.
  { label: "Building Finishing", re: /CUSTOMER\s+BONUS\s+BUILDING/i },
  { label: "Sealing & Bonding", re: /CUSTOMER\s+BONUS\s+SEALING/i },
  { label: "Waterproofing & Roofing", re: /CUSTOMER\s+BONUS\s+(WATERPROOF|ROOFING|REFURB)/i },
  { label: "Concrete & Anchors", re: /CUSTOMER\s+BONUS\s+CONCRETE/i },
  { label: "Flooring", re: /CUSTOMER\s+BONUS\s+FLOORING/i },

  {
    label: "Flooring",
    re: /SIKA\s*FLOOR|SIKA\s*SCREED|SIKA\s*LEVEL|S\s*-?\s*DRAIN|S\s*-?\s*SCUPPER|AIR\s*VENT|WATER\s*OUTLET|PIPE\s*CONNECTION|CAP\s+FOR\s+WATER/i,
  },
  {
    label: "Waterproofing & Roofing",
    re: /LASTIC|IGOL\s*FLEX|IGASOL|SARNA\s*VAP|SARNA\s*FIL|SARNA\s*COL|SIKA\s*PROOF|TOP\s*SEAL|SIKA\s*SWELL|SIKA\s*MUR|SIKA\s*WATERBAR|SIKA\s*WRAP|WATER\s*BAR|SIKA\s*DUR|SIKA\s*-?\s*1\b|ICOSIT|ARCO\s*(BITU|ELAST|SUPER|FORATO|THERMO)|ARTEC\s*\d|ARMEX|DECOBIT|ECOBIT|ELASTECH|FESTA\s+PLUS|SSH\s*(E|P|EKV|MG)|SIKA\s*-?\s*TROCAL|SR\s*(ADHESIVE|CLEANER|CORNER)|SIKA\s*(ANTISOL|CONTROL|PLAST|VISCO|EMACO|TOP\b|WT\b|-4A|GRUND)|MASTER\s*EMACO|METAL\s+SHEET/i,
  },
  {
    label: "Concrete & Anchors",
    re: /ANCHOR\s*FIX|SIKA\s*GROUT|MONO\s*TOP|SIKA\s*GARD|SIKA\s*PLASTIMENT|SIKA\s*LPS|SIKA\s*VZ|SIKA\s*FS|SIKA\s*CEM|SIKA\s*COSMETIC|SIKA\s*BETON|SIKA\s*LATEX|SIKA\s*PUMP/i,
  },
  {
    label: "Sealing & Bonding",
    re: /SIKA\s*(FLEX|SIL|BOND|TACK|BLACK\s*SEAL|BOOM|MULTI\s*SEAL|SEAL(TAPE|-)?|MAX\s*TACK|ACRYL|CRYL)|SIKA\s*BLACK|SIKAMAX|SIKA\s*SEAL|SANISIL|FUGENHINTER/i,
  },
  {
    label: "Building Finishing",
    re: /SIKA\s*CERAM|TILE\s*BOND|SIKA\s*WALL|SIKA\s*HOME|SIKA\s*THERM|INSULATE|SIKA\s*GREEN/i,
  },
  {
    label: "Industry & Accessories",
    re: /SIKA\s*PRIMER|AKTIVATOR|ACTIVATOR|SIKA\s*FIBER|QUARTZ|SF\s*TS|SIKA\s*LAYER|S\s*-?\s*GLASS|S\s*-?\s*FELT|SPL\b|SOLVENT|INJECTION|SIKA\s*SCHA?L|PACKER|PALLET|\bIBC\b|\bROL\b|SIKA\s*COLOR|SIKA\s*SET|SIKA\s*(THINNER|COR|SEPAROL|STELL|CARBO|COLMA|GRUND)|HARDRUBBER|DORR|DÖRR|SIKA\s*TR\s*\d|DISCOUNT|FREIGHT|CHARGES/i,
  },
];

export const SIKA_TM_ORDER = [
  "Building Finishing",
  "Sealing & Bonding",
  "Waterproofing & Roofing",
  "Concrete & Anchors",
  "Flooring",
  "Industry & Accessories",
  "Alte",
];

export function sikaTm(name: string | null | undefined): string {
  if (!name) return "Alte";
  for (const r of RULES) {
    if (r.re.test(name)) return r.label;
  }
  return "Alte";
}

export interface SikaTmBucket<T> {
  label: string;
  products: T[];
  totalSales: number;
}

/** Grupează produse pe TM Sika. Bucketele sunt sortate descendent după `getSales`. */
export function groupBySikaTm<T>(
  products: T[],
  getName: (p: T) => string | null | undefined,
  getSales: (p: T) => number | string | null | undefined,
): SikaTmBucket<T>[] {
  const map = new Map<string, SikaTmBucket<T>>();
  for (const p of products) {
    const label = sikaTm(getName(p));
    let bucket = map.get(label);
    if (!bucket) {
      bucket = { label, products: [], totalSales: 0 };
      map.set(label, bucket);
    }
    bucket.products.push(p);
    const n = Number(getSales(p) ?? 0);
    if (Number.isFinite(n)) bucket.totalSales += n;
  }
  return Array.from(map.values()).sort((a, b) => b.totalSales - a.totalSales);
}

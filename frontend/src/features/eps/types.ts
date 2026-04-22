export interface EpsMonthlyRow {
  category: "KA" | "RETAIL";
  month: number;
  monthName: string;
  qtyY1: string;  // Decimal → string (APISchema camelCase serialization)
  qtyY2: string;
  salesY1: string;
  salesY2: string;
}

export interface EpsDetailsResponse {
  y1: number;
  y2: number;
  rows: EpsMonthlyRow[];
}

export interface EpsClassRow {
  cls: string;   // "50", "70", "80", "100", "120", "150", "200", ...
  qtyY1: string;
  qtyY2: string;
  salesY1: string;
  salesY2: string;
}

export interface EpsBreakdownResponse {
  y1: number;
  y2: number;
  rows: EpsClassRow[];
}

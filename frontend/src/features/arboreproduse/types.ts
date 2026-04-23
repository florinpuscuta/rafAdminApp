export interface TreeProduct {
  productId: string;
  code: string;
  name: string;
  sales: string;
  qty: string;
  salesPrev: string;
  qtyPrev: string;
  avgPrice: string | null;
  avgPricePrev: string | null;
}

export interface TreeSubgroup {
  key: string;
  label: string;
  sales: string;
  qty: string;
  salesPrev: string;
  qtyPrev: string;
  avgPrice: string | null;
  avgPricePrev: string | null;
  products: TreeProduct[];
}

export interface TreeCategory {
  categoryId: string | null;
  code: string;
  label: string;
  sales: string;
  qty: string;
  salesPrev: string;
  qtyPrev: string;
  products: TreeProduct[];
  subgroups: TreeSubgroup[] | null;
}

export interface TreeBrand {
  brandId: string | null;
  name: string;
  isPrivateLabel: boolean;
  sales: string;
  qty: string;
  salesPrev: string;
  qtyPrev: string;
  categories: TreeCategory[];
}

export interface ArboreProduseResponse {
  scope: string;
  year: number;
  lastUpdate: string | null;
  brands: TreeBrand[];
  grandSales: string;
  grandQty: string;
  grandSalesPrev: string;
  grandQtyPrev: string;
  ytdMonths: number[];
  selectedMonths: number[];
}

export interface TreeClient {
  chain: string;
  sales: string;
  qty: string;
  salesPrev: string;
  qtyPrev: string;
  categories: TreeCategory[];
}

export interface ArboreClientiResponse {
  scope: string;
  year: number;
  lastUpdate: string | null;
  clients: TreeClient[];
  grandSales: string;
  grandQty: string;
  grandSalesPrev: string;
  grandQtyPrev: string;
  ytdMonths: number[];
  selectedMonths: number[];
}

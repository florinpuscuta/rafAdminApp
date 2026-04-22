export interface Product {
  id: string;
  code: string;
  name: string;
  category: string | null;
  brand: string | null;
  active: boolean;
  createdAt: string;
}

export interface ProductAlias {
  id: string;
  rawCode: string;
  productId: string;
  resolvedByUserId: string | null;
  resolvedAt: string;
}

export interface UnmappedProductRow {
  rawCode: string;
  sampleName: string | null;
  rowCount: number;
  totalAmount: string;
}

export interface CreateProductPayload {
  code: string;
  name: string;
  category?: string | null;
  brand?: string | null;
}

export interface CreateProductAliasPayload {
  rawCode: string;
  productId: string;
}

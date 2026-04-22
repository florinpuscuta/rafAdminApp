import { apiFetch } from "../../shared/api";
import type {
  CreateProductAliasPayload,
  CreateProductPayload,
  Product,
  ProductAlias,
  UnmappedProductRow,
} from "./types";

export function listProducts(): Promise<Product[]> {
  return apiFetch<Product[]>("/api/products");
}

export function createProduct(payload: CreateProductPayload): Promise<Product> {
  return apiFetch<Product>("/api/products", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listUnmappedProducts(): Promise<UnmappedProductRow[]> {
  return apiFetch<UnmappedProductRow[]>("/api/products/unmapped");
}

export function listProductAliases(): Promise<ProductAlias[]> {
  return apiFetch<ProductAlias[]>("/api/products/aliases");
}

export function createProductAlias(payload: CreateProductAliasPayload): Promise<ProductAlias> {
  return apiFetch<ProductAlias>("/api/products/aliases", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface MergeProductsResult {
  primaryId: string;
  mergedCount: number;
  aliasesReassigned: number;
  salesReassigned: number;
}

export function mergeProducts(
  primaryId: string,
  duplicateIds: string[],
): Promise<MergeProductsResult> {
  return apiFetch<MergeProductsResult>("/api/products/merge", {
    method: "POST",
    body: JSON.stringify({ primaryId, duplicateIds }),
  });
}

export function bulkSetActiveProducts(
  ids: string[],
  active: boolean,
): Promise<{ updated: number }> {
  return apiFetch<{ updated: number }>("/api/products/bulk-set-active", {
    method: "POST",
    body: JSON.stringify({ ids, active }),
  });
}

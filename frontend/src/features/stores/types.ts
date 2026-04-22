export interface Store {
  id: string;
  name: string;
  chain: string | null;
  city: string | null;
  active: boolean;
  createdAt: string;
}

export interface StoreAlias {
  id: string;
  rawClient: string;
  storeId: string;
  resolvedByUserId: string | null;
  resolvedAt: string;
}

export interface UnmappedClientRow {
  rawClient: string;
  rowCount: number;
  totalAmount: string;
}

export interface SuggestedMatch {
  storeId: string;
  storeName: string;
  score: number;
}

export interface SuggestionRow {
  rawClient: string;
  suggestions: SuggestedMatch[];
}

export interface CreateStorePayload {
  name: string;
  chain?: string | null;
  city?: string | null;
}

export interface CreateAliasPayload {
  rawClient: string;
  storeId: string;
}

/**
 * Tipuri pentru /api/marketing/catalog — Catalog Lunar.
 * Port 1:1 din legacy gallery (gallery_type='catalog').
 */

// ── Placeholder compat (folosit de vechiul ecran / tests) ──
export interface MktCatalogItem {
  id: string;
  title: string;
  month: string | null; // "YYYY-MM"
}

export interface MktCatalogResponse {
  items: MktCatalogItem[];
  notice: string | null;
}

// ── Noile schemes (folder/photo) ──
export interface CatalogFolder {
  id: string;
  name: string;
  month: string | null; // "YYYY-MM" extras din name
  photoCount: number;
  coverUrl: string | null;
  createdAt: string;
}

export interface CatalogFolderListResponse {
  folders: CatalogFolder[];
  notice: string | null;
}

export interface CatalogPhoto {
  id: string;
  folderId: string;
  filename: string;
  sizeKb: number;
  caption: string | null;
  uploadedByUserId: string | null;
  uploadedAt: string;
  url: string;
  thumbUrl: string;
}

export interface CatalogFolderDetail {
  folderId: string;
  folderName: string;
  month: string | null;
  photos: CatalogPhoto[];
}

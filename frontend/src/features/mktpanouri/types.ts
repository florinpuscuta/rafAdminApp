/**
 * Tipuri Panouri & Standuri — oglindă 1:1 legacy
 * `adeplast-dashboard/routes/gallery.py` (endpoints `/api/panouri/*`).
 */

export type UUID = string;

export interface StoreListItem {
  name: string;
  agent: string;
  client: string;
  shipTo: string;
  panelCount: number;
  photoCount: number;
}

export interface StoresResponse {
  ok: boolean;
  stores: StoreListItem[];
}

export interface PanouStandRow {
  id: UUID;
  storeName: string;
  panelType: string;
  title: string | null;
  widthCm: number | null;
  heightCm: number | null;
  locationInStore: string | null;
  notes: string | null;
  photoFilename: string | null;
  photoThumb: string | null;
  agent: string | null;
  createdBy: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface PhotoRow {
  id: UUID | null;
  filename: string;
  url: string;
  thumbUrl: string | null;
  sizeKb: number;
  notes: string | null;
  photoDate: string | null;
  uploadedBy: string | null;
  category: string | null;
}

export interface StoreDetailResponse {
  ok: boolean;
  store: string;
  panels: PanouStandRow[];
  photos: PhotoRow[];
}

export interface AddPanelPayload {
  panelType?: string;
  title?: string;
  widthCm?: number | null;
  heightCm?: number | null;
  locationInStore?: string;
  notes?: string;
}

export type UpdatePanelPayload = Partial<AddPanelPayload>;

/**
 * Tipuri pentru /api/marketing/concurenta — Acțiuni Concurență.
 * Shape camelCase, oglindă a schemelor din backend/mkt_concurenta/schemas.py.
 *
 * Port 1:1 al feature-ului legacy `renderConcurenta` din
 * adeplast-dashboard/templates/index.html (~line 12811).
 */

export interface ConcurentaMonthCell {
  month: number; // 1..12
  folderKey: string; // "YYYY_MM"
  label: string; // „Ianuarie", „Februarie", ...
  folderId: string | null;
  count: number;
  coverUrl: string | null;
  isFuture: boolean;
}

export interface ConcurentaYearResponse {
  year: number;
  cells: ConcurentaMonthCell[];
}

export interface ConcurentaFolderOut {
  id: string;
  folderKey: string;
  year: number;
  month: number;
  createdAt: string;
}

export interface ConcurentaPhotoOut {
  id: string;
  folderId: string;
  filename: string;
  contentType: string;
  sizeBytes: number;
  caption: string | null;
  uploadedAt: string;
  url: string;
  thumbUrl: string;
}

export interface ConcurentaPhotosResponse {
  folderKey: string;
  folderId: string;
  images: ConcurentaPhotoOut[];
}

export interface ConcurentaUploadResponse {
  uploaded: number;
  errors: string[];
  folderId: string;
}

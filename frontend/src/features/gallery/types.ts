export type FolderType = "magazine" | "catalog" | "competition" | "other";

export interface GalleryFolder {
  id: string;
  type: string;
  name: string;
  createdAt: string;
  photoCount: number;
}

export interface GalleryPhoto {
  id: string;
  folderId: string;
  filename: string;
  contentType: string;
  sizeBytes: number;
  caption: string | null;
  uploadedByUserId: string | null;
  uploadedAt: string;
  url: string;
}

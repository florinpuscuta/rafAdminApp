export type ProblemeScope = "adp" | "sika" | "sikadp";

export interface ProblemePhoto {
  id: string;
  url: string;
  uploadedBy: string | null;
  uploadedAt: string | null;
}

export interface ProblemeResponse {
  scope: ProblemeScope;
  year: number;
  month: number;
  monthName: string;
  content: string;
  updatedBy: string | null;
  updatedAt: string | null;
  photos: ProblemePhoto[];
  todo: string | null;
}

export interface ProblemeSaveRequest {
  scope: ProblemeScope;
  year: number;
  month: number;
  content: string;
}

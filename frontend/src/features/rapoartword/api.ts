/**
 * API client pentru /api/rapoarte/word.
 *
 * Endpoint-ul e POST și răspunde cu un Blob docx — nu JSON. Folosim `fetch`
 * direct pentru că helper-ul `apiFetch` asumă răspuns JSON. Autentificarea
 * o aplicăm manual pe baza bearer-ului din localStorage.
 */
import { ApiError, getToken } from "../../shared/api";
import type { RapoartWordRequest } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface GeneratedDocx {
  blob: Blob;
  /** Numele fișierului extras din Content-Disposition (fallback fix). */
  filename: string;
}

function parseFilename(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const match = /filename="?([^"]+)"?/i.exec(header);
  return match?.[1] ?? fallback;
}

export async function generateRapoartWord(
  body: RapoartWordRequest = {},
): Promise<GeneratedDocx> {
  const token = getToken();
  const resp = await fetch(`${API_URL}/api/rapoarte/word`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    // Backend-ul întoarce JSON pe erori standard (auth, validare).
    let message = `HTTP ${resp.status}`;
    let code: string | undefined;
    try {
      const data = await resp.json();
      message = data?.detail?.message ?? data?.detail ?? message;
      code = data?.detail?.code;
    } catch {
      // body-ul nu e JSON — lăsăm mesajul default.
    }
    throw new ApiError(resp.status, message, code);
  }

  const blob = await resp.blob();
  const filename = parseFilename(
    resp.headers.get("content-disposition"),
    "raport.docx",
  );
  return { blob, filename };
}

/** Helper pentru a forța download-ul în browser (creează <a download>). */
export function saveDocx({ blob, filename }: GeneratedDocx): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // `revokeObjectURL` imediat ar anula download-ul pe Safari — lăsăm 2s.
  setTimeout(() => URL.revokeObjectURL(url), 2_000);
}

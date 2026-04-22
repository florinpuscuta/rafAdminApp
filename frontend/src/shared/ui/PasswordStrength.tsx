import { useMemo } from "react";

interface Score {
  level: 0 | 1 | 2 | 3 | 4;
  label: string;
  color: string;
  hint: string;
}

/**
 * Heuristică simplă (nu înlocuiește zxcvbn, dar e suficientă pentru un
 * indicator vizual). Score 0..4 pe baza lungimii și a claselor de caractere.
 * Toate hint-urile sunt în română.
 */
export function scorePassword(pwd: string): Score {
  if (pwd.length === 0) {
    return { level: 0, label: "—", color: "#e5e7eb", hint: "" };
  }
  let score = 0;
  if (pwd.length >= 8) score += 1;
  if (pwd.length >= 12) score += 1;
  if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score += 1;
  if (/\d/.test(pwd)) score += 1;
  if (/[^A-Za-z0-9]/.test(pwd)) score += 1;
  // Penalizări pentru pattern-uri triviale
  if (/^(.)\1+$/.test(pwd) || /^(password|parola|12345|qwerty)/i.test(pwd)) {
    score = Math.max(0, score - 2);
  }
  // Plafonăm între 0 și 4
  const level = Math.min(4, Math.max(0, score)) as 0 | 1 | 2 | 3 | 4;

  const presets: Record<Score["level"], { label: string; color: string; hint: string }> = {
    0: { label: "foarte slabă", color: "#dc2626", hint: "Prea scurtă sau previzibilă." },
    1: { label: "slabă", color: "#ea580c", hint: "Adaugă caractere — minim 8." },
    2: { label: "medie", color: "#ca8a04", hint: "Adaugă cifre sau majuscule." },
    3: { label: "bună", color: "#16a34a", hint: "" },
    4: { label: "puternică", color: "#15803d", hint: "" },
  };
  const p = presets[level];
  return { level, label: p.label, color: p.color, hint: p.hint };
}

interface Props {
  password: string;
  /** Ascunde complet componentul dacă parola e goală. */
  hideWhenEmpty?: boolean;
}

export function PasswordStrength({ password, hideWhenEmpty = true }: Props) {
  const score = useMemo(() => scorePassword(password), [password]);
  if (hideWhenEmpty && password.length === 0) return null;

  return (
    <div style={{ marginTop: 6, fontSize: 12 }} aria-live="polite">
      <div style={{ display: "flex", gap: 3, marginBottom: 3 }}>
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 4,
              borderRadius: 2,
              background: i <= score.level ? score.color : "var(--border, #e5e7eb)",
              transition: "background 0.15s",
            }}
          />
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", color: "var(--fg-muted, #666)" }}>
        <span>Putere: <span style={{ color: score.color, fontWeight: 500 }}>{score.label}</span></span>
        {score.hint && <span>{score.hint}</span>}
      </div>
    </div>
  );
}

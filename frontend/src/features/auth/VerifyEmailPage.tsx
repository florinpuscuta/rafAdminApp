import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../shared/api";
import { confirmEmailVerify } from "./api";
import { useAuth } from "./AuthContext";

type Status = "pending" | "success" | "error";

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { refreshUser } = useAuth();
  const [status, setStatus] = useState<Status>("pending");
  const [error, setError] = useState<string | null>(null);
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;
    fired.current = true;

    if (!token) {
      setStatus("error");
      setError("Link-ul nu conține token.");
      return;
    }
    confirmEmailVerify(token)
      .then(async () => {
        setStatus("success");
        await refreshUser();
      })
      .catch((err) => {
        setStatus("error");
        setError(err instanceof ApiError ? err.message : "Eroare la verificare");
      });
  }, [token, refreshUser]);

  return (
    <div style={styles.wrap}>
      <div style={styles.box}>
        {status === "pending" && <p>Verific…</p>}
        {status === "success" && (
          <>
            <h1 style={styles.title}>Email verificat ✓</h1>
            <p style={{ fontSize: 14, color: "#555" }}>
              Poți continua să folosești aplicația.
            </p>
            <p style={styles.alt}>
              <Link to="/">Mergi la dashboard</Link>
            </p>
          </>
        )}
        {status === "error" && (
          <>
            <h1 style={styles.title}>Verificare eșuată</h1>
            <p style={{ color: "#b00020", fontSize: 14 }}>{error}</p>
            <p style={styles.alt}>
              <Link to="/login">Autentifică-te</Link> și cere un link nou din banner.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: { display: "flex", justifyContent: "center", padding: 48 },
  box: { width: 400, textAlign: "center" },
  title: { margin: 0 },
  alt: { fontSize: 14, margin: 0 },
};

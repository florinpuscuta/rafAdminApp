import { useState, type FormEvent } from "react";

import { ApiError } from "../../shared/api";
import { PasswordStrength } from "../../shared/ui/PasswordStrength";
import { useToast } from "../../shared/ui/ToastProvider";
import { changePassword } from "./api";

export default function ChangePasswordForm() {
  const toast = useToast();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();

    if (newPassword !== confirmPassword) {
      toast.error("Parolele noi nu se potrivesc");
      return;
    }

    setSubmitting(true);
    try {
      await changePassword({ oldPassword, newPassword });
      toast.success("Parola a fost actualizată.");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare la schimbarea parolei");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={styles.form}>
      <strong>Schimbă parola ta</strong>
      <div style={styles.row}>
        <input
          required
          type="password"
          placeholder="Parola actuală"
          value={oldPassword}
          onChange={(e) => setOldPassword(e.target.value)}
          style={{ ...styles.input, flex: 1 }}
        />
        <input
          required
          type="password"
          minLength={8}
          placeholder="Parolă nouă (min 8)"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          style={{ ...styles.input, flex: 1 }}
        />
        <input
          required
          type="password"
          minLength={8}
          placeholder="Confirmă parola nouă"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          style={{ ...styles.input, flex: 1 }}
        />
        <button type="submit" disabled={submitting} style={styles.btn}>
          {submitting ? "…" : "Schimbă"}
        </button>
      </div>
      {newPassword && <PasswordStrength password={newPassword} />}
    </form>
  );
}

const styles: Record<string, React.CSSProperties> = {
  form: {
    padding: 14,
    border: "1px solid #eee",
    borderRadius: 6,
    marginBottom: 16,
    background: "#fff",
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  row: { display: "flex", gap: 8 },
  input: { padding: 8, fontSize: 14, border: "1px solid #ccc", borderRadius: 4 },
  btn: { padding: "8px 16px", fontSize: 14, cursor: "pointer" },
  error: {
    padding: "6px 10px",
    background: "#ffebee",
    border: "1px solid #f5a2a8",
    borderRadius: 4,
    fontSize: 13,
    color: "#b00020",
  },
  success: {
    padding: "6px 10px",
    background: "#e6ffed",
    border: "1px solid #a6d8a8",
    borderRadius: 4,
    fontSize: 13,
    color: "#065f13",
  },
};

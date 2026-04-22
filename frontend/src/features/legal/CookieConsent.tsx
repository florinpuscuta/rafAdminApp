import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

const LS_KEY = "adeplast_cookie_consent";

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(LS_KEY)) {
      setVisible(true);
    }
  }, []);

  function handleAccept() {
    localStorage.setItem(LS_KEY, "accepted");
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div style={styles.wrap}>
      <div style={styles.text}>
        Folosim doar cookies strict necesare (sesiune login, preferințe UI).
        Nu folosim tracking de terți. Detalii în{" "}
        <Link to="/privacy" style={styles.link}>Politica de Confidențialitate</Link>.
      </div>
      <button onClick={handleAccept} style={styles.btn}>
        Am înțeles
      </button>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: {
    position: "fixed",
    bottom: 16,
    left: 16,
    right: 16,
    maxWidth: 640,
    margin: "0 auto",
    padding: "14px 18px",
    background: "var(--card)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    boxShadow: "0 10px 30px rgba(15, 23, 42, 0.15)",
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 14,
    zIndex: 10000,
  },
  text: { flex: "1 1 220px", fontSize: 13, lineHeight: 1.5 },
  link: { color: "var(--accent)", textDecoration: "underline", textUnderlineOffset: 2 },
  btn: {
    padding: "9px 18px",
    fontSize: 13,
    fontWeight: 600,
    background: "var(--accent)",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    boxShadow: "0 1px 2px rgba(0,0,0,0.1)",
  },
};

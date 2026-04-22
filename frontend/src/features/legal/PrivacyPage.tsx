export default function PrivacyPage() {
  return (
    <div style={styles.wrap}>
      <h1>Politica de Confidențialitate</h1>
      <p style={styles.meta}>Ultima actualizare: 20 aprilie 2026</p>

      <p>
        <strong>Adeplast SaaS</strong> ("noi", "platforma") respectă
        confidențialitatea datelor utilizatorilor săi. Acest document descrie
        ce date colectăm, cum le folosim și ce drepturi ai conform GDPR.
      </p>

      <h2>1. Ce date colectăm</h2>
      <ul>
        <li><strong>Date de cont</strong>: email, nume organizație, parolă (hashuită cu bcrypt).</li>
        <li><strong>Date de utilizare</strong>: log-uri de autentificare, adresa IP, user-agent — păstrate în audit log.</li>
        <li><strong>Date business</strong>: vânzările și mapping-urile pe care le încarci tu (Excel-uri, fotografii, etc.).</li>
      </ul>

      <h2>2. Cum folosim datele</h2>
      <ul>
        <li>Pentru a-ți furniza serviciul de analiză a vânzărilor.</li>
        <li>Pentru a trimite notificări operaționale (verificare email, resetare parolă).</li>
        <li>Pentru a audita acțiunile sensibile (crearea de utilizatori, modificări de rol, importuri).</li>
      </ul>

      <h2>3. Cu cine partajăm</h2>
      <p>
        Datele rămân pe serverele noastre. Excepții: furnizori de infrastructură
        (hosting, email SMTP, procesator plăți Stripe) — toți cu contracte DPA
        conforme GDPR. Nu vindem date către terți.
      </p>

      <h2>4. Drepturile tale (GDPR)</h2>
      <ul>
        <li>Dreptul de acces — poți descărca datele tale în orice moment.</li>
        <li>Dreptul la rectificare — editezi datele din platformă.</li>
        <li>Dreptul la ștergere — contactează <a href="mailto:privacy@adeplast-saas.example">privacy@adeplast-saas.example</a>.</li>
        <li>Dreptul la portabilitate — export Excel/Word disponibil.</li>
      </ul>

      <h2>5. Cookies</h2>
      <p>
        Folosim doar cookies/localStorage strict necesare (sesiune login, preferințe UI).
        Nu folosim tracking de terți.
      </p>

      <h2>6. Contact</h2>
      <p>
        Întrebări sau cereri GDPR: <a href="mailto:privacy@adeplast-saas.example">privacy@adeplast-saas.example</a>.
      </p>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: { maxWidth: 720, margin: "0 auto", padding: 32, lineHeight: 1.6 },
  meta: { color: "#666", fontSize: 13 },
};

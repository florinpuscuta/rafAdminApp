export default function TermsPage() {
  return (
    <div style={styles.wrap}>
      <h1>Termeni și Condiții</h1>
      <p style={styles.meta}>Ultima actualizare: 20 aprilie 2026</p>

      <p>
        Utilizând <strong>Adeplast SaaS</strong> ești de acord cu acești
        termeni. Te rugăm să îi citești cu atenție.
      </p>

      <h2>1. Cine suntem</h2>
      <p>
        Adeplast SaaS este o platformă de analiză a vânzărilor Key Accounts,
        operată de <em>[Numele companiei]</em>, CUI <em>[CUI]</em>,
        cu sediul în <em>[Adresă]</em>.
      </p>

      <h2>2. Contul tău</h2>
      <ul>
        <li>Ești responsabil pentru securitatea contului tău (parolă, 2FA).</li>
        <li>Contul personal nu poate fi transferat unei terțe părți.</li>
        <li>Admin-ul unei organizații poate crea și dezactiva conturi secundare.</li>
      </ul>

      <h2>3. Ce poți face</h2>
      <ul>
        <li>Încărca și analiza datele proprii de vânzări.</li>
        <li>Invita membri ai echipei tale (în limita planului tău).</li>
        <li>Exporta datele oricând în Excel sau Word.</li>
      </ul>

      <h2>4. Ce nu ai voie</h2>
      <ul>
        <li>Încărca date care încalcă GDPR sau drepturile altora.</li>
        <li>Partaja API keys cu părți neautorizate.</li>
        <li>Abuzul infrastructurii (DDoS, brute force, scraping agresiv).</li>
      </ul>

      <h2>5. Plăți și reînnoiri</h2>
      <p>
        Planurile se reînnoiesc automat la sfârșitul fiecărei perioade de
        facturare (lunar / anual). Poți anula oricând; accesul continuă
        până la sfârșitul perioadei plătite. Fără rambursări parțiale.
      </p>

      <h2>6. Disponibilitate</h2>
      <p>
        Ne străduim să menținem 99% uptime, dar nu garantăm serviciu continuu.
        Nu suntem răspunzători pentru daune indirecte rezultate din indisponibilitate.
      </p>

      <h2>7. Modificări</h2>
      <p>
        Putem actualiza acești termeni. Te anunțăm prin email cu cel puțin
        30 zile înainte de modificări substanțiale.
      </p>

      <h2>8. Legislație aplicabilă</h2>
      <p>
        Se aplică legea română. Disputele se rezolvă la instanțele competente
        din <em>[Oraș]</em>, România.
      </p>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: { maxWidth: 720, margin: "0 auto", padding: 32, lineHeight: 1.6 },
  meta: { color: "#666", fontSize: 13 },
};

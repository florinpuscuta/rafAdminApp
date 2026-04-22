import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Un nume unic pt identificare în Sentry + în UI ("dashboard", "sales"). */
  name?: string;
  /** Custom fallback — primește error + reset. Dacă lipsește, folosim default-ul. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
  eventId: string | null;
}

/**
 * Error boundary cu:
 *   - Sentry hook opportunistic (dacă `window.Sentry` e prezent → captureException)
 *   - Fallback UI cu butoane Reîncearcă / Acasă / (în dev) stack
 *   - `name` logat în context, util când e folosit per-route
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, eventId: null };

  static getDerivedStateFromError(error: Error): State {
    return { error, eventId: null };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    const name = this.props.name ?? "root";
    console.error(`[ErrorBoundary:${name}]`, error, info);

    // Raport Sentry dacă SDK-ul e injectat pe window (optional — dacă user-ul
    // adaugă @sentry/browser via script tag sau Sentry React la un moment dat).
    const w = window as unknown as {
      Sentry?: {
        captureException?: (err: unknown, ctx?: unknown) => string | void;
      };
    };
    if (w.Sentry?.captureException) {
      try {
        const id = w.Sentry.captureException(error, {
          tags: { boundary: name },
          extra: { componentStack: info.componentStack },
        });
        if (typeof id === "string") this.setState({ eventId: id });
      } catch {
        /* non-critical */
      }
    }
  }

  reset = () => this.setState({ error: null, eventId: null });

  goHome = () => {
    this.reset();
    // Folosim window.location pt a forța reset complet al stării app-ului,
    // nu doar navigarea SPA — dacă eroarea a venit din Context/state corupt,
    // reload curat rezolvă.
    window.location.href = "/";
  };

  render() {
    const { error, eventId } = this.state;
    if (error) {
      if (this.props.fallback) return this.props.fallback(error, this.reset);
      return (
        <div style={styles.wrap}>
          <h2 style={{ margin: "0 0 10px" }}>A apărut o eroare</h2>
          <p style={{ color: "var(--fg-muted, #666)", fontSize: 14 }}>
            Ceva a mers prost pe această pagină. Poți reîncerca sau reveni la dashboard.
          </p>
          <pre style={styles.pre}>{String(error.message ?? error)}</pre>
          {eventId && (
            <p style={styles.eventId}>
              Referință eroare: <code>{eventId}</code>
            </p>
          )}
          <div style={styles.actions}>
            <button onClick={this.reset} style={styles.btnPrimary}>Reîncearcă</button>
            <button onClick={this.goHome} style={styles.btnGhost}>Înapoi la Dashboard</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const styles: Record<string, React.CSSProperties> = {
  wrap: { padding: 32, maxWidth: 620, margin: "0 auto" },
  pre: {
    padding: 12,
    background: "#fff5f5",
    border: "1px solid #fbd0d0",
    borderRadius: 4,
    fontSize: 12,
    overflowX: "auto",
    color: "#b00020",
    marginTop: 12,
  },
  eventId: { marginTop: 8, fontSize: 12, color: "var(--fg-muted, #666)" },
  actions: { display: "flex", gap: 8, marginTop: 16 },
  btnPrimary: {
    padding: "8px 16px", fontSize: 14, cursor: "pointer",
    background: "#2563eb", color: "#fff", border: "none", borderRadius: 4,
  },
  btnGhost: {
    padding: "8px 16px", fontSize: 14, cursor: "pointer",
    background: "transparent", color: "var(--fg, inherit)",
    border: "1px solid var(--border, #d0d0d0)", borderRadius: 4,
  },
};

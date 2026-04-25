/**
 * Sentry initialization — LAZY: SDK-ul e descărcat DOAR când DSN-ul e setat.
 * Dev builds fără DSN nu includ Sentry în bundle-ul principal — Vite face
 * code-split via dynamic `import()` și încarcă chunk-ul Sentry doar când
 * `initSentry()` rulează cu DSN.
 *
 * Matches backend pattern (also opt-in via env). Frontend env var e
 * `VITE_SENTRY_DSN` (prefixul VITE_ îl face vizibil în bundle-ul client).
 */
interface InitOptions {
  dsn?: string;
  environment?: string;
  release?: string;
  tracesSampleRate?: number;
}

type SentryModule = typeof import("@sentry/react");

let initialized = false;
let sentryPromise: Promise<SentryModule | null> | null = null;

export function initSentry(opts: InitOptions = {}): void {
  if (initialized) return;
  const dsn = opts.dsn ?? import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;

  initialized = true;
  const environment = opts.environment ?? import.meta.env.VITE_SENTRY_ENVIRONMENT ?? "production";
  const release = opts.release ?? import.meta.env.VITE_APP_VERSION ?? "dev";
  const envRate = Number.parseFloat(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? "");
  const tracesSampleRate =
    opts.tracesSampleRate ?? (Number.isFinite(envRate) ? envRate : 1.0);

  // Dynamic import — chunk-ul Sentry se încarcă async doar acum (dev build
  // fără DSN nu-l include niciodată). Vite creează un JS chunk separat.
  sentryPromise = import("@sentry/react")
    .then((Sentry) => {
      Sentry.init({
        dsn,
        environment,
        release,
        tracesSampleRate,
        integrations: [Sentry.browserTracingIntegration()],
        ignoreErrors: [
          "ResizeObserver loop limit exceeded",
          "ResizeObserver loop completed with undelivered notifications",
          "Non-Error promise rejection captured",
        ],
      });
      // Expose pe window pentru ErrorBoundary opportunistic hook.
      (window as unknown as { Sentry: SentryModule }).Sentry = Sentry;
      return Sentry;
    })
    .catch((err) => {
      // Nu crăpăm app-ul dacă chunk-ul Sentry nu se poate încărca (offline, etc).
      console.warn("Sentry load failed:", err);
      return null;
    });
}

/** Atașează identitatea user-ului curent la toate event-urile Sentry. */
export function setSentryUser(
  user: { id: string; email?: string; tenantId?: string } | null,
): void {
  if (!sentryPromise) return;
  void sentryPromise.then((Sentry) => {
    if (!Sentry) return;
    if (user) {
      Sentry.setUser({ id: user.id, email: user.email });
      if (user.tenantId) Sentry.setTag("tenant_id", user.tenantId);
    } else {
      Sentry.setUser(null);
      Sentry.setTag("tenant_id", null);
    }
  });
}

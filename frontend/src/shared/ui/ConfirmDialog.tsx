import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

interface ConfirmAPI {
  confirm: (opts: ConfirmOptions) => Promise<boolean>;
}

const ConfirmContext = createContext<ConfirmAPI | null>(null);

interface PendingState extends ConfirmOptions {
  resolve: (ok: boolean) => void;
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingState | null>(null);
  const titleId = useRef(`cf-title-${Math.random().toString(36).slice(2, 9)}`).current;
  const msgId = useRef(`cf-msg-${Math.random().toString(36).slice(2, 9)}`).current;
  const previousFocusRef = useRef<HTMLElement | null>(null);

  const confirm = useCallback((opts: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      // Salvăm elementul focusat înainte de deschidere ca să-l restaurăm la close.
      previousFocusRef.current = document.activeElement as HTMLElement | null;
      setPending({ ...opts, resolve });
    });
  }, []);

  const handleConfirm = useCallback(() => {
    pending?.resolve(true);
    setPending(null);
    previousFocusRef.current?.focus?.();
  }, [pending]);

  const handleCancel = useCallback(() => {
    pending?.resolve(false);
    setPending(null);
    previousFocusRef.current?.focus?.();
  }, [pending]);

  // Escape key = cancel (pattern standard pentru dialogs modale).
  useEffect(() => {
    if (!pending) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") handleCancel();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [pending, handleCancel]);

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {pending && (
        <div
          style={styles.backdrop}
          onClick={handleCancel}
          role="presentation"
        >
          <div
            style={styles.dialog}
            onClick={(e) => e.stopPropagation()}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby={pending.title ? titleId : undefined}
            aria-describedby={msgId}
          >
            {pending.title && <h3 id={titleId} style={styles.title}>{pending.title}</h3>}
            <p id={msgId} style={styles.message}>{pending.message}</p>
            <div style={styles.actions}>
              <button onClick={handleCancel} style={styles.btnCancel}>
                {pending.cancelLabel ?? "Anulează"}
              </button>
              <button
                onClick={handleConfirm}
                style={pending.danger ? styles.btnDanger : styles.btnConfirm}
                autoFocus
              >
                {pending.confirmLabel ?? "Confirmă"}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): ConfirmAPI["confirm"] {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used inside <ConfirmProvider>");
  return ctx.confirm;
}

const styles: Record<string, React.CSSProperties> = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.5)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 10001,
  },
  dialog: {
    background: "#fff",
    padding: 24,
    borderRadius: 8,
    maxWidth: 420,
    width: "90%",
    boxShadow: "0 10px 40px rgba(0,0,0,0.2)",
  },
  title: { margin: "0 0 12px", fontSize: 17 },
  message: { margin: "0 0 20px", fontSize: 14, lineHeight: 1.5, color: "#333" },
  actions: { display: "flex", justifyContent: "flex-end", gap: 8 },
  btnCancel: {
    padding: "8px 16px",
    fontSize: 14,
    cursor: "pointer",
    background: "#fff",
    border: "1px solid #d0d0d0",
    borderRadius: 4,
  },
  btnConfirm: {
    padding: "8px 16px",
    fontSize: 14,
    cursor: "pointer",
    background: "#2563eb",
    color: "#fff",
    border: "none",
    borderRadius: 4,
  },
  btnDanger: {
    padding: "8px 16px",
    fontSize: 14,
    cursor: "pointer",
    background: "#b00020",
    color: "#fff",
    border: "none",
    borderRadius: 4,
  },
};

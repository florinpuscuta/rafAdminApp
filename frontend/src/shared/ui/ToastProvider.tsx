import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

type ToastKind = "success" | "error" | "info";

interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastAPI {
  success: (msg: string) => void;
  error: (msg: string) => void;
  info: (msg: string) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastAPI | null>(null);

let _seq = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((kind: ToastKind, message: string) => {
    const id = ++_seq;
    setToasts((prev) => [...prev, { id, kind, message }]);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const api: ToastAPI = {
    success: (m) => push("success", m),
    error: (m) => push("error", m),
    info: (m) => push("info", m),
    dismiss,
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div style={styles.stack}>
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  useEffect(() => {
    const ttl = toast.kind === "error" ? 6000 : 4000;
    const timer = setTimeout(onDismiss, ttl);
    return () => clearTimeout(timer);
  }, [onDismiss, toast.kind]);

  const kindStyle = kindStyles[toast.kind];
  return (
    <div style={{ ...styles.toast, ...kindStyle }} onClick={onDismiss}>
      {toast.message}
    </div>
  );
}

export function useToast(): ToastAPI {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

const styles: Record<string, React.CSSProperties> = {
  stack: {
    position: "fixed",
    top: 16,
    right: 16,
    zIndex: 9999,
    display: "flex",
    flexDirection: "column",
    gap: 8,
    maxWidth: 400,
  },
  toast: {
    padding: "10px 14px",
    borderRadius: 6,
    fontSize: 14,
    cursor: "pointer",
    boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
    animation: "toast-in 0.2s ease-out",
  },
};

const kindStyles: Record<ToastKind, React.CSSProperties> = {
  success: { background: "#e6ffed", border: "1px solid #a6d8a8", color: "#065f13" },
  error: { background: "#ffebee", border: "1px solid #f5a2a8", color: "#b00020" },
  info: { background: "#eff6ff", border: "1px solid #93c5fd", color: "#1e40af" },
};

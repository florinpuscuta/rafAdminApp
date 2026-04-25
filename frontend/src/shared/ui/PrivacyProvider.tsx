import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface PrivacyAPI {
  hideAgents: boolean;
  setHideAgents: (v: boolean) => void;
  toggleHideAgents: () => void;
  maskAgent: (name: string | null | undefined) => string;
}

const PrivacyContext = createContext<PrivacyAPI | null>(null);
const LS_KEY = "adeplast_privacy_hide_agents";

function hashCode(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function PrivacyProvider({ children }: { children: ReactNode }) {
  const [hideAgents, setHideAgentsState] = useState<boolean>(() => {
    try {
      return localStorage.getItem(LS_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    document.body.classList.toggle("privacy-agents", hideAgents);
    try {
      localStorage.setItem(LS_KEY, hideAgents ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [hideAgents]);

  const setHideAgents = useCallback((v: boolean) => setHideAgentsState(v), []);
  const toggleHideAgents = useCallback(
    () => setHideAgentsState((p) => !p),
    [],
  );

  const maskAgent = useCallback(
    (name: string | null | undefined) => {
      if (!hideAgents) return name ?? "";
      if (!name) return "—";
      const idx = (hashCode(name) % 26) + 1;
      const letter = String.fromCharCode(64 + idx);
      return `Agent ${letter}`;
    },
    [hideAgents],
  );

  const value = useMemo<PrivacyAPI>(
    () => ({ hideAgents, setHideAgents, toggleHideAgents, maskAgent }),
    [hideAgents, setHideAgents, toggleHideAgents, maskAgent],
  );

  return (
    <PrivacyContext.Provider value={value}>{children}</PrivacyContext.Provider>
  );
}

export function usePrivacy(): PrivacyAPI {
  const ctx = useContext(PrivacyContext);
  if (!ctx) throw new Error("usePrivacy must be used within PrivacyProvider");
  return ctx;
}

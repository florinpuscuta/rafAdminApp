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
  /** True dacă modul confidențial e forțat (ex. user cu rol `viewer`).
   *  Toggle-ul din Settings devine read-only când e true. */
  forced: boolean;
  setForced: (v: boolean) => void;
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
  const [forced, setForced] = useState<boolean>(false);

  // Effective: dacă e forțat (viewer role), mereu ON; altfel preferința user.
  const effectiveHide = forced || hideAgents;

  useEffect(() => {
    document.body.classList.toggle("privacy-agents", effectiveHide);
    try {
      localStorage.setItem(LS_KEY, hideAgents ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [effectiveHide, hideAgents]);

  const setHideAgents = useCallback((v: boolean) => setHideAgentsState(v), []);
  const toggleHideAgents = useCallback(() => {
    if (forced) return; // no-op pentru viewer
    setHideAgentsState((p) => !p);
  }, [forced]);

  const maskAgent = useCallback(
    (name: string | null | undefined) => {
      if (!effectiveHide) return name ?? "";
      if (!name) return "—";
      const idx = (hashCode(name) % 26) + 1;
      const letter = String.fromCharCode(64 + idx);
      return `Agent ${letter}`;
    },
    [effectiveHide],
  );

  const value = useMemo<PrivacyAPI>(
    () => ({
      hideAgents: effectiveHide,
      setHideAgents, toggleHideAgents, maskAgent,
      forced, setForced,
    }),
    [effectiveHide, setHideAgents, toggleHideAgents, maskAgent, forced],
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

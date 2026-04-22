import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type CompanyScope = "adeplast" | "sika" | "sikadp";

interface CompanyScopeAPI {
  scope: CompanyScope;
  setScope: (s: CompanyScope) => void;
  inSettings: boolean;
  enterSettings: () => void;
  exitSettings: () => void;
}

const CompanyScopeContext = createContext<CompanyScopeAPI | null>(null);
const LS_KEY = "adeplast_company_scope";

function isValidScope(value: unknown): value is CompanyScope {
  return value === "adeplast" || value === "sika" || value === "sikadp";
}

export function CompanyScopeProvider({ children }: { children: ReactNode }) {
  const [scope, setScopeState] = useState<CompanyScope>(() => {
    const saved = localStorage.getItem(LS_KEY);
    return isValidScope(saved) ? saved : "adeplast";
  });
  // "Settings panel" mode — în legacy, click pe ⚙ ascunde scope-ul companiei
  // și afișează un meniu admin. Nu persistăm; mereu pornim pe compania curentă.
  const [inSettings, setInSettings] = useState(false);

  useEffect(() => {
    localStorage.setItem(LS_KEY, scope);
  }, [scope]);

  const setScope = useCallback((s: CompanyScope) => {
    setScopeState(s);
    setInSettings(false);
  }, []);
  const enterSettings = useCallback(() => setInSettings(true), []);
  const exitSettings = useCallback(() => setInSettings(false), []);

  return (
    <CompanyScopeContext.Provider
      value={{ scope, setScope, inSettings, enterSettings, exitSettings }}
    >
      {children}
    </CompanyScopeContext.Provider>
  );
}

export function useCompanyScope(): CompanyScopeAPI {
  const ctx = useContext(CompanyScopeContext);
  if (!ctx) throw new Error("useCompanyScope must be used inside <CompanyScopeProvider>");
  return ctx;
}

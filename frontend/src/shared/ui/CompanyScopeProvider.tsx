import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { getActiveOrgId, setActiveOrgId } from "../api";
import { getMyOrganizations, type OrganizationMembership } from "../../features/orgs/api";

export type CompanyScope = "adeplast" | "sika" | "sikadp";

interface CompanyScopeAPI {
  scope: CompanyScope;
  setScope: (s: CompanyScope) => void;
  inSettings: boolean;
  enterSettings: () => void;
  exitSettings: () => void;
  // Orgele user-ului — folosit pentru a mapa scope → org_id la setare.
  memberships: OrganizationMembership[];
}

const CompanyScopeContext = createContext<CompanyScopeAPI | null>(null);
const LS_KEY = "adeplast_company_scope";

function isValidScope(value: unknown): value is CompanyScope {
  return value === "adeplast" || value === "sika" || value === "sikadp";
}


/** Mapeaza un nume canonic de scope la slug-ul orgei corespondente. */
function slugForScope(s: CompanyScope): string {
  if (s === "adeplast") return "adeplast";
  if (s === "sika") return "sika";
  return ""; // sikadp = consolidated → "all" sentinel
}


export function CompanyScopeProvider({ children }: { children: ReactNode }) {
  const [scope, setScopeState] = useState<CompanyScope>(() => {
    const saved = localStorage.getItem(LS_KEY);
    return isValidScope(saved) ? saved : "adeplast";
  });
  const [inSettings, setInSettings] = useState(false);
  const [memberships, setMemberships] = useState<OrganizationMembership[]>([]);

  useEffect(() => {
    localStorage.setItem(LS_KEY, scope);
  }, [scope]);

  // La login / mount, preluam organizatiile membre si sincronizam
  // X-Active-Org-Id cu scope-ul curent.
  useEffect(() => {
    let cancelled = false;
    getMyOrganizations()
      .then((r) => {
        if (cancelled) return;
        setMemberships(r.items);
        syncActiveOrgId(scope, r.items);
      })
      .catch(() => {
        // Silentios — daca nu suntem logati, header-ul ramane neschimbat.
      });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function syncActiveOrgId(s: CompanyScope, list: OrganizationMembership[]) {
    if (s === "sikadp") {
      // Consolidated view → backend recunoaste sentinelul "all".
      setActiveOrgId("all");
      return;
    }
    const target = slugForScope(s);
    const found = list.find((m) => m.slug === target);
    if (found) {
      setActiveOrgId(found.organizationId);
    } else {
      // Fallback: nu-l atingem (ramane default-ul user-ului).
      setActiveOrgId(null);
    }
  }

  const setScope = useCallback((s: CompanyScope) => {
    const previous = getActiveOrgId();
    setScopeState(s);
    setInSettings(false);
    syncActiveOrgId(s, memberships);
    // Daca header-ul X-Active-Org-Id se schimba, reincarcam datele —
    // toate paginile sunt mounted cu deps care nu cunosc despre header.
    const next = s === "sikadp" ? "all"
      : memberships.find((m) => m.slug === slugForScope(s))?.organizationId ?? null;
    if (previous !== next) {
      window.setTimeout(() => window.location.reload(), 50);
    }
  }, [memberships]);

  const enterSettings = useCallback(() => setInSettings(true), []);
  const exitSettings = useCallback(() => setInSettings(false), []);

  return (
    <CompanyScopeContext.Provider
      value={{ scope, setScope, inSettings, enterSettings, exitSettings, memberships }}
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

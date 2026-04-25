import { useEffect, useState, type CSSProperties } from "react";

import { getActiveOrgId, setActiveOrgId } from "../../shared/api";
import { getMyOrganizations, type OrganizationMembership } from "./api";


/**
 * Switcher in header: dropdown cu org-urile la care e membru user-ul.
 * Selectia se persista in localStorage si e trimisa via X-Active-Org-Id la
 * fiecare request (vezi shared/api.ts::rawFetch).
 */
export default function OrgSwitcher() {
  const [memberships, setMemberships] = useState<OrganizationMembership[]>([]);
  const [activeId, setActiveIdState] = useState<string | null>(getActiveOrgId());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getMyOrganizations()
      .then((r) => {
        if (cancelled) return;
        setMemberships(r.items);
        // Daca nu avem activeId in storage, setam fallback la default.
        if (!getActiveOrgId() && r.items.length > 0) {
          const def = r.items.find((m) => m.isDefault) ?? r.items[0];
          setActiveOrgId(def.organizationId);
          setActiveIdState(def.organizationId);
        }
      })
      .catch(() => {
        // Silentios — switcher-ul ramane gol; user-ul lucreaza pe default.
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading || memberships.length === 0) return null;
  if (memberships.length === 1) {
    return (
      <span style={styles.singleOrg} title={memberships[0].name}>
        {memberships[0].name}
      </span>
    );
  }

  function onChange(value: string) {
    setActiveOrgId(value);
    setActiveIdState(value);
    window.location.reload();
  }

  // "all" = sentinel pentru consolidated view cross-org (vezi backend
  // get_current_org_ids — accept "all" header → toate org-urile user-ului).
  return (
    <select
      value={activeId ?? memberships[0].organizationId}
      onChange={(e) => onChange(e.target.value)}
      style={styles.select}
      title="Organizatia activa"
    >
      {memberships.map((m) => (
        <option key={m.organizationId} value={m.organizationId}>
          {m.name}{m.kind !== "production" ? ` (${m.kind})` : ""}
        </option>
      ))}
      <option value="all">⊕ Consolidat (toate)</option>
    </select>
  );
}


const styles: Record<string, CSSProperties> = {
  select: {
    background: "var(--card)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "5px 10px",
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  singleOrg: {
    fontSize: 12,
    fontWeight: 600,
    color: "var(--muted)",
    padding: "5px 10px",
  },
};

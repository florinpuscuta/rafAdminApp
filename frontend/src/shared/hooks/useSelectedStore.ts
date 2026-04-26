import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "magazin:selected_name";

/**
 * Hook care păstrează numele magazinului selectat sincronizat între
 * `/analiza/magazin` și `/analiza/magazin-dashboard`.
 *
 * Source of truth = numele brut (`RawSale.client`), așa cum îl folosește
 * pagina Analiza. Dashboard-ul (care lucrează cu `Store.id` UUID) face
 * lookup invers prin lista lui de stores.
 *
 * - Citim din localStorage la mount.
 * - Scriem la fiecare set.
 * - Listener pe evenimentul `storage` (sincronizare între tab-uri).
 */
export function useSelectedStore(): {
  selectedStore: string;
  setSelectedStore: (name: string) => void;
} {
  const [selectedStore, setSelectedStoreState] = useState<string>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) ?? "";
    } catch {
      return "";
    }
  });

  const setSelectedStore = useCallback((name: string) => {
    setSelectedStoreState(name);
    try {
      if (name) {
        localStorage.setItem(STORAGE_KEY, name);
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      /* localStorage indisponibil — ignoăm, state-ul în memorie e suficient */
    }
  }, []);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        setSelectedStoreState(e.newValue ?? "");
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  return { selectedStore, setSelectedStore };
}

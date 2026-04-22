import { useCallback, useMemo, useState } from "react";

/**
 * Hook pentru multi-select peste un set de ID-uri vizibile. Păstrează doar
 * ID-urile care sunt și în setul vizibil curent — când filtrezi lista, selecția
 * exclusă automat (nu rămân fantome după filter).
 */
export function useBulkSelection(visibleIds: string[]) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // Curăță automat ID-urile care nu mai sunt vizibile după schimbări în listă/filtru.
  const effectiveSelected = useMemo(() => {
    const visible = new Set(visibleIds);
    const out = new Set<string>();
    selected.forEach((id) => {
      if (visible.has(id)) out.add(id);
    });
    return out;
  }, [visibleIds, selected]);

  const toggle = useCallback((id: string) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleAll = useCallback(() => {
    setSelected((s) => {
      const visible = new Set(visibleIds);
      // Dacă toate cele vizibile sunt deja selectate → deselect all
      const allSelected = visibleIds.length > 0 && visibleIds.every((id) => s.has(id));
      if (allSelected) {
        const next = new Set(s);
        visible.forEach((id) => next.delete(id));
        return next;
      }
      const next = new Set(s);
      visible.forEach((id) => next.add(id));
      return next;
    });
  }, [visibleIds]);

  const clear = useCallback(() => setSelected(new Set()), []);

  const allVisibleSelected =
    visibleIds.length > 0 && visibleIds.every((id) => effectiveSelected.has(id));

  return {
    selected: effectiveSelected,
    count: effectiveSelected.size,
    isSelected: (id: string) => effectiveSelected.has(id),
    toggle,
    toggleAll,
    clear,
    allVisibleSelected,
  };
}

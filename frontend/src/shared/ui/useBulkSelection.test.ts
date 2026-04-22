import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useBulkSelection } from "./useBulkSelection";

describe("useBulkSelection", () => {
  it("starts empty", () => {
    const { result } = renderHook(() => useBulkSelection(["a", "b", "c"]));
    expect(result.current.count).toBe(0);
    expect(result.current.allVisibleSelected).toBe(false);
  });

  it("toggle adds and removes", () => {
    const { result } = renderHook(() => useBulkSelection(["a", "b"]));
    act(() => result.current.toggle("a"));
    expect(result.current.isSelected("a")).toBe(true);
    expect(result.current.count).toBe(1);
    act(() => result.current.toggle("a"));
    expect(result.current.isSelected("a")).toBe(false);
  });

  it("toggleAll selects all visible, toggles back when all selected", () => {
    const { result } = renderHook(() => useBulkSelection(["a", "b", "c"]));
    act(() => result.current.toggleAll());
    expect(result.current.count).toBe(3);
    expect(result.current.allVisibleSelected).toBe(true);
    act(() => result.current.toggleAll());
    expect(result.current.count).toBe(0);
  });

  it("filters out ids that become invisible", () => {
    const { result, rerender } = renderHook(
      ({ ids }: { ids: string[] }) => useBulkSelection(ids),
      { initialProps: { ids: ["a", "b", "c"] } },
    );
    act(() => result.current.toggleAll());
    expect(result.current.count).toBe(3);

    // Schimbăm lista — doar "b" mai e vizibil
    rerender({ ids: ["b"] });
    expect(result.current.count).toBe(1);
    expect(result.current.isSelected("b")).toBe(true);
    expect(result.current.isSelected("a")).toBe(false);
  });

  it("clear() empties the selection", () => {
    const { result } = renderHook(() => useBulkSelection(["a", "b"]));
    act(() => result.current.toggleAll());
    expect(result.current.count).toBe(2);
    act(() => result.current.clear());
    expect(result.current.count).toBe(0);
  });
});
